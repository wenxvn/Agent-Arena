"""Regression checks for experiment identity, public progress and lifecycle boundaries."""

from __future__ import annotations

import json
from hashlib import sha256

import pytest
from test_episode_runner import settings
from test_planner_agent import decision, escape_actions
from typer.testing import CliRunner

from agent_arena.agents import PlannerAssistedAgent, ReactAgent
from agent_arena.arena import ToolReason, action_adapter
from agent_arena.cli import app
from agent_arena.evaluation import (
    EpisodeOutcome,
    EpisodeRunner,
    PublicLoopDetector,
    TraceEvent,
    read_episode_trace,
    write_episode_trace,
)
from agent_arena.evaluation.benchmark import row_from_trace, write_benchmark
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment, create_environment


def test_world_selector_rejects_unknown_world_and_version_before_provider(monkeypatch) -> None:
    for world, version in (("unknown", "spaceship-escape-v2-zh"), ("spaceship-escape", "unknown")):
        monkeypatch.setenv("AGENT_ARENA_WORLD", world)
        monkeypatch.setenv("AGENT_ARENA_WORLD_VERSION", version)
        monkeypatch.setattr(
            "agent_arena.cli._create_decision_provider",
            lambda _: pytest.fail("未知世界不得调用 provider"),
        )
        for command in ("run", "benchmark"):
            result = CliRunner().invoke(app, [command, "--provider", "fake"])
            assert result.exit_code == 2
            assert "不支持该世界或版本" in result.output


def test_runner_records_loaded_identity_and_rejects_mislabelling() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-v2-zh")
    provider = FakeDecisionProvider([decision({"tool": "look"})])
    trace = EpisodeRunner(environment, ReactAgent(provider), settings(step_limit=1)).run()
    assert trace.world_version == environment.identity[1]
    assert trace.provenance.world_definition_id == "spaceship_escape_v1"
    assert trace.provenance.world_definition_hash == environment.identity[3]
    changed = SpaceshipEscapeEnvironment(
        environment.definition.model_copy(update={"version": "new"})
    )
    with pytest.raises(ValueError, match="实际环境身份"):
        EpisodeRunner(changed, ReactAgent(provider), settings(step_limit=1)).run()
    assert len(provider.calls) == 1


def test_public_code_progress_allows_return_route_without_hiding_later_loops() -> None:
    environment = SpaceshipEscapeEnvironment()
    current = environment.reset(0)
    detector = PublicLoopDetector()
    detector.initialize(current)
    for candidate in escape_actions():
        action = action_adapter.validate_python(candidate["action"])
        result, after = environment.step(action)
        assert detector.observe(current, action, result, after) is None
        current = after
    # A repeated read is only new information once, even without visible state changes.
    environment.reset(0)
    detector.initialize(environment.observe())
    action = action_adapter.validate_python({"tool": "look"})
    before = environment.observe()
    result, after = environment.step(action)
    assert detector.observe(before, action, result, after) is None
    assert detector.observe(after, action, result, after) is not None
    detector.initialize(before)
    assert detector.observe(before, action, result, after) is None


def test_loop_detector_observes_new_exits_and_repeated_terminal_reads() -> None:
    environment = SpaceshipEscapeEnvironment()
    before = environment.reset(0)
    detector = PublicLoopDetector()
    detector.initialize(before)
    action = action_adapter.validate_python({"tool": "look"})
    result, _ = environment.step(action)
    detector.observe(before, action, result, before)
    changed = before.model_copy(update={"available_exits": ("corridor", "new_public_exit")})
    assert detector.observe(before, action, result, changed) is None
    # Reach the powered terminal using only actual public transitions.
    current = environment.reset(0)
    detector.initialize(current)
    for candidate in escape_actions()[:15]:
        act = action_adapter.validate_python(candidate["action"])
        result, after = environment.step(act)
        detector.observe(current, act, result, after)
        current = after
    read = action_adapter.validate_python({"tool": "read_terminal", "target": "control_terminal"})
    result, after = environment.step(read)
    assert detector.observe(current, read, result, after) is not None


def test_planner_guidance_matches_actual_request_and_does_not_override_model(tmp_path) -> None:
    candidates = [decision({"tool": "look"}), {"action": {"tool": "move"}}, *escape_actions()]
    provider = FakeDecisionProvider(candidates)
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(), PlannerAssistedAgent(provider), settings()
    ).run()
    assert trace.outcome is EpisodeOutcome.SUCCESS
    assert trace.executed_action_count == 21
    assert trace.steps[0].action.tool == "look"
    assert trace.steps[0].suggested_action.tool == "move"
    request_steps = [
        step for step in trace.steps if step.event is not TraceEvent.CORRECTION_REQUESTED
    ]
    assert len(request_steps) == len(provider.calls)
    for step, call in zip(request_steps, provider.calls, strict=True):
        assert step.planner_feedback in call.request.runtime_feedback
        assert step.planner_feedback_hash == sha256(step.planner_feedback.encode()).hexdigest()
        assert step.correction == call.request.correction
        assert (
            "WorldState" not in call.request.model_dump_json()
            if hasattr(call.request, "model_dump_json")
            else True
        )
    loaded = read_episode_trace(write_episode_trace(trace, tmp_path))
    assert loaded.steps == trace.steps
    row = row_from_trace(loaded, "benchmark", 0)
    assert row.guidance_deviation_count == 2  # look and optional diagnostic read
    assert row.guidance_comparable_count == 21
    assert row.code_read and row.escaped and row.power_restored and row.tools_collected
    assert all(step.suggested_action is not None for step in request_steps)


