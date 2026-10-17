"""V7 must remain a read-only metric layer with no credential-shaped docs."""

from __future__ import annotations

import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_v7_leakage.py"


def test_v7_leakage_scan_is_clean() -> None:
    namespace = runpy.run_path(str(SCRIPT))
    findings = namespace["scan"]()
    assert findings == []


def test_v7_leakage_scan_detects_a_forbidden_import(tmp_path: Path) -> None:
    namespace = runpy.run_path(str(SCRIPT))
    fake_source = tmp_path / "src" / "agent_arena" / "v7"
    fake_source.mkdir(parents=True)
    (fake_source / "bad.py").write_text("import agent_arena.v6.runner\n", encoding="utf-8")
    findings = namespace["scan_source"](fake_source)
    assert any("forbidden import agent_arena.v6.runner" in finding for finding in findings)
