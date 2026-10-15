"""Audit MAP-15's hand-fixed colors, parity answers, and anti-memorization matrix."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY_TICKS = {"A": 0, "B": 1, "C": 2, "T": 3}


def target_color(area: dict, tick: int, complement: dict[str, str]) -> str:
    wall = area["wall_color"]
    return wall if tick % 2 == 0 else complement[wall]


def main() -> None:
    design = json.loads((ROOT / "planning" / "room_signs.json").read_text(encoding="utf-8"))
    regions = design["regions"]
    complement = design["color_complements"]
    colors = set(complement)
    assert set(complement.values()) == colors
    assert all(complement[complement[color]] == color and complement[color] != color for color in colors)
    assert list(regions) == ["A", "B", "C", "T"]

    samples = []
    sequences = {}
    for area_name in regions:
        area = regions[area_name]
        doors = area["door_colors"]
        expected_count = 4 if area_name == "T" else 3
        assert len(doors) == expected_count and len(set(doors)) == expected_count
        assert set(doors) <= colors
        target = target_color(area, ENTRY_TICKS[area_name], complement)
        matching_slots = [i + 1 for i, color in enumerate(doors) if color == target]
        assert len(matching_slots) == 1
        samples.append({
            "area": area_name,
            "role": area["role"],
            "tick_before": ENTRY_TICKS[area_name],
            "parity": "even" if ENTRY_TICKS[area_name] % 2 == 0 else "odd",
            "wall_color": area["wall_color"],
            "door_colors": doors,
            "target_color": target,
            "accepted_slot": matching_slots[0],
        })
        sequences[area_name] = doors

    training = [sequences[name] for name in ("A", "B", "C")]
    assert all(sequences["T"] != row for row in training)
    assert len({tuple(row) for row in [*training, sequences["T"]]}) == 4
    assert [regions[name]["wall_color"] for name in ("A", "B")] == ["red", "red"]
    assert [ENTRY_TICKS[name] % 2 for name in ("A", "B")] == [0, 1]
    assert [regions[name]["wall_color"] for name in ("C", "T")] == ["gold", "gold"]
    assert [ENTRY_TICKS[name] % 2 for name in ("C", "T")] == [0, 1]

    test_wrong_recovery = {
        "test_wall_color": regions["T"]["wall_color"],
        "wrong_choice_tick": 3,
        "wrong_choice_color": regions["T"]["door_colors"][1],
        "tick_after_wrong": 4,
        "recomputed_target_color": target_color(regions["T"], 4, complement),
        "recovery_slot": next(i + 1 for i, color in enumerate(regions["T"]["door_colors"])
                               if color == target_color(regions["T"], 4, complement)),
    }
    assert test_wrong_recovery == {
        "test_wall_color": "gold", "wrong_choice_tick": 3, "wrong_choice_color": "red",
        "tick_after_wrong": 4, "recomputed_target_color": "gold", "recovery_slot": 1,
    }

    result = {
        "map_id": "MAP-15",
        "runtime_verified": False,
        "rule_id": design["target_rule_id"],
        "complement_pairs": complement,
        "manually_authored_samples_and_test": samples,
        "training_order_sequences": sequences,
        "test_sequence_differs_from_every_training_sequence": True,
        "same_wall_color_shown_at_both_parities": {"red": [0, 1], "gold": [0, 1]},
        "one_test_error_recovery": test_wrong_recovery,
        "resources_start": 4,
        "test_wrong_limit": 1,
        "all_regions_have_one_unique_matching_door_at_the_entry_tick": True,
    }
    output = ROOT / "planning" / "rule_audit.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "FOUR_UNIQUE_LOCAL_TARGETS_AND_TRANSFER_CHECKED",
                      "samples": [{"area": x["area"], "tick": x["tick_before"],
                                   "target": x["target_color"], "slot": x["accepted_slot"]}
                                  for x in samples],
                      "test_recovery": test_wrong_recovery,
                      "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
