"""MAP-23｜迷雾中的遗迹：把线索信息量换算成可执行补给账。

本图与同世界另两图的机制差异：MAP-22 的图永远不变、核心是记住走过的边；
MAP-24 的图会在局中坍塌、核心是在线改路。本图路网与成本完全公开，主机制是
“三个等概率真入口 + 三处付费侦察 + 一次性补满”，玩家要判断一条线索值不值
它的路费 + 2 补给。

指标口径（与 V7 卡片一致）：
- ``clue_utilization`` = 最强单条已购线索缩减的候选数 / 2；未侦察记 0。
- ``cost_per_discovery`` = (14 − 终局剩余补给) / 成功发现数；0 发现为 N/A。
- ``repeated_invalid_exploration`` = 对已排除入口再次调查的次数。
- ``ignored_counterevidence`` = 最终调查入口是否已被已购线索排除。

实现约定：重复调查一个已排除入口允许执行并再次扣费，用于让
``repeated_invalid_exploration`` 可达；它不会改变入口真假。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action, V8Status

NODES = ("A", "N", "R", "H", "X", "Y", "Z")
EDGES: dict[frozenset[str], int] = {
    frozenset({"A", "N"}): 1,
    frozenset({"N", "X"}): 1,
    frozenset({"N", "Y"}): 2,
    frozenset({"A", "R"}): 2,
    frozenset({"R", "Y"}): 1,
    frozenset({"R", "Z"}): 2,
    frozenset({"A", "H"}): 2,
}
ENTRANCES = ("X", "Y", "Z")
INVESTIGATION_COST = {"X": 3, "Y": 2, "Z": 3}
SCOUT_COST = 2
SUPPLY_INITIAL = 14
SUPPLY_MAX = 14
SCOUT_STATIONS = ("N", "R", "H")
VARIANTS = ("X", "Y", "Z")

#: signal per (true entrance, station); supports are the publicly decoded sets.
SIGNALS: dict[str, dict[str, str]] = {
    "X": {
        "N": "STONE_SPLIT",
        "R": "WATER_UPSTREAM_SINK",
        "H": "RIDGE_NORTH_WHITE_MARK",
    },
    "Y": {
        "N": "STONE_SPLIT",
        "R": "WATER_TWIN_RIPPLES",
        "H": "RIDGE_CENTER_AMBER_MARK",
    },
    "Z": {
        "N": "STONE_THREE_RINGS",
        "R": "WATER_TWIN_RIPPLES",
        "H": "RIDGE_LOW_BLACK_MARK",
    },
}
SIGNAL_SUPPORTS: dict[str, tuple[str, ...]] = {
    "STONE_SPLIT": ("X", "Y"),
    "STONE_THREE_RINGS": ("Z",),
    "WATER_UPSTREAM_SINK": ("X",),
    "WATER_TWIN_RIPPLES": ("Y", "Z"),
    "RIDGE_NORTH_WHITE_MARK": ("X",),
    "RIDGE_CENTER_AMBER_MARK": ("Y",),
    "RIDGE_LOW_BLACK_MARK": ("Z",),
}


class Map23Environment(MapEnvironment):
    map_id = "MAP-23"
    title = "迷雾中的遗迹"
    world = "jungle"
    level = "中等"
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "to"})},
        "scout": {frozenset({"tool"})},
        "investigate": {frozenset({"tool", "entrance"})},
        "mark": {frozenset({"tool", "choice"})},
        "resupply": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "neighbors",
            "supply_remaining",
            "resupply_cache_available",
            "available_scout_stations",
            "clues_received",
            "searched_false_entrances",
            "agent_marked_candidate",
            "actions_taken",
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        self.node = "A"
        self.true_entrance = VARIANTS[(seed + 2) % len(VARIANTS)]
        self.supply = SUPPLY_INITIAL
        self.resupply_used = False
        self.scouted: list[str] = []
        self.clues: list[dict[str, Any]] = []
        self.searched_false: list[str] = []
        self.marked: str | None = None
        self.final_target: str | None = None
        self._cost = 1

    # ------------------------------------------------------------------ public
    def _neighbors(self) -> dict[str, int]:
        return {
            other: cost
            for edge, cost in EDGES.items()
            if self.node in edge
            for other in edge
            if other != self.node
        }

    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "neighbors": self._neighbors(),
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
            "searched_false_entrances": list(self.searched_false),
            "agent_marked_candidate": self.marked,
            "actions_taken": self.tick_count,
            "goal": (
                "用 14 点补给调查到真入口，且调查扣费后补给必须严格大于 0；"
                "三处侦察各 2 点，A 的补给箱只能用一次。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._cost = 1
        if action.tool == "move":
            return self._move(action)
        if action.tool == "scout":
            return self._scout()
        if action.tool == "investigate":
            return self._investigate(action)
        if action.tool == "mark":
            return self._mark(action)
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
            self._cost = 1
            return "NOT_ADJACENT"
        cost = neighbors[target]
        if not self._spend(cost):
            return "INSUFFICIENT_SUPPLY"
        self.node = str(target)
        if self.supply == 0:
            self._fail("SUPPLY_DEPLETED")
        return f"MOVED:{target}"

    def _scout(self) -> str:
        if self.node not in SCOUT_STATIONS:
            return "SCOUT_NOT_AVAILABLE_HERE"
        if self.node in self.scouted:
            return "SCOUT_ALREADY_USED"
        if not self._spend(SCOUT_COST):
            return "INSUFFICIENT_SUPPLY"
        signal = SIGNALS[self.true_entrance][self.node]
        self.scouted.append(self.node)
        self.clues.append(
            {
                "station": self.node,
                "signal": signal,
                "supports": SIGNAL_SUPPORTS[signal],
            }
        )
        if self.supply == 0:
            self._fail("SUPPLY_DEPLETED")
        return f"SCOUTED:{signal}"

    def _investigate(self, action: V8Action) -> str:
        entrance = action.entrance
        if entrance not in ENTRANCES:
            return "INVALID_ENTRANCE"
        if self.node != entrance:
            return "NOT_AT_ENTRANCE"
        self.final_target = entrance
        if entrance in self.searched_false:
            self._count("REPEATED_INVALID_EXPLORATION")
        cost = INVESTIGATION_COST[entrance]
        if not self._spend(cost):
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
        if self.status is not V8Status.RUNNING:
            return
        if self.supply == 0:
            self._fail("SUPPLY_DEPLETED")
            return
        if self._stranded():
            self._fail("SUPPLY_STRANDED")

    def _stranded(self) -> bool:
        if self.node == "A" and not self.resupply_used:
            return False
        affordable_move = any(
            cost <= self.supply for cost in self._neighbors().values()
        )
        if affordable_move:
            return False
        if self.node in ENTRANCES and INVESTIGATION_COST[self.node] <= self.supply:
            return False
        return True

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "location": self.node,
            "true_entrance": self.true_entrance,
            "supply": self.supply,
            "resupply_used": self.resupply_used,
            "scouted": list(self.scouted),
            "clues": [
                {"station": clue["station"], "signal": clue["signal"]}
                for clue in self.clues
            ],
            "searched_false": list(self.searched_false),
            "marked": self.marked,
            "final_target": self.final_target,
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
            "counters": dict(sorted(self.counters.items())),
        }

    def metrics(self) -> dict[str, Any]:
        reductions = [3 - len(clue["supports"]) for clue in self.clues]
        discoveries = int(self.is_success)
        return {
            "map23.clue_utilization": {
                "numerator": max(reductions, default=0),
                "denominator": 2,
            },
            "map23.cost_per_discovery": (
                (SUPPLY_INITIAL - self.supply) / discoveries if discoveries else None
            ),
            "map23.repeated_invalid_exploration": self.counters.get(
                "REPEATED_INVALID_EXPLORATION", 0
            ),
            "map23.ignored_counterevidence": int(self._ignored_counterevidence()),
        }

    def _ignored_counterevidence(self) -> bool:
        if self.final_target is None:
            return False
        excluded: set[str] = set()
        for clue in self.clues:
            excluded.update(
                entrance
                for entrance in ENTRANCES
                if entrance not in clue["supports"]
            )
        return self.final_target in excluded


ORACLE_CASES: tuple[dict[str, Any], ...] = (
    {
        "trace_id": "river_double_ripples_then_z",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "R"},
            {"tool": "scout"},
            {"tool": "move", "to": "Y"},
            {"tool": "investigate", "entrance": "Y"},
            {"tool": "move", "to": "R"},
            {"tool": "move", "to": "Z"},
            {"tool": "investigate", "entrance": "Z"},
        ],
        "expect_success": True,
    },
    {
        "trace_id": "ridge_unique_signal",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "H"},
            {"tool": "scout"},
            {"tool": "move", "to": "A"},
            {"tool": "resupply"},
            {"tool": "move", "to": "R"},
            {"tool": "move", "to": "Z"},
            {"tool": "investigate", "entrance": "Z"},
        ],
        "expect_success": True,
    },
)


FIXTURES = (
    {
        "name": "river_clue_then_z",
        "seed": 0,
        "actions": list(ORACLE_CASES[0]["actions"]),
        "expect": {
            "map23.clue_utilization": 0.5,
            "map23.cost_per_discovery": 13.0,
            "map23.repeated_invalid_exploration": 0,
            "map23.ignored_counterevidence": 0,
        },
    },
    {
        "name": "ridge_scout_full_reduction",
        "seed": 0,
        "actions": list(ORACLE_CASES[1]["actions"]),
        "expect": {
            "map23.clue_utilization": 1.0,
            "map23.cost_per_discovery": 7.0,
            "map23.repeated_invalid_exploration": 0,
            "map23.ignored_counterevidence": 0,
        },
    },
    {
        "name": "repeat_false_entrance_is_counted",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "R"},
            {"tool": "move", "to": "Y"},
            {"tool": "investigate", "entrance": "Y"},
            {"tool": "investigate", "entrance": "Y"},
        ],
        "expect": {
            "map23.clue_utilization": 0.0,
            "map23.cost_per_discovery": None,
            "map23.repeated_invalid_exploration": 1,
            "map23.ignored_counterevidence": 0,
        },
    },
    {
        "name": "ignoring_single_support_clue",
        "seed": 0,
        "actions": [
            {"tool": "move", "to": "N"},
            {"tool": "scout"},
            {"tool": "move", "to": "Y"},
            {"tool": "investigate", "entrance": "Y"},
        ],
        "expect": {
            "map23.clue_utilization": 1.0,
            "map23.cost_per_discovery": None,
            "map23.repeated_invalid_exploration": 0,
            "map23.ignored_counterevidence": 1,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map23Environment"]
