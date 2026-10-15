"""Replay MAP-12's two hand-authored calendars into an auditable daily ledger."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPAIRS = {7, 14, 21, 28}
EDGE_ENDPOINTS = {
    "H_E": {"H", "E"}, "E_G": {"E", "G"}, "G_S": {"G", "S"},
    "S_L": {"S", "L"}, "H_S": {"H", "S"}, "G_L": {"G", "L"},
}


def replay(name: str, plan: dict) -> list[dict]:
    fuel = 40
    food = {"H": 30, "E": 0, "G": 0}
    parts = {"S": 8, "G": 0, "E": 0}
    heat_fuel_spent = 0
    greenhouse_fuel_spent = 0
    food_consumed = 0
    parts_repaired = 0
    controller_online = True
    heater_on = True
    greenhouse_powered = False
    crop_planted = False
    greenhouse_streak = 0
    research_streak = 0
    research_points = 0
    heat_shortage_streak = 0
    food_shortage_streak = 0
    trace: list[dict] = []

    batches_by_day: dict[int, list[dict]] = {}
    for batch in plan["greenhouse_batches"]:
        batches_by_day.setdefault(batch["power_day"], []).append(batch)
    research_days = set(plan["research_days"])
    parts_by_day: dict[int, list[dict]] = {}
    food_by_day: dict[int, list[dict]] = {}
    for movement in plan["part_transfers"]:
        parts_by_day.setdefault(movement["day"], []).append(movement)
    for movement in plan["food_transfers"]:
        food_by_day.setdefault(movement["day"], []).append(movement)

    for day in range(1, 31):
        actions: list[dict] = []
        if day in REPAIRS:
            controller_online = False  # Wear disconnects G/L before today's work.
            if parts["E"] < 2:
                raise ValueError(f"{name}: parts not at E before repair on day {day}")
            parts["E"] -= 2
            parts_repaired += 2
            controller_online = True
            actions.append({"tool": "repair_controller", "location": "E", "parts": 2})

        for batch in batches_by_day.get(day, []):
            if greenhouse_powered or not controller_online:
                raise ValueError(f"{name}: cannot start greenhouse on day {day}")
            greenhouse_powered = True
            actions.append({"tool": "start_greenhouse_power", "location": "E"})
            if crop_planted:
                raise ValueError(f"{name}: a crop batch is already active on day {day}")
            crop_planted = True
            actions.append({"tool": "plant_batch", "location": "G"})

        did_research = day in research_days
        if did_research:
            if not controller_online:
                raise ValueError(f"{name}: research while controller offline on day {day}")
            actions.append({"tool": "research", "location": "L"})

        for movement in parts_by_day.get(day, []):
            transfer("parts", movement, parts, actions, name, day)
        for movement in food_by_day.get(day, []):
            transfer("food", movement, food, actions, name, day)
        if len(actions) > 2:
            raise ValueError(f"{name}: {len(actions)} labor actions on day {day}")

        if heater_on and fuel >= 1:
            fuel -= 1
            heat_fuel_spent += 1
            heat_shortage_streak = 0
        else:
            heat_shortage_streak += 1

        harvested = 0
        if greenhouse_powered and controller_online and crop_planted:
            if fuel < 1:
                raise ValueError(f"{name}: greenhouse fuel exhausted on day {day}")
            fuel -= 1
            greenhouse_fuel_spent += 1
            greenhouse_streak += 1
            if greenhouse_streak == 3:
                food["G"] += 5
                harvested = 5
                greenhouse_powered = False
                crop_planted = False
                greenhouse_streak = 0
        else:
            greenhouse_streak = 0

        if food["H"] > 0:
            food["H"] -= 1
            food_consumed += 1
            food_shortage_streak = 0
        else:
            food_shortage_streak += 1

        if did_research:
            research_streak += 1
            if research_streak == 3:
                research_points += 3
                research_streak = 0
        else:
            research_streak = 0

        terminal = False
        reason = None
        if heat_shortage_streak >= 2:
            terminal, reason = True, "HEAT_SHORTAGE_STREAK"
        elif food_shortage_streak >= 2:
            terminal, reason = True, "FOOD_SHORTAGE_STREAK"
        elif day == 30 and research_points < 12:
            terminal, reason = True, "RESEARCH_TARGET_MISSED"
        elif day == 30:
            terminal, reason = True, "SUCCESS"

        if fuel + heat_fuel_spent + greenhouse_fuel_spent != 40:
            raise AssertionError(f"{name}: fuel conservation failed on day {day}")
        if sum(food.values()) + food_consumed != 30 + 5 * sum(
            1 for prior in trace if prior["harvested_food"] == 5
        ) + harvested:
            raise AssertionError(f"{name}: food conservation failed on day {day}")
        if sum(parts.values()) + parts_repaired != 8:
            raise AssertionError(f"{name}: parts conservation failed on day {day}")

        state = {
            "fuel_E": fuel,
            "heat_fuel_spent_total": heat_fuel_spent,
            "greenhouse_fuel_spent_total": greenhouse_fuel_spent,
            "food_by_node": dict(food),
            "food_consumed_total": food_consumed,
            "parts_by_node": dict(parts),
            "parts_repaired_total": parts_repaired,
            "heater_on": heater_on,
            "controller_online": controller_online,
            "greenhouse_powered": greenhouse_powered,
            "crop_planted": crop_planted,
            "greenhouse_powered_streak": greenhouse_streak,
            "harvested_food": harvested,
            "research_streak": research_streak,
            "research_points": research_points,
            "heat_shortage_streak": heat_shortage_streak,
            "food_shortage_streak": food_shortage_streak,
            "labor_actions_used": len(actions),
            "labor_slots_remaining": 2 - len(actions),
            "terminal": terminal,
            "terminal_reason": reason,
        }
        trace.append({"trace_id": name, "step": day, "day_before": day - 1,
                      "actions": actions, "harvested_food": harvested,
                      "expected_state": state})

    if research_points < 12 or food_shortage_streak or heat_shortage_streak:
        raise ValueError(f"{name}: hand calendar does not satisfy the success predicate")
    return trace


def transfer(commodity: str, movement: dict, stocks: dict[str, int],
             actions: list[dict], plan_name: str, day: int) -> None:
    edge = movement["edge_id"]
    source, destination = movement["from_node"], movement["to_node"]
    quantity = movement["quantity"]
    limit = 2 if commodity == "parts" else 5
    if edge not in EDGE_ENDPOINTS or EDGE_ENDPOINTS[edge] != {source, destination}:
        raise ValueError(f"{plan_name}: noncanonical edge {edge} on day {day}")
    if source not in stocks or destination not in stocks or not 0 < quantity <= limit:
        raise ValueError(f"{plan_name}: invalid {commodity} transfer on day {day}")
    if stocks[source] < quantity:
        raise ValueError(f"{plan_name}: insufficient {commodity} at {source} on day {day}")
    stocks[source] -= quantity
    stocks[destination] += quantity
    actions.append({"tool": "transfer", "commodity": commodity, "edge_id": edge,
                    "from_node": source, "to_node": destination, "quantity": quantity})


def main() -> None:
    source = ROOT / "planning" / "hand_calendars.json"
    plans = json.loads(source.read_text(encoding="utf-8"))["plans"]
    out_path = ROOT / "oracle_trace.jsonl"
    all_traces = [row for name, plan in plans.items() for row in replay(name, plan)]
    out_path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                                for row in all_traces), encoding="utf-8")
    summary = {}
    for name in plans:
        rows = [row for row in all_traces if row["trace_id"] == name]
        final = rows[-1]["expected_state"]
        summary[name] = {
            "days": len(rows), "terminal": final["terminal_reason"],
            "research_points": final["research_points"], "food_H": final["food_by_node"]["H"],
            "fuel_E": final["fuel_E"], "parts_repaired": final["parts_repaired_total"],
            "max_actions_per_day": max(row["expected_state"]["labor_actions_used"] for row in rows),
        }
    print(json.dumps({"result": "HAND_CALENDARS_REPLAYED", "trace_rows": len(all_traces),
                      "plans": summary, "output": str(out_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
