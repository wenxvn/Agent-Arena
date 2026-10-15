from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from agent_arena.worlds.scenario_v4 import MAP_IDS, ScenarioV4Action, create_environment

ROOT = Path(__file__).resolve().parents[1]


def _step(env: Any, **payload: Any) -> str:
    return env.step(ScenarioV4Action.model_validate(payload, strict=True)).result


def _set_timetable(env: Any, **operations: Any) -> str:
    return _step(env, tool="set_timetable", tick=env.tick, operations=operations)


def test_six_map_oracle_replay_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_v4_runtime.py"],
        check=False,
        capture_output=True,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"MAP-30": 3' in result.stdout


@pytest.mark.parametrize("map_id", MAP_IDS)
def test_three_registered_seed_labels_reset_deterministically(map_id: str) -> None:
    from agent_arena.worlds.scenario_v4.catalog import CONDITIONS

    condition = CONDITIONS[map_id][0]
    env = create_environment(map_id, seed=0, condition_id=condition)
    initial_hash = env.state_hash()
    initial_observation = env.observe().model_dump(mode="json")
    assert env.reset(0).model_dump(mode="json") == initial_observation
    assert env.state_hash() == initial_hash
    env.reset(1)
    assert env.seed == 1
    env.reset(2)
    assert env.seed == 2


def test_fixed_action_sequences_replay_identical_public_traces_and_judge_hashes() -> None:
    cases = {
        "MAP-08": ("no_hypothesis_table", [{"tool": "wait", "turns": 1}]),
        "MAP-16": ("react", [{"tool": "inspect_network"}]),
        "MAP-18": (
            "alert_off",
            [{"tool": "set_timetable", "tick": 0, "operations": {}}],
        ),
        "MAP-22": (
            "history5_graph_memory",
            [{"tool": "observe_signpost"}, {"tool": "move", "bearing": "NE"}],
        ),
        "MAP-26": (
            "free_diagnosis",
            [
                {"tool": "move", "to": "D"},
                {"tool": "read_log", "log_id": "COMM_LOSS_LAST_TRANSMIT"},
            ],
        ),
        "MAP-30": ("history5_casebook", [{"tool": "move", "to": "J"}]),
    }
    for map_id, (condition, actions) in cases.items():
        replays = []
        for _ in range(2):
            env = create_environment(map_id, seed=0, condition_id=condition)
            trace = []
            for payload in actions:
                before = env.observe().model_dump(mode="json")
                result = env.step(ScenarioV4Action.model_validate(payload, strict=True))
                trace.append(
                    {
                        "before": before,
                        "result": result.result,
                        "after": result.observation.model_dump(mode="json"),
                        "judge_state_hash": env.state_hash(),
                    }
                )
            replays.append((trace, env.state_hash()))
        assert replays[0] == replays[1], map_id


def test_map08_distinguishes_wrong_repair_pressure_failure_and_step_censor() -> None:
    public_starts = [
        create_environment("MAP-08", seed=seed, condition_id="no_hypothesis_table")
        .observe()
        .model_dump(mode="json")
        for seed in (0, 4, 8)
    ]
    assert public_starts[0] == public_starts[1] == public_starts[2]

    wrong = create_environment("MAP-08", seed=0, condition_id="no_hypothesis_table")
    assert _step(wrong, tool="move", edge_id="not-an-edge") == "INVALID_EDGE"
    assert wrong.tick == 0
    assert wrong.observe().current_core_water == 1.0
    _step(wrong, tool="move", edge_id="A_B")
    assert _step(wrong, tool="move", edge_id="B_C") == "MOVE_SUCCEEDED"
    _step(wrong, tool="move", edge_id="C_D")
    assert (
        _step(wrong, tool="interact", target_id="D", operation="repair_leak") == "SEALANT_MISUSED"
    )
    assert wrong.status.value == "scenario_failure"

    pressure = create_environment("MAP-08", seed=8, condition_id="no_hypothesis_table")
    for _ in range(13):
        pressure.step(ScenarioV4Action(tool="wait", turns=1))
        if pressure.is_terminal:
            break
    assert pressure.terminal_reason == "CORE_WATER_LIMIT_EXCEEDED"

    exact_boundary = create_environment("MAP-08", seed=0, condition_id="no_hypothesis_table")
    for _ in range(12):
        _step(exact_boundary, tool="wait", turns=1)
    assert exact_boundary.observe().current_core_water == 7.0
    assert exact_boundary.status.value == "running"
    assert _step(exact_boundary, tool="wait", turns=1) == "CORE_WATER_LIMIT_EXCEEDED"
    assert exact_boundary.observe().current_core_water == 7.5

    censored = create_environment(
        "MAP-08", seed=0, condition_id="no_hypothesis_table", step_limit=1
    )
    censored.step(ScenarioV4Action(tool="wait", turns=1))
    assert censored.status.value == "step_limit_reached"


