"""MAP-24 V10｜消失的道路：封路落在主路径上且必须改路（DCR-V10-14）。

V9 的两条根因与对应修复：

1. **“完全不走桥就不会遇到改路”**：V8 的山路 A-F-C 与桥路 A-B-C 成本相同，启发式全程走
   山路，`replanning_latency` / `route_cost_ratio` 都是 N/A。V10 让**桥路成为唯一能在
   截止前完成的路线**（山路把 A-F 提到 3、F-C 提到 3），封路后只能改走山路，且必须在
   观察到封路后立刻改——继续撞已断的桥会超时；
2. **`replanning_latency` 假阳性/漏报**：V8 对“任何非桥边移动”置位，R2 改路 0 次却报
   latency=1；死守旧桥又报 None。V10 改成两条口径清晰、可复算的量：
   `replan_success`（观察到封路后完成且不再尝试断边）与 `replan_latency`
   （观察封路后的第一个移动 tick − 观察 tick），并新增 `collapse_observed` 公开标记。

其它差异：

- 封路时刻随 seed 隐藏变化（4/5/6/7），且**站在桥上不会瞬死**，而是被推回岸边并多耗 2 tick
  ——这保留了“继续撞桥”的合法选择，只是它会被时间余量惩罚；
- D-E 潮道相位随 seed（公开规则、隐藏相位）；
- 4 个预登记实例：封路时刻、潮汐相位、截止时刻都不同。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.metrics.schema import (
    MetricSpec,
    MValue,
    censored,
    not_applicable,
    ratio,
    valid,
)
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

NODES = ("A", "B", "C", "D", "E", "F")
EDGES: dict[frozenset[str], int] = {
    frozenset({"A", "B"}): 1,
    frozenset({"B", "C"}): 1,
    frozenset({"C", "D"}): 1,
    frozenset({"D", "E"}): 1,
    frozenset({"E", "A"}): 1,
    frozenset({"A", "F"}): 3,
    frozenset({"F", "C"}): 3,
}
EDGE_IDS: dict[str, tuple[str, str]] = {
    f"{sorted(edge)[0]}_{sorted(edge)[1]}": (sorted(edge)[0], sorted(edge)[1])
    for edge in EDGES
}
BRIDGE = (frozenset({"A", "B"}), frozenset({"B", "C"}))
ITEMS = {"relic_C": "C", "supply_case_D": "D"}
REQUIRED = ("relic_C", "supply_case_D")
PUSH_BACK_COST = 2


class Variant24:
    def __init__(self, label: str, collapse_tick: int, phase: int, deadline: int) -> None:
        self.label = label
        self.collapse_tick = collapse_tick
        self.phase = phase
        self.deadline = deadline


VARIANTS: dict[int, Variant24] = {
    0: Variant24("early_collapse", 4, 0, 18),
    1: Variant24("mid_collapse", 5, 1, 18),
    2: Variant24("late_collapse", 6, 2, 18),
    3: Variant24("very_late_collapse", 7, 3, 18),
}


class Map24V10Environment(V10Map):
    map_id = "MAP-24"
    title = "消失的道路"
    world = "jungle"
    level = "困难"
    RULE_VERSION = "v10.map24.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    EDGES = EDGE_IDS
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "to"})},
        "take": {frozenset({"tool", "item_id"})},
        "probe_bridge": {frozenset({"tool"})},
        "measure_tide": {frozenset({"tool"})},
        "record_route": {frozenset({"tool"})},
        "wait": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "deadline_tick",
            "location",
            "local_connections",
            "visible_item_here",
            "carried_items",
            "latest_local_tide_reading",
            "bridge_probe_result",
            "collapse_observed",
            "route_notes",
            "tide_rule",
            "goal",
        }
    )
    PRIMARY_METRIC = "map24.v10.replan_success"
    METRIC_SPECS = (
        MetricSpec(
            "map24.v10.replan_success",
            "primary",
            "higher",
            "观察到封路后完成且不再尝试断边",
            "观察到封路的局（1）",
            zero_denominator="从未观察到封路 → NOT_APPLICABLE",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map24.v10.replan_latency",
            "secondary",
            "lower",
            "观察封路后的第一个移动 tick − 观察 tick",
            "观察到封路的局（1）",
            zero_denominator="从未观察到封路 → NOT_APPLICABLE",
            unit="ticks",
            valid_range=(-5.0, 30.0),
        ),
        MetricSpec(
            "map24.v10.collapsed_edge_attempts_after_observation",
            "guardrail",
            "lower",
            "观察到封路后仍尝试断边的次数",
            "—",
            unit="count",
            valid_range=(0.0, 40.0),
        ),
        MetricSpec(
            "map24.v10.route_cost_ratio",
            "guardrail",
            "lower",
            "观察封路后到交付的实际移动成本 / 同点最短可行成本",
            "观察到封路且最短成本 > 0 的局（1）",
            zero_denominator="最短成本为 0 或未观察 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map24.v10.tide_failed_moves",
            "diagnostic",
            "lower",
            "潮道关闭时仍尝试通过的次数",
            "—",
            unit="count",
            valid_range=(0.0, 40.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.phase_offset = self.variant.phase
        self.node = "A"
        self.collapsed = False
        self.carried: list[str] = []
        self.taken: set[str] = set()
        self.notes: dict[str, dict[str, Any]] = {}
        self.tide_reading: dict[str, Any] | None = None
        self.bridge_probe: str | None = None
        self.collapsed_attempts_after = 0
        self.tide_failed_moves = 0
        self.observation_tick: int | None = None
        self.observation_node: str | None = None
        self.first_move_after_observation: int | None = None
        self.remaining_move_cost = 0
        self.delivery_tick: int | None = None
        self.bridge_used_before_collapse = False
        self._cost = 1

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "deadline_tick": self.variant.deadline,
            "tide": {"period": 4, "open": 2, "phase_is_seed_private": True},
            "max_bridge_route_ticks": 5,
            "mountain_route_ticks": 6,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "collapse_tick": self.variant.collapse_tick,
            "phase_offset": self.phase_offset,
            "deadline": self.variant.deadline,
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "路网：A-B-C-D-E-A 环 + A-F-C 山路；A-B 与 B-C 是桥，C-D、D-E、E-A 是地面/潮道。",
            "任务：把 relic_C（在 C）与 supply_case_D（在 D）都带回 A；两者都要。",
            "桥会在**未知时刻**永久断开；站在桥上会被推回岸边并多耗 2 tick。",
            "D-E 潮道每 4 tick 开 2 tick，相位隐藏；measure_tide 在 D 或 E 读出下一 tick 的状态。",
            "probe_bridge 只能在 B 用，耗 2 tick，读出桥是否已断。",
            "山路 A-F-C 比桥路慢：桥路 2 tick 到 C，山路 6 tick。",
            f"tick {self.variant.deadline} 前把两件物资带回 A 即成功。",
        )

    # ------------------------------------------------------------------ public
    def _tide_open(self, tick: int) -> bool:
        return (tick + self.phase_offset) % 4 in (0, 1)

    def _edge_open(self, edge: frozenset[str]) -> bool:
        if edge in BRIDGE and self.collapsed:
            return False
        return True

    def _local_connections(self) -> list[dict[str, Any]]:
        connections: list[dict[str, Any]] = []
        for edge, duration in sorted(EDGES.items(), key=lambda item: sorted(item[0])):
            if self.node not in edge or not self._edge_open(edge):
                continue
            other = next(node for node in edge if node != self.node)
            connections.append(
                {"edge": "-".join(sorted(edge)), "to": other, "ticks": duration}
            )
        return connections

    def _neighbors(self) -> dict[str, tuple[frozenset[str], int]]:
        return {
            next(node for node in edge if node != self.node): (edge, duration)
            for edge, duration in EDGES.items()
            if self.node in edge and self._edge_open(edge)
        }

    def _public(self) -> dict[str, Any]:
        visible = next(
            (
                item
                for item, location in ITEMS.items()
                if location == self.node and item not in self.taken
            ),
            None,
        )
        return {
            "tick": self.tick_count,
            "deadline_tick": self.variant.deadline,
            "location": self.node,
            "local_connections": self._local_connections(),
            "visible_item_here": visible,
            "carried_items": list(self.carried),
            "latest_local_tide_reading": self.tide_reading,
            "bridge_probe_result": self.bridge_probe,
            "collapse_observed": self.observation_tick is not None,
            "route_notes": {node: dict(note) for node, note in sorted(self.notes.items())},
            "tide_rule": {"period_ticks": 4, "open_ticks": 2, "phase_is_seed_private": True},
            "goal": (
                f"在 tick {self.variant.deadline} 前把 relic_C 与 supply_case_D 都带回 A；"
                "桥会在未知时刻永久断开，断了就必须改走山路。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._cost = 1
        tool = action.tool
        if tool == "move":
            return self._move(action)
        if tool == "take":
            return self._take(action)
        if tool == "probe_bridge":
            return self._probe_bridge()
        if tool == "measure_tide":
            return self._measure_tide()
        if tool == "record_route":
            return self._record_route()
        if tool == "wait":
            return "WAITED"
        return "ACTION_NOT_ALLOWED"

    def _move(self, action: V8Action) -> str:
        target = action.to
        if target not in NODES or target == self.node:
            self._cost = 0
            return "INVALID_DESTINATION"
        edge = frozenset({self.node, target})
        duration = EDGES.get(edge)
        if duration is None:
            self._cost = 0
            return "NOT_ADJACENT"
        if edge in BRIDGE and self.collapsed:
            if self.observation_tick is not None:
                self.collapsed_attempts_after += 1
            if self.observation_tick is not None:
                self.remaining_move_cost += 1
            return "MOVE_FAILED_EDGE_CLOSED"
        if edge == frozenset({"D", "E"}) and not self._tide_open(self.tick_count):
            self.tide_failed_moves += 1
            if self.observation_tick is not None:
                self.remaining_move_cost += 1
            return "MOVE_FAILED_EDGE_CLOSED"
        if self.observation_tick is not None and self.first_move_after_observation is None:
            self.first_move_after_observation = self.tick_count
        if self.observation_tick is not None:
            self.remaining_move_cost += duration
        if edge in BRIDGE and not self.collapsed:
            self.bridge_used_before_collapse = True
        self._cost = duration
        self.node = str(target)
        return f"MOVED:{target}"

    def _take(self, action: V8Action) -> str:
        item = action.item_id
        if item not in ITEMS:
            self._cost = 0
            return "INVALID_ITEM"
        if ITEMS[item] != self.node:
            self._cost = 0
            return "ITEM_NOT_HERE"
        if item in self.taken:
            return "ITEM_ALREADY_TAKEN"
        self.taken.add(item)
        self.carried.append(item)
        return f"ITEM_COLLECTED:{item}"

    def _probe_bridge(self) -> str:
        if self.node != "B":
            self._cost = 0
            return "PROBE_ONLY_AT_B"
        if self.bridge_probe is not None:
            return "BRIDGE_ALREADY_PROBED"
        self._cost = 2
        self.bridge_probe = "COLLAPSED" if self.collapsed else "PASSABLE_WITH_CRACKS"
        return f"BRIDGE_PROBED:{self.bridge_probe}"

    def _measure_tide(self) -> str:
        if self.node not in ("D", "E"):
            self._cost = 0
            return "TIDE_MEASURE_ONLY_AT_D_OR_E"
        reading_tick = self.tick_count + 1
        self.tide_reading = {
            "tick": reading_tick,
            "state": "OPEN" if self._tide_open(reading_tick) else "CLOSED",
        }
        return f"TIDE_MEASURED:{self.tide_reading['state']}"

    def _record_route(self) -> str:
        self.notes[self.node] = {
            "tick": self.tick_count,
            "connections": [item["to"] for item in self._local_connections()],
        }
        return f"ROUTE_RECORDED:{self.node}"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    def _after_tick(self) -> None:
        if self.status.value != "running":
            return
        if not self.collapsed and self.tick_count >= self.variant.collapse_tick:
            self.collapsed = True
            self._count("BRIDGE_COLLAPSED")
            if self.node == "B":
                self.node = "A"
                self.tick_count += PUSH_BACK_COST
        if (
            self.observation_tick is None
            and self.collapsed
            and self.node in ("A", "B", "C")
        ):
            self.observation_tick = self.tick_count
            self.observation_node = self.node
        if self.all_delivered():
            self.delivery_tick = self.tick_count
            self._succeed("ALL_ITEMS_DELIVERED")
            return
        if self.tick_count > self.variant.deadline:
            self._fail("DEADLINE_EXCEEDED")

    def all_delivered(self) -> bool:
        return self.node == "A" and all(item in self.carried for item in REQUIRED)

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "tick": self.tick_count,
            "location": self.node,
            "phase_offset": self.phase_offset,
            "collapse_tick": self.variant.collapse_tick,
            "collapsed": self.collapsed,
            "carried": list(self.carried),
            "taken": sorted(self.taken),
            "tide_reading": dict(self.tide_reading) if self.tide_reading else None,
            "observation_tick": self.observation_tick,
            "observation_node": self.observation_node,
            "first_move_after_observation": self.first_move_after_observation,
            "collapsed_attempts_after": self.collapsed_attempts_after,
            "tide_failed_moves": self.tide_failed_moves,
            "remaining_move_cost": self.remaining_move_cost,
            "delivery_tick": self.delivery_tick,
            "truth_seal": self.truth_seal(),
        }

    def _shortest_cost(self, start: str) -> int | None:
        tide_known_open = bool(
            self.tide_reading
            and self.observation_tick is not None
            and self.tide_reading["tick"] >= (self.observation_tick or 0)
            and self.tide_reading["state"] == "OPEN"
        )
        best: dict[str, int | None] = {node: None for node in NODES}
        best[start] = 0
        frontier = [start]
        while frontier:
            current = frontier.pop(0)
            for edge, duration in EDGES.items():
                if current not in edge or not self._edge_open(edge):
                    continue
                if edge == frozenset({"D", "E"}) and not tide_known_open:
                    continue
                other = next(node for node in edge if node != current)
                candidate = (best[current] or 0) + duration
                if best[other] is None or candidate < (best[other] or 0):
                    best[other] = candidate
                    frontier.append(other)
        return best["A"]

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        observed = self.observation_tick is not None
        assessable = observed and self.bridge_used_before_collapse
        if running:
            success: MValue = censored("截尾")
            latency: MValue = censored("截尾")
        elif not assessable:
            success = not_applicable(
                "未观察封路" if not observed else "封路前未使用桥路，无法评估改路"
            )
            latency = not_applicable(
                "未观察封路" if not observed else "封路前未使用桥路，无法评估改路"
            )
        else:
            success = valid(
                int(self.is_success and self.collapsed_attempts_after == 0)
            )
            latency = valid(
                (self.first_move_after_observation - (self.observation_tick or 0))
                if self.first_move_after_observation is not None
                else 0
            )
        if observed and self.observation_node is not None:
            shortest = self._shortest_cost(self.observation_node)
            if shortest:
                cost_ratio: MValue = ratio(self.remaining_move_cost, shortest)
            else:
                cost_ratio = not_applicable("同点最短成本为 0")
        else:
            cost_ratio = not_applicable("未观察封路")
        return {
            "map24.v10.replan_success": success,
            "map24.v10.replan_latency": latency,
            "map24.v10.collapsed_edge_attempts_after_observation": valid(
                self.collapsed_attempts_after
            ),
            "map24.v10.route_cost_ratio": cost_ratio,
            "map24.v10.tide_failed_moves": valid(self.tide_failed_moves),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：封路被观察到（改路判定的前提）。"""

        return self.observation_tick is not None


