"""MAP-16 V10｜单线预约与节点容量：四个预登记实例（DCR-V10-36）。

V8 的 MAP-16 走 `V4MapAdapter`，绑定 V6 冻结场景 `map16_l3_original`，`_reset_state`
只接受 0/1/2 三个**重复标签**且状态完全相同，因此 `seed_effective=False`。

V10 不改 V4 规则文件，只复用 `Map16Environment` 已公开的构造参数（起点、终点、侧线），
把“同一张图的不同实例”显式登记为四个 seed。四条实例都保留核心机制：单线区段预约、
节点容量 1、侧线让行、提交后整帧移动、无安全完成即死锁。

| seed | label | 起点 a/b | 终点 a/b |
|---:|---|---|---|
| 0 | base | A / B | B / A |
| 1 | siding_goal | A / B | D / A |
| 2 | short_start | X / Y | B / A |
| 3 | cross_start | A / X | D / B |

四例均可解；差异在会车点与最短 makespan（见 `sealed_truth()`）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from agent_arena.v10.metrics.schema import (
    MetricSpec,
    MValue,
    censored,
    not_applicable,
    valid,
)
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v4.map16 import Map16Environment
from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.catalog import LEVEL_OF, WORLD_OF
from agent_arena.worlds.scenario_v8.models import V8Action, V8StepResult
from agent_arena.worlds.scenario_v8.v4_adapter import V4_SHAPES_BY_MAP, V4MapAdapter


@dataclass(frozen=True)
class TrackVariant:
    label: str
    start_positions: dict[str, str]
    goals: dict[str, str]


VARIANTS: dict[int, TrackVariant] = {
    0: TrackVariant("base", {"a": "A", "b": "B"}, {"a": "B", "b": "A"}),
    1: TrackVariant("siding_goal", {"a": "A", "b": "B"}, {"a": "D", "b": "A"}),
    2: TrackVariant("short_start", {"a": "X", "b": "Y"}, {"a": "B", "b": "A"}),
    3: TrackVariant("cross_start", {"a": "A", "b": "Y"}, {"a": "D", "b": "A"}),
}

SIDINGS = frozenset({"D"})


class Map16V10Inner(Map16Environment):
    """按 V10 seed 固定实例参数；库层 seed 只作重复标签。"""

    def __init__(self, *, environment_seed: int, step_limit: int) -> None:
        variant = VARIANTS[environment_seed]
        super().__init__(
            step_limit=step_limit,
            start_positions=dict(variant.start_positions),
            goals=dict(variant.goals),
            sidings=SIDINGS,
        )

    def _reset_state(self, seed: int) -> None:
        del seed
        # 实例身份已由构造参数决定；`Map16Environment` 只接受 0/1/2 重复标签。
        super()._reset_state(0)


class Map16V10Environment(V10Map, V4MapAdapter):
    map_id = "MAP-16"
    title = "单线预约与节点容量"
    world = "subway"
    level = "简单"
    RULE_VERSION = "v10.map16.1"
    RULE_SOURCES = ("src/agent_arena/worlds/scenario_v4/map16.py",)
    SEED_SPACE = tuple(sorted(VARIANTS))
    PRIMARY_METRIC = "map16.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map16.v10.mission_success",
            "primary",
            "higher",
            "两列车都在不发生区段/节点冲突的前提下到达各自终点",
            "1",
            censored_rule="截尾 → CENSORED；冲突/死锁终局 → VALID 0",
        ),
        MetricSpec(
            "map16.v10.legal_action_rate",
            "secondary",
            "higher",
            "合法决策数 / 总决策数（结构不符或非法路由计为不合法）",
            "总决策数",
            zero_denominator="无决策 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map16.v10.node_capacity_conflicts",
            "guardrail",
            "lower",
            "节点容量冲突次数（含侧线容量冲突）",
            "—",
            unit="count",
            valid_range=(0.0, 100.0),
        ),
        MetricSpec(
            "map16.v10.deadlock_count",
            "guardrail",
            "lower",
            "进入无安全完成状态（死锁）的次数",
            "—",
            unit="count",
            valid_range=(0.0, 100.0),
        ),
        MetricSpec(
            "map16.v10.makespan_gap",
            "secondary",
            "lower",
            "成功时的完成 tick 与最短排程之差",
            "成功局（1）",
            zero_denominator="未成功 → NOT_APPLICABLE",
            unit="ticks",
            valid_range=(0.0, 100.0),
        ),
        MetricSpec(
            "map16.v10.committed_ticks",
            "diagnostic",
            "lower",
            "终局时的已提交移动 tick 数",
            "—",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        if seed not in self.SEED_SPACE:
            raise ValueError(f"{self.map_id} V10 未预登记环境 seed {seed}")
        self.environment_seed = seed
        self.map_id = "MAP-16"
        self.world = WORLD_OF["MAP-16"]
        self.level = LEVEL_OF["MAP-16"]
        self.SHAPES = V4_SHAPES_BY_MAP["MAP-16"]
        self._inner = Map16V10Inner(environment_seed=seed, step_limit=step_limit)
        self.title = "单线预约与节点容量"
        self.invalid_count = 0
        self.used_siding = False
        self.PUBLIC_FIELDS = self._inner_public_fields() | {
            "goal",
            "ticks_remaining",
            "siding_nodes",
        }
        MapEnvironment.__init__(self, seed=seed, step_limit=step_limit, condition_id="v10")

    @property
    def model(self) -> Map16V10Inner:
        """适配器把 ``_inner`` 声明为 V4 基类；这里收窄回 MAP-16 实例类型。"""

        return cast(Map16V10Inner, self._inner)

    # ------------------------------------------------------------------ instance
    def scenario_descriptor(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        return {
            "label": variant.label,
            "start_positions": dict(variant.start_positions),
            "goals": dict(variant.goals),
            "siding_nodes": sorted(SIDINGS),
        }

    def sealed_truth(self) -> dict[str, Any]:
        variant = VARIANTS[self.environment_seed]
        shortest, _ = self.model._shortest_schedule()
        return {
            "label": variant.label,
            "start_positions": dict(variant.start_positions),
            "goals": dict(variant.goals),
            "shortest_makespan": shortest,
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "线路：A—X—M—Y—B 为单线主线，M—D 为唯一侧线；每段同一 tick 只能过 1 列车，"
            "每个节点（含侧线）同一时刻只能停 1 列车。",
            "两列车 a、b 各自有固定方向表（见 train_route_directions）；"
            "set_route(train_id, next_node) 只登记下一跳，move_train() 才会把**所有**已登记的路由"
            "作为一整帧提交并推进 1 tick。",
            "若两列车的下一跳占用同一区段，或同帧后停在同一节点，立即以对应冲突终局。",
            "让行必须把一列车临时停到侧线 D：occupy_siding(train_id, next_node) 与 set_route 等价，"
            "但目标必须是侧线。",
            "两列车都到达各自终点即成功；提交后若不存在安全完成路径，则判定死锁失败。",
            "本实例的起点、终点与侧线节点见 Observation 的 train_positions、train_goals、"
            "siding_nodes 与 topology。",
        )

    # ------------------------------------------------------------------ rules
    def _public(self) -> dict[str, Any]:
        payload = V4MapAdapter._public(self)
        payload["goal"] = (
            "用 set_route + move_train 把 a、b 分别送到 "
            f"{self.model.goals['a']} 与 {self.model.goals['b']}；必要时用侧线 D 让行。"
        )
        payload["ticks_remaining"] = max(0, self.model.step_limit - self.model.step_count)
        payload["siding_nodes"] = sorted(self.model.sidings)
        return payload

    def step(self, action: V8Action) -> V8StepResult:
        result = V4MapAdapter.step(self, action)
        if self.model.current_tick > 0 and any(
            position in self.model.sidings for position in self.model.positions.values()
        ):
            self.used_siding = True
        return result

    def reject_invalid_action(self) -> V8StepResult:
        if not self.model.is_terminal:
            self.invalid_count += 1
        return V4MapAdapter.reject_invalid_action(self)

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        payload = dict(V4MapAdapter.judge_state(self))
        payload.update(
            {
                "environment_seed": self.environment_seed,
                "invalid_count": self.invalid_count,
                "used_siding": self.used_siding,
                "sidings": sorted(self.model.sidings),
                "shortest_makespan": self.model._shortest_schedule()[0],
            }
        )
        return payload

    def v10_metrics(self) -> dict[str, MValue]:
        running = not self.is_terminal
        success: MValue = censored("截尾") if running else valid(1 if self.is_success else 0)
        total = self.model.step_count
        if total:
            legal: MValue = valid(round((total - self.invalid_count) / total, 6))
        else:
            legal = not_applicable("无决策")
        conflicts = self.model.conflicts
        shortest, _ = self.model._shortest_schedule()
        gap: MValue = (
            valid(max(0, self.model.current_tick - shortest))
            if self.is_success
            else not_applicable("未成功")
        )
        return {
            "map16.v10.mission_success": success,
            "map16.v10.legal_action_rate": legal,
            "map16.v10.node_capacity_conflicts": valid(
                conflicts.get("NODE_CAPACITY_CONFLICT", 0)
                + conflicts.get("SIDING_CAPACITY_CONFLICT", 0)
            ),
            "map16.v10.deadlock_count": valid(self.model.deadlock_count),
            "map16.v10.makespan_gap": gap,
            "map16.v10.committed_ticks": valid(self.model.current_tick),
        }

    def mechanism_triggered(self) -> bool:
        """单线预约 + 侧线让行确实发生：至少提交过一次移动，且列车进过侧线。"""

        return self.used_siding and self.model.current_tick >= 1


__all__ = ["Map16V10Environment", "Map16V10Inner", "TrackVariant", "VARIANTS"]
