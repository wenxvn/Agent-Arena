from agent_arena.arena import ToolReason, ToolResult, ToolStatus
from agent_arena.evaluation.runner import PublicPhaseTracker
from agent_arena.worlds.lighthouse import LighthouseEnvironment
from agent_arena.worlds.spaceship_escape import (
    SPACESHIP_MILESTONES,
    SpaceshipEscapeEnvironment,
)


def _result(reason: ToolReason) -> ToolResult:
    return ToolResult(status=ToolStatus.SUCCESS, reason=reason, summary="测试结果")


def _observation(environment, room: str, inventory: tuple[str, ...] = ()) -> object:
    state = environment._state
    state.current_room = room
    state.inventory = set(inventory)
    return environment.observe()


def _track(milestones, reasons: tuple[ToolReason, ...]) -> PublicPhaseTracker:
    tracker = PublicPhaseTracker(milestones=milestones)
    tracker.initialize(SpaceshipEscapeEnvironment(seed=0).observe())
    for reason in reasons:
        tracker.observe(_result(reason))
    return tracker


def test_spaceship_phase_text_matches_legacy_strings() -> None:
    full_inventory = ("screwdriver", "replacement_fuse")

    tracker = _track(SPACESHIP_MILESTONES, ())
    assert (
        tracker.render(_observation(SpaceshipEscapeEnvironment(seed=0), "control_room"))
        == "当前公开阶段：收集修理工具。已完成：无。未完成：获得 replacement_fuse、screwdriver。"
    )

    tracker = _track(SPACESHIP_MILESTONES, ())
    assert (
        tracker.render(
            _observation(
                SpaceshipEscapeEnvironment(seed=0), "corridor", ("screwdriver",)
            )
        )
        == "当前公开阶段：收集修理工具。已完成：无。未完成：获得 replacement_fuse。"
    )

    tracker = _track(SPACESHIP_MILESTONES, (ToolReason.PICKED_UP,))
    assert (
        tracker.render(
            _observation(
                SpaceshipEscapeEnvironment(seed=0), "corridor", full_inventory
            )
        )
        == "当前公开阶段：恢复主电源。已完成：修理工具。未完成：打开反应堆面板。"
    )

    tracker = _track(
        SPACESHIP_MILESTONES, (ToolReason.PICKED_UP, ToolReason.PANEL_OPENED)
    )
    assert (
        tracker.render(
            _observation(
                SpaceshipEscapeEnvironment(seed=0), "reactor_room", full_inventory
            )
        )
        == "当前公开阶段：恢复主电源。已完成：修理工具和反应堆面板。未完成：恢复主电源。"
    )

    tracker = _track(
        SPACESHIP_MILESTONES,
        (ToolReason.PICKED_UP, ToolReason.PANEL_OPENED, ToolReason.POWER_RESTORED),
    )
    assert (
        tracker.render(
            _observation(
                SpaceshipEscapeEnvironment(seed=0), "control_room", full_inventory
            )
        )
        == "当前公开阶段：读取逃生授权码。已完成：修理工具和主电源。未完成：读取授权码。"
    )

    tracker = _track(
        SPACESHIP_MILESTONES,
        (
            ToolReason.PICKED_UP,
            ToolReason.PANEL_OPENED,
            ToolReason.POWER_RESTORED,
            ToolReason.CODE_READ,
        ),
    )
    assert (
        tracker.render(
            _observation(
                SpaceshipEscapeEnvironment(seed=0), "corridor", full_inventory
            )
        )
        == "当前公开阶段：启动逃生舱。已完成：修理工具、主电源和授权码。未完成：启动逃生舱。"
    )


def test_lighthouse_milestones_render_without_spaceship_terms() -> None:
    environment = LighthouseEnvironment(seed=0)
    assert [milestone.stage for milestone in environment.public_milestones] == [
        "收集修理工具",
        "恢复电力",
        "恢复电力",
        "读取潮汐码",
        "乘坐小艇离开",
    ]
    tracker = PublicPhaseTracker(milestones=environment.public_milestones)
    tracker.initialize(environment.observe())
    text = tracker.render(_observation(environment, "cliff_base")) or ""
    assert "screwdriver" not in text
    assert "反应堆" not in text
    assert "获得 spare_cell、wrench" in text
    tracker.observe(_result(ToolReason.PANEL_OPENED))
    tracker.observe(_result(ToolReason.POWER_RESTORED))
    assert (
        tracker.render(_observation(environment, "engine_cave", ("wrench", "spare_cell")))
        == "当前公开阶段：读取潮汐码。已完成：修理工具和电力。未完成：读取潮汐码。"
    )


def test_tracker_without_milestones_renders_nothing() -> None:
    tracker = PublicPhaseTracker(milestones=())
    tracker.initialize(SpaceshipEscapeEnvironment(seed=0).observe())
    assert tracker.render(SpaceshipEscapeEnvironment(seed=0).observe()) is None
