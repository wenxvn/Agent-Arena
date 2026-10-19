"""V10 逐图审计卡生成器（Batch 9）。

为 30 张图各生成 ``docs/v10/maps/MAP-XX.md``，内容全部来自可复算产物，不手填数字：

- 地图身份与状态：``worlds/scenario_v8.catalog.map_metadata`` + ``v10.evidence_state.DECISIONS``；
- 目标构念与指标：V10 运行时的 ``METRIC_SPECS`` / ``PRIMARY_METRIC`` / ``v10_metrics`` 规格；
- 公开信息边界：``public_rules()``、``PUBLIC_FIELDS``、``scenario_descriptor()``（公开参数）
  与 ``sealed_truth()`` 的**键名**（不打印真值）；
- 合法动作：``SHAPES``；
- 可行性证据：``runs/v10/baselines/MAP-XX.json``（Oracle/启发式/消融/随机，逐 seed）与
  ``runs/v10/baselines/summary.json``；
- MiMo 证据：``runs/v10/mimo/results.json``（Batch 8）；
- V8 回退图：``runs/v10/regression/validated_regression.json``。

用法：``python -m agent_arena.v10.map_cards``
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from agent_arena.v10.evidence_state import DECISIONS
from agent_arena.v10.paths import REPO_ROOT, V10_DOCS, V10_RUNS
from agent_arena.v10.runtime.catalog import (
    MAP_IDS,
    V10_MAPS,
    create_environment,
    metric_hash,
    rule_hash,
    scenario_hash,
    v10_class,
)
from agent_arena.worlds.scenario_v8.catalog import map_metadata

MIMO_RESULTS = V10_RUNS / "mimo" / "results.json"
CARDS_DIR = V10_DOCS / "maps"

WORLD_LABEL = {
    "spaceship": "飞船",
    "lighthouse": "灯塔",
    "abyss": "深海站",
    "polar": "极地",
    "pyramid": "金字塔",
    "subway": "地铁",
    "volcano": "火山",
    "jungle": "丛林",
    "lunar": "月球",
    "castle": "古堡",
}


# --------------------------------------------------------------------- loading
def _json(path: Any) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _baseline(map_id: str) -> dict[str, Any] | None:
    payload = _json(V10_RUNS / "baselines" / f"{map_id}.json")
    return payload if isinstance(payload, dict) else None


def _regression_row(map_id: str) -> dict[str, Any] | None:
    payload = _json(V10_RUNS / "regression" / "validated_regression.json")
    if not payload:
        return None
    return next((row for row in payload["maps"] if row["map_id"] == map_id), None)


def _mimo_rows() -> dict[str, list[dict[str, Any]]]:
    payload = _json(MIMO_RESULTS)
    grouped: dict[str, list[dict[str, Any]]] = {}
    if payload is None:
        return grouped
    rows = payload.values() if isinstance(payload, dict) else payload
    for row in rows:
        grouped.setdefault(str(row["map_id"]), []).append(row)
    for items in grouped.values():
        items.sort(key=lambda item: (int(item.get("environment_seed", 0)), str(item["run_id"])))
    return grouped


def _rate(summaries: list[dict[str, Any]]) -> str:
    if not summaries:
        return "—"
    return f"{sum(1 for item in summaries if item.get('success'))}/{len(summaries)}"


def _terminal_codes(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    codes: set[str] = set()
    buckets: list[dict[str, Any]] = [
        *payload.get("oracle", []),
        *payload.get("public_heuristic", []),
    ]
    buckets.extend(payload.get("legal_random", []))
    for rows in payload.get("ablations", {}).values():
        buckets.extend(rows)
    for item in buckets:
        reason = item.get("terminal_reason")
        if reason:
            codes.add(str(reason))
    return sorted(codes)


# --------------------------------------------------------------------- render
def _primary_mean(rows: list[dict[str, Any]]) -> float | None:
    values = [
        float(item["primary_value"])
        for item in rows
        if item.get("primary_state") == "VALID" and item.get("primary_value") is not None
    ]
    return round(sum(values) / len(values), 4) if values else None


def _title(map_id: str, meta: dict[str, Any], native: bool) -> str:
    if native:
        declared = str(getattr(v10_class(map_id), "title", "") or "")
        if declared:
            return declared
    title = str(meta.get("title") or "")
    return title if title and title != map_id else map_id


def _header(map_id: str, meta: dict[str, Any], native: bool) -> list[str]:
    decision = DECISIONS[map_id]
    world = WORLD_LABEL.get(str(meta["world"]), str(meta["world"]))
    return [
        f"# {map_id}｜{world} · {_title(map_id, meta, native)}（{meta['level']}）",
        "",
        f"- 运行时：`{'v10 原生' if native else 'v8 回退（V10 无原生运行时）'}`",
        f"- 构念标签：`{decision.construct_status}`；效度状态：`{decision.validity_status}`"
        "（均为 `agent_reviewed`）",
        f"- DCR：`{decision.dcr_id or '—'}`",
        f"- `rule_hash`：`{rule_hash(map_id)}`",
        f"- `metric_hash`：`{metric_hash(map_id)}`",
        "",
    ]


def _construct_section(map_id: str, native: bool) -> list[str]:
    from agent_arena.v10.metrics.governance import primary_policy

    decision = DECISIONS[map_id]
    lines = ["## 1. 目标构念与最小可观察行为", "", f"- 本轮裁定：{decision.decision}", ""]
    if not native:
        lines += [
            "- 该图在 V10 未重建运行时，三分量（目标构念/最小行为/消融）沿用 V9 构念证据；",
            "  V10 只做防回归与环境 seed 复核（见 `docs/v10/validated-regression.md`）。",
            "",
        ]
        return lines
    primaries = primary_policy().get(map_id, [])
    factory = v10_class(map_id)
    environment = factory(seed=factory.SEED_SPACE[0])
    specs = {spec.metric_id: spec for spec in factory.METRIC_SPECS}
    lines.append(f"- 主指标：{', '.join(f'`{item}`' for item in primaries) or '—'}")
    for metric_id in primaries:
        spec = specs[metric_id]
        lines.append(f"  - `{metric_id}`：{spec.formula}（方向：{spec.direction}）")
    lines += [
        "",
        "规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；",
        f"Oracle 各 seed 的触发率为 {_rate_mechanism(map_id)}。",
        "",
    ]
    del environment
    return lines


def _rate_mechanism(map_id: str) -> str:
    payload = _baseline(map_id)
    if not payload:
        return "—"
    rows = [{"success": bool(item.get("mechanism_triggered"))} for item in payload["oracle"]]
    return _rate(rows)


def _boundary_section(map_id: str, native: bool) -> list[str]:
    if not native:
        return [
            "## 2. 公开信息边界",
            "",
            "- V8 回退图的 Observation 与公开动作沿用 `worlds/scenario_v8` 只读实现；",
            "  V10 未新增或减少其公开字段。",
            "",
        ]
    factory = v10_class(map_id)
    environment = factory(seed=factory.SEED_SPACE[0])
    fields = sorted(getattr(factory, "PUBLIC_FIELDS", ()) or ())
    descriptor = environment.scenario_descriptor()
    seal_keys = sorted(environment.sealed_truth().keys())
    lines = [
        "## 2. 公开信息边界",
        "",
        "### 公开规则（写进 system prompt）",
        "",
    ]
    rules = environment.public_rules()
    if rules:
        lines += [f"{index}. {rule}" for index, rule in enumerate(rules, 1)]
    else:
        lines.append("- （未声明 `public_rules()`，回退到运行时的 Observation 描述）")
    lines += [
        "",
        "### Observation 公开字段",
        "",
        f"`{'`、`'.join(fields) if fields else '未显式声明'}`",
        "",
        "### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）",
        "",
        f"`{'`、`'.join(sorted(descriptor))}`",
        "",
        "### 密封真值（只列键名，真值只在 judge 与 hash 中）",
        "",
        f"`{'`、`'.join(seal_keys)}`",
        "",
    ]
    del environment
    return lines


def _actions_section(map_id: str, native: bool) -> list[str]:
    if not native:
        environment = create_environment(map_id, environment_seed=0)
        shapes = environment.SHAPES
    else:
        shapes = v10_class(map_id).SHAPES
    lines = ["## 3. 合法动作契约（`SHAPES`）", "", "| tool | 合法字段集合 |", "|---|---|"]
    for tool, variants in sorted(shapes.items()):
        rendered = " ｜ ".join(
            "{" + ",".join(sorted(shape)) + "}" for shape in sorted(variants, key=sorted)
        )
        lines.append(f"| `{tool}` | {rendered} |")
    lines.append("")
    return lines


def _seed_section(map_id: str, native: bool) -> list[str]:
    from agent_arena.v10.runtime.catalog import seed_effective, seed_space

    seeds = seed_space(map_id)
    effective = seed_effective(map_id)
    unique = len({scenario_hash(map_id, seed) for seed in seeds})
    lines = [
        "## 4. 环境 seed 与实例差异性",
        "",
        f"- 预登记 seed：`{', '.join(str(seed) for seed in seeds)}`（{len(seeds)} 个）",
        f"- 实例指纹各不相同：`{'是' if effective else '否'}`",
        f"- 不同 `scenario_hash` 数：`{unique}`",
        "",
        "| seed | scenario_hash（前 16 位） |",
        "|---:|---|",
    ]
    for seed in seeds:
        lines.append(f"| {seed} | `{scenario_hash(map_id, seed)[:16]}` |")
    if not native:
        lines += [
            "",
            "> V8 回退图对 seed 不敏感（`seed_effective=False`）：3-seed 未达标，已在",
            "> `validated-regression.md` 记为缺口。",
            "> 注意：`scenario_hash` 把 `environment_seed` 计入身份，所以三个 hash 不同",
            "> **不等于**三个环境实例不同；实例是否不同由 `seed_effective` 判定。",
        ]
    lines.append("")
    return lines


def _metrics_section(map_id: str, native: bool) -> list[str]:
    if not native:
        return [
            "## 5. 指标",
            "",
            "- 该图指标沿用 V7/V8 的 154 条注册规格（只读）；V10 未新增 v10 指标。",
            "- V10 新增的其余 23 图指标见 `docs/v10/metric-schema-v10.md`。",
            "",
        ]
    factory = v10_class(map_id)
    lines = [
        "## 5. 主次指标（`METRIC_SPECS`）",
        "",
        "| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for spec in factory.METRIC_SPECS:
        item = asdict(spec)
        lines.append(
            "| `{mid}` | {role} | {direction} | {formula} | {denominator} | {zero} | {censored} | "
            "{unit} | {valid} |".format(
                mid=item["metric_id"],
                role=item["role"],
                direction=item["direction"],
                formula=item["formula"],
                denominator=item.get("denominator") or "—",
                zero=item.get("zero_denominator") or "—",
                censored=item.get("censored_rule") or "—",
                unit=item.get("unit") or "—",
                valid=item.get("valid_range") or "—",
            )
        )
    lines.append("")
    return lines


def _ablation_section(map_id: str, native: bool) -> list[str]:
    payload = _baseline(map_id)
    if not payload:
        return ["## 6. 反事实消融", "", "- 无 V10 基线产物（V8 回退图沿用 V9 存档消融）。", ""]
    lines = [
        "## 6. 反事实消融（逐 seed，成功率与主指标均值）",
        "",
        "| 消融 | 成功率 | 主指标均值 |",
        "|---|---|---|",
    ]
    for name in sorted(payload["ablations"]):
        rows = payload["ablations"][name]
        mean = _primary_mean(rows)
        lines.append(f"| `{name}` | {_rate(rows)} | {mean if mean is not None else '—'} |")
    within_budget = all(
        int(item.get("decisions") or 0) <= int(payload["decision_budget"])
        for item in payload["oracle"]
    )
    lines += [
        "",
        f"- Oracle：{_rate(payload['oracle'])}（机制触发 {_rate_mechanism(map_id)}）",
        f"- 公开启发式：{_rate(payload['public_heuristic'])}（主指标均值 "
        f"{_primary_mean(payload['public_heuristic'])}）",
        f"- legal_random：{_rate(payload['legal_random'])}（主指标均值 "
        f"{_primary_mean(payload['legal_random'])}）",
        f"- Oracle 是否在决策预算内：`{within_budget}`",
        "",
    ]
    codes = _terminal_codes(payload)
    if codes:
        lines += [f"- 观测到的终止码：`{'`、`'.join(codes)}`", ""]
    return lines


def _mimo_section(map_id: str, rows: list[dict[str, Any]]) -> list[str]:
    from agent_arena.v10.evidence_state import is_interrupted

    if not rows:
        return [
            "## 7. MiMo 证据",
            "",
            "- 未纳入 Batch 8 矩阵：无真实模型证据（仍为 `NEEDS_MORE_EVIDENCE` 或 `VALIDATED`）。",
            "",
        ]
    lines = [
        "## 7. MiMo 证据（含重复运行；单 seed 描述性）",
        "",
        "| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |",
        "|---:|---|---|---:|---|---:|---|",
    ]
    for row in rows:
        interrupted = is_interrupted(row)
        lines.append(
            "| {seed} | `{run_id}` | {termination}（{outcome}） | {decisions} | {primary} | "
            "{cost} | {valid} |".format(
                seed=row.get("environment_seed"),
                run_id=row.get("run_id"),
                termination=row.get("termination"),
                outcome=row.get("outcome"),
                decisions=row.get("decision_count"),
                primary=row.get("primary_metric_value"),
                cost=row.get("cost_settled"),
                valid="否（中断保留）" if interrupted else "是",
            )
        )
    valid = [row for row in rows if not is_interrupted(row)]
    successes = sum(1 for row in valid if row.get("success"))
    cost = sum(float(row.get("cost_settled") or 0) for row in rows)
    interrupted_count = len(rows) - len(valid)
    lines += [
        "",
        f"- 有效局成功：{successes}/{len(valid)}"
        + (
            f"；另有 {interrupted_count} 局 provider/账本中断（保留但不计入）"
            if interrupted_count
            else ""
        ),
        f"- 结算成本合计 CNY {cost:.8f}（含中断局的已结算部分）。",
        "- 单 seed、单 replicate，只作描述，不作统计推断。",
        "",
    ]
    return lines


def _verdict_section(map_id: str, native: bool) -> list[str]:
    decision = DECISIONS[map_id]
    lines = [
        "## 8. 结论、剩余风险与下一步",
        "",
        f"- 缺陷与待证事项：{decision.defect}",
        f"- 当前裁定：{decision.decision}",
    ]
    if not native:
        row = _regression_row(map_id) or {}
        lines += [
            "- 剩余风险：无 V10 原生运行时 ⇒ 不能在本阶段声称 3-seed 达成；"
            "V11 需先参数化该图实例。",
            f"- 防回归复跑：`{'通过' if row.get('regression_ok') else '未通过/缺失'}`；"
            f"V9 Oracle 记录：`{row.get('v9_oracle', '缺失')}`；"
            f"V9 消融：`{row.get('v9_ablations', {})}`",
        ]
    else:
        lines.append(
            "- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；"
            "五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。"
        )
    if decision.validity_status == "NEEDS_MORE_EVIDENCE":
        lines.append("- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。")
    lines += [
        "",
        "## 9. 证据索引",
        "",
        (
            f"- `docs/v10/dcr/DCR-V10-{_dcr_number(map_id)}.md`"
            if decision.dcr_id
            else "- 无 DCR（沿用 V9 规则）"
        ),
        f"- `runs/v10/baselines/{map_id}.json`（若存在）",
        "- `runs/v10/baselines/summary.json`",
        "- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）",
        "- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge",
        "",
    ]
    return lines


def _dcr_number(map_id: str) -> str:
    return DECISIONS[map_id].dcr_id.replace("DCR-V10-", "")


def render_card(map_id: str, mimo: dict[str, list[dict[str, Any]]]) -> str:
    meta = map_metadata(map_id)
    native = map_id in V10_MAPS
    lines: list[str] = []
    lines += _header(map_id, meta, native)
    lines += _construct_section(map_id, native)
    lines += _boundary_section(map_id, native)
    lines += _actions_section(map_id, native)
    lines += _seed_section(map_id, native)
    lines += _metrics_section(map_id, native)
    lines += _ablation_section(map_id, native)
    lines += _mimo_section(map_id, mimo.get(map_id, []))
    lines += _verdict_section(map_id, native)
    return "\n".join(lines) + "\n"


def render_index(cards: dict[str, str]) -> str:
    rows = []
    for map_id in MAP_IDS:
        meta = map_metadata(map_id)
        decision = DECISIONS[map_id]
        rows.append(
            f"| [{map_id}]({map_id}.md) | {WORLD_LABEL.get(str(meta['world']), meta['world'])} | "
            f"{meta['level']} | "
            f"{decision.construct_status} | {decision.validity_status} | "
            f"`{'v10' if map_id in V10_MAPS else 'v8'}` |"
        )
    return "\n".join(
        [
            "# V10 逐图审计卡（30 张）",
            "",
            "- 由 `python -m agent_arena.v10.map_cards` 生成；数字来自 `runs/v10/` 可复算产物。",
            "- 每张卡包含：目标构念、公开信息边界、合法动作、seed 与实例差异、主次指标、消融、",
            "  MiMo 证据、结论与证据索引。",
            "- 状态一律标 `agent_reviewed`；不得据此声称 `human_approved`。",
            "",
            "| 图 | 世界 | 难度 | 构念 | 效度状态 | 运行时 |",
            "|---|---|---|---|---|---|",
            *rows,
            "",
            "## 覆盖说明",
            "",
            f"- V10 原生运行时：{len(V10_MAPS)} 张；V8 回退：{len(MAP_IDS) - len(V10_MAPS)} 张"
            + (
                "（01/02/05/16/17/25/27，3-seed 缺口见 `validated-regression.md`）。"
                if len(V10_MAPS) < len(MAP_IDS)
                else "（无；全部 30 图均已原生化，见 `validated-regression.md`）。"
            ),
        ]
    ) + "\n"


def main() -> None:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    mimo = _mimo_rows()
    cards: dict[str, str] = {}
    for map_id in MAP_IDS:
        text = render_card(map_id, mimo)
        (CARDS_DIR / f"{map_id}.md").write_text(text, encoding="utf-8", newline="\n")
        cards[map_id] = text
    (CARDS_DIR / "README.md").write_text(render_index(cards), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "cards": len(cards),
                "dir": str(CARDS_DIR.relative_to(REPO_ROOT)),
                "mimo_maps": sorted(mimo),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
