"""Temporary episode persistence used while the real runner is built."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from agent_arena.config import RuntimeSettings


class ScaffoldEpisode(BaseModel):
    """An allowlisted episode header without environment or model content."""

    episode_id: UUID
    created_at: datetime
    world_version: str
    seed: int
    agent: str
    provider: str
    outcome: Literal["scaffold_pending"]
    steps: list[object] = Field(default_factory=list)

    @classmethod
    def from_settings(cls, settings: RuntimeSettings) -> ScaffoldEpisode:
        return cls(
            episode_id=uuid4(),
            created_at=datetime.now(UTC),
            world_version=settings.world_version,
            seed=settings.seed,
            agent=settings.agent,
            provider=settings.provider,
            outcome="scaffold_pending",
        )


def write_scaffold_episode(episode: ScaffoldEpisode, output_dir: Path) -> Path:
    """Write one JSON file through a sibling temporary file and atomic rename."""

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{episode.episode_id}.json"
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_dir,
            prefix=f".{episode.episode_id}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(episode.model_dump(mode="json"), temporary_file, ensure_ascii=True, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        raise
    return destination
