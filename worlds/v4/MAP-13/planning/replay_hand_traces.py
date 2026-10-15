"""Serialize and statically replay MAP-13's two manually authored tool traces."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE_ENDPOINTS = {
    "C_N": {"C", "N"}, "C_E": {"C", "E"},
    "C_S": {"C", "S"}, "C_W": {"C", "W"},
}
NEIGHBORS = {"C": ["N", "E", "S", "W"],
             "N": ["C"], "E": ["C"], "S": ["C"], "W": ["C"]}
CLUE_AT = {"C": "ORIENTATION_ORDER", "N": "N_SUN_NOT_END",
           "E": "E_EYE_RIGHT_OF_REED", "S": "S_ARMOR_ADJACENT_TO_SUN",
           "W": "W_REED_NOT_FIRST"}
CLUE_TEXT = {
    "ORIENTATION_ORDER": "从北室起，按N→E→S→W顺时针读为槽位1至4；右侧表示编号更大，相邻表示编号差1。",
    "N_SUN_NOT_END": "日神不得居于两端。",
    "E_EYE_RIGHT_OF_REED": "眼神位于芦神右侧。",
    "S_ARMOR_ADJACENT_TO_SUN": "甲神须与日神相邻。",
    "W_REED_NOT_FIRST": "芦神不得居于首槽。",
}


def snapshot(tick: int, location: str, observed: list[str], recorded: list[str],
             layout: dict[str, str] | None, wrong: int, opened: bool,
             terminal: bool, reason: str | None, response: str) -> dict:
    return {
        "current_tick": tick,
        "location": location,
        "visible_neighbors": NEIGHBORS[location],
        "observed_clues_and_text": [
            {"clue_id": clue, "text": CLUE_TEXT[clue]} for clue in observed
        ],
        "recorded_clue_ids": list(recorded),
        "trial_layout": dict(layout) if layout is not None else None,
        "incorrect_attempts": wrong,
        "remaining_incorrect_attempts": max(0, 2 - wrong),
        "gate_open": opened,
        "terminal": terminal,
        "terminal_reason": reason,
        "last_response": response,
    }


def replay(trace_id: str, actions: list[dict], target: dict[str, str]) -> list[dict]:
    tick, location, wrong, opened, terminal = 0, "C", 0, False, False
    reason = None
    observed: list[str] = []
    recorded: list[str] = []
    layout: dict[str, str] | None = None
    result: list[dict] = []

    for action in actions:
        if terminal:
            raise ValueError(f"{trace_id}: action after terminal state")
        before = tick
        tool = action["tool"]
        response = ""
        if tool == "move":
            edge = action["edge_id"]
            if edge not in EDGE_ENDPOINTS or EDGE_ENDPOINTS[edge] != {action["from_node"], action["to_node"]}:
                raise ValueError(f"{trace_id}: invalid edge {edge}")
            if action["from_node"] != location or action["to_node"] not in NEIGHBORS[location]:
                raise ValueError(f"{trace_id}: move does not start at current location")
            tick += 1
            location = action["to_node"]
            response = f"arrived:{location}"
        elif tool == "read_inscription":
            if action["room"] != location:
                raise ValueError(f"{trace_id}: read requested away from named room")
            clue = CLUE_AT[location]
            tick += 1
            if clue not in observed:
                observed.append(clue)
            response = f"inscription:{CLUE_TEXT[clue]}"
        elif tool == "record_constraint":
            clue = action["clue_id"]
            if location != "C" or clue not in observed or clue in recorded:
                raise ValueError(f"{trace_id}: invalid record action for {clue}")
            tick += 1
            recorded.append(clue)
            response = f"recorded:{clue}"
        elif tool == "set_trial_layout":
            if location != "C":
                raise ValueError(f"{trace_id}: trial board used away from C")
            candidate = action["layout_by_room"]
            if set(candidate) != {"N", "E", "S", "W"} or set(candidate.values()) != {"日", "眼", "芦", "甲"}:
                raise ValueError(f"{trace_id}: trial is not a four-symbol permutation")
            tick += 1
            layout = dict(candidate)
            response = "trial_layout_set"
        elif tool == "verify_layout":
            if location != "C" or layout is None:
                raise ValueError(f"{trace_id}: verify requires a complete layout at C")
            tick += 1
            if layout == target:
                opened, terminal, reason = True, True, "GATE_OPENED"
                response = "gate_opened"
            else:
                wrong += 1
                response = "gate_closed_no_symbol_feedback"
                if wrong >= 3:
                    terminal, reason = True, "INCORRECT_ATTEMPT_LIMIT"
        else:
            raise ValueError(f"{trace_id}: unsupported hand action {tool}")

        result.append({
            "trace_id": trace_id,
            "step": tick,
            "tick_before": before,
            "action": action,
            "expected_observation": snapshot(tick, location, observed, recorded,
                                             layout, wrong, opened, terminal, reason, response),
        })

    if not terminal or not opened or reason != "GATE_OPENED":
        raise ValueError(f"{trace_id}: hand-authored success trace did not open the gate")
    if tick != 20 or len(recorded) != 5 or set(observed) != set(CLUE_TEXT):
        raise ValueError(f"{trace_id}: expected 20 ticks and complete five-clue evidence")
    return result


def main() -> None:
    hand = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "planning" / "constraint_audit.json").read_text(encoding="utf-8"))
    target = audit["solutions_clockwise"][0]
    if target != hand["correct_layout"]:
        raise ValueError("Hand route target differs from the 24-permutation audit")
    traces = [row for name, actions in hand["plans"].items() for row in replay(name, actions, target)]
    output = ROOT / "oracle_trace.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                                for row in traces), encoding="utf-8")
    print(json.dumps({"result": "TWO_HAND_TRACES_OPEN_GATE", "rows": len(traces),
                      "ticks_per_plan": 20, "evidence_per_plan": 5,
                      "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
