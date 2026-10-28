"""V14 MAP-22 实例差异的公开轨迹归因（只读；零请求）。

用法：
    uv run python scripts/analyze_v14_map22.py            # 打印摘要
    uv run python scripts/analyze_v14_map22.py --write     # 写 docs/v14/map22-instances.md/.json

问题：为什么 `route_log` 只在 MAP-22 的 seed 2 上把 2/9 变成 8/8？
做法：只用**公开**轨迹字段（`current_sign`、`result`、`moves_used`、`ruin_recorded`），
按 seed × 臂聚合"走了多少步 / 被拒多少步 / 重复访问多少 / 发现几个路标 / 何时记录遗迹"。

不读 `judge_state` / `sealed_truth`，不重跑任何局。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v10.runtime.map22 import oracle_actions  # noqa: E402

LIVE_WEB = ROOT / "runs" / "v14" / "live" / "web"

def _load_run(run_id: str) -> dict[str, Any] | None:
    directory = LIVE_WEB / run_id
    result_path = directory / "result.json"
    events_path = directory / "events.jsonl"
    if not result_path.is_file() or not events_path.is_file():
        return None
    result = json.loads(result_path.read_text(encoding="utf-8"))
    steps = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    ]
    return {"result": result, "steps": [s for s in steps if s.get("event") == "decision"]}

def _features(run: dict[str, Any]) -> dict[str, Any]:
    result = run["result"]
    steps = run["steps"]
    config = (result.get("config") or {}).get("agent_config") or {}
    visits: Counter[str] = Counter()
    moves = 0
    rejected = 0
    backtracks = 0
    last_bearing = ""
    ruin_at: int | None = None
    previous_sign = ""
    for step in steps:
        action = step.get("action") or {}
        after = step.get("observation_after") or {}
        sign = str(after.get("current_sign") or "")
        text = str(step.get("result") or "")
        if sign:
            visits[sign] += 1
        if action.get("tool") == "move":
            moves += 1
            if not text.startswith("MOVED"):
                rejected += 1
            else:
                bearing = str(action.get("bearing") or "")
                if last_bearing and bearing == _opposite(last_bearing):
                    backtracks += 1
                last_bearing = bearing
        if ruin_at is None and after.get("ruin_recorded"):
            ruin_at = int(step.get("decision_index") or 0)
        previous_sign = sign or previous_sign
    moves_used = None
    if steps:
        moves_used = (steps[-1].get("observation_after") or {}).get("moves_used")
    metrics = result.get("metrics") or {}
    return {
        "run_id": result.get("run_id"),
        "agent": result.get("agent"),
        "arm": "on" if config.get("route_log") else "off",
        "model": result.get("model"),
        "seed": int(result.get("environment_seed") or 0),
        "replicate_index": int(result.get("replicate_index") or 0),
        "request_cap": int((result.get("usage") or {}).get("max_requests") or 0),
        "success": bool(result.get("success")),
        "termination": result.get("termination"),
        "decisions": int(result.get("decision_count") or 0),
        "move_attempts": moves,
        "moves_rejected": rejected,
        "backtracks": backtracks,
        "distinct_signs": len(visits),
        "max_sign_visits": max(visits.values()) if visits else 0,
        "revisit_steps": sum(count - 1 for count in visits.values() if count > 1),
        "ruin_recorded_at": ruin_at,
        "moves_used": moves_used,
        "route_recall": (metrics.get("map22.v10.route_recall") or {}).get("value"),
        "wasted_moves": (metrics.get("map22.v10.wasted_moves") or {}).get("value"),
    }

def _opposite(bearing: str) -> str:
    return {"north": "south", "south": "north", "east": "west", "west": "east"}.get(
        bearing, ""
    )

def _oracle(seed: int) -> dict[str, Any]:
    actions = oracle_actions(seed)
    return {
        "seed": seed,
        "oracle_actions": len(actions),
        "oracle_moves": sum(1 for a in actions if a.get("tool") == "move"),
    }

def collect() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for directory in sorted(LIVE_WEB.glob("web-*")):
        if not (directory / "result.json").is_file():
            continue
        loaded = _load_run(directory.name)
        if loaded is None or loaded["result"].get("map_id") != "MAP-22":
            continue
        if loaded["result"].get("agent") != "memory.v2":
            continue
        rows.append(_features(loaded))
    # 只保留 seed 2 有意义的对照，但把全部行都输出（不筛选）
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"seed={row['seed']}|{row['arm']}|req={row['request_cap']}"
        bucket = buckets.setdefault(
            key,
            {
                "key": key,
                "runs": 0,
                "successes": 0,
                "decisions": [],
                "moves_rejected": [],
                "backtracks": [],
                "distinct_signs": [],
                "revisit_steps": [],
                "route_recall": [],
                "moves_used": [],
            },
        )
        bucket["runs"] += 1
        bucket["successes"] += 1 if row["success"] else 0
        bucket["decisions"].append(row["decisions"])
        bucket["moves_rejected"].append(row["moves_rejected"])
        bucket["backtracks"].append(row["backtracks"])
        bucket["distinct_signs"].append(row["distinct_signs"])
        bucket["revisit_steps"].append(row["revisit_steps"])
        if row["route_recall"] is not None:
            bucket["route_recall"].append(float(row["route_recall"]))
        if row["moves_used"] is not None:
            bucket["moves_used"].append(int(row["moves_used"]))
    summary = []
    for bucket in sorted(buckets.values(), key=lambda item: item["key"]):
        summary.append(
            {
                "key": bucket["key"],
                "runs": bucket["runs"],
                "successes": bucket["successes"],
                "mean_decisions": _mean(bucket["decisions"]),
                "mean_moves_rejected": _mean(bucket["moves_rejected"]),
                "mean_backtracks": _mean(bucket["backtracks"]),
                "mean_distinct_signs": _mean(bucket["distinct_signs"]),
                "mean_revisit_steps": _mean(bucket["revisit_steps"]),
                "mean_route_recall": _mean(bucket["route_recall"]),
                "max_moves_used": max(bucket["moves_used"]) if bucket["moves_used"] else None,
            }
        )
    return {
        "schema": "v14-map22-instances-1",
        "runs": len(rows),
        "by_bucket": summary,
        "oracle": [_oracle(seed) for seed in (0, 1, 2, 3)],
        "note": (
            "只用公开轨迹字段（current_sign / result / moves_used / ruin_recorded）；"
            "不读隐藏真值，不重跑任何局。"
        ),
    }

def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None

def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# MAP-22 实例差异归因（只读公开轨迹）",
        "",
        f"- 参与分析的局数：{report['runs']}（`memory.v2`，全部 seed × 臂 × 预算）",
        f"- {report['note']}",
        "",
        "## 1. 每个 seed 的最优解规模（客观难度基线）",
        "",
        "| seed | 最优动作数 | 最优移动数 | 移动预算 |",
        "|---:|---:|---:|---:|",
    ]
    for item in report["oracle"]:
        lines.append(
            f"| {item['seed']} | {item['oracle_actions']} | {item['oracle_moves']} | 44 |"
        )
    lines += [
        "",
        "> 4 个 seed 的最优移动数都在 10–14 步，远低于 44 步预算 —— "
        "所以失败不是「路太长」，而是「走错路 / 折返太多」。",
        "",
        "## 2. 按 seed × 臂聚合（公开轨迹）",
        "",
        "| 分桶 | 局数 | 成功 | 平均决策 | 平均被拒移动 | 平均折返 | 平均发现路标 "
        "| 平均重复访问步 | 平均 route_recall | 最大已用移动 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["by_bucket"]:
        lines.append(
            f"| `{row['key']}` | {row['runs']} | {row['successes']} | "
            f"{row['mean_decisions']} | {row['mean_moves_rejected']} | "
            f"{row['mean_backtracks']} | {row['mean_distinct_signs']} | "
            f"{row['mean_revisit_steps']} | {row['mean_route_recall']} | "
            f"{row['max_moves_used']} |"
        )
    lines += [
        "",
        "## 3. 读法",
        "",
        "- `route_recall` 上升说明路线被完整写进公开记忆（机制成立）；",
        "- 若某 seed 的两臂在「平均折返 / 重复访问」上没有差别，说明该实例的失败"
        "不是「记不住路」，而是别的原因（例如目标顺序或遗迹判定）；",
        "- 这张表只能给出**关联**，不能证明因果：样本来自同一个模型、同一批预算。",
        "",
    ]
    return "\n".join(lines)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v14")
    args = parser.parse_args()
    report = collect()
    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "map22-instances.md").write_text(
            markdown(report), encoding="utf-8", newline="\n"
        )
        (args.out / "map22-instances.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(
        json.dumps(
            {
                "runs": report["runs"],
                "buckets": [row["key"] for row in report["by_bucket"]],
                "written": str(args.out / "map22-instances.md") if args.write else None,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())