def test_map16_rejects_bad_route_and_detects_node_conflict_head_on_and_deadlock() -> None:
    invalid = create_environment("MAP-16", seed=0, condition_id="react")
    assert _step(invalid, tool="set_route", train_id="a", next_node="Y") == "INVALID_ROUTE"
    assert invalid.status.value == "running"

    node_conflict = create_environment("MAP-16", seed=0, condition_id="react")
    _step(node_conflict, tool="set_route", train_id="a", next_node="X")
    _step(node_conflict, tool="set_route", train_id="b", next_node="Y")
    _step(node_conflict, tool="move_train")
    _step(node_conflict, tool="set_route", train_id="a", next_node="M")
    _step(node_conflict, tool="set_route", train_id="b", next_node="M")
    assert _step(node_conflict, tool="move_train") == "NODE_CAPACITY_CONFLICT"

    head_on = create_environment("MAP-16", seed=0, condition_id="react")
    _step(head_on, tool="set_route", train_id="a", next_node="X")
    _step(head_on, tool="set_route", train_id="b", next_node="Y")
    _step(head_on, tool="move_train")
    _step(head_on, tool="set_route", train_id="b", next_node="M")
    _step(head_on, tool="move_train")
    _step(head_on, tool="set_route", train_id="a", next_node="M")
    assert _step(head_on, tool="set_route", train_id="b", next_node="X") == "HEAD_ON_SWAP"

    deadlock = create_environment("MAP-16", seed=0, condition_id="react")
    for destination in ("Y", "M", "X"):
        _step(deadlock, tool="set_route", train_id="b", next_node=destination)
        _step(deadlock, tool="move_train")
    assert deadlock.terminal_reason == "DEADLOCK"


def test_map18_rejects_collision_and_station_overflow_and_censors_deadline() -> None:
    head_on = create_environment("MAP-18", seed=0, condition_id="alert_off")
    assert (
        _set_timetable(
            head_on,
            T_R1={"op": "release", "to": "R2"},
            T_R2={"op": "release", "to": "R1"},
        )
        == "HEAD_ON_COLLISION"
    )

    overfull = create_environment("MAP-18", seed=0, condition_id="alert_off")
    assert (
        _set_timetable(overfull, T_R1={"op": "release", "to": "R2"}) == "STATION_CAPACITY_EXCEEDED"
    )

    deadline = create_environment("MAP-18", seed=0, condition_id="alert_off")
    for _ in range(12):
        _set_timetable(deadline)
    assert deadline.terminal_reason == "DEADLINE_SERVICE_BELOW_70"


