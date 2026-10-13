from __future__ import annotations

from collections.abc import Iterable
from itertools import permutations

from agent_arena.arena import ScenarioAction, ScenarioStatus, scenario_action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.scenario.base import ScenarioEnvironment

_WORLD = {
    "SP": "spaceship-escape",
    "LH": "lighthouse-escape",
    "AB": "abyss-escape",
    "PO": "polar-escape",
    "PY": "pyramid-escape",
    "SU": "subway-escape",
    "VO": "volcano-escape",
    "JU": "jungle-escape",
    "LU": "lunar-escape",
    "CA": "castle-escape",
}
_DIFFICULTY = {"E": "easy", "M": "medium", "H": "hard"}


def world(scenario_id: str) -> ScenarioEnvironment:
    family, tier = scenario_id.split("-")
    slug = _WORLD[family]
    environment = create_environment(slug, f"{slug}-world-v3-{_DIFFICULTY[tier]}-zh", seed=31)
    assert isinstance(environment, ScenarioEnvironment)
    environment.reset(seed=31)
    return environment


def act(environment: ScenarioEnvironment, tool: str, **values: str | int):
    action: ScenarioAction = scenario_action_adapter.validate_python({"tool": tool, **values})
    return environment.step(action)


def walk(environment: ScenarioEnvironment, *rooms: str) -> None:
    for room in rooms:
        result, _ = act(environment, "move", destination=room)
        assert result.status.value == "success", (environment.scenario_id, room, result)


def event(environment: ScenarioEnvironment, expected: str) -> None:
    assert environment.step_metadata.scenario_event == expected


def status(environment: ScenarioEnvironment) -> dict[str, str]:
    return {fact.id: fact.value for fact in environment.observe().public_status}


def inspect_all(environment: ScenarioEnvironment, actions: Iterable[tuple[str, str]]) -> None:
    for room, object_id in actions:
        if environment.observe().current_room != room:
            walk(environment, room)
        result, _ = act(environment, "inspect", target=object_id)
        assert result.status.value == "success", (environment.scenario_id, object_id, result)


def test_spaceship_easy_unstable_pod_and_isolated_lab_edge() -> None:
    env = world("SP-E")
    walk(env, "junction", "engineering")
    result, _ = act(env, "interact", target="pressure_regulator", choice="pressurize_pod")
    assert result.status.value == "rejected"
    event(env, "pressure_unstable")
    walk(env, "junction")
    act(env, "interact", target="bulkhead_lab", choice="close")
    result, _ = act(env, "move", destination="lab")
    assert result.status.value == "rejected"
    event(env, "move_rejected")


def test_spaceship_successful_isolation_precedes_same_tick_integrity_loss() -> None:
    env = world("SP-E")
    walk(env, "junction")
    for _ in range(10):
        act(env, "wait", turns=1)
    assert status(env)["ship_integrity"] == "1"
    result, _ = act(env, "interact", target="bulkhead_lab", choice="close")
    assert result.status.value == "success"
    assert status(env)["ship_integrity"] == "1"
    assert env.terminal_status.status is ScenarioStatus.RUNNING


def test_spaceship_medium_requires_suit_and_sample_before_irreversible_seal() -> None:
    env = world("SP-M")
    walk(env, "hub")
    result, _ = act(env, "move", destination="lab")
    assert result.status.value == "rejected"
    event(env, "move_rejected")
    walk(env, "repair_bay")
    result, _ = act(env, "interact", target="pod_regulator", choice="pressurize")
    assert result.status.value == "rejected"
    event(env, "pressure_unstable")


def test_spaceship_hard_requires_suit_and_both_isolations_before_pressurizing() -> None:
    env = world("SP-H")
    walk(env, "hub")
    result, _ = act(env, "move", destination="lab")
    assert result.status.value == "rejected"
    event(env, "move_rejected")
    walk(env, "repair_bay")
    result, _ = act(env, "interact", target="pod_regulator", choice="pressurize")
    assert result.status.value == "rejected"
    event(env, "pressure_unstable")


