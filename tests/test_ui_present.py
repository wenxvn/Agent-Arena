"""T7-B：UI 展示逻辑与密钥门禁（不导入 streamlit，不调用模型）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from agent_arena.ui.present import autonomy_level, compare_conditions, summarize_trace

UI_DIR = Path(__file__).resolve().parent.parent / "src" / "agent_arena" / "ui"


def test_autonomy_levels_labelled() -> None:
    assert autonomy_level({"agent": "memory"}) == "纯 observation 自主"
    assert "observation-derived" in autonomy_level(
        {"agent": "memory", "recent_history_enabled": True}
    )
    assert "world-declared" in autonomy_level(
        {"agent": "memory", "public_phase_context_enabled": True}
    )
    assert "非自主" in autonomy_level({"agent": "planner_assisted"})
    assert autonomy_level({"agent": "planning", "planning_enabled": True}).startswith("planning")
    assert "guarded" in autonomy_level({"agent": "memory", "public_action_guard": True})


def test_summarize_trace_uses_allowlist_fields() -> None:
    trace = {
        "steps": [
            {
                "event": "action_validated",
                "observation": {"current_room": "control_room"},
                "action": {"tool": "move", "destination": "corridor"},
                "result": {"reason": "moved"},
                "progress": {"progress": True},
                "decision_reason": "x" * 500,
                "input_tokens": 100,
                "output_tokens": 20,
            }
        ]
    }
    rows = summarize_trace(trace)
    assert len(rows) == 1
    assert rows[0]["step"] == 1
    assert rows[0]["action"] == "move"
    assert len(rows[0]["decision_reason"]) <= 280


def test_compare_conditions_marks_missing_as_na() -> None:
    summary = compare_conditions([])
    assert summary["attempts"] == 0
    assert summary["success_rate"] == "N/A"
    summary = compare_conditions(
        [
            {"outcome": "success", "steps": 30, "input_tokens": 10, "output_tokens": 5},
            {"outcome": "step_limit", "steps": 60, "input_tokens": 20, "output_tokens": 8},
        ]
    )
    assert summary["success_rate"] == 0.5
    assert summary["mean_steps"] == 45.0


def test_real_trace_replays() -> None:
    candidates = sorted((Path("runs") / "muse-9maps-ship-med").glob("*.json"))
    trace = json.loads(candidates[0].read_text(encoding="utf-8"))
    rows = summarize_trace(trace)
    assert len(rows) == trace["executed_action_count"]
    assert autonomy_level(trace["provenance"]) == "world-declared phase guidance｜世界预定义任务辅助"


def test_ui_touches_no_secrets() -> None:
    forbidden = re.compile(
        r"OPENAI_API_KEY|DASHSCOPE_API_KEY|get_secret_value|load_dotenv|"
        r"openai_api_key|dashscope_api_key|import streamlit"
    )
    hits = []
    for path in sorted(UI_DIR.glob("*.py")):
        if path.name == "app.py":
            text = path.read_text(encoding="utf-8")
            assert "import_module(\"streamlit\")" in text
            text_without_loader = text.replace("import_module(\"streamlit\")", "")
            if forbidden.search(text_without_loader):
                hits.append(path.name)
            continue
        if forbidden.search(path.read_text(encoding="utf-8")):
            hits.append(path.name)
    assert hits == []
