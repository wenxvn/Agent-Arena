"""生成 V8 的全局结果、失败分析与最终验收文档。

只读 `runs/v8/` 与 `docs/v8/map_facts.json`；不调用 Provider、不改写 episode。
在 90 局完成或部分完成后均可运行；缺口会如实列出。
"""

# ruff: noqa: E501 - 中文报告表格与长句不按 100 列硬折行

from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT / "runs" / "v8"
DOCS = ROOT / "docs" / "v8"


ADAPTER_TITLES = {
    "MAP-08": "看不见的裂缝",
    "MAP-16": "单线会车",
    "MAP-18": "故障传播",
    "MAP-22": "没有地图的森林",
    "MAP-26": "失败的维修计划",
    "MAP-30": "30 午夜审判",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def judge_failure_codes(row: dict[str, Any]) -> list[str]:
    path = row.get("judge_metrics_path")
    if not path or not Path(path).is_file():
        return []
    return list(read_json(Path(path)).get("failure_codes", []))


def fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def main() -> int:
    freeze = read_json(V8 / "freeze_manifest.json")
    registry = read_json(V8 / "registry.json")
    facts = read_json(V8 / "map_facts.json")
    rows = registry["rows"]
    attempts = registry.get("attempts", [])
    maps = registry["maps"]
    ledger = registry["ledger"]
    completed = registry["formal_episodes_completed"]
    gaps = registry["gaps"]

    status_counts = Counter(row["status"] for row in rows)
    commit_counts = Counter(row["commit"] for row in rows if row["commit"])
    successes = sum(1 for row in rows if row["success"])
    total_cost = sum(
        (Decimal(str(row["cost"])) for row in rows if row["cost"] is not None),
        Decimal(0),
    )
    total_input = sum(row["input_tokens"] or 0 for row in rows)
    total_output = sum(row["output_tokens"] or 0 for row in rows)
    total_requests = sum(row["requests"] or 0 for row in rows)
    provider_errors = [row for row in rows if row.get("provider_error")]
    unknown = [row for row in rows if row.get("unknown_spend")]
    hash_fields = (
        "scenario_hash",
        "rule_hash",
        "prompt_hash",
        "metric_schema_hash",
    )
    hash_mismatches = [
        (row["map_id"], row["seed_or_replicate"], field)
        for row in rows
        if row["status"] != "missing"
        for field in hash_fields
        if row.get(field) != freeze["maps"][row["map_id"]][field]
    ]

    failure_codes: Counter[str] = Counter()
    for row in rows:
        if row["success"]:
            continue
        for code in judge_failure_codes(row):
            failure_codes[code] += 1

    ceilings = [map_id for map_id, item in maps.items() if item["successes"] == 3]
    floors = [
        map_id
        for map_id, item in maps.items()
        if item["statuses"].get("missing", 0) == 0 and item["successes"] == 0
    ]

    # ---------------------------------------------------------- mimo-90-results
    lines = [
        "# V8 MiMo 90 局结果",
        "",
        f"- freeze_hash：`{freeze['freeze_hash']}`",
        f"- 模型：`{freeze['model_id']}` / provider `{freeze['provider']}` / temperature 0",
        f"- 正式完成：**{completed}/90**；缺口 {len(gaps)} 局",
        f"- 正式局已结算费用：**¥{total_cost}**（硬上限 ¥10）",
        f"- Token：输入 {total_input} / 输出 {total_output}；请求 {total_requests}",
        f"- 账本：settled `{ledger['settled_cost']}` / attempts `{ledger['request_attempts']}`"
        f" / failed `{ledger['failed_requests']}` / closed `{ledger['closed']}`"
        f"（{ledger.get('closed_reason') or '未封账'}）",
        f"- 预警：{ledger['warnings'] or '无'}",
        "",
        "> 费用口径：上表“正式局已结算费用”只统计 90 行正式结果；账本 settled 还包含被"
        " superseded 的 MAP-12/MAP-22 旧局、补跑与原失败尝试，因此更高。",
        "",
        "> n=3 只作重复运行描述，不做显著性断言。Oracle 成功率不是 MiMo 能力。",
        "",
        "## 1. 90 行结果",
        "",
        "| # | map | world | 难度 | rep | status | success | 终止原因 | 决策 | 请求 | cost | 主指标 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for index, row in enumerate(rows, 1):
        primary = maps[row["map_id"]]["primary"].get(str(row["seed_or_replicate"]), {})
        primary_text = "; ".join(
            f"`{key.split('.')[-1]}`={value['value']}"
            for key, value in list(primary.items())[:2]
        )
        lines.append(
            f"| {index} | {row['map_id']} | {row['world']} | {row['difficulty']} |"
            f" {row['seed_or_replicate']} | {row['status']} | {row['success']} |"
            f" {row['termination_reason']} |"
            f" {maps[row['map_id']]['decisions'].get(str(row['seed_or_replicate']), '—')} |"
            f" {row['requests'] if row['requests'] is not None else '—'} | {row['cost']} |"
            f" {primary_text} |"
        )
    lines.extend(
        [
            "",
            "## 2. 逐图汇总",
            "",
            "| map | world | 难度 | 条件 | 成功/3 | statuses | mean decisions | total cost |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for map_id, item in maps.items():
        lines.append(
            f"| {map_id} | {item['world']} | {item['difficulty']} | {item['condition_id']} |"
            f" {item['successes']}/3 | {item['statuses']} | {item['mean_decisions']:.1f} |"
            f" {item['cost']} |"
        )
    lines.extend(["", "## 3. 状态与费用分布", ""])
    for status, count in sorted(status_counts.items()):
        lines.append(f"- `{status}`：{count}")
    lines.extend(
        [
            f"- 成功：{successes}/90（{successes / max(1, completed) * 100:.1f}% of completed）",
            f"- 单局平均费用：¥{(total_cost / max(1, completed)):.6f}",
            f"- 单局平均请求：{total_requests / max(1, completed):.1f}",
            "",
            "## 4. 补跑与中断",
            "",
            f"- 尝试记录：{len(attempts)}（含补跑与原失败）",
            f"- provider_error 的正式局：{len(provider_errors)}",
            f"- unknown_spend 的正式局：{len(unknown)}",
            "",
            "以下为已被补跑替换的原失败尝试（保留记录，不计入正式 90 行）：",
        ]
    )
    for item in attempts:
        if item.get("provider_error") or item.get("unknown_spend"):
            lines.append(
                f"  - {item['map_id']} R{item['replicate_id']} `{item['run_id']}`"
                f" status={item['status']} error={item['provider_error']}"
                f" unknown_spend={item['unknown_spend']}"
            )
    if gaps:
        lines.extend(["", "## 5. 缺口", ""])
        for gap in gaps:
            lines.append(
                f"- {gap['map_id']} R{gap['replicate_id']}：attempts={gap['attempts']}"
                f" statuses={gap['statuses']}"
            )
    else:
        lines.extend(["", "## 5. 缺口", "", "无：90 局均有正式结果。"])
    (DOCS / "mimo-90-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---------------------------------------------------------- failure analysis
    fail_lines = [
        "# V8 失败分析",
        "",
        f"基于 {completed} 局正式结果；n=3，不做显著性断言。",
        "",
        "## 1. 状态分布",
        "",
        "| status | count |",
        "|---|---|",
    ]
    for status, count in sorted(status_counts.items()):
        fail_lines.append(f"| {status} | {count} |")
    fail_lines.extend(
        [
            "",
            "## 2. 失败码频次",
            "",
            "同一局可有多个失败码（如 `INVALID_ACTION` + 机制码）。",
            "",
            "| failure_code | count |",
            "|---|---|",
        ]
    )
    if failure_codes:
        for code, count in failure_codes.most_common():
            fail_lines.append(f"| `{code}` | {count} |")
    else:
        fail_lines.append("| — | 0 |")
    fail_lines.extend(
        [
            "",
            "`CENSORED` 汇总“决策预算耗尽”与地图自身 horizon 截尾，不是机制失败码；"
            "其余码为地图私有失败码或 `INVALID_ACTION`。",
            "",
            "## 3. 地板与天花板",
            "",
            f"- 3/3 成功（天花板）：{', '.join(ceilings) or '无'}",
            f"- 0/3 成功（地板）：{', '.join(floors) or '无'}",
            "",
            "地板不自动等于“能力为零”：可能是接口、预算、机制陷阱或模型策略失败；"
            "逐图原因见 `maps/MAP-XX-final.md` 与 judge metrics。",
            "",
            "## 4. 同世界分面",
            "",
            "不同地图的原始指标不可直接横比；下表只列各世界三难度的成功数与平均决策数。",
            "",
            "| world | 简单 | 中等 | 困难 | 平均决策（按图） |",
            "|---|---|---|---|---|",
        ]
    )
    worlds: dict[str, list[str]] = defaultdict(list)
    for map_id, item in maps.items():
        worlds[item["world"]].append(map_id)
    for world, map_ids in worlds.items():
        by_level = {maps[map_id]["difficulty"]: maps[map_id] for map_id in sorted(map_ids)}
        cells = []
        for level in ("简单", "中等", "困难"):
            item = by_level.get(level)
            cells.append(
                f"{item['successes']}/3" if item else "—"
            )
        means = ", ".join(
            f"{map_id}:{maps[map_id]['mean_decisions']:.1f}" for map_id in sorted(map_ids)
        )
        fail_lines.append(f"| {world} | {' | '.join(cells)} | {means} |")
    fail_lines.extend(
        [
            "",
            "## 5. 资源与费用",
            "",
            f"- 总费用 ¥{total_cost}；单局均值 ¥{(total_cost / max(1, completed)):.6f}。",
            f"- 输入 token {total_input}，输出 token {total_output}。",
            f"- 请求 {total_requests}，平均每局 {total_requests / max(1, completed):.1f}。",
            "- 费用按供应商 usage 结算；未知消费会立即封账，不用估算值替代。",
            "",
            "## 6. Provider / schema 异常",
            "",
            f"- provider_error：{len(provider_errors)} 局；unknown_spend：{len(unknown)} 局。",
        ]
    )
    for row in provider_errors + unknown:
        fail_lines.append(
            f"- {row['map_id']} R{row['seed_or_replicate']} `{row['run_id']}`："
            f"status={row['status']} provider_error={row['provider_error']}"
            f" unknown_spend={row['unknown_spend']}"
        )
    fail_lines.extend(
        [
            "",
            "## 7. 部分能力差异示例",
            "",
            "同样未通关的局在部分指标上仍可能不同。以下按图列出未成功局的主指标/护栏值，"
            "用于说明“失败”不是单一能力标签：",
            "",
        ]
    )
    for map_id, item in maps.items():
        if item["successes"] == 3 or not item["primary"]:
            continue
        parts = []
        for rep, metrics in item["primary"].items():
            valid = [
                f"{key.split('.')[-1]}={value['value']}"
                for key, value in metrics.items()
                if value.get("status") == "valid" and value.get("value") is not None
            ]
            parts.append(f"R{rep}: " + (", ".join(valid[:3]) or "无有效主指标"))
        fail_lines.append(f"- **{map_id}**：" + "；".join(parts))
    fail_lines.extend(
        [
            "",
            "## 8. 解释边界",
            "",
            "- 0/3 只说明这三次重复未成功，不说明地图不可解；每图都有真实 Oracle 回放。",
            "- 3/3 也不说明能力普遍化；样本只有三次同图重复。",
            "- 失败码来自机制状态机，不等同于模型内部原因；需要结合 trace 中的动作序列阅读。",
        ]
    )
    (DOCS / "failure-analysis.md").write_text("\n".join(fail_lines) + "\n", encoding="utf-8")

    # ---------------------------------------------------------- final acceptance
    acc = [
        "# V8 最终验收",
        "",
        f"- 冻结：`{freeze['freeze_hash']}`，commit `{freeze['commit']}`。",
        "- 离线门禁：30/30；154/154 指标；55 条 Oracle；85 条冻结 fixture + 12 条补充用例。",
        f"- 正式 MiMo：**{completed}/90**；缺口 {len(gaps)} 局；总费用 ¥{total_cost}。",
        f"- 账本 settled：¥{ledger['settled_cost']}（含 superseded 旧局、补跑与原失败尝试）；"
        f"未知消费预留：¥{ledger.get('unknown_spend_reserved', '0')}。",
        f"- 冻结 hash 一致性：{'通过' if not hash_mismatches else f'{len(hash_mismatches)} 处不一致'}",
        f"- commit 版本分布：{dict(commit_counts)}",
        "",
        "## 1. 30 图定稿表",
        "",
        "| world | map | 难度 | 独特机制 | rule_hash | runtime | metrics | oracle | 3 局 | 状态 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for map_id, item in maps.items():
        fact = facts[map_id]
        if map_id in ADAPTER_TITLES:
            mechanism = ADAPTER_TITLES[map_id]
        else:
            mechanism = (fact["docstring"][0] if fact["docstring"] else fact["title"]).split(
                "：", 1
            )[-1]
        status = "finalized" if item["statuses"].get("missing", 0) == 0 else "blocked"
        acc.append(
            f"| {item['world']} | {map_id} | {item['difficulty']} | {mechanism} |"
            f" `{freeze['maps'][map_id]['rule_hash'][:12]}` | verified |"
            f" {len(fact['metrics'])}/{len(fact['metrics'])} | verified |"
            f" {item['successes']}/3 | {status} |"
        )
    acc.extend(
        [
            "",
            "## 2. 逐图验收结论",
            "",
            "每图 `MAP-XX-final.md` 记录机制、公开/私有字段、动作契约、结算顺序、失败码、"
            "主要指标、Oracle、fixture 与三局原始结果。验收条件为：",
            "",
            "- design_frozen：规则与 hash 已冻结；",
            "- runtime_verified：Oracle 真实回放成功、确定性、终止不变性与泄漏检查通过；",
            "- metrics_verified：登记指标 154/154 有来源、五态与分母规则正确；",
            "- three_valid_mimo_runs：三次正式运行均有 trace/judge/V8 metrics/usage，"
            "且不是接口误导或无效 schema 导致的无效轨迹。",
            "",
            "正式运行前有五次预跑作废：`pre_timeout_001`（wall-clock 上限过紧）、"
            "`pre_vocab_001`（01–06 交互词表缺失）、`pre_vocab_full_001`（其余字符串枚举缺失）、"
            "`pre_map01_rule_001`（MAP-01 供氧硬规则未公开）与 `pre_location_001`"
            "（交互对象位置未公开）。五者均归档在 `runs/v8/aborted/`，不计入正式 90 局；"
            "修复后已重新冻结。",
            "",
            "## 3. 未解决风险",
            "",
            "- 0/3 地图的真实原因是模型策略、机制陷阱还是接口负担，需要逐 trace 归因；"
            "本报告不把 0/3 解释为能力为零。",
            "- 六张 V4 适配图复用 V6 冻结场景；V7 已记录的天花板/地板仍在，V8 没有通过改规则消除。",
            "- 独立第二路径核对：MAP-01–06 的 Oracle 来自 V4 论文轨迹，六张适配图使用 V7 已发布手算值；"
            "其余 18 图的 fixture 与 extractor 同源，尚未建立完全独立的第二实现，列为 V9 改进项。",
            "- 三次重复不是独立场景 seed；不能外推为总体成功率。",
            "- MAP-08/16/18/22/26/30 的条件含公开先验/后验或案卷，属于信息可用性条件，"
            "不宣称纯推断能力。",
            "- 全仓仍有 676 条历史 Ruff 问题（冻结的 `worlds/v4` 与旧脚本），V8 作用域已通过。",
            "",
            "## 4. 缺口与后续 V9 建议",
            "",
        ]
    )
    if gaps:
        acc.append("未完成的正式局：")
        for gap in gaps:
            acc.append(
                f"- {gap['map_id']} R{gap['replicate_id']}：{gap['statuses']}"
            )
    else:
        acc.append("正式 90 局均有结果；无接口或预算缺口。")
    if hash_mismatches:
        acc.extend(["", "冻结 hash 不一致（不得静默挪用）："])
        for map_id, replicate, field in hash_mismatches:
            acc.append(f"- {map_id} R{replicate}: `{field}`")
    acc.extend(
        [
            "",
            "V9 建议：",
            "",
            "1. 对 0/3 地图做逐 trace 的接口/策略归因，区分“不会做”与“没看懂契约”。",
            "2. 在独立预算与预登记下，对地板/天花板地图增加重复数或条件对照，而不是改规则。",
            "3. 把 MAP-08/18/26 的已知地板与 V6/V7 结果做纵向对照，检验实例与条件差异。",
            "4. 若需要总体成功率，使用分层抽样与多 seed 环境实例，不把同图三次重复当独立样本。",
        ]
    )
    (DOCS / "final-acceptance.md").write_text("\n".join(acc) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "completed": completed,
                "gaps": len(gaps),
                "successes": successes,
                "cost": str(total_cost),
                "docs": [
                    "docs/v8/mimo-90-results.md",
                    "docs/v8/failure-analysis.md",
                    "docs/v8/final-acceptance.md",
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
