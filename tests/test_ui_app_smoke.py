"""T7-B：UI app 端到端冒烟（stub streamlit，真实数据文件，离线）。"""
from __future__ import annotations

import glob
import sys
import types


class _StubSidebar:
    def __init__(self, owner: "_StubStreamlit") -> None:
        self._owner = owner

    def radio(self, label: str, options: list[str]) -> str:
        return self._owner.radio_choice

    def text_input(self, label: str, default: str = "") -> str:
        return self._owner.inputs.get(label, default)


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


def _run_with_stub(radio: str, inputs: dict[str, str]) -> list[tuple[str, object]]:
    from agent_arena.ui import app as ui_app

    stub = _StubStreamlit()
    stub.radio_choice = radio
    stub.inputs = dict(inputs)
    stub.calls = []
    module = types.ModuleType("streamlit")
    module.__dict__.update(
        {name: getattr(stub, name) for name in ("title", "caption", "subheader", "write", "table", "info", "sidebar")}
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
    calls = _run_with_stub("单局回放", {"trace JSON 路径": trace_path})
    tables = [payload for kind, payload in calls if kind == "table"]
    assert len(tables) == 1
    assert len(tables[0]) == expected
    labels = [str(payload) for kind, payload in calls if kind == "write"]
    assert any("world-declared" in label for label in labels)


def test_app_compares_two_benchmark_csvs() -> None:
    csv_a = "results/exp-E1/benchmark_20261011T115200Z_memory_5-seeds_5-episodes_1ebf5977.csv"
    csv_b = "results/muse-memory-s60-h5rp/benchmark_20261010T182036Z_memory_5-seeds_5-episodes_a055086d.csv"
    calls = _run_with_stub("条件对照", {"对照 A benchmark CSV": csv_a, "对照 B benchmark CSV": csv_b})
    summaries = [payload for kind, payload in calls if kind == "write" and isinstance(payload, dict)]
    assert len(summaries) == 2
    assert summaries[0]["success_rate"] == 1.0
    assert summaries[1]["success_rate"] == 0.6
