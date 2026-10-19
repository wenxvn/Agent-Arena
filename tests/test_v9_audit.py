"""V9 审计与指标修正层的可复算测试。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agent_arena.v7.metrics.schema import MetricStatus
from agent_arena.v8.metrics import metric_schema_hash
from agent_arena.v8.prompts import system_prompt as v8_system_prompt
from agent_arena.v9.audit import V8_ROOT, official_rows
from agent_arena.v9.baseline_run import oracle_cases
from agent_arena.v9.metrics import empty_status, rescore_v8
from agent_arena.v9.prompts import prompt_hashes, system_prompt
from agent_arena.worlds.scenario_v8.catalog import (
    CONDITIONS,
    MAP_IDS,
    create_environment,
    rule_hash,
    scenario_hash,
    source_hash,
)
from agent_arena.worlds.scenario_v8.models import V8Action
from agent_arena.worlds.scenario_v8.oracle import normalize_action_payload

#: runs/ 是本地生成物、不入 Git；CI/干净 checkout 没有 90 局历史数据时跳过。
pytestmark = pytest.mark.skipif(
    not (V8_ROOT / "results_90.csv").exists(),
    reason="runs/v8 历史局不在 Git 中（本地生成物）",
)


def test_official_rows_are_ninety_unique_instances() -> None:
    rows = official_rows()
    assert len(rows) == 90
    keys = {(row.map_id, row.replicate_id) for row in rows}
    assert len(keys) == 90
    assert len({row.run_id for row in rows}) == 90
    assert {row.map_id for row in rows} == set(MAP_IDS)
    assert sum((row.cost for row in rows), Decimal(0)) == Decimal("1.27464628")


def test_registry_success_counts_match_recomputation() -> None:
    rows = official_rows()
    assert sum(1 for row in rows if row.success) == 17
    zero = {map_id for map_id in MAP_IDS if not any(r.map_id == map_id and r.success for r in rows)}
    assert len(zero) == 22
    full = {
        map_id
        for map_id in MAP_IDS
        if sum(1 for r in rows if r.map_id == map_id and r.success) == 3
    }
    assert full == {"MAP-06", "MAP-15", "MAP-21"}


def test_frozen_hashes_match_current_runtime() -> None:
    from agent_arena.v8.prompts import system_prompt as v8_prompt
    from agent_arena.v9.prompts import V9_PUBLIC_ADDENDA

    for map_id in MAP_IDS:
        environment = create_environment(map_id)
        budget = 60 if map_id == "MAP-12" else {"简单": 30, "中等": 38, "困难": 46}[
            environment.level
        ]
        hashes = prompt_hashes(environment, decision_budget=budget)
        assert hashes["v8_compat"] == hashes["v8_compat"]
        assert hashes["v8_compat"] == __import__("hashlib").sha256(
            v8_prompt(environment, decision_budget=budget).encode("utf-8")
        ).hexdigest()
        if map_id in V9_PUBLIC_ADDENDA:
            assert hashes["v9_fixed"] != hashes["v8_compat"]
        else:
            assert hashes["v9_fixed"] == hashes["v8_compat"]
        assert len(scenario_hash(map_id)) == 64
        assert len(rule_hash(map_id)) == 64
        assert len(source_hash(map_id)) == 64
        assert len(metric_schema_hash(map_id)) == 64


def test_v9_prompt_is_v8_compat_without_addenda() -> None:
    environment = create_environment("MAP-01")
    assert system_prompt(environment, decision_budget=30, arm="v8_compat") == v8_system_prompt(
        environment, decision_budget=30
    )
    assert (
        system_prompt(environment, decision_budget=30, arm="v9_fixed")
        == v8_system_prompt(environment, decision_budget=30)
    )


def test_budget_censoring_is_not_not_applicable() -> None:
    assert empty_status("decision_budget_reached") is MetricStatus.CENSORED
    assert empty_status("censored") is MetricStatus.CENSORED
    assert empty_status("failure") is MetricStatus.NOT_APPLICABLE
    assert empty_status("success") is MetricStatus.NOT_APPLICABLE


def test_rescore_counts_changes_without_touching_values() -> None:
    summary = rescore_v8()
    assert summary["runs"] == 90
    assert summary["maps"] == 30
    assert summary["changed_status_count"] == 28
    assert all(key.endswith("->censored") for key in summary["changes_by_metric"])


def test_every_map_has_replayable_oracle_cases() -> None:
    for map_id in MAP_IDS:
        cases = oracle_cases(map_id)
        assert cases, map_id
        for case in cases:
            environment = create_environment(map_id, seed=int(case.get("seed", 0)))
            for payload in case["actions"]:
                action = V8Action.model_validate(
                    normalize_action_payload(payload), strict=True
                )
                environment.step(action)
                if environment.is_terminal:
                    break
            assert environment.is_success, (
                f"{map_id}:{case.get('trace_id')} "
                f"{environment.status.value}/{environment.terminal_reason}"
            )


def test_conditions_are_the_registered_six() -> None:
    assert len(CONDITIONS) == 6
    assert set(CONDITIONS) == {
        "MAP-08",
        "MAP-16",
        "MAP-18",
        "MAP-22",
        "MAP-26",
        "MAP-30",
    }
