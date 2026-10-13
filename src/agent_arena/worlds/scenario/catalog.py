"""Explicit registry of the thirty V3 scenario selectors."""

from __future__ import annotations

from collections.abc import Callable

from agent_arena.arena.environment import Environment
from agent_arena.worlds.scenario.abyss import AbyssScenario
from agent_arena.worlds.scenario.castle import CastleScenario
from agent_arena.worlds.scenario.jungle import JungleScenario
from agent_arena.worlds.scenario.lighthouse import LighthouseScenario
from agent_arena.worlds.scenario.lunar import LunarScenario
from agent_arena.worlds.scenario.polar import PolarScenario
from agent_arena.worlds.scenario.pyramid import PyramidScenario
from agent_arena.worlds.scenario.spaceship import SpaceshipScenario
from agent_arena.worlds.scenario.subway import SubwayScenario
from agent_arena.worlds.scenario.volcano import VolcanoScenario

ScenarioFactory = Callable[[str, int], Environment]

_FAMILIES: dict[str, tuple[str, type[Environment]]] = {
    "spaceship": ("spaceship-escape", SpaceshipScenario),
    "lighthouse": ("lighthouse-escape", LighthouseScenario),
    "abyss": ("abyss-escape", AbyssScenario),
    "polar": ("polar-escape", PolarScenario),
    "pyramid": ("pyramid-escape", PyramidScenario),
    "subway": ("subway-escape", SubwayScenario),
    "volcano": ("volcano-escape", VolcanoScenario),
    "jungle": ("jungle-escape", JungleScenario),
    "lunar": ("lunar-escape", LunarScenario),
    "castle": ("castle-escape", CastleScenario),
}
_DIFFICULTIES = ("easy", "medium", "hard")


def _factory(environment_type: type[Environment], difficulty: str) -> ScenarioFactory:
    def build(_world: str, seed: int) -> Environment:
        return environment_type(difficulty=difficulty, seed=seed)  # type: ignore[call-arg]

    return build


SCENARIO_REGISTRY: dict[tuple[str, str], ScenarioFactory] = {
    (world_slug, f"{world_slug}-world-v3-{difficulty}-zh"): _factory(environment_type, difficulty)
    for world_slug, environment_type in _FAMILIES.values()
    for difficulty in _DIFFICULTIES
}


def create_scenario_environment(world: str, world_version: str, *, seed: int = 0) -> Environment:
    factory = SCENARIO_REGISTRY.get((world, world_version))
    if factory is None:
        raise ValueError(f"未知的 V3 Scenario selector：{world} / {world_version}")
    environment = factory(world, seed)
    if environment.identity[:2] != (world, world_version):
        raise ValueError("V3 Scenario 定义与注册 selector 不一致。")
    return environment


__all__ = ["SCENARIO_REGISTRY", "create_scenario_environment"]