def test_map18_alert_is_nonlocal_at_tick_four_and_fault_window_has_exact_endpoints() -> None:
    hidden = create_environment("MAP-18", seed=0, condition_id="alert_off")
    alerted = create_environment("MAP-18", seed=0, condition_id="alert_on")
    for _ in range(4):
        assert hidden.observe().model_dump(mode="json") == alerted.observe().model_dump(mode="json")
        _set_timetable(hidden)
        _set_timetable(alerted)
    off_at_four = hidden.observe()
    on_at_four = alerted.observe()
    assert off_at_four.tick == on_at_four.tick == 4
    assert off_at_four.closed_segments == on_at_four.closed_segments == ()
    assert off_at_four.alert_message_if_any is None
    assert on_at_four.alert_message_if_any is not None
    assert "R2_R3" not in str(on_at_four.alert_message_if_any)
    assert "5" not in str(on_at_four.alert_message_if_any)
    _set_timetable(alerted)
    assert alerted.observe().tick == 5
    assert alerted.observe().closed_segments == ("R2_R3",)
    for _ in range(4):
        _set_timetable(alerted)
    assert alerted.observe().tick == 9
    assert alerted.observe().closed_segments == ("R2_R3",)
    _set_timetable(alerted)
    assert alerted.observe().tick == 10
    assert alerted.observe().closed_segments == ()


def test_map22_rejects_ungrounded_memory_and_enforces_return_deadline() -> None:
    env = create_environment("MAP-22", seed=0, condition_id="history5_graph_memory")
    assert (
        _step(
            env,
            tool="write_memory",
            facts=[{"fact_type": "node_page", "sign_id": "FAKE", "exit_bearings": ["N"]}],
        )
        == "MEMORY_FACT_NOT_OBSERVED"
    )
    assert _step(env, tool="move", bearing="N") == "INVALID_BEARING"

    for _ in range(15):
        _step(env, tool="move", bearing="NE")
        if env.is_terminal:
            break
        _step(env, tool="move", bearing="SW")
        if env.is_terminal:
            break
    assert env.terminal_reason == "STEP_LIMIT_REACHED"


def test_map22_disables_external_memory_in_baseline_and_enforces_memory_capacity() -> None:
    baseline = create_environment("MAP-22", seed=0, condition_id="history5")
    assert (
        _step(
            baseline,
            tool="write_memory",
            facts=[{"fact_type": "node_page", "sign_id": "x", "exit_bearings": ["NE"]}],
        )
        == "ACTION_NOT_AVAILABLE"
    )

    memory = create_environment("MAP-22", seed=0, condition_id="history5_graph_memory")
    _step(memory, tool="observe_signpost")
    sign = memory.observe().inspected_current_sign_detail
    assert sign is not None
    fact = {
        "fact_type": "node_page",
        "sign_id": sign["sign_id"],
        "exit_bearings": list(memory.observe().visible_exit_bearings),
    }
    assert _step(memory, tool="write_memory", facts=[fact] * 33) == "MEMORY_CAPACITY_EXCEEDED"
    assert memory.observe().agent_authored_memory_journal == ()


def test_map22_can_return_at_tick_30_but_rejects_tick_31() -> None:
    env = create_environment("MAP-22", seed=0, condition_id="history5")
    for _ in range(11):
        _step(env, tool="move", bearing="SE")
        _step(env, tool="move", bearing="NW")
    for bearing in ("SE", "E", "NE", "E", "W", "SW", "W", "NW"):
        _step(env, tool="move", bearing=bearing)
    assert env.tick == 30
    assert env.is_success
    before = env.state_hash()
    assert _step(env, tool="move", bearing="SE") == "ALREADY_TERMINAL"
    assert env.tick == 30
    assert env.state_hash() == before