@pytest.mark.parametrize(
    "responses, expected",
    [
        (escape_actions(), EpisodeOutcome.SUCCESS),
        ([{}] * 3, EpisodeOutcome.INVALID_ACTION_LIMIT),
        ([RuntimeError("模型服务失败")], EpisodeOutcome.PROVIDER_ERROR),
        ([decision({"tool": "look"})] * 30, EpisodeOutcome.STEP_LIMIT),
    ],
)
def test_planner_finishes_once_and_can_be_reused_without_previous_state(
    responses, expected
) -> None:
    class RecordingPlanner(PlannerAssistedAgent):
        def __init__(self, provider):
            super().__init__(provider)
            self.finished = []

        def finish(self, outcome):
            self.finished.append(outcome)
            super().finish(outcome)

    provider = FakeDecisionProvider([*responses, *escape_actions()])
    agent = RecordingPlanner(provider)
    environment = SpaceshipEscapeEnvironment()
    runner = EpisodeRunner(environment, agent, settings())
    assert runner.run().outcome is expected
    assert agent.finished == [expected]
    assert agent.planner_feedback is None
    with pytest.raises(RuntimeError):
        agent.request(environment.observe(), correction=False)
    # Failed calls do not consume fixture responses because memory is inactive.
    boundary = len(provider.calls)
    assert runner.run().outcome is EpisodeOutcome.SUCCESS
    assert len(agent.finished) == 2
    first_request = provider.calls[boundary].request
    assert "收集修理工具" in first_request.runtime_feedback
    assert "ALPHA-731" not in first_request.memory_data
    assert "重复了同一公开状态" not in first_request.runtime_feedback


def test_guarded_hints_preserve_model_action_and_environment_rejection() -> None:
    action = {"tool": "move", "destination": "escape_pod"}
    provider = FakeDecisionProvider([decision(action), decision({"tool": "look"})])
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(step_limit=2),
        enable_public_action_hints=True,
    ).run()
    assert trace.executed_action_count == 2
    assert trace.steps[0].action.model_dump() == action
    assert trace.steps[0].result.reason is ToolReason.NOT_ADJACENT
    assert trace.steps[1].observation.current_room == "control_room"
    assert trace.provenance.public_action_hints_enabled
    assert "move(destination=corridor)" in provider.calls[0].request.runtime_feedback


def test_planner_route_table_only_suggests_actual_exits() -> None:
    environment = SpaceshipEscapeEnvironment()
    planner = PlannerAssistedAgent(FakeDecisionProvider([]))
    for room in environment.definition.rooms:
        for target, destination in planner._ROOM_ROUTES.get(room.id, {}).items():
            assert destination in room.exits, (room.id, target)
    reactor = environment.observe().model_copy(
        update={
            "current_room": "reactor_room",
            "available_exits": ("maintenance_room",),
        }
    )
    advice = planner._route_guidance(reactor, "escape_pod", "启动逃生舱")
    assert "move(destination=escape_pod)" not in advice
    assert "优先选择 escape_pod" not in advice


def test_metrics_separate_conditions_and_count_repetitions_and_failures(tmp_path) -> None:
    traces = []
    for assisted in (False, True):
        provider = FakeDecisionProvider([decision({"tool": "look"})] * 3)
        traces.append(
            EpisodeRunner(
                SpaceshipEscapeEnvironment(),
                ReactAgent(provider),
                settings(step_limit=3),
                enable_runtime_feedback=assisted,
            ).run()
        )
    rows = [row_from_trace(trace, "benchmark", index) for index, trace in enumerate(traces)]
    assert rows[0].repeated_action_ratio == pytest.approx(2 / 3)
    assert rows[0].max_consecutive_look == 3
    assert rows[0].unique_public_states == 1
    assert rows[0].guidance_deviation_rate is None
    assert rows[0].condition_id != rows[1].condition_id
    path, _ = write_benchmark(rows, tmp_path)
    payload = json.loads(path.read_text())
    assert payload["aggregates"] is None
    assert len(payload["conditions"]) == 2
    assert all(group["aggregates"]["success_rate"] == 0 for group in payload["conditions"].values())
    error = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(FakeDecisionProvider([])),
        settings(step_limit=3),
        enable_runtime_feedback=False,
    ).run()
    path, _ = write_benchmark([rows[0], row_from_trace(error, "benchmark", 2)], tmp_path)
    payload = json.loads(path.read_text())
    assert payload["aggregates"]["attempted"] == 2
    assert payload["aggregates"]["success_rate"] == 0


def test_invalid_unhashable_tool_is_recorded_without_crashing() -> None:
    provider = FakeDecisionProvider([{"decision_reason": "格式错误", "action": {"tool": []}}] * 3)
    trace = EpisodeRunner(SpaceshipEscapeEnvironment(), ReactAgent(provider), settings()).run()
    assert trace.outcome is EpisodeOutcome.INVALID_ACTION_LIMIT
    assert trace.executed_action_count == 0
