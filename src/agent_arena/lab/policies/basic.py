"""``basic.v1``：基线行动循环。

与 V11 ``execute_live`` 的唯一差异是代码组织方式；提示、5 步历史窗口、动作校验与
预算语义全部保持一致，因此它可以作为其它架构的对照锚点。
"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.adapters import (
    AgentContext,
    PublicActionResult,
    PublicEpisodeContext,
    PublicObservation,
)
from agent_arena.lab.contracts import AgentDecision, AgentIdentity
from agent_arena.lab.policies.base import extract_action_candidate
from agent_arena.lab.registry import get_agent


class BasicPolicy:
    agent_id = "basic.v1"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        registration = get_agent(self.agent_id)
        self._identity = registration.identity
        self.config = registration.normalize_config(config)
        self.history_window = int(self.config.get("history_window", 5))
        self._context: PublicEpisodeContext | None = None

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def reset(self, context: PublicEpisodeContext) -> None:
        self._context = context

    def decide(
        self, observation: PublicObservation, context: AgentContext
    ) -> AgentDecision:
        response = context.gateway.ask(
            observation,
            purpose="decision",
            recent_history=context.recent_history_text(limit=self.history_window),
            correction=context.invalid_total > 0,
            invalid_output_reason="schema" if context.invalid_total else None,
            estimate_text=context.full_history_text(),
        )
        return AgentDecision(
            action=extract_action_candidate(response.candidate),
            decision_reason=None,
            requests=1,
        )

    def observe_result(self, outcome: PublicActionResult) -> None:
        """基线不维护额外状态；历史窗口由 Runner 统一提供。"""

    def close(self) -> None:
        self._context = None


__all__ = ["BasicPolicy"]
