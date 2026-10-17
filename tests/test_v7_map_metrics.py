"""Real-environment replay tests for the six runtime-backed V7 maps.

Each episode re-executes the frozen V6 solver actions against the real V4
environment and then recomputes metrics from the public trace. No provider is
created and nothing is written to ``runs/``.
"""

from __future__ import annotations

from typing import Any

import pytest

from agent_arena.v6.catalog import build_environment, get_scene
from agent_arena.v6.scenes import all_scenes
from agent_arena.v6.solvers import solve
from agent_arena.v7.metrics import registry
from agent_arena.v7.metrics.schema import MetricStatus, parse_trace_rows
from agent_arena.worlds.scenario_v4 import ScenarioV4Action

PREFERRED_CONDITION = {
    "MAP-08": "hypothesis_table",
    "MAP-16": "constraint_table",
    "MAP-18": "alert_on",
    "MAP-22": "history5_graph_memory",
    "MAP-26": "free_diagnosis",
    "MAP-30": "history5_casebook",
}
RUNTIME_MAPS = set(PREFERRED_CONDITION)


def _replay(instance_id: str) -> tuple[Any, dict[str, Any]]:
    scene = get_scene(instance_id)
    condition = PREFERRED_CONDITION[scene.map_id]
    if condition not in scene.paired_conditions:
        condition = scene.paired_conditions[0]
    environment = build_environment(scene, condition, seed=0)
    solution = solve(instance_id, seed=0)
    rows: list[dict[str, Any]] = [
        {
            "event": "trace_header",
            "map_id": scene.map_id,
            "instance_id": instance_id,
            "condition_id": condition,
            "seed": 0,
            "scenario_hash": environment.source_hash,
            "provider": "offline",
            "model": "v6-solver",
        }
    ]
    observation = environment.observe().model_dump(mode="json")
    for index, payload in enumerate(solution.actions):
        step = environment.step(ScenarioV4Action.model_validate(payload, strict=True))
        after = step.observation.model_dump(mode="json")
        rows.append(
            {
                "event": "decision",
                "decision_index": index,
                "action": payload,
                "result": step.result,
                "observation_before": observation,
                "observation_after": after,
                "invalid_output_reason": None,
            }
        )
        observation = after
    judge = {
        "status": "success" if environment.is_success else "failure",
        "judge_state": {
            "true_leak": getattr(environment, "true_leak", None),
            "casebook_visible": getattr(environment, "casebook_visible", None),
        },
    }
    record = parse_trace_rows(rows, judge=judge, source=f"offline:{instance_id}")
    return environment, registry.compute_metrics(record)


@pytest.fixture(scope="module")
def replays() -> dict[str, tuple[Any, dict[str, Any]]]:
    results: dict[str, tuple[Any, dict[str, Any]]] = {}
    for instance_id, scene in sorted(all_scenes().items()):
        if scene.map_id in RUNTIME_MAPS:
            results[instance_id] = _replay(instance_id)
    return results


RUNTIME_INSTANCES = sorted(
    instance_id for instance_id, scene in all_scenes().items() if scene.map_id in RUNTIME_MAPS
)


@pytest.mark.parametrize("instance_id", RUNTIME_INSTANCES)
def test_solver_episode_computes_every_metric(replays, instance_id: str) -> None:
    environment, values = replays[instance_id]
    assert environment.is_success
    expected = {spec.metric_id for spec in registry.specs_for(environment.map_id)}
    assert set(values) == expected
    for metric_id, value in values.items():
        assert value.status in {MetricStatus.VALID, MetricStatus.NOT_APPLICABLE}, metric_id


def _value(replays, instance_id: str, metric_id: str):
    return replays[instance_id][1][metric_id]


def test_map08_diagnosis_uses_private_true_leak(replays) -> None:
    for instance_id in [key for key in replays if key.startswith("map08_")]:
        assert _value(replays, instance_id, "map08.diagnosis_accuracy").value == 1
        assert _value(replays, instance_id, "map08.wrong_repair").value == 0
        assert _value(replays, instance_id, "map08.tests_run").value >= 1
        assert _value(replays, instance_id, "map08.peak_core_water").status is MetricStatus.VALID


def test_map16_solver_hits_optimal_makespan_without_deadlock(replays) -> None:
    for instance_id in [key for key in replays if key.startswith("map16_")]:
        assert _value(replays, instance_id, "map16.makespan_gap").value == 0
        assert _value(replays, instance_id, "map16.deadlock").value == 0
        assert _value(replays, instance_id, "map16.legal_reservation_rate").value == 1.0


def test_map18_services_every_order_and_reports_no_fault_as_na(replays) -> None:
    for instance_id in [key for key in replays if key.startswith("map18_")]:
        assert _value(replays, instance_id, "map18.service_rate").value == 1.0
    no_fault = _value(replays, "map18_l1_no_fault", "map18.first_reroute_delay")
    assert no_fault.status is MetricStatus.NOT_APPLICABLE
    assert no_fault.value is None


