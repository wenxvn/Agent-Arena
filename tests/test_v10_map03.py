"""MAP-03 V10（DCR-V10-01）：长期记忆的反旁路与可解性测试。"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from agent_arena.v10.baselines import map03 as baseline
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import create_environment, scenario_hash
from agent_arena.v10.runtime.map03 import VARIANTS, Map03V10Environment
from agent_arena.worlds.scenario_v8.models import V8Action

SEEDS = tuple(sorted(VARIANTS))
V8_RULE_HASH = "ba6ee7abcbb1bf4fa915ca43a22985640b9378cd38c3483eed56f6e83ea8dad4"


def _step(environment: Map03V10Environment, payload: dict[str, object]) -> str:
    return environment.step(V8Action.model_validate(payload, strict=True)).result


def test_v8_map03_rule_file_is_untouched() -> None:
    path = Path("src/agent_arena/worlds/scenario_v8/maps/map03.py")
    assert sha256(path.read_bytes()).hexdigest() == V8_RULE_HASH


def test_seeds_change_code_route_and_scenario_hash() -> None:
    codes = {VARIANTS[seed][2] for seed in SEEDS}
    labs_and_starts = {(VARIANTS[seed][0], VARIANTS[seed][1]) for seed in SEEDS}
    assert len(codes) == len(SEEDS)
    assert len(labs_and_starts) == len(SEEDS)
    assert len({scenario_hash("MAP-03", seed) for seed in SEEDS}) == len(SEEDS)


@pytest.mark.parametrize("seed", SEEDS)
def test_code_never_leaks_outside_the_single_read_observation(seed: int) -> None:
    code = VARIANTS[seed][2]
    environment = create_environment("MAP-03", environment_seed=seed)
    assert isinstance(environment, Map03V10Environment)
    assert code not in json.dumps(environment.observe(), ensure_ascii=False)
    assert all(code not in rule for rule in environment.public_rules())
    run = run_actions("MAP-03", baseline.oracle_actions(seed), environment_seed=seed)
    carrying = [
        entry["observation_after"]
        for entry in run.actions
        if entry["observation_after"].get("route_tag_value") == code
    ]
    assert len(carrying) == 1
    assert run.success


@pytest.mark.parametrize("seed", SEEDS)
def test_oracle_and_heuristic_succeed_with_memory_gap_beyond_history(seed: int) -> None:
    actions = baseline.oracle_actions(seed)
    assert len(actions) <= 46
    oracle = run_actions("MAP-03", actions, environment_seed=seed)
    assert oracle.success and oracle.mechanism_triggered
    assert oracle.metrics["map03.v10.memory_gap_actions"]["value"] > 5
    heuristic = run_policy("MAP-03", baseline.HEURISTIC(), environment_seed=seed)
    assert heuristic.success
    assert heuristic.metrics["map03.v10.note_holds_code_at_submit"]["value"] == 1


@pytest.mark.parametrize("seed", SEEDS)
def test_memoryless_ablations_fail(seed: int) -> None:
    for name, factory in baseline.ABLATIONS.items():
        run = run_policy("MAP-03", factory(), environment_seed=seed)
        assert not run.success, name
        assert run.terminal_reason == "ROUTE_KEY_REJECTED", name
        assert run.metrics["map03.v10.code_recall_correct"] == {"state": "VALID", "value": 0}


def test_late_read_is_sealed_after_stabilizing() -> None:
    environment = Map03V10Environment(seed=0)
    for payload in baseline.oracle_actions(0)[:17]:
        _step(environment, payload)
    assert environment.sample_cold
    assert (
        _step(environment, {"tool": "interact", "target": "sample_manifest", "choice": "read_tag"})
        == "MANIFEST_SEALED"
    )
    assert environment.observe()["route_tag_value"] is None


def test_submission_cannot_follow_read_directly() -> None:
    environment = Map03V10Environment(seed=0)
    oracle = baseline.oracle_actions(0)
    read_index = next(
        index for index, payload in enumerate(oracle) if payload.get("choice") == "read_tag"
    )
    for payload in oracle[: read_index + 1]:
        _step(environment, payload)
    _step(environment, {"tool": "interact", "target": "cryo_case", "choice": "stabilize_sample"})
    _step(environment, {"tool": "move", "edge_id": "U2_U1"})
    result = _step(environment, {"tool": "submit", "target": "route_console", "answer": "K7"})
    assert result == "PHASE_OUT_OF_ORDER"
    assert environment.submitted_answer is None


def test_eva_exit_is_charged_and_second_sortie_refused() -> None:
    environment = Map03V10Environment(seed=2)  # 起点 D3
    assert _step(environment, {"tool": "move", "edge_id": "D3_V"}) == "EVA_ENTERED"
    assert environment.eva_supply == 2
    assert _step(environment, {"tool": "move", "edge_id": "D3_V"}).startswith("EVA_EXITED")
    assert environment.eva_supply == 1
    assert _step(environment, {"tool": "move", "edge_id": "D3_V"}) == "EVA_SORTIE_REFUSED"
    assert environment.node == "D3"


def test_idling_in_v_exhausts_oxygen() -> None:
    environment = Map03V10Environment(seed=2)
    _step(environment, {"tool": "move", "edge_id": "D3_V"})
    _step(environment, {"tool": "wait", "turns": 1})
    assert not environment.is_terminal
    _step(environment, {"tool": "wait", "turns": 1})
    assert environment.terminal_reason == "EVA_OXYGEN_EXHAUSTED"


def test_memory_channel_contract() -> None:
    environment = Map03V10Environment(seed=0)
    assert _step(environment, {"tool": "write_memory", "facts": [{"key": "a"}]}) == (
        "MEMORY_FACT_SCHEMA"
    )
    for index in range(4):
        _step(
            environment,
            {"tool": "write_memory", "facts": [{"key": f"k{index}", "value": "v"}]},
        )
    notes = environment.observe()["agent_notes"]
    assert [item["key"] for item in notes] == ["k1", "k2", "k3"]


def test_five_state_metrics() -> None:
    environment = Map03V10Environment(seed=0)
    metrics = environment.v10_metrics()
    assert metrics["map03.v10.code_recall_correct"].state.value == "NOT_APPLICABLE"
    assert metrics["map03.v10.phase_completion"].value == 0.0
    run = run_actions(
        "MAP-03",
        [*baseline.oracle_actions(0)[:16], {"tool": "wait", "turns": 1}],
        environment_seed=0,
    )
    assert run.status == "decision_budget_reached"
    assert run.metrics["map03.v10.code_recall_correct"]["state"] == "CENSORED"
    # 读码 + 写笔记后尚未冷藏：只有 P1 完成，部分进度保持 VALID。
    assert run.metrics["map03.v10.phase_completion"] == {
        "state": "VALID",
        "value": 0.2,
        "numerator": 1,
        "denominator": 5,
    }


def test_codes_do_not_collide_with_public_tokens() -> None:
    from agent_arena.v10.runtime.map03 import RESERVED_TOKENS

    for _, _, code, antenna, ack in VARIANTS.values():
        assert not {code, antenna, ack} & RESERVED_TOKENS
        assert len({code, antenna, ack}) == 3
