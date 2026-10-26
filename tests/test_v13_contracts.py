"""V13 契约测试：重复身份、采样登记、协议摘要与 V12 向后兼容。"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from agent_arena.lab.contracts import (
    CONTRACT_VERSION_V13,
    AgentArm,
    ChildRunLink,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
    MatrixCell,
    ProtocolManifest,
    SamplingProvenance,
)
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER


def _spec(**overrides: Any) -> ExperimentSpec:
    payload: dict[str, Any] = {
        "name": "v13-contract",
        "maps": ["MAP-22"],
        "agent_arms": [AgentArm(agent_id="basic.v1")],
        "environment_seeds": [0],
        "provider_id": SIMULATED_PROVIDER,
        "model": SIMULATED_MODEL,
        "mode": ExperimentMode.SIMULATED,
    }
    payload.update(overrides)
    return ExperimentSpec.model_validate(payload)


def test_replicate_index_zero_keeps_v12_condition_key() -> None:
    spec = _spec()
    cell = spec.matrix()[0]
    assert cell.replicate_index == 0
    assert cell.condition_key == "MAP-22|seed=0|basic.v1"
    assert cell.condition_key == cell.base_condition_key


def test_replicates_expand_matrix_with_distinct_keys() -> None:
    spec = _spec(replicates=3)
    cells = spec.matrix()
    assert len(cells) == 3
    assert [cell.replicate_index for cell in cells] == [0, 1, 2]
    keys = [cell.condition_key for cell in cells]
    assert len(set(keys)) == 3
    assert keys[1].endswith("|rep=1")
    # 配对键忽略重复编号：重复不是新的环境 seed。
    assert len({cell.pairing_key for cell in cells}) == 1


def test_only_conditions_accepts_base_key_and_keeps_all_replicates() -> None:
    base = _spec(replicates=3)
    base_key = base.matrix()[0].base_condition_key
    filtered = _spec(replicates=3, only_conditions=[base_key])
    assert len(filtered.matrix()) == 3


def test_replicates_are_bounded() -> None:
    with pytest.raises(ValidationError):
        _spec(replicates=0)
    with pytest.raises(ValidationError):
        _spec(replicates=11)


def test_replicates_change_fingerprint() -> None:
    one = _spec(replicates=1)
    three = _spec(replicates=3)
    assert one.fingerprint() != three.fingerprint()


def test_sampling_provenance_never_claims_deterministic() -> None:
    unknown = SamplingProvenance()
    assert unknown.support == "UNKNOWN"
    assert unknown.deterministic_claim == "UNKNOWN"
    accepted = SamplingProvenance(seed_requested=7, support="SUPPORTED", temperature=0.0)
    assert accepted.deterministic_claim == "SEED_ACCEPTED_BUT_OUTPUT_NOT_GUARANTEED"
    unsupported = SamplingProvenance(seed_requested=7, support="UNSUPPORTED")
    assert unsupported.deterministic_claim == "UNSUPPORTED"
    payload = accepted.as_dict()
    assert "deterministic_claim" in payload


def test_protocol_manifest_fingerprint_is_stable() -> None:
    protocol = ProtocolManifest(
        protocol_id="v13-memory",
        question="route_log 是否提高 route_recall？",
        primary_metric="v12.projection.route_recall",
        secondary_metrics=("wasted_moves",),
        stop_rules=("cost_cap",),
    )
    assert protocol.fingerprint() == protocol.fingerprint()
    other = protocol.model_copy(update={"question": "别的问题"})
    assert other.fingerprint() != protocol.fingerprint()
    assert protocol.as_dict()["fingerprint"] == protocol.fingerprint()


def test_public_dict_is_json_round_trippable_and_reloadable() -> None:
    spec = _spec(
        replicates=2,
        sampling=SamplingProvenance(seed_requested=3, support="UNKNOWN"),
        protocol=ProtocolManifest(
            protocol_id="p1", question="q", primary_metric="m"
        ),
        experiment_kind="replicate",
    )
    payload = spec.public_dict()
    text = json.dumps(payload, ensure_ascii=False)
    reloaded = json.loads(text)
    assert reloaded["replicates"] == 2
    assert reloaded["experiment_kind"] == "replicate"
    assert reloaded["protocol"]["protocol_id"] == "p1"
    # 派生摘要不在 public_dict 里（保证可往返）；消费端按需计算。
    assert "sampling_claim" not in reloaded
    derived = {
        "seeds",
        "seed_source",
        "arms",
        "fingerprint",
        "matrix",
        "matrix_size",
        "agent_versions",
    }
    cleaned = {key: value for key, value in reloaded.items() if key not in derived}
    cleaned["experiment_id"] = "lab-20260101T000000Z-deadbeef"
    restored = ExperimentSpec.model_validate(cleaned)
    assert restored.replicates == 2
    assert restored.sampling.seed_requested == 3
    assert restored.sampling.deterministic_claim == "UNKNOWN"
    assert restored.protocol is not None
    assert restored.contract_version == CONTRACT_VERSION_V13


def test_v12_experiment_json_without_v13_fields_still_loads() -> None:
    """V12 落盘的 experiment.json 没有 replicates/sampling/protocol，必须能读。"""

    legacy = {
        "schema_version": "v12-lab-1",
        "experiment_id": "lab-20261025T120807Z-3aaedd0f",
        "name": "legacy",
        "notes": "",
        "maps": ["MAP-16"],
        "agent_arms": [{"agent_id": "basic.v1", "config": {"history_window": 5}, "label": ""}],
        "environment_seeds": [0],
        "provider_id": SIMULATED_PROVIDER,
        "model": SIMULATED_MODEL,
        "mode": "simulated",
        "execution": "sequential",
        "budget": ExperimentBudget().as_dict(),
        "comparison": {
            "paired_by": ["map_id", "environment_seed"],
            "require_same_versions": True,
            "descriptive_only_for_small_samples": True,
            "min_paired_samples": 3,
        },
        "preflight_only": True,
        "approval": {"approved": False},
        "created_at": "2026-10-25T12:08:07Z",
        "only_conditions": [],
        "supplement_of": None,
        "supplement_reason": "",
        "runtime_version": "v12-lab-1+agent_policy_v1+v12-contract-2",
    }
    spec = ExperimentSpec.model_validate(legacy)
    assert spec.replicates == 1
    assert spec.sampling.support == "UNKNOWN"
    assert spec.protocol is None
    assert len(spec.matrix()) == 1  # 显式 seed 只有 0


def test_matrix_cell_from_dict_ignores_derived_keys() -> None:
    cell = MatrixCell(
        matrix_index=4,
        map_id="MAP-22",
        environment_seed=1,
        agent_id="memory.v2",
        agent_config_hash="abc",
        replicate_index=2,
    )
    payload = {
        **cell.as_dict(),
        "pairing_key": "x",
        "base_condition_key": "y",
        "replicate_key": "z",
    }
    restored = MatrixCell.from_dict(payload)
    assert restored.condition_key == cell.condition_key
    assert restored.replicate_index == 2


def test_child_run_link_defaults_are_v13_safe() -> None:
    link = ChildRunLink(matrix_index=0, run_id="web-1", map_id="MAP-22", environment_seed=0,
                        agent_id="basic.v1")
    assert link.replicate_index == 0
    assert link.experiment_kind == "matrix"
    # 旧文件缺少这两个字段时按默认值读取。
    legacy = link.as_dict()
    legacy.pop("replicate_index")
    legacy.pop("experiment_kind")
    assert ChildRunLink.model_validate(legacy).replicate_index == 0


def test_budget_defaults_unchanged_for_v12(tmp_path: Path) -> None:
    del tmp_path
    budget = ExperimentBudget()
    assert budget.per_run_request_cap == 60
    assert budget.per_run_cost_cap_cny == Decimal("1.00")
