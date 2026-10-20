"""V11 一键自检的快速子集（全量 30 图矩阵在手工验收/CI 中单独运行）。"""

from __future__ import annotations

from agent_arena.web.selfcheck import (
    check_budget,
    check_catalog,
    check_export_consistency,
    check_paths,
    check_redaction,
    check_service_recovery,
)


def test_catalog_check_reports_thirty_maps() -> None:
    detail = check_catalog()
    assert detail["maps"] == 30
    assert detail["worlds"] == 10
    assert detail["forbidden_hits"] == 0


def test_budget_check() -> None:
    assert check_budget() == {"request_cap": True, "unknown_usage": True, "cost_cap": True}


def test_redaction_and_path_checks() -> None:
    assert check_redaction()["secret_echo"] is False
    assert check_paths()["traversal"] is False


def test_export_consistency_check() -> None:
    assert check_export_consistency()["rows"] == 4


def test_recovery_check() -> None:
    assert check_service_recovery()["recovered"] is True
