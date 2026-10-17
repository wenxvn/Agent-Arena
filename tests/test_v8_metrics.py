"""V8 指标投影：五态、比例形状、schema hash 与适配器复用。"""

from __future__ import annotations

import json

import pytest

from agent_arena.v7.metrics.registry import specs_for
from agent_arena.v8.metrics import metric_schema, metric_schema_hash, project_metrics, summarize
from agent_arena.worlds.scenario_v8 import create_environment
from agent_arena.worlds.scenario_v8.models import V8Action
from agent_arena.worlds.scenario_v8.oracle import load_oracle_groups


def test_schema_matches_registry() -> None:
    schema = metric_schema("MAP-04")
    assert [item["metric_id"] for item in schema] == [
        spec.metric_id for spec in specs_for("MAP-04")
    ]
    assert metric_schema_hash("MAP-04") == metric_schema_hash("MAP-04")
    assert metric_schema_hash("MAP-04") != metric_schema_hash("MAP-05")


def test_raw_projection_records_five_states() -> None:
    class FakeEnvironment:
        map_id = "MAP-04"

        def metrics(self):
            return {
                "map04.window_hit_rate": {"numerator": 1, "denominator": 2},
                "map04.earliest_safe_crossing_delay": None,
                "map04.high_tide_entries": 0,
                "map04.stranded_ticks": True,
            }

    projected = project_metrics(FakeEnvironment(), "success")
    assert projected["map04.window_hit_rate"]["status"] == "valid"
    assert projected["map04.window_hit_rate"]["value"] == 0.5
    assert projected["map04.earliest_safe_crossing_delay"]["status"] == "not_applicable"
    assert projected["map04.stranded_ticks"]["value"] == 1
    # Registered but omitted metrics become N/A or censored, never zero.
    assert projected["map04.wait_ticks"]["status"] == "not_applicable"
    assert summarize(projected)["not_applicable"] >= 2


def test_censored_projection_uses_censored_state() -> None:
    class FakeEnvironment:
        map_id = "MAP-04"

        def metrics(self):
            return {
                "map04.window_hit_rate": {"numerator": 0, "denominator": 0},
                "map04.earliest_safe_crossing_delay": None,
            }

    projected = project_metrics(FakeEnvironment(), "censored")
    assert projected["map04.wait_ticks"]["status"] == "censored"


def test_invalid_proportion_shape_is_flagged() -> None:
    class FakeEnvironment:
        map_id = "MAP-04"

        def metrics(self):
            return {"map04.window_hit_rate": {"numerator": "bad", "denominator": 2}}

    projected = project_metrics(FakeEnvironment(), "success")
    assert projected["map04.window_hit_rate"]["status"] == "invalid_trace"


def test_unregistered_metric_is_rejected() -> None:
    class FakeEnvironment:
        map_id = "MAP-04"

        def metrics(self):
            return {"map04.not_registered": 1}

    with pytest.raises(ValueError, match="unregistered"):
        project_metrics(FakeEnvironment(), "success")


def test_raw_map_projection_after_oracle() -> None:
    groups = load_oracle_groups("MAP-04")
    environment = create_environment("MAP-04")
    actions = [row["action"] for row in next(iter(groups.values()))]
    for payload in actions:
        environment.step(V8Action.model_validate(payload, strict=True))
    projected = project_metrics(environment, "success")
    assert projected["map04.window_hit_rate"]["status"] == "valid"
    assert projected["map04.window_hit_rate"]["value"] == 1.0
    assert projected["map04.wait_ticks"]["value"] == 7


def test_adapter_projection_is_json_serialisable() -> None:
    environment = create_environment("MAP-16")
    projected = project_metrics(environment, "running")
    payload = json.dumps(projected, ensure_ascii=False, sort_keys=True)
    assert "map16.committed_ticks" in payload