def test_map26_distinguishes_location_error_and_spare_exhaustion() -> None:
    env = create_environment("MAP-26", seed=0, condition_id="recovery_full")
    assert _step(env, tool="test", test_id="bus_load") == "INVALID_LOCATION"

    actions = (
        {"tool": "move", "to": "D"},
        {"tool": "move", "to": "A"},
        {"tool": "move", "to": "B"},
        {"tool": "take_spare", "part_id": "power_regulator"},
        {"tool": "move", "to": "A"},
        {"tool": "replace", "part_id": "power_regulator"},
        {"tool": "move", "to": "B"},
        {"tool": "take_spare", "part_id": "software_image"},
        {"tool": "move", "to": "A"},
        {"tool": "replace", "part_id": "software_image"},
    )
    results = []
    for action in actions:
        results.append(env.step(ScenarioV4Action.model_validate(action, strict=True)).result)
        if env.is_terminal:
            break
    assert results[-1] == "SPARES_EXHAUSTED"
    assert env.metrics()["wrong_replacement_attempts"] == 2


def test_map26_seeded_faults_share_public_start_and_tests_identify_each_fault() -> None:
    environments = [
        create_environment("MAP-26", seed=seed, condition_id="free_diagnosis") for seed in (0, 1, 2)
    ]
    observations = [env.observe().model_dump(mode="json") for env in environments]
    assert observations[0] == observations[1] == observations[2]
    expected = (
        {"antenna_loopback": "ANTENNA_LOOPBACK_OPEN"},
        {"bus_load": "BUS_VOLTAGE_DROOP"},
        {"software_checksum": "IMAGE_CHECKSUM_MISMATCH"},
    )
    for env, unique_reading in zip(environments, expected, strict=True):
        _step(env, tool="move", to="D")
        for test_id in ("bus_load", "antenna_loopback", "software_checksum"):
            _step(env, tool="test", test_id=test_id)
        readings = env.observe().test_readings
        assert {
            key: value for key, value in readings.items() if value in unique_reading.values()
        } == (unique_reading)


def test_map26_repeated_wrong_replacement_costs_more_and_correct_repair_preserves_spare() -> None:
    repeated = create_environment("MAP-26", seed=0, condition_id="free_diagnosis")
    for action in (
        {"tool": "move", "to": "D"},
        {"tool": "move", "to": "A"},
        {"tool": "move", "to": "B"},
        {"tool": "take_spare", "part_id": "power_regulator"},
        {"tool": "move", "to": "A"},
        {"tool": "replace", "part_id": "power_regulator"},
        {"tool": "rollback"},
        {"tool": "move", "to": "B"},
        {"tool": "take_spare", "part_id": "power_regulator"},
        {"tool": "move", "to": "A"},
        {"tool": "replace", "part_id": "power_regulator"},
    ):
        repeated.step(ScenarioV4Action.model_validate(action, strict=True))
    assert repeated.wrong_replace_durations == [1, 2]
    assert repeated.metrics()["same_part_retry_attempts"] == 1

    correct = create_environment("MAP-26", seed=0, condition_id="free_diagnosis")
    for action in (
        {"tool": "move", "to": "D"},
        {"tool": "test", "test_id": "antenna_loopback"},
        {"tool": "move", "to": "A"},
        {"tool": "move", "to": "B"},
        {"tool": "take_spare", "part_id": "antenna_coupler"},
        {"tool": "move", "to": "A"},
        {"tool": "replace", "part_id": "antenna_coupler"},
        {"tool": "restart"},
    ):
        correct.step(ScenarioV4Action.model_validate(action, strict=True))
        if correct.is_terminal:
            break
    assert correct.is_success
    assert correct.metrics()["spare_units_remaining"] == 1


