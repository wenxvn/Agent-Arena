"""Reference policy that reads only serialized public ScenarioObservation."""

from __future__ import annotations

from collections import deque

from agent_arena.arena import ScenarioAction, ScenarioObservation, scenario_action_adapter

_TOPOLOGY: dict[str, dict[str, tuple[str, ...]]] = {
    "SP-E": {
        "bridge": ("junction",),
        "junction": ("bridge", "engineering", "lab"),
        "lab": ("junction",),
        "engineering": ("junction", "escape_pod"),
        "escape_pod": ("engineering",),
    },
    "SP-M": {
        "bridge": ("hub",),
        "hub": ("bridge", "suit_room", "lab", "repair_bay"),
        "suit_room": ("hub",),
        "lab": ("hub",),
        "repair_bay": ("hub", "escape_pod"),
        "escape_pod": ("repair_bay",),
    },
    "SP-H": {
        "bridge": ("hub",),
        "hub": ("bridge", "suit_room", "lab", "cargo", "repair_bay"),
        "suit_room": ("hub", "service_duct"),
        "service_duct": ("suit_room", "cargo"),
        "lab": ("hub",),
        "cargo": ("hub", "service_duct"),
        "repair_bay": ("hub", "escape_pod"),
        "escape_pod": ("repair_bay",),
    },
    "AB-E": {
        "control": ("valve",),
        "valve": ("control", "pump"),
        "pump": ("valve", "lift"),
        "lift": ("pump",),
    },
    "AB-M": {
        "control": ("west", "east", "pump", "lift"),
        "west": ("control",),
        "east": ("control",),
        "pump": ("control",),
        "lift": ("control",),
    },
    "AB-H": {
        "control": ("greenhouse", "pump", "machine", "lift"),
        "greenhouse": ("control",),
        "pump": ("control",),
        "machine": ("control",),
        "lift": ("control",),
    },
    "LH-E": {
        "keeper_house": ("tower_base",),
        "tower_base": ("keeper_house", "lamp_room", "east_pier"),
        "lamp_room": ("tower_base",),
        "east_pier": ("tower_base",),
    },
    "LH-M": {
        "keeper_house": ("tower_base",),
        "tower_base": ("keeper_house", "lamp_room", "signal_gallery", "west_dock"),
        "lamp_room": ("tower_base",),
        "signal_gallery": ("tower_base",),
        "west_dock": ("tower_base",),
    },
    "LH-H": {
        "keeper_house": ("tower_base",),
        "tower_base": ("keeper_house", "lamp_room", "signal_gallery", "north_beacon"),
        "lamp_room": ("tower_base",),
        "signal_gallery": ("tower_base",),
        "north_beacon": ("tower_base",),
    },
    "PO-E": {
        "station": ("snow_pass", "observatory"),
        "observatory": ("station",),
        "snow_pass": ("station", "shelter"),
        "shelter": ("snow_pass",),
    },
    "PO-M": {
        "station": ("supply_hut",),
        "supply_hut": ("station", "ice_field", "vehicle_pad"),
        "ice_field": ("supply_hut", "drill_site"),
        "drill_site": ("ice_field", "return_route"),
        "return_route": ("drill_site", "station"),
        "vehicle_pad": ("supply_hut",),
    },
    "PO-H": {
        "base": ("heated_hut", "ridge"),
        "heated_hut": ("base", "drill_camp", "ridge"),
        "drill_camp": ("heated_hut",),
        "ridge": ("base", "weather_post", "heated_hut"),
        "weather_post": ("ridge",),
    },
    "PY-E": {
        "entrance": ("east_mural",),
        "east_mural": ("entrance", "sun_chamber"),
        "sun_chamber": ("east_mural", "treasury"),
        "treasury": ("sun_chamber",),
    },
    "PY-M": {
        "entrance": ("north_tomb", "west_tomb", "south_tomb", "sun_chamber"),
        "north_tomb": ("entrance",),
        "west_tomb": ("entrance",),
        "south_tomb": ("entrance",),
        "sun_chamber": ("entrance", "treasury"),
        "treasury": ("sun_chamber",),
    },
    "PY-H": {
        "entrance": ("bridge", "rune_hall"),
        "bridge": ("entrance", "rune_hall"),
        "rune_hall": ("bridge", "treasury"),
        "treasury": ("rune_hall",),
    },
    "VO-E": {
        "control": ("cooling_room", "viewing_deck"),
        "cooling_room": ("control", "exit_platform"),
        "exit_platform": ("cooling_room",),
        "viewing_deck": ("control",),
    },
    "VO-M": {
        "control": ("junction",),
        "junction": ("control", "loop_a_room", "loop_b_room", "service_lift"),
        "loop_a_room": ("junction",),
        "loop_b_room": ("junction",),
        "service_lift": ("junction",),
    },
    "VO-H": {
        "command": ("cooling_hub", "cable_station"),
        "cooling_hub": ("command", "lava_probe", "aux_tank", "vent_room"),
        "lava_probe": ("cooling_hub",),
        "aux_tank": ("cooling_hub",),
        "vent_room": ("cooling_hub",),
        "cable_station": ("command",),
    },
    "JU-E": {
        "camp": ("fork",),
        "fork": ("camp", "red_tree", "blue_tree", "white_tree"),
        "red_tree": ("fork", "ruin"),
        "blue_tree": ("fork", "creek"),
        "white_tree": ("fork", "lookout"),
        "ruin": ("red_tree",),
        "creek": ("blue_tree",),
        "lookout": ("white_tree",),
    },
    "JU-M": {
        "camp": ("fork",),
        "fork": ("camp", "turntable", "north_path", "east_path"),
        "turntable": ("fork",),
        "north_path": ("fork", "hidden_ruin"),
        "east_path": ("fork", "hidden_ruin"),
        "hidden_ruin": ("north_path", "east_path", "camp"),
    },
    "JU-H": {
        "camp": ("fork",),
        "fork": ("camp", "river_bank", "high_ridge"),
        "river_bank": ("fork", "stone_circle"),
        "high_ridge": ("fork", "stone_circle"),
        "stone_circle": ("river_bank", "high_ridge", "altar"),
        "altar": ("stone_circle", "return_pass"),
        "return_pass": ("altar", "camp"),
    },
    "LU-E": {
        "habitat": ("airlock", "storage"),
        "airlock": ("habitat", "solar_pad"),
        "solar_pad": ("airlock",),
        "storage": ("habitat",),
    },
    "LU-M": {
        "habitat": ("power_room",),
        "power_room": ("habitat", "airlock"),
        "airlock": ("power_room", "solar_array", "antenna"),
        "solar_array": ("airlock",),
        "antenna": ("airlock",),
    },
    "LU-H": {
        "habitat": ("supply",),
        "supply": ("habitat", "airlock"),
        "airlock": ("supply", "relay_point", "mast"),
        "relay_point": ("airlock", "crater_rim"),
        "crater_rim": ("relay_point", "mast"),
        "mast": ("airlock", "crater_rim"),
    },
    "CA-E": {
        "great_hall": ("gatehouse", "kitchen", "library"),
        "gatehouse": ("great_hall",),
        "kitchen": ("great_hall", "pantry"),
        "pantry": ("kitchen",),
        "library": ("great_hall",),
    },
    "CA-M": {
        "hall": ("watchtower", "courtyard", "infirmary", "records_room"),
        "watchtower": ("hall",),
        "courtyard": ("hall",),
        "infirmary": ("hall",),
        "records_room": ("hall", "secret_study"),
        "secret_study": ("records_room",),
    },
    "CA-H": {
        "grand_hall": (
            "key_archive",
            "seal_chamber",
            "watch_post",
            "infirmary",
            "servant_quarters",
        ),
        "key_archive": ("grand_hall", "secret_passage"),
        "seal_chamber": ("grand_hall", "secret_passage"),
        "watch_post": ("grand_hall",),
        "infirmary": ("grand_hall",),
        "servant_quarters": ("grand_hall",),
        "secret_passage": ("key_archive", "seal_chamber"),
    },
}


