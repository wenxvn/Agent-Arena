"""MAP-15 V10 基线：Oracle、样例归纳启发式与四类消融。

- ``oracle``：知道密封家族，逐区 inspect 后选目标门，C 处记录真规则；
- ``public_heuristic``：枚举全部 (period, offsets) 假设（2 周期 16 个、3 周期 64 个），
  用 ``training_sample_log`` 中的通过/失败样例过滤；剩余假设唯一时按它选门，否则在训练区
  选“多数假设支持”的门（错了只耗 1 tick，样例会继续缩小假设集）；
- ``no_probe``：不 inspect、不看样例，每区都选 1 号门；
- ``fixed_route``：照搬 seed 0 的 Oracle 槽位序列（在单一固定路径上背答案）；
- ``random_rule``：记录一个格式合法的随机规则并按它行动（policy seed 决定）；
- ``no_transfer``：只用“门色 = 墙色”（offset 恒 0），不从样例迁移相位规律。
"""

from __future__ import annotations

import itertools
import random
from typing import Any

from agent_arena.v10.runtime.map15 import (
    TEST_GATES,
    WHEEL,
    Family,
    Map15V10Environment,
    target_color,
)
from agent_arena.worlds.scenario_v8.models import V8Action

Action = dict[str, Any]
HYPOTHESES: tuple[Family, ...] = tuple(
    Family("h", period, offsets)
    for period in (2, 3)
    for offsets in itertools.product(range(4), repeat=period)
)


def _rule_id(family: Family) -> str:
    return f"period={family.period};offsets={','.join(str(item) for item in family.offsets)}"


def consistent(samples: list[dict[str, Any]]) -> list[Family]:
    alive = []
    for family in HYPOTHESES:
        ok = True
        for sample in samples:
            predicted = target_color(family, sample["wall_color"], int(sample["tick"]))
            passed = sample["result"] == "passed"
            if passed and predicted != sample["door_color"]:
                ok = False
                break
            if not passed and predicted == sample["door_color"]:
                ok = False
                break
        if ok:
            alive.append(family)
    return alive


class _Policy:
    name = "policy"

    def reset(self) -> None:
        self.recorded = False

    def rule_for(self, observation: dict[str, Any]) -> Family | None:
        raise NotImplementedError

    def support(self, observation: dict[str, Any]) -> list[str]:
        return [str(sample["sample_id"]) for sample in observation["training_sample_log"]]

    def pick(self, observation: dict[str, Any]) -> int:
        family = self.rule_for(observation)
        wall = observation["current_wall_color_if_inspected"]
        doors = observation["current_door_colors_if_inspected"]
        tick = int(observation["current_tick"])
        if family is not None:
            wanted = target_color(family, wall, tick)
            if wanted in doors:
                return int(doors.index(wanted)) + 1
        votes = {
            color: sum(
                1
                for hypothesis in consistent(observation["training_sample_log"])
                if target_color(hypothesis, wall, tick) == color
            )
            for color in doors
        }
        best = max(doors, key=lambda color: (votes[color], -doors.index(color)))
        return int(doors.index(best)) + 1

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        area = str(observation["area"])
        if area == "EXIT":
            return {"tool": "wait", "ticks": 1}
        if not observation["inspected_current_area"]:
            return {"tool": "inspect_symbols", "area": area}
        if area == "C" and observation["recorded_rule_hypothesis"] is None:
            family = self.rule_for(observation) or Family("fallback", 2, (0, 0))
            return {
                "tool": "record_rule",
                "rule_id": _rule_id(family),
                "supporting_sample_ids": self.support(observation),
            }
        return {"tool": "choose_door", "slot_index": self.pick(observation)}


def _signature(family: Family) -> tuple[int, ...]:
    """6 个 tick（lcm(2,3)）上的偏移序列：等价假设签名相同。"""

    return tuple(family.offsets[tick % family.period] for tick in range(6))


