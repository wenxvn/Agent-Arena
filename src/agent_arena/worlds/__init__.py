"""Versioned world definitions: Spaceship Escape, Misty Lighthouse and Abyssal Station."""

from agent_arena.worlds.abyss import (
    AbyssEasyEnvironment,
    AbyssEnvironment,
    AbyssHardEnvironment,
    AbyssV2Environment,
    AbyssV3Environment,
    AbyssV4Environment,
    load_abyss_definition,
    load_abyss_easy_definition,
    load_abyss_hard_definition,
    load_abyss_v2_definition,
    load_abyss_v3_definition,
    load_abyss_v4_definition,
)
from agent_arena.worlds.castle import (
    CastleEasyEnvironment,
    CastleEnvironment,
    CastleHardEnvironment,
    load_castle_definition,
    load_castle_easy_definition,
    load_castle_hard_definition,
)
from agent_arena.worlds.flex import (
    CastleV2Environment,
    CastleV2SeededEnvironment,
    LunarV2Environment,
    LunarV2SeededEnvironment,
    PyramidV2Environment,
    PyramidV2SeededEnvironment,
    load_castle_v2_definition,
    load_castle_v2_seeded_definition,
    load_lunar_v2_definition,
    load_lunar_v2_seeded_definition,
    load_pyramid_v2_definition,
    load_pyramid_v2_seeded_definition,
)
from agent_arena.worlds.jungle import (
    JungleEasyEnvironment,
    JungleEnvironment,
    JungleHardEnvironment,
    load_jungle_definition,
    load_jungle_easy_definition,
    load_jungle_hard_definition,
)
from agent_arena.worlds.lighthouse import (
    LighthouseEnvironment,
    LighthouseV2Environment,
    LighthouseV3Environment,
    LighthouseV4Environment,
    LighthouseV5Environment,
    LighthouseV6Environment,
    load_lighthouse_definition,
    load_lighthouse_v2_definition,
    load_lighthouse_v3_definition,
    load_lighthouse_v4_definition,
    load_lighthouse_v5_definition,
    load_lighthouse_v6_definition,
)
from agent_arena.worlds.lunar import (
    LunarEasyEnvironment,
    LunarEnvironment,
    LunarHardEnvironment,
    load_lunar_definition,
    load_lunar_easy_definition,
    load_lunar_hard_definition,
)
from agent_arena.worlds.polar import (
    PolarEasyEnvironment,
    PolarEnvironment,
    PolarHardEnvironment,
    load_polar_definition,
    load_polar_easy_definition,
    load_polar_hard_definition,
)
from agent_arena.worlds.pyramid import (
    PyramidEasyEnvironment,
    PyramidEnvironment,
    PyramidHardEnvironment,
    load_pyramid_definition,
    load_pyramid_easy_definition,
    load_pyramid_hard_definition,
)
from agent_arena.worlds.spaceship_escape import (
    SpaceshipEscapeEnvironment,
    SpaceshipV2Definition,
    SpaceshipV2Environment,
    SpaceshipV3Definition,
    SpaceshipV3Environment,
    SpaceshipV4Definition,
    SpaceshipV4Environment,
    SpaceshipV5Definition,
    SpaceshipV5Environment,
    SpaceshipV6Definition,
    SpaceshipV6Environment,
    WorldDefinition,
    load_spaceship_escape_definition,
    load_spaceship_v2_definition,
    load_spaceship_v3_definition,
    load_spaceship_v4_definition,
    load_spaceship_v5_definition,
    load_spaceship_v6_definition,
)
from agent_arena.worlds.subway import (
    SubwayEasyEnvironment,
    SubwayEnvironment,
    SubwayHardEnvironment,
    load_subway_definition,
    load_subway_easy_definition,
    load_subway_hard_definition,
)
from agent_arena.worlds.variants import (
    SeededShipEnvironment,
    build_seeded_definition,
    load_seeded_base_definition,
)
from agent_arena.worlds.volcano import (
    VolcanoEasyEnvironment,
    VolcanoEnvironment,
    VolcanoHardEnvironment,
    load_volcano_definition,
    load_volcano_easy_definition,
    load_volcano_hard_definition,
)

