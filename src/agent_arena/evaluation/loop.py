"""Public-trajectory loop signals for the bounded episode runner."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from agent_arena.arena import Action, Observation, ToolResult

PublicState = tuple[str, tuple[str, ...], tuple[str, ...]]
PublicOutcome = tuple[PublicState, str, str, str]


@dataclass
class PublicLoopDetector:
    """Detect repeated public behavior without reading hidden environment state."""

    _seen_states: set[PublicState] = field(default_factory=set)
    _seen_rooms: set[str] = field(default_factory=set)
    _seen_outcomes: set[PublicOutcome] = field(default_factory=set)
    _recovery_mode: bool = False

    def initialize(self, observation: Observation) -> None:
        """Start a trajectory using only the reset Observation."""

        self._remember_state(observation)

    def observe(
        self,
        before: Observation,
        action: Action,
        result: ToolResult,
        after: Observation,
    ) -> str | None:
        """Return a public recovery hint for the next request, when needed."""

        before_state = _state_key(before)
        after_state = _state_key(after)
        outcome = (
            before_state,
            _action_key(action),
            result.status.value,
            result.reason.value,
        )
        new_outcome = outcome not in self._seen_outcomes
        new_state = after_state not in self._seen_states
        self._seen_outcomes.add(outcome)
        self._remember_state(after)

        if new_state:
            self._recovery_mode = False
        elif not new_outcome:
            self._recovery_mode = True

        return self._feedback(after) if self._recovery_mode else None

    def _remember_state(self, observation: Observation) -> None:
        self._seen_states.add(_state_key(observation))
        self._seen_rooms.add(observation.current_room)

    def _feedback(self, observation: Observation) -> str:
        unexplored = [
            destination
            for destination in observation.available_exits
            if destination not in self._seen_rooms
        ]
        message = "你重复了同一公开状态下已完成的动作；不要再次执行它。"
        if unexplored:
            return f"{message} 当前可达但尚未访问的出口：{', '.join(unexplored)}。"
        return f"{message} 请使用当前可见对象或出口选择不同的推进动作。"


def _state_key(observation: Observation) -> PublicState:
    return (
        observation.current_room,
        observation.visible_objects,
        observation.inventory,
    )


def _action_key(action: Action) -> str:
    return json.dumps(
        action.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
