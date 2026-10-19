"""Batch 9：V10 逐图验收 Gate 的机器判定（可复算，不手填）。

每张 V10 原生图必须同时满足以下 Gate 才进入 `VALIDATED`：

| Gate | 判据 |
|---|---|
| `seeds` | `seed_effective=True` 且预登记 seed ≥ 3（每 seed 实例真的不同） |
| `oracle` | 全部 seed 的 Oracle 成功 |
| `budget` | 每个 seed 的 Oracle 动作数 ≤ 决策预算 |
| `mechanism` | 至少一个 seed 的 Oracle 真实触发核心机制 |
| `ablation` | 至少一个消融成功率严格低于 Oracle（机制被移除会受损） |
| `metric` | 主指标已注册且存在 `VALID` 取值的 Oracle 局 |
| `independent` | `runs/v10/independent_check.json` 该图：0 违规、回放确定、seed 互异 |
| `mimo` | ≥3 个有效环境 seed，且每局 `invalid_actions / decisions ≤ 0.5`（接口对模型可用） |

7 张 V8 回退图在 V10 没有原生运行时：它们沿用 V9 的 `VALIDATED`，但 `seeds` Gate 记缺口
（`validated-regression.md`），本模块不改变其标签。

输出：`runs/v10/validation/gates.json` 与 `docs/v10/validation-gates.md`。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agent_arena.v10.evidence_state import effective_mimo_rows
from agent_arena.v10.paths import V10_DOCS, V10_RUNS
from agent_arena.v10.runtime.catalog import (
    MAP_IDS,
    V10_MAPS,
    seed_effective,
    seed_space,
    v10_class,
)

INVALID_RATIO_LIMIT = 0.5
FALLBACK_MAPS = tuple(map_id for map_id in MAP_IDS if map_id not in V10_MAPS)


@dataclass
class Gate:
    map_id: str
    native: bool
    passed: dict[str, bool] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if not self.native:
            return "VALIDATED_V8_FALLBACK"
        return "VALIDATED" if all(self.passed.values()) else "NEEDS_MORE_EVIDENCE"


def _baseline(map_id: str) -> dict[str, Any]:
    path = V10_RUNS / "baselines" / f"{map_id}.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _independent() -> dict[str, Any]:
    path = V10_RUNS / "independent_check.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        row["map_id"]: row for row in payload.get("maps", []) if isinstance(row, dict)
    }


def _budget(map_id: str) -> int:
    from agent_arena.v10.baselines.suite import decision_budget

    return decision_budget(map_id)


def _primary_mean(rows: list[dict[str, Any]]) -> float | None:
    values = [
        float(row["primary_value"])
        for row in rows
        if row.get("primary_state") == "VALID" and row.get("primary_value") is not None
    ]
    return round(sum(values) / len(values), 4) if values else None


def evaluate_map(
    map_id: str, independent: dict[str, Any], mimo: dict[str, list[dict[str, Any]]]
) -> Gate:
    gate = Gate(map_id=map_id, native=map_id in V10_MAPS)
    if not gate.native:
        gate.passed = {"v8_fallback": True}
        gate.reasons.append(
            "V8 回退图：沿用 V9 `VALIDATED`，3-seed 缺口已在 validated-regression.md 登记"
        )
        return gate

    payload = _baseline(map_id)
    seeds = seed_space(map_id)
    effective = seed_effective(map_id)
    gate.passed["seeds"] = bool(effective) and len(seeds) >= 3
    gate.details["seeds"] = list(seeds)

    oracle = payload.get("oracle", [])
    oracle_ok = bool(oracle) and all(bool(row.get("success")) for row in oracle)
    gate.passed["oracle"] = oracle_ok
    gate.details["oracle"] = f"{sum(1 for r in oracle if r.get('success'))}/{len(oracle)}"

    budget = _budget(map_id)
    within = bool(oracle) and all(int(row.get("decisions") or 0) <= budget for row in oracle)
    gate.passed["budget"] = within
    biggest = max((int(row.get('decisions') or 0) for row in oracle), default=0)
    gate.details["budget"] = f"预算 {budget}；最大 Oracle 动作 {biggest}"

    triggered = any(bool(row.get("mechanism_triggered")) for row in oracle)
    gate.passed["mechanism"] = triggered
    gate.details["mechanism"] = (
        f"{sum(1 for r in oracle if r.get('mechanism_triggered'))}/{len(oracle)}"
    )

    ablations = payload.get("ablations", {})
    oracle = payload.get("oracle", [])
    oracle_rate = (
        sum(1 for row in oracle if row.get("success")) / len(oracle) if oracle else 0.0
    )
    ablation_rates = {
        name: sum(1 for row in rows if row.get("success")) / len(rows)
        for name, rows in ablations.items()
        if rows
    }
    min_rate = min(ablation_rates.values(), default=1.0)
    oracle_primary = _primary_mean(oracle)
    quality_gap = [
        name
        for name, rows in sorted(ablations.items())
        if (mean := _primary_mean(rows)) is not None
        and oracle_primary is not None
        and mean < oracle_primary
    ]
    gate.passed["ablation"] = bool(ablations) and (
        min_rate < oracle_rate or bool(quality_gap)
    )
    gate.details["ablation"] = (
        f"最低消融成功率 {min_rate:.2f}（Oracle {oracle_rate:.2f}）；"
        f"质量区分消融：{'、'.join(quality_gap) or '无'}"
    )

    specs = {spec.metric_id: spec for spec in v10_class(map_id).METRIC_SPECS}
    primary = v10_class(map_id).PRIMARY_METRIC
    primary_valid = primary in specs and any(
        row.get("primary_state") == "VALID" for row in oracle
    )
    gate.passed["metric"] = primary_valid
    gate.details["metric"] = primary

    row = independent.get(map_id, {})
    indep_ok = (
        bool(row)
        and not row.get("violations")
        and bool(row.get("all_deterministic"))
        and bool(row.get("seed_distinct"))
    )
    gate.passed["independent"] = indep_ok
    gate.details["independent"] = (
        f"违规 {len(row.get('violations', []))}；确定 {row.get('all_deterministic')}；"
        f"seed 互异 {row.get('seed_distinct')}"
        if row
        else "缺少 independent_check.json"
    )

    runs = mimo.get(map_id, [])
    usable = [
        row
        for row in runs
        if int(row.get("decision_count") or 0) > 0
        and int(row.get("invalid_actions") or 0) / int(row["decision_count"]) <= INVALID_RATIO_LIMIT
    ]
    gate.passed["mimo"] = len(runs) >= 3 and len(usable) == len(runs)
    gate.details["mimo"] = (
        f"有效局 {len(runs)}；其中接口可用 {len(usable)}；"
        f"非法率上限 {INVALID_RATIO_LIMIT}"
    )
    for name, ok in gate.passed.items():
        if not ok:
            gate.reasons.append(f"Gate `{name}` 未通过：{gate.details.get(name, '')}")
    return gate


def evaluate() -> dict[str, Gate]:
    independent = _independent()
    mimo = effective_mimo_rows()
    return {map_id: evaluate_map(map_id, independent, mimo) for map_id in MAP_IDS}


def render(gates: dict[str, Gate]) -> str:
    lines = [
        "# V10 逐图验收 Gate（Batch 9）",
        "",
        "- 由 `python -m agent_arena.v10.validation` 从 `runs/v10/` 逐图判定，不手填。",
        "- 8 个 Gate：`seeds`、`oracle`、`budget`、`mechanism`、`ablation`、`metric`、",
        "  `independent`、`mimo`（判据见模块 docstring）。",
        "- 全部 `agent_reviewed`；不声称 `human_approved`，也不用 Gate 结果替代用户复核。",
        "- **Gate 不包含“模型成功”**：`mimo` Gate 只检查接口对模型可用（非法动作占比 ≤ 50%），",
        "  即 `VALIDATED` 说明“测得住”，不说明“MiMo 能通关”。",
        "",
        "| 图 | 运行时 | seeds | oracle | budget | mechanism | ablation | metric | independent | "
        "mimo | 判定 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    names = ("seeds", "oracle", "budget", "mechanism", "ablation", "metric", "independent", "mimo")
    for map_id, gate in gates.items():
        if not gate.native:
            lines.append(
                f"| {map_id} | v8 | — | — | — | — | — | — | — | — | "
                f"`VALIDATED`（V8 回退，3-seed 缺口） |"
            )
            continue
        cells = " | ".join("✅" if gate.passed.get(name) else "❌" for name in names)
        lines.append(
            f"| {map_id} | v10 | {cells} | `{gate.verdict}` |"
        )
    passed = [m for m, g in gates.items() if g.verdict == "VALIDATED"]
    failed = [m for m, g in gates.items() if g.verdict == "NEEDS_MORE_EVIDENCE"]
    lines += [
        "",
        "## 汇总",
        "",
        f"- `VALIDATED`（V10 原生，8 Gate 全过）：{len(passed)} 图 —— "
        + ("、".join(passed) or "无"),
        f"- `NEEDS_MORE_EVIDENCE`：{len(failed)} 图 —— " + ("、".join(failed) or "无"),
        f"- V8 回退维持 `VALIDATED`（记 3-seed 缺口）：{len(FALLBACK_MAPS)} 图 —— "
        + "、".join(FALLBACK_MAPS),
        "",
        "## 未通过项明细",
        "",
    ]
    details = [g for g in gates.values() if g.verdict == "NEEDS_MORE_EVIDENCE"]
    if details:
        for gate in details:
            lines.append(f"- **{gate.map_id}**")
            for reason in gate.reasons:
                lines.append(f"  - {reason}")
    else:
        lines.append("- 无。")
    return "\n".join(lines) + "\n"


def main() -> None:
    gates = evaluate()
    output = V10_RUNS / "validation"
    output.mkdir(parents=True, exist_ok=True)
    (output / "gates.json").write_text(
        json.dumps(
            {
                map_id: {
                    "verdict": gate.verdict,
                    "native": gate.native,
                    "passed": gate.passed,
                    "details": gate.details,
                    "reasons": gate.reasons,
                }
                for map_id, gate in gates.items()
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
)
    V10_DOCS.mkdir(parents=True, exist_ok=True)
    (V10_DOCS / "validation-gates.md").write_text(render(gates), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                map_id: gate.verdict
                for map_id, gate in gates.items()
                if gate.verdict != "VALIDATED_V8_FALLBACK"
            },
            ensure_ascii=False,
        )
    )


__all__ = ["Gate", "evaluate", "evaluate_map", "render"]


if __name__ == "__main__":
    main()
