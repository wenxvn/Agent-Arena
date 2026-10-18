"""MAP-04 V10 基线：真值 Oracle、相位预测启发式与四类消融。

公开启发式只读 `tide_phase` / `tide_period` / `open_phases` / `location` /
`inventory` / `visible_edges` / `failed_crossing_ticks`，用相位算术决定“等几 tick 再通过”。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map04 import (
    BASE_EDGES,
    EXTRA_EDGES,
    oracle_actions,
)

Action = dict[str, Any]
FORWARD = ("T_B1", "B1_B2", "B2_B3", "B3_B4", "B4_D", "G_D")
FORWARD_EXTRA = ("T_B1", "B1_BX", "BX_B2", "B2_B3", "B3_B4", "B4_D", "G_D")


CHAIN: tuple[str, ...] = ("T", "B1", "B2", "B3", "B4", "D", "G")
CHAIN_EXTRA: tuple[str, ...] = ("T", "B1", "BX", "B2", "B3", "B4", "D", "G")


def _route_to(location: str, target: str) -> list[str]:
    """沿绕行海岸路在 location → target 之间取最短的一段边序列。"""

    edges = dict(BASE_EDGES)
    edges.update(EXTRA_EDGES)
    for chain in (CHAIN, CHAIN_EXTRA):
        if any(
            frozenset({chain[index], chain[index + 1]}) not in
            {frozenset(pair) for pair in edges.values()}
            for index in range(len(chain) - 1)
        ):
            continue
        if location not in chain or target not in chain:
            continue
        start, goal = chain.index(location), chain.index(target)
        step = 1 if goal > start else -1
        route: list[str] = []
        for index in range(start, goal, step):
            a, b = chain[index], chain[index + step]
            edge_id = next(
                item for item, pair in edges.items() if frozenset(pair) == frozenset({a, b})
            )
            route.append(edge_id)
        return route
    return []


class Map04PhaseAware:
    """相位预测：等到安全相位再通过，两点之间只走 S_G。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def _safe_delay(self, observation: dict[str, Any]) -> int:
        phase = int(observation["tide_phase"])
        period = int(observation["tide_period"])
        safe = set(observation["open_phases"])
        for delay in range(period):
            if (phase + delay) % period in safe:
                return delay
        return 0

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        carried = "wick" in observation["inventory"]
        fitted = bool(observation["lamp_wick_fitted"])
        if fitted and location == "T":
            return {"tool": "interact", "target": "lamp", "choice": "ignite"}
        if not carried:
            if location == "T":
                return {"tool": "move", "edge_id": "T_S"}
            if location == "S":
                delay = self._safe_delay(observation)
                if delay:
                    return {"tool": "wait", "turns": delay}
                return {"tool": "move", "edge_id": "S_G"}
            return {"tool": "pickup", "item_id": "wick"}
        if location == "T":
            return {"tool": "interact", "target": "lamp", "choice": "fit_wick"}
        if location == "S":
            return {"tool": "move", "edge_id": "T_S"}
        delay = self._safe_delay(observation)
        if delay:
            return {"tool": "wait", "turns": delay}
        return {"tool": "move", "edge_id": "S_G"}


class Map04DetourOnly:
    """只走绕行海岸路，从不使用 S_G（合法但有可衡量成本）。"""

    name = "detour_only"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        carried = "wick" in observation["inventory"]
        fitted = bool(observation["lamp_wick_fitted"])
        if fitted and location == "T":
            return {"tool": "interact", "target": "lamp", "choice": "ignite"}
        if not carried:
            if location == "G":
                return {"tool": "pickup", "item_id": "wick"}
            self.queue = [{"tool": "move", "edge_id": e} for e in _route_to(location, "G")]
            return self.queue.pop(0)
        if location == "T":
            return {"tool": "interact", "target": "lamp", "choice": "fit_wick"}
        self.queue = [{"tool": "move", "edge_id": e} for e in _route_to(location, "T")]
        return self.queue.pop(0)


class Map04BlindRetry:
    """看到门就撞，失败再撞，从不等待。"""

    name = "blind_retry"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        carried = "wick" in observation["inventory"]
        fitted = bool(observation["lamp_wick_fitted"])
        if fitted and location == "T":
            return {"tool": "interact", "target": "lamp", "choice": "ignite"}
        if not carried:
            if location == "T":
                return {"tool": "move", "edge_id": "T_S"}
            if location == "S":
                return {"tool": "move", "edge_id": "S_G"}
            return {"tool": "pickup", "item_id": "wick"}
        if location == "T":
            return {"tool": "interact", "target": "lamp", "choice": "fit_wick"}
        if location == "S":
            return {"tool": "move", "edge_id": "T_S"}
        return {"tool": "move", "edge_id": "S_G"}


class Map04ExcessWait:
    """相位用对了但每次多等一个整周期（时间余量被浪费）。"""

    name = "excess_wait"

    def reset(self) -> None:
        self.inner = Map04PhaseAware()
        self.inner.reset()

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = self.inner.act(observation, history)
        if payload["tool"] == "wait":
            payload = dict(payload)
            payload["turns"] = min(8, int(payload["turns"]) + int(observation["tide_period"]))
        return payload


class Map04FixedScript:
    """用固定相位表（每步空等 1 tick）行动，不读相位。"""

    name = "fixed_phase_script"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        carried = "wick" in observation["inventory"]
        fitted = bool(observation["lamp_wick_fitted"])
        if fitted and location == "T":
            return {"tool": "interact", "target": "lamp", "choice": "ignite"}
        if not carried:
            if location == "T":
                return {"tool": "move", "edge_id": "T_S"}
            if location == "S":
                return {"tool": "wait", "turns": 1}
            return {"tool": "pickup", "item_id": "wick"}
        if location == "T":
            return {"tool": "interact", "target": "lamp", "choice": "fit_wick"}
        return {"tool": "wait", "turns": 1}


HEURISTIC = Map04PhaseAware
ABLATIONS: dict[str, type[Any]] = {
    "detour_only": Map04DetourOnly,
    "blind_retry": Map04BlindRetry,
    "excess_wait": Map04ExcessWait,
    "fixed_phase_script": Map04FixedScript,
}

__all__ = [
    "ABLATIONS",
    "FORWARD",
    "HEURISTIC",
    "Map04BlindRetry",
    "Map04DetourOnly",
    "Map04ExcessWait",
    "Map04FixedScript",
    "Map04PhaseAware",
    "oracle_actions",
]
