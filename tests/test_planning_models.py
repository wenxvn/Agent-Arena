from __future__ import annotations

from agent_arena.planning import PlannerDecision, PlanSignal, PlanState


def test_planner_decision_accepts_json_array_values_but_forbids_actions() -> None:
    decision = PlannerDecision.model_validate(
        {
            "decision_reason": "根据公开事实保持当前目标。",
            "current_subgoal": "获得新的公开信息",
            "success_criteria": ["ToolResult status is success"],
            "known_constraints": ["只能操作当前可见对象"],
            "relevant_resources": [],
            "unresolved_questions": ["下一步公开证据是什么？"],
        }
    )

    assert decision.success_criteria == ("ToolResult status is success",)
    assert "action" not in decision.model_dump()


def test_plan_state_has_episode_local_id_and_frozen_public_fields() -> None:
    first = PlanState(
        overall_goal="完成当前环境任务",
        current_subgoal="获得公开信息",
        success_criteria=("ToolResult status is success",),
    )
    second = PlanState(
        overall_goal=first.overall_goal,
        current_subgoal="推进公开目标",
        success_criteria=first.success_criteria,
    )

    assert first.plan_id != second.plan_id
    assert first.plan_version == "planning_v1"
    assert first.completed_subgoals == ()


def test_plan_signal_uses_only_allowlisted_statuses() -> None:
    signal = PlanSignal(status="no_progress", reason="no_progress")

    assert signal.status == "no_progress"