def test_lighthouse_easy_wrong_bearing_and_unconfirmed_boarding() -> None:
    env = world("LH-E")
    walk(env, "tower_base", "lamp_room")
    act(env, "interact", target="beacon_switch", choice="on")
    result, _ = act(env, "interact", target="beacon_switch", choice="send_signal")
    assert result.status.value == "rejected"
    event(env, "signal_not_acknowledged")
    walk(env, "tower_base", "east_pier")
    result, _ = act(env, "interact", target="signal_flag", choice="board_rescue")
    assert result.status.value == "rejected"
    event(env, "boarding_rejected")


def test_lighthouse_medium_wrong_direction_and_red_first_are_recoverable() -> None:
    env = world("LH-M")
    walk(env, "tower_base", "lamp_room")
    result, _ = act(env, "interact", target="lamp", choice="emit")
    assert result.status.value == "rejected"
    event(env, "wrong_bearing")
    act(env, "interact", target="lens", choice="west")
    act(env, "interact", target="lamp", choice="red")
    result, _ = act(env, "interact", target="lamp", choice="emit")
    assert result.status.value == "rejected"
    event(env, "signal_not_acknowledged")
    assert status(env)["confirmed_stages"] == "0"


def test_lighthouse_hard_wrong_symbol_and_early_emit_are_rejected() -> None:
    env = world("LH-H")
    walk(env, "tower_base", "lamp_room")
    result, _ = act(env, "interact", target="signal_console", choice="long")
    assert result.status.value == "rejected"
    event(env, "sequence_rejected")
    result, _ = act(env, "interact", target="signal_console", choice="emit")
    assert result.status.value == "rejected"
    event(env, "signal_stage_missing")


def test_abyss_easy_unclosed_leak_rebounds_and_lift_checks_water() -> None:
    env = world("AB-E")
    walk(env, "valve", "pump")
    act(env, "interact", target="drain_pump", choice="pump")
    before_wait = int(status(env)["water"])
    act(env, "wait", turns=1)
    assert int(status(env)["water"]) == before_wait + 1
    walk(env, "lift")
    result, _ = act(env, "interact", target="surface_lift", choice="surface")
    assert result.status.value == "rejected"
    event(env, "water_too_high")


def test_abyss_medium_pressure_gate_and_sample_gate() -> None:
    env = world("AB-M")
    result, _ = act(env, "interact", target="equalizer", choice="open")
    assert result.status.value == "rejected"
    event(env, "pressure_delta_high")
    walk(env, "pump")
    for _ in range(3):
        act(env, "interact", target="east_pump", choice="raise_pressure")
    walk(env, "control")
    result, _ = act(env, "interact", target="equalizer", choice="open")
    assert result.status.value == "rejected"
    event(env, "sample_missing")


def test_abyss_hard_flood_growth_and_finite_pump_energy() -> None:
    env = world("AB-H")
    walk(env, "pump")
    for _ in range(3):
        act(env, "interact", target="pump_console", choice="pump_machine")
    assert int(status(env)["pump_uses"]) == 0
    result, _ = act(env, "interact", target="pump_console", choice="pump_machine")
    assert result.status.value == "rejected"
    event(env, "pump_empty")
    assert status(env)["greenhouse_lost"] == "true"


def test_polar_easy_weather_loss_is_explicit_and_reset_restarts_cycle() -> None:
    env = world("PO-E")
    initial = status(env)
    assert initial["weather"] == "CLEAR"
    walk(
        env,
        "snow_pass",
        "station",
        "snow_pass",
        "station",
        "snow_pass",
        "shelter",
        "snow_pass",
        "station",
        "snow_pass",
        "shelter",
        "snow_pass",
        "station",
        "snow_pass",
    )
    assert env.terminal_status.status is ScenarioStatus.FAILURE
    assert env.terminal_status.failure_reason == "户外体热降至零。"
    reset = env.reset(seed=31)
    assert reset.tick == 0
    assert status(env)["body_heat"] == "10"
    assert status(env)["weather"] == "CLEAR"


