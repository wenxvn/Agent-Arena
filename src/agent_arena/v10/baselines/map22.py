"""MAP-22 V10 基线：真值 Oracle、公开记忆 DFS 启发式与四类消融。

公开启发式只用 Observation 的 `current_sign`、`bearings`、`agent_notes` 与公开规则：
把“当前前进路径”和“已试过的 (sign,bearing)”各自压缩成**一条**状态笔记反复重写
（`agent_notes` 只追加，取最后一次即当前状态），据此做带回溯的 DFS；到遗迹后按记录的
路径反向返回营地。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map22 import MOVE_BUDGET, OPPOSITE, oracle_actions

Action = dict[str, Any]


def _state(observation: dict[str, Any], key: str) -> str:
    value = ""
    for note in observation["agent_notes"]:
        if note["key"] == key:
            value = note["value"]
    return value


def _path(observation: dict[str, Any]) -> list[str]:
    raw = _state(observation, "path_state")
    return [item for item in raw.split(",") if item]


def _tried(observation: dict[str, Any]) -> set[str]:
    raw = _state(observation, "tried_state")
    return {item for item in raw.split(",") if item}


class Map22MemoryDFS:
    """公开记忆 DFS：用一条状态笔记维护路径与已试方位。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        sign = str(observation["current_sign"])
        path = _path(observation)
        if sign == "camp" and observation["ruin_recorded"] and not path:
            return {"tool": "return_to_camp"}
        if sign == "ruin":
            if not observation["ruin_recorded"]:
                return {"tool": "check_goal"}
            if not path:
                return {"tool": "return_to_camp"}
            self.queue = [
                {"tool": "move", "bearing": OPPOSITE[bearing]} for bearing in reversed(path)
            ]
            return self.queue.pop(0)
        tried = _tried(observation)
        back = OPPOSITE[path[-1]] if path else None
        candidates = [
            bearing
            for bearing in observation["bearings"]
            if bearing != back and f"{sign}|{bearing}" not in tried
        ]
        if candidates:
            bearing = candidates[0]
            new_path = [*path, bearing]
            new_tried = sorted({*tried, f"{sign}|{bearing}"})
            self.queue = [{"tool": "move", "bearing": bearing}]
            return {
                "tool": "write_memory",
                "facts": [
                    {"key": "path_state", "value": ",".join(new_path)},
                    {"key": "tried_state", "value": ",".join(new_tried)},
                ],
            }
        if not path:
            return {"tool": "observe_signpost"}
        new_path = path[:-1]
        self.queue = [
            {
                "tool": "write_memory",
                "facts": [{"key": "path_state", "value": ",".join(new_path)}],
            },
            {"tool": "move", "bearing": OPPOSITE[path[-1]]},
        ]
        return self.queue.pop(0)


class Map22NoMemoryWrite(Map22MemoryDFS):
    """不写记忆：只用最近 5 条 history 回溯。"""

    name = "no_memory_write"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        if self.queue:
            return self.queue.pop(0)
        sign = str(observation["current_sign"])
        recent = [
            str(item["action"]["bearing"])
            for item in history
            if item["action"].get("tool") == "move" and item["action"].get("bearing")
        ]
        if sign == "ruin":
            if not observation["ruin_recorded"]:
                return {"tool": "check_goal"}
            if not recent:
                return {"tool": "return_to_camp"}
            self.queue = [
                {"tool": "move", "bearing": OPPOSITE[bearing]} for bearing in reversed(recent)
            ]
            return self.queue.pop(0)
        back = OPPOSITE[recent[-1]] if recent else None
        candidates = [bearing for bearing in observation["bearings"] if bearing != back]
        if candidates:
            return {"tool": "move", "bearing": candidates[0]}
        if not recent:
            return {"tool": "observe_signpost"}
        return {"tool": "move", "bearing": OPPOSITE[recent[-1]]}


class Map22FixedBearing(Map22MemoryDFS):
    """固定按 north/east/south/west 顺序走，不记路线。"""

    name = "fixed_bearings"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        sign = str(observation["current_sign"])
        if sign == "ruin" and not observation["ruin_recorded"]:
            return {"tool": "check_goal"}
        bearings = observation["bearings"]
        for bearing in ("north", "east", "south", "west"):
            if bearing in bearings:
                return {"tool": "move", "bearing": bearing}
        return {"tool": "observe_signpost"}


class Map22NoReturn(Map22MemoryDFS):
    """到遗迹后不返程（只记录、原地观察）。"""

    name = "no_return"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        if observation["current_sign"] == "ruin":
            if not observation["ruin_recorded"]:
                return {"tool": "check_goal"}
            return {"tool": "observe_signpost"}
        return super().act(observation, history)


class Map22RandomWalk(Map22MemoryDFS):
    """按固定循环依次尝试可用方位（不看记忆）。"""

    name = "random_walk"

    def reset(self) -> None:
        super().reset()
        self.counter = 0

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        sign = str(observation["current_sign"])
        if sign == "ruin" and not observation["ruin_recorded"]:
            return {"tool": "check_goal"}
        bearings = observation["bearings"]
        if not bearings:
            return {"tool": "observe_signpost"}
        self.counter += 1
        return {"tool": "move", "bearing": bearings[self.counter % len(bearings)]}


HEURISTIC = Map22MemoryDFS
ABLATIONS: dict[str, type[Any]] = {
    "no_memory_write": Map22NoMemoryWrite,
    "fixed_bearings": Map22FixedBearing,
    "no_return": Map22NoReturn,
    "random_walk": Map22RandomWalk,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "MOVE_BUDGET",
    "Map22FixedBearing",
    "Map22MemoryDFS",
    "Map22NoMemoryWrite",
    "Map22NoReturn",
    "Map22RandomWalk",
    "oracle_actions",
]
