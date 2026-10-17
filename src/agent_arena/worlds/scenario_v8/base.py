"""Lifecycle, tick accounting and hash helpers for the isolated V8 maps.

Every map keeps its own state machine in its own module. This base class only
shares the parts the outline explicitly allows to be shared: strict action
shape acceptance, one logical clock, terminal handling, deterministic replay,
and the public/judge boundary.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from hashlib import sha256
from typing import Any

from agent_arena.worlds.scenario_v8.models import (
    V8Action,
    V8Observation,
    V8Status,
    V8StepResult,
)

Shape = frozenset[str]


class MapEnvironment(ABC):
    """One V8 map with explicit public and judge state boundaries."""

    map_id: str = ""
    title: str = ""
    world: str = ""
    level: str = ""
    #: Per-tool allowlist of exact action field sets.
    SHAPES: dict[str, set[Shape]] = {}
    #: Public fields the map may publish; used by the leakage tests.
    PUBLIC_FIELDS: frozenset[str] = frozenset()

    def __init__(
        self,
        *,
        seed: int = 0,
        step_limit: int = 120,
        condition_id: str = "default",
    ) -> None:
        self.seed = seed
        self.step_limit = step_limit
        self.condition_id = condition_id
        self.source_hash = ""
        self.status = V8Status.RUNNING
        self.terminal_reason: str | None = None
        self.tick_count = 0
        self.last_result = "READY"
        self.node = ""
        self.items: list[str] = []
        self.counters: dict[str, int] = {}
        self.violations: dict[str, int] = {}
        self.reset(seed)

    # ------------------------------------------------------------------ lifecycle
    def reset(self, seed: int) -> dict[str, Any]:
        self.seed = seed
        self.status = V8Status.RUNNING
        self.terminal_reason = None
        self.tick_count = 0
        self.last_result = "READY"
        self.node = ""
        self.items = []
        self.counters = {}
        self.violations = {}
        self._reset_state(seed)
        return self.observe()

    def observe(self) -> dict[str, Any]:
        return self._observation()

    def step(self, action: V8Action) -> V8StepResult:
        if self.status is not V8Status.RUNNING:
            return self._result("ALREADY_TERMINAL")
        if not self.accepts(action):
            return self.reject_invalid_action()
        result = self._apply(action)
        self.last_result = result
        self.tick_count += self._action_cost(action)
        self._after_tick()
        self._check_limits()
        return self._result(result)

    def reject_invalid_action(self) -> V8StepResult:
        if self.status is not V8Status.RUNNING:
            return self._result("ALREADY_TERMINAL")
        self.last_result = self._invalid_action()
        self.tick_count += 1
        self._after_tick()
        self._check_limits()
        return self._result(self.last_result)

    def accepts(self, action: V8Action) -> bool:
        shapes = self.SHAPES.get(action.tool)
        if not shapes:
            return False
        return frozenset(action.model_fields_set) in shapes

    def _check_limits(self) -> None:
        if self.status is V8Status.RUNNING and self.tick_count >= self.step_limit:
            self.status = V8Status.CENSORED
            self.terminal_reason = "ACTION_LIMIT_REACHED"

    def _result(self, result: str) -> V8StepResult:
        return V8StepResult(
            result=result,
            status=self.status,
            observation=self.observe(),
        )

    # ------------------------------------------------------------------ helpers
    @property
    def is_success(self) -> bool:
        return self.status is V8Status.SUCCESS

    @property
    def is_terminal(self) -> bool:
        return self.status is not V8Status.RUNNING

    def _succeed(self, reason: str) -> None:
        self.status = V8Status.SUCCESS
        self.terminal_reason = reason

    def _fail(self, reason: str) -> None:
        if self.status is V8Status.RUNNING:
            self.status = V8Status.FAILURE
            self.terminal_reason = reason

    def _violate(self, key: str, amount: int = 1) -> None:
        self.violations[key] = self.violations.get(key, 0) + amount

    def _count(self, key: str, amount: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + amount

    def has(self, item: str) -> bool:
        return item in self.items

    def take(self, item: str) -> bool:
        if item in self.items:
            return False
        self.items.append(item)
        return True

    def drop(self, item: str) -> bool:
        if item not in self.items:
            return False
        self.items.remove(item)
        return True

    # Edges are declared per map as ``EDGES[edge_id] = (a, b)``.
    EDGES: dict[str, tuple[str, str]] = {}
    EDGE_COST: dict[str, int] = {}

    def move_edge(self, edge_id: str) -> tuple[str | None, str]:
        """Move along one declared edge; return ``(new_node, result)``."""

        edge = self.EDGES.get(edge_id)
        if edge is None or self.node not in edge:
            return None, "EDGE_NOT_ADJACENT"
        destination = edge[1] if edge[0] == self.node else edge[0]
        self.node = destination
        return destination, f"MOVED:{destination}"

    def edge_destination(self, edge_id: str) -> str | None:
        edge = self.EDGES.get(edge_id)
        if edge is None or self.node not in edge:
            return None
        return edge[1] if edge[0] == self.node else edge[0]

    def visible_edges(self) -> list[str]:
        return [
            edge_id
            for edge_id, (a, b) in sorted(self.EDGES.items())
            if a == self.node or b == self.node
        ]

    # ------------------------------------------------------------------ contract
    @abstractmethod
    def _reset_state(self, seed: int) -> None: ...

    @abstractmethod
    def _public(self) -> dict[str, Any]: ...

    @abstractmethod
    def _apply(self, action: V8Action) -> str: ...

    def _after_tick(self) -> None:  # noqa: B027 - optional hook, not abstract
        """Automatic per-tick effects (clocks, drains, settlements)."""

    def _action_cost(self, action: V8Action) -> int:
        return 1

    def _invalid_action(self) -> str:
        return "INVALID_ACTION_SCHEMA"

    def _observation(self) -> dict[str, Any]:
        fields = self._public()
        core = {"map_id", "terminal", "terminal_reason", "last_action_result"}
        collision = core & set(fields)
        if collision:  # pragma: no cover - programming error guard
            raise AssertionError(f"Map public fields shadow the core contract: {collision}")
        observation = V8Observation(
            map_id=self.map_id,
            terminal=self.is_terminal,
            terminal_reason=self.terminal_reason,
            last_action_result=self.last_result,
            **fields,
        )
        return observation.as_public_dict()

    @abstractmethod
    def judge_state(self) -> dict[str, Any]:
        """Private state for offline validation and isolated judge metrics."""

    def metrics(self) -> dict[str, Any]:
        """Map-specific judge metrics keyed by the registered metric id."""
        return {}

    def state_hash(self) -> str:
        payload = json.dumps(
            {
                "map_id": self.map_id,
                "condition_id": self.condition_id,
                "source_hash": self.source_hash,
                "judge_state": self.judge_state(),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["MapEnvironment", "Shape"]