def test_polar_medium_vehicle_burns_finite_fuel_and_heater_runs_out() -> None:
    env = world("PO-M")
    walk(env, "supply_hut", "vehicle_pad")
    act(env, "interact", target="snowmobile", choice="ride_to_drill")
    act(env, "pickup", item="ice_core")
    act(env, "interact", target="snowmobile_return", choice="ride_to_pad")
    assert status(env)["fuel"] == "0"
    walk(env, "supply_hut")
    result, _ = act(env, "interact", target="heater", choice="warm")
    assert result.status.value == "rejected"
    event(env, "heater_fuel_empty")
    env = world("PO-M")
    walk(env, "supply_hut")
    act(env, "interact", target="heater", choice="warm")
    act(env, "interact", target="heater", choice="warm")
    result, _ = act(env, "interact", target="heater", choice="warm")
    assert result.status.value == "rejected"
    event(env, "heater_fuel_empty")


def test_polar_hard_rope_gate_and_one_person_escort_limit() -> None:
    env = world("PO-H")
    walk(env, "heated_hut")
    result, _ = act(env, "move", destination="ridge")
    assert result.status.value == "rejected"
    event(env, "move_rejected")
    act(env, "pickup", item="rope_kit")
    act(env, "interact", target="rope_kit", choice="fix")
    walk(env, "ridge", "weather_post")
    act(env, "interact", target="researcher_b", choice="escort")
    result, _ = act(env, "interact", target="researcher_b", choice="escort")
    assert result.status.value == "rejected"
    event(env, "escort_capacity_full")
    assert status(env)["escorted_crew"] == "b"


def test_polar_hard_rescue_requires_reserve_and_records_weather_for_current_action() -> None:
    env = world("PO-H")
    initial = status(env)
    assert initial["weather"] == "CLEAR"
    assert initial["fuel"] == "4"
    walk(env, "heated_hut")
    act(env, "pickup", item="rope_kit")
    act(env, "interact", target="rope_kit", choice="fix")
    for _ in range(4):
        act(env, "interact", target="heater", choice="rest")
    assert status(env)["fuel"] == "0"
    walk(env, "drill_camp")
    act(env, "interact", target="researcher_a", choice="escort")
    walk(env, "heated_hut", "base")
    walk(env, "ridge", "weather_post")
    act(env, "interact", target="researcher_b", choice="escort")
    walk(env, "ridge", "heated_hut", "base")
    assert env.terminal_status.status is ScenarioStatus.PARTIAL_SUCCESS
    assert env.terminal_status.failure_reason == "两名队员获救，但返程燃料低于 1。"


def test_pyramid_easy_requires_public_clue_and_keeps_treasury_locked() -> None:
    env = world("PY-E")
    walk(env, "east_mural", "sun_chamber")
    result, _ = act(env, "submit", target="sun_dial", answer="EAST")
    assert result.status.value == "rejected"
    event(env, "puzzle_clues_missing")
    result, _ = act(env, "move", destination="treasury")
    assert result.status.value == "rejected"
    event(env, "move_rejected")


def test_pyramid_medium_requires_all_three_clues_and_rejects_wrong_order() -> None:
    env = world("PY-M")
    walk(env, "north_tomb")
    act(env, "inspect", target="north_stone")
    walk(env, "entrance", "west_tomb")
    act(env, "inspect", target="west_stone")
    walk(env, "entrance", "south_tomb")
    act(env, "inspect", target="south_stone")
    walk(env, "entrance", "sun_chamber")
    result, _ = act(env, "submit", target="sequence_lock", answer="SUN-STAR-MOON")
    assert result.status.value == "rejected"
    event(env, "puzzle_incorrect")
    result, _ = act(env, "move", destination="treasury")
    assert result.status.value == "rejected"
    event(env, "move_rejected")


def test_pyramid_hard_bridge_clues_and_treasury_are_three_separate_gates() -> None:
    env = world("PY-H")
    walk(env, "bridge")
    result, _ = act(env, "move", destination="rune_hall")
    assert result.status.value == "rejected"
    event(env, "move_rejected")
    act(env, "interact", target="bridge_mechanism", choice="fix")
    walk(env, "rune_hall")
    result, _ = act(env, "submit", target="judgment_lock", answer="SUN-SCARAB-REED-EYE")
    assert result.status.value == "rejected"
    event(env, "puzzle_clues_missing")
    for clue in ("rune_sun", "rune_scarab", "rune_reed", "rune_eye"):
        act(env, "inspect", target=clue)
    result, _ = act(env, "submit", target="judgment_lock", answer="SUN-EYE-SCARAB-REED")
    assert result.status.value == "rejected"
    event(env, "puzzle_incorrect")


