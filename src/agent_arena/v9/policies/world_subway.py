"""V9 subway 世界（MAP-16 / MAP-17 / MAP-18）公开启发式策略。

运行时只读公开 Observation 与自己的 history，不导入 Environment、judge_state、
Oracle 或 Trace。三张图里有两张（MAP-16、MAP-18）是 V4 适配图；其冻结规则实现
在 ``scenario_v4``，策略只使用 Observation 里公开的拓扑、容量、位置、目标与
``published_dispatch_windows``。

编写策略时用到了一部分只存在于冻结规则代码里的事实（例如 MAP-16 的 D 是唯一
侧线、``release_section`` 只能撤销本车尚未提交的预约；MAP-17 的 ``switch_line``
只接受 ``ring|branch``；MAP-18 的闭塞窗口为 (5,10)）。这些事实**没有**出现在公开
prompt 中，逐条标注见 ``docs/v9/maps/MAP-1X-audit.md`` 第 3 节。策略本身只用
Observation 字段，不读取隐藏真值。

三个主策略的目标是"在公开 Observation 上可复现"，不是复刻 Oracle：
MAP-16 用公开拓扑做 BFS 会车规划；MAP-17 用公开 OD 表排 12 行时刻表；
MAP-18 按公开 dispatch window 错峰，把红线恢复留到封锁解除之后。
"""

from __future__ import annotations

from collections import deque
from itertools import product
from typing import Any

Action = dict[str, Any]


# --------------------------------------------------------------------------- MAP-16
def _successors(
    state: tuple[str, ...],
    trains: tuple[str, ...],
    directions: dict[str, dict[str, list[str]]],
) -> list[tuple[str, ...]]:
    """与公开拓扑一致的联合后继：停住或沿本车方向走一步。

    只使用 Observation 的 ``train_route_directions``（每车在当前节点的允许去向）
    与 ``node_capacities``=1 的隐含约束：同 tick 两车不能落到同一节点，也不能
    同时占用同一无向区段（同向亦然）。
    """

    options = [
        sorted({state[index], *directions[train].get(state[index], [])})
        for index, train in enumerate(trains)
    ]
    results: list[tuple[str, ...]] = []
    for combination in product(*options):
        if len(set(combination)) != len(combination):
            continue
        blocked = False
        for left in range(len(combination)):
            for right in range(left + 1, len(combination)):
                if combination[left] != state[left] and combination[right] != state[right]:
                    if frozenset((state[left], combination[left])) == frozenset(
                        (state[right], combination[right])
                    ):
                        blocked = True
        if not blocked:
            results.append(combination)
    return sorted(results)


def _first_step(
    state: tuple[str, ...],
    goal: tuple[str, ...],
    trains: tuple[str, ...],
    directions: dict[str, dict[str, list[str]]],
) -> tuple[str, ...] | None:
    """BFS 到双车终点，返回本 tick 的下一步位置。"""

    if state == goal:
        return state
    parent: dict[tuple[str, ...], tuple[str, ...] | None] = {state: None}
    queue: deque[tuple[str, ...]] = deque([state])
    while queue:
        current = queue.popleft()
        for following in _successors(current, trains, directions):
            if following in parent:
                continue
            parent[following] = current
            if following == goal:
                path = [following]
                while parent[path[-1]] is not None:
                    path.append(parent[path[-1]])  # type: ignore[arg-type]
                path.reverse()
                return path[1] if len(path) > 1 else following
            queue.append(following)
    return None


class Map16Heuristic:
    """单线会车：在公开拓扑上做联合 BFS，让先到避让点的一列车进 D 侧线。

    MAP-16 的可行解必须让两列反向车在 M 附近交会，而全线只有一条侧线 D；
    因此任何一个安全计划都会包含"一列车进 D、另一列通过 M、第一列再出来"。
    本策略不假设哪列车让行：BFS 从当前公开位置搜索 6 tick 的最短联合计划，
    每 tick 先把计划里的每个移动提交为 ``set_route``，再 ``move_train`` 原子结算。

    公开依据：``topology``、``train_route_directions``、``train_positions``、
    ``train_goals``、``segment_capacities``、``node_capacities``、
    ``pending_route_reservations``。
    """

    name = "public_heuristic"

    def reset(self) -> None:
        pass

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        positions = dict(observation["train_positions"])
        goals = dict(observation["train_goals"])
        directions = {
            train: {node: list(nodes) for node, nodes in table.items()}
            for train, table in observation["train_route_directions"].items()
        }
        pending = dict(observation.get("pending_route_reservations") or {})
        trains = tuple(sorted(positions))

        state = tuple(positions[train] for train in trains)
        goal = tuple(goals[train] for train in trains)
        plan = _first_step(state, goal, trains, directions)
        if plan is None:  # 公开拓扑上已无安全完成路径；观察后重试
            return {"tool": "inspect_network"}
        moves = {
            train: plan[index]
            for index, train in enumerate(trains)
            if plan[index] != positions[train]
        }
        # 计划外但仍挂着的预约先撤销，避免 move_train 提交计划外移动。
        for train in trains:
            if train in pending and train not in moves:
                return {
                    "tool": "release_section",
                    "train_id": train,
                    "section_id": f"{positions[train]}{pending[train]}",
                }
        # 一列一列提交预约；D 只是普通节点，set_route 已足以占用侧线。
        for train in trains:
            if train in moves and train not in pending:
                return {
                    "tool": "set_route",
                    "train_id": train,
                    "next_node": moves[train],
                }
        return {"tool": "move_train"}


