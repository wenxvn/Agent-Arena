"""MAP-24 V10 基线：真值 Oracle、公开在线重规划启发式与三类消融。

公开启发式只读 `local_connections`（当前房间的可见边）、`carried_items`、
`visible_item_here`、`latest_local_tide_reading` 与公开规则：维护一张“已确认存在”的边表，
每次移动后用当前房间的 `local_connections` 删掉已消失的边，再在已知图上跑最短路；
潮道相位未知，先在 D/E 读一次再决定何时过。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map24 import (
    EDGES,
    ITEMS,
    REQUIRED,
    oracle_actions,
)

Action = dict[str, Any]


def _edge_key(a: str, b: str) -> frozenset[str]:
    return frozenset({a, b})


def _shortest(
    known: set[frozenset[str]], start: str, goal: str, *, allow_tide: bool
) -> list[str] | None:
    best: dict[str, int] = {start: 0}
    parent: dict[str, str] = {}
    frontier = [start]
    while frontier:
        frontier.sort(key=lambda node: best[node])
        current = frontier.pop(0)
        if current == goal:
            break
        for edge in known:
            if current not in edge:
                continue
            if edge == _edge_key("D", "E") and not allow_tide:
                continue
            other = next(node for node in edge if node != current)
            distance = best[current] + EDGES[edge]
            if other not in best or distance < best[other]:
                best[other] = distance
                parent[other] = current
                frontier.append(other)
    if goal not in parent and goal != start:
        return None
    path = [goal]
    while path[-1] != start:
        path.append(parent[path[-1]])
    return list(reversed(path))


class Map24OnlineReplan:
    """公开启发式：在线维护已知图，发现断边立刻改路。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.known: set[frozenset[str]] = set(EDGES)
        self.tide_open_next: bool | None = None

    def _observe(self, observation: dict[str, Any]) -> None:
        here = str(observation["location"])
        present = {
            _edge_key(here, item["to"]) for item in observation["local_connections"]
        }
        for edge in list(self.known):
            if here in edge and edge not in present:
                self.known.discard(edge)
        reading = observation["latest_local_tide_reading"]
        if reading and reading["tick"] == observation["tick"] + 1:
            self.tide_open_next = reading["state"] == "OPEN"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        self._observe(observation)
        if self.queue:
            return self.queue.pop(0)
        here = str(observation["location"])
        carried = set(observation["carried_items"])
        remaining = [item for item in REQUIRED if item not in carried]
        if not remaining:
            path = _shortest(self.known, here, "A", allow_tide=self._tide_ok(observation, here))
            return self._next_move(here, path, observation)
        target_item = remaining[0]
        target = ITEMS[target_item]
        if here == target:
            self.queue = []
            return {"tool": "take", "item_id": target_item}
        path = _shortest(self.known, here, target, allow_tide=self._tide_ok(observation, here))
        if path is None:
            path = _shortest(self.known, here, target, allow_tide=True)
        return self._next_move(here, path, observation)

    def _tide_ok(self, observation: dict[str, Any], here: str) -> bool:
        if here in ("D", "E") and self.tide_open_next is not None:
            return self.tide_open_next
        return True

    def _next_move(
        self, here: str, path: list[str] | None, observation: dict[str, Any]
    ) -> Action:
        if path is None or len(path) < 2:
            return {"tool": "wait"}
        nxt = path[1]
        if _edge_key(here, nxt) == _edge_key("D", "E"):
            reading = observation["latest_local_tide_reading"]
            fresh = bool(reading and reading["tick"] == observation["tick"])
            if not fresh:
                return {"tool": "measure_tide"}
            if reading["state"] != "OPEN":
                return {"tool": "wait"}
        return {"tool": "move", "to": nxt}


class Map24NoReplan(Map24OnlineReplan):
    """断边后死守旧桥路：继续撞已断的桥。"""

    name = "no_replan"

    def _observe(self, observation: dict[str, Any]) -> None:
        reading = observation["latest_local_tide_reading"]
        if reading and reading["tick"] == observation["tick"] + 1:
            self.tide_open_next = reading["state"] == "OPEN"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        here = str(observation["location"])
        carried = set(observation["carried_items"])
        remaining = [item for item in REQUIRED if item not in carried]
        if here == "B":
            return {"tool": "move", "to": "C"}
        if not remaining:
            path = _shortest(self.known, here, "A", allow_tide=True)
            return self._next_move(here, path, observation)
        target = ITEMS[remaining[0]]
        if here == target:
            return {"tool": "take", "item_id": remaining[0]}
        path = _shortest(self.known, here, "B", allow_tide=True)
        if path is not None and len(path) >= 2:
            return self._next_move(here, path, observation)
        return {"tool": "wait"}


class Map24MountainOnly(Map24OnlineReplan):
    """只走山路，完全不使用桥（合法但慢）。"""

    name = "mountain_only"

    def reset(self) -> None:
        super().reset()
        self.known = {
            _edge_key("A", "F"),
            _edge_key("F", "C"),
            _edge_key("C", "D"),
            _edge_key("D", "E"),
            _edge_key("E", "A"),
        }


class Map24IgnoreTide(Map24OnlineReplan):
    """不读潮汐，直接反复尝试 D-E。"""

    name = "ignore_tide"

    def _next_move(
        self, here: str, path: list[str] | None, observation: dict[str, Any]
    ) -> Action:
        del observation
        if path is None or len(path) < 2:
            return {"tool": "wait"}
        return {"tool": "move", "to": path[1]}


class Map24WasteOpening(Map24OnlineReplan):
    """开局空转 6 tick 再出发（时间余量被浪费）。"""

    name = "waste_opening"

    def reset(self) -> None:
        super().reset()
        self.idle = 6

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        if self.idle > 0:
            self.idle -= 1
            return {"tool": "wait"}
        return super().act(observation, history)


HEURISTIC = Map24OnlineReplan
ABLATIONS: dict[str, type[Any]] = {
    "no_replan": Map24NoReplan,
    "mountain_only": Map24MountainOnly,
    "waste_opening": Map24WasteOpening,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map24MountainOnly",
    "Map24NoReplan",
    "Map24OnlineReplan",
    "Map24WasteOpening",
    "oracle_actions",
]
