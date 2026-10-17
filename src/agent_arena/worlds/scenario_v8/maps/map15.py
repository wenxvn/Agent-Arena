"""MAP-15｜会变化的迷宫：四色互补规则、奇偶相位切换与未见状态迁移。

本图与同世界另两图的机制差异：MAP-13 的碑文约束静态且全真；MAP-14 的规则静态、难点
是不可靠证词与问询预算；本图没有证词，规则本身随全局 tick 奇偶切换——偶数 tick 目标色
等于墙符号色，奇数 tick 等于其互补色（红↔蓝、金↔绿），同一面墙在不同相位要求不同门。
玩家须从 A/B/C 三间训练室的成功样例迁移到 T 的四色未见布局。

动作契约：
- ``choose_door{slot_index}``：按动作开始时的 tick 判定；通过则前进 A→B→C→T→EXIT，
  错误留在原区域、扣 1 枚资源并推进 1 tick。
- ``inspect_symbols{area}``：0 tick，只公开当前区域墙色与临时槽位门色。
- ``record_rule{rule_id, supporting_sample_ids}``：0 tick，只记录玩家假设，不判对错。
- ``predict_transition{answer}``：0 tick，只在 T 可用，提交“当前 tick 目标门色”的预测；
  下一次 T 的 ``choose_door`` 结算该预测。若整局没有显式预测，则用 T 的首次选择作为
  “未见状态预测”代理（与 V7 卡片一致）。

指标口径（与 V7 卡片一致）：
- ``unseen_transition_accuracy``：已结算的 T 预测中正确数 / 已结算预测数；显式预测优先，
  否则以 T 首次选择为代理；未进入 T 记 0/0（N/A）。
- ``probes_to_target``：成功前的 ``choose_door`` 次数；失败局按卡片记 N/A（``None``）。
- ``invalid_transitions``：错误门选择次数，结果码 ``INVALID_TRANSITION``。
- ``loop_states``：同一区域、同一动作前奇偶下重复出现错误选择的次数。
- ``reset_losses``：每次错误同时损失 1 枚资源与 1 个额外 tick，故为
  ``资源损失 + 额外 tick = 2 × 错误次数``；资源先耗尽时优先 ``RESOURCE_DEPLETED``。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action, V8Status

AREAS = ("A", "B", "C", "T")
NEXT_AREA = {"A": "B", "B": "C", "C": "T", "T": "EXIT"}
WALLS = {"A": "red", "B": "red", "C": "gold", "T": "gold"}
DOORS = {
    "A": ("red", "blue", "gold"),
    "B": ("green", "blue", "red"),
    "C": ("blue", "gold", "green"),
    "T": ("gold", "red", "green", "blue"),
}
COLORS = ("red", "blue", "gold", "green")
COMPLEMENT = {"red": "blue", "blue": "red", "gold": "green", "green": "gold"}
INITIAL_RESOURCES = 4
TEST_WRONG_LIMIT = 2


class Map15Environment(MapEnvironment):
    map_id = "MAP-15"
    title = "会变化的迷宫"
    world = "pyramid"
    level = "困难"
    SHAPES: dict[str, set[frozenset[str]]] = {
        "choose_door": {frozenset({"tool", "slot_index"})},
        "inspect_symbols": {frozenset({"tool", "area"})},
        "record_rule": {frozenset({"tool", "rule_id", "supporting_sample_ids"})},
        "predict_transition": {frozenset({"tool", "answer"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "area",
            "current_tick",
            "current_tick_parity",
            "inspected_current_area",
            "current_wall_symbol_color_if_inspected",
            "current_door_colors_in_ephemeral_slot_order_if_inspected",
            "wrong_attempt_resources",
            "test_wrong_attempts",
            "test_wrong_attempts_remaining",
            "training_sample_log",
            "recorded_rule_hypothesis",
            "gate_open",
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        del seed
        self.area = "A"
        self.items = []
        self.resources = INITIAL_RESOURCES
        self.test_errors = 0
        self.inspected_area: str | None = None
        self.samples: list[dict[str, Any]] = []
        self.sample_ids: set[str] = set()
        self.attempts_by_area: dict[str, int] = {area: 0 for area in AREAS}
        self.recorded_rule: dict[str, Any] | None = None
        self.door_choices = 0
        self.invalid_transitions = 0
        self.resource_losses = 0
        self.loop_states = 0
        self._wrong_parities: set[tuple[str, int]] = set()
        self.predictions: list[dict[str, Any]] = []
        self.pending_prediction: dict[str, Any] | None = None
        self.t_first_proxy_pending = False
        self.gate_open = False

    # ------------------------------------------------------------------ public
    def _target_color(self) -> str:
        wall = WALLS[self.area]
        return wall if self.tick_count % 2 == 0 else COMPLEMENT[wall]

    def _public(self) -> dict[str, Any]:
        inspecting = self.inspected_area == self.area and self.area in AREAS
        return {
            "area": self.area,
            "current_tick": self.tick_count,
            "current_tick_parity": "even" if self.tick_count % 2 == 0 else "odd",
            "inspected_current_area": inspecting,
            "current_wall_symbol_color_if_inspected": (
                WALLS[self.area] if inspecting and self.area in WALLS else None
            ),
            "current_door_colors_in_ephemeral_slot_order_if_inspected": (
                list(DOORS[self.area]) if inspecting and self.area in DOORS else None
            ),
            "wrong_attempt_resources": self.resources,
            "test_wrong_attempts": self.test_errors,
            "test_wrong_attempts_remaining": max(0, TEST_WRONG_LIMIT - self.test_errors),
            "training_sample_log": [dict(sample) for sample in self.samples],
            "recorded_rule_hypothesis": (
                None if self.recorded_rule is None else dict(self.recorded_rule)
            ),
            "gate_open": self.gate_open,
            "goal": "从 A/B/C 归纳“偶数同色、奇数互补”的规则，并在 T 通过四色门。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "inspect_symbols":
            if action.area != self.area or self.area not in AREAS:
                return "INSPECTION_OUT_OF_SCOPE"
            self.inspected_area = self.area
            return "CURRENT_WALL_AND_DOORS_VISIBLE"
        if tool == "record_rule":
            return self._record_rule(action)
        if tool == "predict_transition":
            return self._predict(action)
        if tool == "choose_door":
            return self._choose_door(action)
        return "ACTION_NOT_ALLOWED"

    def _record_rule(self, action: V8Action) -> str:
        rule_id = action.rule_id
        support = action.supporting_sample_ids or []
        if not rule_id:
            return "INVALID_ACTION_SCHEMA"
        if any(sample_id not in self.sample_ids for sample_id in support):
            return "UNKNOWN_SAMPLE"
        self.recorded_rule = {
            "rule_id": rule_id,
            "supporting_sample_ids": list(support),
        }
        return "RULE_RECORDED_WITHOUT_CORRECTNESS_FEEDBACK"

    def _predict(self, action: V8Action) -> str:
        if self.area != "T":
            return "PREDICTION_OUT_OF_SCOPE"
        if action.answer not in COLORS:
            return "UNKNOWN_COLOR"
        self.pending_prediction = {
            "answer": action.answer,
            "area": self.area,
            "tick": self.tick_count,
            "parity": "even" if self.tick_count % 2 == 0 else "odd",
        }
        return "PREDICTION_RECORDED"

    def _choose_door(self, action: V8Action) -> str:
        if self.area not in DOORS:
            return "ALREADY_EXITED"
        if action.slot_index is None:
            return "INVALID_ACTION_SCHEMA"
        doors = DOORS[self.area]
        if action.slot_index < 1 or action.slot_index > len(doors):
            return "INVALID_SLOT"
        self.door_choices += 1
        self.attempts_by_area[self.area] += 1
        parity = self.tick_count % 2
        target = self._target_color()
        chosen = doors[action.slot_index - 1]
        self._resolve_prediction(chosen, target, parity)
        if chosen == target:
            passed_area = self.area
            if passed_area == "T":
                self.area = "EXIT"
                self.inspected_area = None
                self.gate_open = True
                self._succeed("GATE_OPENED")
                return "GATE_OPENED"
            sample = {
                "sample_id": (
                    f"SAMPLE_{passed_area}_T{self.tick_count}"
                    f"_ATTEMPT{self.attempts_by_area[passed_area]}"
                ),
                "area": passed_area,
                "tick_before_choice": self.tick_count,
                "parity_before_choice": "even" if parity == 0 else "odd",
                "wall_color": WALLS[passed_area],
                "chosen_door_color": chosen,
                "result": "passed",
            }
            self.samples.append(sample)
            self.sample_ids.add(str(sample["sample_id"]))
            self.inspected_area = None
            self.area = NEXT_AREA[passed_area]
            if self.area == "T":
                self.t_first_proxy_pending = True
            return f"PASSED_FORWARD_TO_{self.area}"
        self.invalid_transitions += 1
        self.resource_losses += 1
        self.resources = max(0, self.resources - 1)
        key = (self.area, parity)
        if key in self._wrong_parities:
            self.loop_states += 1
        else:
            self._wrong_parities.add(key)
        if self.area == "T":
            self.test_errors += 1
        return "INVALID_TRANSITION"

    def _resolve_prediction(self, chosen: str, target: str, parity: int) -> None:
        if self.area != "T":
            return
        if self.pending_prediction is not None:
            predicted = str(self.pending_prediction["answer"])
            self.predictions.append(
                {
                    "source": "explicit",
                    "predicted": predicted,
                    "target": target,
                    "tick": self.tick_count,
                    "correct": predicted == target,
                }
            )
            self.pending_prediction = None
            self.t_first_proxy_pending = False
            return
        if self.t_first_proxy_pending:
            self.predictions.append(
                {
                    "source": "first_choice_proxy",
                    "predicted": chosen,
                    "target": target,
                    "tick": self.tick_count,
                    "correct": chosen == target,
                }
            )
            self.t_first_proxy_pending = False

    def _action_cost(self, action: V8Action) -> int:
        if action.tool in {"inspect_symbols", "record_rule", "predict_transition"}:
            return 0
        return 1

    def _after_tick(self) -> None:
        if self.status is not V8Status.RUNNING:
            return
        if self.resources <= 0:
            self._fail("RESOURCE_DEPLETED")
            return
        if self.area == "T" and self.test_errors >= TEST_WRONG_LIMIT:
            self._fail("TEST_WRONG_LIMIT")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "area": self.area,
            "resources": self.resources,
            "test_errors": self.test_errors,
            "inspected_area": self.inspected_area,
            "samples": [dict(sample) for sample in self.samples],
            "recorded_rule": (
                None if self.recorded_rule is None else dict(self.recorded_rule)
            ),
            "door_choices": self.door_choices,
            "invalid_transitions": self.invalid_transitions,
            "resource_losses": self.resource_losses,
            "loop_states": self.loop_states,
            "predictions": [dict(row) for row in self.predictions],
            "pending_prediction": self.pending_prediction,
            "gate_open": self.gate_open,
            "judge_target_color": (
                self._target_color() if self.area in WALLS else None
            ),
        }

    def metrics(self) -> dict[str, Any]:
        correct = sum(1 for row in self.predictions if row["correct"])
        return {
            "map15.unseen_transition_accuracy": {
                "numerator": correct,
                "denominator": len(self.predictions),
            },
            "map15.probes_to_target": self.door_choices if self.is_success else None,
            "map15.invalid_transitions": self.invalid_transitions,
            "map15.loop_states": self.loop_states,
            "map15.reset_losses": self.resource_losses * 2,
        }


def gated_status() -> Any:
    """Return the running status; helper keeps the guard explicit and typed."""

    from agent_arena.worlds.scenario_v8.models import V8Status

    return V8Status.RUNNING


ORACLE_CASES = (
    {
        "trace_id": "explicit_rule_zero_error",
        "seed": 0,
        "actions": [
            {"tool": "inspect_symbols", "area": "A"},
            {"tool": "choose_door", "slot_index": 1},
            {"tool": "inspect_symbols", "area": "B"},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "inspect_symbols", "area": "C"},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "inspect_symbols", "area": "T"},
            {
                "tool": "record_rule",
                "rule_id": "R_EVEN_SAME_ODD_COMPLEMENT",
                "supporting_sample_ids": [
                    "SAMPLE_A_T0_ATTEMPT1",
                    "SAMPLE_B_T1_ATTEMPT1",
                    "SAMPLE_C_T2_ATTEMPT1",
                ],
            },
            {"tool": "choose_door", "slot_index": 3},
        ],
        "expect_success": True,
    },
    {
        "trace_id": "implicit_one_test_error_recovery",
        "seed": 0,
        "actions": [
            {"tool": "inspect_symbols", "area": "A"},
            {"tool": "choose_door", "slot_index": 1},
            {"tool": "inspect_symbols", "area": "B"},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "inspect_symbols", "area": "C"},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "inspect_symbols", "area": "T"},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "choose_door", "slot_index": 1},
        ],
        "expect_success": True,
    },
)


FIXTURES = (
    {
        "name": "zero_error_with_recorded_rule",
        "seed": 0,
        "actions": [
            {"tool": "inspect_symbols", "area": "A"},
            {"tool": "choose_door", "slot_index": 1},
            {"tool": "inspect_symbols", "area": "B"},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "inspect_symbols", "area": "C"},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "inspect_symbols", "area": "T"},
            {
                "tool": "record_rule",
                "rule_id": "R_EVEN_SAME_ODD_COMPLEMENT",
                "supporting_sample_ids": [
                    "SAMPLE_A_T0_ATTEMPT1",
                    "SAMPLE_B_T1_ATTEMPT1",
                    "SAMPLE_C_T2_ATTEMPT1",
                ],
            },
            {"tool": "choose_door", "slot_index": 3},
        ],
        "expect": {
            "map15.unseen_transition_accuracy": 1.0,
            "map15.probes_to_target": 4,
            "map15.invalid_transitions": 0,
            "map15.loop_states": 0,
            "map15.reset_losses": 0,
        },
    },
    {
        "name": "one_test_error_then_recalculate_parity",
        "seed": 0,
        "actions": [
            {"tool": "choose_door", "slot_index": 1},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "inspect_symbols", "area": "T"},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "inspect_symbols", "area": "T"},
            {"tool": "choose_door", "slot_index": 1},
        ],
        "expect": {
            "map15.unseen_transition_accuracy": 0.0,
            "map15.probes_to_target": 5,
            "map15.invalid_transitions": 1,
            "map15.loop_states": 0,
            "map15.reset_losses": 2,
        },
    },
    {
        "name": "explicit_unseen_prediction_is_scored",
        "seed": 0,
        "actions": [
            {"tool": "choose_door", "slot_index": 1},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "inspect_symbols", "area": "T"},
            {"tool": "predict_transition", "answer": "green"},
            {"tool": "choose_door", "slot_index": 3},
        ],
        "expect": {
            "map15.unseen_transition_accuracy": 1.0,
            "map15.probes_to_target": 4,
            "map15.invalid_transitions": 0,
            "map15.reset_losses": 0,
        },
    },
    {
        "name": "second_test_error_hits_test_wrong_limit",
        "seed": 0,
        "actions": [
            {"tool": "choose_door", "slot_index": 1},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "choose_door", "slot_index": 2},
            {"tool": "choose_door", "slot_index": 2},
        ],
        "expect": {
            "map15.unseen_transition_accuracy": 0.0,
            "map15.invalid_transitions": 2,
            "map15.loop_states": 0,
            "map15.reset_losses": 4,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map15Environment"]
