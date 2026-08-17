"""Allowlisted, redacted episode traces and atomic persistence."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from agent_arena.arena import Action, Observation, ToolResult


class EpisodeOutcome(StrEnum):
    """Terminal results produced by the bounded episode runner."""

    SUCCESS = "success"
    STEP_LIMIT = "step_limit"
    INVALID_ACTION_LIMIT = "invalid_action_limit"
    PROVIDER_ERROR = "provider_error"


class TraceEvent(StrEnum):
    """Events that can be safely persisted without raw provider content."""

    ACTION_VALIDATED = "action_validated"
    ACTION_REJECTED = "action_rejected"
    ACTION_INVALID = "action_invalid"
    CORRECTION_REQUESTED = "correction_requested"
    PROVIDER_ERROR = "provider_error"


class StepTrace(BaseModel):
    """One allowlisted decision or execution event."""

    model_config = ConfigDict(frozen=True)

    event: TraceEvent
    observation: Observation
    correction: bool = False
    decision_reason: str | None = Field(default=None, max_length=280)
    action: Action | None = None
    result: ToolResult | None = None
    latency_ms: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    summary: str | None = Field(default=None, max_length=1_000)


class EpisodeTraceHeader(BaseModel):
    """Stable episode identity supplied before a terminal outcome exists."""

    model_config = ConfigDict(frozen=True)

    episode_id: UUID
    created_at: datetime
    world_version: str
    seed: int
    agent: str
    prompt_version: str
    provider: str


class EpisodeTrace(BaseModel):
    """A complete persisted record of one terminal episode."""

    model_config = ConfigDict(frozen=True)

    episode_id: UUID
    created_at: datetime
    world_version: str
    seed: int
    agent: str
    prompt_version: str
    provider: str
    outcome: EpisodeOutcome
    executed_action_count: int = Field(ge=0)
    invalid_output_count: int = Field(ge=0)
    rejected_action_count: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    steps: tuple[StepTrace, ...]

    @classmethod
    def start(
        cls,
        *,
        world_version: str,
        seed: int,
        agent: str,
        prompt_version: str,
        provider: str,
    ) -> EpisodeTraceHeader:
        """Return stable header values for the runner while outcome is unknown."""

        return EpisodeTraceHeader(
            episode_id=uuid4(),
            created_at=datetime.now(UTC),
            world_version=world_version,
            seed=seed,
            agent=agent,
            prompt_version=prompt_version,
            provider=provider,
        )


_SENSITIVE_VALUE = re.compile(
    r"(?i)\b((?:[a-z0-9]+_)*(?:api[_-]?key|authorization|token|secret|password))\b"
    r"\s*[:=]\s*[^\s,;]+"
)


def write_episode_trace(trace: EpisodeTrace, output_dir: Path) -> Path:
    """Write a redacted JSON trace through a sibling temporary file."""

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{trace.episode_id}.json"
    temporary_path: Path | None = None
    serialized = _redact_value(trace.model_dump(mode="json"))
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_dir,
            prefix=f".{trace.episode_id}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(serialized, temporary_file, ensure_ascii=True, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        raise
    return destination


def _redact_value(value: object) -> object:
    if isinstance(value, str):
        return _SENSITIVE_VALUE.sub(r"\1=[REDACTED]", value)[:1_000]
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    return value
