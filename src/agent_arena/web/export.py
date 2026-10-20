"""运行结果导出：JSON 回放、摘要 JSON、逐动作 CSV（UTF-8 BOM 可选）。

只导出服务层已脱敏的公开数据；不读取密钥、隐藏真值或 Provider 响应头。
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, cast

from agent_arena.web.safety import sanitize_payload

CSV_FIELDS = (
    "step",
    "tool",
    "action_json",
    "result",
    "status",
    "terminal",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "decision_reason",
    "observation_after_json",
)


def replay_document(
    manifest: dict[str, Any],
    result: dict[str, Any] | None,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        sanitize_payload(
            {
                "schema_version": "v11-web-replay-1",
                "run": manifest,
                "result": result,
                "steps": steps,
            }
        ),
    )


def export_json_bytes(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    ).encode("utf-8")


def export_summary_bytes(result: dict[str, Any]) -> bytes:
    summary = {key: value for key, value in result.items() if key != "steps"}
    return export_json_bytes(sanitize_payload(summary))


def export_actions_csv(steps: list[dict[str, Any]], *, bom: bool = True) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for index, step in enumerate(steps, start=1):
        action = step.get("action") or {}
        observation = step.get("observation_after") or {}
        writer.writerow(
            {
                "step": step.get("decision_index", index),
                "tool": action.get("tool") if isinstance(action, dict) else "",
                "action_json": json.dumps(action, ensure_ascii=False, sort_keys=True),
                "result": step.get("result", ""),
                "status": step.get("status", ""),
                "terminal": (
                    bool(observation.get("terminal"))
                    if isinstance(observation, dict)
                    else ""
                ),
                "input_tokens": step.get("input_tokens", ""),
                "output_tokens": step.get("output_tokens", ""),
                "latency_ms": step.get("latency_ms", ""),
                "decision_reason": step.get("decision_reason") or "",
                "observation_after_json": json.dumps(
                    observation, ensure_ascii=False, sort_keys=True
                ),
            }
        )
    encoding = "utf-8-sig" if bom else "utf-8"
    return buffer.getvalue().encode(encoding)


def export_filename(run_id: str, kind: str) -> str:
    suffix = {
        "json": "replay.json",
        "summary": "summary.json",
        "csv": "actions.csv",
    }
    return f"{run_id}-{suffix.get(kind, 'export.txt')}"


def csv_preview(blob: bytes, *, lines: int = 8) -> str:
    """给 UI 的 CSV 预览；只读前几行，避免大文件卡住页面。"""

    text = blob.decode("utf-8-sig")
    return "\n".join(text.splitlines()[:lines])


__all__ = [
    "CSV_FIELDS",
    "csv_preview",
    "export_actions_csv",
    "export_filename",
    "export_json_bytes",
    "export_summary_bytes",
    "replay_document",
]
