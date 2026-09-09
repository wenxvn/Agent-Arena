"""Versioned world definitions, starting with Spaceship Escape."""

from agent_arena.worlds.spaceship_escape import (
    SpaceshipEscapeEnvironment,
    WorldDefinition,
    load_spaceship_escape_definition,
)

__all__ = [
    "SpaceshipEscapeEnvironment",
    "WorldDefinition",
    "load_spaceship_escape_definition",
]


def create_environment(
    world: str, world_version: str, *, seed: int = 0
) -> SpaceshipEscapeEnvironment:
    """Resolve the supported selector; never silently fall back to a different world."""
    if (world, world_version) != ("spaceship-escape", "spaceship-escape-v2-zh"):
        raise ValueError(
            "不支持该世界或版本；当前仅支持 spaceship-escape / spaceship-escape-v2-zh。"
        )
    environment = SpaceshipEscapeEnvironment(seed=seed)
    if environment.identity[:2] != (world, world_version):
        raise ValueError("世界定义与注册版本不一致。")
    return environment
