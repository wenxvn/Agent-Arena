"""Baseline agent policy that requests one structured action at a time."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from agent_arena.arena import Action, Observation
from agent_arena.llm import DecisionProvider
from agent_arena.llm.protocol import DecisionRequest, ProviderResponse


class AgentDecision(BaseModel):
    """The allowlisted portion of a provider response used by the runner."""

    model_config = ConfigDict(extra="forbid", strict=True)

    decision_reason: Annotated[str, Field(min_length=1, max_length=280)]
    action: Action


agent_decision_adapter: TypeAdapter[AgentDecision] = TypeAdapter(AgentDecision)


class ReactAgent:
    """Request candidate decisions without accessing environment internals."""

    name = "react"
    prompt_version = "react_v3"

    def __init__(self, provider: DecisionProvider, prompt_path: Path | None = None) -> None:
        self._provider = provider
        path = prompt_path or self._default_prompt_path()
        self._prompt = path.read_text(encoding="utf-8")

    def request(self, observation: Observation, *, correction: bool) -> ProviderResponse:
        """Return the provider candidate for the current public observation."""

        return self._provider.decide(
            DecisionRequest(
                observation=observation, system_prompt=self._prompt, correction=correction
            )
        )

    def reset(self, observation: Observation) -> None:
        del observation

    def observe(self, action: Action, result: object, observation: Observation) -> None:
        del action, result, observation

    def finish(self, outcome: object) -> None:
        del outcome

    @property
    def base_prompt_hash(self) -> str:
        return sha256(self._prompt.encode("utf-8")).hexdigest()

    def _default_prompt_path(self) -> Path:
        return Path(__file__).resolve().parents[3] / "prompts" / f"{self.prompt_version}.txt"
