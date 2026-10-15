"""Exhaustively audit MAP-14's fixed priest claims and bounded query policies."""
from __future__ import annotations

import json
from functools import lru_cache
from itertools import product
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ("A", "B", "C")
PRIESTS = ("甲", "乙", "丙")
CLAIMS = {
    "A1": {"priest": "甲", "true_for": {"A"}, "text": "当前锁型是日轮锁A吗？"},
    "A2": {"priest": "甲", "true_for": {"B"}, "text": "当前锁型是月牙锁B吗？"},
    "B1": {"priest": "乙", "true_for": {"A", "B"}, "text": "当前锁型不是星井锁C吗？"},
    "B2": {"priest": "乙", "true_for": {"A", "C"}, "text": "当前锁型不是月牙锁B吗？"},
    "C1": {"priest": "丙", "true_for": {"C"}, "text": "当前锁型是星井锁C吗？"},
    "C2": {"priest": "丙", "true_for": {"B", "C"}, "text": "当前锁型不是日轮锁A吗？"},
}
QUERY_IDS = tuple(CLAIMS)
TRUE_STATE = ("B", "乙")
SYSTEMATIC_QUERY_ORDER = ("A1", "A2", "B1", "B2")
ARCHIVE_QUERY_ORDER = ("A1", "B1", "B2")
MAX_QUESTIONS = 4


def answer(claim_id: str, state: tuple[str, str]) -> bool:
    config, truthful_priest = state
    claim_true = config in CLAIMS[claim_id]["true_for"]
    return claim_true if CLAIMS[claim_id]["priest"] == truthful_priest else not claim_true


def response_code(query_ids: tuple[str, ...], state: tuple[str, str]) -> tuple[bool, ...]:
    return tuple(answer(claim_id, state) for claim_id in query_ids)


def unique_codes(states: tuple[tuple[str, str], ...], query_ids: tuple[str, ...]) -> bool:
    codes = [response_code(query_ids, state) for state in states]
    return len(codes) == len(set(codes))


def build_adaptive_tree() -> dict:
    states = tuple(product(CONFIGS, PRIESTS))

    @lru_cache(maxsize=None)
    def solve(candidates: tuple[tuple[str, str], ...], asked_mask: int, depth_left: int):
        if len(candidates) == 1:
            config, priest = candidates[0]
            return {"leaf": {"configuration": config, "truthful_priest": priest}}
        if depth_left == 0:
            return None
        for i, claim_id in enumerate(QUERY_IDS):
            if asked_mask & (1 << i):
                continue
            no = tuple(state for state in candidates if not answer(claim_id, state))
            yes = tuple(state for state in candidates if answer(claim_id, state))
            if not no or not yes:
                continue
            no_branch = solve(no, asked_mask | (1 << i), depth_left - 1)
            if no_branch is None:
                continue
            yes_branch = solve(yes, asked_mask | (1 << i), depth_left - 1)
            if yes_branch is not None:
                return {"ask": claim_id, "if_no": no_branch, "if_yes": yes_branch}
        return None

    result = solve(states, 0, MAX_QUESTIONS)
    if result is None:
        raise AssertionError("No adaptive policy distinguishes all nine hidden states in four queries")
    return result


def walk_tree(tree: dict, state: tuple[str, str]) -> tuple[list[dict], tuple[str, str]]:
    path: list[dict] = []
    current = tree
    while "ask" in current:
        claim_id = current["ask"]
        reply = answer(claim_id, state)
        path.append({"claim_id": claim_id, "answer": "yes" if reply else "no"})
        current = current["if_yes"] if reply else current["if_no"]
    leaf = current["leaf"]
    return path, (leaf["configuration"], leaf["truthful_priest"])


def collect_leaves(tree: dict) -> list[dict]:
    if "leaf" in tree:
        return [tree["leaf"]]
    return collect_leaves(tree["if_no"]) + collect_leaves(tree["if_yes"])


