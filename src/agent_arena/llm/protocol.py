"""Provider boundary shared by the future Agent Loop and test doubles."""

from __future__ import annotations

from typing import Protocol


class DecisionProvider(Protocol):
    """Return a candidate decision without knowing Environment internals."""

    def decide(self, observation: object, prompt: str, correction: bool) -> object:
        """Return a response candidate for the supplied public observation."""
