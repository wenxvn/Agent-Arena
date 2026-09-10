from __future__ import annotations

import json

from test_episode_runner import decision, settings

from agent_arena.agents import ReactAgent
from agent_arena.evaluation import EpisodeRunner
from agent_arena.evaluation.benchmark import row_from_trace, write_benchmark
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def test_benchmark_row_contains_evaluation_v2_progress_and_planning_metrics(tmp_path) -> None:
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        ReactAgent(
            FakeDecisionProvider(
                [
                    decision({"tool": "move", "destination": "corridor"}),
                    decision({"tool": "look"}),
                ]
            )
        ),
        settings(step_limit=2),
    ).run()

    row = row_from_trace(trace, "benchmark", 0)

    assert row.model == "fake-scripted"
    assert row.world == "spaceship-escape"
    assert row.state_progress_count >= 1
    assert row.total_progress_count >= row.state_progress_count
    assert row.planner_call_ratio == 0.0
    assert row.unique_room_count == 2
    assert row.latency == row.latency_ms

    json_path, csv_path = write_benchmark([row], tmp_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert csv_path.exists()
    assert payload["evaluation_schema_version"] == "evaluation_v2"
    assert "mean_state_progress_count" in payload["aggregates"]
    assert "planner_call_ratio" in payload["rows"][0]
