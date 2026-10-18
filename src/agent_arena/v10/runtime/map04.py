"""MAP-04 V10｜潮汐密道：相位预测成为必要条件，绕行保留但计成本（DCR-V10-08）。

与 V8 的差异：

- 预登记 6 个实例：潮汐周期、初始相位、截止时刻与绕行长度都随 seed 变化；
- **盲撞要付代价**：在非安全相位尝试 `S_G` 会耗 3 tick 并被潮水推回原侧，
  相位随之推进；因此“看到门就撞、撞不开再撞”在紧截止下不再可行；
- 绕行仍然合法且完整保留，但它固定消耗 12–16 tick，`time_margin` 会显著低于
  相位预测路线——“合法替代策略”由连续质量量区分，而不是被删掉；
- 主指标从“是否通过窗口”改成**时间余量** `deadline − finish_tick`，
  失败为 0、截尾为 CENSORED；未被灯的局保留部分进度（`fit` 与否）。
"""

from __future__ import annotations

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

BASE_EDGES = {
    "T_S": ("T", "S"),
    "S_G": ("S", "G"),
    "G_D": ("G", "D"),
    "T_B1": ("T", "B1"),
    "B1_B2": ("B1", "B2"),
    "B2_B3": ("B2", "B3"),
    "B3_B4": ("B3", "B4"),
    "B4_D": ("B4", "D"),
}
EXTRA_EDGES = {
    "B1_BX": ("B1", "BX"),
    "BX_B2": ("BX", "B2"),
}
FAILED_CROSSING_TICKS = 3


@dataclass(frozen=True)
class TideVariant:
    period: int
    initial_phase: int
    deadline: int
    extra_detour: bool
    safe_phases: tuple[int, ...] = (0, 1)


VARIANTS: dict[int, TideVariant] = {
    0: TideVariant(6, 2, 15, False),
    1: TideVariant(5, 3, 15, False),
    2: TideVariant(7, 4, 17, True),
    3: TideVariant(6, 0, 15, False),
    4: TideVariant(5, 3, 15, False),
    5: TideVariant(7, 2, 17, True),
}


