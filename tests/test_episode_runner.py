from __future__ import annotations

import json
from pathlib import Path

from agent_arena.agents import CandidateSelectionAgent, ReactAgent
from agent_arena.arena import action_adapter
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation import (
    EpisodeOutcome,
    EpisodeRunner,
    InvalidOutputReason,
    TraceEvent,
    write_episode_trace,
)
from agent_arena.evaluation.runner import PublicCandidateTracker
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def settings(*, step_limit: int = 30) -> RuntimeSettings:
    return RuntimeSettings.model_validate(
        {
            "provider": "fake",
            "world": "spaceship-escape",
            "world_version": "spaceship-escape-v2-zh",
            "agent": "react",
            "seed": 0,
            "runs_dir": "runs",
            "results_dir": "results",
            "step_limit": step_limit,
            "request_timeout_seconds": 30,
            "retry_count": 2,
            "retry_backoff_seconds": [1, 2],
            "enable_thinking": False,
            "model_name": "qwen3.7-plus",
        }
    )


def decision(
    action: dict[str, str],
    reason: str = "Advance using public information.",
) -> dict[str, object]:
    return {"decision_reason": reason, "action": action}


def escape_decisions() -> list[object]:
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


def run(responses: list[object], *, step_limit: int = 30):
    provider = FakeDecisionProvider(responses)
    runner = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(step_limit=step_limit),
    )
    return runner.run(), provider


def test_runner_completes_the_public_escape_path_and_records_decision_observations() -> None:
    trace, provider = run(escape_decisions())

    assert trace.outcome is EpisodeOutcome.SUCCESS
    assert trace.executed_action_count == 20
    assert trace.invalid_output_count == 0
    assert len(provider.calls) == 20
    assert all(step.event is TraceEvent.ACTION_VALIDATED for step in trace.steps)
    assert trace.steps[0].observation.current_room == "control_room"
    assert trace.steps[0].action is not None
    assert trace.steps[0].action.tool == "move"
    assert trace.steps[0].input_tokens is None
    assert trace.steps[0].output_tokens is None
    assert trace.provenance.model_name == "qwen3.7-plus"
    assert trace.provenance.step_limit == 30
    assert len(trace.provenance.base_prompt_hash) == 64
    assert trace.provenance.base_prompt_version == "react_v12_autonomous"
    assert trace.provenance.runtime_feedback_enabled is True
    assert trace.provenance.provider_request_version == "decision_request_v1"


def test_runner_requests_one_correction_without_executing_the_invalid_candidate() -> None:
    trace, provider = run([{"not": "a decision"}, decision({"tool": "look"}), RuntimeError()])

    assert trace.outcome is EpisodeOutcome.PROVIDER_ERROR
    assert trace.invalid_output_count == 1
    assert trace.executed_action_count == 1
    assert [call.request.correction for call in provider.calls] == [False, True, False]
    assert [step.event for step in trace.steps] == [
        TraceEvent.ACTION_INVALID,
        TraceEvent.CORRECTION_REQUESTED,
        TraceEvent.ACTION_VALIDATED,
        TraceEvent.PROVIDER_ERROR,
    ]


def test_runner_stops_after_three_consecutive_invalid_candidates() -> None:
    trace, provider = run([{}, {}, {}])

    assert trace.outcome is EpisodeOutcome.INVALID_ACTION_LIMIT
    assert trace.invalid_output_count == 3
    assert trace.executed_action_count == 0
    assert [call.request.correction for call in provider.calls] == [False, True, False]


def test_runner_records_safe_invalid_output_categories() -> None:
    trace, _ = run([{}, {}, {}])

    assert trace.steps[0].invalid_output_reason is InvalidOutputReason.MISSING_FIELD
    assert trace.steps[2].invalid_output_reason is InvalidOutputReason.MISSING_FIELD


def test_runner_can_enable_public_action_hints_as_a_separate_experiment() -> None:
    provider = FakeDecisionProvider([decision({"tool": "look"}), RuntimeError()])
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(step_limit=1),
        enable_public_action_hints=True,
    ).run()

    assert trace.provenance.public_action_hints_enabled is True
    assert provider.calls[0].request.runtime_feedback is not None
    assert "move(destination=corridor)" in provider.calls[0].request.runtime_feedback


def test_environment_rejection_is_a_valid_action_not_an_invalid_model_output() -> None:
    trace, _ = run([decision({"tool": "move", "destination": "escape_pod"}), RuntimeError()])

    assert trace.outcome is EpisodeOutcome.PROVIDER_ERROR
    assert trace.rejected_action_count == 1
    assert trace.invalid_output_count == 0
    assert trace.steps[0].event is TraceEvent.ACTION_REJECTED