def main() -> None:
    states = tuple(product(CONFIGS, PRIESTS))
    systematic_codes = {state: response_code(SYSTEMATIC_QUERY_ORDER, state) for state in states}
    assert len(set(systematic_codes.values())) == 9

    archived_states = tuple(state for state in states if state[0] in {"A", "B"})
    archive_codes = {state: response_code(ARCHIVE_QUERY_ORDER, state) for state in archived_states}
    assert len(set(archive_codes.values())) == 6

    adaptive = build_adaptive_tree()
    leaves = collect_leaves(adaptive)
    assert len(leaves) == 9
    assert {(leaf["configuration"], leaf["truthful_priest"]) for leaf in leaves} == set(states)
    adaptive_path, adaptive_guess = walk_tree(adaptive, TRUE_STATE)
    assert [row["claim_id"] for row in adaptive_path] == ["A1", "A2", "B1"]
    assert [row["answer"] for row in adaptive_path] == ["yes", "no", "yes"]
    assert adaptive_guess == TRUE_STATE

    archive_actual = ["yes" if answer(claim_id, TRUE_STATE) else "no" for claim_id in ARCHIVE_QUERY_ORDER]
    archive_guess = next(state for state, code in archive_codes.items()
                         if ["yes" if bit else "no" for bit in code] == archive_actual)
    assert archive_actual == ["yes", "yes", "no"] and archive_guess == TRUE_STATE

    f03_queries = ("A1", "A2", "B2", "C1")
    f03_code = response_code(f03_queries, TRUE_STATE)
    f03_compatible_states = [state for state in states
                             if response_code(f03_queries, state) == f03_code]
    assert set(f03_compatible_states) == {TRUE_STATE, ("A", "甲")}

    table = []
    for config, truthful_priest in states:
        state = (config, truthful_priest)
        table.append({
            "configuration": config,
            "truthful_priest": truthful_priest,
            "claim_truth_values": {claim_id: config in claim["true_for"]
                                   for claim_id, claim in CLAIMS.items()},
            "systematic_A1_A2_B1_B2_answers": ["yes" if bit else "no"
                                               for bit in systematic_codes[state]],
        })

    output_data = {
        "map_id": "MAP-14",
        "runtime_verified": False,
        "configurations": list(CONFIGS),
        "truth_teller_candidates": list(PRIESTS),
        "claims": {key: {**value, "true_for": sorted(value["true_for"])}
                   for key, value in CLAIMS.items()},
        "candidate_count": 9,
        "full_four_query_codes_are_unique": True,
        "systematic_query_order": list(SYSTEMATIC_QUERY_ORDER),
        "archive_excludes_configuration": "C",
        "archive_candidate_count": 6,
        "archive_query_order": list(ARCHIVE_QUERY_ORDER),
        "archive_actual_answers": archive_actual,
        "archive_route_unique_state": {"configuration": archive_guess[0], "truthful_priest": archive_guess[1]},
        "adaptive_query_limit": MAX_QUESTIONS,
        "adaptive_tree": adaptive,
        "adaptive_actual_path": adaptive_path,
        "adaptive_actual_leaf": {"configuration": adaptive_guess[0], "truthful_priest": adaptive_guess[1]},
        "F03_ambiguous_question_subset": {
            "query_order": list(f03_queries),
            "actual_answers": ["yes" if bit else "no" for bit in f03_code],
            "compatible_states": [{"configuration": config, "truthful_priest": priest}
                                  for config, priest in f03_compatible_states],
        },
        "actual_hidden_state_for_seed_0": {"configuration": TRUE_STATE[0], "truthful_priest": TRUE_STATE[1]},
        "full_truth_table": table,
    }
    output = ROOT / "planning" / "truth_table_audit.json"
    output.write_text(json.dumps(output_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "NINE_STATES_UNIQUE", "full_states": 9,
                      "archive_states": 6, "archive_actual": archive_actual,
                      "adaptive_actual": adaptive_path, "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
