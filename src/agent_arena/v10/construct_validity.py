"""Batch 9：``docs/v10/construct-validity.md`` 生成器。

只读 ``evidence_state.DECISIONS``、``runs/v10/baselines/`` 与 ``runs/v10/mimo/``，
把“构念标签（FORCED/OPTIONAL/BYPASS/BLOCKED）”与“效度状态
（VALIDATED/NEEDS_MORE_EVIDENCE/NEEDS_REDESIGN/BLOCKED）”两个**独立维度**并列报告，
并给出每个标签的绕过反例证据（消融成功率）与真实模型证据。
"""

from __future__ import annotations

import json
from typing import Any

from agent_arena.v10.evidence_state import DECISIONS, mimo_summary
from agent_arena.v10.paths import V10_DOCS, V10_RUNS
from agent_arena.v10.runtime.catalog import V10_MAPS
from agent_arena.worlds.scenario_v8.catalog import map_metadata

CONSTRUCT_MEANING = {
    "FORCED": "核心机制是通关必要条件（移除即失败）",
    "OPTIONAL": "机制影响质量/成本/风险而非通过与否（须有连续质量指标）",
    "BYPASS": "存在绕过核心机制的路径（V10 目标为清零）",
    "BLOCKED": "接口/规则/预算阻止正常测量",
}


def _baseline(map_id: str) -> dict[str, Any]:
    path = V10_RUNS / "baselines" / f"{map_id}.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _rate(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "—"
    return f"{sum(1 for row in rows if row.get('success'))}/{len(rows)}"


def rows() -> list[dict[str, str]]:
    mimo = mimo_summary()
    output: list[dict[str, str]] = []
    for map_id in sorted(DECISIONS):
        decision = DECISIONS[map_id]
        meta = map_metadata(map_id)
        payload = _baseline(map_id)
        ablations = payload.get("ablations", {})
        ablation_text = "；".join(
            f"`{name}` {_rate(rows_)}" for name, rows_ in sorted(ablations.items())
        )
        worst = "—"
        if ablations:
            rates = [
                sum(1 for row in rows_ if row.get("success")) / len(rows_)
                for rows_ in ablations.values()
                if rows_
            ]
            worst = f"{min(rates):.2f}–{max(rates):.2f}" if rates else "—"
        evidence = mimo.get(map_id)
        mimo_text = (
            f"{evidence['successes']}/{evidence['runs']}" if evidence else "未运行"
        )
        output.append(
            {
                "map_id": map_id,
                "world": str(meta["world"]),
                "construct": decision.construct_status,
                "validity": decision.validity_status,
                "runtime": "v10" if map_id in V10_MAPS else "v8",
                "ablations": ablation_text or "—",
                "worst": worst,
                "mimo": mimo_text,
                "decision": decision.decision,
            }
        )
    return output


def render() -> str:
    table = rows()
    lines = [
        "# V10 构念效度",
        "",
        "- 由 `python -m agent_arena.v10.construct_validity` 生成；数字来自 `runs/v10/`。",
        "- 两个维度**互不替代**：构念标签说明“机制是否通关必要条件”，效度状态说明“测量是否可信”。",
        "- 全部为 `agent_reviewed`；不声称 `human_approved`。",
        "",
        "## 1. 标签定义",
        "",
        "| 标签 | 含义 |",
        "|---|---|",
    ]
    for label, meaning in CONSTRUCT_MEANING.items():
        lines.append(f"| `{label}` | {meaning} |")
    lines += [
        "",
        "## 2. 逐图",
        "",
        "| 图 | 世界 | 构念 | 效度 | 运行时 | 消融证据 | 消融率区间 | MiMo | 裁定 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in table:
        lines.append(
            f"| {row['map_id']} | {row['world']} | {row['construct']} | {row['validity']} | "
            f"`{row['runtime']}` | {row['ablations']} | {row['worst']} | {row['mimo']} | "
            f"{row['decision']} |"
        )
    counts: dict[str, int] = {}
    for row in table:
        counts[row["construct"]] = counts.get(row["construct"], 0) + 1
    validity: dict[str, int] = {}
    for row in table:
        validity[row["validity"]] = validity.get(row["validity"], 0) + 1
    lines += [
        "",
        "## 3. 汇总",
        "",
        "| 维度 | 状态 | 图数 |",
        "|---|---|---:|",
    ]
    for label in ("FORCED", "OPTIONAL", "BYPASS", "BLOCKED"):
        lines.append(f"| 构念 | {label} | {counts.get(label, 0)} |")
    for label in ("VALIDATED", "NEEDS_MORE_EVIDENCE", "NEEDS_REDESIGN", "BLOCKED"):
        lines.append(f"| 效度 | {label} | {validity.get(label, 0)} |")
    lines += [
        "",
        "## 4. 解释",
        "",
        "- `OPTIONAL` 不等于“指标虚设”：MAP-26 的诊断被裁定为 OPTIONAL，但备件/换错次数/精度",
        "  等连续指标仍能区分盲换与真诊断。",
        "- `BYPASS` 标签在 V10 全部清零的依据是逐图消融成功率（见 `baseline-results.md`）与",
        "  `decision-register.md` 的反例测试，而不是通关率变化。",
        "- 30 张图都已有 V10 原生运行时（含 MAP-16，DCR-V10-36），V8 回退数为 0；",
        "  环境 seed 与实例差异见 `validated-regression.md`。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    V10_DOCS.mkdir(parents=True, exist_ok=True)
    (V10_DOCS / "construct-validity.md").write_text(render(), encoding="utf-8", newline="\n")
    print(V10_DOCS / "construct-validity.md")


if __name__ == "__main__":
    main()
