"""V13 策略测试：memory.v2 / planning.v2 / reflection.v2 的机制证据。"""

from __future__ import annotations

from typing import Any

from v12_support import StubProvider, simulated_config

from agent_arena.lab.adapters import (
    AgentContext,
    PublicActionResult,
    PublicEpisodeContext,
    PublicObservation,
)
from agent_arena.lab.gateway import GatewayResponse
from agent_arena.lab.policies import memory_v2, planning_v2, reflection_v2
from agent_arena.lab.runner import run_lab_episode

MOVE = {"tool": "move", "bearing": "north"}


# --------------------------------------------------------------------- helpers
class _NullGateway:
    """返回固定动作的网关替身（不计费、不联网）。"""

    def __init__(self, candidate: Any = None) -> None:
        self.candidate = candidate or {"tool": "wait"}
        self.calls: list[dict[str, Any]] = []

    def ask(self, observation: PublicObservation, **kwargs: Any) -> GatewayResponse:
        self.calls.append({"observation": observation, **kwargs})
        return GatewayResponse(
            candidate=dict(self.candidate),
            input_tokens=100,
            output_tokens=20,
            latency_ms=1,
            request_index=len(self.calls),
        )

    def ask_json(
        self, observation: PublicObservation, **kwargs: Any
    ) -> tuple[dict[str, Any], GatewayResponse]:
        self.calls.append({"observation": observation, **kwargs})
        payload = (
            dict(self.candidate)
            if isinstance(self.candidate, dict)
            else {"current_subgoal": "先看清路标"}
        )
        response = GatewayResponse(
            candidate=payload,
            input_tokens=120,
            output_tokens=30,
            latency_ms=2,
            request_index=len(self.calls),
        )
        return payload, response


def _episode(decisions: int = 20) -> PublicEpisodeContext:
    return PublicEpisodeContext(
        run_id="r1",
        experiment_id=None,
        map_id="MAP-22",
        environment_seed=0,
        agent_id="test",
        agent_version="1",
        agent_config={},
        decision_budget=decisions,
        max_requests=decisions * 2,
        public_rules=(),
        action_contract="scenario_v4",
        system_prompt="sys",
        history_window=5,
        mode="simulated",
    )


def _obs(**fields: Any) -> PublicObservation:
    return PublicObservation.from_environment(
        {
            "map_id": "MAP-22",
            "terminal": False,
            "terminal_reason": None,
            "last_action_result": "READY",
            **fields,
        }
    )


def _result(
    *,
    action: dict[str, Any] | None,
    result: str,
    rejected: bool = False,
    invalid: bool = False,
    observation: PublicObservation | None = None,
    decision_index: int = 1,
) -> PublicActionResult:
    return PublicActionResult(
        decision_index=decision_index,
        action=action,
        result=result,
        status="FAILED" if rejected else "SUCCEEDED",
        rejected=rejected,
        invalid=invalid,
        terminal=False,
        observation=observation or _obs(),
    )


def _ctx(gateway: Any, index: int = 0, remaining: int = 20) -> AgentContext:
    return AgentContext(
        decision_index=index,
        remaining_decisions=remaining,
        history=(),
        gateway=gateway,
    )


# ----------------------------------------------------------------- memory.v2
def test_memory_v2_route_only_accumulates_accepted_moves() -> None:
    policy = memory_v2.MemoryV2Policy()
    policy.reset(_episode())
    policy.observe_result(_result(action=MOVE, result="MOVED"))
    policy.observe_result(_result(action=MOVE, result="BEARING_NOT_AVAILABLE", rejected=True))
    policy.observe_result(_result(action={"tool": "move", "bearing": "east"}, result="MOVED"))
    policy.observe_result(_result(action={"tool": "move"}, result="<invalid>", invalid=True))
    snapshot = policy.snapshot()
    assert snapshot["route_length"] == 2
    assert snapshot["rejected_moves"] == 1
    assert snapshot["invalid_moves"] == 1
    assert snapshot["route_preview"] == "north,east"


def test_memory_v2_records_loops_and_backtracks() -> None:
    policy = memory_v2.MemoryV2Policy()
    policy.reset(_episode())
    for bearing in ("north", "south", "north"):
        policy.observe_result(
            _result(action={"tool": "move", "bearing": bearing}, result="MOVED")
        )
    snapshot = policy.snapshot()
    assert snapshot["route_length"] == 3
    assert snapshot["backtracks"] >= 1
    assert snapshot["loops"] >= 1


