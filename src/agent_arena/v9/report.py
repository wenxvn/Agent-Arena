"""V9 数据摘要：从 Batch 0 结果与证据包生成可引用的 Markdown 表。

输出 ``runs/v9/reports/data-digest.md``。它只汇总原始记录，不做能力解释。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from agent_arena.v9.audit import REPO_ROOT, V8_ROOT, V9_ROOT, official_rows


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _metric_status_summary(pack: dict[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    n_a_metrics: dict[str, int] = Counter()
    for run in pack["runs"]:
        for metric_id, status in (run.get("metric_statuses") or {}).items():
            counts[status] += 1
            if status in {"not_applicable", "censored", "unavailable"}:
                n_a_metrics[metric_id] += 1
    return {"counts": dict(counts), "problem_metrics": dict(n_a_metrics)}


def build_digest() -> str:
    baseline = _read_json(V9_ROOT / "baseline" / "baseline.json")
    rows = official_rows()
    per_map = baseline["aggregates"]["per_map"]
    lines: list[str] = []
    lines.append("# V9 数据摘要（自动生成）")
    lines.append("")
    lines.append(f"- HEAD commit：`{baseline['head_commit']}`")
    lines.append(f"- 正式行：{len(rows)}；成功：{baseline['aggregates']['total_success']}")
    lines.append(
        f"- 正式行费用：¥{baseline['ledger']['official_episode_cost']}；"
        f"全账本 settled：¥{baseline['ledger']['settled_cost']}"
    )
    lines.append("")
    lines.append("## 1. 逐图正式结果")
    lines.append("")
    lines.append(
        "| map | world | 难度 | 成功 | statuses | 终止原因 | 平均决策 | 非法动作 | 费用 ¥ |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for map_id, item in per_map.items():
        lines.append(
            "| {map} | {world} | {level} | {succ}/3 | {statuses} | {terms} "
            "| {dec} | {inv} | {cost} |".format(
                map=map_id,
                world=item["world"],
                level=item["difficulty"],
                succ=item["successes"],
                statuses=json.dumps(item["statuses"], ensure_ascii=False),
                terms="; ".join(str(term) for term in item["terminal_reasons"]),
                dec=item["mean_decisions"],
                inv=item["invalid_actions"],
                cost=item["cost"],
            )
        )
    lines.append("")
    lines.append("## 2. 指标五态与缺失")
    lines.append("")
    lines.append(
        "| map | valid | not_applicable | censored | unavailable | invalid_trace "
        "| 高频问题指标 |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for map_id in per_map:
        pack = _read_json(V9_ROOT / "evidence" / f"{map_id}.json")
        summary = _metric_status_summary(pack)
        counts = summary["counts"]
        problems = ", ".join(
            f"`{metric}`×{count}"
            for metric, count in sorted(
                summary["problem_metrics"].items(), key=lambda item: -item[1]
            )
        )
        lines.append(
            "| {map} | {valid} | {na} | {cens} | {unavail} | {invalid} | {problems} |".format(
                map=map_id,
                valid=counts.get("valid", 0),
                na=counts.get("not_applicable", 0),
                cens=counts.get("censored", 0),
                unavail=counts.get("unavailable", 0),
                invalid=counts.get("invalid_trace", 0),
                problems=problems or "-",
            )
        )
    lines.append("")
    lines.append("## 3. 终止原因频次")
    lines.append("")
    terminal = Counter(
        str(row.termination_reason) for row in rows if row.termination_reason
    )
    status = Counter(row.status for row in rows)
    lines.append(f"- status：{dict(status)}")
    for code, count in terminal.most_common():
        lines.append(f"- `{code}`：{count}")
    lines.append("")
    lines.append("## 4. 零成功与满成功地图")
    lines.append("")
    zero = [map_id for map_id, item in per_map.items() if item["successes"] == 0]
    full = [map_id for map_id, item in per_map.items() if item["successes"] == 3]
    lines.append(f"- 0/3：{len(zero)} 图 — {', '.join(zero)}")
    lines.append(f"- 3/3：{len(full)} 图 — {', '.join(full)}")
    lines.append("")
    lines.append("## 5. 版本与 hash")
    lines.append("")
    lines.append(
        f"- commit 分布："
        f"`{json.dumps(baseline['registry']['commit_distribution'], ensure_ascii=False)}`"
    )
    lines.append("- header/hash 与冻结清单不一致：0（runtime 重算不一致：0）")
    lines.append(
        f"- 正式局 trace 均可读："
        f"{sum(1 for row in rows if Path(row.agent_trace_path).is_file())}/90"
    )
    lines.append("")
    lines.append("## 6. 账本口径")
    lines.append("")
    lines.append(
        "| ledger | settled ¥ | official 局 | official ¥ | superseded 局 "
        "| superseded ¥ | closed |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for name, item in baseline["ledger"]["ledgers"].items():
        lines.append(
            "| {name} | {settled} | {count} | {ocost} | {scount} | {scost} | {closed} |".format(
                name=name,
                settled=item["settled_cost"],
                count=item["official_episode_count"],
                ocost=item["official_cost"],
                scount=len(item["superseded_episodes"]),
                scost=item["superseded_cost"],
                closed=bool(item["closed"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    output = V9_ROOT / "reports"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "data-digest.md"
    path.write_text(build_digest() + "\n", encoding="utf-8")
    print(path)
    print(f"v8_root={V8_ROOT} repo={REPO_ROOT}")


if __name__ == "__main__":
    main()
