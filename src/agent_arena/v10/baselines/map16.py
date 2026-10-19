"""MAP-16 V10 基线：单线预约的 Oracle、公开启发式与消融（DCR-V10-36）。

- Oracle：在四实例上做“单列车逐次移动”的联合状态 BFS，再翻译成
  `set_route` + `move_train` 动作对；
- 启发式：只读 Observation（拓扑/方向表/位置/终点/侧线），每步重新规划；
- 消融：禁用侧线、只登记不提交、双车同帧抢行。
"""

from __future__ import annotations

from collections import deque
from typing import Any

from agent_arena.v10.runtime.map16 import VARIANTS


def _plan(
    positions: dict[str, str],
    goals: dict[str, str],
    directions: dict[str, dict[str, tuple[str, ...]]],
    *,
    forbidden: frozenset[str] = frozenset(),
) -> list[tuple[str, str]]:
    """单列车逐次移动的 BFS；返回 [(train, next_node), ...]。"""

    trains = tuple(positions)
    start = tuple(positions[train] for train in trains)
    goal = tuple(goals[train] for train in trains)
    queue: deque[tuple[str, ...]] = deque([start])
    previous: dict[tuple[str, ...], tuple[tuple[str, ...], str, str] | None] = {start: None}
    while queue:
        state = queue.popleft()
        if state == goal:
            break
        for index, train in enumerate(trains):
            for following in directions[train][state[index]]:
                if following in forbidden or following in state:
                    continue
                candidate = state[:index] + (following,) + state[index + 1 :]
                if candidate in previous:
                    continue
                previous[candidate] = (state, train, following)
                queue.append(candidate)
    if goal not in previous:
        return []
    path: list[tuple[str, str]] = []
    cursor = goal
    while True:
        step = previous[cursor]
        if step is None:
            break
        prior, train, following = step
        path.append((train, following))
        cursor = prior
    path.reverse()
    return path


def oracle_actions(seed: int) -> list[dict[str, Any]]:
    variant = VARIANTS[seed]
    directions = _directions()
    path = _plan(variant.start_positions, variant.goals, directions)
    actions: list[dict[str, Any]] = []
    for train, following in path:
        actions.append({"tool": "set_route", "train_id": train, "next_node": following})
        actions.append({"tool": "move_train"})
    return actions


def _directions() -> dict[str, dict[str, tuple[str, ...]]]:
    from agent_arena.worlds.scenario_v4.map16 import DIRECTIONS

    return DIRECTIONS


class ReservationPolicy:
    """公开启发式：能从 Observation 重建方向表时，就不依赖密封真值。"""

    def __init__(
        self,
        *,
        allow_siding: bool = True,
        move: bool = True,
        name: str = "public_reservation",
    ) -> None:
        self.allow_siding = allow_siding
        self.move = move
        self.name = name

    def reset(self) -> None:
        return None

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        if not self.move:
            current = observation["train_positions"]["a"]
            options = observation["train_route_directions"]["a"][current]
            return {"tool": "set_route", "train_id": "a", "next_node": options[0]}
        if observation["pending_route_reservations"]:
            return {"tool": "move_train"}
        forbidden = frozenset() if self.allow_siding else frozenset(observation["siding_nodes"])
        path = _plan(
            observation["train_positions"],
            observation["train_goals"],
            observation["train_route_directions"],
            forbidden=forbidden,
        )
        if not path:
            return {"tool": "inspect_network"}
        train, following = path[0]
        return {"tool": "set_route", "train_id": train, "next_node": following}


class DoubleBookingPolicy:
    """消融：两列车同帧按各自最短路抢行，不等待对方让行。"""

    name = "double_booking"

    def reset(self) -> None:
        return None

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        pending = observation["pending_route_reservations"]
        positions = observation["train_positions"]
        goals = observation["train_goals"]
        unfinished = [
            train for train in sorted(positions) if positions[train] != goals[train]
        ]
        target = next((train for train in unfinished if train not in pending), None)
        if target is not None:
            path = _plan(
                {target: positions[target]},
                {target: goals[target]},
                observation["train_route_directions"],
            )
            if path:
                return {
                    "tool": "set_route",
                    "train_id": target,
                    "next_node": path[0][1],
                }
        return {"tool": "move_train"}


def HEURISTIC() -> ReservationPolicy:
    return ReservationPolicy()


def no_siding() -> ReservationPolicy:
    return ReservationPolicy(allow_siding=False, name="no_siding") 


def route_only() -> ReservationPolicy:
    return ReservationPolicy(move=False, name="route_only")


ABLATIONS = {
    "no_siding": no_siding,
    "route_only": route_only,
    "double_booking": DoubleBookingPolicy,
}

__all__ = [
    "ABLATIONS",
    "DoubleBookingPolicy",
    "HEURISTIC",
    "ReservationPolicy",
    "oracle_actions",
]