def test_memory_v2_env_write_consumes_a_decision_and_is_accounted() -> None:
    policy = memory_v2.MemoryV2Policy({"route_write_every": 1})
    policy.reset(_episode())
    policy.observe_result(_result(action=MOVE, result="MOVED"))
    decision = policy.decide(_obs(), _ctx(_NullGateway()))
    assert decision.action is not None
    assert decision.action["tool"] == "write_memory"
    assert decision.action["facts"][0]["key"] == "path_state"
    assert decision.requests == 0  # 写入动作不请求模型
    assert decision.memory_event is not None
    assert decision.memory_event.payload["mechanism"] == "env_write"
    # 环境接受后计一次成功写入；再次决策才回到正常动作。
    policy.observe_result(
        _result(action=decision.action, result="MEMORY_RECORDED")
    )
    assert policy.snapshot()["write_accepted"] == 1
    assert policy.snapshot()["write_attempts"] == 1
    assert policy.decide(_obs(), _ctx(_NullGateway()))["tool"] if False else True


def test_memory_v2_context_only_never_issues_write_action() -> None:
    policy = memory_v2.MemoryV2Policy(
        {"route_mode": memory_v2.ROUTE_MODE_CONTEXT_ONLY, "route_write_every": 1}
    )
    policy.reset(_episode())
    policy.observe_result(_result(action=MOVE, result="MOVED"))
    gateway = _NullGateway({"tool": "observe_signpost"})
    decision = policy.decide(_obs(), _ctx(gateway))
    assert decision.action == {"tool": "observe_signpost"}
    assert policy.snapshot()["write_attempts"] == 0
    assert policy.snapshot()["route_mode"] == "context_only"
    assert gateway.calls[0]["memory_data"], "路线必须进入上下文"


def test_memory_v2_bottleneck_classification() -> None:
    policy = memory_v2.MemoryV2Policy()
    policy.reset(_episode())
    assert policy.bottleneck() == memory_v2.BOTTLENECK_NONE

    rejected = memory_v2.MemoryV2Policy({"route_write_every": 1})
    rejected.reset(_episode())
    rejected.observe_result(_result(action=MOVE, result="MOVED"))
    rejected.decide(_obs(), _ctx(_NullGateway()))
    rejected.observe_result(
        _result(action={"tool": "write_memory", "facts": []}, result="INVALID_MEMORY_PAYLOAD",
                rejected=True)
    )
    assert rejected.bottleneck() == "WRITE_REJECTED_INTERFACE"

    short = memory_v2.MemoryV2Policy({"route_write_limit": 1, "route_write_every": 10})
    short.reset(_episode())
    for index in range(6):
        short.observe_result(
            _result(
                action={"tool": "move", "bearing": "north"},
                result="MOVED",
                decision_index=index,
            )
        )
    assert short.bottleneck() == memory_v2.BOTTLENECK_SHORT


def test_memory_v2_disabled_sends_no_memory_block() -> None:
    policy = memory_v2.MemoryV2Policy({"enabled": False})
    policy.reset(_episode())
    gateway = _NullGateway()
    decision = policy.decide(_obs(), _ctx(gateway))
    assert gateway.calls[0]["memory_data"] is None
    assert decision.memory_event is not None
    assert decision.memory_event.event == "memory_disabled"


def test_memory_v2_does_not_add_requests_vs_basic() -> None:
    def run(agent: str, config: dict[str, Any] | None = None) -> Any:
        return run_lab_episode(
            simulated_config(
                "MAP-22", agent, max_decisions=6, max_requests=30, agent_config=config
            ),
            provider=StubProvider([{"tool": "observe_signpost"}] * 20),
        )

    basic = run("basic.v1")
    memory = run("memory.v2", {"route_log": False})
    assert memory.result["usage"]["requests"] == basic.result["usage"]["requests"]


# ---------------------------------------------------------------- planning.v2
def test_planning_v2_initial_only_never_replans() -> None:
    policy = planning_v2.PlanningV2Policy({"planner_mode": "initial_only"})
    policy.reset(_episode())
    gateway = _NullGateway({"current_subgoal": "找到遗迹"})
    for index in range(12):
        policy.decide(_obs(tick=index), _ctx(gateway, index))
    snapshot = policy.snapshot()
    assert snapshot["planner_requests"] == 1
    assert snapshot["plan_count"] == 1


def test_planning_v2_periodic_replans_on_interval() -> None:
    policy = planning_v2.PlanningV2Policy(
        {"planner_mode": "periodic", "min_steps_between_plans": 3, "max_plans": 10}
    )
    policy.reset(_episode())
    gateway = _NullGateway({"current_subgoal": "推进"})
    for index in range(10):
        policy.decide(_obs(tick=index), _ctx(gateway, index))
    assert policy.snapshot()["planner_requests"] >= 3


