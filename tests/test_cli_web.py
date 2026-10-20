"""V11 CLI `agent-arena web` 的安全边界。"""

from __future__ import annotations

from typer.testing import CliRunner

from agent_arena.cli import app

runner = CliRunner()


def test_web_rejects_non_loopback_host() -> None:
    result = runner.invoke(app, ["web", "--host", "0.0.0.0"])
    assert result.exit_code == 2
    assert "回环地址" in result.output


def test_web_help_lists_options() -> None:
    result = runner.invoke(app, ["web", "--help"])
    assert result.exit_code == 0
    assert "--check" in result.output
    assert "--port" in result.output