def _adjacency() -> dict[str, list[tuple[str, int]]]:
    adjacency: dict[str, list[tuple[str, int]]] = {node: [] for node in NODES}
    for edge, duration in EDGES.items():
        a, b = tuple(edge)
        adjacency[a].append((b, duration))
        adjacency[b].append((a, duration))
    return adjacency


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知 Dijkstra：状态 = (节点, tick, 已取件掩码)，封路时刻已知。"""

    variant = VARIANTS[environment_seed]
    adjacency = _adjacency()
    item_list = list(REQUIRED)
    start = ("A", 0, 0)
    best: dict[tuple[str, int, int], int] = {start: 0}
    parent: dict[tuple[str, int, int], tuple[tuple[str, int, int], dict[str, Any]]] = {}
    frontier: list[tuple[int, tuple[str, int, int]]] = [(0, start)]
    goal_state: tuple[str, int, int] | None = None
    while frontier:
        frontier.sort()
        cost, state = frontier.pop(0)
        node, tick, mask = state
        if node == "A" and mask == (1 << len(item_list)) - 1:
            goal_state = state
            break
        if cost > variant.deadline + 2:
            continue
        transitions: list[tuple[int, tuple[str, int, int], dict[str, Any]]] = []
        for mask_bit, item in enumerate(item_list):
            if not mask & (1 << mask_bit) and ITEMS[item] == node:
                transitions.append(
                    (1, (node, tick + 1, mask | (1 << mask_bit)), {"tool": "take", "item_id": item})
                )
        collapsed = tick >= variant.collapse_tick
        for other, duration in adjacency[node]:
            edge = frozenset({node, other})
            if edge in BRIDGE and collapsed:
                continue
            if edge == frozenset({"D", "E"}) and (tick + variant.phase) % 4 not in (0, 1):
                continue
            transitions.append(
                (duration, (other, tick + duration, mask), {"tool": "move", "to": other})
            )
        for duration, new_state, action in transitions:
            total = cost + (duration if action["tool"] == "move" else 1)
            if total > variant.deadline:
                continue
            if best.get(new_state, 10**9) <= total:
                continue
            best[new_state] = total
            parent[new_state] = (state, action)
            frontier.append((total, new_state))
    if goal_state is None:  # pragma: no cover - 每个 seed 都有可行解
        raise RuntimeError("no feasible plan")
    actions: list[dict[str, Any]] = []
    cursor = goal_state
    while cursor != start:
        previous, action = parent[cursor]
        actions.append(action)
        cursor = previous
    actions.reverse()
    return actions


__all__ = [
    "EDGES",
    "Map24V10Environment",
    "NODES",
    "REQUIRED",
    "VARIANTS",
    "Variant24",
    "oracle_actions",
]
