"""Shared deterministic lifecycle for V3 worlds, separate from legacy state."""

from __future__ import annotations

import json
from abc import abstractmethod
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_arena.arena.environment import Environment
from agent_arena.arena.models import (
    InspectAction,
    LookAction,
    MoveAction,
    PickupAction,
    ReadTerminalAction,
    ToolReason,
    ToolResult,
    ToolStatus,
    UseAction,
)
from agent_arena.arena.scenario_models import (
    InteractAction,
    InteractionOption,
    PublicStatusFact,
    ScenarioAction,
    ScenarioObservation,
    ScenarioStatus,
    ScenarioStepMetadata,
    ScenarioTerminalStatus,
    SubmitAction,
    WaitAction,
)


class ScenarioState(BaseModel):
    """Mutable state owned by one scenario environment and never sent to Agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    seed: int
    tick: int = Field(default=0, ge=0)
    current_room: str
    inventory: set[str] = Field(default_factory=set)
    revealed_objects: set[str] = Field(default_factory=set)
    last_action_result: ToolResult | None = None
    terminal_status: ScenarioStatus = ScenarioStatus.RUNNING
    failure_reason: str | None = None
    scenario_events: list[str] = Field(default_factory=list)
    score_components: dict[str, int | float | str | bool] = Field(default_factory=dict)
    facts: dict[str, Any] = Field(default_factory=dict)


ScenarioActionResult = tuple[ToolResult, str | None]


class ScenarioEnvironment(Environment):
    """Base lifecycle; each family implements its own typed rule transitions."""

    family: str
    difficulty: str
    scenario_id: str
    public_goal: str
    world: str
    world_version: str
    mechanic_version: str
    start_room: str
    rooms: dict[str, str]
    exits: dict[str, tuple[str, ...]]
    objects: dict[str, tuple[str, str]]
    interactions: dict[str, tuple[str, ...]]
    items: dict[str, str]

    def __init__(
        self,
        *,
        family: str,
        difficulty: str,
        scenario_id: str,
        public_goal: str,
        world: str,
        world_version: str,
        mechanic_version: str,
        start_room: str,
        rooms: dict[str, str],
        exits: dict[str, tuple[str, ...]],
        objects: dict[str, tuple[str, str]],
        interactions: Mapping[str, tuple[str, ...]],
        items: dict[str, str],
        definition: dict[str, Any],
        seed: int = 0,
    ) -> None:
        self.family = family
        self.difficulty = difficulty
        self.scenario_id = scenario_id
        self.public_goal = public_goal
        self.world = world
        self.world_version = world_version
        self.mechanic_version = mechanic_version
        source_design_id = definition.get("source_design_id")
        if not isinstance(source_design_id, str) or not source_design_id:
            raise ValueError("Scenario definition requires a stable source_design_id.")
        self.source_design_id = source_design_id
        self.start_room = start_room
        self.rooms = rooms
        self.exits = exits
        self.objects = objects
        self.interactions = {target: tuple(choices) for target, choices in interactions.items()}
        self.items = items
        self._definition = definition
        self._seed = seed
        self._state: ScenarioState | None = None
        self._last_step_metadata = ScenarioStepMetadata()
        self._definition_hash = _stable_hash(definition)
        self._ruleset_sha = _ruleset_hash(type(self))

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (self.world, self.world_version, self.scenario_id, self._definition_hash)

    @property
    def action_contract_version(self) -> str:
        return "scenario_v3"

    @property
    def definition_hash(self) -> str:
        return self._definition_hash

    @property
    def source_design_hash(self) -> str:
        return self._definition_hash

    @property
    def ruleset_sha(self) -> str:
        return self._ruleset_sha

    @property
    def terminal_status(self) -> ScenarioTerminalStatus:
        state = self._require_state()
        return ScenarioTerminalStatus(
            status=state.terminal_status,
            failure_reason=state.failure_reason,
        )

    @property
    def step_metadata(self) -> ScenarioStepMetadata:
        return self._last_step_metadata

    @property
    def scenario_state(self) -> ScenarioState:
        """Read-only-by-convention testing/debug view; never an Agent input."""

        return self._require_state()

    def reset(self, seed: int = 0) -> ScenarioObservation:
        self._seed = seed
        self._state = self._initial_state(seed)
        self._last_step_metadata = ScenarioStepMetadata()
        return self.observe()

    def observe(self) -> ScenarioObservation:
        state = self._require_state()
        return ScenarioObservation(
            current_room=state.current_room,
            description=self._room_description(state.current_room),
            visible_objects=self._visible_objects(),
            available_exits=self._available_exits(),
            inventory=tuple(sorted(state.inventory)),
            last_action_result=getattr(state, "last_action_result", None),
            scenario_id=self.scenario_id,
            family=self.family,
            difficulty=self.difficulty,  # type: ignore[arg-type]
            public_goal=self.public_goal,
            tick=state.tick,
            public_status=self._public_status(),
            available_interactions=self._available_interactions(),
        )

    def step(self, action: ScenarioAction) -> tuple[ToolResult, ScenarioObservation]:
        state = self._require_state()
        if state.terminal_status is not ScenarioStatus.RUNNING:
            result = ToolResult(
                status=ToolStatus.REJECTED,
                reason=ToolReason.ALREADY_COMPLETED,
                summary="场景已进入终态，没有执行新动作。",
            )
            state.last_action_result = result
            return result, self.observe()

        result, event = self._apply_action(action)
        state.last_action_result = result
        if event:
            state.scenario_events.append(event)
        # Every schema-valid action reaching Environment consumes exactly one tick.
        state.tick += 1
        if state.terminal_status is ScenarioStatus.RUNNING:
            self._advance_tick()
        self._update_terminal_status()
        self._last_step_metadata = ScenarioStepMetadata(
            scenario_event=event,
            scenario_status=state.terminal_status,
            failure_reason=state.failure_reason,
            score_components=dict(state.score_components),
        )
        return result, self.observe()

    def is_success(self) -> bool:
        return self._require_state().terminal_status is ScenarioStatus.SUCCESS

    def _initial_state(self, seed: int) -> ScenarioState:
        return ScenarioState(seed=seed, current_room=self.start_room)

    def _require_state(self) -> ScenarioState:
        if self._state is None:
            raise RuntimeError("Scenario must be reset before use.")
        return self._state

    def _room_description(self, room: str) -> str:
        return self.rooms[room]

    def _available_exits(self) -> tuple[str, ...]:
        state = self._require_state()
        return tuple(
            destination
            for destination in self.exits.get(state.current_room, ())
            if self._edge_is_open(state.current_room, destination)
        )

    def _visible_objects(self) -> tuple[str, ...]:
        room = self._require_state().current_room
        objects = [
            object_id
            for object_id, (object_room, _) in self.objects.items()
            if object_room == room and self._object_is_visible(object_id)
        ]
        objects.extend(
            item_id
            for item_id, item_room in self.items.items()
            if item_room == room and item_id not in self._require_state().inventory
        )
        return tuple(dict.fromkeys(objects))

    def _available_interactions(self) -> tuple[InteractionOption, ...]:
        visible = set(self._visible_objects())
        return tuple(
            InteractionOption(target=target, choices=choices)
            for target, choices in sorted(self.interactions.items())
            if target in visible and choices
        )

    def _object_is_visible(self, object_id: str) -> bool:
        del object_id
        return True

    def _edge_is_open(self, source: str, destination: str) -> bool:
        del source, destination
        return True

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        return ()

    def _apply_action(self, action: ScenarioAction) -> tuple[ToolResult, str | None]:
        """Apply common spatial actions, then delegate scenario mechanics."""

        common_result = self._apply_common_action(action)
        if common_result is not None:
            return common_result
        return self._apply_family_action(action)

    @abstractmethod
    def _apply_family_action(self, action: ScenarioAction) -> tuple[ToolResult, str | None]:
        """Apply a family-specific action not handled by the spatial base."""

    def _apply_common_action(self, action: ScenarioAction) -> tuple[ToolResult, str | None] | None:
        state = self._require_state()
        if isinstance(action, LookAction):
            return applied(self._room_description(state.current_room), "look")
        if isinstance(action, MoveAction):
            if action.destination not in self._available_exits():
                return rejected("目标地点不是当前可通行的出口。", "move_rejected")
            source = state.current_room
            state.current_room = action.destination
            return applied(f"已从 {source} 移动到 {action.destination}。", "moved")
        if isinstance(action, InspectAction):
            if action.target not in self._visible_objects():
                return rejected("目标当前不可见。", "inspect_rejected")
            state.revealed_objects.add(action.target)
            if action.target in self.objects:
                return applied(self.objects[action.target][1], "inspected")
            return applied("该物品在当前地点可见，可直接拾取。", "inspected")
        if isinstance(action, PickupAction):
            if action.item not in self.items or self.items[action.item] != state.current_room:
                return rejected("该物品不在当前位置。", "pickup_rejected")
            if action.item in state.inventory:
                return rejected("该物品已经在背包中。", "pickup_rejected")
            state.inventory.add(action.item)
            return applied(f"已取得 {action.item}。", "item_collected")
        if isinstance(action, InteractAction):
            choices = {option.target: option.choices for option in self._available_interactions()}
            if action.choice not in choices.get(action.target, ()):
                return rejected("该交互目标或选择当前不可用。", "interaction_rejected")
            return None
        if isinstance(action, WaitAction):
            return applied("等待了一个公开世界回合。", "waited")
        if isinstance(action, SubmitAction):
            if action.target not in self._visible_objects():
                return rejected("提交目标当前不可见。", "submit_rejected")
            return None
        if isinstance(action, (UseAction, ReadTerminalAction)):
            return None
        raise TypeError(f"Unsupported ScenarioAction type: {type(action).__name__}")

    def _advance_tick(self) -> None:
        """Apply family-specific periodic effects after direct action effects."""

    def _update_terminal_status(self) -> None:
        """Set success, partial success, or failure from the current family state."""


def applied(summary: str, event: str | None = None) -> tuple[ToolResult, str | None]:
    return (
        ToolResult(
            status=ToolStatus.SUCCESS,
            reason=ToolReason.SCENARIO_ACTION_APPLIED,
            summary=summary,
        ),
        event,
    )


def rejected(summary: str, event: str | None = None) -> tuple[ToolResult, str | None]:
    return (
        ToolResult(
            status=ToolStatus.REJECTED,
            reason=ToolReason.SCENARIO_ACTION_REJECTED,
            summary=summary,
        ),
        event,
    )


def _stable_hash(definition: dict[str, Any]) -> str:
    encoded = json.dumps(definition, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _ruleset_hash(environment_type: type[ScenarioEnvironment]) -> str:
    source = Path(environment_type.__module__.replace(".", "/") + ".py")
    package_root = Path(__file__).resolve().parents[3]
    candidate = package_root / source
    digest = sha256()
    for path in sorted({Path(__file__).resolve(), candidate.resolve()}):
        digest.update(path.name.encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(environment_type.__module__.encode("utf-8"))
    return digest.hexdigest()


__all__ = [
    "ScenarioActionResult",
    "ScenarioEnvironment",
    "ScenarioState",
    "applied",
    "rejected",
]
