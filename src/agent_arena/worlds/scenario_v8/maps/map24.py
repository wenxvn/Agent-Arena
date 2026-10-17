"""MAP-24｜消失的道路：桥塌事件、潮窗与过期路线笔记。

本图与同世界另两图的机制差异：MAP-22 的图永远不变；MAP-23 的图静态、难度来自
“哪个入口为真”的信息价值。本图在 tick 8 永久移除 A-B、B-C，D-E 潮道按 4 拍
开 2 拍且相位 seed 私有；主机制是“旧笔记与世界不一致时是否改路”。

指标口径（与 V7 卡片一致）：
- ``replanning_latency`` = 坍塌后首次“改路移动”的发起 tick − 8；若 Agent 在
  坍塌时不在 A/B/C 或没有改路需求，返回 ``None``。
- ``route_cost_ratio`` = 首次本地看到断边后到交付的实际移动成本（含失败移动）
  / 同点最短可行移动成本；未观察断边或已交付前未观察，返回 ``None``。
- ``collapsed_edge_attempts`` = 坍塌后仍尝试已移除桥边的次数。
- ``rescue_failure`` = 终局未把两件物资都带回 A 记 1。

实现约定：坍塌在动作完成 tick 结算；tick 8 完成的一拍移动可以先到位，若此时
身在 B 则立即 ``STRANDED_ON_BRIDGE``。潮道开窗用出发 tick 判定。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action, V8Status

EDGES: dict[frozenset[str], int] = {
    frozenset({"A", "B"}): 1,
    frozenset({"B", "C"}): 1,
    frozenset({"C", "D"}): 1,
    frozenset({"D", "E"}): 1,
    frozenset({"E", "A"}): 1,
    frozenset({"A", "F"}): 2,
    frozenset({"F", "C"}): 2,
}
BRIDGE_EDGES = (frozenset({"A", "B"}), frozenset({"B", "C"}))
NODES = ("A", "B", "C", "D", "E", "F")
ITEMS = {"relic_C": "C", "supply_case_D": "D"}
REQUIRED_ITEMS = ("relic_C", "supply_case_D")
BRIDGE_COLLAPSE_TICK = 8
DEADLINE = 24


class Map24Environment(MapEnvironment):
    map_id = "MAP-24"
    title = "消失的道路"
    world = "jungle"
    level = "困难"
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
            "location",
            "local_connections",
            "visible_item_here",
            "carried_items",
            "latest_local_tide_reading",
            "bridge_probe_result",
            "route_notes",
            "tide_rule",
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        self.node = "A"
        self.phase_offset = seed % 4
        self.collapsed = False
        self.carried: list[str] = []
        self.taken: set[str] = set()
        self.notes: dict[str, dict[str, Any]] = {}
        self.tide_reading: dict[str, Any] | None = None
        self.bridge_probe: str | None = None
        self.tide_measurements = 0
        self.collapsed_attempts = 0
        self.failed_moves = 0
        self.observation_tick: int | None = None
        self.observation_node: str | None = None
        self.first_replan_tick: int | None = None
        self.remaining_move_cost = 0
        self.delivery_tick: int | None = None
        self._cost = 1

    # ------------------------------------------------------------------ helpers
    def _tide_open(self, tick: int) -> bool:
        return (tick + self.phase_offset) % 4 in (0, 1)

    def _edge_open(self, edge: frozenset[str]) -> bool:
        if edge in BRIDGE_EDGES and self.collapsed:
            return False
        return True

    def _local_connections(self) -> list[dict[str, Any]]:
        connections = []
        for edge, duration in sorted(
            EDGES.items(), key=lambda item: sorted(item[0])
        ):
            if self.node not in edge:
                continue
            if not self._edge_open(edge):
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

    # ------------------------------------------------------------------ public
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
            "location": self.node,
            "local_connections": self._local_connections(),
            "visible_item_here": visible,
            "carried_items": list(self.carried),
            "latest_local_tide_reading": self.tide_reading,
            "bridge_probe_result": self.bridge_probe,
            "route_notes": {
                node: dict(note) for node, note in sorted(self.notes.items())
            },
            "tide_rule": {
                "period_ticks": 4,
                "open_ticks": 2,
                "phase_is_seed_private": True,
            },
            "goal": (
                "在 tick 24 前把 relic_C 与 supply_case_D 都带回 A；桥会在未知时刻"
                "永久断开，D-E 潮道只在部分窗口可过。"
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
        if edge in BRIDGE_EDGES and self.collapsed:
            self.collapsed_attempts += 1
            if self._observation_active():
                self.remaining_move_cost += 1
            self._cost = 1
            return "MOVE_FAILED_EDGE_CLOSED"
        if edge == frozenset({"D", "E"}) and not self._tide_open(self.tick_count):
            self.failed_moves += 1
            if self._observation_active():
                self.remaining_move_cost += 1
            self._cost = 1
            return "MOVE_FAILED_EDGE_CLOSED"
        if self._observation_active() and edge not in BRIDGE_EDGES:
            if self.first_replan_tick is None:
                self.first_replan_tick = self.tick_count
        self.remaining_move_cost += duration if self._observation_active() else 0
        self._cost = duration
        self.node = str(target)
        return f"MOVED:{target}"

    def _observation_active(self) -> bool:
        return self.observation_tick is not None

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
        self.bridge_probe = (
            "COLLAPSED" if self.collapsed else "PASSABLE_WITH_CRACKS"
        )
        return f"BRIDGE_PROBED:{self.bridge_probe}"

    def _measure_tide(self) -> str:
        if self.node not in ("D", "E"):
            self._cost = 0
            return "TIDE_MEASURE_ONLY_AT_D_OR_E"
        self.tide_measurements += 1
        reading_tick = self.tick_count + 1
        self.tide_reading = {
            "tick": reading_tick,
            "state": "OPEN" if self._tide_open(reading_tick) else "CLOSED",
        }
        return f"TIDE_MEASURED:{self.tide_reading['state']}"

    def _record_route(self) -> str:
        self.notes[self.node] = {
            "tick": self.tick_count,
            "connections": [
                connection["to"] for connection in self._local_connections()
            ],
        }
        return f"ROUTE_RECORDED:{self.node}"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    def _after_tick(self) -> None:
        if self.status is not V8Status.RUNNING:
            return
        if not self.collapsed and self.tick_count >= BRIDGE_COLLAPSE_TICK:
            self.collapsed = True
            self._count("BRIDGE_COLLAPSED")
            if self.node == "B":
                self._fail("STRANDED_ON_BRIDGE")
                return
        if (
            self.observation_tick is None
            and self.tick_count >= BRIDGE_COLLAPSE_TICK
            and self.node in ("A", "B", "C")
        ):
            self.observation_tick = self.tick_count
            self.observation_node = self.node
        if self.all_delivered():
            self._succeed("ALL_ITEMS_DELIVERED")
            self.delivery_tick = self.tick_count
            return
        if self.tick_count > DEADLINE:
            self._fail("DEADLINE_EXCEEDED")

    def all_delivered(self) -> bool:
        return self.node == "A" and all(item in self.carried for item in REQUIRED_ITEMS)

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "location": self.node,
            "phase_offset": self.phase_offset,
            "collapsed": self.collapsed,
            "carried": list(self.carried),
            "taken": sorted(self.taken),
            "notes": {
                node: dict(note) for node, note in sorted(self.notes.items())
            },
            "tide_reading": dict(self.tide_reading) if self.tide_reading else None,
            "tide_measurements": self.tide_measurements,
            "collapsed_attempts": self.collapsed_attempts,
            "failed_moves": self.failed_moves,
            "observation_tick": self.observation_tick,
            "observation_node": self.observation_node,
            "first_replan_tick": self.first_replan_tick,
            "remaining_move_cost": self.remaining_move_cost,
            "delivery_tick": self.delivery_tick,
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
            "counters": dict(sorted(self.counters.items())),
        }

    def _shortest_cost(self, start: str) -> int | None:
        tide_known_open = bool(
            self.tide_reading
            and self.observation_tick is not None
            and self.tide_reading["tick"] >= self.observation_tick
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
                current_best = best[other]
                if current_best is None or candidate < current_best:
                    best[other] = candidate
                    frontier.append(other)
        return best["A"]

    def metrics(self) -> dict[str, Any]:
        latency = None
        if self.first_replan_tick is not None:
            latency = self.first_replan_tick - BRIDGE_COLLAPSE_TICK
        ratio = None
        if self.observation_node is not None:
            shortest = self._shortest_cost(self.observation_node)
            if shortest:
                ratio = self.remaining_move_cost / shortest
        return {
            "map24.replanning_latency": latency,
            "map24.route_cost_ratio": ratio,
            "map24.collapsed_edge_attempts": self.collapsed_attempts,
            "map24.rescue_failure": int(not self.is_success),
        }


ORACLE_CASES: tuple[dict[str, Any], ...] = (
    {
        "trace_id": "probe_then_update",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "B"},
            {"tool": "probe_bridge"},
            {"tool": "record_route"},
            {"tool": "move", "to": "C"},
            {"tool": "take", "item_id": "relic_C"},
            {"tool": "move", "to": "D"},
            {"tool": "take", "item_id": "supply_case_D"},
            {"tool": "move", "to": "C"},
            {"tool": "record_route"},
            {"tool": "move", "to": "F"},
            {"tool": "move", "to": "A"},
        ],
        "expect_success": True,
    },
    {
        "trace_id": "mountain_and_tide",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "F"},
            {"tool": "move", "to": "C"},
            {"tool": "take", "item_id": "relic_C"},
            {"tool": "move", "to": "D"},
            {"tool": "take", "item_id": "supply_case_D"},
            {"tool": "measure_tide"},
            {"tool": "move", "to": "E"},
            {"tool": "move", "to": "A"},
        ],
        "expect_success": True,
    },
)


FIXTURES = (
    {
        "name": "normal_update_after_collapse",
        "seed": 0,
        "actions": list(ORACLE_CASES[0]["actions"]),
        "expect": {
            "map24.replanning_latency": 2,
            "map24.route_cost_ratio": 1.0,
            "map24.collapsed_edge_attempts": 0,
            "map24.rescue_failure": 0,
        },
    },
    {
        "name": "mountain_route_has_no_replan",
        "seed": 0,
        "actions": list(ORACLE_CASES[1]["actions"]),
        "expect": {
            "map24.replanning_latency": None,
            "map24.route_cost_ratio": None,
            "map24.collapsed_edge_attempts": 0,
            "map24.rescue_failure": 0,
        },
    },
    {
        "name": "stranded_on_bridge",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "B"},
            {"tool": "move", "to": "C"},
            {"tool": "take", "item_id": "relic_C"},
            {"tool": "move", "to": "D"},
            {"tool": "take", "item_id": "supply_case_D"},
            {"tool": "move", "to": "C"},
            {"tool": "move", "to": "B"},
            {"tool": "record_route"},
        ],
        "expect": {
            "map24.replanning_latency": None,
            "map24.route_cost_ratio": None,
            "map24.collapsed_edge_attempts": 0,
            "map24.rescue_failure": 1,
        },
    },
    {
        "name": "stale_note_repeats_collapsed_edge",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "B"},
            {"tool": "probe_bridge"},
            {"tool": "record_route"},
            {"tool": "move", "to": "C"},
            {"tool": "take", "item_id": "relic_C"},
            {"tool": "move", "to": "D"},
            {"tool": "take", "item_id": "supply_case_D"},
            {"tool": "move", "to": "C"},
            *({"tool": "move", "to": "B"} for _ in range(16)),
        ],
        "expect": {
            "map24.replanning_latency": None,
            "map24.route_cost_ratio": 4.0,
            "map24.collapsed_edge_attempts": 16,
            "map24.rescue_failure": 1,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map24Environment"]