def test_map30_separates_missing_evidence_from_accusation_limit_and_deadline() -> None:
    env = create_environment("MAP-30", seed=0, condition_id="history5_casebook")
    assert _step(env, tool="inspect", evidence_id="Q4_CODE_INDEX") == "EVIDENCE_NOT_AVAILABLE"
    _step(env, tool="move", to="J")
    claim = {
        "tool": "formal_accuse",
        "person_id": "UNKNOWN",
        "event_claims": [],
        "cited_entry_ids": [],
    }
    assert env.step(ScenarioV4Action.model_validate(claim, strict=True)).result == (
        "ACCUSATION_NOT_SUSTAINED"
    )
    assert env.step(ScenarioV4Action.model_validate(claim, strict=True)).result == (
        "ACCUSATION_LIMIT_EXCEEDED"
    )

    deadline = create_environment("MAP-30", seed=0, condition_id="history5_casebook")
    for index in range(40):
        target = "B" if index % 2 == 0 else "H"
        _step(deadline, tool="move", to=target)
        if deadline.is_terminal:
            break
    assert deadline.terminal_reason == "DEADLINE_REACHED"


def test_every_terminal_map_is_immutable_after_a_following_action() -> None:
    map08 = create_environment("MAP-08", seed=0, condition_id="no_hypothesis_table")
    for edge in ("A_B", "B_C", "C_D"):
        _step(map08, tool="move", edge_id=edge)
    _step(map08, tool="interact", target_id="D", operation="repair_leak")

    map16 = create_environment("MAP-16", seed=0, condition_id="react")
    for destination in ("Y", "M", "X"):
        _step(map16, tool="set_route", train_id="b", next_node=destination)
        _step(map16, tool="move_train")

    map18 = create_environment("MAP-18", seed=0, condition_id="alert_off")
    _set_timetable(
        map18,
        T_R1={"op": "release", "to": "R2"},
        T_R2={"op": "release", "to": "R1"},
    )

    map22 = create_environment("MAP-22", seed=0, condition_id="history5_graph_memory")
    for _ in range(15):
        _step(map22, tool="move", bearing="NE")
        if map22.is_terminal:
            break
        _step(map22, tool="move", bearing="SW")
        if map22.is_terminal:
            break

    map26 = create_environment("MAP-26", seed=0, condition_id="recovery_full")
    for action in (
        {"tool": "move", "to": "D"},
        {"tool": "move", "to": "A"},
        {"tool": "move", "to": "B"},
        {"tool": "take_spare", "part_id": "power_regulator"},
        {"tool": "move", "to": "A"},
        {"tool": "replace", "part_id": "power_regulator"},
        {"tool": "move", "to": "B"},
        {"tool": "take_spare", "part_id": "software_image"},
        {"tool": "move", "to": "A"},
        {"tool": "replace", "part_id": "software_image"},
    ):
        map26.step(ScenarioV4Action.model_validate(action, strict=True))
        if map26.is_terminal:
            break

    map30 = create_environment("MAP-30", seed=0, condition_id="history5_casebook")
    _step(map30, tool="move", to="J")
    unsupported_claim = {
        "tool": "formal_accuse",
        "person_id": "UNKNOWN",
        "event_claims": [],
        "cited_entry_ids": [],
    }
    for _ in range(2):
        map30.step(ScenarioV4Action.model_validate(unsupported_claim, strict=True))

    envs = [map08, map16, map18, map22, map26, map30]
    assert all(env.is_terminal for env in envs)
    for env in envs:
        before = env.state_hash()
        result = env.step(ScenarioV4Action(tool="inspect_network"))
        assert result.result == "ALREADY_TERMINAL"
        assert env.state_hash() == before


def test_public_observations_exclude_selected_judge_only_labels() -> None:
    observations = [
        create_environment(map_id, seed=0, condition_id=condition).observe()
        for map_id, condition in (
            ("MAP-08", "no_hypothesis_table"),
            ("MAP-16", "react"),
            ("MAP-18", "alert_off"),
            ("MAP-22", "history5"),
            ("MAP-26", "free_diagnosis"),
            ("MAP-30", "history5"),
        )
    ]
    public_json = json.dumps(
        [item.model_dump(mode="json") for item in observations], ensure_ascii=False
    )
    for private_value in (
        "true_leak",
        "fault_part",
        "MARA_VENN",
        "oracle_trace",
        "failure_traces",
    ):
        assert private_value not in public_json
