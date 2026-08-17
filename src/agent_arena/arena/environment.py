"""Base interface for deterministic, partially observable environments."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent_arena.arena.models import Action, Observation, ToolResult


class Environment(ABC):
    """Executes validated actions while keeping world state private."""

    @abstractmethod
    def reset(self, seed: int = 0) -> Observation:
        """Restore the environment to its deterministic initial state."""

    @abstractmethod
    def observe(self) -> Observation:
        """Return the current allowlisted observation."""

    @abstractmethod
    def step(self, action: Action) -> tuple[ToolResult, Observation]:
        """Execute one validated action and return its result and observation."""

    @abstractmethod
    def is_success(self) -> bool:
        """Report whether the environment has reached its success condition."""
