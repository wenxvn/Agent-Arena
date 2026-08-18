from agent_arena.arena.models import LookAction, Observation, ToolReason, ToolResult, ToolStatus
from agent_arena.evaluation import PublicLoopDetector


def observation(room: str = "control_room") -> Observation:
    return Observation(
        current_room=room,
        description="公开观察",
        visible_objects=("control_terminal",),
        available_exits=("corridor",),
        inventory=(),
        last_action_result=None,
    )


def rejected() -> ToolResult:
    return ToolResult(
        status=ToolStatus.REJECTED,
        reason=ToolReason.NO_POWER,
        summary="控制终端没有主电源。",
    )


def test_detector_warns_after_repeating_an_action_in_the_same_public_state() -> None:
    detector = PublicLoopDetector()
    action = LookAction(tool="look")
    current = observation()
    detector.initialize(current)
    assert detector.observe(current, action, rejected(), current) is None
    warning = detector.observe(current, action, rejected(), current)
    assert warning is not None
    assert "已完成的动作" in warning


def test_detector_lists_unvisited_public_exits_during_recovery() -> None:
    detector = PublicLoopDetector()
    corridor = Observation(
        current_room="corridor",
        description="走廊",
        visible_objects=(),
        available_exits=("control_room", "storage_room"),
        inventory=(),
        last_action_result=None,
    )
    detector.initialize(corridor)
    action = LookAction(tool="look")
    result = ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.LOOKED, summary="查看。")
    assert detector.observe(corridor, action, result, corridor) is None
    warning = detector.observe(corridor, action, result, corridor)
    assert warning is not None
    assert "storage_room" in warning
