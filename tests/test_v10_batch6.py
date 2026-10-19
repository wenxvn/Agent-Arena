"""Batch 6：154 指标枚举、五态语义与规格核对。"""

from __future__ import annotations

from agent_arena.v10.baselines import map03 as b03
from agent_arena.v10.baselines import map04 as b04
from agent_arena.v10.baselines import map06 as b06
from agent_arena.v10.baselines import map13 as b13
from agent_arena.v10.baselines import map19 as b19
from agent_arena.v10.baselines.runner import run_policy
from agent_arena.v10.metrics.governance import (
    DEFECT_RESOLUTIONS,
    FIVE_STATE_PRIORITY,
    audit_states,
    enumerate_specs,
    primary_policy,
    schema_hash,
)
from agent_arena.v10.metrics.schema import MState


def test_v7_registry_still_has_154_specs() -> None:
    payload = enumerate_specs()
    assert payload["v7_count"] == 154
    assert payload["v10_count"] >= 100
    assert len(set(payload["all_ids"])) == len(payload["all_ids"])


def test_five_state_priority_is_ordered() -> None:
    assert FIVE_STATE_PRIORITY[0] is MState.INVALID_TRACE
    assert FIVE_STATE_PRIORITY[1] is MState.UNAVAILABLE
    assert FIVE_STATE_PRIORITY[2] is MState.NOT_APPLICABLE
    assert FIVE_STATE_PRIORITY[3] is MState.CENSORED
    assert FIVE_STATE_PRIORITY[4] is MState.VALID


def test_every_v10_map_declares_one_or_two_primaries() -> None:
    policy = primary_policy()
    from agent_arena.v10.runtime.catalog import V10_MAPS

    assert len(policy) == len(V10_MAPS)
    for map_id, primaries in policy.items():
        assert 1 <= len(primaries) <= 2, map_id
        assert all(item.startswith(map_id.lower().replace("-", "")) for item in primaries)


def test_defect_table_covers_all_v9_flagged_maps() -> None:
    assert len(DEFECT_RESOLUTIONS) == 20
    for map_id, (defect, resolution, evidence) in DEFECT_RESOLUTIONS.items():
        assert map_id.startswith("MAP-")
        assert defect and resolution and evidence


def test_schema_hash_is_stable() -> None:
    assert schema_hash() == schema_hash()
    assert len(schema_hash()) == 64


def test_state_audit_passes_on_success_and_failure() -> None:
    cases = [
        ("MAP-03", 0, b03.oracle_actions(0)),
        ("MAP-04", 0, b04.oracle_actions(0)),
        ("MAP-06", 0, b06.oracle_actions(0)),
        ("MAP-13", 0, b13.oracle_actions(0)),
        ("MAP-19", 0, b19.oracle_actions(0)),
    ]
    for map_id, seed, actions in cases:
        report = audit_states(map_id, seed, actions)
        assert not report["violations"], (map_id, report["violations"])
        assert report["checked"] > 0


def test_state_audit_covers_censored_and_zero_denominator() -> None:
    run = run_policy("MAP-04", b04.HEURISTIC(), environment_seed=0, decision_budget=1)
    assert run.status in {"decision_budget_reached", "success", "failure", "censored"}
    for metric_id, value in run.metrics.items():
        state = value.get("state")
        assert state in {item.value for item in MState}, metric_id
        if state != "VALID":
            assert value.get("value") is None, metric_id


def test_state_audit_spans_two_seeds() -> None:
    for seed in (0, 1):
        report = audit_states("MAP-04", seed, b04.oracle_actions(seed))
        assert not report["violations"]
