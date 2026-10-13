"""Deterministic implementation of the eighth world: Jungle Ruins."""

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


class JungleDefinition(BaseModel):
    """Versioned, read only data needed to instantiate the jungle world."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["jungle_escape_v1"]
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


def load_jungle_definition() -> JungleDefinition:
    """Load the checked in static definition for the jungle world."""

    definition_path = files("agent_arena.worlds").joinpath("data/jungle_escape_v1.json")
    return JungleDefinition.model_validate_json(definition_path.read_text(encoding="utf-8"))


class JungleEasyDefinition(BaseModel):
    """Versioned data for the six room easy jungle; same rule contract."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["jungle_escape_easy"]
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]


def load_jungle_easy_definition() -> JungleEasyDefinition:
    """Load the checked in static definition for the easy jungle version."""

    definition_path = files("agent_arena.worlds").joinpath("data/jungle_escape_easy.json")
    return JungleEasyDefinition.model_validate_json(
        definition_path.read_text(encoding="utf-8")
    )


class JungleHardDefinition(BaseModel):
    """Versioned data for the ten room hard jungle; same rule contract."""

    model_config = ConfigDict(frozen=True)

    world_id: Literal["jungle_escape_hard"]
    version: str
    goal: str
    start_room: str
    authorization_code: str
    rooms: tuple[RoomDefinition, ...]
    objects: tuple[ObjectDefinition, ...]
    items: tuple[ItemDefinition, ...]


def load_jungle_hard_definition() -> JungleHardDefinition:
    """Load the checked in static definition for the hard jungle version."""

    definition_path = files("agent_arena.worlds").joinpath("data/jungle_escape_hard.json")
    return JungleHardDefinition.model_validate_json(
        definition_path.read_text(encoding="utf-8")
    )


JUNGLE_MILESTONES: tuple[PublicMilestone, ...] = (
    PublicMilestone(
        stage="收集修理工具",
        done_text="无",
        undone="获得 {missing}",
        key_items=frozenset({"machete", "solar_cell"}),
    ),
    PublicMilestone(
        stage="恢复供电",
        done_text="修理工具",
        undone="打开苔藓舱盖",
        trigger_reasons=frozenset({ToolReason.PANEL_OPENED}),
    ),
    PublicMilestone(
        stage="恢复供电",
        done_text="修理工具和苔藓舱盖",
        undone="恢复供电",
        trigger_reasons=frozenset({ToolReason.POWER_RESTORED}),
    ),
    PublicMilestone(
        stage="读取祭坛码",
        done_text="修理工具和供电",
        undone="读取祭坛码",
        trigger_reasons=frozenset({ToolReason.CODE_READ}),
    ),
    PublicMilestone(
        stage="乘河船离开",
        done_text="修理工具、供电和祭坛码",
        undone="乘河船离开",
    ),
)


