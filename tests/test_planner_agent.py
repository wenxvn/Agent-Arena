from __future__ import annotations

from agent_arena.agents import PlannerAssistedAgent
from agent_arena.arena import Observation, ToolReason, ToolResult, ToolStatus, action_adapter
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation import EpisodeOutcome, EpisodeRunner
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def settings() -> RuntimeSettings:
    return RuntimeSettings.model_validate(
        {
            "provider": "fake",
            "world": "spaceship-escape",
            "world_version": "spaceship-escape-v2-zh",
            "agent": "planner_assisted",
            "seed": 0,
            "runs_dir": "runs",
            "results_dir": "results",
            "step_limit": 30,
            "request_timeout_seconds": 30,
            "retry_count": 2,
            "retry_backoff_seconds": [1, 2],
            "enable_thinking": False,
            "model_name": "test-model",
        }
    )


def decision(action: dict[str, str]) -> dict[str, object]:
    return {"decision_reason": "按公开规划建议推进。", "action": action}


def escape_actions() -> list[object]:
    return [
        decision({"tool": "move", "destination": "corridor"}),
        decision({"tool": "move", "destination": "storage_room"}),
        decision({"tool": "inspect", "target": "storage_crate"}),
        decision({"tool": "pickup", "item": "screwdriver"}),
        decision({"tool": "pickup", "item": "replacement_fuse"}),
        decision({"tool": "move", "destination": "corridor"}),
        decision({"tool": "move", "destination": "maintenance_room"}),
        decision({"tool": "read_terminal", "target": "diagnostic_terminal"}),
        decision({"tool": "move", "destination": "reactor_room"}),
        decision({"tool": "use", "item": "screwdriver", "target": "reactor_panel"}),
        decision({"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"}),
        decision({"tool": "move", "destination": "maintenance_room"}),
        decision({"tool": "move", "destination": "corridor"}),
        decision({"tool": "move", "destination": "control_room"}),
        decision({"tool": "read_terminal", "target": "control_terminal"}),
        decision({"tool": "move", "destination": "corridor"}),
        decision({"tool": "move", "destination": "maintenance_room"}),
        decision({"tool": "move", "destination": "reactor_room"}),
        decision({"tool": "move", "destination": "escape_pod"}),
        decision({"tool": "use", "item": "ALPHA-731", "target": "escape_pod"}),
    ]


def test_planner_passes_public_phase_guidance_to_provider() -> None:
    provider = FakeDecisionProvider([{}])
    agent = PlannerAssistedAgent(provider)
    environment = SpaceshipEscapeEnvironment()
    observation = environment.reset(0)

    agent.reset(observation)
    agent.request(observation, correction=False)

    request = provider.calls[0].request
    assert request.memory_data is not None
    assert request.runtime_feedback is not None
    assert "公开规划建议" in request.runtime_feedback
    assert "收集修理工具" in request.runtime_feedback
    assert "move(destination=corridor)" in request.runtime_feedback
    assert "ALPHA-731" not in request.system_prompt


def test_planner_keeps_authorization_code_from_public_result() -> None:
    provider = FakeDecisionProvider([{}])
    agent = PlannerAssistedAgent(provider)
    environment = SpaceshipEscapeEnvironment()
    observation = environment.reset(0)
    agent.reset(observation)

    # Feed only public contracts for the completed power and code stages.
    power_result = ToolResult(
        status=ToolStatus.SUCCESS,
        reason=ToolReason.POWER_RESTORED,
        summary="主电源已恢复。",
    )
    powered_observation = Observation(
        current_room="reactor_room",
        description="反应堆舱主电源已恢复。",
        visible_objects=(),
        available_exits=("maintenance_room",),
        inventory=("replacement_fuse", "screwdriver"),
        last_action_result=power_result,
    )
    agent.observe(
        action_adapter.validate_python(
            {"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"}
        ),
        power_result,
        powered_observation,
    )
    code_result = ToolResult(
        status=ToolStatus.SUCCESS,
        reason=ToolReason.CODE_READ,
        summary="逃生授权码：ALPHA-731",
    )
    agent.observe(
        action_adapter.validate_python({"tool": "read_terminal", "target": "control_terminal"}),
        code_result,
        powered_observation,
    )
    escape_observation = Observation(
        current_room="escape_pod",
        description="逃生舱等待授权码。",
        visible_objects=("escape_pod",),
        available_exits=("reactor_room",),
        inventory=("replacement_fuse", "screwdriver"),
        last_action_result=code_result,
    )
    agent.request(escape_observation, correction=False)

    assert provider.calls[-1].request.memory_data is not None
    assert "ALPHA-731" in provider.calls[-1].request.memory_data
    assert provider.calls[-1].request.runtime_feedback is not None
    assert "ALPHA-731" in provider.calls[-1].request.runtime_feedback


def test_planner_agent_fake_episode_is_labelled_and_completes() -> None:
    provider = FakeDecisionProvider(escape_actions())
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        PlannerAssistedAgent(provider),
        settings(),
    ).run()

    assert trace.outcome is EpisodeOutcome.SUCCESS
    assert trace.agent == "planner_assisted"
    assert trace.executed_action_count == 20
    assert trace.prompt_version == "planner_assisted_v2"
    assert trace.provenance.base_prompt_version == "react_v11"