def test_runner_passes_public_repeat_failure_feedback_to_the_next_request() -> None:
    trace, provider = run(
        [
            decision({"tool": "move", "destination": "escape_pod"}),
            decision({"tool": "move", "destination": "escape_pod"}),
            RuntimeError(),
        ]
    )

    assert trace.outcome is EpisodeOutcome.PROVIDER_ERROR
    assert provider.calls[0].request.runtime_feedback is None
    assert provider.calls[1].request.runtime_feedback is None
    assert provider.calls[2].request.runtime_feedback is not None
    assert "已完成的动作" in provider.calls[2].request.runtime_feedback
    assert trace.steps[1].runtime_feedback == provider.calls[2].request.runtime_feedback


def test_runner_can_disable_runtime_feedback_for_autonomous_baseline() -> None:
    provider = FakeDecisionProvider(
        [
            decision({"tool": "move", "destination": "escape_pod"}),
            decision({"tool": "move", "destination": "escape_pod"}),
            RuntimeError(),
        ]
    )
    runner = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(),
        enable_runtime_feedback=False,
    )
    trace = runner.run()

    assert trace.provenance.runtime_feedback_enabled is False
    assert all(call.request.runtime_feedback is None for call in provider.calls)
    assert all(step.runtime_feedback is None for step in trace.steps)


def test_runner_can_send_bounded_public_recent_history() -> None:
    provider = FakeDecisionProvider(
        [
            decision({"tool": "look"}),
            decision({"tool": "move", "destination": "corridor"}),
            RuntimeError(),
        ]
    )
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(),
        recent_history_window=1,
    ).run()

    assert trace.provenance.recent_history_enabled is True
    assert trace.provenance.recent_history_window == 1
    assert provider.calls[0].request.recent_history is None
    assert provider.calls[1].request.recent_history is not None
    assert '"tool":"look"' in provider.calls[1].request.recent_history
    assert provider.calls[2].request.recent_history is not None
    assert '"tool":"move"' in provider.calls[2].request.recent_history
    assert '"tool":"look"' not in provider.calls[2].request.recent_history


def test_recent_history_is_disabled_by_default() -> None:
    provider = FakeDecisionProvider(
        [decision({"tool": "look"}), RuntimeError()]
    )
    EpisodeRunner(SpaceshipEscapeEnvironment(), ReactAgent(provider), settings()).run()
    assert all(call.request.recent_history is None for call in provider.calls)


def test_candidate_selection_resolves_an_opaque_public_candidate_id() -> None:
    provider = FakeDecisionProvider(
        [
            {"decision_reason": "探索可达出口。", "candidate_id": "a2"},
            RuntimeError(),
        ]
    )
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        CandidateSelectionAgent(provider),
        settings(),
        enable_candidate_selection=True,
        enable_runtime_feedback=False,
        enable_stuck_recovery=False,
    ).run()

    assert trace.outcome is EpisodeOutcome.PROVIDER_ERROR
    assert trace.executed_action_count == 1
    assert trace.steps[0].action == action_adapter.validate_python(
        {"tool": "move", "destination": "corridor"}
    )
    assert trace.provenance.candidate_selection_enabled is True
    assert provider.calls[0].request.output_contract == "candidate_selection"
    assert provider.calls[0].request.runtime_feedback is not None
    assert "a2=move(destination=corridor)" in provider.calls[0].request.runtime_feedback


def test_public_candidate_tracker_excludes_a_rejected_action_in_its_successor_state() -> None:
    environment = SpaceshipEscapeEnvironment()
    observation = environment.reset(0)
    tracker = PublicCandidateTracker()
    tracker.initialize(observation)
    action = action_adapter.validate_python({"tool": "read_terminal", "target": "control_terminal"})
    result, after = environment.step(action)
    tracker.observe(observation, action, result, after)

    identities = [candidate.action for candidate in tracker.candidates(after).values]
    assert action not in identities


def test_public_semantic_guard_rejects_only_publicly_invalid_actions() -> None:
    provider = FakeDecisionProvider(
        [
            decision({"tool": "move", "destination": "escape_pod"}),
            decision({"tool": "move", "destination": "corridor"}),
            RuntimeError(),
        ]
    )
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(),
        enable_public_action_guard=True,
        enable_runtime_feedback=False,
        enable_stuck_recovery=False,
    ).run()

    assert trace.provenance.public_action_guard_enabled is True
    assert trace.executed_action_count == 1
    assert trace.rejected_action_count == 1
    assert trace.steps[0].event is TraceEvent.ACTION_REJECTED
    assert trace.steps[0].result is None
    assert "available_exits" in (trace.steps[0].summary or "") or trace.steps[0].runtime_feedback
    assert trace.steps[1].event is TraceEvent.ACTION_VALIDATED


