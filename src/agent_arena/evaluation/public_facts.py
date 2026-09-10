"""Public, episode-local facts extracted from observations and tool results."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from agent_arena.arena import Action, Observation, ToolReason, ToolResult


class PublicFact(BaseModel):
    """A bounded fact that can be proven from public episode evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    subject: str = Field(min_length=1, max_length=120)
    predicate: str = Field(min_length=1, max_length=80)
    value: str | None = Field(default=None, max_length=120)

    def canonical_key(self) -> tuple[str, str, str | None]:
        """Return the stable key used for episode-local de-duplication."""

        return self.subject, self.predicate, self.value


class EpisodeKnowledge(BaseModel):
    """Facts discovered during one episode, never shared with another episode."""

    model_config = ConfigDict(extra="forbid", strict=True)

    discovered_facts: tuple[PublicFact, ...] = ()

    def contains(self, fact: PublicFact) -> bool:
        return any(item.canonical_key() == fact.canonical_key() for item in self.discovered_facts)

    def add(self, facts: Iterable[PublicFact]) -> EpisodeKnowledge:
        values = list(self.discovered_facts)
        known = {fact.canonical_key() for fact in values}
        for fact in facts:
            if fact.canonical_key() not in known:
                values.append(fact)
                known.add(fact.canonical_key())
        return EpisodeKnowledge(discovered_facts=tuple(values))


# These reasons communicate a condition or an outcome that may remain useful
# after the observation's persistent fields return to the same values. Generic
# actions such as ``look`` and ``move`` are intentionally not facts: their state
# change is already measured by State Progress.
_FACT_REASONS = frozenset(
    {
        ToolReason.PANEL_OPENED,
        ToolReason.POWER_RESTORED,
        ToolReason.DIAGNOSTIC_READ,
        ToolReason.CODE_READ,
        ToolReason.ESCAPED,
        ToolReason.ALREADY_COMPLETED,
        ToolReason.NOT_ADJACENT,
        ToolReason.NOT_VISIBLE,
        ToolReason.NOT_REVEALED,
        ToolReason.NOT_PRESENT,
        ToolReason.ALREADY_COLLECTED,
        ToolReason.MISSING_ITEM,
        ToolReason.WRONG_TARGET,
        ToolReason.READ_TERMINAL_REQUIRED,
        ToolReason.PANEL_CLOSED,
        ToolReason.CODE_UNREAD,
        ToolReason.INCORRECT_CODE,
        ToolReason.NO_POWER,
    }
)


def extract_public_facts(
    observation: Observation,
    action: Action | None,
    result: ToolResult | None,
) -> tuple[PublicFact, ...]:
    """Extract allowlisted facts without parsing free-form result text.

    The result reason is a structured public field. The action target provides
    the subject when one exists; otherwise the current observed room is used.
    No WorldState or environment-specific hidden field is consulted.
    """

    if result is None or result.reason not in _FACT_REASONS:
        return ()
    subject = _action_subject(action) or observation.current_room
    return (
        PublicFact(subject=subject, predicate="result", value=result.reason.value),
    )


def _action_subject(action: Action | None) -> str | None:
    if action is None:
        return None
    data = action.model_dump(mode="python")
    if action.tool in {"inspect", "read_terminal", "use"}:
        value = data.get("target")
    elif action.tool in {"pickup"}:
        value = data.get("item")
    elif action.tool == "move":
        value = data.get("destination")
    else:
        value = None
    return value if isinstance(value, str) and value else None
