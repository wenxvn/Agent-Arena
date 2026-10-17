"""Thirty-map V8 catalog and content hashes.

The six maps that already had an isolated V4 runtime keep that runtime through a
thin adapter; the other twenty-four are implemented in ``scenario_v8.maps``.
Nothing here mutates the V3/V4/V5/V6/V7 contracts.
"""

from __future__ import annotations

import dataclasses
import importlib
from hashlib import sha256
from pathlib import Path
from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment

MAP_IDS: tuple[str, ...] = tuple(f"MAP-{index:02d}" for index in range(1, 31))
WORLD_OF: dict[str, str] = {
    **{f"MAP-{index:02d}": "spaceship" for index in range(1, 4)},
    **{f"MAP-{index:02d}": "lighthouse" for index in range(4, 7)},
    **{f"MAP-{index:02d}": "abyss" for index in range(7, 10)},
    **{f"MAP-{index:02d}": "polar" for index in range(10, 13)},
    **{f"MAP-{index:02d}": "pyramid" for index in range(13, 16)},
    **{f"MAP-{index:02d}": "subway" for index in range(16, 19)},
    **{f"MAP-{index:02d}": "volcano" for index in range(19, 22)},
    **{f"MAP-{index:02d}": "jungle" for index in range(22, 25)},
    **{f"MAP-{index:02d}": "lunar" for index in range(25, 28)},
    **{f"MAP-{index:02d}": "castle" for index in range(28, 31)},
}
_LEVELS = ("简单", "中等", "困难")
LEVEL_OF = {map_id: _LEVELS[(int(map_id.split("-")[1]) - 1) % 3] for map_id in MAP_IDS}

#: The single formal V8 condition per map. The six V4 maps keep their
#: capability-bearing condition instead of a stripped ablation.
CONDITIONS: dict[str, str] = {
    "MAP-08": "hypothesis_table",
    "MAP-16": "constraint_table",
    "MAP-18": "alert_on",
    "MAP-22": "history5_graph_memory",
    "MAP-26": "free_diagnosis",
    "MAP-30": "history5_casebook",
}
_V4_RUNTIME_MAPS = frozenset(CONDITIONS)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_MAP_SOURCE_ROOT = _REPOSITORY_ROOT / "worlds" / "v4"
_SOURCE_FILES = (
    "map_spec.yaml",
    "evidence_or_rules.yaml",
    "acceptance.md",
    "oracle_trace.jsonl",
    "failure_traces/cases.yaml",
)


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonical(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    return value


def create_environment(
    map_id: str,
    *,
    seed: int = 0,
    step_limit: int = 160,
    condition_id: str | None = None,
) -> MapEnvironment:
    """Build one registered V8 map. Unknown ids are refused."""

    if map_id not in MAP_IDS:
        raise ValueError(f"未注册的 V8 地图：{map_id}")
    condition = condition_id or CONDITIONS.get(map_id, "default")
    if map_id in _V4_RUNTIME_MAPS:
        from agent_arena.worlds.scenario_v8.v4_adapter import V4MapAdapter

        environment: MapEnvironment = V4MapAdapter(
            map_id, seed=seed, step_limit=step_limit, condition_id=condition
        )
    else:
        module = importlib.import_module(f"agent_arena.worlds.scenario_v8.maps.map{map_id[-2:]}")
        factory = getattr(module, f"Map{map_id[-2:]}Environment")
        environment = factory(seed=seed, step_limit=step_limit)
        environment.condition_id = condition
    environment.source_hash = source_hash(map_id)
    return environment


def map_metadata(map_id: str) -> dict[str, Any]:
    environment = create_environment(map_id, seed=0)
    return {
        "map_id": map_id,
        "world": WORLD_OF[map_id],
        "level": LEVEL_OF[map_id],
        "title": environment.title,
        "condition_id": environment.condition_id,
    }


def source_hash(map_id: str, *, root: Path | None = None) -> str:
    """Hash the inspected V4 design package for one map."""

    if map_id not in MAP_IDS:
        raise ValueError(f"未注册的 V8 地图：{map_id}")
    base = (root or _MAP_SOURCE_ROOT) / map_id
    digest = sha256()
    for relative in _SOURCE_FILES:
        path = base / relative
        if not path.is_file():
            raise FileNotFoundError(f"V4 设计文件缺失：{relative}")
        content = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def rule_hash(map_id: str) -> str:
    """Hash the executable rule module (or the V4 module for the six maps)."""

    if map_id in _V4_RUNTIME_MAPS:
        path = (
            _REPOSITORY_ROOT
            / "src"
            / "agent_arena"
            / "worlds"
            / "scenario_v4"
            / f"map{map_id[-2:]}.py"
        )
    else:
        path = (
            _REPOSITORY_ROOT
            / "src"
            / "agent_arena"
            / "worlds"
            / "scenario_v8"
            / "maps"
            / f"map{map_id[-2:]}.py"
        )
    return sha256(path.read_bytes()).hexdigest()


def scenario_hash(map_id: str) -> str:
    """Stable identity of the map instance used by the formal runs."""

    payload = "|".join(
        [
            map_id,
            WORLD_OF[map_id],
            LEVEL_OF[map_id],
            CONDITIONS.get(map_id, "default"),
        ]
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def oracle_path(map_id: str) -> Path:
    return _MAP_SOURCE_ROOT / map_id / "oracle_trace.jsonl"


__all__ = [
    "CONDITIONS",
    "LEVEL_OF",
    "MAP_IDS",
    "WORLD_OF",
    "create_environment",
    "map_metadata",
    "oracle_path",
    "rule_hash",
    "scenario_hash",
    "source_hash",
]
