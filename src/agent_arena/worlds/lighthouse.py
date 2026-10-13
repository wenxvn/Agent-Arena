"""Deterministic implementation of the second world: Misty Lighthouse."""

from __future__ import annotations

import json
from hashlib import sha256
from importlib.resources import files
from typing import Literal

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
    ObjectDefinition,
    RoomDefinition,
    WorldDefinitionLike,
)


class LighthouseDefinition(BaseModel):
    """Versioned, read only data needed to instantiate the lighthouse world."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["lighthouse_escape_v1"]
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]


class ItemDefinition(BaseModel):
    """Static item metadata used by pickup rules."""

    model_config = ConfigDict(frozen=True)

    id: str
    container_id: str


def load_lighthouse_definition() -> LighthouseDefinition:
    """Load the checked in static definition for the lighthouse world."""

    definition_path = files("agent_arena.worlds").joinpath("data/lighthouse_escape_v1.json")
    return LighthouseDefinition.model_validate_json(definition_path.read_text(encoding="utf-8"))


class LighthouseV2Definition(BaseModel):
    """Versioned data for the expanded eight room lighthouse; same rule contract."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["lighthouse_escape_v2"]
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]


def load_lighthouse_v2_definition() -> LighthouseV2Definition:
    """Load the checked in static definition for the expanded lighthouse version."""

    definition_path = files("agent_arena.worlds").joinpath("data/lighthouse_escape_v2.json")
    return LighthouseV2Definition.model_validate_json(
        definition_path.read_text(encoding="utf-8")
    )


LIGHTHOUSE_MILESTONES: tuple[PublicMilestone, ...] = (
    PublicMilestone(
        stage="收集修理工具",
        done_text="无",
        undone="获得 {missing}",
        key_items=frozenset({"wrench", "spare_cell"}),
    ),
    PublicMilestone(
        stage="恢复电力",
        done_text="修理工具",
        undone="打开引擎盖板",
        trigger_reasons=frozenset({ToolReason.PANEL_OPENED}),
    ),
    PublicMilestone(
        stage="恢复电力",
        done_text="修理工具和引擎盖板",
        undone="恢复电力",
        trigger_reasons=frozenset({ToolReason.POWER_RESTORED}),
    ),
    PublicMilestone(
        stage="读取潮汐码",
        done_text="修理工具和电力",
        undone="读取潮汐码",
        trigger_reasons=frozenset({ToolReason.CODE_READ}),
    ),
    PublicMilestone(
        stage="乘坐小艇离开",
        done_text="修理工具、电力和潮汐码",
        undone="乘坐小艇离开",
    ),
)


