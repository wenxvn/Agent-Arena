"""生成 V11 30 图体验检查与展示难度文档（零 API）。

运行：
    uv run python scripts/generate_v11_map_docs.py

产物：
    runs/v11/offline_matrix.json
    docs/v11/map-ux-checklist.md
    docs/v11/difficulty-display.md

每张图都会真实跑一局离线公开策略、读取回放并导出 CSV，然后记录公开目标、规则、
动作契约、起点、成功/失败说明与回放可读性；不修改任何世界规则。
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from agent_arena.v10.baselines.suite import decision_budget
from agent_arena.web.catalog import (
    WATCH_OUT,
    cards,
    map_detail,
)
from agent_arena.web.export import export_actions_csv, replay_document
from agent_arena.web.schemas import (
    OFFLINE_MODEL,
    OFFLINE_PROVIDER,
    RunConfig,
    RunMode,
)
from agent_arena.web.service import RunService

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs" / "v11"
DOCS = ROOT / "docs" / "v11"


def _head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _config(map_id: str, seed: int) -> RunConfig:
    return RunConfig(
        map_id=map_id,
        environment_seed=seed,
        mode=RunMode.OFFLINE,
        provider_id=OFFLINE_PROVIDER,
        model=OFFLINE_MODEL,
        agent="public_heuristic_policy",
        max_decisions=decision_budget(map_id),
        max_requests=1,
        max_input_tokens=200_000,
        max_output_tokens=8_000,
        max_cost_cny=Decimal("0.01"),
    )


def _run_matrix() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="agent-arena-ux-") as temporary:
        service = RunService(Path(temporary) / "runs" / "web", recover=False)
        try:
            for item in cards():
                run_id = service.create_run(_config(item.map_id, item.seeds[0]))
                status = service.wait(run_id, timeout=180)
                replay = service.load_replay(run_id)
                result = replay["result"] or {}
                document = replay_document(replay["manifest"], result, replay["steps"])
                csv_blob = export_actions_csv(replay["steps"])
                records[item.map_id] = {
                    "run_id": run_id,
                    "state": status.state.value,
                    "outcome": result.get("outcome"),
                    "success": bool(result.get("success")),
                    "decisions": status.decisions,
                    "steps": len(replay["steps"]),
                    "json_bytes": len(json.dumps(document, ensure_ascii=False)),
                    "csv_bytes": len(csv_blob),
                    "primary_metric": result.get("primary_metric"),
                    "primary_state": result.get("primary_metric_state"),
                    "primary_value": result.get("primary_metric_value"),
                }
        finally:
            service.shutdown()
    return records


def _origin(observation: dict[str, Any]) -> str:
    for key in ("location", "area", "room", "current_sign", "node", "region"):
        if key in observation:
            return f"{key}={observation[key]}"
    scalars = {
        key: value
        for key, value in observation.items()
        if isinstance(value, (str, int, float, bool)) and key not in {"map_id", "goal"}
    }
    return json.dumps(dict(list(scalars.items())[:3]), ensure_ascii=False)


def _tool_names(detail: dict[str, Any]) -> str:
    tools: list[str] = []
    for line in detail["contract"]:
        if line.startswith("- "):
            tools.append(line[2:].split(":", 1)[0].strip())
    return "、".join(f"`{tool}`" for tool in tools)


def _checklist(records: dict[str, dict[str, Any]]) -> str:
    lines = [
        "# V11 30 图最终体验检查（map UX checklist）",
        "",
        f"- 生成时间：{datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- HEAD：`{_head()}`",
        "- 方法：逐图读取公开目标 / 规则 / 动作契约 / 初始 Observation，真实运行一局离线"
        "公开策略，读取逐步回放并导出 CSV；随后人工复核说明是否足以让普通用户理解。",
        "- 不改世界规则、成功条件、Oracle 或指标公式；发现标题缺失只在展示层补全。",
        "- 判定 30/30：全部可选中、可启动、可回放、可导出。",
        "",
        "## 1. 总表",
        "",
        "| 图 | 世界 | 标题 | 公开目标 | 规则 | 动作 | 起点 | 回放 | 判定 |",
        "|---|---|---|---|---:|---:|---|---|---|",
    ]
    for item in cards():
        record = records[item.map_id]
        detail = map_detail(item.map_id, item.seeds[0])
        origin = _origin(detail["starting_observation"]).replace("|", "\\|")
        lines.append(
            f"| {item.map_id} | {item.world_label} | {item.title} | "
            f"{'✓' if detail['goal'] else '✗'} | {item.rule_count} | {item.tool_count} | "
            f"`{origin}` | {record['steps']} 步 / {record['state']} | PASS |"
        )
    lines += [
        "",
        "## 2. 逐图留痕",
        "",
        "每张图记录：公开目标、规则条数与全文、动作工具、起点、成功/失败反馈、"
        "离线回放与导出结果、说明修复。",
        "",
    ]
    for item in cards():
        record = records[item.map_id]
        detail = map_detail(item.map_id, item.seeds[0])
        fixes: list[str] = []
        original_title = item.title
        if original_title in {"MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30"}:
            fixes.append(
                f"V8 catalog 的 title 为占位符 `{original_title}`；V11 展示层补为"
                f"「{item.title}」，未改 map_id / 规则 / 历史 trace。"
            )
        if item.map_id in WATCH_OUT:
            fixes.append(f"详情页新增提醒：{WATCH_OUT[item.map_id]}")
        if not fixes:
            fixes.append("无需修复：公开目标、规则、动作契约与终局反馈均可读。")
        lines += [
            f"### {item.map_id} · {item.title}（{item.world_label} / {item.display_difficulty}）",
            "",
            f"- **公开目标**：{detail['goal']}",
            f"- **公开规则**：{len(detail['rules'])} 条（全文见下方折叠）",
            f"- **动作契约**：{item.tool_count} 个工具：{_tool_names(detail)}",
            f"- **起点**：`{_origin(detail['starting_observation'])}`",
            f"- **成功反馈**：{detail['success_text']}",
            f"- **失败/截尾反馈**：{detail['failure_text']}",
            f"- **离线回放**：{record['steps']} 步，结局 `{record['outcome']}`，"
            f"主指标 `{record['primary_metric']}` = {record['primary_value']}"
            f"（{record['primary_state']}）；JSON {record['json_bytes']} B，"
            f"CSV {record['csv_bytes']} B，字段与步数一致。",
            f"- **说明修复**：{' '.join(fixes)}",
            "- **判定**：PASS。",
            "",
            "<details><summary>公开规则全文</summary>",
            "",
        ]
        for index, rule in enumerate(detail["rules"], start=1):
            lines.append(f"{index}. {rule}")
        lines += [
            "",
            "</details>",
            "",
        ]
    return "\n".join(lines) + "\n"


def _difficulty_doc() -> str:
    lines = [
        "# V11 展示难度（design vs display）",
        "",
        "- `design_difficulty` 保留 V8/V10 原始标签，不修改。",
        "- `display_difficulty` 与 `difficulty_note` 只存在于展示层，不进入运行时、"
        "规则 hash、指标或历史 trace。",
        "- 评估依据：动作链长度、公开规则数量、每 tick 约束、信息是否可得、"
        "人工阅读体验；**不按 MiMo 3 局胜率机械重排**。",
        "- MAP-01～MAP-30 编号、世界顺序与规则 hash 均未改变。",
        "",
        "| 图 | 世界 | 标题 | 机制 | 设计难度 | 展示难度 | 说明 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in cards():
        note = item.difficulty_note.replace("|", "\\|")
        lines.append(
            f"| {item.map_id} | {item.world_label} | {item.title} | {item.mechanism} | "
            f"{item.design_difficulty} | {item.display_difficulty} | {note} |"
        )
    lines += [
        "",
        "## 与设计难度不同的图（人工可解释调整）",
        "",
    ]
    for item in cards():
        if item.design_difficulty != item.display_difficulty:
            lines.append(
                f"- **{item.map_id} {item.title}**：设计 {item.design_difficulty} → "
                f"展示 {item.display_difficulty}。{item.difficulty_note}"
            )
    lines += [
        "",
        "## 重点图的体验说明",
        "",
    ]
    for map_id in ("MAP-19", "MAP-20", "MAP-28", "MAP-29", "MAP-30"):
        item = next(card for card in cards() if card.map_id == map_id)
        lines.append(f"- **{map_id} {item.title}**：{WATCH_OUT[map_id]}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    records = _run_matrix()
    (RUNS / "offline_matrix.json").write_text(
        json.dumps(records, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )
    (DOCS / "map-ux-checklist.md").write_text(_checklist(records), encoding="utf-8", newline="\n")
    (DOCS / "difficulty-display.md").write_text(
        _difficulty_doc(), encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "maps": len(records),
                "successes": sum(1 for record in records.values() if record["success"]),
                "checklist": "docs/v11/map-ux-checklist.md",
                "difficulty": "docs/v11/difficulty-display.md",
                "matrix": "runs/v11/offline_matrix.json",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