def test_public_semantic_guard_has_a_bounded_decision_budget() -> None:
    provider = FakeDecisionProvider(
        [decision({"tool": "move", "destination": "escape_pod"})] * 3
    )
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(step_limit=3),
        enable_public_action_guard=True,
    ).run()

    assert trace.outcome is EpisodeOutcome.STEP_LIMIT
    assert trace.executed_action_count == 0
    assert trace.rejected_action_count == 3
    assert len(provider.calls) == 3


def test_stuck_recovery_can_be_enabled_independently_of_default_runtime_feedback() -> None:
    provider = FakeDecisionProvider(
        [
            decision({"tool": "move", "destination": "escape_pod"}),
            decision({"tool": "move", "destination": "escape_pod"}),
            RuntimeError(),
        ]
    )
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(),
        enable_runtime_feedback=False,
        enable_stuck_recovery=True,
    ).run()

    assert trace.provenance.runtime_feedback_enabled is False
    assert trace.provenance.stuck_recovery_enabled is True
    assert provider.calls[2].request.runtime_feedback is not None


def test_runner_can_send_concrete_public_action_candidates() -> None:
    provider = FakeDecisionProvider([decision({"tool": "look"}), RuntimeError()])
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(step_limit=1),
        enable_concrete_action_candidates=True,
        enable_runtime_feedback=False,
        enable_stuck_recovery=False,
    ).run()

    assert trace.provenance.concrete_action_candidates_enabled is True
    feedback = provider.calls[0].request.runtime_feedback
    assert feedback is not None
    assert "look()" in feedback
    assert "move(destination=corridor)" in feedback
    assert "read_terminal(target=control_terminal)" in feedback


def test_runner_can_send_public_phase_context_without_route_guidance() -> None:
    provider = FakeDecisionProvider(
        [
            decision({"tool": "move", "destination": "corridor"}),
            decision({"tool": "move", "destination": "storage_room"}),
            decision({"tool": "inspect", "target": "storage_crate"}),
            decision({"tool": "pickup", "item": "screwdriver"}),
            RuntimeError(),
        ]
    )
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(),
        enable_public_phase_context=True,
        enable_runtime_feedback=False,
        enable_stuck_recovery=False,
    ).run()

    assert trace.provenance.public_phase_context_enabled is True
    initial_feedback = provider.calls[0].request.runtime_feedback
    assert initial_feedback is not None
    assert "收集修理工具" in initial_feedback
    assert "move(destination=" not in initial_feedback
    after_pickup = provider.calls[4].request.runtime_feedback
    assert after_pickup is not None
    assert "replacement_fuse" in after_pickup


def test_runner_stops_at_the_configured_environment_step_limit() -> None:
    trace, _ = run(
        [decision({"tool": "look"}), decision({"tool": "look"}), decision({"tool": "look"})],
        step_limit=3,
    )

    assert trace.outcome is EpisodeOutcome.STEP_LIMIT
    assert trace.executed_action_count == 3
    assert trace.invalid_output_count == 0


def test_runner_reports_each_new_decision_request() -> None:
    reported_steps: list[tuple[int, bool]] = []
    provider = FakeDecisionProvider(
        [{}, decision({"tool": "look"}), RuntimeError()]
    )
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(provider),
        settings(),
        on_decision_start=lambda step, correction: reported_steps.append((step, correction)),
    )
    trace = trace.run()

    assert trace.outcome is EpisodeOutcome.PROVIDER_ERROR
    assert reported_steps == [(1, False), (1, True), (2, False)]


def test_trace_writer_redacts_decision_and_provider_secret_like_text(tmp_path: Path) -> None:
    trace, _ = run(
        [
            decision({"tool": "look"}, reason="OPENAI_API_KEY=decision-secret"),
            RuntimeError("OPENAI_API_KEY=provider-secret"),
        ]
    )

    trace_path = write_episode_trace(trace, tmp_path)
    contents = trace_path.read_text(encoding="utf-8")
    parsed = json.loads(contents)

    assert "decision-secret" not in contents
    assert "provider-secret" not in contents
    assert "主控制中心" in contents
    assert parsed["steps"][0]["decision_reason"] == "OPENAI_API_KEY=[REDACTED]"
