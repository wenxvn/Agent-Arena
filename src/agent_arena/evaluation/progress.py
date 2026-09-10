"""Public State and Epistemic Progress detection."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, model_validator

from agent_arena.arena import Action, Observation, ToolResult
from agent_arena.evaluation.public_facts import EpisodeKnowledge, PublicFact, extract_public_facts


class PublicProgressState(BaseModel):
    """Persistent public state used for State Progress comparisons."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    current_room: str
    visible_objects: tuple[str, ...]
    available_exits: tuple[str, ...]
    inventory: tuple[str, ...]
    last_result_status: str | None = None
    last_result_reason: str | None = None


def public_progress_state(
    observation: Observation, result: ToolResult | None = None
) -> PublicProgressState:
    """Project only public observation/result fields."""

    public_result = result or observation.last_action_result
    return PublicProgressState(
        current_room=observation.current_room,
        visible_objects=tuple(observation.visible_objects),
        available_exits=tuple(observation.available_exits),
        inventory=tuple(observation.inventory),
        last_result_status=public_result.status.value if public_result else None,
        last_result_reason=public_result.reason.value if public_result else None,
    )


class ProgressEvent(BaseModel):
    """Evidence for one action's public progress."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    state_progress: bool = False
    epistemic_progress: bool = False
    new_facts: tuple[PublicFact, ...] = ()
    state_changes: tuple[str, ...] = ()
    progress: bool = False

    @model_validator(mode="after")
    def derive_progress(self) -> ProgressEvent:
        expected = self.state_progress or self.epistemic_progress
        if self.progress == expected:
            return self
        return self.model_copy(update={"progress": expected})


@dataclass
class ProgressDetector:
    """Track public facts and distinguish state from epistemic progress."""

    knowledge: EpisodeKnowledge

    def __init__(self) -> None:
        self.knowledge = EpisodeKnowledge()

    def reset(self, observation: Observation | None = None) -> None:
        """Start a fresh episode; the optional observation is not hidden state."""

        del observation
        self.knowledge = EpisodeKnowledge()

    def evaluate(
        self,
        before: Observation,
        action: Action,
        result: ToolResult,
        after: Observation,
    ) -> ProgressEvent:
        before_state = public_progress_state(before)
        after_state = public_progress_state(after, result)
        state_changes = tuple(
            field
            for field in ("current_room", "visible_objects", "available_exits", "inventory")
            if getattr(before_state, field) != getattr(after_state, field)
        )
        observed = extract_public_facts(after, action, result)
        new_facts = tuple(fact for fact in observed if not self.knowledge.contains(fact))
        self.knowledge = self.knowledge.add(observed)
        return ProgressEvent(
            state_progress=bool(state_changes),
            epistemic_progress=bool(new_facts),
            new_facts=new_facts,
            state_changes=state_changes,
            progress=bool(state_changes or new_facts),
        )
