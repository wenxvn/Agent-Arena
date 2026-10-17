from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_v7_pilot.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_v7_pilot", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v7_pilot_selection_is_registered_and_balanced() -> None:
    module = _load_module()
    specs = module._selected_specs()
    assert len(specs) == 12
    assert len({spec.episode_id for spec in specs}) == 12
    assert sorted({spec.map_id for spec in specs}) == [
        "MAP-08",
        "MAP-16",
        "MAP-18",
        "MAP-22",
        "MAP-26",
        "MAP-30",
    ]
    counts: dict[str, int] = {}
    for spec in specs:
        counts[spec.map_id] = counts.get(spec.map_id, 0) + 1
    assert set(counts.values()) == {2}


def test_v7_pilot_registration_exists_before_paid_run() -> None:
    module = _load_module()
    text = module.REGISTRATION_PATH.read_text(encoding="utf-8")
    assert "预登记" in text
    assert "CNY 2.00" in text
    assert "12 局" in text
    assert "停止条件" in text
    assert module.OPERATIONAL_COST_CAP < module.PRICE_SHEETS["CNY"].max_cost