def test_pyramid_medium_and_hard_constraints_are_unique_and_each_clue_matters() -> None:
    medium_permutations = list(permutations(("SUN", "MOON", "STAR")))
    medium_clues = (
        lambda row: row.index("SUN") < row.index("STAR"),
        lambda row: row[0] != "MOON",
        lambda row: row[1] != "STAR",
    )
    assert [row for row in medium_permutations if all(clue(row) for clue in medium_clues)] == [
        ("SUN", "MOON", "STAR")
    ]
    for omitted in range(len(medium_clues)):
        assert (
            len(
                [
                    row
                    for row in medium_permutations
                    if all(clue(row) for index, clue in enumerate(medium_clues) if index != omitted)
                ]
            )
            > 1
        )

    hard_permutations = list(permutations(("SUN", "SCARAB", "REED", "EYE")))
    hard_clues = (
        lambda row: row.index("SUN") < row.index("SCARAB"),
        lambda row: abs(row.index("SUN") - row.index("SCARAB")) == 1,
        lambda row: row.index("SUN") < row.index("REED"),
        lambda row: row.index("REED") < row.index("EYE"),
    )
    assert [row for row in hard_permutations if all(clue(row) for clue in hard_clues)] == [
        ("SUN", "SCARAB", "REED", "EYE")
    ]
    for omitted in range(len(hard_clues)):
        assert (
            len(
                [
                    row
                    for row in hard_permutations
                    if all(clue(row) for index, clue in enumerate(hard_clues) if index != omitted)
                ]
            )
            > 1
        )


def test_subway_easy_red_signal_and_wrong_route_do_not_move_train() -> None:
    env = world("SU-E")
    result, _ = act(env, "interact", target="train_1", choice="advance")
    assert result.status.value == "rejected"
    event(env, "signal_red")
    act(env, "interact", target="switch", choice="south")
    act(env, "interact", target="signal_panel", choice="green_train_1")
    result, _ = act(env, "interact", target="train_1", choice="advance")
    assert result.status.value == "rejected"
    event(env, "route_mismatch")
    assert status(env)["train_1_segment"] == "yard"


def test_subway_medium_shared_track_is_exclusive_and_route_locks_after_departure() -> None:
    env = world("SU-M")
    act(env, "interact", target="switch_a", choice="platform_a")
    act(env, "interact", target="switch_b", choice="platform_b")
    act(env, "interact", target="signal_panel", choice="green_a")
    act(env, "interact", target="train_a", choice="advance")
    result, _ = act(env, "interact", target="switch_a", choice="platform_a")
    assert result.status.value == "rejected"
    event(env, "route_locked")
    act(env, "interact", target="signal_panel", choice="green_b")
    result, _ = act(env, "interact", target="train_b", choice="advance")
    assert result.status.value == "rejected"
    event(env, "track_occupied")


def test_subway_hard_maintenance_lock_and_priority_failure_are_explicit() -> None:
    env = world("SU-H")
    assert status(env)["maintenance_lock"] == "false"
    result, _ = act(env, "interact", target="maintenance_console", choice="release_b")
    assert result.status.value == "rejected"
    event(env, "maintenance_not_active")
    act(env, "interact", target="switch_panel", choice="route_b")
    act(env, "interact", target="signal_panel", choice="green_b")
    act(env, "interact", target="train_b", choice="advance")
    assert status(env)["maintenance_lock"] == "true"
    result, _ = act(env, "interact", target="switch_panel", choice="route_c")
    assert result.status.value == "rejected"
    event(env, "maintenance_locked")
    act(env, "interact", target="train_b", choice="advance")
    act(env, "interact", target="maintenance_console", choice="release_b")
    act(env, "interact", target="switch_panel", choice="route_c")
    act(env, "interact", target="signal_panel", choice="green_c")
    act(env, "interact", target="train_c", choice="advance")
    result, _ = act(env, "interact", target="train_c", choice="advance")
    assert result.status.value == "success"
    assert env.terminal_status.status is ScenarioStatus.FAILURE
    assert env.terminal_status.failure_reason == "C 车早于 A 车抵达，违反公开优先顺序。"


