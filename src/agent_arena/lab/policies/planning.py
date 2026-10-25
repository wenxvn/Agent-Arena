"""``planning.v1``：高层子目标 + 计划监控。

- Planner 只输出**非执行性**计划字段（子目标、完成条件、约束、未决问题），
  绝不输出 tool/action；
- Executor 仍是同一个动作契约与同一个网关；
- 重规划由公开事件触发：连续无进展、连续被拒、或达到周期上限；
- 每次 Planner 调用都是真实请求，全部计入请求数、token、费用与账本；
- ``enabled=False`` 时不发任何 Planner 请求、不注入计划文本（消融臂）。
"""

from __future__ import annotations

import json
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
    plan_block,
)
from agent_arena.lab.registry import get_agent

PLANNER_INSTRUCTIONS = (
    "你当前是 Planner，只能输出计划字段，不得输出 tool、action 或任何具体动作。\n"
    "输出 JSON 对象，字段：decision_reason（≤280 字）、current_subgoal（≤240 字）、"
    "success_criteria（字符串数组，1–8 条）、known_constraints（字符串数组）、"
    "relevant_resources（字符串数组）、unresolved_questions（字符串数组）。\n"
    "只依据公开观察与公开动作结果制定计划；不要臆造未公开信息。"
)

#: 计划监控用的公开进度字段（各图 PUBLIC_FIELDS 的子集，缺失即忽略）。
PROGRESS_FIELDS: tuple[str, ...] = (
    "tick",
    "ticks_remaining",
    "action_budget_remaining",
    "moves_used",
    "tick_count",
    "delivered_passengers",
    "canceled_passengers",
    "ruin_recorded",
    "chain_reconciled",
    "candidate_sites",
    "candidate_faults",
    "test_results",
    "installed_part",
    "wear",
    "spares",
    "casebook",
    "task_status",
)


