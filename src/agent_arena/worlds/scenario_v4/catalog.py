"""Allowlisted V4 worlds and exact pre-registered pilot conditions."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from agent_arena.worlds.scenario_v4.base import ScenarioV4Environment
from agent_arena.worlds.scenario_v4.map08 import Map08Environment
from agent_arena.worlds.scenario_v4.map16 import Map16Environment
from agent_arena.worlds.scenario_v4.map18 import Map18Environment
from agent_arena.worlds.scenario_v4.map22 import Map22Environment
from agent_arena.worlds.scenario_v4.map26 import Map26Environment
from agent_arena.worlds.scenario_v4.map30 import Map30Environment

MAP_IDS = ("MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30")
CONDITIONS: dict[str, tuple[str, ...]] = {
    "MAP-08": ("no_hypothesis_table", "hypothesis_table"),
    "MAP-16": ("react", "constraint_table"),
    "MAP-18": ("alert_off", "alert_on"),
    "MAP-22": ("history5", "history5_graph_memory"),
    "MAP-26": ("free_diagnosis", "recovery_full", "recovery_hidden", "recovery_structured"),
    "MAP-30": ("history_full", "history5", "history5_casebook"),
}
_FIXED_SCENE_MAPS = frozenset({"MAP-16", "MAP-18", "MAP-22", "MAP-30"})
_SOURCE_FILES = (
    "map_spec.yaml",
    "evidence_or_rules.yaml",
    "acceptance.md",
    "oracle_trace.jsonl",
    "failure_traces/cases.yaml",
)
_CONDITION_SOURCE_FILES = {
    "MAP-22": ("planning/hand_traces.json",),
    "MAP-26": ("planning/hand_traces.json",),
    "MAP-30": ("planning/hand_traces.json",),
}
_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_MAP_SOURCE_ROOT = _REPOSITORY_ROOT / "worlds" / "v4"


def create_environment(
    map_id: str,
    *,
    seed: int,
    condition_id: str,
    step_limit: int = 100,
) -> ScenarioV4Environment:
    """Create only an allowlisted V4 map with a pre-registered condition."""
    if map_id not in MAP_IDS:
        raise ValueError(
            "The V4 registry only accepts MAP-08, MAP-16, MAP-18, MAP-22, MAP-26, MAP-30."
        )
    if condition_id not in CONDITIONS[map_id]:
        raise ValueError(f"Condition is not registered for {map_id}.")
    if map_id == "MAP-08" and seed not in {0, 4, 8}:
        raise ValueError("MAP-08 pilot seeds are limited to 0, 4, and 8.")
    if map_id == "MAP-26" and seed not in {0, 1, 2}:
        raise ValueError("MAP-26 pilot seeds are limited to 0, 1, and 2.")
    if map_id in _FIXED_SCENE_MAPS and seed not in {0, 1, 2}:
        raise ValueError(f"{map_id} only accepts the three registered fixed-scene repeat labels.")

    if map_id == "MAP-08":
        environment: ScenarioV4Environment = Map08Environment(step_limit=step_limit)
    elif map_id == "MAP-16":
        environment = Map16Environment(step_limit=step_limit)
    elif map_id == "MAP-18":
        environment = Map18Environment(
            alert_enabled=condition_id == "alert_on", step_limit=step_limit
        )
    elif map_id == "MAP-22":
        environment = Map22Environment(
            memory_enabled=condition_id == "history5_graph_memory", step_limit=step_limit
        )
    elif map_id == "MAP-26":
        feedback_mode = {
            "free_diagnosis": "full",
            "recovery_full": "full",
            "recovery_hidden": "hidden",
            "recovery_structured": "structured",
        }[condition_id]
        environment = Map26Environment(feedback_mode=feedback_mode, step_limit=step_limit)
    else:
        environment = Map30Environment(
            casebook_visible=condition_id == "history5_casebook", step_limit=step_limit
        )
    environment.condition_id = condition_id
    environment.source_hash = source_hash(map_id)
    environment.reset(seed)
    return environment


def source_hash(map_id: str) -> str:
    """Hash the inspected source package without reading it into an Agent request."""
    if map_id not in MAP_IDS:
        raise ValueError("Unknown V4 map ID.")
    root = _MAP_SOURCE_ROOT / map_id
    digest = sha256()
    for relative in (*_SOURCE_FILES, *_CONDITION_SOURCE_FILES.get(map_id, ())):
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Required V4 source file is missing: {relative}")
        content = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def map_source_hashes() -> dict[str, str]:
    return {map_id: source_hash(map_id) for map_id in MAP_IDS}
