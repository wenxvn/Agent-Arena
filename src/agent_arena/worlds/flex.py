"""Parameterized rule engine for pilot maps: branch / parallel / code-first.

Same public contract as the other worlds (six tools, one Action schema,
Observation-only agents, shared ToolReason vocabulary). Only three things
vary by JSON definition: repair sites (branch vs parallel collection),
whether reading the code needs power (order), and which containers reveal
items. Seeded variants reuse the identical rules with per-seed placement.
"""

from __future__ import annotations

import json
import random
from hashlib import sha256
from importlib.resources import files
from itertools import combinations
from math import gcd

from pydantic import BaseModel, ConfigDict

from agent_arena.arena.environment import Environment
from agent_arena.arena.models import (
    Action,
    InspectAction,
    LookAction,
    MoveAction,
    Observation,
    PickupAction,
    PublicMilestone,
    ReadTerminalAction,
    ToolReason,
    ToolResult,
    ToolStatus,
    UseAction,
    WorldState,
)
from agent_arena.worlds.spaceship_escape import (
    ItemDefinition,
    ObjectDefinition,
    RoomDefinition,
)


class FlexCell(BaseModel):
    """One replaceable unit inside a repair site."""

    model_config = ConfigDict(frozen=True)

    cell: str
    tool: str


class FlexSite(BaseModel):
    """One repair site: a panel plus one or more cells."""

    model_config = ConfigDict(frozen=True)

    panel: str
    panel_tool: str
    cells: tuple[FlexCell, ...]


class FlexMilestone(BaseModel):
    """Declarative milestone; triggers reuse the shared ToolReason vocabulary."""

    model_config = ConfigDict(frozen=True)

    stage: str
    done_text: str
    undone: str
    key_items: frozenset[str] = frozenset()
    trigger_reasons: frozenset[ToolReason] = frozenset()


class FlexDefinition(BaseModel):
    """Versioned data for one flex pilot map (fixed tool placement)."""

    model_config = ConfigDict(frozen=True)

    world_id: str
    slug: str
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]
    containers: tuple[str, ...]
    repair_sites: tuple[FlexSite, ...]
    repair_rooms: tuple[str, ...]
    code_terminal: str
    code_requires_power: bool = True
    code_label: str
    decoy_terminals: tuple[str, ...] = ()
    diagnostic_terminal: str
    diagnostic_ok: str
    diagnostic_down: str
    escape_room: str
    escape_vehicle: str
    summaries: dict[ToolReason, str]
    cell_staged_summary: str
    panel_opened_summary: str
    power_restored_summary: str
    escape_summary: str
    no_power_summary: str
    milestones: tuple[FlexMilestone, ...]
    seed_containers: tuple[str, ...] = ()


class FlexSeededDefinition(FlexDefinition):
    """Same map with per-seed tool placement among seed_containers."""

    model_config = ConfigDict(frozen=True)


def _load(name: str, model: type[FlexDefinition]) -> FlexDefinition:
    path = files("agent_arena.worlds").joinpath(f"data/{name}.json")
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def build_seeded_items(definition: FlexDefinition, seed: int) -> tuple[ItemDefinition, ...]:
    """Deterministically deal tool items across the candidate containers."""

    if not definition.seed_containers:
        return definition.items
    tools = sorted({item.id for item in definition.items})
    rng = random.Random(seed)
    order = list(definition.seed_containers)
    rng.shuffle(order)
    return tuple(
        ItemDefinition(id=tool, container_id=order[index % len(order)])
        for index, tool in enumerate(tools)
    )


_V3_SEEDED_LAYOUT_CACHE: dict[tuple[str, str], tuple[FlexSeededDefinition, ...]] = {}


def build_v3_seeded_definition(
    definition: FlexSeededDefinition, seed: int
) -> FlexSeededDefinition:
    """Select one frozen V3 layout using a stable, exhaustive seed permutation."""

    if seed < 0:
        raise ValueError("V3 seeded worlds require a non-negative seed.")
    base_identity = FlexEnvironment(definition=definition).identity
    cache_key = (definition.world_id, base_identity[3])
    layouts = _V3_SEEDED_LAYOUT_CACHE.get(cache_key)
    if layouts is None:
        layouts = _build_v3_layout_population(definition)
        _V3_SEEDED_LAYOUT_CACHE[cache_key] = layouts

    population_size = len(layouts)
    digest = sha256(
        f"agent-arena-v3-seed-map-v1\0{base_identity[1]}".encode()
    ).digest()
    stride = int.from_bytes(digest[:8], "big") % population_size or 1
    while gcd(stride, population_size) != 1:
        stride = (stride + 1) % population_size or 1
    offset = int.from_bytes(digest[8:16], "big") % population_size
    layout_index = (offset + stride * (seed % population_size)) % population_size
    return layouts[layout_index]


