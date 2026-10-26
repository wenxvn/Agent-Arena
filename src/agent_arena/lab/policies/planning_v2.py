"""``planning.v2``：可配置的规划 / 重规划策略（P0-3 / V13-04-02 … 04-06）。

``planning.v1`` 的重规划只有"初始 + 连续无进展 + 连续被拒"三种，且没有节流。
``planning.v2`` 把重规划拆成**三个可分别开关的因子**（V13-04-05 要求"分离消融"）：

| 配置 | 含义 | 对应消融 |
|---|---|---|
| `planner_mode=initial_only` | 只规划一次，永不重规划 | **重规划关** |
| `planner_mode=periodic` | 每 `min_steps_between_plans` 步强制重规划 | **低频/高频 Planner** |
| `planner_mode=adaptive`（默认） | 只在公开触发条件成立时重规划 | 规划开 |
| `enabled=False` | 完全不请求 Planner、不注入计划 | **规划关** |

其余设计：

- Planner 输出仍然只有**非执行性**字段（子目标、公开完成条件、约束、未决问题），
  不输出 tool/action，也不读取任何私有状态；
- 每次 Planner 请求写入 ``plan_request`` 记录：触发原因、关联决策、token、
  延迟，便于逐请求归因成本；
- **TTL 是下限不是上限**：`min_steps_between_plans` 会延迟触发；文档与测试都明确
  这一点（"过期而不及时改计划"是已知代价，不是 bug 隐藏）；
- `budget_aware=True` 时，剩余决策不足时不再请求 Planner（省预算，但会记录跳过）。
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
    plan_block,
)
from agent_arena.lab.policies.planning import PLANNER_INSTRUCTIONS, progress_signature
from agent_arena.lab.registry import get_agent

MODE_ADAPTIVE = "adaptive"
MODE_INITIAL_ONLY = "initial_only"
MODE_PERIODIC = "periodic"
PLANNER_MODES = (MODE_ADAPTIVE, MODE_INITIAL_ONLY, MODE_PERIODIC)

TRIGGER_INITIAL = "initial"
TRIGGER_STALL = "no_progress"
TRIGGER_REJECT = "repeated_rejection"
TRIGGER_PROGRESS = "public_progress"
TRIGGER_PERIODIC = "periodic"
TRIGGER_GOAL_CHANGED = "goal_completed_or_changed"

#: 预算感知：剩余决策低于该比例时不再请求 Planner。
BUDGET_GUARD_RATIO = 0.25


class PlanningV2Policy:
    agent_id = "planning.v2"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        registration = get_agent(self.agent_id)
        self._identity = registration.identity
        self.config = registration.normalize_config(config)
        self.enabled = bool(self.config.get("enabled", True))
        self.planner_mode = str(self.config.get("planner_mode", MODE_ADAPTIVE))
        if self.planner_mode not in PLANNER_MODES:
            raise ValueError(
                f"planner_mode 只能是 {PLANNER_MODES}，收到 {self.planner_mode}"
            )
        self.min_steps_between_plans = max(
            1, int(self.config.get("min_steps_between_plans", 4))
        )
        self.stall_threshold = max(1, int(self.config.get("stall_threshold", 4)))
        self.reject_threshold = max(1, int(self.config.get("reject_threshold", 2)))
        self.max_plans = max(1, int(self.config.get("max_plans", 6)))
        self.budget_aware = bool(self.config.get("budget_aware", True))
        self.history_window = int(self.config.get("history_window", 5))
        self._reset_state()

    def _reset_state(self) -> None:
        self._plan: dict[str, Any] | None = None
        self._plan_count = 0
        self._last_signature = ""
        self._stall = 0
        self._reject_streak = 0
        self._planner_requests = 0
        self._planner_tokens_in = 0
        self._planner_tokens_out = 0
        self._last_plan_step = -999
        self._plan_requests: list[dict[str, Any]] = []
        self._skipped_budget = 0
        self._skipped_ttl = 0
        self._goal_public: str = ""
        self._decision_budget = 1
        self._announced = False

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def reset(self, context: PublicEpisodeContext) -> None:
        self._reset_state()
        self._context = context
        self._decision_budget = max(1, int(context.decision_budget))

    def close(self) -> None:
        self._plan = None

    # ------------------------------------------------------------------- trigger
    def _public_goal(self, observation: PublicObservation) -> str:
        goal = observation.fields.get("goal")
        if isinstance(goal, str):
            return goal[:240]
        return ""

    def _trigger(
        self, observation: PublicObservation, context: AgentContext
    ) -> tuple[str, dict[str, Any]] | None:
        """返回 (trigger, evidence) 或 None。所有判据都是公开信息。"""

        if self._plan is None:
            return TRIGGER_INITIAL, {"decision_index": context.decision_index}

        signature = progress_signature(observation)
        changed = signature != self._last_signature
        if not changed:
            self._stall += 1
        else:
            self._stall = 0
            self._last_signature = signature

        goal = self._public_goal(observation)
        if goal and goal != self._goal_public:
            return TRIGGER_GOAL_CHANGED, {"goal_before": self._goal_public, "goal": goal}

        if self.planner_mode == MODE_INITIAL_ONLY:
            return None

        if self.planner_mode == MODE_PERIODIC:
            steps = context.decision_index - self._last_plan_step
            if steps >= self.min_steps_between_plans:
                return TRIGGER_PERIODIC, {"steps_since_plan": steps}
            return None

        # adaptive：只有公开触发条件成立才重规划。
        if self._reject_streak >= self.reject_threshold:
            return TRIGGER_REJECT, {"reject_streak": self._reject_streak}
        if self._stall >= self.stall_threshold:
            return TRIGGER_STALL, {
                "stall_steps": self._stall,
                "threshold": self.stall_threshold,
            }
        if changed:
            # 公开进度刚发生变化：只有计划已经很旧时才重规划，避免每步都调 Planner。
            steps = context.decision_index - self._last_plan_step
            if steps >= self.min_steps_between_plans:
                return TRIGGER_PROGRESS, {"steps_since_plan": steps}
        return None

    # ------------------------------------------------------------------- planner
    def _run_planner(
        self, observation: PublicObservation, context: AgentContext, trigger: str
    ) -> tuple[dict[str, Any] | None, int, int, int, int]:
        payload, response = context.gateway.ask_json(
            observation,
            purpose="planner",
            plan_data=plan_block(self._plan),
            recent_history=context.recent_history_text(limit=self.history_window),
            output_contract="planner",
            system_prompt=("你在玩一个确定性回合制解密关卡。" + PLANNER_INSTRUCTIONS),
        )
        self._planner_requests += 1
        self._planner_tokens_in += response.input_tokens
        self._planner_tokens_out += response.output_tokens
        entry = {
            "plan_index": self._plan_count + 1,
            "trigger": trigger,
            "decision_index": context.decision_index,
            "requests": 1,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "latency_ms": response.latency_ms,
            "accepted": bool(payload),
        }
        self._plan_requests.append(entry)
        if not payload:
            return None, 1, response.input_tokens, response.output_tokens, response.latency_ms
        criteria = payload.get("success_criteria")
        normalized = (
            [
                bounded_text(item, limit=240)
                for item in criteria[:8]
                if str(item).strip()
            ]
            if isinstance(criteria, list)
            else []
        )

        def _list(name: str) -> list[str]:
            value = payload.get(name)
            if not isinstance(value, list):
                return []
            return [bounded_text(item, limit=240) for item in value[:12]]

        plan = {
            "plan_index": self._plan_count + 1,
            "trigger": trigger,
            "decision_index": context.decision_index,
            "subgoal": bounded_text(payload.get("current_subgoal", ""), limit=240),
            "success_criteria": normalized,
            "known_constraints": _list("known_constraints"),
            "relevant_resources": _list("relevant_resources"),
            "unresolved_questions": _list("unresolved_questions"),
            "planner_reason": bounded_text(payload.get("decision_reason", ""), limit=280),
            "steps_since_plan": 0,
            "public_only": True,
        }
        return (
            plan,
            1,
            response.input_tokens,
            response.output_tokens,
            response.latency_ms,
        )

    # -------------------------------------------------------------------- decide
    def decide(
        self, observation: PublicObservation, context: AgentContext
    ) -> AgentDecision:
        plan_event: AgentEvent | None = None
        extra_requests = 0
        if not self.enabled:
            if not self._announced:
                self._announced = True
                plan_event = AgentEvent(
                    kind="ablation",
                    event="planning_disabled",
                    decision_index=context.decision_index,
                    summary="规划关闭（消融臂）：不请求 Planner，也不注入计划。",
                    payload={"enabled": False, "version": "v2"},
                )
        else:
            trigger = self._trigger(observation, context)
            if trigger is not None and self._plan_count >= self.max_plans:
                if not self._announced:
                    self._announced = True
                    plan_event = AgentEvent(
                        kind="plan",
                        event="plan_budget_exhausted",
                        decision_index=context.decision_index,
                        summary=f"计划次数已达上限（{self.max_plans}），继续使用最后一个计划。",
                        payload={"plan_count": self._plan_count, "max_plans": self.max_plans},
                    )
            elif trigger is not None:
                name, evidence = trigger
                steps = context.decision_index - self._last_plan_step
                budget_guard = (
                    self.budget_aware
                    and self._plan is not None
                    and context.remaining_decisions
                    <= max(1, int(self._decision_budget * BUDGET_GUARD_RATIO))
                )
                # 预算感知：剩余决策很少时不再花钱规划（会记录跳过原因）。
                if budget_guard and name != TRIGGER_INITIAL:
                    self._skipped_budget += 1
                    plan_event = AgentEvent(
                        kind="plan",
                        event="planner_skipped_budget",
                        decision_index=context.decision_index,
                        summary="剩余决策预算不足，跳过本次重规划（预算感知）。",
                        payload={
                            "trigger": name,
                            "remaining_decisions": context.remaining_decisions,
                        },
                    )
                elif (
                    name != TRIGGER_INITIAL
                    and steps < self.min_steps_between_plans
                ):
                    # TTL 下限：触发被延迟——这是已知代价，必须留证据。
                    self._skipped_ttl += 1
                    plan_event = AgentEvent(
                        kind="plan",
                        event="planner_deferred_ttl",
                        decision_index=context.decision_index,
                        summary=(
                            f"重规划触发（{name}）被 TTL 延迟：距上次计划 {steps} 步 "
                            f"< {self.min_steps_between_plans}。"
                        ),
                        payload={
                            "trigger": name,
                            "steps_since_plan": steps,
                            "min_steps_between_plans": self.min_steps_between_plans,
                        },
                    )
                else:
                    plan, used, tokens_in, tokens_out, latency = self._run_planner(
                        observation, context, name
                    )
                    extra_requests += used
                    if plan is not None:
                        self._plan_count += 1
                        self._plan = plan
                        self._stall = 0
                        self._reject_streak = 0
                        self._last_signature = progress_signature(observation)
                        self._last_plan_step = context.decision_index
                        self._goal_public = self._public_goal(observation)
                        plan_event = AgentEvent(
                            kind="plan",
                            event=(
                                "plan_created"
                                if self._plan_count == 1
                                else "plan_replanned"
                            ),
                            decision_index=context.decision_index,
                            summary=f"计划 #{self._plan_count}（{name}）：{plan['subgoal']}",
                            payload={
                                "trigger": name,
                                "evidence": evidence,
                                "plan_index": self._plan_count,
                                "subgoal": plan["subgoal"],
                                "success_criteria": plan["success_criteria"],
                                "plan_count": self._plan_count,
                                "max_plans": self.max_plans,
                                "planner_mode": self.planner_mode,
                                "latency_ms": latency,
                                "steps_since_plan": 0,
                            },
                            requests=used,
                            input_tokens=tokens_in,
                            output_tokens=tokens_out,
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
        if outcome.rejected or outcome.invalid:
            self._reject_streak += 1
        else:
            self._reject_streak = 0

    # --------------------------------------------------------------- diagnostics
    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "version": "v2",
            "planner_mode": self.planner_mode,
            "plan": compact_json(self._plan, limit=900) if self._plan else None,
            "plan_count": self._plan_count,
            "planner_requests": self._planner_requests,
            "planner_tokens_in": self._planner_tokens_in,
            "planner_tokens_out": self._planner_tokens_out,
            "max_plans": self.max_plans,
            "skipped_budget": self._skipped_budget,
            "skipped_ttl": self._skipped_ttl,
            "plan_requests": list(self._plan_requests),
            "min_steps_between_plans": self.min_steps_between_plans,
            "budget_aware": self.budget_aware,
        }


def make_planning_v2(config: dict[str, Any] | None = None) -> PlanningV2Policy:
    return PlanningV2Policy(config)


__all__ = [
    "BUDGET_GUARD_RATIO",
    "MODE_ADAPTIVE",
    "MODE_INITIAL_ONLY",
    "MODE_PERIODIC",
    "PLANNER_MODES",
    "TRIGGER_GOAL_CHANGED",
    "TRIGGER_INITIAL",
    "TRIGGER_PERIODIC",
    "TRIGGER_PROGRESS",
    "TRIGGER_REJECT",
    "TRIGGER_STALL",
    "PlanningV2Policy",
    "make_planning_v2",
]
