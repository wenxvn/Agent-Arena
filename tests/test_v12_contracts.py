"""V12 契约测试：schema round-trip、非法矩阵、版本指纹与模式隔离。"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError
from v12_support import simulated_config

from agent_arena.lab.contracts import (
    AGENT_CONTRACT_VERSION,
    SCHEMA_VERSION,
    AgentArm,
    AgentDecision,
    AgentEvent,
    ComparisonPolicy,
    ExperimentBudget,
    ExperimentManifest,
    ExperimentMode,
    ExperimentSpec,
    ExperimentState,
    Finding,
    LiveApproval,
    MatrixCell,
    config_hash,
)
from agent_arena.lab.registry import (
    agent_catalog,
    clear_external_agents,
    get_agent,
    registered_agent_ids,
)
from agent_arena.web.schemas import (
    OFFLINE_MODEL,
    OFFLINE_PROVIDER,
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
    RunConfig,
    RunMode,
)


def _spec(**overrides: object) -> ExperimentSpec:
    payload: dict[str, object] = {
        "name": "contract",
        "maps": ["MAP-22"],
        "agent_arms": [AgentArm(agent_id="basic.v1")],
        "provider_id": SIMULATED_PROVIDER,
        "model": SIMULATED_MODEL,
        "mode": ExperimentMode.SIMULATED,
    }
    payload.update(overrides)
    return ExperimentSpec.model_validate(payload)


def test_schema_version_is_v12() -> None:
    assert SCHEMA_VERSION == "v12-lab-1"
    assert AGENT_CONTRACT_VERSION == "agent_policy_v1"


def test_spec_round_trip_keeps_matrix_and_fingerprint() -> None:
    spec = _spec(
        maps=["MAP-22", "MAP-18"],
        agent_arms=[
            AgentArm(agent_id="basic.v1"),
            AgentArm(agent_id="memory.v1", config={"enabled": True}),
        ],
    )
    payload = spec.public_dict()
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    reloaded = json.loads(text)
    assert reloaded["schema_version"] == SCHEMA_VERSION
    assert len(spec.matrix()) == 2 * 3 * 2
    assert spec.fingerprint() == spec.fingerprint()
    assert reloaded["fingerprint"] == spec.fingerprint()


def test_matrix_is_deterministic_and_indexed() -> None:
    spec = _spec(
        maps=["MAP-22", "MAP-18"],
        agent_arms=[AgentArm(agent_id="basic.v1"), AgentArm(agent_id="planning.v1")],
    )
    first = spec.matrix()
    second = spec.matrix()
    assert [cell.as_dict() for cell in first] == [cell.as_dict() for cell in second]
    assert [cell.matrix_index for cell in first] == list(range(len(first)))
    assert len({cell.condition_key for cell in first}) == len(first)
    # 配对键忽略实验臂，只保留地图 + seed。
    assert len({cell.pairing_key for cell in first}) == 2 * 3


def test_auto_seed_selection_uses_common_three() -> None:
    spec = _spec(maps=["MAP-08", "MAP-30"])
    assert spec.resolved_seeds() == (0, 1, 2)


def test_explicit_seed_must_exist_in_every_map() -> None:
    with pytest.raises(ValidationError):
        # MAP-30 只登记 0/1/2。
        _spec(maps=["MAP-22", "MAP-30"], environment_seeds=[3])


def test_unknown_map_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _spec(maps=["MAP-99"])


def test_duplicate_arms_are_rejected() -> None:
    with pytest.raises(ValidationError):
        _spec(agent_arms=[AgentArm(agent_id="basic.v1"), AgentArm(agent_id="basic.v1")])


def test_unknown_agent_config_key_is_rejected_before_enqueue() -> None:
    with pytest.raises(ValidationError):
        _spec(agent_arms=[AgentArm(agent_id="memory.v1", config={"nope": 1})])


def test_arm_config_is_normalized_so_hash_matches_runtime() -> None:
    spec = _spec(agent_arms=[AgentArm(agent_id="memory.v1")])
    arm = spec.agent_arms[0]
    registration = get_agent("memory.v1")
    assert arm.config == registration.normalize_config({})
    assert arm.config_hash == config_hash(
        {"agent_id": "memory.v1", "config": registration.normalize_config({})}
    )


def test_simulated_mode_cannot_use_real_provider() -> None:
    with pytest.raises(ValidationError):
        _spec(provider_id="openai_compatible", model="mimo-v2.6-flash")


def test_live_mode_cannot_use_simulated_provider() -> None:
    with pytest.raises(ValidationError):
        _spec(mode=ExperimentMode.LIVE)


def test_budget_caps_are_ordered() -> None:
    with pytest.raises(ValidationError):
        _spec(
            budget=ExperimentBudget(
                per_run_cost_cap_cny=Decimal("5"), experiment_cost_cap_cny=Decimal("1")
            )
        )
    with pytest.raises(ValidationError):
        _spec(budget=ExperimentBudget(per_run_request_cap=100, experiment_request_cap=10))


def test_manifest_round_trip() -> None:
    manifest = ExperimentManifest(
        experiment_id="lab-20260101T000000Z-abcdef12",
        name="m",
        mode="simulated",
        matrix=[cell.as_dict() for cell in _spec().matrix()],
    )
    payload = manifest.as_dict()
    reloaded = ExperimentManifest.model_validate(payload)
    assert reloaded.state is ExperimentState.CREATED
    assert reloaded.terminal is False
    assert reloaded.matrix == manifest.matrix


def test_matrix_cell_from_dict_ignores_derived_key() -> None:
    cell = _spec().matrix()[0]
    payload = cell.as_dict()
    assert payload["condition_key"]
    assert MatrixCell.from_dict(payload).as_dict() == payload


def test_agent_decision_and_events_are_serializable() -> None:
    event = AgentEvent(
        kind="memory",
        event="memory_updated",
        decision_index=3,
        summary="更新 2 条",
        payload={"size": 4},
    )
    decision = AgentDecision(action={"tool": "wait"}, memory_event=event, requests=1)
    payload = decision.as_dict()
    assert payload["events"][0]["event"] == "memory_updated"
    assert payload["requests"] == 1


def test_finding_round_trip() -> None:
    finding = Finding(
        category="repeated_action_loop",
        map_id="MAP-22",
        run_id="web-20260101T000000Z-abcdef12",
        evidence_event_ids=("step-3",),
        evidence_steps=(3,),
        summary="连续 3 步重复同一动作",
    )
    payload = finding.as_dict()
    assert payload["evidence_event_ids"] == ["step-3"]
    assert Finding.model_validate(payload).category == "repeated_action_loop"


def test_comparison_policy_defaults() -> None:
    policy = ComparisonPolicy()
    assert policy.paired_by == ("map_id", "environment_seed")
    assert policy.min_paired_samples == 3
    assert policy.require_same_versions is True


def test_approval_defaults_to_unapproved() -> None:
    assert LiveApproval().approved is False
    assert _spec().approval.approved is False


def test_registry_exposes_builtin_agents() -> None:
    ids = registered_agent_ids()
    for agent_id in ("basic.v1", "memory.v1", "planning.v1", "reflection.v1"):
        assert agent_id in ids
    catalog = agent_catalog()
    assert {row["agent_id"] for row in catalog} >= {"basic.v1", "memory.v1"}
    assert all(row["default_config"] is not None for row in catalog)


def test_registry_clears_external_agents() -> None:
    clear_external_agents()
    assert "external.v1" not in registered_agent_ids()


def test_run_config_accepts_lab_agent_in_simulated_mode() -> None:
    config = simulated_config("MAP-22", "memory.v1")
    assert config.mode is RunMode.SIMULATED
    assert config.agent_config == {}


def test_run_config_rejects_unregistered_agent() -> None:
    with pytest.raises(ValidationError):
        simulated_config("MAP-22", "not-a-policy.v1")


def test_run_config_offline_semantics_unchanged() -> None:
    """V11 离线契约不能被改成“三种 Agent 的离线成绩”。"""

    with pytest.raises(ValidationError):
        RunConfig(
            map_id="MAP-22",
            environment_seed=0,
            mode=RunMode.OFFLINE,
            provider_id=OFFLINE_PROVIDER,
            model=OFFLINE_MODEL,
            agent="memory.v1",
            max_decisions=10,
            max_requests=1,
            max_input_tokens=200_000,
            max_output_tokens=8_000,
            max_cost_cny=Decimal("0.01"),
        )


def test_run_config_live_rejects_unknown_agent() -> None:
    with pytest.raises(ValidationError):
        RunConfig(
            map_id="MAP-22",
            environment_seed=0,
            mode=RunMode.LIVE,
            provider_id="openai_compatible",
            model="mimo-v2.6-flash",
            agent="mystery.v1",
            max_decisions=10,
            max_requests=10,
            max_input_tokens=200_000,
            max_output_tokens=8_000,
            max_cost_cny=Decimal("0.5"),
        )


def test_legacy_v11_config_without_agent_fields_still_loads() -> None:
    """旧 manifest 的 config 没有 agent_config/experiment_id，必须可读。"""

    legacy = {
        "schema_version": "v11-web-1",
        "map_id": "MAP-01",
        "environment_seed": 0,
        "mode": "offline",
        "provider_id": OFFLINE_PROVIDER,
        "model": OFFLINE_MODEL,
        "agent": "public_heuristic_policy",
        "policy_seed": 0,
        "max_decisions": 30,
        "max_requests": 1,
        "max_input_tokens": 200_000,
        "max_output_tokens": 8_000,
        "max_cost_cny": "0.01",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    config = RunConfig.model_validate(legacy)
    assert config.agent_config == {}
    assert config.experiment_id is None
    assert config.matrix_index is None
