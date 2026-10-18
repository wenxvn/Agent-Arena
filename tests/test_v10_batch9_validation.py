"""Batch 9：8 项验收 Gate 的逻辑测试（用合成产物，不依赖 runs/）。"""

from __future__ import annotations

from typing import Any

import pytest

from agent_arena.v10 import validation
from agent_arena.v10.runtime.catalog import MAP_IDS


def _oracle_row(success: bool = True, primary: float = 1.0) -> dict[str, Any]:
    return {
        "success": success,
        "decisions": 5,
        "mechanism_triggered": True,
        "primary_state": "VALID",
        "primary_value": primary,
    }


def _payload(
    *,
    oracle_primary: float = 1.0,
    ablation_success: bool = True,
    ablation_primary: float = 0.5,
) -> dict[str, Any]:
    return {
        "oracle": [_oracle_row(primary=oracle_primary) for _ in range(3)],
        "ablations": {
            "ablation": [
                {
                    "success": ablation_success,
                    "primary_state": "VALID",
                    "primary_value": ablation_primary,
                }
                for _ in range(3)
            ]
        },
    }


def _mimo(ratio_invalid: float, runs: int = 3) -> dict[str, list[dict[str, Any]]]:
    return {
        "MAP-08": [
            {
                "decision_count": 10,
                "invalid_actions": int(ratio_invalid * 10),
                "success": False,
            }
            for _ in range(runs)
        ]
    }


@pytest.fixture()
def patched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validation, "seed_effective", lambda _map: True)
    monkeypatch.setattr(validation, "seed_space", lambda _map: (0, 1, 2))
    monkeypatch.setattr(
        validation,
        "_independent",
        lambda: {
            "MAP-08": {"violations": [], "all_deterministic": True, "seed_distinct": True}
        },
    )


def test_ablation_gate_passes_when_success_drops(
    monkeypatch: pytest.MonkeyPatch, patched: None
) -> None:
    monkeypatch.setattr(
        validation, "_baseline", lambda _map: _payload(ablation_success=False)
    )
    gate = validation.evaluate_map("MAP-08", validation._independent(), _mimo(0.0))
    assert gate.passed["ablation"] is True


def test_ablation_gate_passes_when_quality_drops_only(
    monkeypatch: pytest.MonkeyPatch, patched: None
) -> None:
    monkeypatch.setattr(
        validation,
        "_baseline",
        lambda _map: _payload(ablation_success=True, ablation_primary=0.2),
    )
    gate = validation.evaluate_map("MAP-08", validation._independent(), _mimo(0.0))
    assert gate.passed["ablation"] is True
    assert "质量区分消融" in gate.details["ablation"]


def test_ablation_gate_fails_without_any_separation(
    monkeypatch: pytest.MonkeyPatch, patched: None
) -> None:
    monkeypatch.setattr(
        validation,
        "_baseline",
        lambda _map: _payload(ablation_success=True, ablation_primary=1.0),
    )
    gate = validation.evaluate_map("MAP-08", validation._independent(), _mimo(0.0))
    assert gate.passed["ablation"] is False
    assert gate.verdict == "NEEDS_MORE_EVIDENCE"


def test_mimo_gate_fails_on_systematic_invalid_actions(
    monkeypatch: pytest.MonkeyPatch, patched: None
) -> None:
    monkeypatch.setattr(validation, "_baseline", lambda _map: _payload())
    gate = validation.evaluate_map("MAP-08", validation._independent(), _mimo(1.0))
    assert gate.passed["mimo"] is False
    assert any("mimo" in reason for reason in gate.reasons)


def test_mimo_gate_passes_below_invalid_ratio(
    monkeypatch: pytest.MonkeyPatch, patched: None
) -> None:
    monkeypatch.setattr(validation, "_baseline", lambda _map: _payload())
    gate = validation.evaluate_map("MAP-08", validation._independent(), _mimo(0.4))
    assert gate.passed["mimo"] is True


def test_fallback_maps_keep_v8_validated() -> None:
    gate = validation.evaluate_map("MAP-01", {}, {})
    assert gate.native is False
    assert gate.verdict == "VALIDATED_V8_FALLBACK"
    assert "3-seed 缺口" in gate.reasons[0]


def test_evaluate_covers_all_maps() -> None:
    gates = validation.evaluate()
    assert set(gates) == set(MAP_IDS)
    for gate in gates.values():
        assert gate.verdict in {
            "VALIDATED",
            "VALIDATED_V8_FALLBACK",
            "NEEDS_MORE_EVIDENCE",
        }
