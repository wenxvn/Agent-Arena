"""V11 网页冒烟：用 stub streamlit 渲染各页面，验证不抛异常。"""

from __future__ import annotations

import sys
import types
from decimal import Decimal
from pathlib import Path
from typing import Any

from agent_arena.web.schemas import (
    OFFLINE_MODEL,
    OFFLINE_PROVIDER,
    RunConfig,
    RunMode,
)
from agent_arena.web.service import RunService


class _Ctx:
    def __enter__(self) -> _Ctx:
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def selectbox(self, label: str, options: list[Any], index: int = 0, **kwargs: Any) -> Any:
        del label, kwargs
        return options[index] if options else ""

    def text_input(self, label: str, value: str = "", **kwargs: Any) -> str:
        del label, kwargs
        return value

    def number_input(self, label: str, **kwargs: Any) -> Any:
        del label
        return kwargs.get("value", kwargs.get("min_value", 0))

    def checkbox(self, label: str, value: bool = False, **kwargs: Any) -> bool:
        del label, kwargs
        return value

    def button(self, label: str, **kwargs: Any) -> bool:
        del label, kwargs
        return False

    def __getattr__(self, name: str) -> Any:
        def noop(*args: Any, **kwargs: Any) -> _Ctx:
            del args, kwargs
            return _Ctx()

        return noop


class _Sidebar:
    def __init__(self, owner: _Stub) -> None:
        self.owner = owner

    def radio(
        self,
        label: str,
        options: list[str],
        index: int = 0,
        key: str | None = None,
        **kwargs: Any,
    ) -> str:
        del label, kwargs
        if key and key in self.owner.session_state:
            return str(self.owner.session_state[key])
        return options[index] if options else ""

    def selectbox(self, label: str, options: list[Any], index: int = 0, **kwargs: Any) -> Any:
        del label, kwargs
        return options[index] if options else ""

    def text_input(self, label: str, value: str = "", **kwargs: Any) -> str:
        del label, kwargs
        return value

    def slider(self, label: str, low: int, high: int, default: int, **kwargs: Any) -> int:
        del label, default, kwargs
        return high