def test_volcano_easy_closed_valve_means_no_cooling_and_departure_is_gated() -> None:
    env = world("VO-E")
    walk(env, "cooling_room")
    act(env, "interact", target="main_pump", choice="on")
    act(env, "wait", turns=1)
    assert status(env)["pump_confirmed"] == "false"
    walk(env, "exit_platform")
    result, _ = act(env, "interact", target="cable_car", choice="depart")
    assert result.status.value == "rejected"
    event(env, "evacuation_precondition")


def test_volcano_medium_flow_capacity_and_heat_gate() -> None:
    env = world("VO-M")
    act(env, "interact", target="pump_switch", choice="run_a_high")
    walk(env, "loop_b_room")
    result, _ = act(env, "interact", target="valve_b", choice="high")
    assert result.status.value == "rejected"
    event(env, "flow_capacity_exceeded")
    walk(env, "junction", "service_lift")
    result, _ = act(env, "interact", target="evac", choice="depart")
    assert result.status.value == "rejected"
    event(env, "balance_not_reached")


def test_volcano_hard_shield_and_coolant_are_hard_preconditions() -> None:
    env = world("VO-H")
    walk(env, "cooling_hub", "lava_probe")
    result, _ = act(env, "pickup", item="core_sample")
    assert result.status.value == "rejected"
    event(env, "probe_shield_required")
    walk(env, "cooling_hub")
    act(env, "interact", target="pump_control", choice="on")
    for _ in range(7):
        act(env, "wait", turns=1)
    assert status(env)["coolant"] == "0"
    result, _ = act(env, "interact", target="pump_control", choice="on")
    assert result.status.value == "rejected"
    event(env, "coolant_empty")


def test_jungle_easy_wrong_branch_recovers_and_report_requires_notes() -> None:
    env = world("JU-E")
    walk(env, "fork", "blue_tree", "fork", "red_tree", "ruin")
    result, _ = act(env, "submit", target="field_report", answer="ruin_notes")
    assert result.status.value == "rejected"
    event(env, "notes_missing")
    result, _ = act(env, "pickup", item="ruin_notes")
    assert result.status.value == "success"
    walk(env, "red_tree", "fork", "camp")
    result, _ = act(env, "submit", target="field_report", answer="wrong")
    assert result.status.value == "rejected"
    event(env, "report_invalid")


def test_jungle_medium_turning_gate_closes_old_edge_but_keeps_safe_return() -> None:
    env = world("JU-M")
    walk(env, "fork", "north_path", "hidden_ruin", "north_path", "fork", "turntable")
    act(env, "interact", target="turntable", choice="set_east")
    walk(env, "fork", "north_path")
    result, _ = act(env, "move", destination="hidden_ruin")
    assert result.status.value == "rejected"
    event(env, "move_rejected")
    walk(env, "fork", "turntable", "fork", "east_path", "hidden_ruin")
    result, _ = act(env, "interact", target="return_shortcut", choice="open_return")
    assert result.status.value == "rejected"
    event(env, "shortcut_precondition")


def test_jungle_hard_tide_and_distributed_clues_gate_stone_sequence() -> None:
    env = world("JU-H")
    act(env, "inspect", target="weather_log")
    walk(env, "fork")
    act(env, "inspect", target="oak_mark")
    walk(env, "river_bank")
    act(env, "inspect", target="fern_mark")
    walk(env, "fork", "high_ridge")
    act(env, "inspect", target="vine_mark")
    walk(env, "stone_circle")
    result, _ = act(env, "interact", target="three_stones", choice="fern")
    assert result.status.value == "rejected"
    event(env, "marker_sequence_reset")
    assert status(env)["marker_progress"] == "0"
    result, _ = act(env, "interact", target="three_stones", choice="oak")
    assert result.status.value == "success"
    result, _ = act(env, "interact", target="three_stones", choice="fern")
    assert result.status.value == "success"
    result, _ = act(env, "interact", target="three_stones", choice="vine")
    assert result.status.value == "success"
    result, _ = act(env, "interact", target="three_stones", choice="vine")
    assert result.status.value == "rejected"
    event(env, "sequence_complete")