def progress_signature(observation: PublicObservation) -> str:
    payload = {
        key: observation.fields.get(key)
        for key in PROGRESS_FIELDS
        if key in observation.fields
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


class PlanningPolicy:
    agent_id = "planning.v1"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        registration = get_agent(self.agent_id)
        self._identity = registration.identity
        self.config = registration.normalize_config(config)
        self.enabled = bool(self.config.get("enabled", True))
        self.replan_every = max(1, int(self.config.get("replan_every", 6)))
        self.max_plans = max(1, int(self.config.get("max_plans", 8)))
        self.history_window = int(self.config.get("history_window", 5))
        self._plan: dict[str, Any] | None = None
        self._plan_count = 0
        self._last_signature = ""
        self._stall = 0
        self._reject_streak = 0
        self._planner_requests = 0
        self._announced = False

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def reset(self, context: PublicEpisodeContext) -> None:
        self._plan = None
        self._plan_count = 0
        self._last_signature = ""
        self._stall = 0
        self._reject_streak = 0
        self._planner_requests = 0
        self._announced = False
        self._context = context

    def close(self) -> None:
        self._plan = None

    # ------------------------------------------------------------------- planner
    def _needs_plan(self, observation: PublicObservation) -> tuple[bool, str]:
        if self._plan is None:
            return True, "initial"
        signature = progress_signature(observation)
        if signature == self._last_signature:
            self._stall += 1
        else:
            self._stall = 0
            self._last_signature = signature
        if self._reject_streak >= 2:
            return True, "repeated_rejection"
        if self._stall >= self.replan_every:
            return True, "no_progress"
        return False, ""

    def _run_planner(
        self, observation: PublicObservation, context: AgentContext, trigger: str
    ) -> tuple[dict[str, Any] | None, int, int, int]:
        payload, response = context.gateway.ask_json(
            observation,
            purpose="planner",
            plan_data=plan_block(self._plan),
            recent_history=context.recent_history_text(limit=self.history_window),
            output_contract="planner",
            system_prompt=(
                "你在玩一个确定性回合制解密关卡。"
                f"{PLANNER_INSTRUCTIONS}"
            ),
        )
        self._planner_requests += 1
        if not payload:
            return None, 1, response.input_tokens, response.output_tokens
        criteria = payload.get("success_criteria")
        if isinstance(criteria, list):
            normalized = [
                bounded_text(item, limit=240) for item in criteria[:8] if str(item).strip()
            ]
        else:
            normalized = []
        plan = {
            "plan_index": self._plan_count + 1,
            "trigger": trigger,
            "decision_index": context.decision_index,
            "subgoal": bounded_text(payload.get("current_subgoal", ""), limit=240),
            "success_criteria": normalized,
            "known_constraints": [
                bounded_text(item, limit=240)
                for item in (payload.get("known_constraints") or [])[:12]
            ]
            if isinstance(payload.get("known_constraints"), list)
            else [],
            "relevant_resources": [
                bounded_text(item, limit=240)
                for item in (payload.get("relevant_resources") or [])[:12]
            ]
            if isinstance(payload.get("relevant_resources"), list)
            else [],
            "unresolved_questions": [
                bounded_text(item, limit=240)
                for item in (payload.get("unresolved_questions") or [])[:12]
            ]
            if isinstance(payload.get("unresolved_questions"), list)
            else [],
            "planner_reason": bounded_text(payload.get("decision_reason", ""), limit=280),
            "steps_since_plan": 0,
        }
        return plan, 1, response.input_tokens, response.output_tokens

    # -------------------------------------------------------------------- decide
    def decide(
        self, observation: PublicObservation, context: AgentContext
    ) -> AgentDecision:
        plan_event: AgentEvent | None = None
        extra_requests = 0
        plan_tokens_in = plan_tokens_out = 0
        if not self.enabled:
            if not self._announced:
                self._announced = True
                plan_event = AgentEvent(
                    kind="ablation",
                    event="planning_disabled",
                    decision_index=context.decision_index,
                    summary="规划关闭（消融臂）：不请求 Planner，也不注入计划。",
                    payload={"enabled": False},
                )
        else:
            needed, trigger = self._needs_plan(observation)
            if needed and self._plan_count < self.max_plans:
                plan, used, tokens_in, tokens_out = self._run_planner(
                    observation, context, trigger
                )
                extra_requests += used
                plan_tokens_in += tokens_in
                plan_tokens_out += tokens_out
                if plan is not None:
                    self._plan_count += 1
                    self._plan = plan
                    self._stall = 0
                    self._reject_streak = 0
                    self._last_signature = progress_signature(observation)
                    plan_event = AgentEvent(
                        kind="plan",
                        event="plan_created" if self._plan_count == 1 else "plan_replanned",
                        decision_index=context.decision_index,
                        summary=f"计划 #{self._plan_count}（{trigger}）：{plan['subgoal']}",
                        payload={
                            "trigger": trigger,
                            "plan_index": self._plan_count,
                            "subgoal": plan["subgoal"],
                            "success_criteria": plan["success_criteria"],
                            "plan_count": self._plan_count,
                            "max_plans": self.max_plans,
                        },
                        requests=used,
                        input_tokens=tokens_in,
                        output_tokens=tokens_out,
                    )
            elif needed and self._plan_count >= self.max_plans and not self._announced:
                self._announced = True
                plan_event = AgentEvent(
                    kind="plan",
                    event="plan_budget_exhausted",
                    decision_index=context.decision_index,
                    summary=f"计划次数已达上限（{self.max_plans}），继续使用最后一个计划。",
                    payload={"plan_count": self._plan_count, "max_plans": self.max_plans},
                )

        if self._plan is not None:
            self._plan["steps_since_plan"] = int(self._plan.get("steps_since_plan", 0)) + 1

        response = context.gateway.ask(
            observation,
            purpose="decision",
            plan_data=plan_block(self._plan) if self.enabled else None,
            recent_history=context.recent_history_text(limit=self.history_window),
            correction=context.invalid_streak > 0,
            invalid_output_reason="schema" if context.invalid_streak else None,
            estimate_text=context.full_history_text(),
        )
        return AgentDecision(
            action=extract_action_candidate(response.candidate),
            decision_reason=None,
            plan_event=plan_event,
            requests=1 + extra_requests,
        )

    def observe_result(self, outcome: PublicActionResult) -> None:
        if outcome.rejected:
            self._reject_streak += 1
        elif outcome.invalid:
            self._reject_streak += 1
        else:
            self._reject_streak = 0

    # --------------------------------------------------------------- diagnostics
    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "plan": compact_json(self._plan, limit=900) if self._plan else None,
            "plan_count": self._plan_count,
            "planner_requests": self._planner_requests,
            "max_plans": self.max_plans,
        }


__all__ = ["PLANNER_INSTRUCTIONS", "PROGRESS_FIELDS", "PlanningPolicy", "progress_signature"]
