"""V9 独立指标复算的回归测试。"""

from __future__ import annotations

from agent_arena.v9.metric_checks import registry
from agent_arena.v9.metric_checks.base import run_all


def test_all_independent_metric_checks_match() -> None:
    summary = run_all()
    assert summary["maps"] == 30
    assert summary["checks"] == 120
    assert summary["matched"] == 120
    assert summary["mismatched"] == 0
    assert summary["not_computable"] == 0


def test_registry_covers_every_map_and_two_checks() -> None:
    checks = registry()
    assert set(checks) == {f"MAP-{index:02d}" for index in range(1, 31)}
    for map_id, items in checks.items():
        assert len(items) >= 2, map_id
        kinds = {item.kind for item in items}
        assert "primary" in kinds, map_id
