"""MAP-17 V10 基线：四车排程的 Oracle、脚本化启发式与消融（DCR-V10-34）。

MAP-17 的动作契约是"每 tick 提交一整行时刻表"，没有自然的逐步启发式；因此本模块的
``public_heuristic`` 是**脚本化参考策略**（复用 V8 已验证的 12-tick 时刻表），
在报告中如实标注。消融通过对同一份时刻表做结构性破坏得到。
"""

from __future__ import annotations

import copy
from typing import Any

from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.worlds.scenario_v8.maps.map17 import ORACLE_CASES
from agent_arena.worlds.scenario_v8.models import V8Action

BASE_PLAN: list[dict[str, Any]] = [dict(item) for item in ORACLE_CASES[0]["actions"]]


class ScriptedTimetable:
    """按队列回放时刻表；``mutate`` 用于生成消融。"""

    def __init__(
        self,
        *,
        name: str = "scripted_time_priority",
        mutate: str | None = None,
    ) -> None:
        self.name = name
        self.mutate = mutate
        self._queue: list[dict[str, Any]] = []
        self.reset()

    def reset(self) -> None:
        self._queue = [copy.deepcopy(item) for item in BASE_PLAN]
        if self.mutate == "no_board":
            for item in self._queue:
                for operation in item["operations"].values():
                    operation.pop("board", None)
        elif self.mutate == "half_board":
            for item in self._queue:
                for operation in item["operations"].values():
                    board = operation.get("board")
                    if board:
                        operation["board"] = {
                            od: max(1, count // 2) for od, count in board.items()
                        }
        elif self.mutate == "no_ring":
            for item in self._queue:
                operations = item["operations"]
                item["operations"] = {
                    train: operation
                    for train, operation in operations.items()
                    if operation.get("board", {}).get("B_to_E") is None
                    and operation.get("op") != "switch_line"
                }

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        del history
        if self._queue:
            return self._queue.pop(0)
        # 队列用尽后继续提交空时刻表，让时限较长的实例走到结算
        return {
            "tool": "set_timetable",
            "tick": int(observation.get("tick", 0)),
            "operations": {},
        }


def HEURISTIC() -> ScriptedTimetable:
    return ScriptedTimetable()


def _plan(seed: int) -> list[dict[str, Any]]:
    """基础 12-tick 时刻表；时限更长的实例补空行到 horizon。"""

    environment = create_environment("MAP-17", environment_seed=seed)
    horizon = int(environment.judge_state()["horizon"])
    plan = [copy.deepcopy(item) for item in BASE_PLAN]
    for tick in range(len(BASE_PLAN), horizon):
        plan.append({"tool": "set_timetable", "tick": tick, "operations": {}})
    return plan


def oracle_actions(seed: int) -> list[dict[str, Any]]:
    environment = create_environment("MAP-17", environment_seed=seed)
    plan = _plan(seed)
    for payload in plan:
        if environment.is_terminal:
            break
        action = V8Action.model_validate(payload, strict=True)
        if not environment.accepts(action):
            raise AssertionError(f"MAP-17 方案含非法动作：{payload}")
        environment.step(action)
    if not environment.is_success:
        raise AssertionError(
            f"MAP-17 seed {seed} 方案不可行（{environment.status.value}）"
        )
    return plan


ABLATIONS = {
    "no_board": lambda: ScriptedTimetable(name="no_board", mutate="no_board"),
    "half_board": lambda: ScriptedTimetable(name="half_board", mutate="half_board"),
    "no_ring": lambda: ScriptedTimetable(name="no_ring", mutate="no_ring"),
}

__all__ = ["ABLATIONS", "BASE_PLAN", "HEURISTIC", "ScriptedTimetable", "oracle_actions"]