class LighthouseEnvironment(Environment):
    """A six room chain world with a single public escape route."""

    definition: WorldDefinitionLike

    def __init__(self, definition: LighthouseDefinition | None = None, seed: int = 0) -> None:
        self.definition = definition or load_lighthouse_definition()
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._state = self._initial_state(seed)

    @property
    def identity(self) -> tuple[str, str, str, str]:
        serialized = json.dumps(self.definition.model_dump(mode="json"), sort_keys=True)
        return (
            "lighthouse-escape",
            f"lighthouse-escape-{self.definition.version}",
            self.definition.world_id,
            sha256(serialized.encode("utf-8")).hexdigest(),
        )

    def reset(self, seed: int = 0) -> Observation:
        self._state = self._initial_state(seed)
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
        return LIGHTHOUSE_MILESTONES

    def _initial_state(self, seed: int) -> WorldState:
        return WorldState(seed=seed, current_room=self.definition.start_room)

    def _current_room(self) -> RoomDefinition:
        return self._rooms[self._state.current_room]

    def _available_exits(self) -> tuple[str, ...]:
        exits = self._current_room().exits
        if self._state.current_room == "engine_cave" and not self._state.authorization_code_read:
            return tuple(destination for destination in exits if destination != "skiff_cove")
        return exits

    def _visible_objects(self) -> tuple[str, ...]:
        visible = list(self._current_room().object_ids)
        for container_id in sorted(
            {item.container_id for item in self._items.values()}
        ):
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
        visible = [
            object_id for object_id in visible if object_id not in self._state.blocked_objects
        ]
        if not self._state.reactor_panel_open:
            visible = [object_id for object_id in visible if object_id != "burnt_cell"]
        else:
            visible = [object_id for object_id in visible if object_id != "engine_cover"]
        if self._state.main_power:
            visible = [object_id for object_id in visible if object_id != "burnt_cell"]
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
        if action.target == "tool_chest":
            self._state.revealed_items.update(self._items)
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
        if action.target == "engine_cover":
            return self._open_engine_cover(action)
        if action.target == "burnt_cell":
            return self._replace_cell(action)
        if action.target == "harbor_skiff":
            return self._launch_skiff(action)
        return self._rejected(ToolReason.WRONG_TARGET)

    def _open_engine_cover(self, action: UseAction) -> ToolResult:
        if self._state.current_room != "engine_cave":
            return self._rejected(ToolReason.WRONG_TARGET)
        if action.item != "wrench" or action.item not in self._state.inventory:
            return self._rejected(ToolReason.MISSING_ITEM)
        if self._state.reactor_panel_open:
            return self._rejected(ToolReason.WRONG_TARGET)
        self._state.reactor_panel_open = True
        return self._success(ToolReason.PANEL_OPENED)

    def _replace_cell(self, action: UseAction) -> ToolResult:
        if self._state.current_room != "engine_cave":
            return self._rejected(ToolReason.WRONG_TARGET)
        if action.item != "spare_cell" or action.item not in self._state.inventory:
            return self._rejected(ToolReason.MISSING_ITEM)
        if not self._state.reactor_panel_open:
            return self._rejected(ToolReason.PANEL_CLOSED)
        if self._state.main_power:
            return self._rejected(ToolReason.WRONG_TARGET)
        self._state.main_power = True
        return self._success(ToolReason.POWER_RESTORED)

    def _launch_skiff(self, action: UseAction) -> ToolResult:
        if self._state.current_room != "skiff_cove":
            return self._rejected(ToolReason.WRONG_TARGET)
        if not self._state.authorization_code_read:
            return self._rejected(ToolReason.CODE_UNREAD)
        if action.item != self.definition.authorization_code:
            return self._rejected(ToolReason.INCORRECT_CODE)
        self._state.escaped = True
        return self._success(ToolReason.ESCAPED)

    def _read_terminal(self, action: ReadTerminalAction) -> ToolResult:
        if action.target not in self._visible_objects():
            return self._rejected(ToolReason.NOT_VISIBLE)
        if action.target == "field_radio":
            if self._state.main_power:
                return self._success(
                    ToolReason.DIAGNOSTIC_READ,
                    "电台广播：电力稳定，各系统正常。",
                )
            return self._success(
                ToolReason.DIAGNOSTIC_READ,
                "电台广播：电力中断，请手动修复引擎洞的老引擎。",
            )
        if action.target == "signal_board":
            return self._rejected(ToolReason.NO_POWER)
        if action.target == "lamp_console":
            if not self._state.main_power:
                return self._rejected(ToolReason.NO_POWER)
            self._state.authorization_code_read = True
            return self._success(
                ToolReason.CODE_READ,
                f"潮汐码：{self.definition.authorization_code}",
            )
        return self._rejected(ToolReason.WRONG_TARGET)

    @staticmethod
    def _success(reason: ToolReason, summary: str | None = None) -> ToolResult:
        return ToolResult(
            status=ToolStatus.SUCCESS,
            reason=reason,
            summary=summary or _SUMMARIES[reason],
        )

    @staticmethod
    def _rejected(reason: ToolReason) -> ToolResult:
        return ToolResult(status=ToolStatus.REJECTED, reason=reason, summary=_SUMMARIES[reason])


class LighthouseV2Environment(LighthouseEnvironment):
    """The expanded eight room lighthouse; identical rules, new map and code."""

    def __init__(self, definition: LighthouseV2Definition | None = None, seed: int = 0) -> None:
        self.definition = definition or load_lighthouse_v2_definition()
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._state = self._initial_state(seed)


class LighthouseV4Definition(BaseModel):
    """Versioned data for the redesigned six room easy lighthouse; same rule contract."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["lighthouse_escape_v4"]
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]


def load_lighthouse_v4_definition() -> LighthouseV4Definition:
    """Load the checked in static definition for the redesigned easy lighthouse."""

    definition_path = files("agent_arena.worlds").joinpath("data/lighthouse_escape_v4.json")
    return LighthouseV4Definition.model_validate_json(
        definition_path.read_text(encoding="utf-8")
    )


class LighthouseV5Definition(BaseModel):
    """Versioned data for the redesigned eight room medium lighthouse; same rule contract."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["lighthouse_escape_v5"]
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]


