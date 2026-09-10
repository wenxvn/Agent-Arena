from __future__ import annotations

from pathlib import Path

from test_episode_runner import decision, settings
from typer.testing import CliRunner

from agent_arena.agents import ReactAgent
from agent_arena.cli import app
from agent_arena.evaluation import (
    EpisodeRunner,
    FailureCategory,
    FailureType,
    analyze_trace,
    write_episode_trace,
)
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def run_trace(responses: list[object], *, step_limit: int = 6):
    return EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(FakeDecisionProvider(responses)),
        settings(step_limit=step_limit),
    ).run()


def test_failure_detector_marks_repeated_inspection_and_navigation_cycle() -> None:
    trace = run_trace(
        [
            decision({"tool": "move", "destination": "corridor"}),
            decision({"tool": "move", "destination": "storage_room"}),
            decision({"tool": "inspect", "target": "storage_crate"}),
            decision({"tool": "inspect", "target": "storage_crate"}),
            decision({"tool": "inspect", "target": "storage_crate"}),
            decision({"tool": "move", "destination": "corridor"}),
            decision({"tool": "move", "destination": "storage_room"}),
            decision({"tool": "move", "destination": "corridor"}),
            decision({"tool": "move", "destination": "storage_room"}),
        ],
        step_limit=9,
    )

    analysis = analyze_trace(trace)

    assert analysis.automatic_failure_signals.repeated_inspection == 1
    assert analysis.automatic_failure_signals.repeated_navigation >= 1
    failure_types = {annotation.failure_type for annotation in analysis.annotations}
    assert FailureType.REPEATED_INSPECTION in failure_types
    assert FailureType.REPEATED_NAVIGATION in failure_types
    assert all(
        annotation.category is not FailureCategory.PLANNING
        for annotation in analysis.annotations
    )


def test_failure_detector_marks_repeated_rejection_and_invalid_output() -> None:
    repeated = run_trace(
        [
            decision({"tool": "read_terminal", "target": "control_terminal"}),
            decision({"tool": "read_terminal", "target": "control_terminal"}),
        ],
        step_limit=2,
    )
    repeated_analysis = analyze_trace(repeated)
    assert repeated_analysis.automatic_failure_signals.rejected_action == 2
    assert repeated_analysis.automatic_failure_signals.repeated_failure == 1
    assert repeated_analysis.repeated_known_fact_action_count == 1

    invalid = run_trace([{}, {}, {}], step_limit=3)
    invalid_analysis = analyze_trace(invalid)
    assert invalid_analysis.automatic_failure_signals.invalid_output >= 1
    assert any(
        annotation.failure_type is FailureType.INVALID_OUTPUT
        for annotation in invalid_analysis.annotations
    )


def test_analyze_trace_cli_prints_safe_failure_summary(tmp_path: Path) -> None:
    trace = run_trace([decision({"tool": "look"})], step_limit=1)
    trace_path = write_episode_trace(trace, tmp_path)

    result = CliRunner().invoke(app, ["analyze-trace", str(trace_path)])

    assert result.exit_code == 0
    assert "Automatic failure signals:" in result.output
    assert "State progress events:" in result.output
    assert "Planner calls:" in result.output
