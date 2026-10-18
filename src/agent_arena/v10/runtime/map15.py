"""MAP-15 V10｜会变化的迷宫：多规律家族、训练/测试分离与规则假设节点（DCR-V10-04）。

与 V8 的差异：

- 规则不再写进 goal。目标门色 = 墙色沿公开色环前进 ``offset[tick mod period]`` 格；
  ``period``/``offsets`` 由环境 seed 选定的家族决定（隐藏，密封），共 6 个家族、10 个 seed；
- 每个 seed 的墙色、门的槽位排列都不同；训练区 A/B/C 的墙色只用两种颜色，测试区 T
  的两道门 T1/T2 使用训练中**从未出现**的另两种墙色；
- 公开档案 ``training_sample_log`` 预置 2 条往期样例（连续 2 个 tick），
  训练区每次选门（对或错）都追加一条样例；训练区选错只耗 1 tick、不扣资源；
- 进入 T 前必须 ``record_rule(rule_id="period=P;offsets=a,b[,c]")``，环境只校验格式、
  不反馈对错；
- T 区：T1、T2 在连续两个 tick 上结算；选错扣 1 次容错且**不推进 tick**，``wait`` 在 T
  被拒且不推进 tick；第 2 次错误失败。V8 的“错一次 → 相位翻转 → 同槽必中”自愈被消除；
- ``predict_transition(answer)`` 在 T 可选，预测下一次选门的目标色，单独计分。
"""

from __future__ import annotations

import random
import re
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

WHEEL = ("red", "gold", "blue", "green")
TRAINING_AREAS = ("A", "B", "C")
TEST_GATES = ("T1", "T2")
NEXT_AREA = {"A": "B", "B": "C", "C": "T1", "T1": "T2", "T2": "EXIT"}
TEST_WRONG_LIMIT = 2
#: 两条连续 tick 的档案样例只能确定周期 2 的规律；周期 3 的第三个偏移必须靠训练区证据。
ARCHIVE_SAMPLES = 2
RULE_PATTERN = re.compile(r"^period=([23]);offsets=([0-3](?:,[0-3]){1,2})$")


@dataclass(frozen=True)
class Family:
    name: str
    period: int
    offsets: tuple[int, ...]

    @property
    def rule_id(self) -> str:
        return f"period={self.period};offsets={','.join(str(item) for item in self.offsets)}"


FAMILIES = {
    "parity_complement": Family("parity_complement", 2, (0, 2)),
    "parity_next": Family("parity_next", 2, (0, 1)),
    "parity_prev": Family("parity_prev", 2, (0, 3)),
    "parity_inverted": Family("parity_inverted", 2, (2, 0)),
    "triad_step": Family("triad_step", 3, (0, 1, 3)),
    "triad_back": Family("triad_back", 3, (0, 2, 1)),
}
#: 预登记 seed → 家族；每个家族至少出现一次。
FAMILY_BY_SEED = {
    0: "parity_complement",
    1: "parity_next",
    2: "triad_step",
    3: "parity_prev",
    4: "parity_inverted",
    5: "triad_back",
    6: "parity_complement",
    7: "triad_step",
    8: "parity_next",
    9: "parity_inverted",
}


def target_color(family: Family, wall: str, tick: int) -> str:
    offset = family.offsets[tick % family.period]
    return WHEEL[(WHEEL.index(wall) + offset) % len(WHEEL)]


def parse_rule(rule_id: str) -> Family | None:
    match = RULE_PATTERN.match(rule_id.strip())
    if not match:
        return None
    period = int(match.group(1))
    offsets = tuple(int(item) for item in match.group(2).split(","))
    if len(offsets) != period:
        return None
    return Family("hypothesis", period, offsets)


@dataclass(frozen=True)
class Layout:
    family: Family
    walls: dict[str, str]
    doors: dict[str, tuple[str, ...]]
    archive_base_tick: int
    archive_walls: tuple[str, ...]


def build_layout(seed: int) -> Layout:
    rng = random.Random(f"map15-v10|{seed}")
    family = FAMILIES[FAMILY_BY_SEED[seed]]
    wheel = list(WHEEL)
    rng.shuffle(wheel)
    seen, unseen = wheel[:2], wheel[2:]
    walls = {"A": seen[0], "B": seen[1], "C": seen[0], "T1": unseen[0], "T2": unseen[1]}
    doors: dict[str, tuple[str, ...]] = {}
    for area in TRAINING_AREAS:
        needed = sorted({target_color(family, walls[area], tick) for tick in range(6)})
        fill = [color for color in WHEEL if color not in needed]
        rng.shuffle(fill)
        options = needed + fill[: max(0, 3 - len(needed))]
        rng.shuffle(options)
        doors[area] = tuple(options)
    for gate in TEST_GATES:
        options = list(WHEEL)
        rng.shuffle(options)
        doors[gate] = tuple(options)
    archive_walls = tuple(seen[index % 2] for index in range(ARCHIVE_SAMPLES))
    return Layout(family, walls, doors, rng.randint(0, 5), archive_walls)


