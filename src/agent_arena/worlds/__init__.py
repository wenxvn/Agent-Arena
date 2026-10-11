"""Versioned world definitions: Spaceship Escape, Misty Lighthouse and Abyssal Station."""

from agent_arena.worlds.abyss import (
    AbyssEasyEnvironment,
    AbyssEnvironment,
    AbyssHardEnvironment,
    load_abyss_definition,
    load_abyss_easy_definition,
    load_abyss_hard_definition,
)
from agent_arena.worlds.lighthouse import (
    LighthouseEnvironment,
    LighthouseV2Environment,
    LighthouseV3Environment,
    load_lighthouse_definition,
    load_lighthouse_v2_definition,
    load_lighthouse_v3_definition,
)
from agent_arena.worlds.spaceship_escape import (
    SpaceshipEscapeEnvironment,
    SpaceshipV2Definition,
    SpaceshipV2Environment,
    SpaceshipV3Definition,
    SpaceshipV3Environment,
    WorldDefinition,
    load_spaceship_escape_definition,
    load_spaceship_v2_definition,
    load_spaceship_v3_definition,
)

__all__ = [
    "AbyssEasyEnvironment",
    "AbyssEnvironment",
    "AbyssHardEnvironment",
    "LighthouseEnvironment",
    "LighthouseV2Environment",
    "LighthouseV3Environment",
    "SpaceshipEscapeEnvironment",
    "SpaceshipV2Definition",
    "SpaceshipV2Environment",
    "SpaceshipV3Definition",
    "SpaceshipV3Environment",
    "WorldDefinition",
    "load_abyss_definition",
    "load_abyss_easy_definition",
    "load_abyss_hard_definition",
    "load_lighthouse_definition",
    "load_lighthouse_v2_definition",
    "load_lighthouse_v3_definition",
    "load_spaceship_escape_definition",
    "load_spaceship_v2_definition",
    "load_spaceship_v3_definition",
]

Environment = (
    SpaceshipEscapeEnvironment | LighthouseEnvironment | AbyssEnvironment
)


def create_environment(
    world: str, world_version: str, *, seed: int = 0
) -> Environment:
    """Resolve the supported selector; never silently fall back to a different world."""
    if (world, world_version) == ("spaceship-escape", "spaceship-escape-v2-zh"):
        environment: Environment = SpaceshipEscapeEnvironment(seed=seed)
    elif (world, world_version) == ("lighthouse-escape", "lighthouse-escape-v1-zh"):
        environment = LighthouseEnvironment(seed=seed)
    elif (world, world_version) == ("spaceship-escape", "spaceship-escape-v3-zh"):
        environment = SpaceshipV2Environment(seed=seed)
    elif (world, world_version) == ("lighthouse-escape", "lighthouse-escape-v2-zh"):
        environment = LighthouseV2Environment(seed=seed)
    elif (world, world_version) == ("abyss-escape", "abyss-escape-v1-zh"):
        environment = AbyssEnvironment(seed=seed)
    elif (world, world_version) == ("spaceship-escape", "spaceship-escape-v4-zh"):
        environment = SpaceshipV3Environment(seed=seed)
    elif (world, world_version) == ("lighthouse-escape", "lighthouse-escape-v3-zh"):
        environment = LighthouseV3Environment(seed=seed)
    elif (world, world_version) == ("abyss-escape", "abyss-escape-easy-zh"):
        environment = AbyssEasyEnvironment(seed=seed)
    elif (world, world_version) == ("abyss-escape", "abyss-escape-hard-zh"):
        environment = AbyssHardEnvironment(seed=seed)
    else:
        raise ValueError(
            "不支持该世界或版本；当前支持 spaceship-escape / spaceship-escape-v2-zh"
            "、spaceship-escape / spaceship-escape-v3-zh"
            "、spaceship-escape / spaceship-escape-v4-zh"
            "、lighthouse-escape / lighthouse-escape-v1-zh"
            "、lighthouse-escape / lighthouse-escape-v2-zh"
            "、lighthouse-escape / lighthouse-escape-v3-zh"
            "、abyss-escape / abyss-escape-easy-zh"
            "、abyss-escape / abyss-escape-v1-zh"
            " 与 abyss-escape / abyss-escape-hard-zh。"
        )
    if environment.identity[:2] != (world, world_version):
        raise ValueError("世界定义与注册版本不一致。")
    return environment