def public_oracle_action(observation: ScenarioObservation) -> ScenarioAction:
    """Choose one action using only the supplied public observation and fixed plan."""

    scenario_id = observation.scenario_id
    status = {fact.id: fact.value for fact in observation.public_status}
    inventory = set(observation.inventory)
    room = observation.current_room

    def action(tool: str, **values: str | int) -> ScenarioAction:
        return scenario_action_adapter.validate_python({"tool": tool, **values})

    def move_to(destination: str) -> ScenarioAction | None:
        if room == destination:
            return None
        topology = _TOPOLOGY[scenario_id]
        queue: deque[tuple[str, str | None]] = deque([(room, None)])
        visited = {room}
        while queue:
            current, first = queue.popleft()
            for neighbor in topology.get(current, ()):
                if neighbor in visited:
                    continue
                if current == room and neighbor not in observation.available_exits:
                    continue
                next_first = neighbor if first is None else first
                if neighbor == destination:
                    return action("move", destination=next_first)
                visited.add(neighbor)
                queue.append((neighbor, next_first))
        return None

    def to(destination: str) -> ScenarioAction:
        return move_to(destination) or action("wait", turns=1)

    if scenario_id.startswith("SP-"):
        difficulty = scenario_id[-1]
        if difficulty == "E":
            if room not in {"junction", "engineering", "escape_pod"}:
                return to("junction")
            if room == "junction":
                return (
                    action("interact", target="bulkhead_lab", choice="close")
                    if status["lab_bulkhead"] == "open"
                    else to("engineering")
                )
            if room == "engineering":
                return (
                    action("interact", target="pressure_regulator", choice="pressurize_pod")
                    if status["pod_pressurized"] == "false"
                    else to("escape_pod")
                )
            return action("interact", target="launch_control", choice="evacuate")
        if "suit" not in inventory:
            if room != "suit_room":
                return to("suit_room")
            return action("pickup", item="suit")
        required = "sample_canister" if difficulty == "M" else "blackbox"
        if required not in inventory:
            return to("lab") if room != "lab" else action("pickup", item=required)
        if difficulty == "H" and "sealant" not in inventory:
            return to("cargo") if room != "cargo" else action("pickup", item="sealant")
        bulkhead = "lab_door" if difficulty == "M" else "door_lab"
        if status["lab_bulkhead"] == "open":
            return (
                to("hub") if room != "hub" else action("interact", target=bulkhead, choice="close")
            )
        if difficulty == "H" and status["leak_rate"] != "0":
            return (
                to("hub")
                if room != "hub"
                else action("interact", target="door_cargo", choice="close")
            )
        if difficulty == "H" and status["hull_repaired"] == "false":
            return (
                to("repair_bay")
                if room != "repair_bay"
                else action("use", item="sealant", target="hull_patch")
            )
        if difficulty == "H" and status["pod_pressurized"] == "false":
            return (
                to("repair_bay")
                if room != "repair_bay"
                else action("interact", target="pod_regulator", choice="pressurize")
            )
        if difficulty == "M" and status["pod_pressurized"] == "false":
            return (
                to("repair_bay")
                if room != "repair_bay"
                else action("interact", target="pod_regulator", choice="pressurize")
            )
        return (
            to("escape_pod")
            if room != "escape_pod"
            else action("interact", target="launch_control", choice="evacuate")
        )

    if scenario_id.startswith("AB-"):
        if scenario_id == "AB-E":
            if status["leak_open"] == "true":
                return (
                    to("valve")
                    if room != "valve"
                    else action("interact", target="leak_valve", choice="close")
                )
            if int(status["water"]) > 2:
                return (
                    to("pump")
                    if room != "pump"
                    else action("interact", target="drain_pump", choice="pump")
                )
            return (
                to("lift")
                if room != "lift"
                else action("interact", target="surface_lift", choice="surface")
            )
        if scenario_id == "AB-M":
            if "sample_canister" not in inventory:
                return to("west") if room != "west" else action("pickup", item="sample_canister")
            if int(status["pressure_delta"]) > 1:
                return (
                    to("pump")
                    if room != "pump"
                    else action("interact", target="east_pump", choice="raise_pressure")
                )
            if status["equalizer_open"] == "false":
                return (
                    to("control")
                    if room != "control"
                    else action("interact", target="equalizer", choice="open")
                )
            return (
                to("lift")
                if room != "lift"
                else action("interact", target="surface_lift", choice="surface")
            )
        if status["greenhouse_gate_open"] == "true":
            return (
                to("greenhouse")
                if room != "greenhouse"
                else action("interact", target="overflow_gate", choice="close")
            )
        if "data_disk" not in inventory:
            return to("machine") if room != "machine" else action("pickup", item="data_disk")
        if int(status["machine_water"]) >= 3:
            return (
                to("pump")
                if room != "pump"
                else action("interact", target="pump_console", choice="pump_machine")
            )
        return (
            to("lift")
            if room != "lift"
            else action("interact", target="surface_lift", choice="surface")
        )

    if scenario_id.startswith("LH-"):
        if status["rescue_confirmed"] == "true":
            dock = {"LH-E": "east_pier", "LH-M": "west_dock", "LH-H": "north_beacon"}[scenario_id]
            return (
                to(dock)
                if room != dock
                else action(
                    "interact",
                    target={"LH-E": "signal_flag", "LH-M": "rescue_boat", "LH-H": "rescue_beacon"}[
                        scenario_id
                    ],
                    choice="board_rescue" if scenario_id == "LH-E" else "board",
                )
            )
        if room != "lamp_room":
            target_room = "lamp_room"
            next_action = move_to(target_room)
            if next_action is not None:
                return next_action
            if room == "keeper_house" and scenario_id != "LH-E":
                return to("signal_gallery")
            return action("wait", turns=1)
        direction = (
            "EAST" if scenario_id == "LH-E" else "WEST" if scenario_id == "LH-M" else "NORTH"
        )
        if status["lens_direction"] != direction:
            return action("interact", target="lens", choice=direction.lower())
        if scenario_id == "LH-E":
            if status["lamp_on"] == "false":
                return action("interact", target="beacon_switch", choice="on")
            return (
                action("wait", turns=1)
                if status["tide"] != "LOW"
                else action("interact", target="beacon_switch", choice="send_signal")
            )
        if scenario_id == "LH-M":
            stage = int(status["confirmed_stages"])
            if stage == 0:
                return (
                    action("interact", target="lamp", choice="emit")
                    if status["lamp_color"] == "WHITE"
                    else action("interact", target="lamp", choice="white")
                )
            if stage == 1:
                if status["lamp_color"] != "RED":
                    return action("interact", target="lamp", choice="red")
                return (
                    action("wait", turns=1)
                    if status["tide"] != "HIGH"
                    else action("interact", target="lamp", choice="emit")
                )
            return action("wait", turns=1)
        stage = int(status["confirmed_stages"])
        if stage < 2:
            return action("interact", target="signal_console", choice=("short", "long")[stage])
        return (
            action("wait", turns=1)
            if status["tide"] != "HIGH" or status["fog"] != "CLEAR"
            else action("interact", target="signal_console", choice="emit")
        )

    if scenario_id.startswith("PO-"):
        if scenario_id == "PO-E":
            if status["weather_radio_read"] == "false" and room == "station":
                return action("inspect", target="weather_radio")
            if room != "shelter":
                return to("shelter")
            if status["radio_antenna_read"] == "false":
                return action("inspect", target="radio_antenna")
            return action("interact", target="radio_antenna", choice="activate")
        if scenario_id == "PO-M":
            if status["supply_log_read"] == "false":
                if room != "supply_hut":
                    return to("supply_hut")
                return action("inspect", target="supply_log")
            if "ice_core" in inventory:
                if room == "drill_site" and status["fuel"] != "0":
                    return action("interact", target="snowmobile_return", choice="ride_to_pad")
                if room != "station":
                    return to("station")
                if status["sample_receiver_read"] == "false":
                    return action("inspect", target="sample_receiver")
                return action("interact", target="sample_receiver", choice="deliver")
            if room == "drill_site":
                return action("pickup", item="ice_core")
            if room == "vehicle_pad" and status["fuel"] != "0":
                return action("interact", target="snowmobile", choice="ride_to_drill")
            if room == "station":
                return to("vehicle_pad")
            if room == "vehicle_pad":
                return to("drill_site")
            return action("pickup", item="ice_core") if room == "drill_site" else to("drill_site")
        crew_rescued = (
            set() if status["rescued_crew"] == "none" else set(status["rescued_crew"].split(","))
        )
        escorted = status["escorted_crew"]
        if status["control_board_read"] == "false":
            if room != "base":
                return to("base")
            return action("inspect", target="control_board")
        if status["fuel_depot_read"] == "false":
            if room != "base":
                return to("base")
            return action("inspect", target="fuel_depot")
        if status["rope_fixed"] == "false":
            if room != "heated_hut":
                return to("heated_hut")
            if status["rope_kit_read"] == "false":
                return action("inspect", target="rope_kit")
            if "rope_kit" not in inventory:
                return action("pickup", item="rope_kit")
            return action("interact", target="rope_kit", choice="fix")
        if room == "heated_hut" and "rope_kit" not in inventory:
            return action("pickup", item="rope_kit")
        if room == "heated_hut" and status["rope_fixed"] == "false":
            return action("interact", target="rope_kit", choice="fix")
        if room == "heated_hut" and int(status["body_heat"]) < 7 and int(status["fuel"]) > 1:
            return action("interact", target="heater", choice="rest")
        if escorted != "none":
            if int(status["body_heat"]) < 7 and int(status["fuel"]) > 1 and room != "heated_hut":
                return to("heated_hut")
            return to("base")
        if len(crew_rescued) == 2:
            return to("base")
        if len(crew_rescued) == 0:
            target, crew = "weather_post", "researcher_b"
        else:
            target, crew = "drill_camp", "researcher_a"
        if room == target:
            return action("interact", target=crew, choice="escort")
        if room == "base" and int(status["body_heat"]) < 7 and int(status["fuel"]) > 1:
            return to("heated_hut")
        return to(target)

    if scenario_id.startswith("PY-"):
        answer, lock = {
            "PY-E": ("EAST", "sun_dial"),
            "PY-M": ("SUN-MOON-STAR", "sequence_lock"),
            "PY-H": ("SUN-SCARAB-REED-EYE", "judgment_lock"),
        }[scenario_id]
        if scenario_id == "PY-H" and status["bridge_fixed"] == "false":
            return (
                to("bridge")
                if room != "bridge"
                else action("interact", target="bridge_mechanism", choice="fix")
            )
        clues = {
            "PY-E": (("east_mural_clue", "east_mural"),),
            "PY-M": (
                ("north_stone", "north_tomb"),
                ("west_stone", "west_tomb"),
                ("south_stone", "south_tomb"),
            ),
            "PY-H": (
                ("rune_sun", "rune_hall"),
                ("rune_scarab", "rune_hall"),
                ("rune_reed", "rune_hall"),
                ("rune_eye", "rune_hall"),
            ),
        }[scenario_id]
        seen = set() if status["clues_seen"] == "none" else set(status["clues_seen"].split(","))
        missing_clue = next(
            ((clue, clue_room) for clue, clue_room in clues if clue not in seen), None
        )
        if missing_clue is not None:
            clue, clue_room = missing_clue
            return to(clue_room) if room != clue_room else action("inspect", target=clue)
        if status["lock_unlocked"] == "false":
            puzzle_room = "sun_chamber" if scenario_id != "PY-H" else "rune_hall"
            return (
                to(puzzle_room)
                if room != puzzle_room
                else action("submit", target=lock, answer=answer)
            )
        if status["treasury_open"] == "false":
            if scenario_id == "PY-H":
                return action("interact", target="treasury_door", choice="open")
            return action("interact", target="treasury_door", choice="open")
        if required_item(scenario_id) not in inventory:
            return (
                to("treasury")
                if room != "treasury"
                else action("pickup", item=required_item(scenario_id))
            )
        return to("entrance")

    if scenario_id.startswith("SU-"):
        if scenario_id == "SU-E":
            if status["train_1_route"] != "north":
                return action("interact", target="switch", choice="north")
            if status["train_1_signal"] != "green":
                return action("interact", target="signal_panel", choice="green_train_1")
            if status["train_1_segment"] != "north_platform":
                return action("interact", target="train_1", choice="advance")
            return action("wait", turns=1)
        trains = (
            ("train_a", "train_b") if scenario_id == "SU-M" else ("train_a", "train_b", "train_c")
        )
        if status["maintenance_lock"] == "true":
            if status["train_b_segment"] != "platform_b":
                return action("interact", target="train_b", choice="advance")
            return action("interact", target="maintenance_console", choice="release_b")
        if scenario_id == "SU-M":
            for train, switch, route in (
                ("train_a", "switch_a", "platform_a"),
                ("train_b", "switch_b", "platform_b"),
            ):
                if status[f"{train}_route"] == "unset":
                    return action("interact", target=switch, choice=route)
        else:
            for train in trains:
                if status[f"{train}_route"] == "unset":
                    return action("interact", target="switch_panel", choice=f"route_{train[-1]}")
        for train in trains:
            if status[f"{train}_signal"] != "green":
                return action("interact", target="signal_panel", choice=f"green_{train[-1]}")
        order = trains if scenario_id == "SU-M" else ("train_a", "train_c", "train_b")
        for train in order:
            segment = status[f"{train}_segment"]
            final = f"platform_{train[-1]}"
            if segment != final:
                if (
                    train == "train_b"
                    and scenario_id == "SU-H"
                    and status["maintenance_lock"] == "true"
                ):
                    continue
                return action("interact", target=train, choice="advance")
        return action("wait", turns=1)

    if scenario_id.startswith("VO-"):
        if scenario_id == "VO-E":
            if status["valve_open"] == "false":
                return (
                    to("cooling_room")
                    if room != "cooling_room"
                    else action("interact", target="coolant_valve", choice="open")
                )
            if status["pump_confirmed"] == "false":
                return (
                    to("cooling_room")
                    if room != "cooling_room"
                    else action("interact", target="main_pump", choice="on")
                )
            if room != "exit_platform":
                return to("exit_platform")
            if int(status["heat"]) > 5:
                return action("wait", turns=1)
            return action("interact", target="cable_car", choice="depart")
        if scenario_id == "VO-M":
            if status["flow_a"] == "off" and status["flow_b"] == "off":
                return action("interact", target="pump_switch", choice="run_a_high")
            if status["flow_a"] != "low" or status["flow_b"] != "low":
                return action("interact", target="pump_switch", choice="balance_low")
            return (
                to("service_lift")
                if room != "service_lift"
                else action("interact", target="evac", choice="depart")
            )
        if status["pump_on"] == "false" and status["sample_collected"] == "false":
            return (
                to("cooling_hub")
                if room != "cooling_hub"
                else action("interact", target="pump_control", choice="on")
            )
        if status["sample_collected"] == "false":
            if room != "lava_probe":
                return to("lava_probe")
            if status["shield_deployed"] == "false":
                return action("interact", target="probe_shield", choice="deploy")
            return action("pickup", item="core_sample")
        if status["vent_open"] == "false":
            return (
                to("vent_room")
                if room != "vent_room"
                else action("interact", target="vent_flap", choice="open")
            )
        if status["pump_on"] == "true":
            return (
                to("cooling_hub")
                if room != "cooling_hub"
                else action("interact", target="pump_control", choice="off")
            )
        return (
            to("cable_station")
            if room != "cable_station"
            else action("interact", target="cable_car", choice="evacuate")
        )

    if scenario_id.startswith("JU-"):
        if scenario_id == "JU-E":
            seen = (
                set()
                if status["landmarks_seen"] == "none"
                else set(status["landmarks_seen"].split(","))
            )
            if "scout_note" not in seen:
                return to("camp") if room != "camp" else action("inspect", target="scout_note")
            if "red_marker" not in seen:
                return (
                    to("red_tree") if room != "red_tree" else action("inspect", target="red_marker")
                )
            if room != "ruin" and "ruin_notes" not in inventory:
                return to("ruin")
            if "ruin_notes" not in inventory:
                return action("pickup", item="ruin_notes")
            if room == "camp":
                return action("submit", target="field_report", answer="ruin_notes")
            return to("camp")
        if scenario_id == "JU-M":
            seen = (
                set()
                if status["landmarks_seen"] == "none"
                else set(status["landmarks_seen"].split(","))
            )
            if "camp_note" not in seen:
                return to("camp") if room != "camp" else action("inspect", target="camp_note")
            if "rune_marker" not in seen:
                return to("fork") if room != "fork" else action("inspect", target="rune_marker")
            if status["gate_direction"] != "EAST":
                return (
                    to("turntable")
                    if room != "turntable"
                    else action("interact", target="turntable", choice="set_east")
                )
            if "stone_tablet" not in inventory:
                if room == "hidden_ruin":
                    return action("pickup", item="stone_tablet")
                return to("east_path") if room != "east_path" else to("hidden_ruin")
            if status["shortcut_unlocked"] == "false":
                return action("interact", target="return_shortcut", choice="open_return")
            return to("camp")
        seen = (
            set()
            if status["landmarks_seen"] == "none"
            else set(status["landmarks_seen"].split(","))
        )
        for target, target_room in (
            ("weather_log", "camp"),
            ("path_sign", "fork"),
            ("oak_mark", "fork"),
            ("fern_mark", "river_bank"),
            ("vine_mark", "high_ridge"),
        ):
            if target not in seen:
                if (
                    target_room == "river_bank"
                    and room == "fork"
                    and status["weather_phase"] == "HIGH"
                ):
                    return action("wait", turns=1)
                return to(target_room) if room != target_room else action("inspect", target=target)
        if not status["altar_unlocked"] == "true":
            if room != "stone_circle":
                if (
                    room == "fork"
                    and "river_bank" in observation.available_exits
                    and status["weather_phase"] == "LOW"
                ):
                    return to("river_bank")
                return to("stone_circle")
            progress = int(status["marker_progress"])
            choice = ("oak", "fern", "vine")[progress]
            return action("interact", target="three_stones", choice=choice)
        if "relic_seed" not in inventory:
            return to("altar") if room != "altar" else action("pickup", item="relic_seed")
        if status["return_gate_open"] == "false":
            return action("interact", target="return_seal", choice="unfasten")
        return to("camp")

    if scenario_id.startswith("LU-"):
        if scenario_id == "LU-E":
            if "patch_kit" not in inventory:
                return to("storage") if room != "storage" else action("pickup", item="patch_kit")
            if status["panel_repaired"] == "false":
                if room == "storage":
                    return to("habitat")
                if room == "habitat":
                    return to("airlock")
                if room == "airlock":
                    if status["eva_prepared"] == "false":
                        return action("interact", target="suit_rack", choice="prepare")
                    if status["eva_active"] == "false":
                        return action("interact", target="suit_rack", choice="cycle_out")
                    return to("solar_pad")
                return action("use", item="patch_kit", target="broken_panel")
            if room == "solar_pad":
                return to("airlock")
            if room == "airlock":
                if status["eva_active"] == "true":
                    return action("interact", target="suit_rack", choice="cycle_in")
                return to("habitat")
            return action("look")
        if scenario_id == "LU-M":
            if "battery_module" not in inventory:
                return (
                    to("power_room")
                    if room != "power_room"
                    else action("pickup", item="battery_module")
                )
            if int(status["solar_charges"]) < 3:
                if room == "habitat":
                    return to("airlock") if "eva_prepared" in status else to("power_room")
                if room == "power_room":
                    return to("airlock")
                if room == "airlock":
                    if status["eva_prepared"] == "false":
                        return action("interact", target="airlock", choice="prepare")
                    if status["eva_active"] == "false":
                        return action("interact", target="airlock", choice="cycle_out")
                    return to("solar_array")
                if status["sun_phase"] != "DAY":
                    return action("wait", turns=1)
                return action("interact", target="solar_charger", choice="charge")
            if status["comms_repaired"] == "true":
                if room == "habitat":
                    return action("look")
                if room == "antenna":
                    return to("airlock")
                if room == "power_room":
                    return to("habitat")
                if room == "airlock":
                    return (
                        action("interact", target="airlock", choice="cycle_in")
                        if status["eva_active"] == "true"
                        else to("habitat")
                    )
                return to("airlock")
            if room == "airlock":
                if status["eva_active"] == "false":
                    return action("interact", target="airlock", choice="cycle_out")
                return to("antenna")
            if room == "antenna":
                return (
                    action("interact", target="comms_socket", choice="install")
                    if status["comms_repaired"] == "false"
                    else to("airlock")
                )
            if room == "solar_array":
                return to("airlock")
            return to("airlock")
        if "charged_cell" not in inventory and status["mast_repaired"] == "false":
            return to("supply") if room != "supply" else action("pickup", item="charged_cell")
        if status["mast_repaired"] == "false":
            if room == "habitat":
                return to("airlock")
            if room == "supply":
                return to("airlock")
            if room == "airlock":
                if status["eva_prepared"] == "false":
                    return action("interact", target="airlock", choice="prepare")
                if status["eva_active"] == "false":
                    return action("interact", target="airlock", choice="cycle_out")
                return to("mast")
            if room == "mast":
                return action("interact", target="signal_mast", choice="repair")
            return to("airlock")
        rescued = status["crew_rescued"] == "true"
        if rescued and room == "habitat":
            return action("look")
        if rescued:
            if room == "supply":
                return to("habitat")
            if room == "airlock":
                return (
                    action("interact", target="airlock", choice="cycle_in")
                    if status["eva_active"] == "true"
                    else to("habitat")
                )
            return to("airlock")
        if not rescued and room == "habitat":
            return to("supply")
        if room == "supply":
            if int(status["eva_oxygen"]) < 12 and int(status["reserve_oxygen"]) > 0:
                return action("interact", target="o2_station", choice="refill")
            return to("airlock")
        if room == "airlock":
            if status["eva_prepared"] == "false":
                return action("interact", target="airlock", choice="prepare")
            if status["mast_repaired"] == "true" and not rescued:
                if status["eva_active"] == "true":
                    if int(status["eva_oxygen"]) < 12:
                        return action("interact", target="airlock", choice="cycle_in")
                    return to("relay_point")
                if int(status["eva_oxygen"]) < 12:
                    return to("habitat")
                return action("interact", target="airlock", choice="cycle_out")
            if status["eva_active"] == "false":
                return action("interact", target="airlock", choice="cycle_out")
            return to("mast" if status["mast_repaired"] == "false" else "relay_point")
        if room == "relay_point" and not rescued:
            return action("interact", target="astronaut_b", choice="escort")
        if room == "relay_point" and rescued:
            return to("airlock")
        return to("airlock")

    if scenario_id.startswith("CA-"):
        recorded = (
            set() if status["evidence_ids"] == "none" else set(status["evidence_ids"].split(","))
        )
        if scenario_id == "CA-E":
            dialogue = (
                ("gatekeeper_key_location", "gatehouse", "gatekeeper", "where_key"),
                ("cook_box_location", "kitchen", "cook", "where_stored"),
            )
            missing_dialogue = next((entry for entry in dialogue if entry[0] not in recorded), None)
            if missing_dialogue is not None:
                _, room_target, target, choice = missing_dialogue
                return (
                    to(room_target)
                    if room != room_target
                    else action("interact", target=target, choice=choice)
                )
            if status["key_revealed"] == "false":
                return to("pantry") if room != "pantry" else action("inspect", target="key_box")
            if "archive_key" not in inventory:
                return to("pantry") if room != "pantry" else action("pickup", item="archive_key")
            if status["library_unlocked"] == "false":
                return (
                    to("great_hall")
                    if room != "great_hall"
                    else action("use", item="archive_key", target="library_door")
                )
            return (
                to("library")
                if room != "library"
                else action("interact", target="archive_desk", choice="register")
            )

        if scenario_id == "CA-M":
            evidence_plan: tuple[tuple[str, str, str, str, str], ...] = (
                ("access_log", "records_room", "inspect", "access_log", ""),
                ("clock_report", "records_room", "inspect", "clock_report", ""),
                ("caretaker_statement", "courtyard", "interact", "caretaker", "where_were_you"),
                ("guard_timeline", "watchtower", "interact", "guard", "night_patrol"),
            )
            missing = next((entry for entry in evidence_plan if entry[0] not in recorded), None)
            if missing is not None:
                _, room_target, tool, target, choice = missing
                if room != room_target:
                    return to(room_target)
                return (
                    action("inspect", target=target)
                    if tool == "inspect"
                    else action("interact", target=target, choice=choice)
                )
            if status["verdict_accepted"] == "false":
                return (
                    to("hall")
                    if room != "hall"
                    else action("submit", target="case_board", answer="CARETAKER")
                )
            if status["secret_study_open"] == "false":
                return (
                    to("records_room")
                    if room != "records_room"
                    else action("interact", target="secret_study_door", choice="open")
                )
            if "sealed_scroll" not in inventory:
                return (
                    to("secret_study")
                    if room != "secret_study"
                    else action("pickup", item="sealed_scroll")
                )
            return (
                to("hall")
                if room != "hall"
                else action("interact", target="case_board", choice="close_case")
            )

        evidence_plan = (
            ("key_ledger", "key_archive", "inspect", "key_ledger", ""),
            ("seal_wax", "seal_chamber", "inspect", "seal_wax", ""),
            ("door_record", "seal_chamber", "inspect", "door_record", ""),
            ("guard_roster", "watch_post", "inspect", "guard_roster", ""),
            ("medical_chart", "infirmary", "inspect", "medical_chart", ""),
            ("marius_statement", "servant_quarters", "interact", "marius", "key_access"),
            ("gareth_statement", "watch_post", "interact", "gareth", "where_were_you"),
            ("elise_statement", "infirmary", "interact", "elise", "where_were_you"),
        )
        missing = next((entry for entry in evidence_plan if entry[0] not in recorded), None)
        if missing is not None:
            _, room_target, tool, target, choice = missing
            if room != room_target:
                return to(room_target)
            return (
                action("inspect", target=target)
                if tool == "inspect"
                else action("interact", target=target, choice=choice)
            )
        return (
            to("grand_hall")
            if room != "grand_hall"
            else action(
                "submit",
                target="verdict_desk",
                answer="MARIUS|KEY_LEDGER+SEAL_WAX",
            )
        )

    raise ValueError(f"No public oracle is registered for {scenario_id}.")


def required_item(scenario_id: str) -> str:
    return {"PY-E": "map_scroll", "PY-M": "stone_tablet", "PY-H": "seal_relic"}[scenario_id]


def state_value(observation: ScenarioObservation, key: str) -> str | None:
    return next((fact.value for fact in observation.public_status if fact.id == key), None)


__all__ = ["public_oracle_action"]
