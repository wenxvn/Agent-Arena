"""``reflection.v2``：可验证激活的反思（P1-1 / V13-06-02 … 06-05）。

DCR-V12-05 的教训：``reflection.v1`` 在 MAP-16 上**从未触发**（终止太快），
于是"反思开/关"两臂的 ``reflection_triggered`` 都是 0，对照无效。V13 因此把
"是否真的被处理"做成可测量的一等公民：

- **触发器**（全部是公开规则，不由 LLM 自判）：
  `repeated_rejection` / `repeated_action` / `no_progress` / `budget_drain`；
- **激活率**：``eligible``（触发条件成立且冷却已过、额度未用尽）与
  ``triggered``（真的发出了反思请求）分开计数；二者之差就是被冷却/额度挡下的次数；
- **零暴露**：``triggered == 0`` 时输出 ``NO_TREATMENT_EXPOSURE``，**不是**"反思无效"；
- **触发后恢复率**：反思后 ``recovery_window`` 步内公开进度是否变化（只算公开证据）；
- **误触发**：触发时动作其实刚成功且进度在推进（``budget_drain`` 的误判）；
- **trigger-only 对照**：`trigger_only=True` 时只判断触发、不请求模型，用来验证
  "判断触发"本身不会偷偷注入额外有利提示；
- 冷却与上限：`cooldown_steps` / `max_reflections`，额外请求全部计入同一账本。
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

REFLECTION_V2_INSTRUCTIONS = (
    "你是同一局的 Reflection 模块。只依据下面提供的公开历史与公开动作结果，"
    "指出可验证的行为问题并给出下一步可执行的改进建议。\n"
    "禁止臆造未公开信息，禁止输出具体动作 JSON，禁止声称知道隐藏真值。\n"
    "输出 JSON 对象，字段：advice（≤240 字，可执行的改进建议）、"
    "avoid（字符串数组，≤4 条要避免的重复模式）、next_focus（≤120 字）。"
)

EXPOSURE_NONE = "NO_TREATMENT_EXPOSURE"
EXPOSURE_TRIGGERED = "TREATMENT_TRIGGERED"

TRIGGER_REPEATED_ACTION = "repeated_action"
TRIGGER_REPEATED_REJECTION = "repeated_rejection"
TRIGGER_NO_PROGRESS = "no_progress"
TRIGGER_BUDGET_DRAIN = "budget_drain"


class ReflectionV2Policy:
    agent_id = "reflection.v2"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        registration = get_agent(self.agent_id)
        self._identity = registration.identity
        self.config = registration.normalize_config(config)
        self.enabled = bool(self.config.get("enabled", True))
        self.trigger_only = bool(self.config.get("trigger_only", False))
        self.max_reflections = max(0, int(self.config.get("max_reflections", 3)))
        self.cooldown_steps = max(0, int(self.config.get("cooldown_steps", 4)))
        self.stall_threshold = max(1, int(self.config.get("stall_threshold", 3)))
        self.reject_threshold = max(1, int(self.config.get("reject_threshold", 2)))
        self.recovery_window = max(1, int(self.config.get("recovery_window", 3)))
        self.history_window = int(self.config.get("history_window", 5))
        self._reset_state()

    def _reset_state(self) -> None:
        self._last_signature = ""
        self._stall = 0
        self._reject_streak = 0
        self._recent_actions: list[str] = []
        self._reflections = 0
        self._last_reflection_step = -999
        self._advice: dict[str, Any] | None = None
        self._eligible = 0
        self._triggered = 0
        self._blocked_cooldown = 0
        self._blocked_quota = 0
        self._false_triggers = 0
        self._recoveries = 0
        self._pending_recovery: dict[str, Any] | None = None
        self._trigger_log: list[dict[str, Any]] = []
        self._announced = False

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def reset(self, context: PublicEpisodeContext) -> None:
        self._reset_state()
        self._context = context

    def close(self) -> None:
        self._advice = None

    # ------------------------------------------------------------------ detect
    def _detect(
        self, observation: PublicObservation, context: AgentContext
    ) -> tuple[str, dict[str, Any], bool] | None:
        """返回 (trigger, evidence, is_false_trigger) 或 None。"""

        signature = progress_signature(observation)
        if signature == self._last_signature:
            self._stall += 1
        else:
            self._stall = 0
            self._last_signature = signature

        if len(self._recent_actions) >= 3 and len(set(self._recent_actions[-3:])) == 1:
            # 被拒的重复动作更具体：先报 repeated_rejection，再退回 repeated_action。
            if self._reject_streak >= self.reject_threshold:
                return TRIGGER_REPEATED_REJECTION, {
                    "reject_streak": self._reject_streak,
                    "repeated_action": self._recent_actions[-1],
                    "steps": [context.decision_index],
                }, False
            return TRIGGER_REPEATED_ACTION, {
                "action": self._recent_actions[-1],
                "repeat_count": 3,
                "steps": [context.decision_index - index for index in (2, 1, 0)],
            }, False
        if self._reject_streak >= self.reject_threshold:
            return TRIGGER_REPEATED_REJECTION, {
                "reject_streak": self._reject_streak,
                "steps": [context.decision_index],
            }, False
        if self._stall >= self.stall_threshold:
            return TRIGGER_NO_PROGRESS, {
                "stall_steps": self._stall,
                "threshold": self.stall_threshold,
                "steps": [context.decision_index - self._stall, context.decision_index],
            }, False
        tick = observation.fields.get("tick")
        if (
            isinstance(tick, int)
            and self._reject_streak == 0
            and self._stall == 0
            and len(self._recent_actions) >= 2
            and self._recent_actions[-1] == self._recent_actions[-2]
        ):
            # 同动作重复但进度在推进：可能是正常的周期性动作（误触发风险）。
            return TRIGGER_BUDGET_DRAIN, {
                "tick": tick,
                "steps": [context.decision_index - 1, context.decision_index],
            }, True
        return None

    # ----------------------------------------------------------------- reflect
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
                f"公开触发器：{trigger}；证据：{compact_json(evidence, limit=400)}"
            ),
            system_prompt=REFLECTION_V2_INSTRUCTIONS,
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
        self._pending_recovery = {
            "trigger": trigger,
            "at": context.decision_index,
            "signature": progress_signature(observation),
            "steps_left": self.recovery_window,
            "recovered": False,
        }
        if not advice["advice"] and not advice["next_focus"]:
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
                    "cooldown_steps": self.cooldown_steps,
                    "recovery_window": self.recovery_window,
                },
                requests=1,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            ),
            1,
            response.input_tokens,
            response.output_tokens,
        )

    # ------------------------------------------------------------------ decide
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
                    payload={"enabled": False, "version": "v2"},
                )
        else:
            detected = self._detect(observation, context)
            if detected is not None:
                trigger, evidence, false_trigger = detected
                cooldown_ok = (
                    context.decision_index - self._last_reflection_step
                    >= self.cooldown_steps
                )
                quota_ok = self._reflections < self.max_reflections
                eligible = cooldown_ok and quota_ok
                if eligible:
                    self._eligible += 1
                elif not quota_ok:
                    self._blocked_quota += 1
                else:
                    self._blocked_cooldown += 1
                self._trigger_log.append(
                    {
                        "decision_index": context.decision_index,
                        "trigger": trigger,
                        "eligible": eligible,
                        "cooldown_ok": cooldown_ok,
                        "quota_ok": quota_ok,
                        "false_trigger": false_trigger,
                        "evidence": evidence,
                    }
                )
                if eligible and self.trigger_only:
                    # trigger-only：只暴露"触发发生了"，不请求模型、不注入建议。
                    self._triggered += 1
                    reflection_event = AgentEvent(
                        kind="reflection",
                        event="reflection_trigger_only",
                        decision_index=context.decision_index,
                        summary=(
                            f"触发器命中（{trigger}），trigger-only 臂不请求模型；"
                            "用于验证触发判定本身不注入额外提示。"
                        ),
                        payload={
                            "trigger": trigger,
                            "evidence": evidence,
                            "requests": 0,
                        },
                        requests=0,
                    )
                elif eligible:
                    self._triggered += 1
                    if false_trigger:
                        self._false_triggers += 1
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
        if self._pending_recovery is not None:
            pending = self._pending_recovery
            signature = progress_signature(outcome.observation)
            if signature != pending["signature"]:
                pending["recovered"] = True
                self._recoveries += 1
                self._pending_recovery = None
                return
            pending["steps_left"] = int(pending["steps_left"]) - 1
            if int(pending["steps_left"]) <= 0:
                self._pending_recovery = None

    # --------------------------------------------------------------- diagnostics
    @property
    def exposure(self) -> str:
        if not self.enabled:
            return "DISABLED"
        return EXPOSURE_TRIGGERED if self._triggered else EXPOSURE_NONE

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "version": "v2",
            "trigger_only": self.trigger_only,
            "reflections": self._reflections,
            "max_reflections": self.max_reflections,
            "eligible": self._eligible,
            "triggered": self._triggered,
            "blocked_cooldown": self._blocked_cooldown,
            "blocked_quota": self._blocked_quota,
            "false_triggers": self._false_triggers,
            "recoveries": self._recoveries,
            "activation_rate": (
                round(self._triggered / self._eligible, 4) if self._eligible else None
            ),
            "recovery_rate": (
                round(self._recoveries / self._triggered, 4)
                if self._triggered
                else None
            ),
            "exposure": self.exposure,
            "advice": dict(self._advice) if self._advice else None,
            "trigger_log": list(self._trigger_log),
        }


def make_reflection_v2(config: dict[str, Any] | None = None) -> ReflectionV2Policy:
    return ReflectionV2Policy(config)


__all__ = [
    "EXPOSURE_NONE",
    "EXPOSURE_TRIGGERED",
    "REFLECTION_V2_INSTRUCTIONS",
    "TRIGGER_BUDGET_DRAIN",
    "TRIGGER_NO_PROGRESS",
    "TRIGGER_REPEATED_ACTION",
    "TRIGGER_REPEATED_REJECTION",
    "ReflectionV2Policy",
    "make_reflection_v2",
]
