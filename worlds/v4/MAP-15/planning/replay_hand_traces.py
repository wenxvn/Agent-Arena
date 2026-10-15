"""Replay MAP-15's two manually authored success routes into an observation ledger."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEXT_AREA = {"A": "B", "B": "C", "C": "T", "T": "EXIT"}
AREA_ROLE = {"A": "training", "B": "training", "C": "training", "T": "test"}
TEST_WRONG_LIMIT = 1


def calculate_target(area: dict, tick: int, complement: dict[str, str]) -> str:
    wall = area["wall_color"]
    return wall if tick % 2 == 0 else complement[wall]


def public_state(area_name: str, tick: int, inspected: bool, layout: dict,
                resources: int, test_errors: int, training_log: list[dict],
                rule_record: dict | None, gate_open: bool, terminal: bool,
                reason: str | None, response: str) -> dict:
    layout_now = layout.get(area_name)
    signs_visible = inspected and layout_now is not None
    return {
        "area": area_name,
        "current_tick": tick,
        "current_tick_parity": "even" if tick % 2 == 0 else "odd",
        "inspected_current_area": inspected,
        "current_wall_symbol_color_if_inspected": layout_now["wall_color"] if signs_visible else None,
        "current_door_colors_in_ephemeral_slot_order_if_inspected": layout_now["door_colors"] if signs_visible else None,
        "wrong_attempt_resources": resources,
        "test_wrong_attempts": test_errors,
        "test_wrong_attempts_remaining": max(0, TEST_WRONG_LIMIT - test_errors),
        "training_sample_log": list(training_log),
        "recorded_rule_hypothesis": rule_record,
        "gate_open": gate_open,
        "terminal": terminal,
        "terminal_reason": reason,
        "last_response": response,
    }


def replay(trace_id: str, actions: list[dict], design: dict, audit: dict) -> list[dict]:
    layout = design["regions"]
    complement = design["color_complements"]
    area, tick, resources, test_errors = "A", 0, 4, 0
    inspected = False
    training_log: list[dict] = []
    rule_record: dict | None = None
    gate_open = terminal = False
    reason: str | None = None
    rows: list[dict] = []
    per_area_attempts = {name: 0 for name in layout}

    for action in actions:
        if terminal:
            raise ValueError(f"{trace_id}: action after terminal")
        before_tick = tick
        tool = action["tool"]
        response = ""
        if tool == "inspect_symbols":
            if action["area"] != area or area not in layout:
                raise ValueError(f"{trace_id}: symbols inspected outside current area")
            inspected = True
            response = "current_wall_and_ephemeral_doors_visible"
        elif tool == "record_rule":
            if rule_record is not None:
                raise ValueError(f"{trace_id}: rule hypothesis recorded more than once")
            allowed_rules = {"R_EVEN_SAME_ODD_COMPLEMENT", "R_ODD_SAME_EVEN_COMPLEMENT",
                             "R_ALWAYS_SAME", "R_ALWAYS_COMPLEMENT"}
            if action["rule_id"] not in allowed_rules:
                raise ValueError(f"{trace_id}: unsupported rule id")
            known_samples = {sample["sample_id"] for sample in training_log}
            support = set(action["supporting_sample_ids"])
            if not support or not support <= known_samples:
                raise ValueError(f"{trace_id}: rule hypothesis cites unobserved samples")
            rule_record = {"rule_id": action["rule_id"],
                           "supporting_sample_ids": list(action["supporting_sample_ids"])}
            response = "rule_recorded_without_correctness_feedback"
        elif tool == "choose_door":
            if not inspected or area not in layout:
                raise ValueError(f"{trace_id}: choose_door requires inspected current area")
            door_slot = action["slot_index"]
            doors = layout[area]["door_colors"]
            if not 1 <= door_slot <= len(doors):
                raise ValueError(f"{trace_id}: slot out of range")
            per_area_attempts[area] += 1
            chosen_color = doors[door_slot - 1]
            goal = calculate_target(layout[area], tick, complement)
            passed = chosen_color == goal
            tick += 1
            if passed:
                response = "gate_opened" if area == "T" else f"passed_forward_to_{NEXT_AREA[area]}"
                if AREA_ROLE[area] == "training":
                    training_log.append({
                        "sample_id": f"SAMPLE_{area}_T{before_tick}_ATTEMPT{per_area_attempts[area]}",
                        "area": area,
                        "tick_before_choice": before_tick,
                        "parity_before_choice": "even" if before_tick % 2 == 0 else "odd",
                        "wall_color": layout[area]["wall_color"],
                        "chosen_door_color": chosen_color,
                        "result": "passed",
                    })
                    area = NEXT_AREA[area]
                    inspected = False
                else:
                    gate_open = terminal = True
                    reason = "GATE_OPENED"
                    area = "EXIT"
                    inspected = False
            else:
                response = "door_rejected_no_target_color_feedback"
                resources -= 1
                if AREA_ROLE[area] == "training":
                    training_log.append({
                        "sample_id": f"SAMPLE_{area}_T{before_tick}_ATTEMPT{per_area_attempts[area]}",
                        "area": area,
                        "tick_before_choice": before_tick,
                        "parity_before_choice": "even" if before_tick % 2 == 0 else "odd",
                        "wall_color": layout[area]["wall_color"],
                        "chosen_door_color": chosen_color,
                        "result": "rejected",
                    })
                elif area == "T":
                    test_errors += 1
                if resources == 0:
                    terminal, reason = True, "RESOURCE_DEPLETED"
                elif area == "T" and test_errors >= 2:
                    terminal, reason = True, "TEST_WRONG_LIMIT"
        else:
            raise ValueError(f"{trace_id}: unsupported action {tool}")

        observed = public_state(area, tick, inspected, layout, resources, test_errors,
                                training_log, rule_record, gate_open, terminal, reason, response)
        if "target_color" in observed or "actual_rule" in observed:
            raise AssertionError("Private rule target leaked into observation")
        rows.append({"trace_id": trace_id, "step": len(rows) + 1,
                     "tick_before": before_tick, "action": action,
                     "expected_observation": observed})

    if not terminal or not gate_open or reason != "GATE_OPENED":
        raise ValueError(f"{trace_id}: hand route did not pass the test area")
    return rows


def main() -> None:
    design = json.loads((ROOT / "planning" / "room_signs.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "planning" / "rule_audit.json").read_text(encoding="utf-8"))
    hand = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    if audit["rule_id"] != design["target_rule_id"]:
        raise ValueError("Rule audit and local sign table disagree")
    traces = [row for name, actions in hand["plans"].items() for row in replay(name, actions, design, audit)]
    output = ROOT / "oracle_trace.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                                for row in traces), encoding="utf-8")
    summaries = {}
    for name in hand["plans"]:
        rows = [row for row in traces if row["trace_id"] == name]
        final = rows[-1]["expected_observation"]
        summaries[name] = {
            "actions": len(rows), "ticks": final["current_tick"],
            "resources": final["wrong_attempt_resources"],
            "test_errors": final["test_wrong_attempts"],
            "rule_recorded": final["recorded_rule_hypothesis"] is not None,
            "result": final["terminal_reason"],
        }
    print(json.dumps({"result": "HAND_ROUTES_REPLAYED", "rows": len(traces),
                      "plans": summaries, "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
