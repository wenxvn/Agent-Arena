"""Keep the developer's local `.env` out of the deterministic test suite."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from agent_arena.config import RuntimeSettings


@pytest.fixture(autouse=True)
def _isolate_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Delete ambient provider credentials so CLI tests use Fake defaults."""

    for name in list(os.environ):
        if name.startswith(("AGENT_ARENA_", "OPENAI_", "OLLAMA_", "DASHSCOPE_")):
            monkeypatch.delenv(name, raising=False)
    original_load = RuntimeSettings.load.__func__

    def _load_without_local_dotenv(
        cls: type[RuntimeSettings],
        cli_overrides: dict[str, Any] | None = None,
        *,
        env_file: Path | None = None,
    ) -> RuntimeSettings:
        return original_load(cls, cli_overrides, env_file=env_file)

    monkeypatch.setattr(RuntimeSettings, "load", classmethod(_load_without_local_dotenv))
