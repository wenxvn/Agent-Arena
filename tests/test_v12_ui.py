"""V12 Lab 页面冒烟：配置 / 监控 / 结果三页在 stub streamlit 下不崩溃。"""

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


def _render(monkeypatch: Any, tmp_path: Path, view: str) -> _Stub:
    from agent_arena.ui import app as ui_app

    monkeypatch.setattr(ui_app, "WEB_RUNS_DIR", tmp_path / "web")
    monkeypatch.setattr(ui_app, "LAB_RUNS_DIR", tmp_path / "lab")
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


def test_lab_config_page_renders_matrix_and_preflight(monkeypatch: Any, tmp_path: Path) -> None:
    stub = _render(monkeypatch, tmp_path, "Lab · 实验配置")
    text = _text(stub)
    assert "配置一组架构对照实验" in text
    assert "预检" in text
    assert "矩阵" in text
    assert "子局" in text


def test_lab_monitor_page_shows_empty_state(monkeypatch: Any, tmp_path: Path) -> None:
    stub = _render(monkeypatch, tmp_path, "Lab · 实验监控")
    text = _text(stub)
    assert "还没有实验" in text


def test_lab_result_page_shows_empty_state(monkeypatch: Any, tmp_path: Path) -> None:
    stub = _render(monkeypatch, tmp_path, "Lab · 结果与对照")
    text = _text(stub)
    assert "还没有结果" in text


def _prepare_experiment(tmp_path: Path) -> str:
    from agent_arena.lab.experiment import ExperimentService
    from agent_arena.web.service import RunService

    runs = RunService(tmp_path / "web", recover=False)
    lab = ExperimentService(tmp_path / "lab", run_service=runs, recover=False)
    try:
        spec = ExperimentSpec(
            name="ui-smoke",
            maps=["MAP-22"],
            agent_arms=[AgentArm(agent_id="basic.v1"), AgentArm(agent_id="memory.v1")],
            environment_seeds=[0],
            provider_id=SIMULATED_PROVIDER,
            model=SIMULATED_MODEL,
            mode=ExperimentMode.SIMULATED,
            budget=ExperimentBudget(
                per_run_request_cap=40,
                per_run_decision_cap=4,
                experiment_request_cap=400,
                experiment_cost_cap_cny=Decimal("5"),
            ),
        )
        experiment_id = lab.create_experiment(spec)
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=300)
        return experiment_id
    finally:
        runs.shutdown()


def test_lab_monitor_renders_children(monkeypatch: Any, tmp_path: Path) -> None:
    experiment_id = _prepare_experiment(tmp_path)
    stub = _render(monkeypatch, tmp_path, "Lab · 实验监控")
    text = _text(stub)
    assert "COMPLETED" in text
    assert "basic.v1" in text or "memory.v1" in text
    assert experiment_id in text


def test_lab_result_renders_summary_and_tabs(monkeypatch: Any, tmp_path: Path) -> None:
    _prepare_experiment(tmp_path)
    stub = _render(monkeypatch, tmp_path, "Lab · 结果与对照")
    text = _text(stub)
    assert "实验臂汇总" in text
    assert "SIMULATED" in text
    assert "有效分母" in text
    assert any(name == "tabs" for name, _ in stub.calls)


def test_lab_views_are_in_navigation() -> None:
    from agent_arena.ui import app as ui_app

    for view in ("Lab · 实验配置", "Lab · 实验监控", "Lab · 结果与对照"):
        assert view in ui_app.VIEWS


def test_live_mode_requires_explicit_approval_text(monkeypatch: Any, tmp_path: Path) -> None:
    """真实通道必须给出“先批准再提交”的显式提示。"""

    from agent_arena.ui import lab as lab_ui

    stub = _Stub()

    def fake_selectbox(label: str, options: list[Any], index: int = 0, **kwargs: Any) -> Any:
        del kwargs
        if label == "执行通道":
            return lab_ui.PROVIDER_LABELS["openai_compatible"]
        return options[index] if options else ""

    stub.selectbox = fake_selectbox  # type: ignore[method-assign]
    spec = lab_ui._build_spec(stub, allow_live=False)
    text = _text(stub)
    assert "预算批准" in text
    assert spec is not None
    assert spec.mode is ExperimentMode.LIVE
    assert spec.preflight_only is True
    assert spec.approval.approved is False