class Map16NoSiding:
    """消融：只让字母序第一列未到终点的车沿主线推进，永不使用 D 侧线。

    复现 V8 R0 的因果：a 单线推进到 Y 后与停在 B 的 b 互相堵死，
    ``_has_safe_completion`` 判定不可恢复并以 DEADLOCK 终局。
    """

    name = "no_siding"

    def reset(self) -> None:
        pass

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        positions = dict(observation["train_positions"])
        goals = dict(observation["train_goals"])
        directions = observation["train_route_directions"]
        pending = dict(observation.get("pending_route_reservations") or {})
        if pending:
            return {"tool": "move_train"}
        for train in sorted(positions):
            if positions[train] == goals[train]:
                continue
            options = [node for node in directions[train].get(positions[train], []) if node != "D"]
            if options:
                return {"tool": "set_route", "train_id": train, "next_node": options[0]}
        return {"tool": "inspect_network"}  # 不会到达；保底提交形状合法的动作


# --------------------------------------------------------------------------- MAP-17
#: 时刻表骨架，由公开 ``demand_matrix`` 的 OD 名与拓扑手工排定，12 tick 结束。
#: 每个 tick 一行；board 里的数字会在运行时按 ``waiting_demand`` 与空座收缩。
_MAP17_TABLE: dict[int, dict[str, dict[str, Any]]] = {
    0: {
        "T_A": {"op": "stop", "board": {"A_to_C": 2}},
        "T_C": {"op": "stop", "board": {"C_to_F": 2}},
        "T_D": {"op": "stop", "board": {"D_to_B": 2}},
        "T_F": {"op": "stop", "board": {"F_to_A": 2}},
    },
    1: {
        "T_A": {"op": "release", "to": "B"},
        "T_C": {"op": "release", "to": "B"},
        "T_D": {"op": "release", "to": "C"},
        "T_F": {"op": "release", "to": "E"},
    },
    2: {
        "T_A": {"op": "release", "to": "C"},
        "T_C": {"op": "switch_line", "line": "branch", "board": {"B_to_E": 1}},
        "T_D": {"op": "delay"},
        "T_F": {"op": "release", "to": "B"},
    },
    3: {
        "T_C": {"op": "release", "to": "E"},
        "T_D": {"op": "release", "to": "B"},
        "T_F": {"op": "release", "to": "A"},
    },
    4: {
        "T_C": {"op": "release", "to": "F"},
        "T_D": {"op": "switch_line", "line": "branch", "board": {"B_to_E": 1}},
    },
    5: {"T_D": {"op": "release", "to": "E"}},
}

_MAP17_ADJACENCY: dict[str, tuple[str, ...]] = {
    "A": ("B", "D"),
    "B": ("A", "C", "E"),
    "C": ("B", "D"),
    "D": ("C", "A"),
    "E": ("B", "F"),
    "F": ("E",),
}


def _shrink_board(observation: dict[str, Any], manifest: dict[str, int]) -> dict[str, int]:
    """按公开 ``waiting_demand`` 收缩登车清单，避免 INVALID_BOARDING_MANIFEST。"""

    waiting = dict(observation.get("waiting_demand") or {})
    board: dict[str, int] = {}
    for od, count in manifest.items():
        available = int(waiting.get(od, 0))
        if available > 0:
            board[od] = min(int(count), available)
    return board