def test_map22_returns_with_frozen_optimal_moves(replays) -> None:
    for instance_id in [key for key in replays if key.startswith("map22_")]:
        assert _value(replays, instance_id, "map22.return_success").value == 1
        assert _value(replays, instance_id, "map22.path_gap").value == 0
        assert _value(replays, instance_id, "map22.memory_grounding_violations").value == 0


def test_map26_free_and_recovery_conditions_differ(replays) -> None:
    for instance_id in [key for key in replays if key.startswith("map26_")]:
        assert _value(replays, instance_id, "map26.repair_success").value == 1
        assert _value(replays, instance_id, "map26.diagnosis_accuracy").value == 1
        assert _value(replays, instance_id, "map26.spares_remaining").value >= 1
    free = _value(replays, "map26_l1_antenna_fault", "map26.recovery_latency")
    assert free.status is MetricStatus.NOT_APPLICABLE
    recovery = _value(replays, "map26_recovery_antenna", "map26.recovery_latency")
    assert recovery.status is MetricStatus.VALID
    assert recovery.value == 6


def test_map30_full_chain_in_casebook_condition(replays) -> None:
    for instance_id in [key for key in replays if key.startswith("map30_")]:
        assert _value(replays, instance_id, "map30.q4_recall_accuracy").value == 1
        assert _value(replays, instance_id, "map30.evidence_chain_coverage").value == 1.0
        assert _value(replays, instance_id, "map30.unsupported_accusations").value == 0


def _synthetic(map_id: str, instance_id: str, condition: str, rows: list[dict], judge=None):
    header = {
        "event": "trace_header",
        "map_id": map_id,
        "instance_id": instance_id,
        "condition_id": condition,
        "seed": 0,
        "scenario_hash": "synthetic-hash",
    }
    return parse_trace_rows([header, *rows], judge=judge)


def _move(action: str, before: dict, after: dict, index: int) -> dict:
    return {
        "event": "decision",
        "decision_index": index,
        "action": {"tool": "move", "edge_id": action},
        "result": "MOVE_SUCCEEDED",
        "observation_before": before,
        "observation_after": after,
        "invalid_output_reason": None,
    }


def _place(silhouette: str, exits: list[str]) -> dict:
    return {"current_coarse_silhouette": silhouette, "visible_exit_bearings": exits}


def _terminal_row(observation: dict, result: str = "TERMINAL") -> dict:
    return {
        "event": "decision",
        "decision_index": 999,
        "action": {"tool": "wait"},
        "result": result,
        "observation_before": observation,
        "observation_after": observation,
        "invalid_output_reason": None,
    }


def test_map22_legal_round_trip_is_not_a_repeated_edge() -> None:
    a = _place("A", ["north"])
    b = _place("B", ["south"])
    terminal = dict(b, terminal=True, terminal_reason="RETURNED_TO_CAMP_WITH_RUIN_RECORD")
    record = _synthetic(
        "MAP-22",
        "map22_l1_short_return",
        "history5_graph_memory",
        [
            _move("A-B", a, b, 0),
            _move("B-A", b, a, 1),
            _move("A-B", a, b, 2),
            _terminal_row(terminal),
        ],
    )
    # The third move repeats the directed A-B edge once; B-A is a distinct edge.
    values = registry.compute_metrics(record)
    assert values["map22.repeated_public_edge_rate"].value == pytest.approx(1 / 3, abs=1e-6)
    assert values["map22.return_success"].status is MetricStatus.VALID
    assert values["map22.return_success"].value == 1


def test_map30_empty_casebook_is_unavailable_without_visibility_flag() -> None:
    final = {
        "casebook": [],
        "terminal": True,
        "terminal_reason": "SOMETHING_ELSE",
        "unsupported_formal_accusations": 0,
    }
    record = _synthetic(
        "MAP-30",
        "map30_l1_two_event_case",
        "history_full",
        [_terminal_row(final)],
    )
    values = registry.compute_metrics(record)
    assert values["map30.evidence_chain_coverage"].status is MetricStatus.UNAVAILABLE
    assert values["map30.evidence_chain_coverage"].value is None


def test_map30_explicit_visibility_makes_empty_casebook_a_legal_zero() -> None:
    final = {
        "casebook": [],
        "terminal": True,
        "terminal_reason": "SOMETHING_ELSE",
        "unsupported_formal_accusations": 0,
    }
    record = _synthetic(
        "MAP-30",
        "map30_l1_two_event_case",
        "history5_casebook",
        [_terminal_row(final)],
        judge={"status": "success", "judge_state": {"casebook_visible": True}},
    )
    values = registry.compute_metrics(record)
    assert values["map30.evidence_chain_coverage"].status is MetricStatus.VALID
    assert values["map30.evidence_chain_coverage"].value == 0.0
