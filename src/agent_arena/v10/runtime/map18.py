"""MAP-18 V10｜故障传播：故障必然发生在服务完成前的在线恢复调度（DCR-V10-02）。

与 V4/V8 的差异（规则变更，见 ``docs/v10/dcr/DCR-V10-02.md``）：

- **时钟分离**：``current_tick`` 是物理时钟（每个被提交的时刻表行 +1，到
  ``horizon`` 结算）；``tick_count`` 是动作预算（任何决策含被拒行都 +1，上限
  ``horizon + ACTION_SLACK``）。V4 ``step_limit = min(step_limit, horizon)`` 让一次被拒
  就使 horizon 永远到不了，V10 不再夹紧；
- **发车窗口强制**：任务在 ``release_tick`` 前离开起点 → 整行 ``DISPATCH_WINDOW_VIOLATION``
  （物理时钟不前进，消耗动作预算）。因此不能把全部任务抢跑到故障前；
- **故障随 seed 变化**：区段、开始时刻与时长按预登记变体表变化；每个变体至少有一项
  任务的路线穿过故障区段且最早可通过时刻落在故障窗口内（``fault_unavoidable``）；
- 成功门槛 13/18、到 horizon 结算、交付后列车不可再动、取消不可逆、容量规则全部公开；
  故障区段与时长仍隐藏，只在封闭期间以 ``closed_segments`` 公开；
- 任务全部交付/取消后立即结算，不必空转到 horizon；
- ``turnback`` 从 V10 动作集移除：被取消的空车可直接 ``release`` 调位。
"""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass
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

