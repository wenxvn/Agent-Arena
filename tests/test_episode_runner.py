from __future__ import annotations

import json
from pathlib import Path

from agent_arena.agents import ReactAgent
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation import (
    EpisodeOutcome,
    EpisodeRunner,
    TraceEvent,
    write_episode_trace,
)
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def settings(*, step_limit: int = 30) -> RuntimeSettings:
    return RuntimeSettings.model_validate(
        {
            "provider": "fake",
            "world": "spaceship-escape",
            "world_version": "spaceship-escape-v1",
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


def test_runner_requests_one_correction_without_executing_the_invalid_candidate() -> None:
    trace, provider = run([{"not": "a decision"}, decision({"tool": "look"}), RuntimeError()])

    assert trace.outcome is EpisodeOutcome.PROVIDER_ERROR
    assert trace.invalid_output_count == 1
    assert trace.executed_action_count == 1
    assert [call.correction for call in provider.calls] == [False, True, False]
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
    assert [call.correction for call in provider.calls] == [False, True, False]


def test_environment_rejection_is_a_valid_action_not_an_invalid_model_output() -> None:
    trace, _ = run([decision({"tool": "move", "destination": "escape_pod"}), RuntimeError()])

    assert trace.outcome is EpisodeOutcome.PROVIDER_ERROR
    assert trace.rejected_action_count == 1
    assert trace.invalid_output_count == 0
    assert trace.steps[0].event is TraceEvent.ACTION_REJECTED


def test_runner_stops_at_the_configured_environment_step_limit() -> None:
    trace, _ = run(
        [decision({"tool": "look"}), decision({"tool": "look"}), decision({"tool": "look"})],
        step_limit=3,
    )

    assert trace.outcome is EpisodeOutcome.STEP_LIMIT
    assert trace.executed_action_count == 3
    assert trace.invalid_output_count == 0


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
    assert parsed["steps"][0]["decision_reason"] == "OPENAI_API_KEY=[REDACTED]"
