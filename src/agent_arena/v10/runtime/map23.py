"""MAP-23 V10｜迷雾中的遗迹：线索成为出手的前提（DCR-V10-13）。

与 V8 的差异：

- **调查必须先有线索**：`investigate` 只有在（a）已用 `mark` 声明候选入口、（b）至少买过
  一条侦察线索、且（c）该候选与全部已购线索相容时才执行；否则返回
  `MARK_REQUIRED` / `CLUE_REQUIRED` / `MARK_EXCLUDED_BY_CLUE`，并记
  `unjustified_investigations`。V9 的“完全不侦察、逐个付费试”被这条接口规则消除；
- **四个入口**（X/Y/Z/W）× 三处侦察（N/R/H）：`no_scout` 无法出手，
  而“单站线索”对部分真值仍然二义（Y/Z），因此“线索值不值它的路费”第一次成为
  真实的探索—利用权衡；
- 真入口随 seed 覆盖全部四个变体（V8 三局恒为 Z）；
- 指标：主指标为线索利用率（最强单条线索缩减的候选比例），另有花费效率、未论证调查
  与重复无效探索。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.metrics.schema import (
    MetricSpec,
    MValue,
    censored,
    not_applicable,
    valid,
)
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

ENTRANCES = ("X", "Y", "Z", "W")
SCOUT_STATIONS = ("N", "R", "H")
EDGE_COSTS: dict[frozenset[str], int] = {
    frozenset({"A", "N"}): 1,
    frozenset({"A", "R"}): 1,
    frozenset({"A", "H"}): 2,
    frozenset({"A", "X"}): 2,
    frozenset({"A", "Y"}): 2,
    frozenset({"A", "Z"}): 3,
    frozenset({"A", "W"}): 3,
}
EDGES: dict[str, tuple[str, str]] = {
    f"{sorted(edge)[0]}_{sorted(edge)[1]}": (sorted(edge)[0], sorted(edge)[1])
    for edge in EDGE_COSTS
}
INVESTIGATION_COST = {"X": 2, "Y": 2, "Z": 3, "W": 3}
SCOUT_COST = {"N": 2, "R": 2, "H": 3}
SUPPLY_INITIAL = 16
SUPPLY_MAX = 16

SIGNAL_SUPPORTS: dict[str, tuple[str, ...]] = {
    "S_N_1": ("X", "Y"),
    "S_N_2": ("Z", "W"),
    "S_R_1": ("X", "Z"),
    "S_R_2": ("Y", "W"),
    "S_H_1": ("X",),
    "S_H_2": ("Y", "Z"),
    "S_H_3": ("W",),
}
#: 真入口 → 各侦察站的信号（公开：站点被侦察后立刻返回 supports）。
SIGNALS: dict[str, dict[str, str]] = {
    "X": {"N": "S_N_1", "R": "S_R_1", "H": "S_H_1"},
    "Y": {"N": "S_N_1", "R": "S_R_2", "H": "S_H_2"},
    "Z": {"N": "S_N_2", "R": "S_R_1", "H": "S_H_2"},
    "W": {"N": "S_N_2", "R": "S_R_2", "H": "S_H_3"},
}
TRUTH_BY_SEED = {0: "X", 1: "Y", 2: "Z", 3: "W"}


class Map23V10Environment(V10Map):
    map_id = "MAP-23"
    title = "迷雾中的遗迹"
    world = "jungle"
    level = "中等"
    RULE_VERSION = "v10.map23.1"
    SEED_SPACE = tuple(sorted(TRUTH_BY_SEED))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "to"})},
        "scout": {frozenset({"tool"})},
        "mark": {frozenset({"tool", "choice"})},
        "investigate": {frozenset({"tool", "entrance"})},
        "resupply": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "neighbors",
            "entrances",
            "investigation_cost",
            "scout_cost",
            "supply_remaining",
            "resupply_cache_available",
            "available_scout_stations",
            "clues_received",
            "agent_marked_candidate",
            "searched_false_entrances",
            "actions_taken",
            "goal",
        }
    )
    PRIMARY_METRIC = "map23.v10.clue_utilization"
    METRIC_SPECS = (
        MetricSpec(
            "map23.v10.clue_utilization",
            "primary",
            "higher",
            "最强单条已购线索缩减的候选比例 (n − |supports|) / (n − 1)",
            "买过线索的局（1）",
            zero_denominator="未侦察 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map23.v10.spent_ratio",
            "secondary",
            "lower",
            "花费补给 / 初始补给",
            "1",
        ),
        MetricSpec(
            "map23.v10.unjustified_investigations",
            "guardrail",
            "lower",
            "缺少 mark / 线索 / 与线索矛盾的调查尝试次数",
            "—",
            unit="count",
            valid_range=(0.0, 20.0),
        ),
        MetricSpec(
            "map23.v10.repeated_invalid_exploration",
            "guardrail",
            "lower",
            "对已排除入口再次调查的次数",
            "—",
            unit="count",
            valid_range=(0.0, 20.0),
        ),
        MetricSpec(
            "map23.v10.ignored_counterevidence",
            "guardrail",
            "lower",
            "最终调查入口是否已被已购线索排除",
            "1",
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.node = "A"
        self.true_entrance = TRUTH_BY_SEED[seed]
        self.supply = SUPPLY_INITIAL
        self.resupply_used = False
        self.scouted: list[str] = []
        self.clues: list[dict[str, Any]] = []
        self.searched_false: list[str] = []
        self.marked: str | None = None
        self.final_target: str | None = None
        self.unjustified = 0
        self._cost = 1

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "entrances": list(ENTRANCES),
            "scout_stations": list(SCOUT_STATIONS),
            "investigation_cost": dict(INVESTIGATION_COST),
            "scout_cost": dict(SCOUT_COST),
            "supply_initial": SUPPLY_INITIAL,
            "edges": {
                "-".join(sorted(edge)): cost for edge, cost in sorted(EDGE_COSTS.items())
            },
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {"true_entrance": self.true_entrance, "signals": SIGNALS[self.true_entrance]}

    def public_rules(self) -> tuple[str, ...]:
        return (
            "A 是枢纽，直连 N/R/H（侦察站）与 X/Y/Z/W（入口）；move(to) 扣路费。",
            f"scout 只在侦察站可用、每站一次，费用 {SCOUT_COST}；返回该站的 supports "
            "（该线索认为可能的入口集合）。",
            "investigate 必须先 mark 声明候选，且必须**至少买过一条线索**，"
            "并且候选不能被已购线索排除；否则被拒并记 unjustified。",
            f"调查费用 {INVESTIGATION_COST}；真入口 + 扣费后补给 > 0 即成功。",
            f"A 的补给箱一次性补满到 {SUPPLY_MAX}。",
        )

    # ------------------------------------------------------------------ public
    def _neighbors(self) -> dict[str, int]:
        return {
            other: cost
            for edge, cost in EDGE_COSTS.items()
            if self.node in edge
            for other in edge
            if other != self.node
        }

    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "neighbors": self._neighbors(),
            "entrances": list(ENTRANCES),
            "investigation_cost": dict(INVESTIGATION_COST),
            "scout_cost": dict(SCOUT_COST),
            "supply_remaining": self.supply,
            "resupply_cache_available": (
                self.node == "A" and not self.resupply_used and self.supply < SUPPLY_MAX
            ),
            "available_scout_stations": (
                [self.node]
                if self.node in SCOUT_STATIONS and self.node not in self.scouted
                else []
            ),
            "clues_received": [
                {
                    "station": clue["station"],
                    "signal": clue["signal"],
                    "supports": list(clue["supports"]),
                }
                for clue in self.clues
            ],
            "agent_marked_candidate": self.marked,
            "searched_false_entrances": list(self.searched_false),
            "actions_taken": self.tick_count,
            "goal": (
                "先买线索再出手：mark 一个与线索相容的候选入口，然后到该入口调查；"
                "调查扣费后补给必须严格大于 0。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._cost = 1
        if action.tool == "move":
            return self._move(action)
        if action.tool == "scout":
            return self._scout()
        if action.tool == "mark":
            return self._mark(action)
        if action.tool == "investigate":
            return self._investigate(action)
        if action.tool == "resupply":
            return self._resupply()
        return "ACTION_NOT_ALLOWED"

    def _spend(self, amount: int) -> bool:
        if self.supply < amount:
            return False
        self.supply -= amount
        return True

    def _move(self, action: V8Action) -> str:
        target = action.to
        neighbors = self._neighbors()
        if target not in neighbors:
            return "NOT_ADJACENT"
        if not self._spend(neighbors[target]):
            return "INSUFFICIENT_SUPPLY"
        self.node = str(target)
        return f"MOVED:{target}"

    def _scout(self) -> str:
        if self.node not in SCOUT_STATIONS:
            return "SCOUT_NOT_AVAILABLE_HERE"
        if self.node in self.scouted:
            return "SCOUT_ALREADY_USED"
        if not self._spend(SCOUT_COST[self.node]):
            return "INSUFFICIENT_SUPPLY"
        signal = SIGNALS[self.true_entrance][self.node]
        self.scouted.append(self.node)
        self.clues.append(
            {"station": self.node, "signal": signal, "supports": SIGNAL_SUPPORTS[signal]}
        )
        return f"SCOUTED:{signal}"

    def candidates(self) -> set[str]:
        """与全部已购线索相容的候选入口。"""

        allowed = set(ENTRANCES)
        for clue in self.clues:
            allowed &= set(clue["supports"])
        return allowed

    def _investigate(self, action: V8Action) -> str:
        entrance = action.entrance
        if entrance not in ENTRANCES:
            return "INVALID_ENTRANCE"
        if self.node != entrance:
            return "NOT_AT_ENTRANCE"
        if not self.clues:
            self.unjustified += 1
            return "CLUE_REQUIRED"
        if self.marked != entrance:
            self.unjustified += 1
            return "MARK_REQUIRED"
        if entrance not in self.candidates():
            self.unjustified += 1
            return "MARK_EXCLUDED_BY_CLUE"
        self.final_target = entrance
        if entrance in self.searched_false:
            self._count("REPEATED_INVALID_EXPLORATION")
        if not self._spend(INVESTIGATION_COST[entrance]):
            return "INSUFFICIENT_SUPPLY"
        if entrance == self.true_entrance:
            if self.supply > 0:
                self._succeed("TRUE_ENTRANCE_FOUND")
                return "TRUE_ENTRANCE_FOUND"
            self._fail("SUPPLY_MUST_REMAIN_POSITIVE")
            return "SUPPLY_MUST_REMAIN_POSITIVE"
        if entrance not in self.searched_false:
            self.searched_false.append(entrance)
        if self.supply == 0:
            self._fail("SUPPLY_DEPLETED")
            return "FALSE_ENTRANCE"
        return "FALSE_ENTRANCE"

    def _mark(self, action: V8Action) -> str:
        if action.choice not in ENTRANCES:
            return "INVALID_ENTRANCE"
        self.marked = action.choice
        return f"MARKED:{action.choice}"

    def _resupply(self) -> str:
        if self.node != "A":
            return "RESUPPLY_ONLY_AT_A"
        if self.resupply_used:
            return "RESUPPLY_ALREADY_USED"
        self.resupply_used = True
        self.supply = SUPPLY_MAX
        return "RESUPPLIED"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    def _after_tick(self) -> None:
        if self.status.value != "running":
            return
        if self.supply == 0:
            self._fail("SUPPLY_DEPLETED")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "tick": self.tick_count,
            "location": self.node,
            "true_entrance": self.true_entrance,
            "supply": self.supply,
            "resupply_used": self.resupply_used,
            "scouted": list(self.scouted),
            "clues": [dict(clue) for clue in self.clues],
            "candidates": sorted(self.candidates()),
            "marked": self.marked,
            "final_target": self.final_target,
            "unjustified_investigations": self.unjustified,
            "searched_false": list(self.searched_false),
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        if running:
            utilization: MValue = censored("截尾")
            spent: MValue = censored("截尾")
        else:
            spent = valid(round((SUPPLY_INITIAL - self.supply) / SUPPLY_INITIAL, 6))
            if not self.clues:
                utilization = not_applicable("未侦察")
            else:
                reductions = [
                    (len(ENTRANCES) - len(clue["supports"])) / (len(ENTRANCES) - 1)
                    for clue in self.clues
                ]
                utilization = valid(round(max(reductions), 6))
        return {
            "map23.v10.clue_utilization": utilization,
            "map23.v10.spent_ratio": spent,
            "map23.v10.unjustified_investigations": valid(self.unjustified),
            "map23.v10.repeated_invalid_exploration": valid(
                self.counters.get("REPEATED_INVALID_EXPLORATION", 0)
            ),
            "map23.v10.ignored_counterevidence": valid(
                int(self.final_target is not None and self.final_target not in self.candidates())
            ),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：买的线索真的改变了出手（最终调查入口在候选集内且由线索缩过）。"""

        return bool(self.clues) and self.final_target is not None


