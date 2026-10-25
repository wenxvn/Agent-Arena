"""T7-B：UI app 端到端冒烟（stub streamlit，真实数据文件，离线）。"""
from __future__ import annotations

import json
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

    def header(self, text: object) -> None:
        self.calls.append(("header", text))

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
                "header",
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


def test_app_replays_synthetic_trace(monkeypatch, tmp_path) -> None:
    from agent_arena.ui import app as ui_app

    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "synthetic"
    run_dir.mkdir(parents=True)
    trace = {
        "episode_id": "synthetic-episode",
        "agent": "memory",
        "world_version": "synthetic-world-v1",
        "seed": 0,
        "outcome": "success",
        "executed_action_count": 2,
        "provenance": {"agent": "memory", "public_phase_context_enabled": True},
        "steps": [
            {"action": {"tool": "move", "destination": "hall"}},
            {"action": {"tool": "use", "target": "escape_pod"}},
        ],
    }
    (run_dir / "episode_synthetic.json").write_text(
        json.dumps(trace), encoding="utf-8"
    )
    monkeypatch.setattr(ui_app, "RUNS_DIR", runs_dir)

    calls = _run_with_stub(
        "单局回放",
        {"实验目录": "synthetic", "trace 文件": "episode_synthetic.json"},
    )
    tables = [payload for kind, payload in calls if kind == "table"]
    assert len(tables) == 1
    assert len(tables[0]) == 2
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


def test_app_compares_two_benchmark_csvs(monkeypatch, tmp_path) -> None:
    from agent_arena.ui import app as ui_app

    results_dir = tmp_path / "results"
    results_dir.mkdir()
    csv_a = results_dir / "condition-a.csv"
    csv_b = results_dir / "condition-b.csv"
    csv_a.write_text(
        "outcome,steps,input_tokens,output_tokens\n"
        "success,10,100,20\n"
        "success,20,110,25\n",
        encoding="utf-8",
    )
    csv_b.write_text(
        "outcome,steps,input_tokens,output_tokens\n"
        "success,10,100,20\n"
        "success,20,110,25\n"
        "success,30,120,30\n"
        "step_limit,50,130,35\n"
        "step_limit,60,140,40\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ui_app, "RESULTS_DIR", results_dir)
    calls = _run_with_stub(
        "条件对照",
        {"对照 A benchmark CSV": str(csv_a), "对照 B benchmark CSV": str(csv_b)},
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


def test_app_matrix_view_aggregates_synthetic_directory(monkeypatch, tmp_path) -> None:
    from agent_arena.ui import app as ui_app

    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "synthetic"
    run_dir.mkdir(parents=True)
    counts = [50, 70, 110, 160, 210]
    for seed, count in enumerate(counts):
        trace = {
            "world_version": "synthetic-world-v1",
            "seed": seed,
            "outcome": "success",
            "executed_action_count": count,
            "steps": [],
        }
        (run_dir / f"episode_success_{seed}.json").write_text(
            json.dumps(trace), encoding="utf-8"
        )
    failed_trace = {
        "world_version": "synthetic-world-v1",
        "seed": 5,
        "outcome": "step_limit",
        "executed_action_count": 200,
        "steps": [],
    }
    (run_dir / "episode_failed.json").write_text(
        json.dumps(failed_trace), encoding="utf-8"
    )
    monkeypatch.setattr(ui_app, "RUNS_DIR", runs_dir)

    calls = _run_with_stub("矩阵总览", {"矩阵目录": "synthetic"})
    tables = [payload for kind, payload in calls if kind == "table"]
    assert len(tables) == 1
    assert tables[0][0]["success"] == "5/6"
    curves = [
        payload for kind, payload in calls
        if kind == "write" and isinstance(payload, dict) and "success_at_k" in payload
    ]
    assert len(curves) == 1
    assert curves[0]["success_at_k"][200] == 0.8


def test_app_hotspot_view_counts_synthetic_directory(monkeypatch, tmp_path) -> None:
    from agent_arena.ui import app as ui_app

    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "synthetic"
    run_dir.mkdir(parents=True)
    for index in range(6):
        steps = (
            [
                {
                    "action": {"tool": "read_terminal", "target": "escape_pod"},
                    "result": {"reason": "wrong_target"},
                },
                {
                    "action": {"tool": "read_terminal", "target": "control_terminal"},
                    "result": {"reason": "code_read"},
                },
                {
                    "action": {"tool": "move", "destination": "airlock"},
                    "result": {"reason": "moved"},
                },
            ]
            if index == 0
            else []
        )
        trace = {"seed": index, "outcome": "success", "steps": steps}
        (run_dir / f"episode_{index}.json").write_text(
            json.dumps(trace), encoding="utf-8"
        )
    monkeypatch.setattr(ui_app, "RUNS_DIR", runs_dir)

    calls = _run_with_stub("错误热点", {"实验目录": "synthetic"})
    tables = [payload for kind, payload in calls if kind == "table"]
    assert len(tables) == 1
    assert len(tables[0]) == 6
    assert all("wrong_tool" in row for row in tables[0])


def test_app_rejects_path_escape(tmp_path) -> None:
    from agent_arena.ui import app as ui_app

    runs_dir = tmp_path / "runs"
    (runs_dir / "synthetic").mkdir(parents=True)

    assert ui_app._safe_dir(runs_dir, "../src") is None
    assert ui_app._safe_dir(runs_dir, "synthetic") is not None
    assert ui_app._safe_dir(runs_dir, "no-such-dir") is None
