"""T7-B：UI app 端到端冒烟（stub streamlit，真实数据文件，离线）。"""
from __future__ import annotations

import glob
import sys
import types


class _StubSidebar:
    def __init__(self, owner: _StubStreamlit) -> None:
        self._owner = owner

    def radio(self, label: str, options: list[str]) -> str:
        return self._owner.radio_choice

    def text_input(self, label: str, default: str = "") -> str:
        return self._owner.inputs.get(label, default)

    def selectbox(self, label: str, options: list[str]) -> str:
        override = self._owner.inputs.get(label)
        if isinstance(override, str) and override in options:
            return override
        return options[0]

    def slider(self, label: str, low: int, high: int, default: int) -> int:
        assert low < high
        return default


class _StubStreamlit:
    radio_choice = "单局回放"
    inputs: dict[str, str] = {}
    calls: list[tuple[str, object]] = []

    def __init__(self) -> None:
        self.sidebar = _StubSidebar(self)

    def title(self, text: object) -> None:
        self.calls.append(("title", text))

    def caption(self, text: object) -> None:
        self.calls.append(("caption", text))

    def subheader(self, text: object) -> None:
        self.calls.append(("subheader", text))

    def write(self, text: object) -> None:
        self.calls.append(("write", text))

    def table(self, text: object) -> None:
        self.calls.append(("table", text))

    def info(self, text: object) -> None:
        self.calls.append(("info", text))

    def error(self, text: object) -> None:
        self.calls.append(("error", text))


def _run_with_stub(radio: str, inputs: dict[str, str]) -> list[tuple[str, object]]:
    from agent_arena.ui import app as ui_app

    stub = _StubStreamlit()
    stub.radio_choice = radio
    stub.inputs = dict(inputs)
    stub.calls = []
    module = types.ModuleType("streamlit")
    module.__dict__.update(
        {
            name: getattr(stub, name)
            for name in (
                "title",
                "caption",
                "subheader",
                "write",
                "table",
                "info",
                "error",
                "sidebar",
            )
        }
    )
    sys.modules["streamlit"] = module
    try:
        ui_app.main()
    finally:
        sys.modules.pop("streamlit", None)
    return stub.calls


def test_app_replays_real_trace() -> None:
    import json

    trace_path = sorted(glob.glob("runs/muse-9maps-ship-med/*.json"))[0]
    expected = json.load(open(trace_path, encoding="utf-8"))["executed_action_count"]
    calls = _run_with_stub(
        "单局回放",
        {"实验目录": "muse-9maps-ship-med", "trace 文件": trace_path.split("\\")[-1]},
    )
    tables = [payload for kind, payload in calls if kind == "table"]
    assert len(tables) == 1
    assert len(tables[0]) == min(expected, 30)
    labels = [str(payload) for kind, payload in calls if kind == "write"]
    assert any("world-declared" in label for label in labels)


def test_app_replays_empty_trace_without_single_page_slider(monkeypatch, tmp_path) -> None:
    from agent_arena.ui import app as ui_app

    run_dir = tmp_path / "empty-trace"
    run_dir.mkdir()
    (run_dir / "episode_empty.json").write_text('{"steps": []}', encoding="utf-8")
    monkeypatch.setattr(ui_app, "RUNS_DIR", tmp_path)

    calls = _run_with_stub(
        "单局回放",
        {"实验目录": "empty-trace", "trace 文件": "episode_empty.json"},
    )

    tables = [payload for kind, payload in calls if kind == "table"]
    assert tables == [[]]


def test_app_compares_two_benchmark_csvs() -> None:
    csv_a = "results/exp-E1/benchmark_20261011T115200Z_memory_5-seeds_5-episodes_1ebf5977.csv"
    csv_b = (
        "results/muse-memory-s60-h5rp/benchmark_20261010T182036Z_memory_5-seeds_"
        "5-episodes_a055086d.csv"
    )
    calls = _run_with_stub(
        "条件对照", {"对照 A benchmark CSV": csv_a, "对照 B benchmark CSV": csv_b}
    )
    summaries = [
        payload for kind, payload in calls if kind == "write" and isinstance(payload, dict)
    ]
    assert len(summaries) == 2
    assert summaries[0]["success_rate"] == 1.0
    assert summaries[1]["success_rate"] == 0.6


