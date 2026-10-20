"""V11 公开动作级失败归因。

复用 V10 的 ``MECHANISM_TOOLS`` 口径，把“机制是否尝试/被拒/被接受”映射为
可复核标签。只读取公开动作与结果，不推断模型意图，也不读取密封真值。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.attribution import MECHANISM_TOOLS
from agent_arena.v10.baselines.runner import REJECT_MARKERS

LABELS: dict[str, str] = {
    "TRIGGERED": "机制已触发",
    "CONTRACT_ARTIFACT": "接口假象（非法动作占比过高）",
    "KEY_ACTION_NEVER_ATTEMPTED": "机制动作从未尝试",
    "KEY_ACTION_ATTEMPTED_REJECTED": "机制动作被尝试但全部被拒",
    "KEY_ACTION_USED_NO_TRIGGER": "机制动作被接受但未触发阈值/时序",
    "INCOMPLETE": "未完成，无法归因",
}

DETAILS: dict[str, str] = {
    "TRIGGERED": "环境记录核心机制已被真实触发。",
    "CONTRACT_ARTIFACT": "超过一半动作未通过公开契约，本局不能用于能力结论。",
    "KEY_ACTION_NEVER_ATTEMPTED": "本局没有调用该图的核心机制动作。",
    "KEY_ACTION_ATTEMPTED_REJECTED": "调用过机制动作，但结果全部被环境拒绝，通常是前置条件未满足。",
    "KEY_ACTION_USED_NO_TRIGGER": "机制动作被接受，但机制阈值/时序仍未达成。",
    "INCOMPLETE": "本局未产生足够动作或未结束，无法做机制归因。",
}


def attribute_steps(
    map_id: str,
    steps: list[dict[str, Any]],
    *,
    invalid_actions: int,
    mechanism_triggered: bool | None,
    outcome: str,
) -> dict[str, Any]:
    tools = set(MECHANISM_TOOLS.get(map_id, ()))
    attempts: list[dict[str, Any]] = []
    for step in steps:
        action = step.get("action")
        if not isinstance(action, dict):
            continue
        if action.get("tool") in tools:
            attempts.append(step)
    rejected = [
        step
        for step in attempts
        if str(step.get("result", "")).startswith(REJECT_MARKERS)
    ]
    accepted = [step for step in attempts if step not in rejected]

    if mechanism_triggered:
        label = "TRIGGERED"
    elif steps and invalid_actions / max(1, len(steps)) > 0.5:
        label = "CONTRACT_ARTIFACT"
    elif not steps:
        label = "INCOMPLETE"
    elif not attempts:
        label = "KEY_ACTION_NEVER_ATTEMPTED"
    elif not accepted:
        label = "KEY_ACTION_ATTEMPTED_REJECTED"
    else:
        label = "KEY_ACTION_USED_NO_TRIGGER"

    return {
        "label": label,
        "label_zh": LABELS[label],
        "detail": DETAILS[label],
        "mechanism_tools": sorted(tools),
        "attempts": len(attempts),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "outcome": outcome,
    }


__all__ = ["DETAILS", "LABELS", "attribute_steps"]
