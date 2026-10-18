"""MAP-13 V10｜四神之门：记录成为出手前提、多规则实例与指标口径分离（DCR-V10-15）。

V9 的两条根因：

1. **`record_constraint` 不参与任何指标**——跳过全部记录的 15 步路线仍 `ratio=5/5`、
   `GATE_OPENED`；“观察与记录是两件事”这一构念在接口上不成立；
2. **`illegal_door_attempts` 把“未成型试排”和“错排”混在一个计数里**（V9 判为
   `METRIC_DEFECT`），且 `constraint_satisfaction_ratio` 在从未试排时也给 0/5。

V10 的修复：

- `set_trial_layout` 要求**至少记录过 1 条约束**，`verify_layout` 要求**至少记录过 4 条**
  （`CONSTRAINTS_NOT_RECORDED`）——记录从“可选动作”变成出手前提；
- 4 个预登记实例：符号集、目标排列与四条谓词的符号角色都不同（每个实例的唯一解由
  24 种排列暴力筛选保证），不是同一道题换名字；
- 方向钉保留 **OPTIONAL**：不读它也能开门，但 `constraint_satisfaction_ratio` 上限
  为 4/5——用连续质量量而不是删掉挑战；
- 指标口径分离：`illegal_verify_without_layout`（未成型试排）与 `wrong_layout_attempts`
  （错排）分开计数；`constraint_satisfaction_ratio` 在从未试排时是 `NOT_APPLICABLE`。
"""

from __future__ import annotations

from itertools import permutations
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

ROOMS = ("C", "N", "E", "S", "W")
SLOTS = ("N", "E", "S", "W")
ROOM_ORDER = {"C": -1, "N": 0, "E": 1, "S": 2, "W": 3}
MAX_INCORRECT_ATTEMPTS = 3
EDGES: dict[str, tuple[str, str]] = {
    f"C_{room}": ("C", room) for room in SLOTS
}


class Variant13:
    def __init__(self, seed: int, symbols: tuple[str, str, str, str]) -> None:
        self.seed = seed
        self.symbols = symbols
        sun, eye, reed, armor = symbols
        self.roles = {"sun": sun, "eye": eye, "reed": reed, "armor": armor}
        self.target = self._unique_solution()
        self.clues = {
            "ORIENTATION_ORDER": (
                "C",
                "从北室起，按 N→E→S→W 顺时针读为槽位 1 至 4；右侧表示编号更大，"
                "相邻表示编号差 1。",
            ),
            "N_SUN_NOT_END": ("N", f"{sun}神不得居于两端。"),
            "E_EYE_RIGHT_OF_REED": ("E", f"{eye}神位于{reed}神右侧。"),
            "S_ARMOR_ADJACENT_TO_SUN": ("S", f"{armor}神须与{sun}神相邻。"),
            "W_REED_NOT_FIRST": ("W", f"{reed}神不得居于首槽。"),
        }

    def satisfies(self, layout: dict[str, str]) -> bool:
        position = {slot: index + 1 for index, slot in enumerate(SLOTS)}
        by_symbol = {symbol: position[slot] for slot, symbol in layout.items()}
        sun = by_symbol[self.roles["sun"]]
        eye = by_symbol[self.roles["eye"]]
        reed = by_symbol[self.roles["reed"]]
        armor = by_symbol[self.roles["armor"]]
        return (
            sun not in (1, 4)
            and eye > reed
            and abs(armor - sun) == 1
            and reed != 1
        )

    def _unique_solution(self) -> dict[str, str]:
        found: list[dict[str, str]] = []
        for order in permutations(self.symbols):
            layout = dict(zip(SLOTS, order, strict=True))
            if self.satisfies(layout):
                found.append(layout)
        if len(found) != 1:  # pragma: no cover - 预登记实例都唯一
            raise ValueError(f"seed {self.seed} 的约束不唯一：{len(found)}")
        return found[0]


