"""T6：seed 当前是 replicate id（非地图随机源）的契约测试。不调用模型。"""
from __future__ import annotations

import pytest

from agent_arena.worlds import create_environment


def test_same_seed_reproducible() -> None:
    env_a = create_environment("spaceship-escape", "spaceship-escape-v2-zh", seed=0)
    env_b = create_environment("spaceship-escape", "spaceship-escape-v2-zh", seed=0)
    assert env_a.identity == env_b.identity
    assert env_a.observe().current_room == env_b.observe().current_room


def test_different_seeds_share_same_map() -> None:
    env_a = create_environment("spaceship-escape", "spaceship-escape-v2-zh", seed=0)
    env_b = create_environment("spaceship-escape", "spaceship-escape-v2-zh", seed=4)
    # seed 只改变 WorldState 标签，不改变地图定义 hash 与授权码。
    assert env_a.identity[3] == env_b.identity[3]
    assert env_a._state.seed != env_b._state.seed


def test_unknown_world_version_rejected() -> None:
    with pytest.raises(ValueError):
        create_environment("spaceship-escape", "spaceship-escape-v99-zh", seed=0)
