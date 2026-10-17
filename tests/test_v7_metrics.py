"""Schema, registry, and missing-value contract tests for the V7 layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_arena.v7.metrics import registry
from agent_arena.v7.metrics.common import (
    counted,
    episode_is_censored,
    legal_action_rate,
    ratio,
)
from agent_arena.v7.metrics.schema import (
    MetricKind,
    MetricStatus,
    MetricValue,
    TraceFormatError,
    load_trace,
    parse_trace_rows,
)

MAP_IDS = tuple(f"MAP-{index:02d}" for index in range(1, 31))
RUNTIME_MAPS = {"MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30"}


def _rows(
    map_id: str = "MAP-22",
    instance_id: str = "synthetic",
    *,
    condition: str = "history5_graph_memory",
    terminal: bool = True,
    terminal_reason: str = "RETURNED_TO_CAMP_WITH_RUIN_RECORD",
    results: tuple[str, ...] = (),
    final: dict | None = None,
) -> list[dict]:
    header = {
        "event": "trace_header",
        "map_id": map_id,
        "instance_id": instance_id,
        "condition_id": condition,
        "seed": 0,
        "scenario_hash": "synthetic-hash",
        "provider": "offline",
        "model": "test",
    }
    rows: list[dict] = [header]
    observation: dict = {"tick": 0}
    for index, result in enumerate(results):
        after = dict(observation)
        rows.append(
            {
                "event": "decision",
                "decision_index": index,
                "action": {"tool": "wait"},
                "result": result,
                "observation_before": observation,
                "observation_after": after,
                "invalid_output_reason": None,
            }
        )
        observation = after
    observation = dict(final or observation)
    observation.setdefault("terminal", terminal)
    observation.setdefault("terminal_reason", terminal_reason)
    rows.append(
        {
            "event": "decision",
            "decision_index": len(results),
            "action": {"tool": "wait"},
            "result": "TERMINAL",
            "observation_before": observation,
            "observation_after": observation,
            "invalid_output_reason": None,
        }
    )
    return rows


def _record(**kwargs):
    return parse_trace_rows(_rows(**kwargs), source="synthetic")


def test_registry_covers_all_thirty_maps_with_frozen_counts() -> None:
    specs = registry.all_specs()
    assert len(specs) == 154
    assert {spec.map_id for spec in specs} == set(MAP_IDS)
    assert len([spec for spec in specs if spec.implemented]) == 44
    assert len([spec for spec in specs if not spec.implemented]) == 110
    assert set(registry.implemented_map_ids()) == RUNTIME_MAPS


def test_metric_ids_are_unique_prefixed_and_documented() -> None:
    ids = [spec.metric_id for spec in registry.all_specs()]
    assert len(ids) == len(set(ids))
    for spec in registry.all_specs():
        assert spec.metric_id.startswith(spec.map_id.replace("-", "").lower() + ".")
        assert spec.map_id in spec.doc_ref
        assert spec.construct_name
        assert spec.formula
        assert spec.valid_range
        assert spec.source_events
        assert spec.missing_rule
        assert spec.censor_rule


def test_every_map_declares_primary_guardrail_and_diagnostic() -> None:
    for map_id in MAP_IDS:
        kinds = {spec.kind for spec in registry.specs_for(map_id)}
        assert MetricKind.PRIMARY in kinds, map_id
        assert MetricKind.GUARDRAIL in kinds, map_id
        assert MetricKind.DIAGNOSTIC in kinds, map_id


def test_valid_range_matches_the_declared_unit() -> None:
    for spec in registry.all_specs():
        if spec.unit == "比例 0..1":
            assert spec.valid_range == "0..1", spec.metric_id
        elif spec.unit == "0/1":
            assert spec.valid_range == "0 或 1", spec.metric_id
        elif spec.unit == "水位单位":
            assert spec.valid_range.startswith("0..7.5"), spec.metric_id
        else:
            assert spec.valid_range, spec.metric_id
    signed = [spec for spec in registry.all_specs() if spec.unit in {"损失单位", "库存单位"}]
    assert signed
    assert all("可正可负" in spec.valid_range for spec in signed)


def test_design_only_map_raises_instead_of_returning_zero() -> None:
    record = _record(map_id="MAP-17", instance_id="map17_synthetic")
    with pytest.raises(NotImplementedError, match="设计态"):
        registry.compute_metrics(record)


def test_missing_statuses_never_fabricate_zero() -> None:
    for value in (
        MetricValue.unavailable("map17.x", "missing"),
        MetricValue.not_applicable("map17.x", "no denominator"),
        MetricValue.censored("map17.x", "budget"),
        MetricValue.invalid_trace("map17.x", "bad trace"),
    ):
        assert value.value is None
        assert value.status is not MetricStatus.VALID


def test_ratio_with_zero_denominator_is_not_applicable() -> None:
    value = ratio("map22.synthetic_rate", 0, 0)
    assert value.status is MetricStatus.NOT_APPLICABLE
    assert value.value is None


def test_legal_action_rate_counts_explicit_refusals_only() -> None:
    record = _record(results=("MOVE_SUCCEEDED", "INVALID_BEARING", "TRACK_CLOSED"))
    value = legal_action_rate(record, "map22.legal_action_rate")
    assert value.status is MetricStatus.VALID
    assert value.denominator == 4
    assert value.value == 0.75


def test_episode_is_censored_uses_judge_then_terminal() -> None:
    terminal = _record(results=("MOVE_SUCCEEDED",))
    assert episode_is_censored(terminal) is False
    open_episode = _record(terminal=False, terminal_reason="RUNNING")
    assert episode_is_censored(open_episode) is True
    judged = parse_trace_rows(
        _rows(results=("MOVE_SUCCEEDED",)),
        judge={"status": "provider_error_limit"},
    )
    assert episode_is_censored(judged) is True


def test_parse_trace_rejects_missing_header_and_bad_decision() -> None:
    with pytest.raises(TraceFormatError, match="empty"):
        parse_trace_rows([])
    with pytest.raises(TraceFormatError, match="trace_header"):
        parse_trace_rows([{"event": "decision"}])
    rows = _rows(results=("MOVE_SUCCEEDED",))
    del rows[1]["decision_index"]
    with pytest.raises(TraceFormatError, match="decision_index"):
        parse_trace_rows(rows)


def test_metric_value_class_helpers_keep_status() -> None:
    assert counted("map22.x", 3).status is MetricStatus.VALID
    assert counted("map22.x", 3).value == 3


def test_load_trace_reads_jsonl_and_optional_judge(tmp_path: Path) -> None:
    trace_path = tmp_path / "agent_trace.jsonl"
    rows = _rows(results=("MOVE_SUCCEEDED",))
    trace_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    judge_path = tmp_path / "judge_metrics.json"
    judge_path.write_text(json.dumps({"status": "success", "metrics": {"gap": 0}}))
    record = load_trace(trace_path, judge_path=judge_path)
    assert record.map_id == "MAP-22"
    assert record.judge_metrics == {"gap": 0}
    assert load_trace(trace_path).map_id == "MAP-22"
