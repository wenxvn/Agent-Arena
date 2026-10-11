"""T3：Phase 先验审计——P 在零探索时即暴露物品名与阶段顺序。

断言 world-declared guidance 的存在（不是纯 observation 派生），
为自主性分级提供契约证据。不调用模型。
"""
from __future__ import annotations

from agent_arena.evaluation.runner import PublicPhaseTracker
from agent_arena.worlds.abyss import ABYSS_MILESTONES
from agent_arena.worlds.lighthouse import LighthouseEnvironment
from agent_arena.worlds.spaceship_escape import (
    SPACESHIP_MILESTONES,
    SpaceshipEscapeEnvironment,
)


def test_phase_text_exposes_key_items_before_discovery() -> None:
    env = SpaceshipEscapeEnvironment(seed=0)
    tracker = PublicPhaseTracker(milestones=SPACESHIP_MILESTONES)
    tracker.initialize(env.observe())
    text = tracker.render(env.observe()) or ""
    # 玩家尚未 inspect 任何容器，但阶段文本已报出精确物品 ID。
    assert "replacement_fuse" in text
    assert "screwdriver" in text


def test_phase_stage_order_is_world_declared() -> None:
    stages = [m.stage for m in SPACESHIP_MILESTONES]
    assert stages == ["收集修理工具", "恢复主电源", "恢复主电源", "读取逃生授权码", "启动逃生舱"]
    light_stages = [m.stage for m in LighthouseEnvironment(seed=0).public_milestones]
    assert light_stages[0] == "收集修理工具"
    assert light_stages[-1] == "乘坐小艇离开"
    abyss_stages = [m.stage for m in ABYSS_MILESTONES]
    assert abyss_stages[-1] == "乘坐逃生舱离开"


def test_tracker_without_milestones_exposes_nothing() -> None:
    tracker = PublicPhaseTracker(milestones=())
    env = SpaceshipEscapeEnvironment(seed=0)
    tracker.initialize(env.observe())
    assert tracker.render(env.observe()) is None