def test_app_compare_rejects_csv_outside_runs_and_results(monkeypatch, tmp_path) -> None:
    from agent_arena.ui import app as ui_app

    runs_dir = tmp_path / "runs"
    results_dir = tmp_path / "results"
    runs_dir.mkdir()
    results_dir.mkdir()
    outside_csv = tmp_path / "outside.csv"
    outside_csv.write_text("outcome,steps\nsuccess,1\n", encoding="utf-8")
    deep_csv = results_dir / "nested" / "deeper" / "benchmark.csv"
    deep_csv.parent.mkdir(parents=True)
    deep_csv.write_text("outcome,steps\nsuccess,1\n", encoding="utf-8")
    monkeypatch.setattr(ui_app, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(ui_app, "RESULTS_DIR", results_dir)

    inputs = {
        "对照 A benchmark CSV": str(outside_csv),
        "对照 B benchmark CSV": str(deep_csv),
    }
    calls = _run_with_stub("条件对照", inputs)

    infos = [str(payload) for kind, payload in calls if kind == "info"]
    summaries = [
        payload for kind, payload in calls if kind == "write" and isinstance(payload, dict)
    ]
    assert len(infos) == 2
    assert all("runs/ 或 results/" in info for info in infos)
    assert summaries == []
    assert ui_app._safe_csv_path("results/missing.csv") is None


def test_app_rejects_trace_symlink_escape(monkeypatch, tmp_path) -> None:
    from agent_arena.ui import app as ui_app

    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "experiment"
    run_dir.mkdir(parents=True)
    outside_trace = tmp_path / "outside.json"
    outside_trace.write_text('{"steps": [], "secret": "must not display"}', encoding="utf-8")
    link = run_dir / "episode_escape.json"
    try:
        link.symlink_to(outside_trace)
    except (OSError, NotImplementedError):
        # Windows may deny symlink creation without Developer Mode; the
        # resolved-path boundary is still exercised against the same target.
        assert ui_app._safe_trace_path(run_dir, outside_trace) is None
        return

    monkeypatch.setattr(ui_app, "RUNS_DIR", runs_dir)
    traces, skipped = ui_app._scan_traces(run_dir)
    assert traces == []
    assert skipped == 0

    calls = _run_with_stub("单局回放", {"实验目录": "experiment"})
    infos = [str(payload) for kind, payload in calls if kind == "info"]
    displayed = [str(payload) for kind, payload in calls if kind == "write"]
    assert any("没有 episode trace" in info for info in infos)
    assert all("must not display" not in item for item in displayed)


def test_app_matrix_view_aggregates_real_directory() -> None:
    calls = _run_with_stub("矩阵总览", {"矩阵目录": "muse-9maps-ship-med"})
    tables = [payload for kind, payload in calls if kind == "table"]
    assert len(tables) == 1
    assert tables[0][0]["success"] == "5/6"
    curves = [
        payload for kind, payload in calls
        if kind == "write" and isinstance(payload, dict) and "success_at_k" in payload
    ]
    assert len(curves) == 1
    assert curves[0]["success_at_k"][200] == 0.8


def test_app_hotspot_view_counts_real_directory() -> None:
    calls = _run_with_stub("错误热点", {"实验目录": "muse-9maps-ship-med"})
    tables = [payload for kind, payload in calls if kind == "table"]
    assert len(tables) == 1
    assert len(tables[0]) == 6
    assert all("wrong_tool" in row for row in tables[0])


def test_app_rejects_path_escape() -> None:
    from pathlib import Path

    from agent_arena.ui import app as ui_app

    assert ui_app._safe_dir(Path("runs"), "../src") is None
    assert ui_app._safe_dir(Path("runs"), "muse-9maps-ship-med") is not None
    assert ui_app._safe_dir(Path("runs"), "no-such-dir") is None
