"""V10 公开 system prompt 组装（与冻结 runner 逐字一致）。"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.contract import action_contract
from agent_arena.v10.contract_hints import CONTRACT_HINTS


def system_prompt(map_id: str, environment: Any) -> str:
    rules = "\n".join(f"- {item}" for item in environment.public_rules())
    hints = "".join(f"\n注意：{item}" for item in CONTRACT_HINTS.get(map_id, ()))
    return (
        f"你在玩一个确定性回合制解密关卡（{map_id}）。每回合必须从允许动作里选一个。\n"
        "输出必须是一个 JSON 对象：字段 tool 加上该 tool 允许的字段；"
        "禁止输出 command/target/args 等旧格式。示例：tool=move 且 to=B。\n"
        f"公开规则：\n{rules}\n\n"
        f"{action_contract(environment.SHAPES)}{hints}"
    )


__all__ = ["system_prompt"]
