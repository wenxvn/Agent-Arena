"""V11 CLI `agent-arena web` 的安全边界与 --check 行为。"""

from __future__ import annotations

import re

from typer.testing import CliRunner

from agent_arena.cli import app

runner = CliRunner()


def test_web_rejects_non_loopback_host() -> None:
    result = runner.invoke(app, ["web", "--host", "0.0.0.0"])
    assert result.exit_code == 2
    assert "回环地址" in result.output


def test_web_help_exits_zero() -> None:
    result = runner.invoke(app, ["web", "--help"])
    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "web" in plain.lower()


def test_web_check_runs_selfcheck(monkeypatch) -> None:
    from agent_arena.web import selfcheck

    monkeypatch.setattr(
        selfcheck,
        "run_checks",
        lambda **kwargs: {"ok": True, "failed": 0, "head": "test", "checks": []},
    )
    result = runner.invoke(app, ["web", "--check"])
    assert result.exit_code == 0
    assert '"ok": true' in result.output