def _cheapest_plan(environment_seed: int) -> tuple[list[str], str]:
    """在公开规则下选最省补给的“先侦察再出手”方案。"""

    truth = TRUTH_BY_SEED[environment_seed]
    best: tuple[int, list[str], str] | None = None
    stations = list(SCOUT_STATIONS)
    for size in (1, 2):
        for index in range(len(stations)):
            combo = stations[index : index + size] if size == 1 else stations[index :]
            if size == 2 and len(combo) != 2:
                combo = stations[:2]
            allowed = set(ENTRANCES)
            for station in combo:
                allowed &= set(SIGNAL_SUPPORTS[SIGNALS[truth][station]])
            if len(allowed) != 1:
                continue
            target = next(iter(allowed))
            cost = sum(
                2 * EDGE_COSTS[frozenset({"A", station})] + SCOUT_COST[station]
                for station in combo
            )
            cost += EDGE_COSTS[frozenset({"A", target})]
            cost += INVESTIGATION_COST[target]
            if best is None or cost < best[0]:
                best = (cost, list(combo), target)
    if best is None:  # pragma: no cover - 每个真值都有可用方案
        raise RuntimeError("no plan")
    return best[1], best[2]


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    stations, target = _cheapest_plan(environment_seed)
    actions: list[dict[str, Any]] = []
    for station in stations:
        actions.append({"tool": "move", "to": station})
        actions.append({"tool": "scout"})
        actions.append({"tool": "move", "to": "A"})
    actions.append({"tool": "mark", "choice": target})
    actions.append({"tool": "move", "to": target})
    actions.append({"tool": "investigate", "entrance": target})
    return actions


__all__ = [
    "ENTRANCES",
    "INVESTIGATION_COST",
    "Map23V10Environment",
    "SCOUT_STATIONS",
    "SIGNALS",
    "SIGNAL_SUPPORTS",
    "SUPPLY_INITIAL",
    "TRUTH_BY_SEED",
    "oracle_actions",
]