class JungleEnvironment(Environment):
    """An eight room jungle world with decoys and a single public escape route."""

    definition: WorldDefinitionLike

    def __init__(self, definition: JungleDefinition | None = None, seed: int = 0) -> None:
        self.definition = definition or load_jungle_definition()
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._state = self._initial_state(seed)

    @property
    def identity(self) -> tuple[str, str, str, str]:
        serialized = json.dumps(self.definition.model_dump(mode="json"), sort_keys=True)
        return (
            "jungle-escape",
            f"jungle-escape-{self.definition.version}",
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
        return JUNGLE_MILESTONES

    def _initial_state(self, seed: int) -> WorldState:
        return WorldState(seed=seed, current_room=self.definition.start_room)

    def _current_room(self) -> RoomDefinition:
        return self._rooms[self._state.current_room]

    def _available_exits(self) -> tuple[str, ...]:
        exits = self._current_room().exits
        if self._state.current_room == "temple_engine" and not self._state.authorization_code_read:
            return tuple(destination for destination in exits if destination != "river_pier")
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
        if not self._state.reactor_panel_open:
            visible = [object_id for object_id in visible if object_id != "dead_cell"]
        else:
            visible = [object_id for object_id in visible if object_id != "mossy_hatch"]
        if self._state.main_power:
            visible = [object_id for object_id in visible if object_id != "dead_cell"]
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
        if action.target == "cache_box":
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
        if action.target == "mossy_hatch":
            return self._open_panel(action)
        if action.target == "dead_cell":
            return self._restore_power(action)
        if action.target == "river_boat":
            return self._escape(action)
        return self._rejected(ToolReason.WRONG_TARGET)

    def _open_panel(self, action: UseAction) -> ToolResult:
        if self._state.current_room != "temple_engine":
            return self._rejected(ToolReason.WRONG_TARGET)
        if action.item != "machete" or action.item not in self._state.inventory:
            return self._rejected(ToolReason.MISSING_ITEM)
        if self._state.reactor_panel_open:
            return self._rejected(ToolReason.WRONG_TARGET)
        self._state.reactor_panel_open = True
        return self._success(ToolReason.PANEL_OPENED)

    def _restore_power(self, action: UseAction) -> ToolResult:
        if self._state.current_room != "temple_engine":
            return self._rejected(ToolReason.WRONG_TARGET)
        if action.item != "solar_cell" or action.item not in self._state.inventory:
            return self._rejected(ToolReason.MISSING_ITEM)
        if not self._state.reactor_panel_open:
            return self._rejected(ToolReason.PANEL_CLOSED)
        if self._state.main_power:
            return self._rejected(ToolReason.WRONG_TARGET)
        self._state.main_power = True
        return self._success(ToolReason.POWER_RESTORED)

    def _escape(self, action: UseAction) -> ToolResult:
        if self._state.current_room != "river_pier":
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
        if action.target == "ranger_radio":
            if self._state.main_power:
                return self._success(
                    ToolReason.DIAGNOSTIC_READ,
                    "巡护广播：供电稳定，各系统正常。",
                )
            return self._success(
                ToolReason.DIAGNOSTIC_READ,
                "巡护广播：电力中断，请手动修复神庙机房的老水力机。",
            )
        if action.target == "broken_sign":
            return self._rejected(ToolReason.NO_POWER)
        if action.target == "altar_console":
            if not self._state.main_power:
                return self._rejected(ToolReason.NO_POWER)
            self._state.authorization_code_read = True
            return self._success(
                ToolReason.CODE_READ,
                f"祭坛码：{self.definition.authorization_code}",
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


class JungleEasyEnvironment(JungleEnvironment):
    """The six room easy jungle; identical rules, compact map and nearby code room."""

    def __init__(self, definition: JungleEasyDefinition | None = None, seed: int = 0) -> None:
        self.definition = definition or load_jungle_easy_definition()
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._state = self._initial_state(seed)


class JungleHardEnvironment(JungleEnvironment):
    """The ten room hard jungle; identical rules, deeper tools and more decoys."""

    def __init__(self, definition: JungleHardDefinition | None = None, seed: int = 0) -> None:
        self.definition = definition or load_jungle_hard_definition()
        self._rooms = {room.id: room for room in self.definition.rooms}
        self._objects = {item.id: item for item in self.definition.objects}
        self._items = {item.id: item for item in self.definition.items}
        self._state = self._initial_state(seed)


_SUMMARIES: dict[ToolReason, str] = {
    ToolReason.LOOKED: "你查看了当前林区。",
    ToolReason.MOVED: "你移动到了指定林区。",
    ToolReason.INSPECTED: "你检查了指定对象。",
    ToolReason.PICKED_UP: "你将物品放入了背包。",
    ToolReason.PANEL_OPENED: "苔藓舱盖已打开。",
    ToolReason.POWER_RESTORED: "供电已恢复。",
    ToolReason.DIAGNOSTIC_READ: "你收听了广播。",
    ToolReason.CODE_READ: "你读取了祭坛终端中的祭坛码。",
    ToolReason.ESCAPED: "河船已成功出发。",
    ToolReason.ALREADY_COMPLETED: "离开程序已经完成。",
    ToolReason.NOT_ADJACENT: "当前林区无法直接到达该处。",
    ToolReason.NOT_VISIBLE: "当前林区看不到该目标。",
    ToolReason.NOT_REVEALED: "该物品尚未被发现。",
    ToolReason.NOT_PRESENT: "当前林区没有该物品。",
    ToolReason.ALREADY_COLLECTED: "该物品已经在背包中。",
    ToolReason.MISSING_ITEM: "你没有所需物品。",
    ToolReason.WRONG_TARGET: "当前不能将该物品用于这个目标。",
    ToolReason.READ_TERMINAL_REQUIRED: "终端请使用 read_terminal 工具读取。",
    ToolReason.PANEL_CLOSED: "请先打开苔藓舱盖，再更换电芯。",
    ToolReason.CODE_UNREAD: "请先读取祭坛码，再启动河船。",
    ToolReason.INCORRECT_CODE: "该祭坛码不正确。",
    ToolReason.NO_POWER: "损坏路牌没有电力。",
}
