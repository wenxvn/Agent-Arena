"""V11 导出：字段、BOM、脱敏与文件名。"""

from __future__ import annotations

import csv
import io
import json

from agent_arena.web.export import (
    export_actions_csv,
    export_filename,
    export_json_bytes,
    export_summary_bytes,
    replay_document,
)


def _steps() -> list[dict[str, object]]:
    return [
        {
            "event": "decision",
            "decision_index": 1,
            "action": {"tool": "move", "to": "B"},
            "result": "MOVED:B",
            "status": "running",
            "observation_after": {"map_id": "MAP-01", "terminal": False, "location": "B"},
            "input_tokens": 100,
            "output_tokens": 10,
            "latency_ms": 20,
            "decision_reason": "公开规则策略",
        }
    ]


def test_replay_document_redacts_secret_patterns() -> None:
    manifest = {"run_id": "web-x", "note": "Authorization: Bearer abcdefgh12345678"}
    document = replay_document(manifest, {"api_key": "sk-abcdefgh12345678"}, _steps())
    text = json.dumps(document, ensure_ascii=False)
    assert "sk-abcdefgh" not in text
    assert "abcdefgh12345678" not in text


def test_csv_has_expected_fields_and_bom() -> None:
    blob = export_actions_csv(_steps())
    assert blob.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(blob.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["step"] == "1"
    assert rows[0]["tool"] == "move"
    assert json.loads(rows[0]["action_json"]) == {"tool": "move", "to": "B"}
    assert rows[0]["terminal"] == "False"


def test_csv_can_disable_bom() -> None:
    assert not export_actions_csv(_steps(), bom=False).startswith(b"\xef\xbb\xbf")


def test_json_and_summary_exports_are_utf8() -> None:
    document = replay_document({"run_id": "r"}, {"title": "破损的曙光号"}, _steps())
    blob = export_json_bytes(document)
    assert "破损的曙光号" in blob.decode("utf-8")
    summary = export_summary_bytes({"title": "破损的曙光号", "steps": [1]})
    assert "steps" not in json.loads(summary)


def test_trace_jsonl_has_header_and_steps() -> None:
    from agent_arena.web.export import export_trace_jsonl

    lines = export_trace_jsonl(_steps()).decode("utf-8").splitlines()
    assert json.loads(lines[0])["event"] == "trace_header"
    assert json.loads(lines[1])["event"] == "decision"
    assert "sk-" not in "\n".join(lines)


def test_export_filenames_are_bounded() -> None:
    assert export_filename("web-20260101T000000Z-abcdef12", "json").endswith("replay.json")
    assert export_filename("web-20260101T000000Z-abcdef12", "csv").endswith("actions.csv")
    assert export_filename("web-20260101T000000Z-abcdef12", "weird").endswith("export.txt")
