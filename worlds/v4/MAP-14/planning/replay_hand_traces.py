"""Replay MAP-14's two manually authored routes without exposing judge state."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE_ENDPOINTS = {"P_A": {"P", "A"}, "A_O": {"A", "O"}, "O_J": {"O", "J"}}
NEIGHBORS = {"P": ["A"], "A": ["P", "O"], "O": ["A", "J"], "J": ["O"]}
PUBLIC_CARDS = {
    "A1": {"speaker": "甲", "text": "当前锁型是日轮锁A吗？"},
    "A2": {"speaker": "甲", "text": "当前锁型是月牙锁B吗？"},
    "B1": {"speaker": "乙", "text": "当前锁型不是星井锁C吗？"},
    "B2": {"speaker": "乙", "text": "当前锁型不是月牙锁B吗？"},
    "C1": {"speaker": "丙", "text": "当前锁型是星井锁C吗？"},
    "C2": {"speaker": "丙", "text": "当前锁型不是日轮锁A吗？"},
}
ARCHIVE_ID = "ARCHIVE_NOT_C"
MAX_QUESTIONS = 4
WRONG_LIMIT = 2
CONFIG_ID = {"A": "A_sun_wheel", "B": "B_crescent", "C": "C_star_well"}
PRIEST_NAME = {"A_priest": "甲", "B_priest": "乙", "C_priest": "丙"}


def snapshot(tick: int, location: str, archive: dict | None, answers: list[dict],
             comparison: dict | None, wrong: int, opened: bool, terminal: bool,
             reason: str | None, response: str) -> dict:
    return {
        "current_tick": tick,
        "location": location,
        "visible_neighbors": NEIGHBORS[location],
        "public_statement_cards": PUBLIC_CARDS if location == "P" else {},
        "archive_record_if_read": archive,
        "question_answers": list(answers),
        "questions_used": len(answers),
        "questions_remaining": MAX_QUESTIONS - len(answers),
        "comparison_record": comparison,
        "wrong_submissions": wrong,
        "wrong_submissions_remaining": WRONG_LIMIT - wrong,
        "gate_open": opened,
        "terminal": terminal,
        "terminal_reason": reason,
        "last_response": response,
    }


def replay(trace_id: str, actions: list[dict], audit: dict) -> list[dict]:
    actual = audit["actual_hidden_state_for_seed_0"]
    actual_config = actual["configuration"]
    actual_config_id = CONFIG_ID[actual_config]
    truthful_priest = actual["truthful_priest"]
    claim_table = audit["claims"]
    tick, location = 0, "P"
    archive: dict | None = None
    answers: list[dict] = []
    asked: set[str] = set()
    comparison: dict | None = None
    wrong, opened, terminal = 0, False, False
    reason: str | None = None
    rows: list[dict] = []

    for action in actions:
        if terminal:
            raise ValueError(f"{trace_id}: action after terminal")
        before = tick
        tool = action["tool"]
        response = ""
        if tool == "move":
            edge = action["edge_id"]
            if edge not in EDGE_ENDPOINTS or EDGE_ENDPOINTS[edge] != {action["from_node"], action["to_node"]}:
                raise ValueError(f"{trace_id}: invalid edge {edge}")
            if action["from_node"] != location or action["to_node"] not in NEIGHBORS[location]:
                raise ValueError(f"{trace_id}: move does not start at current node")
            tick += 1
            location = action["to_node"]
            response = f"arrived:{location}"
        elif tool == "read_archive":
            if location != "A" or archive is not None:
                raise ValueError(f"{trace_id}: archive read outside A or repeated")
            tick += 1
            archive = {"evidence_id": ARCHIVE_ID, "text": "星井锁C从未安装在当前审判门上。"}
            response = ARCHIVE_ID
        elif tool == "ask":
            claim_id = action["claim_id"]
            if location != "P" or claim_id not in claim_table or claim_id in asked:
                raise ValueError(f"{trace_id}: invalid or repeated priest question")
            if len(answers) >= MAX_QUESTIONS:
                raise ValueError(f"{trace_id}: question budget exceeded")
            claim = claim_table[claim_id]
            claim_true = actual_config in claim["true_for"]
            response_yes = claim_true if claim["priest"] == truthful_priest else not claim_true
            tick += 1
            asked.add(claim_id)
            answer_row = {
                "evidence_id": f"ANSWER_{claim_id}",
                "claim_id": claim_id,
                "speaker": claim["priest"],
                "text": claim["text"],
                "answer": "yes" if response_yes else "no",
            }
            answers.append(answer_row)
            response = answer_row["answer"]
        elif tool == "compare_evidence":
            if location != "O":
                raise ValueError(f"{trace_id}: comparison board used outside O")
            support = set(action["support_evidence_ids"])
            available = {row["evidence_id"] for row in answers}
            if archive is not None:
                available.add(ARCHIVE_ID)
            if not support or not support <= available:
                raise ValueError(f"{trace_id}: comparison uses unobserved evidence")
            tick += 1
            comparison = {
                "configuration_candidate": action["configuration_candidate"],
                "truthful_priest_candidate": action["truthful_priest_candidate"],
                "support_evidence_ids": list(action["support_evidence_ids"]),
            }
            response = "hypothesis_sealed_without_judgment"
        elif tool == "submit_configuration":
            if location != "J" or comparison is None:
                raise ValueError(f"{trace_id}: configuration submitted without O record at J")
            tick += 1
            if action["configuration"] == actual_config_id:
                opened, terminal, reason = True, True, "GATE_OPENED"
                response = "gate_opened"
            else:
                wrong += 1
                response = "gate_closed_no_configuration_hint"
                if wrong >= WRONG_LIMIT:
                    terminal, reason = True, "WRONG_SUBMISSION_LIMIT"
        else:
            raise ValueError(f"{trace_id}: unsupported action {tool}")

        public_state = snapshot(tick, location, archive, answers, comparison, wrong,
                                opened, terminal, reason, response)
        if "truthful_priest" in public_state or "actual_configuration" in public_state:
            raise AssertionError("Private role/configuration leaked into observation")
        rows.append({"trace_id": trace_id, "step": tick, "tick_before": before,
                     "action": action, "expected_observation": public_state})

    if not terminal or not opened or reason != "GATE_OPENED":
        raise ValueError(f"{trace_id}: hand-authored route did not open the gate")
    if comparison is None or comparison["configuration_candidate"] != actual_config_id:
        raise ValueError(f"{trace_id}: comparison record does not support successful lock selection")
    if comparison["truthful_priest_candidate"] not in PRIEST_NAME or PRIEST_NAME[comparison["truthful_priest_candidate"]] != truthful_priest:
        raise ValueError(f"{trace_id}: truth-teller deduction is inconsistent with successful evidence")
    if len(answers) > MAX_QUESTIONS:
        raise AssertionError("Question cap exceeded")
    return rows


def main() -> None:
    plans = json.loads((ROOT / "planning" / "hand_traces.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "planning" / "truth_table_audit.json").read_text(encoding="utf-8"))
    traces = [row for name, actions in plans["plans"].items() for row in replay(name, actions, audit)]
    output = ROOT / "oracle_trace.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                                for row in traces), encoding="utf-8")
    print(json.dumps({"result": "TWO_HAND_ROUTES_OPEN_GATE", "rows": len(traces),
                      "routes": {name: len(actions) for name, actions in plans["plans"].items()},
                      "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
