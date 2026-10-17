"""生成 V9 MiMo 结果表（从 episode 目录与账本复算，不复制摘要）。"""

# ruff: noqa: E501 - 文档生成器包含大量中文表格字面量

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V9 = ROOT / "runs" / "v9"
OUTPUT = ROOT / "docs" / "v9" / "mimo-results.md"


def _episode_roots() -> list[Path]:
    roots = [V9 / "experiments" / "episodes"]
    for supplement in sorted(V9.glob("supplement_*")):
        candidate = supplement / "experiments" / "episodes"
        if candidate.is_dir():
            roots.append(candidate)
    return roots


def _ledger_paths() -> list[Path]:
    paths = [V9 / "ledger.jsonl"]
    for supplement in sorted(V9.glob("supplement_*")):
        candidate = supplement / "ledger.jsonl"
        if candidate.is_file():
            paths.append(candidate)
    return paths


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ledger() -> dict:
    settled = []
    failed = []
    closed = []
    reserved = []
    for path in _ledger_paths():
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        settled.extend(event for event in events if event["event"] == "request_settled")
        failed.extend(event for event in events if event["event"] == "request_failed")
        closed.extend(event for event in events if event["event"] == "experiment_closed")
        reserved.extend(event for event in events if event["event"] == "request_reserved")
    by_episode: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for event in settled:
        by_episode[str(event.get("episode_id"))] += Decimal(str(event.get("actual_cost", "0")))
    resolved = {str(event.get("request_id")) for event in [*settled, *failed]}
    pending = sum(
        (
            Decimal(str(event.get("reserved_cost", "0")))
            for event in reserved
            if str(event.get("request_id")) not in resolved
        ),
        Decimal(0),
    )
    settled_total = sum(by_episode.values(), Decimal(0))
    return {
        "settled": str(settled_total),
        "pending": str(pending),
        "projected": str(settled_total + pending),
        "requests": len(settled),
        "failed": len(failed),
        "unknown_spend": sum(1 for event in failed if event.get("unknown_spend")),
        "closed": closed,
        "by_episode": by_episode,
    }


