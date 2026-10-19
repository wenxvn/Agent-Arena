"""Batch 8/9 报告生成器：``docs/v10/mimo-results.md`` 与 ``docs/v10/cost-ledger-audit.md``。

两部分都只读取 ``runs/v10/mimo/`` 下的既有产物（结果、逐局 trace/judge、append-only 账本），
不发起任何 provider 调用，也不改写历史账本。逐字数字由账本重算，禁止手填。
"""

from __future__ import annotations

import json
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

from agent_arena.v10.evidence_state import is_interrupted
from agent_arena.v10.ledger import global_spend, ledger_spend
from agent_arena.v10.paths import REPO_ROOT, V10_DOCS, V10_RUNS
from agent_arena.v10.runtime.catalog import MAP_IDS, V10_MAPS
from agent_arena.worlds.scenario_v8.catalog import map_metadata

MIMO_ROOT = V10_RUNS / "mimo"
CAP_CNY = Decimal("10")
EARLY_LEDGERS = (
    "ledger.jsonl",
    "ledger_supplement_001.jsonl",
    "ledger_supplement_002.jsonl",
    "ledger_supplement_003.jsonl",
    "ledger_supplement_004.jsonl",
)

GROUP_OF_SEED_TAG = {
    "p0": "P0 五图",
    "castle": "古堡三图",
    "interface": "接口七图",
    "ext": "扩展八图",
    "i2": "接口修复重跑（MAP-18/19/20/28）",
    "j2": "接口补全重跑（MAP-20 公开规则）",
    "k2": "MAP-05 原生首测",
    "k2b": "MAP-05 契约补区间重跑",
    "l2": "MAP-02 原生首测",
}


def _load_results() -> list[dict[str, Any]]:
    path = MIMO_ROOT / "results.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = list(payload.values()) if isinstance(payload, dict) else list(payload)
    rows.sort(key=lambda row: (str(row["map_id"]), int(row.get("environment_seed", 0))))
    return rows


def _group_of(row: dict[str, Any]) -> str:
    if row.get("group"):
        return str(row["group"])
    run_id = str(row.get("run_id", ""))
    for tag in ("castle", "interface", "ext", "p0"):
        if run_id.endswith(f"-{tag}") or run_id.endswith(f"-{tag}-r2"):
            return tag
    return "p0"


def _ledger_files() -> list[Path]:
    return sorted(MIMO_ROOT.glob("ledger*.jsonl"))