class Map17Heuristic:
    """早高峰：四车各自吃掉本始发站 OD，B→E 由经过 B 的两列车各带 1 人。

    公开依据：``demand_matrix``（OD 名与权重）、``waiting_demand``（实时收缩登车清单）、
    ``train_positions``、``topology``、``tick``、``energy_remaining``。12 行骨架是按
    公开 OD 表与拓扑手工排定的常量（与 Oracle 同构，但不是从 Oracle 读出来的）。
    设计取舍：优先服务率与最后交付 tick —— 12 tick 内把 10/10 人全部送达，
    能耗 11/18，等待只来自首 tick 的 10 人·tick 与 B 站换乘排队。
    """

    name = "public_heuristic"

    def reset(self) -> None:
        pass

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        tick = int(observation["tick"])
        row = _MAP17_TABLE.get(tick, {})
        positions = dict(observation["train_positions"])
        operations: dict[str, dict[str, Any]] = {}
        for train in sorted(row):
            spec = row[train]
            op = str(spec["op"])
            here = positions.get(train)
            if op == "release":
                destination = str(spec["to"])
                if destination not in _MAP17_ADJACENCY.get(str(here), ()):  # 防御：重试时状态已变
                    operations[train] = {"op": "delay"}
                    continue
                operations[train] = {"op": "release", "to": destination}
            elif op == "stop":
                board = _shrink_board(observation, dict(spec.get("board") or {}))
                operations[train] = {"op": "stop", "board": board}
            elif op == "switch_line":
                if here != "B":
                    operations[train] = {"op": "delay"}
                    continue
                board = _shrink_board(observation, dict(spec.get("board") or {}))
                operations[train] = {
                    "op": "switch_line",
                    "line": str(spec["line"]),
                    "board": board,
                }
            else:
                operations[train] = {"op": "delay"}
        return {"tool": "set_timetable", "tick": tick, "operations": operations}


class Map17NoBranchSwitch:
    """消融：不执行 ``switch_line``，因此 E/F 支线不可达。

    C→F 与 B→E 两组 OD 必然无法送达（6/10），tick 12 以
    DEADLINE_SERVICE_BELOW_80 终局；用来证明 ``switch_line`` 是主机制而非装饰。
    """

    name = "no_branch_switch"

    def reset(self) -> None:
        pass

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        tick = int(observation["tick"])
        positions = dict(observation["train_positions"])
        operations: dict[str, dict[str, Any]] = {}
        if tick == 0:
            for train, od in (
                ("T_A", "A_to_C"),
                ("T_C", "C_to_F"),
                ("T_D", "D_to_B"),
                ("T_F", "F_to_A"),
            ):
                board = _shrink_board(observation, {od: 2})
                operations[train] = {"op": "stop", "board": board}
        elif tick == 1:
            for train, destination in (
                ("T_A", "B"),
                ("T_C", "B"),
                ("T_D", "C"),
                ("T_F", "E"),
            ):
                operations[train] = {"op": "release", "to": destination}
        elif tick == 2:
            operations["T_A"] = {"op": "release", "to": "C"}
            operations["T_F"] = {"op": "release", "to": "B"}
            operations["T_C"] = {"op": "delay"}
            operations["T_D"] = {"op": "delay"}
        elif tick == 3:
            operations["T_D"] = {"op": "release", "to": "B"}
            operations["T_F"] = {"op": "release", "to": "A"}
        elif tick == 4:
            for train in ("T_A", "T_C", "T_D", "T_F"):
                operations[train] = {"op": "delay"}
        else:
            return {"tool": "set_timetable", "tick": tick, "operations": {}}
        for train, spec in list(operations.items()):
            if spec["op"] == "release":
                destination = str(spec["to"])
                if destination not in _MAP17_ADJACENCY.get(str(positions.get(train)), ()):
                    operations[train] = {"op": "delay"}
        return {"tool": "set_timetable", "tick": tick, "operations": operations}


# --------------------------------------------------------------------------- MAP-18
#: 邻接表由公开 ``topology`` 的三条线路顺序 + ``interchange_segments`` 推得。
_MAP18_ADJACENCY: dict[str, tuple[str, ...]] = {
    "R1": ("R2",),
    "R2": ("R1", "R3", "B2"),
    "R3": ("R2",),
    "B1": ("B2",),
    "B2": ("B1", "B3", "R2"),
    "B3": ("B2", "G2"),
    "G1": ("G2",),
    "G2": ("G1", "G3", "B3"),
    "G3": ("G2",),
}

#: 任务只能由固定列车完成；映射来自公开 ``task_passenger_counts``/窗口键。
_MAP18_TRAIN_TASK: dict[str, str] = {
    "T_R1": "TASK_R1_R2",
    "T_R2": "TASK_R2_R3",
    "T_R3": "TASK_R3_R2",
    "T_B": "TASK_B1_B3",
    "T_G": "TASK_G1_G3",
    "T_X": "TASK_R2_G2",
}

#: 主策略：遵守公开 ``published_dispatch_windows``，红线恢复留到封锁解除后。
_MAP18_TABLE: dict[int, dict[str, str]] = {
    0: {"T_B": "B2", "T_G": "G2"},
    1: {"T_B": "B3", "T_G": "G3"},
    4: {"T_X": "B2"},
    5: {"T_X": "B3", "T_R1": "R2"},
    6: {"T_X": "G2"},
    10: {"T_R2": "R3"},
    11: {"T_R3": "R2"},
}