class _Stub:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}
        self.sidebar = _Sidebar(self)
        self.calls: list[tuple[str, Any]] = []

    def set_page_config(self, **kwargs: Any) -> None:
        del kwargs

    def _record(self, name: str, value: Any) -> None:
        self.calls.append((name, value))

    def title(self, text: Any) -> None:
        self._record("title", text)

    def caption(self, text: Any) -> None:
        self._record("caption", text)

    def subheader(self, text: Any) -> None:
        self._record("subheader", text)

    def write(self, text: Any) -> None:
        self._record("write", text)

    def table(self, text: Any) -> None:
        self._record("table", text)

    def dataframe(self, text: Any, **kwargs: Any) -> None:
        del kwargs
        self._record("dataframe", text)

    def info(self, text: Any) -> None:
        self._record("info", text)

    def error(self, text: Any) -> None:
        self._record("error", text)

    def warning(self, text: Any) -> None:
        self._record("warning", text)

    def success(self, text: Any) -> None:
        self._record("success", text)

    def markdown(self, text: Any, **kwargs: Any) -> None:
        del kwargs
        self._record("markdown", text)

    def code(self, text: Any, **kwargs: Any) -> None:
        del kwargs
        self._record("code", text)

    def json(self, text: Any) -> None:
        self._record("json", text)

    def divider(self) -> None:
        self._record("divider", "")

    def metric(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def progress(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def line_chart(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def columns(self, count: int | list[float]) -> list[_Ctx]:
        size = len(count) if isinstance(count, list) else count
        return [_Ctx() for _ in range(size)]

    def container(self, *args: Any, **kwargs: Any) -> _Ctx:
        del args, kwargs
        return _Ctx()

    def expander(self, label: str, *args: Any, **kwargs: Any) -> _Ctx:
        del args, kwargs
        self._record("expander", label)
        return _Ctx()

    def spinner(self, *args: Any, **kwargs: Any) -> _Ctx:
        del args, kwargs
        return _Ctx()

    def selectbox(self, label: str, options: list[Any], index: int = 0, **kwargs: Any) -> Any:
        del label, kwargs
        return options[index] if options else ""

    def multiselect(
        self,
        label: str,
        options: list[Any],
        default: list[Any] | None = None,
        **kwargs: Any,
    ) -> list[Any]:
        del label, kwargs
        return list(default or options[:2])

    def radio(self, label: str, options: list[str], index: int = 0, **kwargs: Any) -> str:
        del label, kwargs
        return options[index] if options else ""

    def text_input(self, label: str, value: str = "", **kwargs: Any) -> str:
        del label, kwargs
        return value

    def number_input(self, label: str, **kwargs: Any) -> Any:
        del label
        return kwargs.get("value", kwargs.get("min_value", 0))

    def checkbox(self, label: str, value: bool = False, **kwargs: Any) -> bool:
        del label, kwargs
        return value

    def button(self, label: str, **kwargs: Any) -> bool:
        del label, kwargs
        return False

    def download_button(self, label: str, **kwargs: Any) -> bool:
        del label, kwargs
        return False

    def slider(self, label: str, low: int, high: int, default: int, **kwargs: Any) -> int:
        del label, low, default, kwargs
        return high

    def rerun(self) -> None:
        self._record("rerun", "")


def _config(seed: int = 0) -> RunConfig:
    return RunConfig(
        map_id="MAP-01",
        environment_seed=seed,
        mode=RunMode.OFFLINE,
        provider_id=OFFLINE_PROVIDER,
        model=OFFLINE_MODEL,
        agent="public_heuristic_policy",
        max_decisions=30,
        max_requests=1,
        max_input_tokens=10_000,
        max_output_tokens=1_000,
        max_cost_cny=Decimal("0.01"),
    )


def _prepare_runs(base: Path) -> str:
    service = RunService(base, recover=False)
    try:
        run_id = service.create_run(_config())
        service.wait(run_id, timeout=60)
        service.create_run(_config(seed=1))
        service.wait(service.list_runs()[0].run_id, timeout=60)
        return run_id
    finally:
        service.shutdown()


def _render(monkeypatch: Any, tmp_path: Path, view: str, run_id: str = "") -> _Stub:
    from agent_arena.ui import app as ui_app

    base = tmp_path / "web"
    monkeypatch.setattr(ui_app, "WEB_RUNS_DIR", base)
    ui_app.reset_service()
    stub = _Stub()
    stub.session_state["nav"] = view
    if run_id:
        stub.session_state["active_run"] = run_id
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


def test_home_renders_cards_and_quickstart(monkeypatch, tmp_path) -> None:
    stub = _render(monkeypatch, tmp_path, "首页 / 地图大厅")
    titles = [str(value) for name, value in stub.calls if name == "title"]
    assert any("十世界三十图" in title for title in titles)
    assert any("地图大厅" in str(value) for name, value in stub.calls if name == "subheader")


def test_config_renders_public_rules_without_starting(monkeypatch, tmp_path) -> None:
    stub = _render(monkeypatch, tmp_path, "挑战配置")
    text = " ".join(str(value) for _, value in stub.calls)
    assert "公开规则" in text
    assert "动作契约" in text
    assert "开始挑战" not in text  # 按钮是动作，不写入文本


def test_live_and_result_pages_render_completed_run(monkeypatch, tmp_path) -> None:
    run_id = _prepare_runs(tmp_path / "web")
    live = _render(monkeypatch, tmp_path, "运行监控", run_id)
    assert any("动作时间线" in str(value) for _, value in live.calls)
    result = _render(monkeypatch, tmp_path, "结果与回放", run_id)
    text = " ".join(str(value) for _, value in result.calls)
    assert "逐步回放" in text
    assert "导出" in text


def test_history_page_renders_filters_and_leaderboard(monkeypatch, tmp_path) -> None:
    run_id = _prepare_runs(tmp_path / "web")
    stub = _render(monkeypatch, tmp_path, "历史与对照", run_id)
    text = " ".join(str(value) for _, value in stub.calls)
    assert "多局对照（2–4 局）" in text
    assert "本地同模型成绩榜" in text


def test_settings_page_renders_provider_status(monkeypatch, tmp_path) -> None:
    stub = _render(monkeypatch, tmp_path, "设置与帮助")
    text = " ".join(str(value) for _, value in stub.calls)
    assert "Provider 配置" in text
    assert "费用与预算边界" in text


def test_deep_link_sets_view_and_run() -> None:
    from agent_arena.ui import app as ui_app

    stub = _Stub()
    stub.query_params = {
        "view": "结果与回放",
        "run": "web-20261020T024951Z-3e3249a7",
        "map": "MAP-19",
    }
    ui_app._apply_deep_link(stub)
    assert stub.session_state["nav"] == "结果与回放"
    assert stub.session_state["active_run"] == "web-20261020T024951Z-3e3249a7"
    assert stub.session_state["selected_map"] == "MAP-19"


def test_pending_nav_is_applied_before_widget() -> None:
    from agent_arena.ui import app as ui_app

    stub = _Stub()
    stub.session_state["pending_nav"] = "挑战配置"
    ui_app._apply_pending_nav(stub)
    assert stub.session_state["nav"] == "挑战配置"
    assert "pending_nav" not in stub.session_state


def test_deep_link_only_applies_on_first_load() -> None:
    from agent_arena.ui import app as ui_app

    stub = _Stub()
    stub.session_state["nav"] = "挑战配置"
    stub.session_state["_deep_link_applied"] = True
    stub.query_params = {"view": "结果与回放"}
    ui_app._apply_deep_link(stub)
    assert stub.session_state["nav"] == "挑战配置"
