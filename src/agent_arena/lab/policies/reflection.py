"""``reflection.v1``：条件反思（P1）。

触发器全部是**可解释的公开规则**，不由 LLM 自判：

| 触发器 | 规则 |
|---|---|
| ``no_progress`` | 公开进度指纹连续 ``stall_threshold`` 次决策未变化 |
| ``repeated_rejection`` | 连续 ``reject_threshold`` 次动作被环境拒绝或非法 |
| ``repeated_action`` | 同一动作连续出现 3 次 |
| ``budget_drain`` | 决策在消耗，但公开 tick 未推进（存在空转） |

限额：``max_reflections`` 次/局、``cooldown_steps`` 步冷却；每次反思都是真实请求，
计入请求数/token/费用。``enabled=False`` 时不发任何反思请求（消融臂）。
"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.adapters import (
    AgentContext,
    PublicActionResult,
    PublicEpisodeContext,
    PublicObservation,
)
from agent_arena.lab.contracts import AgentDecision, AgentEvent, AgentIdentity
from agent_arena.lab.policies.base import (
    bounded_text,
    compact_json,
    extract_action_candidate,
)
from agent_arena.lab.policies.planning import progress_signature
from agent_arena.lab.registry import get_agent

REFLECTION_INSTRUCTIONS = (
    "你是同一局的 Reflection 模块。只依据下面提供的公开历史与公开动作结果，"
    "指出可验证的行为问题并给出下一步可执行的改进建议。\n"
    "禁止臆造未公开信息，禁止输出具体动作 JSON，禁止声称知道隐藏真值。\n"
    "输出 JSON 对象，字段：advice（≤240 字，可执行的改进建议）、"
    "avoid（字符串数组，≤4 条要避免的重复模式）、next_focus（≤120 字）。"
)


class ReflectionPolicy:
    agent_id = "reflection.v1"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        registration = get_agent(self.agent_id)
        self._identity = registration.identity
        self.config = registration.normalize_config(config)
        self.enabled = bool(self.config.get("enabled", True))
        self.max_reflections = max(0, int(self.config.get("max_reflections", 3)))
        self.cooldown_steps = max(0, int(self.config.get("cooldown_steps", 4)))
        self.stall_threshold = max(1, int(self.config.get("stall_threshold", 3)))
        self.reject_threshold = max(1, int(self.config.get("reject_threshold", 2)))
        self.history_window = int(self.config.get("history_window", 5))
        self._last_signature = ""
        self._stall = 0
        self._reject_streak = 0
        self._recent_actions: list[str] = []
        self._reflections = 0
        self._last_reflection_step = -999
        self._advice: dict[str, Any] | None = None
        self._pending_effect: dict[str, Any] | None = None
        self._announced = False

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def reset(self, context: PublicEpisodeContext) -> None:
        self._last_signature = ""
        self._stall = 0
        self._reject_streak = 0
        self._recent_actions = []
        self._reflections = 0
        self._last_reflection_step = -999
        self._advice = None
        self._pending_effect = None
        self._announced = False
        self._context = context

    def close(self) -> None:
        self._advice = None

    # ----------------------------------------------------------------- triggers
    def _detect(
        self, observation: PublicObservation, context: AgentContext
    ) -> tuple[str, dict[str, Any]] | None:
        signature = progress_signature(observation)
        if signature == self._last_signature:
            self._stall += 1
        else:
            self._stall = 0
            self._last_signature = signature

        if len(self._recent_actions) >= 3 and len(set(self._recent_actions[-3:])) == 1:
            return "repeated_action", {
                "action": self._recent_actions[-1],
                "repeat_count": 3,
                "steps": [context.decision_index - index for index in (2, 1, 0)],
            }
        if self._reject_streak >= self.reject_threshold:
            return "repeated_rejection", {
                "reject_streak": self._reject_streak,
                "steps": [context.decision_index],
            }
        if self._stall >= self.stall_threshold:
            return "no_progress", {
                "stall_steps": self._stall,
                "threshold": self.stall_threshold,
                "steps": [context.decision_index - self._stall, context.decision_index],
            }
        tick = observation.fields.get("tick")
        if (
            isinstance(tick, int)
            and self._reject_streak == 0
            and self._stall == 0
            and len(self._recent_actions) >= 2
            and self._recent_actions[-1] == self._recent_actions[-2]
        ):
            return "budget_drain", {
                "tick": tick,
                "steps": [context.decision_index - 1, context.decision_index],
            }
        return None

    # ------------------------------------------------------------------ reflect
    def _reflect(
        self,
        observation: PublicObservation,
        context: AgentContext,
        trigger: str,
        evidence: dict[str, Any],
    ) -> tuple[AgentEvent | None, int, int, int]:
        payload, response = context.gateway.ask_json(
            observation,
            purpose="reflection",
            recent_history=context.recent_history_text(limit=self.history_window),
            runtime_feedback=(
                f"公开触发器：{trigger}；证据："
                f"{compact_json(evidence, limit=400)}"
            ),
            system_prompt=REFLECTION_INSTRUCTIONS,
        )
        self._reflections += 1
        self._last_reflection_step = context.decision_index
        advice: dict[str, Any] = {
            "advice": bounded_text(payload.get("advice", ""), limit=240),
            "avoid": [
                bounded_text(item, limit=120)
                for item in (
                    payload.get("avoid") if isinstance(payload.get("avoid"), list) else []
                )[:4]
            ],
            "next_focus": bounded_text(payload.get("next_focus", ""), limit=120),
            "trigger": trigger,
            "decision_index": context.decision_index,
        }
        if not advice["advice"] and not advice["next_focus"]:
            # 空反思不当作有效建议，但仍已计费。
            return (
                AgentEvent(
                    kind="reflection",
                    event="reflection_empty",
                    decision_index=context.decision_index,
                    summary=f"反思请求返回空建议（trigger={trigger}），已计费但不注入。",
                    payload={"trigger": trigger, "evidence": evidence},
                    requests=1,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                ),
                1,
                response.input_tokens,
                response.output_tokens,
            )
        self._advice = advice
        self._pending_effect = {"trigger": trigger, "step": context.decision_index}
        return (
            AgentEvent(
                kind="reflection",
                event="reflection_triggered",
                decision_index=context.decision_index,
                summary=f"反思触发（{trigger}）：{advice['advice'][:160]}",
                payload={
                    "trigger": trigger,
                    "evidence": evidence,
                    "advice": advice["advice"],
                    "avoid": advice["avoid"],
                    "next_focus": advice["next_focus"],
                    "reflection_index": self._reflections,
                    "max_reflections": self.max_reflections,
                },
                requests=1,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            ),
            1,
            response.input_tokens,
            response.output_tokens,
        )

    # ------------------------------------------------------------------- decide
    def decide(
        self, observation: PublicObservation, context: AgentContext
    ) -> AgentDecision:
        reflection_event: AgentEvent | None = None
        extra_requests = 0
        if not self.enabled:
            if not self._announced:
                self._announced = True
                reflection_event = AgentEvent(
                    kind="ablation",
                    event="reflection_disabled",
                    decision_index=context.decision_index,
                    summary="反思关闭（消融臂）：不请求反思，也不注入建议。",
                    payload={"enabled": False},
                )
        else:
            detected = self._detect(observation, context)
            can_reflect = (
                detected is not None
                and self._reflections < self.max_reflections
                and context.decision_index - self._last_reflection_step >= self.cooldown_steps
            )
            if can_reflect and detected is not None:
                trigger, evidence = detected
                reflection_event, used, _, _ = self._reflect(
                    observation, context, trigger, evidence
                )
                extra_requests += used

        feedback = None
        if self.enabled and self._advice:
            feedback = (
                "反思建议（公开触发器产生，仅供参考）："
                f"{self._advice['advice']}；避免：{', '.join(self._advice['avoid'])}；"
                f"下一步聚焦：{self._advice['next_focus']}"
            )

        response = context.gateway.ask(
            observation,
            purpose="decision",
            recent_history=context.recent_history_text(limit=self.history_window),
            runtime_feedback=feedback,
            correction=context.invalid_streak > 0,
            invalid_output_reason="schema" if context.invalid_streak else None,
            estimate_text=context.full_history_text(),
        )
        return AgentDecision(
            action=extract_action_candidate(response.candidate),
            decision_reason=None,
            reflection_event=reflection_event,
            requests=1 + extra_requests,
        )

    def observe_result(self, outcome: PublicActionResult) -> None:
        action = outcome.action
        if isinstance(action, dict):
            self._recent_actions.append(compact_json(action, limit=200))
        else:
            self._recent_actions.append("<invalid>")
        self._recent_actions = self._recent_actions[-6:]
        if outcome.rejected or outcome.invalid:
            self._reject_streak += 1
        else:
            self._reject_streak = 0
        if self._pending_effect is not None:
            self._pending_effect["after_step"] = outcome.decision_index
            self._pending_effect["after_rejected"] = bool(
                outcome.rejected or outcome.invalid
            )
            self._pending_effect["after_result"] = outcome.result[:200]
            self._pending_effect = None

    # --------------------------------------------------------------- diagnostics
    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "reflections": self._reflections,
            "max_reflections": self.max_reflections,
            "advice": dict(self._advice) if self._advice else None,
        }


__all__ = ["REFLECTION_INSTRUCTIONS", "ReflectionPolicy"]
