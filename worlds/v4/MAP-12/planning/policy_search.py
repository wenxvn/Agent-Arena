"""MAP-12-only calendar search; it does not generate map content or runtime code.

This small standard-library DFS searches consecutive research-block placement and
day/slot placement of this map's two-edge parts and harvested-food transfers.
Topology, resource rules, greenhouse dates, repair dates, and transfer sizes are
fixed from the human-authored MAP-12 design. The returned calendar is feasibility
evidence only; the authored oracle and alternate strategy are reviewed separately.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


HORIZON = 30
ACTION_LIMIT = 2
REPAIR_DAYS = (7, 14, 21, 28)
GREENHOUSE_DAYS = (1, 2, 3)
LAST_FOOD_DELIVERY_DAY = 8


def action_sequences(day: int, slots: int, s: int, g: int, e: int,
                     food_g: int, food_e: int) -> tuple[tuple[tuple[str, ...], tuple[int, ...]], ...]:
    """Enumerate legal ordered transfer sequences, including leaving slots idle."""

    found: list[tuple[tuple[str, ...], tuple[int, ...]]] = [((), (s, g, e, food_g, food_e))]

    def extend(prefix: tuple[str, ...], state: tuple[int, ...], remaining: int) -> None:
        if remaining == 0:
            return
        ss, gg, ee, fgg, fee = state
        available: list[tuple[str, tuple[int, ...]]] = []
        if ss >= 2:
            available.append(("transfer_parts_S_to_G_edge_G_S", (ss - 2, gg + 2, ee, fgg, fee)))
        if gg >= 2:
            available.append(("transfer_parts_G_to_E_edge_E_G", (ss, gg - 2, ee + 2, fgg, fee)))
        if day >= 4 and fgg >= 5:
            available.append(("transfer_food_G_to_E_edge_E_G", (ss, gg, ee, fgg - 5, fee + 5)))
        if fee >= 5:
            available.append(("transfer_food_E_to_H_edge_H_E", (ss, gg, ee, fgg, fee - 5)))
        for name, nxt in available:
            seq = prefix + (name,)
            found.append((seq, nxt))
            extend(seq, nxt, remaining - 1)

    extend((), (s, g, e, food_g, food_e), slots)
    # Keep the first occurrence of each end state and its shortest ordered action list.
    unique: dict[tuple[int, ...], tuple[str, ...]] = {}
    for seq, state in found:
        if state not in unique or len(seq) < len(unique[state]):
            unique[state] = seq
    return tuple((seq, state) for state, seq in unique.items())


def search(research_start: int) -> dict | None:
    @lru_cache(maxsize=None)
    def visit(day: int, s: int, g: int, e: int, food_g: int, food_e: int,
              h_food: int, heat_misses: int, food_misses: int, points: int,
              research_streak: int, repairs_done: int, food_delivered: bool):
        if day > HORIZON:
            if points >= 12 and repairs_done == len(REPAIR_DAYS) and food_delivered:
                return ()
            return None

        forced: list[str] = []
        # Wear occurs before labor actions; enough parts must already be at E.
        if day in REPAIR_DAYS:
            if e < 2:
                return None
            e -= 2
            forced.append("repair_controller")
            repairs_done += 1
        if research_start <= day < research_start + 12:
            forced.append("research")
            research_streak += 1
            if research_streak == 3:
                points += 3
                research_streak = 0
        else:
            research_streak = 0
        if day == 1:
            forced.extend(("start_greenhouse_power", "plant_batch"))
        if len(forced) > ACTION_LIMIT:
            return None

        free_slots = ACTION_LIMIT - len(forced)
        for transfers, next_resources in action_sequences(day, free_slots, s, g, e, food_g, food_e):
            ns, ng, ne, nfg, nfe = next_resources
            if day == 3:
                nfg += 5  # The hand-fixed three-day powered batch harvests after actions.
            # With the 40-unit reserve, day-end fuel never becomes negative.
            if sum(1 + (1 if d in GREENHOUSE_DAYS else 0) for d in range(1, day + 1)) > 40:
                continue
            delivered_today = "transfer_food_E_to_H_edge_H_E" in transfers
            h_before_ration = h_food + (5 if delivered_today else 0)
            served = h_before_ration > 0
            nh = h_before_ration - (1 if served else 0)
            nfood_misses = 0 if served else food_misses + 1
            nheat_misses = heat_misses  # Heater remains on and has its fixed reserve.
            if nfood_misses >= 2 or nheat_misses >= 2:
                continue
            delivered = food_delivered or delivered_today
            if day <= LAST_FOOD_DELIVERY_DAY and not delivered and day == LAST_FOOD_DELIVERY_DAY:
                continue
            suffix = visit(day + 1, ns, ng, ne, nfg, nfe, nh, nheat_misses,
                           nfood_misses, points, research_streak, repairs_done, delivered)
            if suffix is not None:
                todays = forced + list(transfers)
                return ((day, todays, {
                    "parts_S": ns, "parts_G": ng, "parts_E_after_labor": ne,
                    "food_G_after_harvest": nfg, "food_E_after_labor": nfe,
                    "food_H_after_ration": nh, "research_points": points,
                    "research_streak": research_streak, "heat_shortage_streak": nheat_misses,
                    "food_shortage_streak": nfood_misses,
                    "fuel_E_after_settlement": 40 - sum(1 + (1 if d in GREENHOUSE_DAYS else 0) for d in range(1, day + 1)),
                }),) + suffix
        return None

    result = visit(1, 8, 0, 0, 0, 0, 30, 0, 0, 0, 0, 0, False)
    if result is None:
        return None
    return {"research_start_day": research_start, "days": [
        {"day": day, "actions": actions, "state": state} for day, actions, state in result
    ]}


def main() -> None:
    selected = None
    for start in range(2, 20):
        selected = search(start)
        if selected is not None:
            break
    if selected is None:
        raise SystemExit("No feasible calendar found in the bounded MAP-12 search space")
    selected["planner"] = "MAP-12-specific standard-library DFS; no runtime or map generator"
    selected["constraints"] = {
        "daily_action_limit": ACTION_LIMIT,
        "repair_days": list(REPAIR_DAYS),
        "parts_transfer": 2,
        "food_transfer": 5,
        "greenhouse_powered_days": list(GREENHOUSE_DAYS),
        "research_days": 12,
        "food_harvest_delivered_by_day": LAST_FOOD_DELIVERY_DAY,
    }
    output = Path(__file__).with_name("planner_search.json")
    output.write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": "FEASIBLE", "research_start_day": selected["research_start_day"],
                      "days_with_actions": sum(bool(row["actions"]) for row in selected["days"]),
                      "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
