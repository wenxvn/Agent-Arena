from __future__ import annotations

from test_episode_runner import decision, settings

from agent_arena.agents import ReactAgent
from agent_arena.evaluation import (
    EpisodeRunner,
    EpisodeTrace,
    read_episode_trace,
    write_episode_trace,
)
from agent_arena.evaluation.benchmark import row_from_trace
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def test_new_trace_records_schema_version_and_step_progress(tmp_path) -> None:
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(FakeDecisionProvider([decision({"tool": "look"})])),
        settings(step_limit=1),
    ).run()

    path = write_episode_trace(trace, tmp_path)
    loaded = read_episode_trace(path)

    assert loaded.trace_schema_version == 2
    assert loaded.steps[0].progress is not None
    assert loaded.steps[0].progress.progress is False


def test_legacy_trace_without_progress_fields_remains_readable() -> None:
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(FakeDecisionProvider([decision({"tool": "look"})])),
        settings(step_limit=1),
    ).run()
    payload = trace.model_dump(mode="json")
    payload.pop("trace_schema_version")
    payload["provenance"]["trace_contract_version"] = "legacy"
    for step in payload["steps"]:
        step.pop("progress", None)

    legacy = EpisodeTrace.model_validate(payload)
    row = row_from_trace(legacy, "legacy", 0)

    assert legacy.trace_schema_version == 2
    assert row.no_progress_action_count == 1
