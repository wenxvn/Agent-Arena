from __future__ import annotations

from agent_arena.arena import ToolReason, ToolResult, ToolStatus, action_adapter
from agent_arena.planning import PlanMonitor, PlanState, SuccessCriterion, public_progress_state
from agent_arena.worlds import SpaceshipEscapeEnvironment


def plan(criteria: str) -> PlanState:
    return PlanState(
        overall_goal="完成当前环境任务",
        current_subgoal="完成一个公开中间目标",
        success_criteria=(criteria,),
    )


def test_monitor_marks_subgoal_complete_from_public_inventory_evidence() -> None:
    environment = SpaceshipEscapeEnvironment()
    before = environment.reset(0)
    action = action_adapter.validate_python({"tool": "move", "destination": "corridor"})
    result, after = environment.step(action)
    after = after.model_copy(update={"inventory": ("screwdriver", "replacement_fuse")})

    signal = PlanMonitor().evaluate(
        plan("inventory contains screwdriver replacement_fuse"),
        before,
        action,
        result,
        after,
    )

    assert signal.status == "subgoal_completed"


def test_monitor_replans_after_three_public_no_progress_transitions() -> None:
    environment = SpaceshipEscapeEnvironment()
    observation = environment.reset(0)
    action = action_adapter.validate_python({"tool": "look"})
    monitor = PlanMonitor()
    monitor.reset()
    current = observation

    signals = []
    for _ in range(3):
        result, after = environment.step(action)
        signals.append(
            monitor.evaluate(plan("room is reactor_room"), current, action, result, after)
        )
        current = after

    assert [signal.status for signal in signals] == ["continue", "continue", "no_progress"]


def test_monitor_replans_after_the_same_public_failure_repeats() -> None:
    environment = SpaceshipEscapeEnvironment()
    before = environment.reset(0)
    action = action_adapter.validate_python({"tool": "move", "destination": "escape_pod"})
    monitor = PlanMonitor()

    first_result, first_after = environment.step(action)
    first_signal = monitor.evaluate(
        plan("room is reactor_room"), before, action, first_result, first_after
    )
    second_result, second_after = environment.step(action)
    second_signal = monitor.evaluate(
        plan("room is reactor_room"), first_after, action, second_result, second_after
    )

    assert first_signal.status == "continue"
    assert second_signal.status == "repeated_failure"


def test_public_progress_state_has_no_hidden_world_fields() -> None:
    observation = SpaceshipEscapeEnvironment().reset(0)
    state = public_progress_state(observation)

    assert "WorldState" not in state.model_dump_json()
    assert set(state.model_dump()) == {
        "current_room",
        "visible_objects",
        "available_exits",
        "inventory",
        "last_result_status",
        "last_result_reason",
    }


def test_monitor_counts_repeated_known_fact_as_no_progress() -> None:
    environment = SpaceshipEscapeEnvironment()
    observation = environment.reset(0)
    action = action_adapter.validate_python(
        {"tool": "use", "item": "screwdriver", "target": "control_terminal"}
    )
    result = ToolResult(
        status=ToolStatus.SUCCESS,
        reason=ToolReason.POWER_RESTORED,
        summary="公开结果。",
    )
    monitor = PlanMonitor()
    state = PlanState(
        overall_goal="完成环境任务",
        current_subgoal="确认公开状态",
        success_criteria=(
            SuccessCriterion(
                criterion_type="room_reached",
                target="reactor_room",
                description="到达反应堆室",
            ),
        ),
    )

    signals = [
        monitor.evaluate(state, observation, action, result, observation)
        for _ in range(4)
    ]

    assert signals[0].status == "continue"
    assert monitor.no_progress_count == 3
    assert signals[-1].status == "no_progress"
