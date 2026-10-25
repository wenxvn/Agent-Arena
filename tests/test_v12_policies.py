"""V12 策略测试：记忆/规划/反思事件、消融开关、状态隔离与公开边界。"""

from __future__ import annotations

import json
from typing import Any

from v12_support import StubProvider, simulated_config

from agent_arena.lab.adapters import PublicObservation
from agent_arena.lab.policies.basic import BasicPolicy
from agent_arena.lab.policies.external import ExternalPolicyAdapter
from agent_arena.lab.policies.memory import MemoryPolicy
from agent_arena.lab.runner import run_lab_episode
from agent_arena.web.schemas import RunState

OBSERVE = {"tool": "observe_signpost"}


def _planner_payload(subgoal: str = "先找到遗迹") -> dict[str, Any]:
    return {
        "tool": "observe_signpost",
        "decision_reason": "先看清当前路标",
        "current_subgoal": subgoal,
        "success_criteria": ["到达遗迹", "返回营地"],
        "known_constraints": ["只能看到当前路标"],
        "relevant_resources": ["方位"],
        "unresolved_questions": ["遗迹在哪个方向"],
    }


def _reflection_payload() -> dict[str, Any]:
    return {
        "tool": "observe_signpost",
        "advice": "先记录方位再移动，避免原地打转",
        "avoid": ["重复同一方位"],
        "next_focus": "记录方位",
    }


def _run(agent: str, provider: StubProvider, *, config: dict[str, Any] | None = None) -> Any:
    return run_lab_episode(
        simulated_config("MAP-22", agent, max_decisions=8, max_requests=40, **(config or {})),
        provider=provider,
    )


# ---------------------------------------------------------------------- memory
def test_memory_policy_emits_update_events_and_injects_block() -> None:
    provider = StubProvider([OBSERVE] * 8)
    outcome = _run("memory.v1", provider)
    events = [item for item in outcome.result["agent_events"] if item["kind"] == "memory"]
    assert events, "记忆策略必须产生 memory 事件"
    assert any(item["agent_event"] == "memory_updated" for item in events)
    # 第一次决策还没有历史记忆之外的状态，之后应把公开字段注入 memory_data。
    assert any(request.memory_data for request in provider.calls)
    payload = events[0]["payload"]
    assert payload["capacity"] >= 1
    assert outcome.result["provenance"]["policy"]["enabled"] is True


def test_memory_policy_respects_capacity() -> None:
    provider = StubProvider([OBSERVE] * 8)
    outcome = _run("memory.v1", provider, config={"agent_config": {"capacity": 3}})
    snapshot = outcome.result["provenance"]["policy"]
    assert snapshot["size"] <= 3
    assert snapshot["capacity"] == 3
    assert snapshot["evictions"] >= 0


def test_memory_ablation_off_removes_memory_data() -> None:
    provider = StubProvider([OBSERVE] * 4)
    outcome = _run("memory.v1", provider, config={"agent_config": {"enabled": False}})
    assert all(request.memory_data is None for request in provider.calls)
    events = [item for item in outcome.result["agent_events"] if item["kind"] == "ablation"]
    assert any(item["agent_event"] == "memory_disabled" for item in events)
    assert outcome.result["agent_config_hash"] != MemoryPolicy().config and True


def test_memory_reset_clears_facts() -> None:
    policy = MemoryPolicy({"capacity": 5})
    policy.reset(_context())
    observation = PublicObservation.from_environment(
        {
            "map_id": "MAP-22",
            "terminal": False,
            "terminal_reason": None,
            "last_action_result": "READY",
            "current_sign": "camp",
            "bearings": ["west"],
        }
    )
    from agent_arena.lab.adapters import AgentContext

    gateway = _NullGateway()
    policy.decide(observation, AgentContext(0, 10, (), gateway))
    assert policy.snapshot()["size"] > 0
    policy.reset(_context())
    # reset 只保留 episode 级别的三条基础事实。
    assert policy.snapshot()["size"] == 3


def test_memory_does_not_add_requests() -> None:
    basic = _run("basic.v1", StubProvider([OBSERVE] * 6))
    memory = _run("memory.v1", StubProvider([OBSERVE] * 6))
    assert memory.result["usage"]["requests"] == basic.result["usage"]["requests"]