VARIANTS: dict[int, Variant13] = {
    0: Variant13(0, ("日", "眼", "芦", "甲")),
    1: Variant13(1, ("焰", "镜", "苇", "盾")),
    2: Variant13(2, ("星", "瞳", "穗", "铠")),
    3: Variant13(3, ("雷", "珠", "藤", "盔")),
}


class Map13V10Environment(V10Map):
    map_id = "MAP-13"
    title = "四神之门"
    world = "pyramid"
    level = "简单"
    RULE_VERSION = "v10.map13.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    EDGES = EDGES
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "edge_id"})},
        "read_inscription": {frozenset({"tool", "room"})},
        "record_constraint": {frozenset({"tool", "clue_id"})},
        "set_trial_layout": {frozenset({"tool", "layout_by_room"})},
        "verify_layout": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "visible_neighbors",
            "current_tick",
            "symbols",
            "observed_clues",
            "recorded_clue_ids",
            "required_recorded_for_layout",
            "required_recorded_for_verify",
            "trial_layout",
            "incorrect_attempts",
            "remaining_incorrect_attempts",
            "gate_open",
            "goal",
        }
    )
    PRIMARY_METRIC = "map13.v10.constraint_satisfaction_ratio"
    METRIC_SPECS = (
        MetricSpec(
            "map13.v10.constraint_satisfaction_ratio",
            "primary",
            "higher",
            "（最后一次试排满足的房间谓词数 + 方向钉是否已读）/ 5",
            "试排过的局（1）",
            zero_denominator="从未试排 → NOT_APPLICABLE",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map13.v10.correct_sequence",
            "secondary",
            "higher",
            "最后一次试排是否等于唯一解",
            "试排过的局（1）",
            zero_denominator="从未试排 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map13.v10.recorded_clues",
            "secondary",
            "higher",
            "已记录的约束条数 / 5",
            "5",
        ),
        MetricSpec(
            "map13.v10.wrong_layout_attempts",
            "guardrail",
            "lower",
            "错排导致的 STATE_RESET 次数",
            "—",
            unit="count",
            valid_range=(0.0, 10.0),
        ),
        MetricSpec(
            "map13.v10.illegal_verify_without_layout",
            "guardrail",
            "lower",
            "未成型试排就 verify 的次数",
            "—",
            unit="count",
            valid_range=(0.0, 20.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.position = "C"
        self.items = []
        self.observed: list[str] = []
        self.recorded: list[str] = []
        self.trial_layout: dict[str, str] | None = None
        self.last_attempted: dict[str, str] | None = None
        self.incorrect_attempts = 0
        self.wrong_layout_attempts = 0
        self.illegal_without_layout = 0
        self.gate_open = False

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "symbols": list(self.variant.symbols),
            "slots": list(SLOTS),
            "clue_count": len(self.variant.clues),
            "max_incorrect_attempts": MAX_INCORRECT_ATTEMPTS,
            "required_recorded_for_layout": 1,
            "required_recorded_for_verify": 4,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "target_layout": dict(self.variant.target),
            "roles": dict(self.variant.roles),
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "星形拓扑：营地 C 直连 N/E/S/W 四间外室，外室之间没有直连。",
            "read_inscription(room) 只能读**自己所在**的房间；每条碑文只能读一次同一内容。",
            "record_constraint(clue_id) 只能在 C，且只能记录**已读**的碑文。",
            "set_trial_layout 在 C，必须恰含 N/E/S/W 四槽且四符号各一次；"
            "**至少记录过 1 条约束**才能试排。",
            "verify_layout 在 C；**至少记录过 4 条约束**才能验证（观察≠记录）。",
            "错排会清空试排；累计 3 次错排即失败。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        neighbours = sorted(
            (
                (second if first == self.position else first)
                for edge_id, (first, second) in self.EDGES.items()
                if self.position in (first, second)
            ),
            key=lambda room: ROOM_ORDER.get(room, 99),
        )
        return {
            "location": self.position,
            "visible_edges": [
                edge_id for edge_id, pair in sorted(self.EDGES.items()) if self.position in pair
            ],
            "visible_neighbors": neighbours,
            "current_tick": self.tick_count,
            "symbols": list(self.variant.symbols),
            "observed_clues": [
                {"clue_id": clue_id, "text": self.variant.clues[clue_id][1]}
                for clue_id in self.observed
            ],
            "recorded_clue_ids": list(self.recorded),
            "required_recorded_for_layout": 1,
            "required_recorded_for_verify": 4,
            "trial_layout": dict(self.trial_layout) if self.trial_layout else None,
            "incorrect_attempts": self.incorrect_attempts,
            "remaining_incorrect_attempts": max(
                0, MAX_INCORRECT_ATTEMPTS - 1 - self.incorrect_attempts
            ),
            "gate_open": self.gate_open,
            "goal": "读碑文、**记录下来**、排出唯一排列并验证开门。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "move":
            return self._move(action)
        if tool == "read_inscription":
            return self._read(action)
        if tool == "record_constraint":
            return self._record(action)
        if tool == "set_trial_layout":
            return self._set_layout(action)
        if tool == "verify_layout":
            return self._verify()
        return "ACTION_NOT_ALLOWED"

    def _move(self, action: V8Action) -> str:
        edge = self.EDGES.get(action.edge_id or "")
        if edge is None or self.position not in edge:
            return "INVALID_EDGE"
        self.position = edge[1] if edge[0] == self.position else edge[0]
        return f"ARRIVED:{self.position}"

    def _read(self, action: V8Action) -> str:
        room = action.room
        if room not in ROOMS or room != self.position:
            return "INVALID_LOCATION"
        clue_id = next(
            (key for key, (home, _text) in self.variant.clues.items() if home == room), None
        )
        if clue_id is None:  # pragma: no cover
            return "NO_INSCRIPTION"
        if clue_id not in self.observed:
            self.observed.append(clue_id)
        return f"inscription:{self.variant.clues[clue_id][1]}"

    def _record(self, action: V8Action) -> str:
        if self.position != "C":
            return "INVALID_LOCATION"
        clue_id = action.clue_id
        if clue_id is None or clue_id not in self.variant.clues:
            return "CLUE_NOT_OBSERVED"
        if clue_id not in self.observed:
            return "CLUE_NOT_OBSERVED"
        if clue_id in self.recorded:
            return "CLUE_ALREADY_RECORDED"
        self.recorded.append(clue_id)
        return f"recorded:{clue_id}"

    def _set_layout(self, action: V8Action) -> str:
        if self.position != "C":
            return "INVALID_LOCATION"
        if len(self.recorded) < 1:
            return "CONSTRAINTS_NOT_RECORDED"
        layout = action.layout_by_room
        if not isinstance(layout, dict) or set(layout) != set(SLOTS):
            return "INVALID_LAYOUT"
        if sorted(str(layout[slot]) for slot in SLOTS) != sorted(self.variant.symbols):
            return "INVALID_LAYOUT"
        self.trial_layout = {str(slot): str(layout[slot]) for slot in SLOTS}
        return "trial_layout_set"

    def _verify(self) -> str:
        if self.position != "C":
            return "INVALID_LOCATION"
        layout = self.trial_layout
        if layout is None:
            self.illegal_without_layout += 1
            return "ILLEGAL_DOOR"
        if len(self.recorded) < 4:
            return "CONSTRAINTS_NOT_RECORDED"
        self.last_attempted = dict(layout)
        if layout == self.variant.target:
            self.gate_open = True
            self._succeed("GATE_OPENED")
            return "GATE_OPENED"
        self.incorrect_attempts += 1
        self.wrong_layout_attempts += 1
        self.trial_layout = None
        if self.incorrect_attempts >= MAX_INCORRECT_ATTEMPTS:
            self._fail("INCORRECT_ATTEMPT_LIMIT")
        return "STATE_RESET"

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "position": self.position,
            "tick": self.tick_count,
            "observed": list(self.observed),
            "recorded": list(self.recorded),
            "trial_layout": dict(self.trial_layout) if self.trial_layout else None,
            "last_attempted": dict(self.last_attempted) if self.last_attempted else None,
            "incorrect_attempts": self.incorrect_attempts,
            "wrong_layout_attempts": self.wrong_layout_attempts,
            "illegal_without_layout": self.illegal_without_layout,
            "gate_open": self.gate_open,
            "truth_seal": self.truth_seal(),
        }

    def _layout_for_metrics(self) -> dict[str, str] | None:
        return self.last_attempted or self.trial_layout

    def _satisfied(self) -> int:
        layout = self._layout_for_metrics()
        if layout is None:
            return 0
        position = {slot: index + 1 for index, slot in enumerate(SLOTS)}
        by_symbol = {symbol: position[slot] for slot, symbol in layout.items()}
        sun = by_symbol[self.variant.roles["sun"]]
        eye = by_symbol[self.variant.roles["eye"]]
        reed = by_symbol[self.variant.roles["reed"]]
        armor = by_symbol[self.variant.roles["armor"]]
        satisfied = 0
        if sun in (2, 3):
            satisfied += 1
        if eye > reed:
            satisfied += 1
        if abs(armor - sun) == 1:
            satisfied += 1
        if reed != 1:
            satisfied += 1
        if "ORIENTATION_ORDER" in self.observed:
            satisfied += 1
        return satisfied

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        layout = self._layout_for_metrics()
        if running:
            satisfaction: MValue = censored("截尾")
            correct: MValue = censored("截尾")
        elif layout is None:
            satisfaction = not_applicable("从未试排")
            correct = not_applicable("从未试排")
        else:
            satisfaction = ratio(self._satisfied(), 5)
            correct = valid(int(layout == self.variant.target))
        return {
            "map13.v10.constraint_satisfaction_ratio": satisfaction,
            "map13.v10.correct_sequence": correct,
            "map13.v10.recorded_clues": ratio(len(self.recorded), len(self.variant.clues)),
            "map13.v10.wrong_layout_attempts": valid(self.wrong_layout_attempts),
            "map13.v10.illegal_verify_without_layout": valid(self.illegal_without_layout),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：真的把碑文记录下来（≥1 条）。"""

        return len(self.recorded) >= 1


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：读 C 的方向钉与四室碑文，逐条记录，排出唯一解并验证。"""

    variant = VARIANTS[environment_seed]
    actions: list[dict[str, Any]] = [
        {"tool": "read_inscription", "room": "C"},
        {"tool": "record_constraint", "clue_id": "ORIENTATION_ORDER"},
    ]
    for slot, clue_id in (
        ("N", "N_SUN_NOT_END"),
        ("E", "E_EYE_RIGHT_OF_REED"),
        ("S", "S_ARMOR_ADJACENT_TO_SUN"),
        ("W", "W_REED_NOT_FIRST"),
    ):
        actions.append({"tool": "move", "edge_id": f"C_{slot}"})
        actions.append({"tool": "read_inscription", "room": slot})
        actions.append({"tool": "move", "edge_id": f"C_{slot}"})
        actions.append({"tool": "record_constraint", "clue_id": clue_id})
    actions.append(
        {"tool": "set_trial_layout", "layout_by_room": dict(variant.target)}
    )
    actions.append({"tool": "verify_layout"})
    return actions


__all__ = [
    "EDGES",
    "MAX_INCORRECT_ATTEMPTS",
    "Map13V10Environment",
    "SLOTS",
    "VARIANTS",
    "Variant13",
    "oracle_actions",
]
