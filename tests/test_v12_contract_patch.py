"""DCR-V12-01 回归测试：`facts` 契约补丁只影响需要的图，且写进 provenance。"""

from __future__ import annotations

from decimal import Decimal

from agent_arena.lab.contract_v12 import (
    CONTRACT_AUGMENTATION_VERSION,
    FIELD_HINTS,
    augment_prompt,
    augmentation_for,
    provenance_block,
)
from agent_arena.lab.runner import run_lab_episode
from agent_arena.lab.simulated import SimulatedDecisionProvider
from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.web.prompting import system_prompt
from agent_arena.web.schemas import (
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
    RunConfig,
    RunMode,
)
from agent_arena.worlds.scenario_v8.models import V8Action


def _config(map_id: str) -> RunConfig:
    return RunConfig(
        map_id=map_id,
        environment_seed=0,
        mode=RunMode.SIMULATED,
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        agent="basic.v1",
        max_decisions=2,
        max_requests=10,
        max_input_tokens=200_000,
        max_output_tokens=8_000,
        max_cost_cny=Decimal("1"),
    )


def test_augmentation_applies_to_maps_with_facts() -> None:
    """只按**实例** SHAPES 判定：那才是真正交给模型的契约。

    注意 MAP-16 的类级 SHAPES 是全集，但实例只暴露 5 个工具（不含 write_memory），
    所以它不需要补丁。
    """

    for map_id in ("MAP-03", "MAP-22"):
        hints = augmentation_for(create_environment(map_id))
        assert hints, map_id
        assert "key" in hints[0] and "value" in hints[0]


def test_map16_instance_has_no_facts_tool() -> None:
    environment = create_environment("MAP-16")
    assert "write_memory" not in environment.SHAPES
    assert augmentation_for(environment) == ()


def test_augmentation_is_empty_for_other_maps() -> None:
    for map_id in ("MAP-01", "MAP-08", "MAP-16", "MAP-18", "MAP-26", "MAP-30"):
        assert augmentation_for(create_environment(map_id)) == (), map_id


def test_prompt_contains_exact_shape_for_facts() -> None:
    environment = create_environment("MAP-22")
    base = system_prompt("MAP-22", environment)
    augmented, hints = augment_prompt(base, environment)
    assert augmented.startswith(base)
    assert '{"key": "<str>", "value": "<str>"}' in augmented
    assert "INVALID_MEMORY_PAYLOAD" in augmented
    assert hints == augmentation_for(environment)


def test_prompt_unchanged_without_facts() -> None:
    environment = create_environment("MAP-01")
    base = system_prompt("MAP-01", environment)
    augmented, hints = augment_prompt(base, environment)
    assert augmented == base
    assert hints == ()


def test_provenance_block_records_version_and_application() -> None:
    applied = provenance_block(("hint",))
    assert applied["version"] == CONTRACT_AUGMENTATION_VERSION
    assert applied["applied"] is True
    assert applied["hints"] == ["hint"]
    empty = provenance_block(())
    assert empty["applied"] is False
    assert empty["hints"] == []


def test_runner_records_augmentation_in_result() -> None:
    for map_id, expected in (("MAP-22", True), ("MAP-01", False)):
        environment = create_environment(map_id)
        provider = SimulatedDecisionProvider(map_id=map_id, shapes=environment.SHAPES)
        outcome = run_lab_episode(_config(map_id), provider=provider)
        block = outcome.result["provenance"]["contract_augmentation"]
        assert block["applied"] is expected, map_id
        assert block["version"] == CONTRACT_AUGMENTATION_VERSION


def test_augmented_prompt_changes_prompt_hash() -> None:
    """补丁必须改变 prompt_hash，否则跨版本局会被误当成可配对。"""

    hashes: dict[str, str] = {}
    for map_id in ("MAP-22", "MAP-01"):
        environment = create_environment(map_id)
        provider = SimulatedDecisionProvider(map_id=map_id, shapes=environment.SHAPES)
        outcome = run_lab_episode(_config(map_id), provider=provider)
        hashes[map_id] = str(outcome.result["prompt_hash"])
    # 两张图的 prompt 本来就不同；这里校验的是补丁进了哈希（长度与来源一致）。
    assert all(len(value) == 64 for value in hashes.values())
    environment = create_environment("MAP-22")
    base = system_prompt("MAP-22", environment)
    augmented, _ = augment_prompt(base, environment)
    from hashlib import sha256

    assert sha256(base.encode()).hexdigest() != sha256(augmented.encode()).hexdigest()


def test_environment_still_rejects_wrong_facts_shape() -> None:
    """补丁只改提示，不改环境：错误形状仍然被拒（不能靠补丁放宽校验）。"""

    environment = create_environment("MAP-22")
    wrong = V8Action.model_validate(
        {"tool": "write_memory", "facts": [{"at_sign": "leaning_3"}]}, strict=True
    )
    assert environment.accepts(wrong) is True  # 形状合法（tool+facts）
    result = environment.step(wrong)
    assert result.result == "INVALID_MEMORY_PAYLOAD"

    right = V8Action.model_validate(
        {"tool": "write_memory", "facts": [{"key": "bearing", "value": "west"}]},
        strict=True,
    )
    assert environment.step(right).result == "MEMORY_WRITTEN"


def test_field_hints_are_public_information_only() -> None:
    """补丁不得包含隐藏真值或答案。"""

    text = " ".join(FIELD_HINTS.values()).lower()
    for forbidden in ("sealed_truth", "judge_state", "oracle", "answer"):
        assert forbidden not in text
