"""Exhaustively audit MAP-13's 24 symbol permutations and clue necessity."""
from __future__ import annotations

import json
from itertools import permutations
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ("日", "眼", "芦", "甲")
ROOM_ORDERS = {
    "clockwise": ("N", "E", "S", "W"),
    "counterclockwise_mirror": ("N", "W", "S", "E"),
}


def position(layout: tuple[str, ...], symbol: str) -> int:
    return layout.index(symbol) + 1


CLUES = {
    "N_SUN_NOT_END": lambda p: position(p, "日") in (2, 3),
    "E_EYE_RIGHT_OF_REED": lambda p: position(p, "眼") > position(p, "芦"),
    "S_ARMOR_ADJACENT_TO_SUN": lambda p: abs(position(p, "甲") - position(p, "日")) == 1,
    "W_REED_NOT_FIRST": lambda p: position(p, "芦") != 1,
}


def satisfying_layouts(order: tuple[str, ...], enabled: set[str] | None = None) -> list[dict[str, str]]:
    active = set(CLUES) if enabled is None else enabled
    found = []
    for symbols_by_slot in permutations(SYMBOLS):
        if all(CLUES[clue](symbols_by_slot) for clue in active):
            found.append(dict(zip(order, symbols_by_slot, strict=True)))
    return found


def passes_room_clues(layout: dict[str, str], enabled: set[str] | None = None) -> bool:
    symbols_by_slot = tuple(layout[room] for room in ROOM_ORDERS["clockwise"])
    active = set(CLUES) if enabled is None else enabled
    return all(CLUES[name](symbols_by_slot) for name in active)


def main() -> None:
    all_permutations = list(permutations(SYMBOLS))
    assert len(all_permutations) == 24

    cw_order = ROOM_ORDERS["clockwise"]
    remaining = all_permutations
    candidate_counts = [{"after": "unfiltered", "count": len(remaining)}]
    for clue_name, predicate in CLUES.items():
        remaining = [candidate for candidate in remaining if predicate(candidate)]
        candidate_counts.append({"after": clue_name, "count": len(remaining)})

    unique_clockwise = satisfying_layouts(cw_order)
    assert len(unique_clockwise) == 1
    deletion_counts = {
        clue_name: len(satisfying_layouts(cw_order, set(CLUES) - {clue_name}))
        for clue_name in CLUES
    }
    assert all(count > 1 for count in deletion_counts.values()), deletion_counts

    mirrored_order = ROOM_ORDERS["counterclockwise_mirror"]
    unique_mirror = satisfying_layouts(mirrored_order)
    assert len(unique_mirror) == 1
    layouts_without_orientation = {
        tuple(sorted(layout.items()))
        for layout in unique_clockwise + unique_mirror
    }
    assert len(layouts_without_orientation) == 2

    failure_candidates = {
        "F01_orientation_marker_skipped": unique_mirror[0],
        "F02_east_clue_omitted": [
            {"N": "眼", "E": "日", "S": "甲", "W": "芦"},
            {"N": "眼", "E": "芦", "S": "日", "W": "甲"},
            {"N": "眼", "E": "甲", "S": "日", "W": "芦"},
        ],
        "F03_west_clue_omitted": [
            {"N": "芦", "E": "日", "S": "甲", "W": "眼"},
            {"N": "芦", "E": "眼", "S": "日", "W": "甲"},
            {"N": "芦", "E": "甲", "S": "日", "W": "眼"},
        ],
    }
    assert all(passes_room_clues(layout, set(CLUES) - {"E_EYE_RIGHT_OF_REED"})
               and not passes_room_clues(layout, {"E_EYE_RIGHT_OF_REED"})
               for layout in failure_candidates["F02_east_clue_omitted"])
    assert all(passes_room_clues(layout, set(CLUES) - {"W_REED_NOT_FIRST"})
               and not passes_room_clues(layout, {"W_REED_NOT_FIRST"})
               for layout in failure_candidates["F03_west_clue_omitted"])

    result = {
        "map_id": "MAP-13",
        "permutation_count": len(all_permutations),
        "primary_clues": list(CLUES),
        "candidate_counts_clockwise": candidate_counts,
        "solutions_clockwise": unique_clockwise,
        "clue_deletion_solution_counts_clockwise": deletion_counts,
        "solutions_counterclockwise_mirror": unique_mirror,
        "distinct_physical_layouts_without_orientation_marker": len(layouts_without_orientation),
        "orientation_marker_is_necessary_to_select_physical_room_mapping": True,
        "failure_candidate_layouts": failure_candidates,
        "runtime_verified": False,
    }
    output = ROOT / "planning" / "constraint_audit.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "UNIQUE_AND_EACH_PRIMARY_CLUE_NECESSARY",
                      "permutations": len(all_permutations),
                      "cw_solution": unique_clockwise[0],
                      "deletion_counts": deletion_counts,
                      "orientation_free_layouts": len(layouts_without_orientation),
                      "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
