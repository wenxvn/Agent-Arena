"""Lifecycle and hash helpers isolated from V3 and Legacy environments."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from hashlib import sha256
from typing import Any

from pydantic import BaseModel

from agent_arena.worlds.scenario_v4.models import ScenarioV4Action, V4Status


class V4StepResult(BaseModel):
    """Public result of one V4 action and its resulting observation."""

    result: str
    status: V4Status
    tick: int
    observation: BaseModel


class ScenarioV4Environment(ABC):
    """One isolated V4 map with explicit public and judge state boundaries."""

    map_id: str
    condition_id: str
    source_hash: str
    seed: int
    step_limit: int
    status: V4Status
    terminal_reason: str | None

    def reset(self, seed: int) -> BaseModel:
        self.seed = seed
        self.status = V4Status.RUNNING
        self.terminal_reason = None
        self.step_count = 0
        self._reset_state(seed)
        return self.observe()

    def observe(self) -> BaseModel:
        return self._observation()

    def step(self, action: ScenarioV4Action) -> V4StepResult:
        if self.status is not V4Status.RUNNING:
            return V4StepResult(
                result="ALREADY_TERMINAL",
                status=self.status,
                tick=self.tick,
                observation=self.observe(),
            )
        result = self._apply(action)
        self.step_count += 1
        if self.status is V4Status.RUNNING and self.step_count >= self.step_limit:
            self.status = V4Status.CENSORED
            self.terminal_reason = "ACTION_LIMIT_REACHED"
        return V4StepResult(
            result=result,
            status=self.status,
            tick=self.tick,
            observation=self.observe(),
        )

    def reject_invalid_action(self) -> V4StepResult:
        """Apply one model decision whose JSON did not satisfy the V4 Action schema."""
        if self.status is not V4Status.RUNNING:
            return V4StepResult(
                result="ALREADY_TERMINAL",
                status=self.status,
                tick=self.tick,
                observation=self.observe(),
            )
        result = self._invalid_action()
        self.step_count += 1
        if self.status is V4Status.RUNNING and self.step_count >= self.step_limit:
            self.status = V4Status.CENSORED
            self.terminal_reason = "ACTION_LIMIT_REACHED"
        return V4StepResult(
            result=result,
            status=self.status,
            tick=self.tick,
            observation=self.observe(),
        )

    @property
    @abstractmethod
    def tick(self) -> int:
        """Map-specific logical time."""

    @abstractmethod
    def _reset_state(self, seed: int) -> None: ...

    @abstractmethod
    def _observation(self) -> BaseModel: ...

    @abstractmethod
    def _apply(self, action: ScenarioV4Action) -> str: ...

    @abstractmethod
    def _invalid_action(self) -> str: ...

    @abstractmethod
    def judge_state(self) -> dict[str, Any]:
        """Return private state for offline validation and isolated judge metrics."""

    @abstractmethod
    def metrics(self) -> dict[str, Any]: ...

    def state_hash(self) -> str:
        payload = json.dumps(
            {
                "condition_id": getattr(self, "condition_id", None),
                "source_hash": getattr(self, "source_hash", None),
                "judge_state": self.judge_state(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    @property
    def is_success(self) -> bool:
        return self.status is V4Status.SUCCESS

    @property
    def is_terminal(self) -> bool:
        return self.status is not V4Status.RUNNING