ADJACENCY: dict[str, tuple[str, ...]] = {
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
INITIAL_POSITIONS = {
    "T_R1": "R1",
    "T_R2": "R2",
    "T_R3": "R3",
    "T_B": "B1",
    "T_G": "G1",
    "T_X": "R2",
}
TRAIN_TASK = {
    "T_R1": "TASK_R1_R2",
    "T_R2": "TASK_R2_R3",
    "T_R3": "TASK_R3_R2",
    "T_B": "TASK_B1_B3",
    "T_G": "TASK_G1_G3",
    "T_X": "TASK_R2_G2",
}
ROUTES: dict[str, tuple[str, ...]] = {
    "TASK_R1_R2": ("R1", "R2"),
    "TASK_R2_R3": ("R2", "R3"),
    "TASK_R3_R2": ("R3", "R2"),
    "TASK_B1_B3": ("B1", "B2", "B3"),
    "TASK_G1_G3": ("G1", "G2", "G3"),
    "TASK_R2_G2": ("R2", "B2", "B3", "G2"),
}
PASSENGERS = 3
TOTAL_DEMAND = PASSENGERS * len(ROUTES)
SUCCESS_THRESHOLD = 13
STATION_CAPACITY = 2
ACTION_SLACK = 8
RELEASE_TICKS = {
    "TASK_B1_B3": 0,
    "TASK_G1_G3": 0,
    "TASK_R2_G2": 4,
    "TASK_R1_R2": 5,
    "TASK_R2_R3": 5,
    "TASK_R3_R2": 6,
}
TOPOLOGY = {
    "red_nodes": ("R1", "R2", "R3"),
    "blue_nodes": ("B1", "B2", "B3"),
    "green_nodes": ("G1", "G2", "G3"),
    "interchange_segments": ("R2_B2", "B3_G2"),
    "segment_capacity_per_tick": 1,
    "station_train_berth_capacity": STATION_CAPACITY,
}


def edge_key(a: str, b: str) -> str:
    return "_".join(sorted((a, b)))


@dataclass(frozen=True)
class FaultVariant:
    edge: tuple[str, str]
    start: int
    duration: int
    horizon: int

    @property
    def end(self) -> int:
        return self.start + self.duration


#: 预登记变体：区段、开始、时长、物理 horizon。seed 0 复现 V4 的 R2-R3 [5,10) / 12。
#: 恢复难点 cohort（预登记）：
#: 0 R2-R3 重开后对向争用（需错峰）；1 R2-B2 短封闭使 R2 泊位被困车占满（需让 T_R3 等待）；
#: 2 B2-B3 重开后同向争用（需排队）；3 R2-B2 长封闭（T_X 已不可能按时送达，需取消并调空车
#: 让出泊位）；4 B3-G2 只需等待的对照。
VARIANTS: dict[int, FaultVariant] = {
    0: FaultVariant(("R2", "R3"), 5, 5, 12),
    1: FaultVariant(("B2", "R2"), 4, 4, 12),
    2: FaultVariant(("B2", "B3"), 1, 5, 12),
    3: FaultVariant(("B2", "R2"), 4, 8, 12),
    4: FaultVariant(("B3", "G2"), 5, 4, 12),
}


def planned_arrival(task_id: str) -> int:
    return RELEASE_TICKS[task_id] + len(ROUTES[task_id]) - 1


def affected_tasks(variant: FaultVariant) -> tuple[str, ...]:
    """路线穿过故障区段、且最早通过该区段的时刻落在故障窗口内的任务。"""

    fault = edge_key(*variant.edge)
    affected = []
    for task_id, route in ROUTES.items():
        for hop, (a, b) in enumerate(zip(route, route[1:], strict=False)):
            if edge_key(a, b) != fault:
                continue
            earliest = RELEASE_TICKS[task_id] + hop
            if variant.start <= earliest < variant.end:
                affected.append(task_id)
    return tuple(sorted(affected))


class Map18V10Environment(V10Map):
    map_id = "MAP-18"
    title = "故障传播"
    world = "subway"
    level = "困难"
    RULE_VERSION = "v10.map18.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "set_timetable": {frozenset({"tool", "tick", "operations"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "horizon",
            "ticks_remaining",
            "action_budget_remaining",
            "topology",
            "task_routes",
            "train_task",
            "train_positions",
            "station_berths",
            "task_status",
            "published_dispatch_windows",
            "delivered_passengers",
            "canceled_passengers",
            "success_threshold_passengers",
            "closed_segments",
            "alert_message_if_any",
            "recovery_status",
            "goal",
        }
    )
    PRIMARY_METRIC = "map18.v10.service_rate"
    METRIC_SPECS = (
        MetricSpec(
            "map18.v10.service_rate",
            "primary",
            "higher",
            "delivered_passengers / 18",
            "18（取消不删分母）",
            censored_rule="部分送达在截尾/失败时仍 VALID",
        ),
        MetricSpec(
            "map18.v10.recovery_delay_ticks",
            "primary",
            "lower",
            "max(受影响任务送达/取消 tick) - fault_start",
            "受影响任务全部了结（1）",
            censored_rule=(
                "截止或预算截尾时仍有受影响任务未了结 → CENSORED；冲突终局 → NOT_APPLICABLE"
            ),
            unit="ticks",
            valid_range=(-14.0, 20.0),
        ),
        MetricSpec(
            "map18.v10.conflict_terminal",
            "guardrail",
            "lower",
            "终局原因 ∈ {HEAD_ON_COLLISION, SEGMENT_CAPACITY, STATION_CAPACITY_EXCEEDED}",
            "1",
        ),
        MetricSpec(
            "map18.v10.closed_entry_attempts",
            "guardrail",
            "lower",
            "count(release/detour 进入封闭区段)",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map18.v10.plan_changes",
            "secondary",
            "none",
            "故障开始后，受影响列车的操作偏离公开无故障时刻表的次数（含暂停、取消、调位）",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map18.v10.window_violations",
            "guardrail",
            "lower",
            "count(DISPATCH_WINDOW_VIOLATION 行)",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map18.v10.rejected_rows",
            "guardrail",
            "lower",
            "count(被拒、物理时钟未前进的决策)",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map18.v10.delay_person_ticks",
            "secondary",
            "lower",
            "Σ 3 × max(实际到达 - 计划到达, 0)（仅送达任务）",
            "—",
            unit="person_ticks",
            valid_range=(0.0, 300.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int | None = None) -> None:
        variant = VARIANTS.get(seed)
        if variant is None:
            raise ValueError(f"MAP-18 V10 未预登记环境 seed {seed}")
        budget = variant.horizon + ACTION_SLACK if step_limit is None else step_limit
        super().__init__(seed=seed, step_limit=budget)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.fault_edge_key = edge_key(*self.variant.edge)
        self.affected = affected_tasks(self.variant)
        self.horizon = self.variant.horizon
        self.alert_tick = self.variant.start - 1
        self.positions = dict(INITIAL_POSITIONS)
        self.task_status = {task: "pending" for task in ROUTES}
        self.progress = {task: 0 for task in ROUTES}
        self.current_tick = 0
        self.delivered = 0
        self.canceled = 0
        self.delay_person_ticks = 0
        self.resolved_tick: dict[str, int] = {}
        self.closed_entry_attempts = 0
        self.window_violations = 0
        self.rejected_rows = 0
        self.plan_changes = 0
        self.last_mode: dict[str, str] = {}
        self.fault_observed = False
        self.pending_affected_at_fault: tuple[str, ...] = ()

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "horizon": self.horizon,
            "action_budget": self.step_limit,
            "alert_tick": self.alert_tick,
            "release_ticks": dict(RELEASE_TICKS),
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "fault_edge": self.fault_edge_key,
            "fault_start": self.variant.start,
            "fault_duration": self.variant.duration,
            "affected_tasks": list(self.affected),
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "每个决策提交当前 tick 的一整行时刻表：set_timetable(tick=当前 tick, operations)。"
            "operations 只列需要动作的列车；未列出的列车原地等待。被提交的行使物理 tick +1。",
            "op ∈ release(to)|detour(to)：沿一条相邻区段移动一站（detour 与 release 等价，"
            "用于跨线联络段）；temporary_stop：原地等待；cancel_service(task_id)：列车在起点时"
            "取消本车任务，3 人计入服务损失且不可撤销，空车之后可用 release 调位。",
            "每项任务只能由 train_task 指定的列车沿 task_routes 的路线完成；列车在 release_tick "
            "之前离开起点 → 整行被拒 DISPATCH_WINDOW_VIOLATION（tick 不前进，消耗动作预算）。",
            "每个区段每 tick 最多 1 列车（双向合计）；每站最多 2 列车（含已交付停靠的车）。"
            "相向对穿 HEAD_ON_COLLISION、同段双车 SEGMENT_CAPACITY、站台超员 "
            "STATION_CAPACITY_EXCEEDED 都会立即终局。",
            "已交付的列车不能再移动（整行被拒 COMPLETED_TRAIN_MOVED）。非法相邻、未知列车、"
            "tick 不符等也整行被拒，tick 不前进但消耗动作预算。",
            "运行期间可能有一个区段临时封闭；区段与时长事先未知，封闭期间出现在 closed_segments。"
            "进入封闭区段的列车返回 TRACK_CLOSED 并原地等待，同行其他操作照常结算。",
            f"到 horizon 结算：送达 ≥ {SUCCESS_THRESHOLD}/{TOTAL_DEMAND} 人为成功；所有任务都已"
            "交付或取消时提前结算。动作预算用尽仍未结算即截尾。",
        )

    # ------------------------------------------------------------------ public
    def _closed_now(self) -> bool:
        return self.variant.start <= self.current_tick < self.variant.end

    def _public(self) -> dict[str, Any]:
        alert = None
        if self.current_tick == self.alert_tick:
            alert = {
                "id": "NETWORK_DISRUPTION_WATCH",
                "message": "下一 tick 可能有一个区段临时封闭；区段与时长未知。",
            }
        if self._closed_now():
            recovery = "section_closed"
        elif self.current_tick >= self.variant.end:
            recovery = "reopened"
        else:
            recovery = "normal"
        return {
            "tick": self.current_tick,
            "horizon": self.horizon,
            "ticks_remaining": self.horizon - self.current_tick,
            "action_budget_remaining": self.step_limit - self.tick_count,
            "topology": TOPOLOGY,
            "task_routes": {task: list(route) for task, route in ROUTES.items()},
            "train_task": dict(TRAIN_TASK),
            "train_positions": dict(self.positions),
            "station_berths": dict(sorted(Counter(self.positions.values()).items())),
            "task_status": dict(self.task_status),
            "published_dispatch_windows": {
                task: {
                    "release_tick": RELEASE_TICKS[task],
                    "planned_arrival_tick": planned_arrival(task),
                }
                for task in ROUTES
            },
            "delivered_passengers": self.delivered,
            "canceled_passengers": self.canceled,
            "success_threshold_passengers": SUCCESS_THRESHOLD,
            "closed_segments": [self.fault_edge_key] if self._closed_now() else [],
            "alert_message_if_any": alert,
            "recovery_status": recovery,
            "goal": (
                f"在 horizon 前送达至少 {SUCCESS_THRESHOLD}/{TOTAL_DEMAND} 名乘客，"
                "并在区段封闭时安全恢复服务。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _invalid_action(self) -> str:
        return self._reject("INVALID_ACTION_SCHEMA")

    def _reject(self, reason: str) -> str:
        self.rejected_rows += 1
        if reason.startswith("DISPATCH_WINDOW_VIOLATION"):
            self.window_violations += 1
        return reason

    def _next_hop(self, task_id: str) -> str | None:
        route = ROUTES[task_id]
        index = self.progress[task_id]
        return route[index + 1] if index + 1 < len(route) else None

    def _apply(self, action: V8Action) -> str:
        if action.tick != self.current_tick:
            return self._reject("TICK_MISMATCH")
        operations = action.operations or {}
        if any(train not in self.positions for train in operations):
            return self._reject("UNKNOWN_TRAIN")
        moves: dict[str, tuple[str, str]] = {}
        closed_trains: list[str] = []
        cancels: list[str] = []
        for train, op_data in sorted(operations.items()):
            if not isinstance(op_data, dict):
                return self._reject("INVALID_OPERATION")
            op = op_data.get("op")
            task_id = TRAIN_TASK[train]
            state = self.task_status[task_id]
            current = self.positions[train]
            if op in {"release", "detour"}:
                if set(op_data) != {"op", "to"} or not isinstance(op_data.get("to"), str):
                    return self._reject("INVALID_OPERATION")
                destination = op_data["to"]
                if destination not in ADJACENCY[current]:
                    return self._reject("INVALID_LINK")
                if state == "delivered":
                    return self._reject("COMPLETED_TRAIN_MOVED")
                if state == "pending":
                    if destination != self._next_hop(task_id):
                        return self._reject("OFF_ROUTE")
                    if self.progress[task_id] == 0 and self.current_tick < RELEASE_TICKS[task_id]:
                        return self._reject(f"DISPATCH_WINDOW_VIOLATION:{train}")
                if self._closed_now() and edge_key(current, destination) == self.fault_edge_key:
                    closed_trains.append(train)
                    continue
                moves[train] = (current, destination)
            elif op == "temporary_stop":
                if set(op_data) != {"op"}:
                    return self._reject("INVALID_OPERATION")
            elif op == "cancel_service":
                if set(op_data) != {"op", "task_id"}:
                    return self._reject("INVALID_OPERATION")
                if (
                    op_data.get("task_id") != task_id
                    or state != "pending"
                    or self.progress[task_id] != 0
                ):
                    return self._reject("INVALID_CANCELLATION")
                cancels.append(task_id)
            else:
                return self._reject("INVALID_OPERATION")

        owners: dict[str, str] = {}
        for train, (origin, destination) in sorted(moves.items()):
            key = edge_key(origin, destination)
            if key in owners:
                other = owners[key]
                reason = (
                    "HEAD_ON_COLLISION"
                    if self.positions[other] == destination
                    else "SEGMENT_CAPACITY"
                )
                self._fail(reason)
                return reason
            owners[key] = train
        next_positions = dict(self.positions)
        for train, (_, destination) in moves.items():
            next_positions[train] = destination
        if max(Counter(next_positions.values()).values(), default=0) > STATION_CAPACITY:
            self._fail("STATION_CAPACITY_EXCEEDED")
            return "STATION_CAPACITY_EXCEEDED"

        self.closed_entry_attempts += len(closed_trains)
        self._count_plan_changes(moves, closed_trains, cancels)
        if self._closed_now():
            if not self.fault_observed:
                self.fault_observed = True
                self.pending_affected_at_fault = tuple(
                    task for task in self.affected if self.task_status[task] == "pending"
                )
        self.positions = next_positions
        for task_id in cancels:
            self.task_status[task_id] = "canceled"
            self.canceled += PASSENGERS
            self.resolved_tick[task_id] = self.current_tick
        arrival = self.current_tick + 1
        for train in moves:
            task_id = TRAIN_TASK[train]
            if self.task_status[task_id] != "pending":
                continue
            self.progress[task_id] += 1
            if self.progress[task_id] == len(ROUTES[task_id]) - 1:
                self.task_status[task_id] = "delivered"
                self.delivered += PASSENGERS
                self.resolved_tick[task_id] = arrival
                self.delay_person_ticks += PASSENGERS * max(arrival - planned_arrival(task_id), 0)
        self.current_tick += 1
        self._settle()
        if closed_trains:
            return ";".join(f"{train}:TRACK_CLOSED" for train in closed_trains)
        return "TICK_COMMITTED"

    def _count_plan_changes(
        self,
        moves: dict[str, tuple[str, str]],
        closed_trains: list[str],
        cancels: list[str],
    ) -> None:
        """故障开始后，受影响列车的操作模式（前进/等待/撞闭塞/取消）每切换一次计 1。"""

        if self.current_tick < self.variant.start:
            return
        for task_id in self.affected:
            if self.task_status[task_id] != "pending":
                continue
            if self.current_tick < RELEASE_TICKS[task_id]:
                continue
            train = next(name for name, task in TRAIN_TASK.items() if task == task_id)
            if task_id in cancels:
                mode = "cancel"
            elif train in moves:
                mode = "move"
            elif train in closed_trains:
                mode = "closed"
            else:
                mode = "hold"
            previous = self.last_mode.get(train)
            if previous is not None and previous != mode:
                self.plan_changes += 1
            self.last_mode[train] = mode

    def _settle(self) -> None:
        if all(state != "pending" for state in self.task_status.values()) or (
            self.current_tick >= self.horizon
        ):
            if self.delivered >= SUCCESS_THRESHOLD:
                self._succeed("SERVICE_COMPLETE")
            else:
                self._fail("DEADLINE_SERVICE_BELOW_THRESHOLD")

    def clone(self) -> Map18V10Environment:
        """离线 Oracle 搜索用的浅克隆（可变容器逐个复制）。"""

        twin = copy.copy(self)
        for name in (
            "positions",
            "task_status",
            "progress",
            "resolved_tick",
            "last_mode",
            "counters",
            "violations",
        ):
            setattr(twin, name, dict(getattr(self, name)))
        return twin

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "tick": self.current_tick,
            "actions_used": self.tick_count,
            "positions": dict(sorted(self.positions.items())),
            "task_status": dict(sorted(self.task_status.items())),
            "progress": dict(sorted(self.progress.items())),
            "delivered": self.delivered,
            "canceled": self.canceled,
            "delay_person_ticks": self.delay_person_ticks,
            "resolved_tick": dict(sorted(self.resolved_tick.items())),
            "fault_observed": self.fault_observed,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        conflict = self.terminal_reason in {
            "HEAD_ON_COLLISION",
            "SEGMENT_CAPACITY",
            "STATION_CAPACITY_EXCEEDED",
        }
        if not self.affected:
            recovery = not_applicable("本实例无受影响任务")
        elif all(task in self.resolved_tick for task in self.affected):
            recovery = valid(
                max(self.resolved_tick[task] for task in self.affected) - self.variant.start
            )
        elif conflict:
            recovery = not_applicable(f"冲突终局：{self.terminal_reason}")
        else:
            recovery = censored("截止或预算截尾时受影响任务未了结")
        return {
            "map18.v10.service_rate": ratio(self.delivered, TOTAL_DEMAND),
            "map18.v10.recovery_delay_ticks": recovery,
            "map18.v10.conflict_terminal": valid(int(conflict)),
            "map18.v10.closed_entry_attempts": valid(self.closed_entry_attempts),
            "map18.v10.plan_changes": valid(self.plan_changes),
            "map18.v10.window_violations": valid(self.window_violations),
            "map18.v10.rejected_rows": valid(self.rejected_rows),
            "map18.v10.delay_person_ticks": valid(self.delay_person_ticks),
        }

    def mechanism_triggered(self) -> bool:
        """故障真实发生时，仍有受影响任务未完成。"""

        return self.fault_observed and bool(self.pending_affected_at_fault)


__all__ = [
    "ADJACENCY",
    "INITIAL_POSITIONS",
    "Map18V10Environment",
    "RELEASE_TICKS",
    "ROUTES",
    "TRAIN_TASK",
    "VARIANTS",
    "affected_tasks",
    "edge_key",
    "planned_arrival",
]
