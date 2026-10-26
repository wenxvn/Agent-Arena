"""V13 Lab 页面冒烟：稳定性与效度、报告与审计两页在 stub streamlit 下不崩溃。"""

from __future__ import annotations

import sys
import types
from decimal import Decimal
from pathlib import Path
from typing import Any

from test_web_ui_smoke import _Stub

from agent_arena.lab.contracts import (
    AgentArm,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
)
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER


def _render(monkeypatch: Any, tmp_path: Path, view: str, *, seed: bool = False) -> _Stub:
    from agent_arena.ui import app as ui_app

    monkeypatch.setattr(ui_app, "WEB_RUNS_DIR", tmp_path / "web")
    monkeypatch.setattr(ui_app, "LAB_RUNS_DIR", tmp_path / "lab")
    ui_app.reset_service()
    if seed:
        _prepare_experiment(tmp_path)
        ui_app.reset_service()
    stub = _Stub()
    stub.session_state["nav"] = view
    module = types.ModuleType("streamlit")
    for name in dir(stub):
        if not name.startswith("_"):
            setattr(module, name, getattr(stub, name))
    monkeypatch.setitem(sys.modules, "streamlit", module)
    try:
        ui_app.main()
    finally:
        sys.modules.pop("streamlit", None)
        ui_app.reset_service()
    return stub


def _text(stub: _Stub) -> str:
    return " ".join(str(value) for _, value in stub.calls)


def _prepare_experiment(tmp_path: Path) -> str:
    from agent_arena.lab.experiment import ExperimentService
    from agent_arena.web.service import RunService

    runs = RunService(tmp_path / "web", recover=False)
    lab = ExperimentService(tmp_path / "lab", run_service=runs, recover=False)
    try:
        spec = ExperimentSpec(
            name="v13-ui",
            maps=["MAP-22"],
            agent_arms=[AgentArm(agent_id="basic.v1"), AgentArm(agent_id="memory.v2")],
            environment_seeds=[0],
            provider_id=SIMULATED_PROVIDER,
            model=SIMULATED_MODEL,
            mode=ExperimentMode.SIMULATED,
            replicates=2,
            budget=ExperimentBudget(
                per_run_request_cap=20,
                per_run_decision_cap=4,
                experiment_request_cap=200,
                experiment_cost_cap_cny=Decimal("1"),
            ),
        )
        experiment_id = lab.create_experiment(spec)
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=300)
        return experiment_id
    finally:
        runs.shutdown()


def test_stability_page_renders_historical_analysis(monkeypatch: Any, tmp_path: Path) -> None:
    stub = _render(monkeypatch, tmp_path, "Lab · 稳定性与效度")
    text = _text(stub)
    assert "稳定性与效度" in text
    assert "重复 ≠ 新 seed" in text
    assert "六图效度" in text
    assert "翻转率" in text


def test_stability_page_uses_runtime_records(monkeypatch: Any, tmp_path: Path) -> None:
    stub = _render(monkeypatch, tmp_path, "Lab · 稳定性与效度", seed=True)
    text = _text(stub)
    assert "当前实验" in text
    assert "可比分组" in text
    assert "能力画像" in text


def test_audit_page_renders_report_and_ledger(monkeypatch: Any, tmp_path: Path) -> None:
    stub = _render(monkeypatch, tmp_path, "Lab · 报告与审计")
    text = _text(stub)
    assert "报告与审计" in text
    assert "账本审计" in text
    assert "SDK 自检" in text
    assert "NO_EXTERNAL_BILL_PROVIDED" in text or "RECONCILED" in text


def test_audit_page_with_experiment(monkeypatch: Any, tmp_path: Path) -> None:
    stub = _render(monkeypatch, tmp_path, "Lab · 报告与审计", seed=True)
    text = _text(stub)
    assert "experiment_id" in text
    assert not [value for name, value in stub.calls if name == "error"]


def test_bill_rows_parser_keeps_only_public_columns() -> None:
    from agent_arena.ui.lab import read_bill_csv_rows

    rows = read_bill_csv_rows("run_id,amount,currency\nweb-1,0.0123,CNY\n,1,CNY\n")
    assert len(rows) == 1
    assert rows[0]["run_id"] == "web-1"
    assert rows[0]["event"] == "run_settled"