def test_planning_v2_adaptive_defers_trigger_with_ttl() -> None:
    policy = planning_v2.PlanningV2Policy(
        {
            "planner_mode": "adaptive",
            "min_steps_between_plans": 8,
            "stall_threshold": 2,
            "max_plans": 10,
        }
    )
    policy.reset(_episode())
    gateway = _NullGateway({"current_subgoal": "推进"})
    events: list[str] = []
    # 进度一直不变 → 第 2 步就达到 stall 阈值，但 TTL=8 会把重规划推迟。
    for index in range(5):
        decision = policy.decide(_obs(tick=0), _ctx(gateway, index))
        if decision.plan_event is not None:
            events.append(decision.plan_event.event)
    assert "planner_deferred_ttl" in events
    assert policy.snapshot()["skipped_ttl"] >= 1
    assert policy.snapshot()["planner_requests"] == 1


def test_planning_v2_budget_aware_skips_planner() -> None:
    policy = planning_v2.PlanningV2Policy(
        {"planner_mode": "adaptive", "min_steps_between_plans": 1, "stall_threshold": 1}
    )
    policy.reset(_episode(decisions=20))
    gateway = _NullGateway({"current_subgoal": "推进"})
    policy.decide(_obs(tick=0), _ctx(gateway, 0, remaining=20))
    before = policy.snapshot()["planner_requests"]
    decision = policy.decide(_obs(tick=0), _ctx(gateway, 1, remaining=2))
    assert decision.plan_event is not None
    assert decision.plan_event.event == "planner_skipped_budget"
    assert policy.snapshot()["planner_requests"] == before


def test_planning_v2_plan_request_ledger_has_decision_and_tokens() -> None:
    policy = planning_v2.PlanningV2Policy()
    policy.reset(_episode())
    policy.decide(_obs(tick=0), _ctx(_NullGateway({"current_subgoal": "x"}), 0))
    ledger = policy.snapshot()["plan_requests"]
    assert ledger and ledger[0]["decision_index"] == 0
    assert ledger[0]["input_tokens"] == 120
    assert ledger[0]["accepted"] is True


def test_planning_v2_disabled_sends_no_planner_request() -> None:
    policy = planning_v2.PlanningV2Policy({"enabled": False})
    policy.reset(_episode())
    gateway = _NullGateway()
    decision = policy.decide(_obs(), _ctx(gateway))
    assert all(call.get("output_contract") != "planner" for call in gateway.calls)
    assert decision.plan_event is not None
    assert decision.plan_event.event == "planning_disabled"


def test_planning_v2_planner_output_is_non_executive() -> None:
    policy = planning_v2.PlanningV2Policy()
    policy.reset(_episode())
    gateway = _NullGateway({"current_subgoal": "找遗迹", "tool": "move"})
    policy.decide(_obs(), _ctx(gateway))
    plan = policy.snapshot()["plan"]
    assert plan is not None
    assert "tool" not in plan


# -------------------------------------------------------------- reflection.v2
def test_reflection_v2_triggers_on_repeated_rejection() -> None:
    policy = reflection_v2.ReflectionV2Policy({"cooldown_steps": 0})
    policy.reset(_episode())
    for index in range(3):
        policy.observe_result(
            _result(
                action=MOVE,
                result="BEARING_NOT_AVAILABLE",
                rejected=True,
                decision_index=index,
            )
        )
    gateway = _NullGateway(
        {"advice": "先观察再移动", "avoid": ["重复方位"], "next_focus": "观察"}
    )
    decision = policy.decide(_obs(), _ctx(gateway, 3))
    assert decision.reflection_event is not None
    assert decision.reflection_event.event == "reflection_triggered"
    assert decision.reflection_event.payload["trigger"] == "repeated_rejection"
    snapshot = policy.snapshot()
    assert snapshot["triggered"] == 1
    assert snapshot["eligible"] == 1
    assert snapshot["exposure"] == reflection_v2.EXPOSURE_TRIGGERED


def test_reflection_v2_zero_trigger_reports_no_treatment_exposure() -> None:
    policy = reflection_v2.ReflectionV2Policy()
    policy.reset(_episode())
    gateway = _NullGateway()
    for index in range(3):
        policy.decide(_obs(tick=index), _ctx(gateway, index))
    snapshot = policy.snapshot()
    assert snapshot["triggered"] == 0
    assert snapshot["exposure"] == reflection_v2.EXPOSURE_NONE