#: 消融：无视 dispatch window，把全部任务压到封锁开始（tick 5）之前。
#: 同一 tick 一条边只能有一列车（``segment_capacity_per_tick``=1），因此
#: B2→B3 必须让 T_B 与 T_X 错开一个 tick。
_MAP18_FRONTLOAD_TABLE: dict[int, dict[str, str]] = {
    0: {"T_X": "B2", "T_B": "B2", "T_G": "G2"},
    1: {"T_B": "B3", "T_G": "G3"},
    2: {"T_X": "B3", "T_R3": "R2"},
    3: {"T_X": "G2", "T_R2": "R3"},
    4: {"T_R1": "R2"},
}


class Map18Heuristic:
    """故障传播：按公开窗口错峰，闭塞期间不动 R2–R3，重开后再交付红线任务。

    公开依据：``closed_segments``、``recovery_status``、``train_positions``、
    ``delivered_tasks``/``canceled_tasks``、``topology``、``tick``。12 行骨架是按公开
    ``published_dispatch_windows`` 手工排定的常量（运行时不再读取该字段）；不读取
    隐藏的故障窗口——作业时只用 ``closed_segments`` 判断当前是否仍封闭。
    alert 只说"下一 tick 可能封锁、区段与时长未定"，因此策略不能依赖告警定位区段。

    结果：12 个决策全部被接受，18/18 人送达，tick 12 以 SERVICE_COMPLETE 终局；
    ``recovery_delay`` = 6（红线恢复比封锁公开晚 6 tick）。
    """

    name = "public_heuristic"

    def reset(self) -> None:
        pass

    def _row(self, observation: dict[str, Any]) -> dict[str, str]:
        return _MAP18_TABLE.get(int(observation["tick"]), {})

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        return _map18_action(self, observation, history, self._row(observation))


class Map18IgnoreWindows:
    """消融：完全不看 dispatch window，把所有任务排在封锁窗口之前。

    这是本图的构造旁路证据：tick 5 之前 18/18 已送达，闭塞从未影响任何移动，
    因此 ``first_reroute_delay`` 与 ``recovery_delay`` 只能报 N/A，
    而服务率仍是 1.0、延误为 0 —— 指标层反而"奖励"了无视告警的策略。
    """

    name = "ignore_windows"

    def reset(self) -> None:
        pass

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        row = _MAP18_FRONTLOAD_TABLE.get(int(observation["tick"]), {})
        return _map18_action(self, observation, history, row)


def _map18_action(
    policy: Any,
    observation: dict[str, Any],
    history: list[dict[str, Any]],
    row: dict[str, str],
) -> Action:
    """把"列车→下一节点"的行渲染成 set_timetable，并做三重防御。

    - 已交付/已取消的任务不再移动（否则整行 COMPLETED_TRAIN_MOVED）；
    - 目标不在公开邻接表内时退化为 ``temporary_stop``；
    - 目标边属于当前 ``closed_segments`` 时同样等待。
    """

    del history, policy
    tick = int(observation["tick"])
    positions = dict(observation["train_positions"])
    delivered = set(observation.get("delivered_tasks") or [])
    canceled = set(observation.get("canceled_tasks") or [])
    closed = {
        frozenset(str(item).split("_"))
        for item in (observation.get("closed_segments") or [])
    }
    operations: dict[str, dict[str, Any]] = {}
    for train, destination in row.items():
        task = _MAP18_TRAIN_TASK.get(train)
        if task in delivered or task in canceled:
            continue
        origin = str(positions.get(train))
        if destination not in _MAP18_ADJACENCY.get(origin, ()):
            continue
        if frozenset((origin, destination)) in closed:
            operations[train] = {"op": "temporary_stop"}
            continue
        operations[train] = {"op": "release", "to": destination}
    return {"tool": "set_timetable", "tick": tick, "operations": operations}


HEURISTICS: dict[str, type[Any]] = {
    "MAP-16": Map16Heuristic,
    "MAP-17": Map17Heuristic,
    "MAP-18": Map18Heuristic,
}

ABLATIONS: dict[str, dict[str, type[Any]]] = {
    "MAP-16": {"no_siding": Map16NoSiding},
    "MAP-17": {"no_branch_switch": Map17NoBranchSwitch},
    "MAP-18": {"ignore_windows": Map18IgnoreWindows},
}

__all__ = [
    "ABLATIONS",
    "HEURISTICS",
    "Map16Heuristic",
    "Map16NoSiding",
    "Map17Heuristic",
    "Map17NoBranchSwitch",
    "Map18Heuristic",
    "Map18IgnoreWindows",
]
