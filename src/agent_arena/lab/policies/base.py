"""策略协议与共享工具。

四种内置架构共享同一条调用链：

- 同一 ``system_prompt``（与 V10/V11 冻结提示逐字一致）；
- 同一动作契约与同一个 ``V8Action`` 校验；
- 同一 ``DecisionGateway`` 预算出口；
- 差异只在**额外上下文**（记忆 / 计划 / 反思建议）与**额外请求**。

因此 ``basic.v1`` 是基线锚点，其它架构的差异可以被归因到被操纵的变量。
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from agent_arena.lab.adapters import (
    AgentContext,
    PublicActionResult,
    PublicEpisodeContext,
    PublicObservation,
)
from agent_arena.lab.contracts import AgentDecision, AgentEvent, AgentIdentity


@runtime_checkable
class AgentPolicy(Protocol):
    """可独立测试的策略接口；实现不得持有 Environment 或 Provider。"""

    @property
    def identity(self) -> AgentIdentity: ...

    def reset(self, context: PublicEpisodeContext) -> None: ...

    def decide(
        self, observation: PublicObservation, context: AgentContext
    ) -> AgentDecision: ...

    def observe_result(self, outcome: PublicActionResult) -> None: ...

    def close(self) -> None: ...


def extract_action_candidate(candidate: Any) -> dict[str, Any] | None:
    """从 Provider 输出里取出动作候选。

    与 V10 MiMo runner / V11 ``execute_live`` 完全同口径：**只接受平铺的动作对象**，
    不做 ``{"action": {...}}`` 之类的宽松解包，避免不同架构因解析策略不同而产生
    不可比的非法动作率。
    """

    if isinstance(candidate, dict) and isinstance(candidate.get("tool"), str):
        return dict(candidate)
    return None


def bounded_text(value: Any, *, limit: int = 240) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text[:limit]


def compact_json(payload: Any, *, limit: int = 1_200) -> str:
    """把公开结构压成有界 JSON 文本（超长时截断并标注）。"""

    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "…<truncated>"


def memory_block(facts: list[dict[str, Any]], *, max_chars: int) -> str | None:
    """把结构化记忆渲染成模型可见文本；空记忆返回 ``None``。"""

    if not facts:
        return None
    lines = ["公开记忆（本局内，来自公开观察与动作结果；按最近使用排序）："]
    used = len(lines[0])
    for fact in facts:
        line = f"- [{fact.get('kind', 'fact')}] {fact.get('key')} = {fact.get('value')}"
        if used + len(line) > max_chars:
            lines.append("- …（记忆已按容量上限截断）")
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def plan_block(plan: dict[str, Any] | None) -> str | None:
    if not plan:
        return None
    return compact_json(plan, limit=900)


def event(
    kind: str,
    name: str,
    *,
    decision_index: int,
    summary: str = "",
    payload: dict[str, Any] | None = None,
    requests: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> AgentEvent:
    return AgentEvent(
        kind=kind,  # type: ignore[arg-type]
        event=name,
        decision_index=decision_index,
        summary=summary[:600],
        payload=dict(payload or {}),
        requests=requests,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def normalize_decision(result: Any) -> AgentDecision:
    """把插件返回值统一成 ``AgentDecision``。

    允许三种写法（SDK 兼容层）：

    - 已经是 ``AgentDecision``；
    - ``{"action": {...}, "requests": n}``；
    - 直接返回动作对象 ``{"tool": ...}``。
    """

    if isinstance(result, AgentDecision):
        return result
    if isinstance(result, dict) and "action" in result and "tool" not in result:
        requests = result.get("requests")
        return AgentDecision(
            action=extract_action_candidate(result.get("action")),
            requests=int(requests) if isinstance(requests, int) else 0,
        )
    return AgentDecision(action=extract_action_candidate(result))


def call_hook(hook: Any, *args: Any) -> Any:
    """调用可选钩子，兼容 ``hook()`` 与 ``hook(context)`` 两种签名。

    第三方插件常写成无参 ``reset()``；内置策略用 ``reset(context)``。两者都允许，
    但**异常不会被吞掉**：只有 ``TypeError`` 由参数数量引起时才回退。
    """

    if not callable(hook):
        return None
    try:
        return hook(*args)
    except TypeError:
        if not args:
            raise
        return hook()


__all__ = [
    "AgentPolicy",
    "bounded_text",
    "call_hook",
    "compact_json",
    "event",
    "extract_action_candidate",
    "memory_block",
    "normalize_decision",
    "plan_block",
]