def main() -> None:
    ledger = _ledger()
    manifests = []
    seen: set[str] = set()
    for episode_root in _episode_roots():
        for manifest_path in episode_root.glob("*/episode_manifest.json"):
            manifest = _read_json(manifest_path)
            run_id = manifest["run_id"]
            if run_id in seen:
                continue
            if manifest.get("status") == "running" or "v9_metrics_path" not in manifest:
                continue
            seen.add(run_id)
            metrics_path = Path(manifest["v9_metrics_path"])
            metrics = _read_json(metrics_path) if metrics_path.is_file() else {}
            manifests.append((manifest, metrics))
    manifests.sort(key=lambda item: (item[0]["map_id"], item[0]["arm"], item[0]["replicate_id"]))

    grouped: dict[tuple[str, str], list[tuple[dict, dict]]] = defaultdict(list)
    for manifest, metrics in manifests:
        grouped[(manifest["map_id"], manifest["arm"])].append((manifest, metrics))

    lines = [
        "# V9 有界 MiMo 验证结果",
        "",
        "- 预登记：`docs/v9/mimo-preregistration.json`（manifest hash 见文件）",
        "- 模型：`mimo-v2.6-flash` / temperature 0 / 同实例 seed",
        f"- 账本 settled：**¥{ledger['settled']}**；pending 预留 ¥{ledger['pending']}；"
        f"projected ¥{ledger['projected']}；请求 {ledger['requests']}；失败 {ledger['failed']}；"
        f"unknown spend {ledger['unknown_spend']}；closed={bool(ledger['closed'])}",
        "- 口径：每条件 2 次重复（4 张主修复图）或 1 次（接口图/地板图/旁路图）；"
        "n 很小，只作描述，不做显著性断言。MAP-12 的 `v9_fixed` 臂未完成（provider 不稳定），"
        "因此 MAP-12 只有 `v8_compat` 两局与离线修复证据。逐局权威来源是各 "
        "`episode_manifest.json`；`runs/v9/mimo_results.json` 只保留最后一次执行的摘要。",
        "- 账本事件：主账本在 MAP-12 R1 v8_compat 第 29 次请求、supplement_001 在 "
        "MAP-12 R0 v9_fixed 第 19 次请求均遇到 provider `InternalServerError`，按规则 "
        "`UNKNOWN_PROVIDER_SPEND` 封账；MAP-12 的 v9_fixed 臂两次失败后不再重试，"
        "其余 episode 在 `runs/v9/supplement_002/` 执行。两个旧账本均未重开。",
        "",
        "## 1. 逐局结果",
        "",
        "| map | arm | rep | status | success | 终止原因 | 决策 | 费用 ¥ | 主指标（overlay 优先） |",
        "|---|---|---:|---|---|---|---:|---:|---|",
    ]
    for (map_id, arm), items in sorted(grouped.items()):
        for manifest, metrics in sorted(items, key=lambda item: item[0]["replicate_id"]):
            overlay = metrics.get("overlay") or {}
            projected = metrics.get("metrics") or {}
            chosen = overlay or projected
            rendered = "; ".join(
                f"`{key}`={value.get('value')}"
                for key, value in list(chosen.items())[:2]
            )
            lines.append(
                "| {map} | {arm} | {rep} | {status} | {success} | {reason} | {decisions} | {cost} | {metrics} |".format(
                    map=map_id,
                    arm=arm,
                    rep=manifest["replicate_id"],
                    status=manifest["status"],
                    success=manifest["success"],
                    reason=manifest.get("termination_reason") or "-",
                    decisions=manifest["decision_count"],
                    cost=manifest["usage"]["cost"],
                    metrics=rendered,
                )
            )

    lines.extend(["", "## 2. 同图前后对照", "", "| map | v8_compat | v9_fixed | 变化 |", "|---|---|---|---|"])
    valid_statuses = {"success", "failure", "censored", "decision_budget_reached"}
    for map_id in sorted({key[0] for key in grouped}):
        if (map_id, "v8_compat") not in grouped:
            continue
        pre = grouped[(map_id, "v8_compat")]
        post = grouped[(map_id, "v9_fixed")]
        pre_valid = [(m, x) for m, x in pre if m.get("status") in valid_statuses]
        post_valid = [(m, x) for m, x in post if m.get("status") in valid_statuses]
        pre_unknown = len(pre) - len(pre_valid)
        post_unknown = len(post) - len(post_valid)
        pre_count = sum(1 for m, _ in pre_valid if m["success"])
        post_count = sum(1 for m, _ in post_valid if m["success"])
        pre_success = f"{pre_count}/{len(pre_valid)}" + (
            f"（另有 {pre_unknown} 次 provider 中断）" if pre_unknown else ""
        )
        post_success = f"{post_count}/{len(post_valid)}" + (
            f"（另有 {post_unknown} 次 provider 中断）" if post_unknown else ""
        )
        pre_terms = ", ".join(
            sorted({str(m.get('termination_reason') or m.get('status')) for m, _ in pre_valid})
        )
        post_terms = ", ".join(
            sorted({str(m.get('termination_reason') or m.get('status')) for m, _ in post_valid})
        )
        if not post_valid:
            trend = "无有效对照"
            lines.append(f"| {map_id} | {pre_success}（{pre_terms}） | 无有效 post 局 | {trend} |")
            continue
        trend = "改善" if post_count > pre_count else ("持平" if post_count == pre_count else "变差")
        lines.append(
            f"| {map_id} | {pre_success}（{pre_terms}） | {post_success}（{post_terms}） | {trend} |"
        )

    lines.extend(
        [
            "",
            "## 3. 关键读数",
            "",
            "- **MAP-07**：`v8_compat` 30 决策耗尽、0 次阀门操作；`v9_fixed` 8 决策成功。公开 `control_panel` 后阀门链才真正启动。",
            "- **MAP-10**：0/2 → **2/2**；失败从“未装载”转为完整的装载→发电机→发报链，`fuel_consumed=8`。",
            "- **MAP-11**：0/2 → **2/2**；`abandoned_reachable_targets` 从 1 降到 0，救援链被触发。",
            "- **MAP-26**：0/1（38 决策耗尽、合法率 0.24）→ **1/1**（13 决策、诊断准确率 1、合法率 0.85）。",
            "- **MAP-09**：0/2 → 0/2，但失败从第 2 决策 `SHORT_CIRCUIT` 后移到第 12 决策 `OXYGEN_DEPLETED`；接口修复生效，能力仍未解决。",
            "- **MAP-08**：0/1 → 0/1，但失败从 38 决策耗尽变成 24 决策 `CORE_WATER_LIMIT_EXCEEDED`；模型开始执行机制，仍未完成。",
            "- **MAP-12**：`v8_compat` 两局均 `RESEARCH_TARGET_MISSED`（研究分 0）；`v9_fixed` 未完成（provider 两次 unknown spend），不能宣称在线效果。",
            "- **MAP-06 seed 5**：3 决策 `RESOURCE_EXHAUSTED`，与 seed 0 的 2 决策直达成功形成对照，确认 V8 的 3/3 是实例旁路。",
            "- **MAP-14/18/22/29**：仍在地板/截尾；MAP-14 `query_gap=-3`（从未问询），MAP-18 7 决策 `STATION_CAPACITY_EXCEEDED`，MAP-22/29 决策预算耗尽。",
            "- **MAP-15/21**：MAP-15 11 决策成功（goal 仍泄露规则）；MAP-21 本次 6 决策 `FATAL_ERUPTION`（没有选择直达撤离），说明旁路存在但不等于模型必然使用。",
            "",
            "## 4. 解读与限制",
            "",
            "- 这是 **E3-pilot**：样本小、单实例 seed、模型单一；不构成 V9 主实验或能力排名。",
            "- `v8_compat` 与 `v9_fixed` 的唯一差别是登记过的公开信息补充；规则、动作集、预算、"
            "模型、temperature 相同。",
            "- 失败、截尾、provider 异常与费用全部保留；没有“试到成功为止”。",
            "- 指标并列 V8 旧值与 V9 overlay；overlay 不是 V7 登记指标，不能与旧值相加。",
            "",
            "## 5. 账本",
            "",
            "| 项目 | 值 |",
            "|---|---|",
            f"| settled | ¥{ledger['settled']} |",
            f"| pending reserved | ¥{ledger['pending']} |",
            f"| projected | ¥{ledger['projected']} |",
            f"| requests | {ledger['requests']} |",
            f"| failed | {ledger['failed']} |",
            f"| unknown_spend | {ledger['unknown_spend']} |",
            f"| closed | {bool(ledger['closed'])} |",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT)
    print(f"episodes={len(manifests)} settled={ledger['settled']}")


if __name__ == "__main__":
    main()
