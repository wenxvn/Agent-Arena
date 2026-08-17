from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from agent_arena.cli import app
from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import ModelVerificationError

runner = CliRunner()


def test_cli_exposes_foundation_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "run" in result.output
    assert "benchmark" in result.output
    assert "verify-model" in result.output


def test_run_writes_a_terminal_allowlisted_episode(monkeypatch, tmp_path: Path) -> None:
    defaults_file = tmp_path / "runtime.defaults.json"
    defaults_file.write_text(
        json.dumps(
            {
                "provider": "fake",
                "world": "spaceship-escape",
                "world_version": "spaceship-escape-v1",
                "agent": "react",
                "seed": 0,
                "runs_dir": str(tmp_path / "runs"),
                "results_dir": "results",
                "step_limit": 30,
                "request_timeout_seconds": 30,
                "retry_count": 2,
                "retry_backoff_seconds": [1, 2],
                "enable_thinking": False,
                "model_name": "qwen3.7-plus",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(RuntimeSettings, "defaults_file", defaults_file)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    trace_paths = list((tmp_path / "runs").glob("*.json"))
    assert len(trace_paths) == 1
    trace = json.loads(trace_paths[0].read_text(encoding="utf-8"))
    assert trace["outcome"] == "success"
    assert trace["executed_action_count"] == 20
    assert len(trace["steps"]) == 20
    assert "OPENAI_API_KEY" not in trace_paths[0].read_text(encoding="utf-8")


def test_verify_model_does_not_echo_provider_exception_content(monkeypatch) -> None:
    class FailingVerifier:
        def __init__(self, settings: RuntimeSettings) -> None:
            del settings

        def verify(self) -> None:
            raise ModelVerificationError("secret-like-response-body")

    monkeypatch.setattr("agent_arena.cli.BailianModelVerifier", FailingVerifier)

    result = runner.invoke(app, ["verify-model"])

    assert result.exit_code == 1
    assert "Model verification failed" in result.output
    assert "secret-like-response-body" not in result.output