# -------------------------------------------------------------------- planning
def test_planning_creates_plan_and_counts_planner_requests() -> None:
    provider = StubProvider([_planner_payload()] * 10)
    outcome = _run("planning.v1", provider)
    plan_events = [item for item in outcome.result["agent_events"] if item["kind"] == "plan"]
    assert plan_events[0]["agent_event"] == "plan_created"
    assert outcome.result["usage"]["purposes"]["planner"] >= 1
    assert outcome.result["usage"]["requests"] > outcome.result["decision_count"]
    planner_calls = [call for call in provider.calls if call.output_contract == "planner"]
    assert planner_calls, "Planner 必须使用非执行性输出契约"
    assert "Planner" in planner_calls[0].system_prompt
    decision_calls = [call for call in provider.calls if call.output_contract == "action"]
    assert any(call.plan_data for call in decision_calls)


def test_planning_replans_on_no_progress() -> None:
    provider = StubProvider([_planner_payload()] * 12)
    outcome = _run(
        "planning.v1", provider, config={"agent_config": {"replan_every": 2, "max_plans": 4}}
    )
    events = [
        item["agent_event"]
        for item in outcome.result["agent_events"]
        if item["kind"] == "plan"
    ]
    assert "plan_replanned" in events
    assert outcome.result["usage"]["purposes"]["planner"] >= 2


def test_planning_ablation_off_sends_no_planner_request() -> None:
    provider = StubProvider([OBSERVE] * 6)
    outcome = _run("planning.v1", provider, config={"agent_config": {"enabled": False}})
    assert all(call.output_contract == "action" for call in provider.calls)
    assert outcome.result["usage"]["purposes"].get("planner", 0) == 0
    events = [item for item in outcome.result["agent_events"] if item["kind"] == "ablation"]
    assert any(item["agent_event"] == "planning_disabled" for item in events)


def test_planning_respects_max_plans() -> None:
    provider = StubProvider([_planner_payload()] * 20)
    outcome = _run(
        "planning.v1", provider, config={"agent_config": {"replan_every": 1, "max_plans": 2}}
    )
    assert outcome.result["usage"]["purposes"]["planner"] <= 2


# ------------------------------------------------------------------ reflection
def test_reflection_triggers_on_repeated_action() -> None:
    provider = StubProvider([OBSERVE] * 8 + [_reflection_payload()] * 4)
    outcome = _run("reflection.v1", provider)
    reflections = [
        item for item in outcome.result["agent_events"] if item["kind"] == "reflection"
    ]
    assert reflections, "连续重复动作应触发反思"
    payload = reflections[0]["payload"]
    assert payload["trigger"] in {"repeated_action", "no_progress", "budget_drain"}
    assert reflections[0]["requests"] == 1
    assert outcome.result["usage"]["purposes"]["reflection"] >= 1


def test_reflection_is_bounded_by_max_reflections() -> None:
    provider = StubProvider([_reflection_payload()] * 40)
    outcome = _run(
        "reflection.v1",
        provider,
        config={"agent_config": {"max_reflections": 2, "cooldown_steps": 0}},
    )
    assert outcome.result["usage"]["purposes"].get("reflection", 0) <= 2


def test_reflection_cooldown_limits_frequency() -> None:
    provider = StubProvider([_reflection_payload()] * 40)
    outcome = _run(
        "reflection.v1",
        provider,
        config={"agent_config": {"max_reflections": 3, "cooldown_steps": 100}},
    )
    assert outcome.result["usage"]["purposes"].get("reflection", 0) == 1


def test_reflection_ablation_off_sends_no_reflection() -> None:
    provider = StubProvider([OBSERVE] * 10)
    outcome = _run("reflection.v1", provider, config={"agent_config": {"enabled": False}})
    assert outcome.result["usage"]["purposes"].get("reflection", 0) == 0
    assert all(call.runtime_feedback is None for call in provider.calls)
    events = [item for item in outcome.result["agent_events"] if item["kind"] == "ablation"]
    assert any(item["agent_event"] == "reflection_disabled" for item in events)


def test_reflection_trigger_is_rule_based_not_model_decided() -> None:
    """触发器必须来自公开规则：模型输出里的“建议反思/trigger”字段不会被采信。"""

    memory_write = {
        "tool": "write_memory",
        "facts": [{"key": "note", "value": "x"}],
        "advice": "请反思",
        "trigger": "no_progress",
    }
    alternating = [
        {**OBSERVE, "advice": "请反思", "trigger": "no_progress"},
        memory_write,
    ] * 4
    provider = StubProvider(alternating)
    outcome = _run(
        "reflection.v1",
        provider,
        config={
            "agent_config": {
                "max_reflections": 1,
                "stall_threshold": 99,
                "reject_threshold": 99,
            }
        },
    )
    assert outcome.result["usage"]["purposes"].get("reflection", 0) == 0
    assert all(call.runtime_feedback is None for call in provider.calls)