def _build_v3_layout_population(
    definition: FlexSeededDefinition,
) -> tuple[FlexSeededDefinition, ...]:
    containers = definition.seed_containers
    if len(containers) != 6 or len(set(containers)) != 6:
        raise ValueError("V3 seeded worlds require exactly six unique candidate containers.")
    tools = tuple(sorted(item.id for item in definition.items))
    if len(tools) not in {2, 4}:
        raise ValueError("V3 seeded layouts support either two or four tools.")

    objects = {item.id: item for item in definition.objects}
    if any(container not in objects for container in containers):
        raise ValueError("Every V3 seed container must have an object definition.")
    slot_rooms = {container: objects[container].room_id for container in containers}
    population: list[tuple[str, FlexSeededDefinition]] = []
    candidate_ids = set(containers)

    for container_a, container_b in combinations(containers, 2):
        if len(tools) == 4:
            distributions = [
                {
                    **{tool: container_a for tool in left},
                    **{tool: container_b for tool in tools if tool not in left},
                }
                for left in combinations(tools, 2)
            ]
        else:
            distributions = [
                {tools[0]: container_a, tools[1]: container_b},
                {tools[0]: container_b, tools[1]: container_a},
            ]

        for distribution in distributions:
            active_ids = tuple(sorted(set(distribution.values())))
            rooms = []
            for room in definition.rooms:
                object_ids = [
                    object_id
                    for object_id in room.object_ids
                    if object_id not in candidate_ids
                ]
                object_ids.extend(
                    container_id
                    for container_id in active_ids
                    if slot_rooms[container_id] == room.id
                )
                rooms.append(room.model_copy(update={"object_ids": tuple(object_ids)}))

            layout = definition.model_copy(
                update={
                    "rooms": tuple(rooms),
                    "items": tuple(
                        ItemDefinition(id=tool, container_id=container_id)
                        for tool, container_id in sorted(distribution.items())
                    ),
                }
            )
            instance_hash = FlexEnvironment(definition=layout).identity[3]
            population.append((instance_hash, layout))

    if not population:
        raise ValueError("V3 seeded definition produced no layouts.")
    if len({instance_hash for instance_hash, _ in population}) != len(population):
        raise ValueError("V3 seeded definition produced duplicate instance hashes.")
    return tuple(layout for _, layout in sorted(population, key=lambda item: item[0]))


