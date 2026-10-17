"""MAP-17｜早高峰：B-C 共享瓶颈下的四车联合时刻表与多目标 Pareto 取舍。

本图与同世界另两图的机制差异：MAP-16 是两列车固定起终点的 makespan/死锁题；MAP-18 有
闭塞故障与在线恢复；本图没有故障与随机延误，主机制是同一张 10 人 OD 客流表上“服务率、
乘客等待、能耗/人、最后交付 tick”四个目标互不支配的联合调度。每个 tick 提交一行
``set_timetable{tick, operations}``，四列车同步执行各自的一个操作。

规则要点：
- 环线 A-B-C-D-A + 支线 B-E-F，每段 1 tick；B-C 是唯一双向合并容量 1 的区段；每站至多
  2 列车；每车 3 座；12 个结算 tick；能耗上限 18。
- 操作：``release{to}`` 耗 1 能量并占用本 tick 区段；``stop{board}`` 停 1 tick 装载；
  ``switch_line{line, board}`` 仅在 B、停 1 tick、设定离站线路并装载；``delay`` 原地等。
- ``board`` 是 ``{OD: 人数}`` 清单，只允许装当前站始发的 OD；目的地到达时自动下车。
- B 站换乘等待：本图不实现中途下车换乘（与设计文档的未决项一致），B 站队列的等待
  （例如 B→E 乘客等待支线列车）完整计入 ``passenger_wait_person_ticks``；每次 ``stop`` /
  ``switch_line`` 前，tick 开始时仍在站台的所有人都累计 1 人·tick。
- 预检失败（tick 不符、区段冲突、站台超容、非法登车清单、能耗越界）整行不提交：
  位置、能耗、等待与 tick 全部不变。``SHARED_SEGMENT_CONFLICT`` 对同向双车同样生效。
- tick 12 结算：送达 ≥ 8/10 成功 ``DEMAND_THRESHOLD_MET``，否则
  ``DEADLINE_SERVICE_BELOW_80``。

指标口径（与 V7 卡片一致）：
- ``service_rate``：实际在目的站下车人数 / 10（按 OD 客流权重，不按上车数）。
- ``cumulative_wait_person_ticks``：逐 tick 在站台等待的人数累加；换乘/支线等待同样计入。
- ``energy_per_passenger``：``energy_used / delivered``；0 人送达时为 N/A（``None``）。
- ``overcapacity_events``：``PLATFORM_CAPACITY`` + ``SHARED_SEGMENT_CONFLICT`` 被拒次数。
- Pareto 向量（服务损失、等待/120、能耗/18、最后交付/12）只进 ``judge_state``，不注册为
  额外 metric，也不向玩家给出参照前沿。
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action, V8Status

STATIONS = ("A", "B", "C", "D", "E", "F")
ADJACENCY: dict[str, tuple[str, ...]] = {
    "A": ("B", "D"),
    "B": ("A", "C", "E"),
    "C": ("B", "D"),
    "D": ("C", "A"),
    "E": ("B", "F"),
    "F": ("E",),
}
#: OD -> (origin, destination, weight); weights sum to 10.
DEMAND: dict[str, tuple[str, str, int]] = {
    "A_to_C": ("A", "C", 2),
    "B_to_E": ("B", "E", 2),
    "C_to_F": ("C", "F", 2),
    "D_to_B": ("D", "B", 2),
    "F_to_A": ("F", "A", 2),
}
TRAIN_IDS = ("T_A", "T_C", "T_D", "T_F")
INITIAL_POSITIONS = {"T_A": "A", "T_C": "C", "T_D": "D", "T_F": "F"}
HORIZON = 12
ENERGY_BUDGET = 18
SEATS_PER_TRAIN = 3
BERTHS_PER_STATION = 2
SERVICE_THRESHOLD = 8
TOTAL_DEMAND = sum(spec[2] for spec in DEMAND.values())
BC_EDGE = frozenset({"B", "C"})


class Map17Environment(MapEnvironment):
    map_id = "MAP-17"
    title = "早高峰"
    world = "subway"
    level = "中等"
    SHAPES: dict[str, set[frozenset[str]]] = {
        "set_timetable": {frozenset({"tool", "tick", "operations"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "ticks_remaining",
            "topology",
            "demand_matrix",
            "train_positions",
            "station_train_counts",
            "train_seat_capacity",
            "onboard_passengers",
            "waiting_demand",
            "delivered_by_od",
            "energy_consumed",
            "energy_remaining",
            "passenger_wait_person_ticks",
            "last_delivery_tick",
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.positions = dict(INITIAL_POSITIONS)
        self.onboard: dict[str, dict[str, int]] = {train: {} for train in TRAIN_IDS}
        self.waiting = {od: spec[2] for od, spec in DEMAND.items()}
        self.delivered = {od: 0 for od in DEMAND}
        self.energy_used = 0
        self.wait_person_ticks = 0
        self.last_delivery_tick = 0
        self.line = {train: "ring" for train in TRAIN_IDS}
        self._rejected = False

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        counts = Counter(self.positions.values())
        return {
            "tick": self.tick_count,
            "ticks_remaining": max(0, HORIZON - self.tick_count),
            "topology": {
                "ring_nodes": ["A", "B", "C", "D"],
                "ring_segments": ["AB", "BC", "CD", "DA"],
                "branch_nodes": ["B", "E", "F"],
                "branch_segments": ["BE", "EF"],
                "shared_bidirectional_segment": "BC",
                "segment_capacity_per_tick": 1,
                "station_train_berth_capacity": BERTHS_PER_STATION,
            },
            "demand_matrix": {od: spec[2] for od, spec in DEMAND.items()},
            "train_positions": dict(self.positions),
            "station_train_counts": {
                station: counts.get(station, 0) for station in STATIONS
            },
            "train_seat_capacity": {train: SEATS_PER_TRAIN for train in TRAIN_IDS},
            "onboard_passengers": {
                train: {
                    od: count
                    for od, count in sorted(self.onboard[train].items())
                    if count > 0
                }
                for train in TRAIN_IDS
            },
            "waiting_demand": {od: self.waiting[od] for od in DEMAND},
            "delivered_by_od": dict(self.delivered),
            "energy_consumed": self.energy_used,
            "energy_remaining": ENERGY_BUDGET - self.energy_used,
            "passenger_wait_person_ticks": self.wait_person_ticks,
            "last_delivery_tick": self.last_delivery_tick,
            "goal": "在 12 tick 内运送至少 8/10 名乘客，并自行权衡服务率、等待与能耗。",
        }

    # ------------------------------------------------------------------ rules
    @staticmethod
    def _parse_manifest(manifest: Any) -> dict[str, int] | None:
        if manifest is None:
            return {}
        if not isinstance(manifest, dict):
            return None
        parsed: dict[str, int] = {}
        for od, count in manifest.items():
            if not isinstance(od, str) or od not in DEMAND:
                return None
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                return None
            parsed[od] = count
        return parsed

    def _parse_operations(
        self, operations: dict[str, dict[str, Any]]
    ) -> tuple[dict[str, str], dict[str, dict[str, int]], dict[str, str], str | None]:
        moves: dict[str, str] = {}
        boards: dict[str, dict[str, int]] = {}
        line_changes: dict[str, str] = {}
        for train in sorted(operations):
            if train not in self.positions:
                return {}, {}, {}, "UNKNOWN_TRAIN"
            op_data = operations[train]
            if not isinstance(op_data, dict):
                return {}, {}, {}, "INVALID_OPERATION"
            op = op_data.get("op")
            if op == "release":
                destination = op_data.get("to")
                if (
                    not isinstance(destination, str)
                    or destination not in ADJACENCY[self.positions[train]]
                ):
                    return {}, {}, {}, "INVALID_LINK"
                if (
                    self.positions[train] == "B"
                    and destination == "E"
                    and self.line[train] != "branch"
                ):
                    return {}, {}, {}, "INVALID_LINE_SWITCH"
                moves[train] = destination
            elif op == "stop":
                manifest = self._parse_manifest(op_data.get("board", {}))
                if manifest is None:
                    return {}, {}, {}, "INVALID_BOARDING_MANIFEST"
                boards[train] = manifest
            elif op == "switch_line":
                if self.positions[train] != "B":
                    return {}, {}, {}, "INVALID_LINE_SWITCH"
                line = op_data.get("line")
                if line not in ("ring", "branch"):
                    return {}, {}, {}, "INVALID_LINE_SWITCH"
                manifest = self._parse_manifest(op_data.get("board", {}))
                if manifest is None:
                    return {}, {}, {}, "INVALID_BOARDING_MANIFEST"
                boards[train] = manifest
                line_changes[train] = str(line)
            elif op == "delay":
                continue
            else:
                return {}, {}, {}, "INVALID_OPERATION"
        return moves, boards, line_changes, None

    def _reject(self, code: str) -> str:
        self._rejected = True
        self._count(code)
        return code

    def _apply(self, action: V8Action) -> str:
        self._rejected = False
        if action.tool != "set_timetable":
            return self._reject("ACTION_NOT_ALLOWED")
        if action.tick is None or action.operations is None:
            return self._reject("INVALID_ACTION_SCHEMA")
        if action.tick != self.tick_count:
            return self._reject("TICK_MISMATCH")
        moves, boards, line_changes, error = self._parse_operations(action.operations)
        if error is not None:
            return self._reject(error)

        bc_moves = [
            train
            for train, destination in moves.items()
            if frozenset((self.positions[train], destination)) == BC_EDGE
        ]
        if len(bc_moves) > 1:
            return self._reject("SHARED_SEGMENT_CONFLICT")
        if self.energy_used + len(moves) > ENERGY_BUDGET:
            return self._reject("ENERGY_BUDGET_EXCEEDED")

        before = dict(self.positions)
        next_positions = dict(self.positions)
        for train, destination in moves.items():
            next_positions[train] = destination
        berths = Counter(next_positions.values())
        if max(berths.values(), default=0) > BERTHS_PER_STATION:
            return self._reject("PLATFORM_CAPACITY")

        wait_left = dict(self.waiting)
        additions_by_train: dict[str, dict[str, int]] = {}
        for train in sorted(boards):
            station = next_positions[train]
            total = sum(self.onboard[train].values())
            additions: dict[str, int] = {}
            for od, count in boards[train].items():
                if count == 0:
                    continue
                if DEMAND[od][0] != station:
                    return self._reject("INVALID_BOARDING_MANIFEST")
                if wait_left[od] < count:
                    return self._reject("INVALID_BOARDING_MANIFEST")
                total += count
                if total > SEATS_PER_TRAIN:
                    return self._reject("INVALID_BOARDING_MANIFEST")
                wait_left[od] -= count
                additions[od] = count
            additions_by_train[train] = additions

        # Commit the whole row atomically.
        self.wait_person_ticks += sum(self.waiting.values())
        for train, destination in moves.items():
            self.positions[train] = destination
        arrival_tick = self.tick_count + 1
        for train, destination in moves.items():
            group = self.onboard[train]
            for od in list(group):
                if DEMAND[od][1] == destination:
                    self.delivered[od] += group[od]
                    del group[od]
                    self.last_delivery_tick = max(
                        self.last_delivery_tick, arrival_tick
                    )
        for train, additions in additions_by_train.items():
            for od, count in additions.items():
                self.onboard[train][od] = self.onboard[train].get(od, 0) + count
        self.waiting = wait_left
        for train, line in line_changes.items():
            self.line[train] = line
        for train in moves:
            if before[train] == "B":
                self.line[train] = "ring"
        self.energy_used += len(moves)
        return "TICK_COMMITTED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return 0 if self._rejected else 1

    def _after_tick(self) -> None:
        if self.status is not V8Status.RUNNING:
            return
        if self._rejected or self.tick_count < HORIZON:
            return
        if self.delivered_total >= SERVICE_THRESHOLD:
            self._succeed("DEMAND_THRESHOLD_MET")
        else:
            self._fail("DEADLINE_SERVICE_BELOW_80")

    # ------------------------------------------------------------------ judge
    @property
    def delivered_total(self) -> int:
        return sum(self.delivered.values())

    def judge_state(self) -> dict[str, Any]:
        delivered = self.delivered_total
        return {
            "tick": self.tick_count,
            "positions": dict(sorted(self.positions.items())),
            "line": dict(sorted(self.line.items())),
            "onboard": {
                train: dict(sorted(self.onboard[train].items()))
                for train in TRAIN_IDS
            },
            "waiting": dict(sorted(self.waiting.items())),
            "delivered": dict(sorted(self.delivered.items())),
            "delivered_total": delivered,
            "energy_used": self.energy_used,
            "wait_person_ticks": self.wait_person_ticks,
            "last_delivery_tick": self.last_delivery_tick,
            "counters": dict(sorted(self.counters.items())),
            "pareto_vector": {
                "service_loss": 1 - delivered / TOTAL_DEMAND,
                "wait_normalized": self.wait_person_ticks / 120,
                "energy_normalized": self.energy_used / ENERGY_BUDGET,
                "last_delivery_normalized": self.last_delivery_tick / HORIZON,
            },
        }

    def metrics(self) -> dict[str, Any]:
        delivered = self.delivered_total
        return {
            "map17.service_rate": {
                "numerator": delivered,
                "denominator": TOTAL_DEMAND,
            },
            "map17.cumulative_wait_person_ticks": self.wait_person_ticks,
            "map17.energy_per_passenger": (
                self.energy_used / delivered if delivered else None
            ),
            "map17.overcapacity_events": self.counters.get(
                "PLATFORM_CAPACITY", 0
            )
            + self.counters.get("SHARED_SEGMENT_CONFLICT", 0),
        }


ORACLE_CASES: tuple[dict[str, Any], ...] = (
    {
        "trace_id": "time_priority",
        "seed": 0,
        "actions": [
            {
                "tool": "set_timetable",
                "tick": 0,
                "operations": {
                    "T_A": {"op": "stop", "board": {"A_to_C": 2}},
                    "T_C": {"op": "stop", "board": {"C_to_F": 2}},
                    "T_D": {"op": "stop", "board": {"D_to_B": 2}},
                    "T_F": {"op": "stop", "board": {"F_to_A": 2}},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 1,
                "operations": {
                    "T_A": {"op": "release", "to": "B"},
                    "T_C": {"op": "release", "to": "B"},
                    "T_D": {"op": "release", "to": "C"},
                    "T_F": {"op": "release", "to": "E"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 2,
                "operations": {
                    "T_A": {"op": "release", "to": "C"},
                    "T_C": {
                        "op": "switch_line",
                        "line": "branch",
                        "board": {"B_to_E": 1},
                    },
                    "T_D": {"op": "delay"},
                    "T_F": {"op": "release", "to": "B"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 3,
                "operations": {
                    "T_C": {"op": "release", "to": "E"},
                    "T_D": {"op": "release", "to": "B"},
                    "T_F": {"op": "release", "to": "A"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 4,
                "operations": {
                    "T_C": {"op": "release", "to": "F"},
                    "T_D": {
                        "op": "switch_line",
                        "line": "branch",
                        "board": {"B_to_E": 1},
                    },
                },
            },
            {
                "tool": "set_timetable",
                "tick": 5,
                "operations": {"T_D": {"op": "release", "to": "E"}},
            },
            {"tool": "set_timetable", "tick": 6, "operations": {}},
            {"tool": "set_timetable", "tick": 7, "operations": {}},
            {"tool": "set_timetable", "tick": 8, "operations": {}},
            {"tool": "set_timetable", "tick": 9, "operations": {}},
            {"tool": "set_timetable", "tick": 10, "operations": {}},
            {"tool": "set_timetable", "tick": 11, "operations": {}},
        ],
        "expect_success": True,
    },
    {
        "trace_id": "energy_priority",
        "seed": 0,
        "actions": [
            {
                "tool": "set_timetable",
                "tick": 0,
                "operations": {
                    "T_A": {"op": "stop", "board": {"A_to_C": 2}},
                    "T_C": {"op": "stop", "board": {"C_to_F": 2}},
                    "T_D": {"op": "stop", "board": {"D_to_B": 2}},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 1,
                "operations": {
                    "T_A": {"op": "release", "to": "B"},
                    "T_C": {"op": "release", "to": "B"},
                    "T_D": {"op": "release", "to": "C"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 2,
                "operations": {
                    "T_A": {"op": "release", "to": "C"},
                    "T_C": {
                        "op": "switch_line",
                        "line": "branch",
                        "board": {"B_to_E": 1},
                    },
                    "T_D": {"op": "delay"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 3,
                "operations": {
                    "T_C": {"op": "release", "to": "E"},
                    "T_D": {"op": "release", "to": "B"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 4,
                "operations": {
                    "T_C": {"op": "release", "to": "F"},
                    "T_D": {
                        "op": "switch_line",
                        "line": "branch",
                        "board": {"B_to_E": 1},
                    },
                },
            },
            {
                "tool": "set_timetable",
                "tick": 5,
                "operations": {"T_D": {"op": "release", "to": "E"}},
            },
            {"tool": "set_timetable", "tick": 6, "operations": {}},
            {"tool": "set_timetable", "tick": 7, "operations": {}},
            {"tool": "set_timetable", "tick": 8, "operations": {}},
            {"tool": "set_timetable", "tick": 9, "operations": {}},
            {"tool": "set_timetable", "tick": 10, "operations": {}},
            {"tool": "set_timetable", "tick": 11, "operations": {}},
        ],
        "expect_success": True,
    },
)


FIXTURES = (
    {
        "name": "time_priority_vector",
        "seed": 0,
        "actions": list(ORACLE_CASES[0]["actions"]),
        "expect": {
            "map17.service_rate": 1.0,
            "map17.cumulative_wait_person_ticks": 16,
            "map17.energy_per_passenger": 1.1,
            "map17.overcapacity_events": 0,
        },
    },
    {
        "name": "shared_bc_reverse_swap_is_rejected",
        "seed": 0,
        "actions": [
            {
                "tool": "set_timetable",
                "tick": 0,
                "operations": {
                    "T_A": {"op": "stop", "board": {"A_to_C": 2}},
                    "T_C": {"op": "stop", "board": {"C_to_F": 2}},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 1,
                "operations": {
                    "T_A": {"op": "release", "to": "B"},
                    "T_C": {"op": "delay"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 2,
                "operations": {
                    "T_A": {"op": "release", "to": "C"},
                    "T_C": {"op": "release", "to": "B"},
                },
            },
        ],
        "expect": {
            "map17.service_rate": 0.0,
            "map17.cumulative_wait_person_ticks": 16,
            "map17.energy_per_passenger": None,
            "map17.overcapacity_events": 1,
        },
    },
    {
        "name": "third_train_overfills_b_platform",
        "seed": 0,
        "actions": [
            {
                "tool": "set_timetable",
                "tick": 0,
                "operations": {
                    "T_A": {"op": "stop", "board": {"A_to_C": 2}},
                    "T_C": {"op": "stop", "board": {"C_to_F": 2}},
                    "T_F": {"op": "stop", "board": {"F_to_A": 2}},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 1,
                "operations": {
                    "T_A": {"op": "release", "to": "B"},
                    "T_C": {"op": "release", "to": "B"},
                    "T_F": {"op": "release", "to": "E"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 2,
                "operations": {
                    "T_A": {"op": "delay"},
                    "T_C": {
                        "op": "switch_line",
                        "line": "branch",
                        "board": {"B_to_E": 1},
                    },
                    "T_F": {"op": "release", "to": "B"},
                },
            },
        ],
        "expect": {
            "map17.service_rate": 0.0,
            "map17.cumulative_wait_person_ticks": 14,
            "map17.energy_per_passenger": None,
            "map17.overcapacity_events": 1,
        },
    },
    {
        "name": "energy_budget_rejection_keeps_clock_and_wait",
        "seed": 0,
        "actions": [
            {"tool": "set_timetable", "tick": 0, "operations": {}},
            {
                "tool": "set_timetable",
                "tick": 1,
                "operations": {
                    "T_A": {"op": "release", "to": "B"},
                    "T_C": {"op": "release", "to": "B"},
                    "T_D": {"op": "release", "to": "C"},
                    "T_F": {"op": "release", "to": "E"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 2,
                "operations": {
                    "T_A": {"op": "release", "to": "A"},
                    "T_C": {"op": "release", "to": "C"},
                    "T_D": {"op": "release", "to": "D"},
                    "T_F": {"op": "release", "to": "F"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 3,
                "operations": {
                    "T_A": {"op": "release", "to": "B"},
                    "T_C": {"op": "release", "to": "B"},
                    "T_D": {"op": "release", "to": "C"},
                    "T_F": {"op": "release", "to": "E"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 4,
                "operations": {
                    "T_A": {"op": "release", "to": "A"},
                    "T_C": {"op": "release", "to": "C"},
                    "T_D": {"op": "release", "to": "D"},
                    "T_F": {"op": "release", "to": "F"},
                },
            },
            {
                "tool": "set_timetable",
                "tick": 5,
                "operations": {
                    "T_A": {"op": "release", "to": "B"},
                    "T_C": {"op": "release", "to": "B"},
                    "T_D": {"op": "release", "to": "C"},
                    "T_F": {"op": "release", "to": "E"},
                },
            },
        ],
        "expect": {
            "map17.service_rate": 0.0,
            "map17.cumulative_wait_person_ticks": 50,
            "map17.energy_per_passenger": None,
            "map17.overcapacity_events": 0,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map17Environment"]