class Map04V10Environment(V10Map):
    map_id = "MAP-04"
    title = "潮汐密道"
    world = "lighthouse"
    level = "简单"
    RULE_VERSION = "v10.map04.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "edge_id"})},
        "inspect": {frozenset({"tool", "target"})},
        "pickup": {frozenset({"tool", "item_id"})},
        "interact": {frozenset({"tool", "target", "choice"})},
        "wait": {frozenset({"tool", "turns"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "tide_phase",
            "tide_period",
            "open_phases",
            "failed_crossing_ticks",
            "inventory",
            "wick_location",
            "lamp_wick_fitted",
            "lamp_lit",
            "rescue_deadline_tick",
            "goal",
        }
    )
    PRIMARY_METRIC = "map04.v10.time_margin"
    METRIC_SPECS = (
        MetricSpec(
            "map04.v10.time_margin",
            "primary",
            "higher",
            "成功时 deadline − 点亮 tick；失败 = 0",
            "1",
            unit="ticks",
            valid_range=(-60.0, 60.0),
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map04.v10.window_hit_rate",
            "secondary",
            "higher",
            "安全相位通过次数 / 尝试次数",
            "尝试过 S_G 的局",
            zero_denominator="从未尝试过 S_G → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map04.v10.high_tide_entries",
            "guardrail",
            "lower",
            "非安全相位尝试次数",
            "—",
            unit="count",
            valid_range=(0.0, 30.0),
        ),
        MetricSpec(
            "map04.v10.wait_ticks",
            "diagnostic",
            "none",
            "主动等待 tick",
            "—",
            unit="ticks",
            valid_range=(0.0, 60.0),
        ),
        MetricSpec(
            "map04.v10.detour_edges",
            "diagnostic",
            "lower",
            "走绕行海岸路的边数",
            "—",
            unit="count",
            valid_range=(0.0, 40.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.EDGES = dict(BASE_EDGES)
        if self.variant.extra_detour:
            self.EDGES.update(EXTRA_EDGES)
        self.node = "T"
        self.items = []
        self.tide_phase = self.variant.initial_phase
        self.tide_period = self.variant.period
        self.wick_available = True
        self.lamp_wick_fitted = False
        self.lamp_lit = False
        self.rescue_deadline_tick = self.variant.deadline
        self.crossing_attempts = 0
        self.crossing_successes = 0
        self.first_crossing_tick: int | None = None
        self.high_tide_entries = 0
        self.wait_ticks = 0
        self.detour_edges = 0
        self.finish_tick: int | None = None
        self._last_cost = 1

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "tide_period": self.variant.period,
            "open_phases": list(self.variant.safe_phases),
            "rescue_deadline_tick": self.variant.deadline,
            "edges": sorted(self.EDGES),
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "initial_phase": self.variant.initial_phase,
            "period": self.variant.period,
            "deadline": self.variant.deadline,
            "extra_detour": self.variant.extra_detour,
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "地形：T—S—G 与 T—B1—…—B4—D—G 两条路线；G 存放灯芯，T 有灯塔。",
            "tide_phase 每 tick +1 并对 tide_period 取模；open_phases 是安全相位。",
            f"S_G 只能在安全相位通过；否则失败并耗 {FAILED_CROSSING_TICKS} tick、"
            "被潮水推回原侧。",
            "pickup(wick) 在 G；interact(lamp, fit_wick) 与 interact(lamp, ignite) 在 T。",
            "rescue_deadline_tick 前必须点亮；评分是成功时的时间余量，越早越好。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "tide_phase": self.tide_phase,
            "tide_period": self.tide_period,
            "open_phases": list(self.variant.safe_phases),
            "failed_crossing_ticks": FAILED_CROSSING_TICKS,
            "inventory": list(self.items),
            "wick_location": "G" if self.wick_available else "carried",
            "lamp_wick_fitted": self.lamp_wick_fitted,
            "lamp_lit": self.lamp_lit,
            "rescue_deadline_tick": self.rescue_deadline_tick,
            "goal": "在救援船抵达前把灯芯装进灯塔并点亮；越早越好。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        self._last_cost = 1
        if tool == "move":
            if action.edge_id is None:
                return "INVALID_ACTION_SCHEMA"
            edge_id = action.edge_id
            if edge_id == "S_G":
                self.crossing_attempts += 1
                if self.tide_phase not in self.variant.safe_phases:
                    self.high_tide_entries += 1
                    self._last_cost = FAILED_CROSSING_TICKS
                    return "TIDE_WINDOW_CLOSED"
                self.crossing_successes += 1
                if self.first_crossing_tick is None:
                    self.first_crossing_tick = self.tick_count + 1
            if edge_id in {"T_B1", "B1_B2", "B1_BX", "BX_B2", "B2_B3", "B3_B4", "B4_D", "G_D"}:
                self.detour_edges += 1
            destination, result = self.move_edge(edge_id)
            return result if destination is not None else "EDGE_NOT_ADJACENT"
        if tool == "inspect":
            if action.target == "tide_gauge":
                return f"TIDE_PHASE:{self.tide_phase}"
            return "TARGET_NOT_VISIBLE"
        if tool == "pickup":
            if action.item_id != "wick" or self.node != "G" or not self.wick_available:
                return "ITEM_NOT_PRESENT"
            self.wick_available = False
            self.take("wick")
            return "PICKED:wick"
        if tool == "wait":
            turns = int(action.turns or 1)
            self.wait_ticks += turns
            self._last_cost = turns
            return "WAITED"
        if tool == "interact":
            return self._interact(action)
        return "ACTION_NOT_ALLOWED"

    def _interact(self, action: V8Action) -> str:
        if action.target != "lamp" or self.node != "T":
            return "TARGET_NOT_VISIBLE" if action.target == "lamp" else "ACTION_NOT_ALLOWED"
        if action.choice == "fit_wick":
            if not self.has("wick"):
                return "WICK_REQUIRED"
            if self.lamp_wick_fitted:
                return "WICK_ALREADY_FITTED"
            self.lamp_wick_fitted = True
            return "WICK_FITTED"
        if action.choice == "ignite":
            if not self.lamp_wick_fitted:
                return "WICK_NOT_FITTED"
            self.lamp_lit = True
            self.finish_tick = self.tick_count + 1
            self._succeed("SIGNAL_LIT")
            return "SIGNAL_LIT"
        return "ACTION_NOT_ALLOWED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._last_cost

    def _after_tick(self) -> None:
        self.tide_phase = (self.tide_phase + self._last_cost) % self.tide_period
        if self.tick_count >= self.rescue_deadline_tick and not self.lamp_lit:
            self._fail("RESCUE_SIGNAL_WINDOW_EXPIRED")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "location": self.node,
            "inventory": sorted(self.items),
            "tide_phase": self.tide_phase,
            "lamp_wick_fitted": self.lamp_wick_fitted,
            "lamp_lit": self.lamp_lit,
            "crossing_attempts": self.crossing_attempts,
            "crossing_successes": self.crossing_successes,
            "first_crossing_tick": self.first_crossing_tick,
            "high_tide_entries": self.high_tide_entries,
            "wait_ticks": self.wait_ticks,
            "detour_edges": self.detour_edges,
            "finish_tick": self.finish_tick,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        if self.lamp_lit:
            assert self.finish_tick is not None
            margin: MValue = valid(self.rescue_deadline_tick - self.finish_tick)
        elif running:
            margin = censored("未点亮即截尾")
        else:
            margin = valid(0)
        if self.crossing_attempts == 0:
            hit = not_applicable("从未尝试 S_G")
        else:
            hit = ratio(self.crossing_successes, self.crossing_attempts)
        return {
            "map04.v10.time_margin": margin,
            "map04.v10.window_hit_rate": hit,
            "map04.v10.high_tide_entries": valid(self.high_tide_entries),
            "map04.v10.wait_ticks": valid(self.wait_ticks),
            "map04.v10.detour_edges": valid(self.detour_edges),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：至少一次相位判断影响了通过结果（尝试过 S_G）。"""

        return self.crossing_attempts > 0


def _safety(phase: int, variant: TideVariant) -> bool:
    return phase in variant.safe_phases


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知 BFS：在 (节点, 相位, 是否取芯, 是否装芯) 状态空间求最早点亮路线。"""

    variant = VARIANTS[environment_seed]
    edges = dict(BASE_EDGES)
    if variant.extra_detour:
        edges.update(EXTRA_EDGES)
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for edge_id, (a, b) in edges.items():
        adjacency.setdefault(a, []).append((b, edge_id))
        adjacency.setdefault(b, []).append((a, edge_id))

    start = ("T", variant.initial_phase, False, False)
    frontier: list[tuple[int, tuple[str, int, bool, bool], list[dict[str, Any]]]] = [
        (0, start, [])
    ]
    seen: dict[tuple[str, int, bool, bool], int] = {start: 0}
    best: tuple[int, list[dict[str, Any]]] | None = None
    while frontier:
        frontier.sort(key=lambda item: item[0])
        ticks, state, path = frontier.pop(0)
        node, phase, carried, fitted = state
        if fitted and node == "T":
            best = (ticks, [*path, {"tool": "interact", "target": "lamp", "choice": "ignite"}])
            break
        transitions: list[tuple[int, tuple[str, int, bool, bool], dict[str, Any]]] = []
        for destination, edge_id in adjacency.get(node, []):
            cost = 1
            ok = True
            if edge_id == "S_G" and not _safety(phase, variant):
                cost = FAILED_CROSSING_TICKS
                ok = False
            new_phase = (phase + cost) % variant.period
            if ok:
                transitions.append(
                    (
                        cost,
                        (destination, new_phase, carried, fitted),
                        {"tool": "move", "edge_id": edge_id},
                    )
                )
        transitions.append(
            (1, (node, (phase + 1) % variant.period, carried, fitted), {"tool": "wait", "turns": 1})
        )
        if node == "G" and not carried:
            transitions.append(
                (
                    1,
                    (node, (phase + 1) % variant.period, True, fitted),
                    {"tool": "pickup", "item_id": "wick"},
                )
            )
        if node == "T" and carried and not fitted:
            transitions.append(
                (
                    1,
                    (node, (phase + 1) % variant.period, carried, True),
                    {"tool": "interact", "target": "lamp", "choice": "fit_wick"},
                )
            )
        for cost, new_state, action in transitions:
            total = ticks + cost
            if total >= variant.deadline:
                continue
            if seen.get(new_state, 10**9) <= total:
                continue
            seen[new_state] = total
            frontier.append((total, new_state, [*path, action]))
    if best is None:  # pragma: no cover - every registered seed is solvable
        raise RuntimeError("no feasible route")
    return best[1]


__all__ = [
    "BASE_EDGES",
    "FAILED_CROSSING_TICKS",
    "Map04V10Environment",
    "TideVariant",
    "VARIANTS",
    "oracle_actions",
]