class FlexEnvironment(Environment):
    """One engine for branch, parallel-collection and code-first pilot maps."""

    def __init__(self, definition: FlexDefinition | None = None, seed: int = 0) -> None:
        self.definition = definition or _load("lunar_escape_v2", FlexDefinition)
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._panels: dict[str, FlexSite] = {}
        self._cells: dict[str, tuple[FlexSite, FlexCell]] = {}
        for site in self.definition.repair_sites:
            self._panels[site.panel] = site
            for cell in site.cells:
                self._cells[cell.cell] = (site, cell)
        self._state = self._initial_state(seed)
        self._open_panels: set[str] = set()
        self._done_cells: set[str] = set()

    @property
    def identity(self) -> tuple[str, str, str, str]:
        definition_data = self.definition.model_dump(mode="json")
        # Pydantic preserves frozenset iteration order in JSON arrays; normalize the
        # unordered milestone fields so this world hash is stable across processes.
        for milestone in definition_data["milestones"]:
            milestone["key_items"] = sorted(milestone["key_items"])
            milestone["trigger_reasons"] = sorted(milestone["trigger_reasons"])
        serialized = json.dumps(definition_data, sort_keys=True)
        return (
            self.definition.slug,
            f"{self.definition.slug}-{self.definition.version}",
            self.definition.world_id,
            sha256(serialized.encode("utf-8")).hexdigest(),
        )

    def reset(self, seed: int = 0) -> Observation:
        self._state = self._initial_state(seed)
        self._open_panels = set()
        self._done_cells = set()
        return self.observe()

    def observe(self) -> Observation:
        room = self._current_room()
        return Observation(
            current_room=room.id,
            description=room.description,
            visible_objects=self._visible_objects(),
            available_exits=self._available_exits(),
            inventory=tuple(sorted(self._state.inventory)),
            last_action_result=self._state.last_action_result,
        )

    def step(self, action: Action) -> tuple[ToolResult, Observation]:
        self._state.step_count += 1
        if self._state.escaped:
            result = self._rejected(ToolReason.ALREADY_COMPLETED)
        elif isinstance(action, LookAction):
            result = self._success(ToolReason.LOOKED)
        elif isinstance(action, MoveAction):
            result = self._move(action)
        elif isinstance(action, InspectAction):
            result = self._inspect(action)
        elif isinstance(action, PickupAction):
            result = self._pickup(action)
        elif isinstance(action, UseAction):
            result = self._use(action)
        elif isinstance(action, ReadTerminalAction):
            result = self._read_terminal(action)
        else:
            raise TypeError(f"Unsupported validated action: {action!r}")

        self._state.last_action_result = result
        return result, self.observe()

    def is_success(self) -> bool:
        return self._state.escaped

    @property
    def public_milestones(self) -> tuple[PublicMilestone, ...]:
        return tuple(
            PublicMilestone(
                stage=item.stage,
                done_text=item.done_text,
                undone=item.undone,
                key_items=item.key_items,
                trigger_reasons=item.trigger_reasons,
            )
            for item in self.definition.milestones
        )

    def _initial_state(self, seed: int) -> WorldState:
        return WorldState(seed=seed, current_room=self.definition.start_room)

    def _current_room(self) -> RoomDefinition:
        return self._rooms[self._state.current_room]

    def _available_exits(self) -> tuple[str, ...]:
        exits = self._current_room().exits
        if (
            self._state.current_room in self.definition.repair_rooms
            and not self._state.authorization_code_read
        ):
            return tuple(
                destination
                for destination in exits
                if destination != self.definition.escape_room
            )
        return exits

    def _visible_objects(self) -> tuple[str, ...]:
        visible = list(self._current_room().object_ids)
        for container_id in sorted({item.container_id for item in self._items.values()}):
            if self._state.current_room != self._objects[container_id].room_id:
                continue
            contained = [
                item_id
                for item_id, item in self._items.items()
                if item.container_id == container_id
            ]
            if contained and all(item_id in self._state.inventory for item_id in contained):
                visible = [object_id for object_id in visible if object_id != container_id]
            visible.extend(
                item_id
                for item_id in sorted(self._state.revealed_items)
                if item_id not in self._state.inventory
                and self._items.get(item_id) is not None
                and self._items[item_id].container_id == container_id
            )
        for panel, site in self._panels.items():
            if panel not in self._open_panels:
                for cell in site.cells:
                    visible = [object_id for object_id in visible if object_id != cell.cell]
            else:
                visible = [object_id for object_id in visible if object_id != panel]
                if self._state.main_power:
                    for cell in site.cells:
                        visible = [object_id for object_id in visible if object_id != cell.cell]
        return tuple(visible)

    def _move(self, action: MoveAction) -> ToolResult:
        if action.destination not in self._available_exits():
            return self._rejected(ToolReason.NOT_ADJACENT)
        self._state.current_room = action.destination
        return self._success(ToolReason.MOVED)

    def _inspect(self, action: InspectAction) -> ToolResult:
        if action.target not in self._visible_objects() or action.target not in self._objects:
            return self._rejected(ToolReason.NOT_VISIBLE)
        if self._objects[action.target].kind == "terminal":
            return self._rejected(ToolReason.READ_TERMINAL_REQUIRED)
        if action.target in self.definition.containers:
            self._state.revealed_items.update(
                item_id
                for item_id, item in self._items.items()
                if item.container_id == action.target
            )
        return self._success(ToolReason.INSPECTED, self._objects[action.target].inspect_result)

    def _pickup(self, action: PickupAction) -> ToolResult:
        if action.item in self._state.inventory:
            return self._rejected(ToolReason.ALREADY_COLLECTED)
        item = self._items.get(action.item)
        if item is None:
            return self._rejected(ToolReason.NOT_PRESENT)
        if action.item not in self._state.revealed_items:
            return self._rejected(ToolReason.NOT_REVEALED)
        container = self._objects[item.container_id]
        if container.room_id != self._state.current_room:
            return self._rejected(ToolReason.NOT_PRESENT)
        self._state.inventory.add(action.item)
        return self._success(ToolReason.PICKED_UP)

    def _use(self, action: UseAction) -> ToolResult:
        if action.target in self._panels:
            return self._open_panel(action)
        if action.target in self._cells:
            return self._replace_cell(action)
        if action.target == self.definition.escape_vehicle:
            return self._escape(action)
        return self._rejected(ToolReason.WRONG_TARGET)

    def _open_panel(self, action: UseAction) -> ToolResult:
        site = self._panels[action.target]
        if self._state.current_room not in self.definition.repair_rooms:
            return self._rejected(ToolReason.WRONG_TARGET)
        if action.item != site.panel_tool or action.item not in self._state.inventory:
            return self._rejected(ToolReason.MISSING_ITEM)
        if action.target in self._open_panels:
            return self._rejected(ToolReason.WRONG_TARGET)
        self._open_panels.add(action.target)
        return self._success(ToolReason.PANEL_OPENED, self.definition.panel_opened_summary)

    def _replace_cell(self, action: UseAction) -> ToolResult:
        site, cell = self._cells[action.target]
        if self._state.current_room not in self.definition.repair_rooms:
            return self._rejected(ToolReason.WRONG_TARGET)
        if action.item != cell.tool or action.item not in self._state.inventory:
            return self._rejected(ToolReason.MISSING_ITEM)
        if site.panel not in self._open_panels:
            return self._rejected(ToolReason.PANEL_CLOSED)
        if self._state.main_power or action.target in self._done_cells:
            return self._rejected(ToolReason.WRONG_TARGET)
        self._done_cells.add(action.target)
        if self._site_complete(site):
            self._state.main_power = True
            return self._success(
                ToolReason.POWER_RESTORED, self.definition.power_restored_summary
            )
        return self._success(ToolReason.CELL_STAGED, self.definition.cell_staged_summary)

    def _site_complete(self, site: FlexSite) -> bool:
        return site.panel in self._open_panels and all(
            cell.cell in self._done_cells for cell in site.cells
        )

    def _escape(self, action: UseAction) -> ToolResult:
        if self._state.current_room != self.definition.escape_room:
            return self._rejected(ToolReason.WRONG_TARGET)
        if not self._state.main_power:
            return self._rejected(ToolReason.NO_POWER, self.definition.no_power_summary)
        if not self._state.authorization_code_read:
            return self._rejected(ToolReason.CODE_UNREAD)
        if action.item != self.definition.authorization_code:
            return self._rejected(ToolReason.INCORRECT_CODE)
        self._state.escaped = True
        return self._success(ToolReason.ESCAPED, self.definition.escape_summary)

    def _read_terminal(self, action: ReadTerminalAction) -> ToolResult:
        if action.target not in self._visible_objects():
            return self._rejected(ToolReason.NOT_VISIBLE)
        if action.target == self.definition.diagnostic_terminal:
            if self._state.main_power:
                return self._success(ToolReason.DIAGNOSTIC_READ, self.definition.diagnostic_ok)
            return self._success(ToolReason.DIAGNOSTIC_READ, self.definition.diagnostic_down)
        if action.target in self.definition.decoy_terminals:
            return self._rejected(ToolReason.NO_POWER, self.definition.no_power_summary)
        if action.target == self.definition.code_terminal:
            if self.definition.code_requires_power and not self._state.main_power:
                return self._rejected(ToolReason.NO_POWER, self.definition.no_power_summary)
            self._state.authorization_code_read = True
            return self._success(
                ToolReason.CODE_READ,
                f"{self.definition.code_label}：{self.definition.authorization_code}",
            )
        return self._rejected(ToolReason.WRONG_TARGET)

    def _success(self, reason: ToolReason, summary: str | None = None) -> ToolResult:
        return ToolResult(
            status=ToolStatus.SUCCESS,
            reason=reason,
            summary=summary or self.definition.summaries[reason],
        )

    def _rejected(self, reason: ToolReason, summary: str | None = None) -> ToolResult:
        return ToolResult(
            status=ToolStatus.REJECTED,
            reason=reason,
            summary=summary or self.definition.summaries[reason],
        )


