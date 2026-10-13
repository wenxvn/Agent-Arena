"""Seeded world variants: same rules, per-seed randomized tool placement.

Only `CANDIDATE_CONTAINERS` placement varies with seed; rooms, exits,
terminals, puzzles and the authorization code are unchanged. Old maps and
their JSON files are never modified by this module.
"""
from __future__ import annotations

import random
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict

from agent_arena.worlds.spaceship_escape import (
    ItemDefinition,
    ObjectDefinition,
    RoomDefinition,
    SpaceshipEscapeEnvironment,
)

CANDIDATE_CONTAINERS: tuple[str, ...] = ("storage_crate", "wall_locker", "supply_crate")

TOOL_ITEMS: tuple[str, ...] = ("screwdriver", "replacement_fuse")


class SeededShipDefinition(BaseModel):
    """Ship map with extra containers; tools are assigned per seed."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["spaceship_escape_v1_seeded"]
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]


def load_seeded_base_definition() -> SeededShipDefinition:
    """Load the static superset map; per-seed placement happens in the builder."""

    definition_path = files("agent_arena.worlds").joinpath(
        "data/spaceship_escape_v1_seeded.json"
    )
    return SeededShipDefinition.model_validate_json(
        definition_path.read_text(encoding="utf-8")
    )


def build_seeded_definition(seed: int) -> SeededShipDefinition:
    """Deterministically assign the two tools to two distinct containers."""

    base = load_seeded_base_definition()
    rng = random.Random(seed)
    order = list(CANDIDATE_CONTAINERS)
    rng.shuffle(order)
    placement = dict(zip(TOOL_ITEMS, order[: len(TOOL_ITEMS)], strict=True))
    items = tuple(
        ItemDefinition(id=item_id, container_id=placement[item_id]) for item_id in TOOL_ITEMS
    )
    return base.model_copy(update={"items": items})


class SeededShipEnvironment(SpaceshipEscapeEnvironment):
    """Identical rules to the ship; only the tool layout depends on seed."""

    def __init__(self, definition: SeededShipDefinition | None = None, seed: int = 0) -> None:
        resolved = definition or build_seeded_definition(seed)
        self.definition = resolved
        self._rooms = {room.id: room for room in resolved.rooms}
        self._objects = {item.id: item for item in resolved.objects}
        self._items = {item.id: item for item in resolved.items}
        self._state = self._initial_state(seed)
