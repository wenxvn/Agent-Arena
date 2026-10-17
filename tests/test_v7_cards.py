"""Structural self-review checks for the 30 V7 design cards."""

from __future__ import annotations

import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_v7_cards.py"


def test_card_audit_has_no_structural_findings() -> None:
    namespace = runpy.run_path(str(SCRIPT))
    result = namespace["audit"]()
    assert result["cards"] == 30
    assert result["metrics"] == 154
    assert result["findings"] == []
    assert result["max_specific_construct_similarity"] <= 0.8