class LunarV2Environment(FlexEnvironment):
    """Branch pilot: main or auxiliary reactor, either one restores power."""

    def __init__(self, definition: FlexDefinition | None = None, seed: int = 0) -> None:
        resolved = definition or _load("lunar_escape_v2", FlexDefinition)
        super().__init__(resolved, seed)


class LunarV2SeededEnvironment(FlexEnvironment):
    """Seeded branch pilot: tool placement varies with seed, same rules."""

    def __init__(self, definition: FlexSeededDefinition | None = None, seed: int = 0) -> None:
        base = definition or _load("lunar_escape_v2_seeded", FlexSeededDefinition)
        assert isinstance(base, FlexSeededDefinition)
        placed = base.model_copy(update={"items": build_seeded_items(base, seed)})
        super().__init__(placed, seed)


class LunarV3SeededEnvironment(FlexEnvironment):
    """Seeded branch pilot with a frozen 90-layout V3 population."""

    def __init__(self, definition: FlexSeededDefinition | None = None, seed: int = 0) -> None:
        base = definition or load_lunar_v3_seeded_definition()
        assert isinstance(base, FlexSeededDefinition)
        super().__init__(build_v3_seeded_definition(base, seed), seed)


class CastleV2Environment(FlexEnvironment):
    """Parallel-collection pilot: one furnace needs a lid plus two cells."""

    def __init__(self, definition: FlexDefinition | None = None, seed: int = 0) -> None:
        resolved = definition or _load("castle_escape_v2", FlexDefinition)
        super().__init__(resolved, seed)