__all__ = [
    "AbyssEasyEnvironment",
    "AbyssEnvironment",
    "AbyssHardEnvironment",
    "AbyssV2Environment",
    "AbyssV3Environment",
    "AbyssV4Environment",
    "CastleEasyEnvironment",
    "CastleEnvironment",
    "CastleHardEnvironment",
    "CastleV2Environment",
    "CastleV2SeededEnvironment",
    "JungleEasyEnvironment",
    "JungleEnvironment",
    "JungleHardEnvironment",
    "LighthouseEnvironment",
    "LighthouseV2Environment",
    "LighthouseV3Environment",
    "LighthouseV4Environment",
    "LighthouseV5Environment",
    "LighthouseV6Environment",
    "LunarEasyEnvironment",
    "LunarEnvironment",
    "LunarHardEnvironment",
    "LunarV2Environment",
    "LunarV2SeededEnvironment",
    "PolarEasyEnvironment",
    "PolarEnvironment",
    "PolarHardEnvironment",
    "PyramidEasyEnvironment",
    "PyramidEnvironment",
    "PyramidHardEnvironment",
    "PyramidV2Environment",
    "PyramidV2SeededEnvironment",
    "SeededShipEnvironment",
    "SpaceshipEscapeEnvironment",
    "SpaceshipV2Definition",
    "SpaceshipV2Environment",
    "SpaceshipV3Definition",
    "SpaceshipV3Environment",
    "SpaceshipV4Definition",
    "SpaceshipV4Environment",
    "SpaceshipV5Definition",
    "SpaceshipV5Environment",
    "SpaceshipV6Definition",
    "SpaceshipV6Environment",
    "SubwayEasyEnvironment",
    "SubwayEnvironment",
    "SubwayHardEnvironment",
    "VolcanoEasyEnvironment",
    "VolcanoEnvironment",
    "VolcanoHardEnvironment",
    "WorldDefinition",
    "build_seeded_definition",
    "load_abyss_definition",
    "load_abyss_easy_definition",
    "load_abyss_hard_definition",
    "load_abyss_v2_definition",
    "load_abyss_v3_definition",
    "load_abyss_v4_definition",
    "load_castle_definition",
    "load_castle_easy_definition",
    "load_castle_hard_definition",
    "load_castle_v2_definition",
    "load_castle_v2_seeded_definition",
    "load_jungle_definition",
    "load_jungle_easy_definition",
    "load_jungle_hard_definition",
    "load_lighthouse_definition",
    "load_lighthouse_v2_definition",
    "load_lighthouse_v3_definition",
    "load_lighthouse_v4_definition",
    "load_lighthouse_v5_definition",
    "load_lighthouse_v6_definition",
    "load_lunar_definition",
    "load_lunar_easy_definition",
    "load_lunar_hard_definition",
    "load_lunar_v2_definition",
    "load_lunar_v2_seeded_definition",
    "load_polar_definition",
    "load_polar_easy_definition",
    "load_polar_hard_definition",
    "load_pyramid_definition",
    "load_pyramid_easy_definition",
    "load_pyramid_hard_definition",
    "load_pyramid_v2_definition",
    "load_pyramid_v2_seeded_definition",
    "load_seeded_base_definition",
    "load_spaceship_escape_definition",
    "load_spaceship_v2_definition",
    "load_spaceship_v3_definition",
    "load_spaceship_v4_definition",
    "load_spaceship_v5_definition",
    "load_spaceship_v6_definition",
    "load_subway_definition",
    "load_subway_easy_definition",
    "load_subway_hard_definition",
    "load_volcano_definition",
    "load_volcano_easy_definition",
    "load_volcano_hard_definition",
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
    elif (world, world_version) == ("polar-escape", "polar-escape-easy-zh"):
        environment = PolarEasyEnvironment(seed=seed)
    elif (world, world_version) == ("polar-escape", "polar-escape-v1-zh"):
        environment = PolarEnvironment(seed=seed)
    elif (world, world_version) == ("polar-escape", "polar-escape-hard-zh"):
        environment = PolarHardEnvironment(seed=seed)
    elif (world, world_version) == ("pyramid-escape", "pyramid-escape-easy-zh"):
        environment = PyramidEasyEnvironment(seed=seed)
    elif (world, world_version) == ("pyramid-escape", "pyramid-escape-v1-zh"):
        environment = PyramidEnvironment(seed=seed)
    elif (world, world_version) == ("pyramid-escape", "pyramid-escape-hard-zh"):
        environment = PyramidHardEnvironment(seed=seed)
    elif (world, world_version) == ("subway-escape", "subway-escape-easy-zh"):
        environment = SubwayEasyEnvironment(seed=seed)
    elif (world, world_version) == ("subway-escape", "subway-escape-v1-zh"):
        environment = SubwayEnvironment(seed=seed)
    elif (world, world_version) == ("subway-escape", "subway-escape-hard-zh"):
        environment = SubwayHardEnvironment(seed=seed)
    elif (world, world_version) == ("volcano-escape", "volcano-escape-easy-zh"):
        environment = VolcanoEasyEnvironment(seed=seed)
    elif (world, world_version) == ("volcano-escape", "volcano-escape-v1-zh"):
        environment = VolcanoEnvironment(seed=seed)
    elif (world, world_version) == ("volcano-escape", "volcano-escape-hard-zh"):
        environment = VolcanoHardEnvironment(seed=seed)
    elif (world, world_version) == ("jungle-escape", "jungle-escape-easy-zh"):
        environment = JungleEasyEnvironment(seed=seed)
    elif (world, world_version) == ("jungle-escape", "jungle-escape-v1-zh"):
        environment = JungleEnvironment(seed=seed)
    elif (world, world_version) == ("jungle-escape", "jungle-escape-hard-zh"):
        environment = JungleHardEnvironment(seed=seed)
    elif (world, world_version) == ("lunar-escape", "lunar-escape-easy-zh"):
        environment = LunarEasyEnvironment(seed=seed)
    elif (world, world_version) == ("lunar-escape", "lunar-escape-v1-zh"):
        environment = LunarEnvironment(seed=seed)
    elif (world, world_version) == ("lunar-escape", "lunar-escape-hard-zh"):
        environment = LunarHardEnvironment(seed=seed)
    elif (world, world_version) == ("castle-escape", "castle-escape-easy-zh"):
        environment = CastleEasyEnvironment(seed=seed)
    elif (world, world_version) == ("castle-escape", "castle-escape-v1-zh"):
        environment = CastleEnvironment(seed=seed)
    elif (world, world_version) == ("castle-escape", "castle-escape-hard-zh"):
        environment = CastleHardEnvironment(seed=seed)
    elif (world, world_version) == ("lunar-escape", "lunar-escape-v2-zh"):
        environment = LunarV2Environment(seed=seed)
    elif (world, world_version) == ("lunar-escape", "lunar-escape-v2-seeded-zh"):
        environment = LunarV2SeededEnvironment(seed=seed)
    elif (world, world_version) == ("castle-escape", "castle-escape-v2-zh"):
        environment = CastleV2Environment(seed=seed)
    elif (world, world_version) == ("castle-escape", "castle-escape-v2-seeded-zh"):
        environment = CastleV2SeededEnvironment(seed=seed)
    elif (world, world_version) == ("pyramid-escape", "pyramid-escape-v2-zh"):
        environment = PyramidV2Environment(seed=seed)
    elif (world, world_version) == ("pyramid-escape", "pyramid-escape-v2-seeded-zh"):
        environment = PyramidV2SeededEnvironment(seed=seed)
    elif (world, world_version) == ("spaceship-escape", "spaceship-escape-v5-zh-seeded"):
        environment = SeededShipEnvironment(seed=seed)
    elif (world, world_version) == ("spaceship-escape", "spaceship-escape-easy-zh"):
        environment = SpaceshipV4Environment(seed=seed)
    elif (world, world_version) == ("spaceship-escape", "spaceship-escape-v1-zh"):
        environment = SpaceshipV5Environment(seed=seed)
    elif (world, world_version) == ("spaceship-escape", "spaceship-escape-hard-zh"):
        environment = SpaceshipV6Environment(seed=seed)
    elif (world, world_version) == ("lighthouse-escape", "lighthouse-escape-v4-zh"):
        environment = LighthouseV4Environment(seed=seed)
    elif (world, world_version) == ("lighthouse-escape", "lighthouse-escape-v5-zh"):
        environment = LighthouseV5Environment(seed=seed)
    elif (world, world_version) == ("lighthouse-escape", "lighthouse-escape-v6-zh"):
        environment = LighthouseV6Environment(seed=seed)
    elif (world, world_version) == ("abyss-escape", "abyss-escape-v2-zh"):
        environment = AbyssV2Environment(seed=seed)
    elif (world, world_version) == ("abyss-escape", "abyss-escape-v3-zh"):
        environment = AbyssV3Environment(seed=seed)
    elif (world, world_version) == ("abyss-escape", "abyss-escape-v4-zh"):
        environment = AbyssV4Environment(seed=seed)
    else:
        raise ValueError(
            "不支持该世界或版本；当前支持 spaceship-escape / spaceship-escape-v2-zh"
            "、spaceship-escape / spaceship-escape-v3-zh"
            "、spaceship-escape / spaceship-escape-v4-zh"
            "、spaceship-escape / spaceship-escape-v5-zh-seeded"
            "、spaceship-escape / spaceship-escape-easy-zh"
            "、spaceship-escape / spaceship-escape-v1-zh"
            "、spaceship-escape / spaceship-escape-hard-zh"
            "、lighthouse-escape / lighthouse-escape-v1-zh"
            "、lighthouse-escape / lighthouse-escape-v2-zh"
            "、lighthouse-escape / lighthouse-escape-v3-zh"
            "、lighthouse-escape / lighthouse-escape-v4-zh"
            "、lighthouse-escape / lighthouse-escape-v5-zh"
            "、lighthouse-escape / lighthouse-escape-v6-zh"
            "、abyss-escape / abyss-escape-easy-zh"
            "、abyss-escape / abyss-escape-v1-zh"
            "、abyss-escape / abyss-escape-v2-zh"
            "、abyss-escape / abyss-escape-v3-zh"
            "、abyss-escape / abyss-escape-v4-zh"
            "、abyss-escape / abyss-escape-hard-zh"
            "、polar-escape / polar-escape-easy-zh"
            "、polar-escape / polar-escape-v1-zh"
            "、polar-escape / polar-escape-hard-zh"
            "、pyramid-escape / pyramid-escape-easy-zh"
            "、pyramid-escape / pyramid-escape-v1-zh"
            "、pyramid-escape / pyramid-escape-hard-zh"
            "、subway-escape / subway-escape-easy-zh"
            "、subway-escape / subway-escape-v1-zh"
            "、subway-escape / subway-escape-hard-zh"
            "、volcano-escape / volcano-escape-easy-zh"
            "、volcano-escape / volcano-escape-v1-zh"
            "、volcano-escape / volcano-escape-hard-zh"
            "、jungle-escape / jungle-escape-easy-zh"
            "、jungle-escape / jungle-escape-v1-zh"
            "、jungle-escape / jungle-escape-hard-zh"
            "、lunar-escape / lunar-escape-easy-zh"
            "、lunar-escape / lunar-escape-v1-zh"
            "、lunar-escape / lunar-escape-hard-zh"
            "、castle-escape / castle-escape-easy-zh"
            "、castle-escape / castle-escape-v1-zh"
            "、castle-escape / castle-escape-hard-zh"
            "、castle-escape / castle-escape-v2-zh"
            "、castle-escape / castle-escape-v2-seeded-zh"
            "、lunar-escape / lunar-escape-v2-zh"
            "、lunar-escape / lunar-escape-v2-seeded-zh"
            "、pyramid-escape / pyramid-escape-v2-zh"
            "、pyramid-escape / pyramid-escape-v2-seeded-zh"
            " 与 abyss-escape / abyss-escape-hard-zh。"
        )
    if environment.identity[:2] != (world, world_version):
        raise ValueError("世界定义与注册版本不一致。")
    return environment