# -------------------------------------------------------------------- external
def test_external_adapter_only_sees_public_fields() -> None:
    class Plugin:
        def __init__(self) -> None:
            self.seen: list[dict[str, Any]] = []

        def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
            self.seen.append(observation)
            return {"tool": "observe_signpost"}

    plugin = Plugin()
    adapter = ExternalPolicyAdapter("basic.v1", plugin, config={})
    from agent_arena.lab.adapters import AgentContext

    observation = PublicObservation.from_environment(
        {
            "map_id": "MAP-22",
            "terminal": False,
            "terminal_reason": None,
            "last_action_result": "READY",
            "current_sign": "camp",
            "bearings": ["west"],
            "agent_notes": [],
        }
    )
    decision = adapter.decide(observation, AgentContext(0, 5, (), _NullGateway()))
    assert decision.action == {"tool": "observe_signpost"}
    text = json.dumps(plugin.seen, ensure_ascii=False)
    for forbidden in ("sealed_truth", "judge_state", "truth_seal"):
        assert forbidden not in text


def test_public_observation_rejects_hidden_truth() -> None:
    import pytest

    from agent_arena.lab.adapters import LeakageError

    with pytest.raises(LeakageError):
        PublicObservation.from_environment(
            {
                "map_id": "MAP-22",
                "terminal": False,
                "terminal_reason": None,
                "last_action_result": "READY",
                "sealed_truth": {"graph": {}},
            }
        )


# ---------------------------------------------------------------------- shared
class _NullGateway:
    """只用于直接调用策略的单元测试；不发送任何请求。"""

    class _Response:
        candidate: dict[str, Any] = {"tool": "observe_signpost"}
        input_tokens = 10
        output_tokens = 5
        latency_ms = 1
        request_index = 1

    def ask(self, observation: Any, **kwargs: Any) -> Any:
        del observation, kwargs
        return self._Response()

    def ask_json(self, observation: Any, **kwargs: Any) -> tuple[dict[str, Any], Any]:
        del observation, kwargs
        return {}, self._Response()


def _context() -> Any:
    from agent_arena.lab.adapters import PublicEpisodeContext

    return PublicEpisodeContext(
        run_id="run",
        experiment_id=None,
        map_id="MAP-22",
        environment_seed=0,
        agent_id="memory.v1",
        agent_version="1.0.0",
        agent_config={},
        decision_budget=10,
        max_requests=20,
        public_rules=(),
        action_contract="",
        system_prompt="",
        history_window=5,
        mode="simulated",
    )


def test_basic_policy_is_stateless() -> None:
    policy = BasicPolicy()
    policy.reset(_context())
    observation = PublicObservation.from_environment(
        {
            "map_id": "MAP-22",
            "terminal": False,
            "terminal_reason": None,
            "last_action_result": "READY",
            "current_sign": "camp",
        }
    )
    from agent_arena.lab.adapters import AgentContext

    decision = policy.decide(observation, AgentContext(0, 5, (), _NullGateway()))
    assert decision.action == {"tool": "observe_signpost"}
    assert decision.events() == []
    policy.close()


def test_policy_factory_returns_fresh_instances() -> None:
    from agent_arena.lab.registry import get_agent

    for agent_id in ("basic.v1", "memory.v1", "planning.v1", "reflection.v1"):
        factory = get_agent(agent_id).factory()
        first = factory({})
        second = factory({})
        assert first is not second, agent_id


def test_all_policies_can_run_a_short_episode_without_state_bleed() -> None:
    for agent_id in ("basic.v1", "memory.v1", "planning.v1", "reflection.v1"):
        first = _run(agent_id, StubProvider([_planner_payload()] * 30))
        second = _run(agent_id, StubProvider([_planner_payload()] * 30))
        assert first.result["state"] in {
            RunState.SUCCEEDED.value,
            RunState.FAILED.value,
            RunState.BUDGET_REACHED.value,
        }
        assert first.result["decision_count"] == second.result["decision_count"]