class Map15Inductive(_Policy):
    """信息寻求式归纳：训练区按多数假设选门；在 C 区记录前，若一致假设仍不等价，
    就选能把假设集一分为二的门（或等待换相位）来获取证据，直到等价类唯一。"""

    name = "public_heuristic"

    def classes(self, observation: dict[str, Any]) -> dict[tuple[int, ...], Family]:
        alive = consistent(observation["training_sample_log"])
        result: dict[tuple[int, ...], Family] = {}
        for family in sorted(alive, key=lambda item: (item.period, item.offsets)):
            result.setdefault(_signature(family), family)
        return result

    def rule_for(self, observation: dict[str, Any]) -> Family | None:
        classes = self.classes(observation)
        if len(classes) == 1:
            return next(iter(classes.values()))
        return None

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        area = str(observation["area"])
        if area != "C" or not observation["inspected_current_area"]:
            return super().act(observation, history)
        classes = self.classes(observation)
        if len(classes) == 1:
            family = next(iter(classes.values()))
            recorded = observation["recorded_rule_hypothesis"]
            if recorded is None or recorded["rule_id"] != _rule_id(family):
                return {
                    "tool": "record_rule",
                    "rule_id": _rule_id(family),
                    "supporting_sample_ids": self.support(observation),
                }
            return {"tool": "choose_door", "slot_index": self.pick(observation)}
        if observation["recorded_rule_hypothesis"] is None:
            placeholder = next(iter(classes.values()))
            return {
                "tool": "record_rule",
                "rule_id": _rule_id(placeholder),
                "supporting_sample_ids": self.support(observation),
            }
        wall = observation["current_wall_color_if_inspected"]
        doors = observation["current_door_colors_if_inspected"]
        tick = int(observation["current_tick"])
        votes = {
            color: sum(
                1 for family in classes.values() if target_color(family, wall, tick) == color
            )
            for color in doors
        }
        split = [color for color in doors if 0 < votes[color] < len(classes)]
        if not split:
            return {"tool": "wait", "ticks": 1}
        # 选票数最少的分割门：大概率失败（留在 C 并获得证据）。若它成功会直接进入 T1，
        # 所以先把记录改成“预测该门”的假设，保证记录与通过证据一致。
        probe = min(split, key=lambda color: (votes[color], doors.index(color)))
        backing = next(
            family for family in classes.values() if target_color(family, wall, tick) == probe
        )
        if observation["recorded_rule_hypothesis"]["rule_id"] != _rule_id(backing):
            return {
                "tool": "record_rule",
                "rule_id": _rule_id(backing),
                "supporting_sample_ids": self.support(observation),
            }
        return {"tool": "choose_door", "slot_index": doors.index(probe) + 1}


class Map15NoProbe(_Policy):
    name = "no_probe"

    def rule_for(self, observation: dict[str, Any]) -> Family | None:
        del observation
        return None

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if observation["area"] == "C" and observation["recorded_rule_hypothesis"] is None:
            return {
                "tool": "record_rule",
                "rule_id": "period=2;offsets=0,0",
                "supporting_sample_ids": self.support(observation)[:1],
            }
        return {"tool": "choose_door", "slot_index": 1}


class Map15NoTransfer(_Policy):
    name = "no_transfer"

    def rule_for(self, observation: dict[str, Any]) -> Family | None:
        del observation
        return Family("same_color", 2, (0, 0))


class Map15RandomRule(_Policy):
    name = "random_rule"

    def __init__(self, seed: int = 0) -> None:
        rng = random.Random(f"map15-random-rule|{seed}")
        self.family = rng.choice(HYPOTHESES)

    def rule_for(self, observation: dict[str, Any]) -> Family | None:
        del observation
        return self.family


class Map15FixedRoute:
    """照搬 seed 0 Oracle 的槽位序列，不看当前实例。"""

    name = "fixed_route"

    def reset(self) -> None:
        self.queue = [
            payload
            for payload in oracle_actions(0)
            if payload["tool"] in {"choose_door", "record_rule"}
        ]

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            payload = self.queue.pop(0)
            if payload["tool"] == "record_rule":
                return {
                    "tool": "record_rule",
                    "rule_id": payload["rule_id"],
                    "supporting_sample_ids": [
                        str(observation["training_sample_log"][0]["sample_id"])
                    ],
                }
            return payload
        return {"tool": "choose_door", "slot_index": 1}


def oracle_actions(environment_seed: int) -> list[Action]:
    environment = Map15V10Environment(seed=environment_seed)
    family = environment.family
    actions: list[Action] = []

    def step(payload: Action) -> None:
        actions.append(payload)
        environment.step(V8Action.model_validate(payload, strict=True))

    while not environment.is_terminal:
        area = environment.area
        step({"tool": "inspect_symbols", "area": area})
        if area == "C" and environment.recorded_rule is None:
            step(
                {
                    "tool": "record_rule",
                    "rule_id": family.rule_id,
                    "supporting_sample_ids": [
                        str(sample["sample_id"]) for sample in environment.samples
                    ],
                }
            )
        doors = environment.layout.doors[area]
        wanted = target_color(family, environment.layout.walls[area], environment.tick_count)
        if area in TEST_GATES:
            step({"tool": "predict_transition", "answer": wanted})
        step({"tool": "choose_door", "slot_index": doors.index(wanted) + 1})
    return actions


HEURISTIC = Map15Inductive
ABLATIONS: dict[str, type[Any]] = {
    "no_probe": Map15NoProbe,
    "fixed_route": Map15FixedRoute,
    "random_rule": Map15RandomRule,
    "no_transfer": Map15NoTransfer,
}

__all__ = ["ABLATIONS", "HEURISTIC", "HYPOTHESES", "WHEEL", "consistent", "oracle_actions"]
