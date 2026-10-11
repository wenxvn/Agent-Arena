"""T7-B：UI 展示逻辑与密钥门禁（不导入 streamlit，不调用模型）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from agent_arena.ui.present import (
    aggregate_traces,
    autonomy_level,
    compare_conditions,
    error_hotspots,
    page_rows,
    success_at_k,
    summarize_trace,
    trace_overview,
)

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


def test_trace_overview_uses_allowlist_fields() -> None:
    trace = {
        "episode_id": "abc",
        "agent": "memory",
        "world_version": "polar-escape-easy-zh",
        "seed": 1,
        "outcome": "success",
        "executed_action_count": 22,
        "invalid_output_count": 0,
        "rejected_action_count": 3,
        "latency_ms": 100,
        "provenance": {"model_name": "muse-spark-1.3-contributor", "base_prompt_hash": "44229085xx"},
        "steps": [{"input_tokens": 10, "output_tokens": 2}],
    }
    overview = trace_overview(trace)
    assert overview["steps"] == 22
    assert overview["prompt_hash"] == "44229085"
    assert overview["input_tokens"] == 10
    assert overview["autonomy"] == "纯 observation 自主"


def test_success_at_k_counts_budget_hits() -> None:
    curve = success_at_k([20, 60, 100], [30, 60, 100])
    assert curve == {30: 1 / 3, 60: 2 / 3, 100: 1.0}
    assert success_at_k([], [30]) == {30: 0.0}


def test_error_hotspots_counts_three_categories() -> None:
    def action_step(tool: str, reason: str, **extra: object) -> dict[str, object]:
        action: dict[str, object] = {"tool": tool}
        action.update(extra)
        return {"action": action, "result": {"reason": reason}}

    trace = {
        "steps": [
            action_step("read_terminal", "wrong_target", target="harbor_skiff"),
            action_step("read_terminal", "code_read", target="lamp_console"),
            action_step("read_terminal", "code_read", target="lamp_console"),
            action_step("move", "moved", destination="engine_cave"),
            action_step("look", "looked"),
        ]
    }
    hotspots = error_hotspots(trace)
    assert hotspots["wrong_tool_at_terminal"] == 1
    assert hotspots["code_reads"] == 2
    assert hotspots["repeated_code_read"] == 1
    assert hotspots["post_code_moves"] == 2
    assert error_hotspots({}) == {
        "wrong_tool_at_terminal": 0,
        "code_reads": 0,
        "repeated_code_read": 0,
        "post_code_moves": 0,
    }


def test_aggregate_traces_groups_by_world_version() -> None:
    traces = [
        {"world_version": "v", "outcome": "success", "seed": 0, "executed_action_count": 20},
        {"world_version": "v", "outcome": "success", "seed": 1, "executed_action_count": 30},
        {"world_version": "v", "outcome": "step_limit", "seed": 2, "executed_action_count": 60},
    ]
    rows = aggregate_traces(traces)
    assert len(rows) == 1
    assert rows[0]["success"] == "2/3"
    assert rows[0]["mean_steps"] == 25.0
    assert rows[0]["median_steps"] == 30
    assert aggregate_traces([]) == []


def test_page_rows_bounds() -> None:
    rows = [{"step": index} for index in range(1, 6)]
    assert [row["step"] for row in page_rows(rows, 1, 2)] == [1, 2]
    assert [row["step"] for row in page_rows(rows, 3, 2)] == [5]
    assert page_rows(rows, 4, 2) == []
    assert page_rows(rows, 0, 2) == []