def load_lighthouse_v5_definition() -> LighthouseV5Definition:
    """Load the checked in static definition for the redesigned medium lighthouse."""

    definition_path = files("agent_arena.worlds").joinpath("data/lighthouse_escape_v5.json")
    return LighthouseV5Definition.model_validate_json(
        definition_path.read_text(encoding="utf-8")
    )


class LighthouseV6Definition(BaseModel):
    """Versioned data for the redesigned ten room hard lighthouse; same rule contract."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["lighthouse_escape_v6"]
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]


def load_lighthouse_v6_definition() -> LighthouseV6Definition:
    """Load the checked in static definition for the redesigned hard lighthouse."""

    definition_path = files("agent_arena.worlds").joinpath("data/lighthouse_escape_v6.json")
    return LighthouseV6Definition.model_validate_json(
        definition_path.read_text(encoding="utf-8")
    )


class LighthouseV4Environment(LighthouseEnvironment):
    """The redesigned six room easy lighthouse: dead-end radio, forked workshop."""

    def __init__(self, definition: LighthouseV4Definition | None = None, seed: int = 0) -> None:
        self.definition = definition or load_lighthouse_v4_definition()
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._state = self._initial_state(seed)


class LighthouseV5Environment(LighthouseEnvironment):
    """The redesigned eight room medium lighthouse: code in the signal tower."""

    def __init__(self, definition: LighthouseV5Definition | None = None, seed: int = 0) -> None:
        self.definition = definition or load_lighthouse_v5_definition()
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._state = self._initial_state(seed)


class LighthouseV6Environment(LighthouseEnvironment):
    """The redesigned ten room hard lighthouse: chain plus two decoy pairs."""

    def __init__(self, definition: LighthouseV6Definition | None = None, seed: int = 0) -> None:
        self.definition = definition or load_lighthouse_v6_definition()
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._state = self._initial_state(seed)


class LighthouseV3Definition(BaseModel):
    """Versioned data for the ten room hard lighthouse; same rule contract."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["lighthouse_escape_v3"]
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]


def load_lighthouse_v3_definition() -> LighthouseV3Definition:
    """Load the checked in static definition for the hard lighthouse version."""

    definition_path = files("agent_arena.worlds").joinpath("data/lighthouse_escape_v3.json")
    return LighthouseV3Definition.model_validate_json(
        definition_path.read_text(encoding="utf-8")
    )


class LighthouseV3Environment(LighthouseV2Environment):
    """The ten room hard lighthouse; identical rules, deeper tools and moved code room."""

    def __init__(self, definition: LighthouseV3Definition | None = None, seed: int = 0) -> None:
        self.definition = definition or load_lighthouse_v3_definition()
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._state = self._initial_state(seed)


_SUMMARIES: dict[ToolReason, str] = {
    ToolReason.LOOKED: "你查看了当前地点。",
    ToolReason.MOVED: "你移动到了指定地点。",
    ToolReason.INSPECTED: "你检查了指定对象。",
    ToolReason.PICKED_UP: "你将物品放入了背包。",
    ToolReason.PANEL_OPENED: "引擎盖板已打开。",
    ToolReason.POWER_RESTORED: "电力已恢复。",
    ToolReason.DIAGNOSTIC_READ: "你收听了电台广播。",
    ToolReason.CODE_READ: "你读取了信号灯控制台中的潮汐码。",
    ToolReason.ESCAPED: "小艇已成功出发。",
    ToolReason.ALREADY_COMPLETED: "离开程序已经完成。",
    ToolReason.NOT_ADJACENT: "当前地点无法直接到达该处。",
    ToolReason.NOT_VISIBLE: "当前地点看不到该目标。",
    ToolReason.NOT_REVEALED: "该物品尚未被发现。",
    ToolReason.NOT_PRESENT: "当前地点没有该物品。",
    ToolReason.ALREADY_COLLECTED: "该物品已经在背包中。",
    ToolReason.MISSING_ITEM: "你没有所需物品。",
    ToolReason.WRONG_TARGET: "当前不能将该物品用于这个目标。",
    ToolReason.READ_TERMINAL_REQUIRED: "终端请使用 read_terminal 工具读取。",
    ToolReason.PANEL_CLOSED: "请先打开引擎盖板，再更换电芯。",
    ToolReason.CODE_UNREAD: "请先读取潮汐码，再启动小艇。",
    ToolReason.INCORRECT_CODE: "该潮汐码不正确。",
    ToolReason.NO_POWER: "信号板没有电力。",
}
