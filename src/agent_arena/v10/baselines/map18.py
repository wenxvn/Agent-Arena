"""MAP-18 V10 基线：真值感知 Oracle（记忆化搜索）、公开启发式与四类对照。

- ``oracle``：知道密封故障，枚举每 tick 的可行时刻表行，按
  (成功, 送达人数, -延误, -取消) 字典序最优；只证明可解性，不代表可发现性；
- ``public_heuristic``：只读 Observation；按计划到达时刻排优先级，逐 tick 前进，
  避开 ``closed_segments``、同段冲突与站台超员；若受阻任务已不可能在 horizon 前送达且
  占用他人目的站，就取消并把空车调离；
- ``no_replan``：照公开无故障计划执行，被闭塞挡住就下一 tick 原样重试，不做冲突复查；
- ``greedy_dispatch``：所有可发车列车尽快前进，避开封闭区段与同段冲突，但不看站台容量；
- ``ignore_windows``：无视发车窗口抢跑，被拒后按拒绝码逐个剔除抢跑列车（考察旁路成本）。
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from agent_arena.v10.runtime.map18 import (
    ADJACENCY,
    RELEASE_TICKS,
    ROUTES,
    STATION_CAPACITY,
    TRAIN_TASK,
    Map18V10Environment,
    edge_key,
    planned_arrival,
)
from agent_arena.worlds.scenario_v8.models import V8Action

Action = dict[str, Any]
TASK_TRAIN = {task: train for train, task in TRAIN_TASK.items()}


def _row(tick: int, operations: dict[str, dict[str, Any]]) -> Action:
    return {"tool": "set_timetable", "tick": tick, "operations": operations}


# --------------------------------------------------------------------------- Oracle
def _candidate_rows(
    environment: Map18V10Environment, *, allow_cancel: bool
) -> list[dict[str, dict[str, Any]]]:
    per_train: list[list[tuple[str, dict[str, Any] | None]]] = []
    for train in sorted(TRAIN_TASK):
        task = TRAIN_TASK[train]
        state = environment.task_status[task]
        options: list[tuple[str, dict[str, Any] | None]] = [(train, None)]
        position = environment.positions[train]
        if state == "pending":
            hop = ROUTES[task][environment.progress[task] + 1]
            started = environment.progress[task] > 0
            if started or environment.current_tick >= RELEASE_TICKS[task]:
                closed = (
                    environment._closed_now()
                    and edge_key(position, hop) == environment.fault_edge_key
                )
                if not closed:
                    options.append((train, {"op": "release", "to": hop}))
            # 剪枝：只允许取消首段当前封闭的待发任务（Oracle 证明可解，不保证全局最优）。
            first_closed = (
                environment._closed_now() and edge_key(position, hop) == environment.fault_edge_key
            )
            if not started and allow_cancel and first_closed:
                options.append((train, {"op": "cancel_service", "task_id": task}))
        elif state == "canceled":
            for neighbor in ADJACENCY[position]:
                options.append((train, {"op": "release", "to": neighbor}))
        per_train.append(options)
    rows: list[dict[str, dict[str, Any]]] = [{}]
    for options in per_train:
        rows = [
            {**row, train: op} if op is not None else dict(row)
            for row in rows
            for train, op in options
        ]
    return rows


def _key(environment: Map18V10Environment) -> tuple[Any, ...]:
    return (
        environment.current_tick,
        tuple(sorted(environment.positions.items())),
        tuple(sorted(environment.task_status.items())),
        tuple(sorted(environment.progress.items())),
    )


def oracle_actions(environment_seed: int) -> list[Action]:
    """先在不取消的子空间搜索；没有成功方案时才放开取消。"""

    plan = _search(environment_seed, allow_cancel=False)
    if plan[0][0] == 1:
        return plan[1]
    return _search(environment_seed, allow_cancel=True)[1]


def _search(
    environment_seed: int, *, allow_cancel: bool
) -> tuple[tuple[int, int, int, int], list[Action]]:
    root = Map18V10Environment(seed=environment_seed)
    root.step_limit = 10**6
    memo: dict[tuple[Any, ...], tuple[tuple[int, int, int, int], list[Action]]] = {}

    # 记忆化值只含“从当前状态起”的未来延误；送达/取消人数由状态键唯一决定。
    def score(environment: Map18V10Environment) -> tuple[int, int, int, int]:
        return (int(environment.is_success), environment.delivered, 0, -environment.canceled)

    def solve(
        environment: Map18V10Environment,
    ) -> tuple[tuple[int, int, int, int], list[Action]]:
        if environment.is_terminal:
            return score(environment), []
        key = _key(environment)
        if key in memo:
            return memo[key]
        best: tuple[tuple[int, int, int, int], list[Action]] = (
            (-1, -1, -(10**6), -(10**6)),
            [],
        )
        for operations in _candidate_rows(environment, allow_cancel=allow_cancel):
            twin = environment.clone()
            payload = _row(twin.current_tick, operations)
            before = twin.current_tick
            twin.step(V8Action.model_validate(payload, strict=True))
            if twin.current_tick == before and not twin.is_terminal:
                continue
            if twin.status.value == "scenario_failure" and twin.terminal_reason != (
                "DEADLINE_SERVICE_BELOW_THRESHOLD"
            ):
                continue
            tail_value, tail = solve(twin)
            step_delay = twin.delay_person_ticks - environment.delay_person_ticks
            value = (tail_value[0], tail_value[1], tail_value[2] - step_delay, tail_value[3])
            if value > best[0]:
                best = (value, [payload, *tail])
        memo[key] = best
        return best

    return solve(root)


# --------------------------------------------------------------------------- 公开启发式
def _pending(observation: dict[str, Any]) -> list[str]:
    status = observation["task_status"]
    return [task for task in sorted(ROUTES) if status[task] == "pending"]


def _progress(observation: dict[str, Any], task: str) -> int:
    route = ROUTES[task]
    position = observation["train_positions"][TASK_TRAIN[task]]
    return route.index(position)


def _closed(observation: dict[str, Any]) -> set[str]:
    return {str(item) for item in observation.get("closed_segments") or []}


def _safe_moves(observation: dict[str, Any], proposals: list[tuple[str, str]]) -> dict[str, str]:
    """按优先级逐个接受，满足：同段每 tick 1 车、站台 ≤2；直到不动点。"""

    positions = dict(observation["train_positions"])
    accepted: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for train, destination in proposals:
            if train in accepted:
                continue
            edges = {edge_key(positions[name], to) for name, to in accepted.items()}
            if edge_key(positions[train], destination) in edges:
                continue
            trial = {**accepted, train: destination}
            nxt = dict(positions)
            nxt.update(trial)
            if max(Counter(nxt.values()).values()) > STATION_CAPACITY:
                continue
            accepted[train] = destination
            changed = True
    return accepted


class Map18Heuristic:
    name = "public_heuristic"
    capacity_aware = True
    closure_aware = True
    allow_cancel = True

    def reset(self) -> None:
        return None

    def _eligible(self, observation: dict[str, Any], task: str) -> bool:
        return _progress(observation, task) > 0 or observation["tick"] >= RELEASE_TICKS[task]

    def proposals(self, observation: dict[str, Any]) -> list[tuple[str, str]]:
        closed = _closed(observation) if self.closure_aware else set()
        result = []
        for task in sorted(_pending(observation), key=lambda item: (planned_arrival(item), item)):
            if not self._eligible(observation, task):
                continue
            train = TASK_TRAIN[task]
            position = observation["train_positions"][train]
            hop = ROUTES[task][_progress(observation, task) + 1]
            if edge_key(position, hop) in closed:
                continue
            result.append((train, hop))
        return result

    def _blockers(self, observation: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """不可能按时送达、且占用他人目的站的待发列车：取消。已取消空车：调离到无人需要的邻站。"""

        operations: dict[str, dict[str, Any]] = {}
        positions = observation["train_positions"]
        pending = _pending(observation)
        needed = {ROUTES[task][-1] for task in pending} | {
            node for task in pending for node in ROUTES[task][1:]
        }
        remaining = int(observation["ticks_remaining"])
        closed = _closed(observation)
        for task in pending:
            if _progress(observation, task) != 0:
                continue
            train = TASK_TRAIN[task]
            hops = len(ROUTES[task]) - 1
            first = edge_key(ROUTES[task][0], ROUTES[task][1])
            others_need = any(
                ROUTES[other][-1] == positions[train] for other in pending if other != task
            )
            if first in closed and hops >= remaining and others_need:
                operations[train] = {"op": "cancel_service", "task_id": task}
        counts = Counter(positions.values())
        status = observation["task_status"]
        for task in sorted(ROUTES):
            if status[task] != "canceled":
                continue
            train = TASK_TRAIN[task]
            here = positions[train]
            if here not in needed:
                continue
            for neighbor in ADJACENCY[here]:
                if (
                    neighbor not in needed
                    and counts.get(neighbor, 0) < STATION_CAPACITY
                    and edge_key(here, neighbor) not in closed
                ):
                    operations[train] = {"op": "release", "to": neighbor}
                    break
        return operations

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        tick = int(observation["tick"])
        operations: dict[str, dict[str, Any]] = {}
        if self.allow_cancel:
            operations.update(self._blockers(observation))
        proposals = [item for item in self.proposals(observation) if item[0] not in operations]
        relocations = [
            (train, op["to"]) for train, op in operations.items() if op["op"] == "release"
        ]
        if self.capacity_aware:
            accepted = _safe_moves(observation, relocations + proposals)
            for train in list(operations):
                if operations[train]["op"] == "release" and train not in accepted:
                    del operations[train]
            moves = {train: to for train, to in accepted.items() if train not in operations}
        else:
            moves = dict(proposals)
        for train, destination in moves.items():
            operations[train] = {"op": "release", "to": destination}
        return _row(tick, operations)


class Map18NoReplan(Map18Heuristic):
    """照公开无故障计划执行：到点就发车，被挡住就原样重试；不看封闭区段，不做冲突复查。"""

    name = "no_replan"
    capacity_aware = False
    closure_aware = False
    allow_cancel = False


class Map18GreedyDispatch(Map18Heuristic):
    """贪心：尽快前进，避开封闭区段与同段冲突，但不做站台容量前瞻、不取消。"""

    name = "greedy_dispatch"
    allow_cancel = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        tick = int(observation["tick"])
        positions = observation["train_positions"]
        used: set[str] = set()
        operations: dict[str, dict[str, Any]] = {}
        for train, hop in self.proposals(observation):
            key = edge_key(positions[train], hop)
            if key in used:
                continue
            used.add(key)
            operations[train] = {"op": "release", "to": hop}
        return _row(tick, operations)


class Map18IgnoreWindows(Map18Heuristic):
    """抢跑：把所有待发任务当作已到发车时刻；被拒后剔除拒绝码点名的列车再提交。"""

    name = "ignore_windows"

    def reset(self) -> None:
        self.banned: dict[int, set[str]] = {}

    def _eligible(self, observation: dict[str, Any], task: str) -> bool:
        tick = int(observation["tick"])
        return TASK_TRAIN[task] not in self.banned.get(tick, set())

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        if history:
            last = str(history[-1].get("result", ""))
            if last.startswith("DISPATCH_WINDOW_VIOLATION:"):
                self.banned.setdefault(int(observation["tick"]), set()).add(last.split(":", 1)[1])
        return super().act(observation, history)


HEURISTIC = Map18Heuristic
ABLATIONS: dict[str, type[Map18Heuristic]] = {
    "no_replan": Map18NoReplan,
    "greedy_dispatch": Map18GreedyDispatch,
    "ignore_windows": Map18IgnoreWindows,
}

__all__ = ["ABLATIONS", "HEURISTIC", "Map18Heuristic", "oracle_actions"]