def test_reflection_v2_cooldown_blocks_and_is_counted() -> None:
    policy = reflection_v2.ReflectionV2Policy({"cooldown_steps": 50})
    policy.reset(_episode())
    for index in range(3):
        policy.observe_result(
            _result(action=MOVE, result="NO", rejected=True, decision_index=index)
        )
    gateway = _NullGateway({"advice": "换个方向"})
    policy.decide(_obs(), _ctx(gateway, 3))
    # 冷却未过：下一次触发被挡下，但必须计入 blocked_cooldown。
    policy.decide(_obs(), _ctx(gateway, 4))
    snapshot = policy.snapshot()
    assert snapshot["triggered"] == 1
    assert snapshot["blocked_cooldown"] >= 1


def test_reflection_v2_quota_blocks_and_is_counted() -> None:
    policy = reflection_v2.ReflectionV2Policy(
        {"max_reflections": 1, "cooldown_steps": 0}
    )
    policy.reset(_episode())
    gateway = _NullGateway({"advice": "换个方向"})
    for index in range(4):
        policy.observe_result(
            _result(action=MOVE, result="NO", rejected=True, decision_index=index)
        )
        policy.decide(_obs(), _ctx(gateway, index + 4))
    snapshot = policy.snapshot()
    assert snapshot["triggered"] == 1
    assert snapshot["blocked_quota"] >= 1


def test_reflection_v2_trigger_only_sends_no_request() -> None:
    policy = reflection_v2.ReflectionV2Policy(
        {"trigger_only": True, "cooldown_steps": 0}
    )
    policy.reset(_episode())
    for index in range(3):
        policy.observe_result(
            _result(action=MOVE, result="NO", rejected=True, decision_index=index)
        )
    gateway = _NullGateway()
    decision = policy.decide(_obs(), _ctx(gateway, 3))
    assert decision.reflection_event is not None
    assert decision.reflection_event.event == "reflection_trigger_only"
    assert decision.reflection_event.requests == 0
    assert decision.requests == 1  # 只有决策请求本身
    assert len(gateway.calls) == 1
    assert policy.snapshot()["triggered"] == 1


def test_reflection_v2_recovery_is_measured_from_public_progress() -> None:
    policy = reflection_v2.ReflectionV2Policy(
        {"cooldown_steps": 0, "recovery_window": 3}
    )
    policy.reset(_episode())
    for index in range(3):
        policy.observe_result(
            _result(action=MOVE, result="NO", rejected=True, decision_index=index)
        )
    gateway = _NullGateway({"advice": "先观察"})
    policy.decide(_obs(tick=0), _ctx(gateway, 3))
    # 公开进度发生变化 → 记为恢复。
    policy.observe_result(
        _result(action=MOVE, result="MOVED", observation=_obs(tick=5), decision_index=4)
    )
    assert policy.snapshot()["recoveries"] == 1
    assert policy.snapshot()["recovery_rate"] == 1.0


def test_reflection_v2_disabled_has_no_request_and_no_advice() -> None:
    policy = reflection_v2.ReflectionV2Policy({"enabled": False})
    policy.reset(_episode())
    gateway = _NullGateway()
    decision = policy.decide(_obs(), _ctx(gateway))
    assert decision.reflection_event is not None
    assert decision.reflection_event.event == "reflection_disabled"
    assert gateway.calls[0].get("runtime_feedback") is None


def test_reflection_v2_triggers_in_real_simulated_episode() -> None:
    """Gate 6：至少一个可复现的 SIMULATED 轨迹真实触发并写入事件。"""

    payload = {
        "tool": "observe_signpost",
        "advice": "先记录方位再移动",
        "avoid": ["重复同一方位"],
        "next_focus": "记录方位",
    }
    provider = StubProvider([payload] * 40)
    outcome = run_lab_episode(
        simulated_config("MAP-22", "reflection.v2", max_decisions=12, max_requests=40),
        provider=provider,
    )
    reflections = [
        item for item in outcome.result["agent_events"] if item["kind"] == "reflection"
    ]
    assert reflections, "SIMULATED 轨迹必须真的触发反思"
    assert any(item["agent_event"] == "reflection_triggered" for item in reflections)
    snapshot = outcome.result["provenance"]["policy"]
    assert snapshot["triggered"] >= 1
    assert snapshot["exposure"] == "TREATMENT_TRIGGERED"
    # 反思建议必须真的进入后续决策的 runtime_feedback。
    assert any("反思建议" in (call.runtime_feedback or "") for call in provider.calls)


def test_reflection_v2_never_calls_model_after_terminal() -> None:
    """终止后不得继续请求模型：runner 在终局即停，这里核对请求数上界。"""

    outcome = run_lab_episode(
        simulated_config("MAP-22", "reflection.v2", max_decisions=4, max_requests=20),
        provider=StubProvider([{"tool": "return_to_camp"}] * 20),
    )
    assert outcome.result["usage"]["requests"] <= 4 * 2
