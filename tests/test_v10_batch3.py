"""Batch 3：MAP-28 / MAP-29（DCR-V10-06）与 MAP-30（DCR-V10-07）。"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from agent_arena.v10.baselines import map28 as b28
from agent_arena.v10.baselines import map29 as b29
from agent_arena.v10.baselines import map30 as b30
from agent_arena.v10.baselines.runner import run_actions, run_policy
from agent_arena.v10.runtime.catalog import create_environment, scenario_hash
from agent_arena.v10.runtime.map28 import CASES as CASES28
from agent_arena.v10.runtime.map28 import Map28V10Environment
from agent_arena.v10.runtime.map29 import NPC_LABEL, Map29V10Environment
from agent_arena.v10.runtime.map29 import SCENARIOS as CASES29
from agent_arena.v10.runtime.map29 import oracle_actions as oracle29
from agent_arena.v10.runtime.map30 import COURTROOM
from agent_arena.v10.runtime.map30 import SCENARIOS as CASES30
from agent_arena.worlds.scenario_v8.models import V8Action

FROZEN = (
    ("src/agent_arena/worlds/scenario_v8", "src/agent_arena/worlds/scenario_v8/maps/map28.py"),
    ("src/agent_arena/worlds/scenario_v8", "src/agent_arena/worlds/scenario_v8/maps/map29.py"),
    ("src/agent_arena/worlds/scenario_v4", "src/agent_arena/worlds/scenario_v4/map30.py"),
)


@pytest.mark.parametrize("root,path", FROZEN, ids=["map28", "map29", "map30"])
def test_v8_v4_rule_files_match_freeze_manifest(root: str, path: str) -> None:
    manifest = json.loads(Path("docs/v10/freeze-manifest.json").read_text(encoding="utf-8"))
    files = manifest["roots"][root]["files"]
    assert sha256(Path(path).read_bytes()).hexdigest() == files[path]


# --------------------------------------------------------------------------- MAP-28
def test_map28_four_distinct_cases_and_hashes() -> None:
    assert len(CASES28) == 4
    assert len({scenario_hash("MAP-28", seed) for seed in CASES28}) == 4
    truths = {tuple(sorted(case.truth.items())) for case in CASES28.values()}
    assert len(truths) == 4


def test_map28_goal_and_public_fields_do_not_leak_truth() -> None:
    for seed in CASES28:
        case = CASES28[seed]
        environment = create_environment("MAP-28", environment_seed=seed)
        text = json.dumps(environment.observe(), ensure_ascii=False)
        assert "truth" not in text and "sealed" not in text
        assert case.truth["entry_time"] not in text
        assert case.truth["exit_time"] not in text
        for rule in environment.public_rules():  # type: ignore[attr-defined]
            assert case.truth["entry_time"] not in rule
            assert "sealed" not in rule


def test_map28_enumerations_are_published() -> None:
    environment = create_environment("MAP-28", environment_seed=0)
    observation = environment.observe()
    assert observation["persons"] == list(CASES28[0].persons)
    assert observation["entry_paths"] == list(CASES28[0].paths)
    assert observation["required_key_evidence"]


def test_map28_three_failure_codes_are_distinguishable() -> None:
    # EVIDENCE_MISSING：引用未记录证据
    environment = Map28V10Environment(seed=0)
    result = environment.step(
        V8Action.model_validate(
            {
                "tool": "submit",
                "claims": [
                    {"claim_id": field, "value": CASES28[0].truth[field]}
                    for field in ("person_id", "entry_path_id", "entry_time", "exit_time")
                ],
                "citations_by_claim": {
                    field: ["KEY_REGISTER_K3_CELINE"] for field in
                    ("person_id", "entry_path_id", "entry_time", "exit_time")
                },
            },
            strict=True,
        )
    )
    assert result.result == "EVIDENCE_MISSING"


def test_map28_oracle_heuristic_and_ablations() -> None:
    for seed in CASES28:
        run = run_actions("MAP-28", b28.oracle_actions(seed), environment_seed=seed)
        assert run.success and run.mechanism_triggered
        assert run.metrics["map28.v10.timeline_constraint_satisfaction"]["value"] == 1.0
        heuristic = run_policy("MAP-28", b28.HEURISTIC(), environment_seed=seed, decision_budget=30)
        assert heuristic.success
    for name, factory in b28.ABLATIONS.items():
        runs = [
            run_policy("MAP-28", factory(), environment_seed=seed, decision_budget=30)
            for seed in CASES28
        ]
        if name == "cite_all":
            # 只在“证词误记路径”的实例上被引用自洽规则拦下
            assert sum(run.success for run in runs) <= 3
        else:
            assert sum(run.success for run in runs) == 0, name


def test_map28_cite_all_falls_into_misremembered_path_trap() -> None:
    runs = {
        seed: run_policy(
            "MAP-28", b28.ABLATIONS["cite_all"](), environment_seed=seed, decision_budget=30
        )
        for seed in CASES28
    }
    assert not runs[3].success
    assert runs[3].metrics["map28.v10.timeline_constraint_satisfaction"]["value"] == 0.75


# --------------------------------------------------------------------------- MAP-29
def test_map29_roles_are_not_published_and_vary_by_seed() -> None:
    assignments = {seed: tuple(sorted(case.roles.items())) for seed, case in CASES29.items()}
    assert len(set(assignments.values())) == len(assignments)
    environment = Map29V10Environment(seed=0)
    text = json.dumps(environment.observe(), ensure_ascii=False)
    for description in (
        "故意隐瞒",
        "时间锚定",
        "只听到声音",
        "部分真实",
        "archive_keeper",
        "location_concealer",
        "time_anchored",
    ):
        assert description not in text
    assert environment.observe()["npc_labels"] == NPC_LABEL


def test_map29_partial_truth_is_classified_only_when_compared() -> None:
    partial_seed = next(seed for seed, case in CASES29.items() if case.partial_npc is not None)
    run = run_policy("MAP-29", b29.HEURISTIC(), environment_seed=partial_seed, decision_budget=38)
    assert run.success
    assert run.metrics["map29.v10.partial_truth_classified"]["value"] == 1
    other = next(seed for seed, case in CASES29.items() if case.partial_npc is None)
    assert (
        run_policy("MAP-29", b29.HEURISTIC(), environment_seed=other, decision_budget=38)
        .metrics["map29.v10.partial_truth_classified"]["state"]
        == "NOT_APPLICABLE"
    )


def test_map29_oracle_and_ablations() -> None:
    for seed in CASES29:
        oracle = run_actions("MAP-29", oracle29(seed), environment_seed=seed)
        assert oracle.success and oracle.mechanism_triggered
        heuristic = run_policy("MAP-29", b29.HEURISTIC(), environment_seed=seed, decision_budget=38)
        assert heuristic.success
    for name, factory in b29.ABLATIONS.items():
        runs = [
            run_policy("MAP-29", factory(), environment_seed=seed, decision_budget=38)
            for seed in CASES29
        ]
        assert sum(run.success for run in runs) == 0, name


def test_map29_archive_prereq_is_a_real_cross_phase_dependency() -> None:
    seed = next(seed for seed, case in CASES29.items() if case.archive_prereq is not None)
    environment = Map29V10Environment(seed=seed)
    keeper = environment.scenario.npc_at("archive_keeper")
    for _ in range(2):
        environment.step(V8Action.model_validate({"tool": "move", "to": "H"}, strict=True))
        environment.step(
            V8Action.model_validate(
                {"tool": "move", "to": environment.scenario.rooms[keeper]}, strict=True
            )
        )
        result = environment.step(
            V8Action.model_validate(
                {
                    "tool": "ask",
                    "npc_id": keeper,
                    "question_template_id": "ARCHIVE_CROSS_INDEX",
                },
                strict=True,
            )
        )
        assert result.result == "ARCHIVE_NEEDS_PREREQ"


# --------------------------------------------------------------------------- MAP-30
def test_map30_cases_vary_dependency_and_truth() -> None:
    assert len(CASES30) == 3
    assert len({scenario_hash("MAP-30", seed) for seed in CASES30}) == 3
    assert any(event.is_decoy for event in CASES30[2].events)
    labels = {case.label for case in CASES30.values()}
    assert len(labels) == 3


def test_map30_entry_ids_and_courtroom_are_published() -> None:
    environment = create_environment("MAP-30", environment_seed=2)
    observation = environment.observe()
    assert observation["courtroom_node"] == COURTROOM
    assert set(observation["entry_ids"]) == set(CASES30[2].entry_ids)
    assert set(observation["evidence_locations"]) == {
        event.evidence_id for event in CASES30[2].events
    } | {CASES30[2].archive_evidence}
    text = json.dumps(observation, ensure_ascii=False)
    assert CASES30[2].culprit_person not in text
    assert CASES30[2].culprit_code not in text


def test_map30_oracle_heuristic_and_ablations() -> None:
    for seed in CASES30:
        oracle = run_actions("MAP-30", b30.oracle_actions(seed), environment_seed=seed)
        assert oracle.success and oracle.mechanism_triggered
        assert oracle.metrics["map30.v10.chain_reconciled"]["value"] == 1
        heuristic = run_policy("MAP-30", b30.HEURISTIC(), environment_seed=seed, decision_budget=46)
        assert heuristic.success
        assert heuristic.metrics["map30.v10.q4_recall_accuracy"]["value"] == 1
    for name, factory in b30.ABLATIONS.items():
        runs = [
            run_policy("MAP-30", factory(), environment_seed=seed, decision_budget=46)
            for seed in CASES30
        ]
        assert sum(run.success for run in runs) == 0, name


def test_map30_accusation_precision_is_not_awarded_for_rejected_accusations() -> None:
    seed = 0
    run = run_policy(
        "MAP-30", b30.ABLATIONS["late_guess"](), environment_seed=seed, decision_budget=46
    )
    assert not run.success
    state = run.metrics["map30.v10.accusation_claim_precision"]["state"]
    assert state == "NOT_APPLICABLE"


def test_map30_window_delay_measures_long_interval_recall() -> None:
    runs = [
        run_policy(
            "MAP-30", b30.ABLATIONS["window_delay"](), environment_seed=seed, decision_budget=46
        )
        for seed in CASES30
    ]
    assert all(
        run.metrics["map30.v10.window_pressure_events"]["value"] >= 1 for run in runs
    )
    assert all(
        run.metrics["map30.v10.evidence_chain_coverage"]["value"] < 1.0 for run in runs
    )