class CastleV2SeededEnvironment(FlexEnvironment):
    """Seeded parallel-collection pilot: tool placement varies with seed."""

    def __init__(self, definition: FlexSeededDefinition | None = None, seed: int = 0) -> None:
        base = definition or _load("castle_escape_v2_seeded", FlexSeededDefinition)
        assert isinstance(base, FlexSeededDefinition)
        placed = base.model_copy(update={"items": build_seeded_items(base, seed)})
        super().__init__(placed, seed)


class PyramidV2Environment(FlexEnvironment):
    """Code-first pilot: the glyph console reads without power."""

    def __init__(self, definition: FlexDefinition | None = None, seed: int = 0) -> None:
        resolved = definition or _load("pyramid_escape_v2", FlexDefinition)
        super().__init__(resolved, seed)


class PyramidV2SeededEnvironment(FlexEnvironment):
    """Seeded code-first pilot: tool placement varies with seed."""

    def __init__(self, definition: FlexSeededDefinition | None = None, seed: int = 0) -> None:
        base = definition or _load("pyramid_escape_v2_seeded", FlexSeededDefinition)
        assert isinstance(base, FlexSeededDefinition)
        placed = base.model_copy(update={"items": build_seeded_items(base, seed)})
        super().__init__(placed, seed)


class PyramidV3SeededEnvironment(FlexEnvironment):
    """Seeded code-first pilot with a frozen 30-layout V3 population."""

    def __init__(self, definition: FlexSeededDefinition | None = None, seed: int = 0) -> None:
        base = definition or load_pyramid_v3_seeded_definition()
        assert isinstance(base, FlexSeededDefinition)
        super().__init__(build_v3_seeded_definition(base, seed), seed)


def load_lunar_v2_definition() -> FlexDefinition:
    """Load the checked in branch pilot definition."""

    return _load("lunar_escape_v2", FlexDefinition)


def load_lunar_v2_seeded_definition() -> FlexSeededDefinition:
    """Load the checked in seeded branch pilot definition."""

    loaded = _load("lunar_escape_v2_seeded", FlexSeededDefinition)
    assert isinstance(loaded, FlexSeededDefinition)
    return loaded


def load_lunar_v3_seeded_definition() -> FlexSeededDefinition:
    """Load the checked in six-container V3 branch definition."""

    loaded = _load("lunar_escape_v3_seeded", FlexSeededDefinition)
    assert isinstance(loaded, FlexSeededDefinition)
    return loaded


def load_castle_v2_definition() -> FlexDefinition:
    """Load the checked in parallel-collection pilot definition."""

    return _load("castle_escape_v2", FlexDefinition)


def load_castle_v2_seeded_definition() -> FlexSeededDefinition:
    """Load the checked in seeded parallel-collection pilot definition."""

    loaded = _load("castle_escape_v2_seeded", FlexSeededDefinition)
    assert isinstance(loaded, FlexSeededDefinition)
    return loaded


def load_pyramid_v2_definition() -> FlexDefinition:
    """Load the checked in code-first pilot definition."""

    return _load("pyramid_escape_v2", FlexDefinition)


def load_pyramid_v2_seeded_definition() -> FlexSeededDefinition:
    """Load the checked in seeded code-first pilot definition."""

    loaded = _load("pyramid_escape_v2_seeded", FlexSeededDefinition)
    assert isinstance(loaded, FlexSeededDefinition)
    return loaded


def load_pyramid_v3_seeded_definition() -> FlexSeededDefinition:
    """Load the checked in six-container V3 code-first definition."""

    loaded = _load("pyramid_escape_v3_seeded", FlexSeededDefinition)
    assert isinstance(loaded, FlexSeededDefinition)
    return loaded
