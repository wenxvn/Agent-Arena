from __future__ import annotations

import json
from pathlib import Path

from agent_arena.agents import PlanningAgent
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation import (
    EpisodeOutcome,
    EpisodeRunner,
    read_episode_trace,
    write_episode_trace,
)
from agent_arena.evaluation.benchmark import row_from_trace, write_benchmark
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def settings() -> RuntimeSettings:
    return RuntimeSettings.model_validate(
        {
            "provider": "fake",
            "world": "spaceship-escape",
            "world_version": "spaceship-escape-v2-zh",
            "agent": "planning",
            "seed": 0,
            "runs_dir": "runs",
            "results_dir": "results",
            "step_limit": 30,
            "request_timeout_seconds": 30,
            "retry_count": 2,
            "retry_backoff_seconds": [1, 2],
            "enable_thinking": False,
            "model_name": "fake",
        }
    )


def decision(action: dict[str, str]) -> dict[str, object]:
    return {"decision_reason": "围绕当前子目标执行公开动作。", "action": action}


def planning_responses() -> list[object]:
    plans = [
        ("获得公开资源", ["inventory contains screwdriver replacement_fuse"]),
        ("恢复系统", ["ToolResult reason is power_restored"]),
        ("读取授权", ["ToolResult reason is code_read"]),
        ("完成最终目标", ["ToolResult reason is escaped"]),
    ]
    actions = [
        {"tool": "move", "destination": "corridor"},
        {"tool": "move", "destination": "storage_room"},
        {"tool": "inspect", "target": "storage_crate"},
        {"tool": "pickup", "item": "screwdriver"},
        {"tool": "pickup", "item": "replacement_fuse"},
        {"tool": "move", "destination": "corridor"},
        {"tool": "move", "destination": "maintenance_room"},
        {"tool": "read_terminal", "target": "diagnostic_terminal"},
        {"tool": "move", "destination": "reactor_room"},
        {"tool": "use", "item": "screwdriver", "target": "reactor_panel"},
        {"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"},
        {"tool": "move", "destination": "maintenance_room"},
        {"tool": "move", "destination": "corridor"},
        {"tool": "move", "destination": "control_room"},
        {"tool": "read_terminal", "target": "control_terminal"},
        {"tool": "move", "destination": "corridor"},
        {"tool": "move", "destination": "maintenance_room"},
        {"tool": "move", "destination": "reactor_room"},
        {"tool": "move", "destination": "escape_pod"},
        {"tool": "use", "item": "ALPHA-731", "target": "escape_pod"},
    ]
    boundaries = (5, 11, 15, 20)
    responses: list[object] = []
    start = 0
    for (subgoal, criteria), end in zip(plans, boundaries, strict=True):
        responses.append(
            {
                "decision_reason": "根据公开结果切换当前子目标。",
                "current_subgoal": subgoal,
                "success_criteria": criteria,
                "known_constraints": [],
                "relevant_resources": [],
                "unresolved_questions": [],
            }
        )
        responses.extend(decision(action) for action in actions[start:end])
        start = end
    return responses


def test_planning_trace_records_lifecycle_and_benchmark_metrics(tmp_path: Path) -> None:
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        PlanningAgent(FakeDecisionProvider(planning_responses())),
        settings(),
    ).run()

    assert trace.outcome is EpisodeOutcome.SUCCESS
    assert trace.provenance.planning_enabled is True
    assert trace.provenance.planner_prompt_version == "planning_v1"
    assert trace.provenance.planning_policy == "event_triggered"
    assert sum(step.planner_called for step in trace.steps) == 4
    assert sum(step.subgoal_completed for step in trace.steps) == 4
    assert trace.steps[0].current_subgoal == "获得公开资源"
    assert trace.steps[5].replan_reason == "success_criteria_met"
    assert trace.steps[5].plan_id != trace.steps[0].plan_id
    assert all("WorldState" not in step.model_dump_json() for step in trace.steps)

    loaded = read_episode_trace(write_episode_trace(trace, tmp_path))
    row = row_from_trace(loaded, "benchmark", 0)
    assert row.planner_call_count == 4
    assert row.replan_count == 3
    assert row.completed_subgoal_count == 4
    assert row.subgoal_completion_rate == 1.0

    json_path, csv_path = write_benchmark([row], tmp_path / "results")
    manifest = json.loads(json_path.read_text(encoding="utf-8"))
    assert csv_path.exists()
    assert manifest["schema_version"] == "benchmark_v3"
    assert manifest["aggregates"]["mean_planner_call_count"] == 4.0


def test_planning_trace_replans_after_no_progress() -> None:
    responses: list[object] = [
        {
            "decision_reason": "建立一个需要公开证据的子目标。",
            "current_subgoal": "获得未出现的公开证据",
            "success_criteria": ["room is reactor_room"],
            "known_constraints": [],
            "relevant_resources": [],
            "unresolved_questions": [],
        },
        decision({"tool": "look"}),
        decision({"tool": "look"}),
        decision({"tool": "look"}),
        {
            "decision_reason": "连续无进展，重新确认当前公开目标。",
            "current_subgoal": "继续获得公开证据",
            "success_criteria": ["room is reactor_room"],
            "known_constraints": [],
            "relevant_resources": [],
            "unresolved_questions": [],
        },
        decision({"tool": "look"}),
    ]
    episode_settings = settings().model_copy(update={"step_limit": 4})
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        PlanningAgent(FakeDecisionProvider(responses)),
        episode_settings,
    ).run()

    assert trace.outcome is EpisodeOutcome.STEP_LIMIT
    assert trace.steps[2].plan_signal == "no_progress"
    assert trace.steps[3].replan_reason == "no_progress"
    assert sum(step.planner_called for step in trace.steps) == 2
