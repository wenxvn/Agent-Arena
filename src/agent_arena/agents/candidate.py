"""Model policy for selecting from public, deterministic Action candidates."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from agent_arena.agents.react import ReactAgent
from agent_arena.arena import Observation
from agent_arena.llm.protocol import DecisionProvider, DecisionRequest, ProviderResponse


class CandidateSelectionDecision(BaseModel):
    """Allowlisted model output before the runner resolves a public Action."""

    model_config = ConfigDict(extra="forbid", strict=True)

    decision_reason: Annotated[str, Field(min_length=1, max_length=280)]
    candidate_id: Annotated[str, Field(pattern=r"^a[1-9][0-9]*$")]


candidate_selection_adapter: TypeAdapter[CandidateSelectionDecision] = TypeAdapter(
    CandidateSelectionDecision
)


class CandidateSelectionAgent(ReactAgent):
    """Choose one runner-provided public candidate without receiving a route."""

    name = "candidate_select"
    prompt_version = "candidate_select_v1"
    base_prompt_version = "react_v12_autonomous"

    def __init__(self, provider: DecisionProvider, prompt_path: Path | None = None) -> None:
        super().__init__(provider, prompt_path or self._default_prompt_path())

    def request(
        self,
        observation: Observation,
        *,
        correction: bool,
        runtime_feedback: str | None = None,
        invalid_output_reason: str | None = None,
        recent_history: str | None = None,
    ) -> ProviderResponse:
        return self._provider.decide(
            DecisionRequest(
                observation=observation,
                system_prompt=self._prompt,
                correction=correction,
                runtime_feedback=runtime_feedback,
                invalid_output_reason=invalid_output_reason,
                recent_history=recent_history,
                output_contract="candidate_selection",
            )
        )

    @property
    def base_prompt_hash(self) -> str:
        return sha256(self._prompt.encode("utf-8")).hexdigest()

    @staticmethod
    def _default_prompt_path() -> Path:
        return Path(__file__).resolve().parents[3] / "prompts" / "candidate_select_v1.txt"