def _ledger_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _ledger_files():
        settled, pending, requests = ledger_spend(path)
        events = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        closed = next(
            (event for event in events if event["event"] == "experiment_closed"), None
        )
        episodes = sorted({str(event["episode_id"]) for event in events if event.get("episode_id")})
        rows.append(
            {
                "name": path.name,
                "settled": settled,
                "pending": pending,
                "requests": requests,
                "episodes": episodes,
                "closed_reason": closed["reason"] if closed else "",
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        )
    return rows


def _episode_costs() -> dict[str, dict[str, Any]]:
    """逐局请求数 / token / 成本（跨所有账本求和）。"""

    totals: dict[str, dict[str, Any]] = {}
    for path in _ledger_files():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            event = json.loads(line)
            episode_id = event.get("episode_id")
            if not isinstance(episode_id, str):
                continue
            row = totals.setdefault(
                episode_id,
                {"requests": 0, "failed": 0, "input": 0, "output": 0, "cost": Decimal(0)},
            )
            if event["event"] == "request_settled":
                row["requests"] += 1
                row["input"] += int(event.get("input_tokens") or 0)
                row["output"] += int(event.get("output_tokens") or 0)
                row["cost"] += Decimal(str(event.get("actual_cost", "0")))
            elif event["event"] == "request_failed":
                row["failed"] += 1
    return totals


def _fmt(value: Decimal) -> str:
    return f"{value:.8f}"


# --------------------------------------------------------------------- results
def render_results() -> str:
    rows = _load_results()
    costs = _episode_costs()
    ledger_rows = _ledger_rows()
    settled = sum((row["settled"] for row in ledger_rows), Decimal(0))
    pending = sum((row["pending"] for row in ledger_rows), Decimal(0))
    by_group: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_group.setdefault(_group_of(row), []).append(row)
    lines = [
        "# V10 Batch 8：有界 MiMo 复测结果",
        "",
        "- 由 `python -m agent_arena.v10.mimo_report` 从 `runs/v10/mimo/` 逐字重算，禁止手填。",
        "- 模型：`mimo-v2.6-flash`；temperature=0；reasoning 关闭；每次请求先前预留、按供应商",
        "  usage 结算；未知消费立即封账（保留预留，**不按 0 计**）。",
        f"- 全局上限 CNY {CAP_CNY}；已结算 **CNY {_fmt(settled)}**；未知/未结预留 "
        f"**CNY {_fmt(pending)}**；合计占用 **CNY {_fmt(settled + pending)}**。",
        "- 每图 3 个环境 seed、单一 replicate；`n=3` 只作描述，不作显著性断言，也不做跨模型排名。",
        "",
        "## 1. 覆盖与账本",
        "",
        "| 账本 | 请求 | 结算 CNY | 未结预留 CNY | 关闭原因 | sha256（前 12 位） |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in ledger_rows:
        lines.append(
            f"| `{row['name']}` | {row['requests']} | {_fmt(row['settled'])} | "
            f"{_fmt(row['pending'])} | {row['closed_reason'] or '—'} | `{row['sha256'][:12]}` |"
        )
    lines += [
        "",
        "## 2. 分组结果（仅统计有效局）",
        "",
        "| 分组 | 有效局 | 成功 | 成功率 | 中断保留 | 结算 CNY |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for group in ("p0", "castle", "interface", "ext", "i2", "j2", "k2", "k2b", "l2"):
        items = by_group.get(group, [])
        if not items:
            continue
        valid = [row for row in items if not is_interrupted(row)]
        cost = sum(
            (costs.get(str(row["run_id"]), {}).get("cost", Decimal(0)) for row in items), Decimal(0)
        )
        successes = sum(1 for row in valid if row.get("success"))
        rate = f"{successes / len(valid):.3f}" if valid else "—"
        lines.append(
            f"| {GROUP_OF_SEED_TAG.get(group, group)} | {len(valid)} | {successes} | "
            f"{rate} | {len(items) - len(valid)} | {_fmt(cost)} |"
        )
    lines += [
        "",
        "## 3. 逐图逐 seed",
        "",
        "| 图 | 世界 | 难度 | seed | run_id | 结局 | 决策数 | 主指标 | 机制触发 | CNY | 有效 |",
        "|---|---|---|---:|---|---|---:|---|---|---:|---|",
    ]
    for row in rows:
        meta = map_metadata(str(row["map_id"]))
        episode_cost = costs.get(str(row["run_id"]), {}).get("cost", Decimal(0))
        lines.append(
            f"| {row['map_id']} | {meta['world']} | {meta['level']} | "
            f"{row.get('environment_seed')} | `{row['run_id']}` | "
            f"{row.get('termination')} | {row.get('decision_count')} | "
            f"{row.get('primary_metric_value')} | {row.get('mechanism_triggered')} | "
            f"{_fmt(episode_cost)} | {'否' if is_interrupted(row) else '是'} |"
        )
    taxonomy: dict[str, int] = {}
    for row in rows:
        outcome = str(row.get("outcome"))
        taxonomy[outcome] = taxonomy.get(outcome, 0) + 1
    lines += [
        "",
        "## 4. 结局分类（V10 首次真实归因）",
        "",
        "| outcome | 局数 |",
        "|---|---:|",
    ]
    for outcome, count in sorted(taxonomy.items()):
        lines.append(f"| `{outcome}` | {count} |")
    successes = sum(1 for row in rows if row.get("success"))
    valid_rows = [row for row in rows if not is_interrupted(row)]
    valid_successes = sum(1 for row in valid_rows if row.get("success"))
    interrupted = [row for row in rows if is_interrupted(row)]
    retries = [row for row in rows if str(row.get("run_id", "")).endswith("-r2")]
    fallback = sorted(set(MAP_IDS) - set(V10_MAPS))
    lines += [
        "",
        f"- 有效局成功 **{valid_successes}/{len(valid_rows)}**；其余为机制失败/决策预算耗尽。",
        f"- 结论范围：本矩阵只覆盖 V10 原生图；{len(fallback)} 张 V8 回退图",
        f"  （{'、'.join(fallback)}）仍有 3-seed 缺口，见 `validated-regression.md`，",
        "  不得据此声称 30/30 的 MiMo 多 seed 覆盖。",
        "",
        "## 5. 中断与补跑（全部保留，不覆盖）",
        "",
        "| run_id | 图 | seed | 结局 | 决策数 | 处置 |",
        "|---|---|---:|---|---:|---|",
    ]
    for row in interrupted:
        lines.append(
            f"| `{row['run_id']}` | {row['map_id']} | {row.get('environment_seed')} | "
            f"{row.get('outcome')} | {row.get('decision_count')} | 保留记录，"
            "不计入该 seed 有效证据；按预登记规则另开账本、以新 run_id 补跑 |"
        )
    if not interrupted:
        lines.append("| — | — | — | — | — | 无中断 |")
    lines += [
        "",
        "补跑局（`-r2`，新 run_id + 原因已在 `mimo-preregistration.json` 登记）：",
        "",
        "| run_id | 图 | seed | 结局 | 决策数 |",
        "|---|---|---:|---|---:|",
    ]
    for row in retries:
        lines.append(
            f"| `{row['run_id']}` | {row['map_id']} | {row.get('environment_seed')} | "
            f"{row.get('termination')} | {row.get('decision_count')} |"
        )
    lines += [
        "",
        "另有阶段 3（`-i2`）接口修复后的同图全 seed 重跑：见 DCR-V10-24 与"
        " `mimo-preregistration.json` 的 `phase_3_interface_fix`。",
        "阶段 3 与阶段 1/2 的同图同 seed 只作“接口修复前后”的配对描述，不称严格同条件 A/B。",
        "",
    ]
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------- cost
def render_cost_audit() -> str:
    ledger_rows = _ledger_rows()
    rows = _load_results()
    costs = _episode_costs()
    settled, pending, requests = global_spend(_ledger_files())
    lines = [
        "# V10 成本与账本审计（Batch 8）",
        "",
        "- 由 `python -m agent_arena.v10.mimo_report` 生成；数字来自 append-only 账本重算。",
        f"- 全局上限 CNY {CAP_CNY}；结算 **CNY {_fmt(settled)}**；未知/未结预留 "
        f"**CNY {_fmt(pending)}**；合计 **CNY {_fmt(settled + pending)}**；"
        f"剩余 **CNY {_fmt(CAP_CNY - settled - pending)}**。",
        f"- 累计请求预留事件：{requests}。",
        "",
        "## 1. 逐账本",
        "",
        "| 账本 | 字节 | 请求 | 结算 CNY | 未结预留 CNY | 局数 | 关闭原因 | sha256 |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in ledger_rows:
        lines.append(
            f"| `{row['name']}` | {row['bytes']} | {row['requests']} | {_fmt(row['settled'])} | "
            f"{_fmt(row['pending'])} | {len(row['episodes'])} | {row['closed_reason'] or '—'} | "
            f"`{row['sha256']}` |"
        )
    lines += [
        "",
        "## 2. 未知消费与封账事件",
        "",
        "| 账本 | 关闭原因 | 处理 |",
        "|---|---|---|",
    ]
    for row in ledger_rows:
        if not row["closed_reason"]:
            continue
        reason = row["closed_reason"]
        handling = {
            "UNKNOWN_PROVIDER_SPEND": "保留全额预留、停止自动调用，人工审计后另开账本",
            "PROVIDER_USAGE_OUTSIDE_REGISTERED_CAP": (
                "保留未结预留；定位为早期 runner 把完整 Observation 写入 history，"
                "修复后新 run_id 补跑"
            ),
        }.get(reason, "保留账本，人工审计")
        lines.append(f"| `{row['name']}` | `{reason}` | {handling} |")
    lines += [
        "",
        "## 3. 逐局成本",
        "",
        "| run_id | 请求 | 失败请求 | 输入 token | 输出 token | CNY |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        item = costs.get(str(row["run_id"]))
        if not item:
            continue
        lines.append(
            f"| `{row['run_id']}` | {item['requests']} | {item['failed']} | {item['input']} | "
            f"{item['output']} | {_fmt(item['cost'])} |"
        )
    early = [row for row in ledger_rows if row["name"] in EARLY_LEDGERS]
    lines += [
        "",
        "## 4. 规则遵循声明",
        "",
        "- 未拆分账本规避上限：所有 V10 账本（含早期 5 个）都按 `prior_spend` 计入同一次 ¥10 "
        "额度。",
        f"- 早期账本（{len(early)} 个）保留未删："
        + "、".join(f"`{row['name']}`" for row in early)
        + "。",
        "- 未知费用未被当作 0：`UNKNOWN_PROVIDER_SPEND` 的失败请求保留全额预留，直到封账。",
        "- 未调用除 MiMo 之外的任何收费 provider。",
        "",
        "## 5. 复算",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe -m agent_arena.v10.mimo_report",
        "```",
        "",
        f"仓库根：`{REPO_ROOT}`；产物目录：`runs/v10/mimo/`。（`runs/` 默认不纳入 Git。）",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    results = render_results()
    cost = render_cost_audit()
    V10_DOCS.mkdir(parents=True, exist_ok=True)
    (V10_DOCS / "mimo-results.md").write_text(results, encoding="utf-8", newline="\n")
    (V10_DOCS / "cost-ledger-audit.md").write_text(cost, encoding="utf-8", newline="\n")
    print(json.dumps({"results_bytes": len(results), "cost_bytes": len(cost)}))


if __name__ == "__main__":
    main()