class Map15V10Environment(V10Map):
    map_id = "MAP-15"
    title = "会变化的迷宫"
    world = "pyramid"
    level = "困难"
    RULE_VERSION = "v10.map15.1"
    SEED_SPACE = tuple(sorted(FAMILY_BY_SEED))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "choose_door": {frozenset({"tool", "slot_index"})},
        "inspect_symbols": {frozenset({"tool", "area"})},
        "record_rule": {frozenset({"tool", "rule_id", "supporting_sample_ids"})},
        "predict_transition": {frozenset({"tool", "answer"})},
        "wait": {frozenset({"tool", "ticks"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "area",
            "current_tick",
            "color_wheel",
            "inspected_current_area",
            "current_wall_color_if_inspected",
            "current_door_colors_if_inspected",
            "training_sample_log",
            "recorded_rule_hypothesis",
            "pending_prediction",
            "test_wrong_attempts",
            "test_wrong_attempts_remaining",
            "gate_open",
            "goal",
        }
    )
    PRIMARY_METRIC = "map15.v10.test_gate_first_try_accuracy"
    METRIC_SPECS = (
        MetricSpec(
            "map15.v10.test_gate_first_try_accuracy",
            "primary",
            "higher",
            "T1/T2 首次选择即正确的门数 / 已首次尝试的测试门数",
            "已尝试的测试门（1–2）",
            censored_rule="进入 T 前截尾 → CENSORED；进入 T 前失败 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map15.v10.rule_generalization",
            "primary",
            "higher",
            "recorded rule (period, offsets) == 密封家族",
            "记录过规则的局（1）",
            zero_denominator="从未记录 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map15.v10.prediction_accuracy",
            "secondary",
            "higher",
            "显式 predict_transition 正确数 / 已结算预测数",
            "已结算预测",
        ),
        MetricSpec(
            "map15.v10.sample_phase_coverage",
            "secondary",
            "higher",
            "record_rule 引用样例覆盖真实周期相位数 / period",
            "记录过规则的局",
        ),
        MetricSpec(
            "map15.v10.training_errors",
            "diagnostic",
            "none",
            "训练区错误选门次数（探索成本）",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map15.v10.test_errors",
            "guardrail",
            "lower",
            "测试区错误选门次数",
            "—",
            unit="count",
            valid_range=(0.0, 2.0),
        ),
        MetricSpec(
            "map15.v10.exploration_ticks",
            "diagnostic",
            "lower",
            "进入 T1 时的 tick",
            "进入 T1 的局",
            unit="ticks",
            valid_range=(0.0, 200.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.layout = build_layout(seed)
        self.family = self.layout.family
        self.area = "A"
        self.inspected_area: str | None = None
        self.samples: list[dict[str, Any]] = []
        self.recorded_rule: dict[str, Any] | None = None
        self.pending_prediction: str | None = None
        self.predictions: list[bool] = []
        self.training_errors = 0
        self.test_errors = 0
        self.test_first_try: dict[str, bool] = {}
        self.entered_test_tick: int | None = None
        self.gate_open = False
        self._cost = 0
        for index, wall in enumerate(self.layout.archive_walls):
            tick = self.layout.archive_base_tick + index
            self.samples.append(
                {
                    "sample_id": f"ARCHIVE_{index + 1}",
                    "source": "archive",
                    "tick": tick,
                    "wall_color": wall,
                    "door_color": target_color(self.family, wall, tick),
                    "result": "passed",
                }
            )

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "training_walls": [self.layout.walls[area] for area in TRAINING_AREAS],
            "test_walls": [self.layout.walls[gate] for gate in TEST_GATES],
            "doors": {area: list(colors) for area, colors in self.layout.doors.items()},
            "archive_base_tick": self.layout.archive_base_tick,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {"family": self.family.name, "rule_id": self.family.rule_id}

    def public_rules(self) -> tuple[str, ...]:
        return (
            "区域依次为 A → B → C（训练区）→ T1 → T2（测试区）→ EXIT；每区有若干门，"
            "choose_door(slot_index) 选第几扇门（从 1 开始）。",
            "色环顺序 red → gold → blue → green → red。每次选门时，正确门的颜色 = 当前墙色沿色环"
            "前进 k 格；k 只取决于当前 tick 除以某个周期的余数，周期为 2 或 3，k ∈ {0,1,2,3}。"
            "这条规律在所有区域相同，但具体周期与各余数下的 k 未知，需要从样例推断。",
            "inspect_symbols(area=当前区域) 不耗 tick，显示墙色与各门颜色（按槽位顺序）。",
            "training_sample_log 含 2 条往期档案样例；在训练区每次选门（对或错）都追加一条样例。"
            "训练区选错：耗 1 tick、留在原区、不扣容错。选对：耗 1 tick、前进一区。",
            "离开 C 进入测试区前，必须先 record_rule(rule_id, supporting_sample_ids)，rule_id 格式"
            " 'period=P;offsets=k0,k1[,k2]'（offsets 依次对应余数 0,1,2）；环境只校验格式，不告诉"
            "对错。supporting_sample_ids 只能引用 training_sample_log 中的 id。",
            "测试区：T1 与 T2 的墙色在训练中从未出现。选对耗 1 tick 前进；选错不耗 tick、扣 1 次"
            f"容错，共 {TEST_WRONG_LIMIT} 次错误即失败；测试区内 wait 被拒且不推进 tick。",
            "predict_transition(answer=颜色) 只在测试区可用、不耗 tick，"
            "预测下一次选门时的正确门色，"
            "单独计分。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        inspecting = self.inspected_area == self.area and self.area in self.layout.walls
        return {
            "area": self.area,
            "current_tick": self.tick_count,
            "color_wheel": list(WHEEL),
            "inspected_current_area": inspecting,
            "current_wall_color_if_inspected": (
                self.layout.walls[self.area] if inspecting else None
            ),
            "current_door_colors_if_inspected": (
                list(self.layout.doors[self.area]) if inspecting else None
            ),
            "training_sample_log": [dict(sample) for sample in self.samples],
            "recorded_rule_hypothesis": (
                None if self.recorded_rule is None else dict(self.recorded_rule)
            ),
            "pending_prediction": self.pending_prediction,
            "test_wrong_attempts": self.test_errors,
            "test_wrong_attempts_remaining": max(0, TEST_WRONG_LIMIT - self.test_errors),
            "gate_open": self.gate_open,
            "goal": "从样例推断门色随时间变化的规律，记录假设，并在测试区连续通过 T1 与 T2。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._cost = 0
        tool = action.tool
        if tool == "inspect_symbols":
            if action.area != self.area or self.area not in self.layout.walls:
                return "INSPECTION_OUT_OF_SCOPE"
            self.inspected_area = self.area
            return "CURRENT_WALL_AND_DOORS_VISIBLE"
        if tool == "record_rule":
            return self._record_rule(action)
        if tool == "predict_transition":
            if self.area not in TEST_GATES:
                return "PREDICTION_OUT_OF_SCOPE"
            if action.answer not in WHEEL:
                return "UNKNOWN_COLOR"
            self.pending_prediction = action.answer
            return "PREDICTION_RECORDED"
        if tool == "wait":
            if self.area in TEST_GATES:
                return "WAIT_FORBIDDEN_IN_TEST"
            self._cost = int(action.ticks or 1)
            return "WAITED"
        if tool == "choose_door":
            return self._choose(action)
        return "ACTION_NOT_ALLOWED"

    def _record_rule(self, action: V8Action) -> str:
        rule_id = str(action.rule_id or "")
        support = list(action.supporting_sample_ids or [])
        if parse_rule(rule_id) is None:
            return "RULE_FORMAT_INVALID"
        known = {sample["sample_id"] for sample in self.samples}
        if not support or any(item not in known for item in support):
            return "UNKNOWN_SAMPLE"
        self.recorded_rule = {"rule_id": rule_id.strip(), "supporting_sample_ids": support}
        return "RULE_RECORDED_WITHOUT_CORRECTNESS_FEEDBACK"

    def _choose(self, action: V8Action) -> str:
        if self.area not in self.layout.doors:
            return "ALREADY_EXITED"
        doors = self.layout.doors[self.area]
        slot = int(action.slot_index or 0)
        if slot < 1 or slot > len(doors):
            return "INVALID_SLOT"
        if self.area == "C" and self.recorded_rule is None:
            return "RULE_RECORD_REQUIRED"
        chosen = doors[slot - 1]
        target = target_color(self.family, self.layout.walls[self.area], self.tick_count)
        if self.pending_prediction is not None and self.area in TEST_GATES:
            self.predictions.append(self.pending_prediction == target)
            self.pending_prediction = None
        if self.area in TRAINING_AREAS:
            self._cost = 1
            self.samples.append(
                {
                    "sample_id": f"SAMPLE_{self.area}_T{self.tick_count}_{len(self.samples) + 1}",
                    "source": "training",
                    "tick": self.tick_count,
                    "wall_color": self.layout.walls[self.area],
                    "door_color": chosen,
                    "result": "passed" if chosen == target else "failed",
                }
            )
            if chosen != target:
                self.training_errors += 1
                return "INVALID_TRANSITION"
            return self._advance()
        # 测试区
        gate = self.area
        first = gate not in self.test_first_try
        if chosen != target:
            if first:
                self.test_first_try[gate] = False
            self.test_errors += 1
            if self.test_errors >= TEST_WRONG_LIMIT:
                self._fail("TEST_WRONG_LIMIT")
            return "INVALID_TRANSITION"
        if first:
            self.test_first_try[gate] = True
        self._cost = 1
        return self._advance()

    def _advance(self) -> str:
        passed = self.area
        self.area = NEXT_AREA[passed]
        self.inspected_area = None
        if self.area == "T1":
            self.entered_test_tick = self.tick_count + 1
        if self.area == "EXIT":
            self.gate_open = True
            self._succeed("GATE_OPENED")
            return "GATE_OPENED"
        return f"PASSED_FORWARD_TO_{self.area}"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    def _invalid_action(self) -> str:
        self._cost = 0 if self.area in TEST_GATES else 1
        return "INVALID_ACTION_SCHEMA"

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "area": self.area,
            "tick": self.tick_count,
            "recorded_rule": self.recorded_rule,
            "training_errors": self.training_errors,
            "test_errors": self.test_errors,
            "test_first_try": dict(self.test_first_try),
            "predictions": list(self.predictions),
            "truth_seal": self.truth_seal(),
        }

    def _recorded_family(self) -> Family | None:
        if self.recorded_rule is None:
            return None
        return parse_rule(str(self.recorded_rule["rule_id"]))

    def v10_metrics(self) -> dict[str, MValue]:
        running = not self.is_terminal or self.status.value == "step_limit_reached"
        if self.test_first_try:
            accuracy = ratio(
                sum(1 for ok in self.test_first_try.values() if ok), len(self.test_first_try)
            )
        elif running:
            accuracy = censored("进入测试区前截尾")
        else:
            accuracy = not_applicable("未进入测试区")
        recorded = self._recorded_family()
        if recorded is None:
            generalization = not_applicable("未记录规则")
            coverage = not_applicable("未记录规则")
        else:
            generalization = valid(
                int(
                    recorded.period == self.family.period
                    and recorded.offsets == self.family.offsets
                )
            )
            assert self.recorded_rule is not None
            cited = set(self.recorded_rule["supporting_sample_ids"])
            phases = {
                sample["tick"] % self.family.period
                for sample in self.samples
                if sample["sample_id"] in cited and sample["result"] == "passed"
            }
            coverage = ratio(len(phases), self.family.period)
        return {
            "map15.v10.test_gate_first_try_accuracy": accuracy,
            "map15.v10.rule_generalization": generalization,
            "map15.v10.prediction_accuracy": ratio(sum(self.predictions), len(self.predictions)),
            "map15.v10.sample_phase_coverage": coverage,
            "map15.v10.training_errors": valid(self.training_errors),
            "map15.v10.test_errors": valid(self.test_errors),
            "map15.v10.exploration_ticks": (
                valid(self.entered_test_tick)
                if self.entered_test_tick is not None
                else not_applicable("未进入测试区")
            ),
        }

    def mechanism_triggered(self) -> bool:
        """进入测试区且两道测试门都在非零偏移相位下结算过至少一道。"""

        if self.entered_test_tick is None:
            return False
        ticks = (self.entered_test_tick, self.entered_test_tick + 1)
        return any(self.family.offsets[tick % self.family.period] != 0 for tick in ticks)


__all__ = [
    "FAMILIES",
    "FAMILY_BY_SEED",
    "Family",
    "Map15V10Environment",
    "WHEEL",
    "build_layout",
    "parse_rule",
    "target_color",
]