def test_lunar_easy_requires_suit_and_patch_kit() -> None:
    env = world("LU-E")
    walk(env, "airlock")
    result, _ = act(env, "interact", target="suit_rack", choice="cycle_out")
    assert result.status.value == "rejected"
    event(env, "suit_required")
    walk(env, "habitat", "storage", "habitat", "airlock")
    act(env, "interact", target="suit_rack", choice="prepare")
    act(env, "interact", target="suit_rack", choice="cycle_out")
    walk(env, "solar_pad")
    result, _ = act(env, "use", item="patch_kit", target="broken_panel")
    assert result.status.value == "rejected"
    event(env, "panel_repair_precondition")


def test_lunar_medium_shadow_and_missing_module_reject_charging() -> None:
    env = world("LU-M")
    walk(env, "power_room", "airlock")
    act(env, "interact", target="airlock", choice="prepare")
    act(env, "interact", target="airlock", choice="cycle_out")
    walk(env, "solar_array")
    result, _ = act(env, "interact", target="solar_charger", choice="charge")
    assert result.status.value == "rejected"
    event(env, "module_missing")

    env = world("LU-M")
    walk(env, "power_room")
    act(env, "pickup", item="battery_module")
    walk(env, "airlock")
    act(env, "interact", target="airlock", choice="prepare")
    act(env, "interact", target="airlock", choice="cycle_out")
    act(env, "wait", turns=1)
    act(env, "wait", turns=1)
    act(env, "wait", turns=1)
    walk(env, "solar_array")
    assert status(env)["sun_phase"] == "SHADOW"
    result, _ = act(env, "interact", target="solar_charger", choice="charge")
    assert result.status.value == "rejected"
    event(env, "no_sunlight")


def test_lunar_hard_requires_cell_for_mast_and_mast_before_escort() -> None:
    env = world("LU-H")
    walk(env, "supply", "airlock")
    act(env, "interact", target="airlock", choice="prepare")
    act(env, "interact", target="airlock", choice="cycle_out")
    walk(env, "mast")
    result, _ = act(env, "interact", target="signal_mast", choice="repair")
    assert result.status.value == "rejected"
    event(env, "mast_repair_precondition")
    walk(env, "airlock", "relay_point")
    result, _ = act(env, "interact", target="astronaut_b", choice="escort")
    assert result.status.value == "rejected"
    event(env, "mast_offline")


def test_castle_easy_requires_both_dialogues_before_key_box_and_key() -> None:
    env = world("CA-E")
    walk(env, "kitchen", "pantry")
    result, _ = act(env, "inspect", target="key_box")
    assert result.status.value == "rejected"
    event(env, "key_box_clue_gate")
    result, _ = act(env, "pickup", item="archive_key")
    assert result.status.value == "rejected"
    event(env, "key_not_revealed")


def test_castle_medium_requires_cross_checked_evidence_and_correct_verdict() -> None:
    env = world("CA-M")
    walk(env, "records_room", "hall")
    result, _ = act(env, "submit", target="case_board", answer="CARETAKER")
    assert result.status.value == "rejected"
    event(env, "evidence_incomplete")
    walk(env, "records_room")
    act(env, "inspect", target="access_log")
    act(env, "inspect", target="clock_report")
    walk(env, "hall", "watchtower")
    act(env, "interact", target="guard", choice="night_patrol")
    walk(env, "hall")
    result, _ = act(env, "submit", target="case_board", answer="GUARD")
    assert result.status.value == "rejected"
    event(env, "accusation_inconsistent")


def test_castle_hard_secret_route_and_verdict_do_not_bypass_evidence() -> None:
    env = world("CA-H")
    walk(env, "key_archive")
    act(env, "inspect", target="key_ledger")
    result, _ = act(env, "move", destination="secret_passage")
    assert result.status.value == "rejected"
    event(env, "move_rejected")
    walk(env, "grand_hall")
    result, _ = act(
        env,
        "submit",
        target="verdict_desk",
        answer="GARETH|KEY_LEDGER+SEAL_WAX",
    )
    assert result.status.value == "rejected"
    event(env, "evidence_incomplete")
