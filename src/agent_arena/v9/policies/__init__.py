"""V9 基线注册表：按世界导入公开启发式与消融策略。"""

from __future__ import annotations

import importlib
from typing import Any

from agent_arena.v9.policies.base import PublicPolicy

_WORLD_MODULES = (
    "spaceship",
    "lighthouse",
    "abyss",
    "polar",
    "pyramid",
    "subway",
    "volcano",
    "jungle",
    "lunar",
    "castle",
)


def _modules() -> list[Any]:
    loaded: list[Any] = []
    for name in _WORLD_MODULES:
        module_name = f"agent_arena.v9.policies.world_{name}"
        try:
            loaded.append(importlib.import_module(module_name))
        except ModuleNotFoundError:
            continue
    return loaded


def heuristics() -> dict[str, type[PublicPolicy]]:
    registry: dict[str, type[PublicPolicy]] = {}
    for module in _modules():
        for map_id, factory in getattr(module, "HEURISTICS", {}).items():
            registry[map_id] = factory
    return registry


def ablations() -> dict[str, dict[str, type[PublicPolicy]]]:
    registry: dict[str, dict[str, type[PublicPolicy]]] = {}
    for module in _modules():
        registry.update(getattr(module, "ABLATIONS", {}))
    return registry


__all__ = ["ablations", "heuristics"]
