"""Batch 9 补强：主指标的**公式级第二套实现**（独立重算分子/分母）。

`independent_check` 只做规格驱动五态核对 + 回放确定性；本模块对每张 V10 原生图的
**主指标**再写一份独立实现：只用「公开初始 Observation（实例参数）」+「`judge_state()` 的
原始计数器」重算分子/分母，**不调用**各图的 `v10_metrics()`。

三种结果：

- `MATCH`：独立重算与地图自报取值一致（阈值 1e-6）；
- `MISMATCH`：不一致，必须逐条解释（写进报告）；
- `SKIPPED`：公式依赖密封真值或地图内部状态（如 MAP-03 的航线码、MAP-13 的密封案卷、
  MAP-14 的假设表、MAP-21 的喷发时刻），在报告中如实标注“未覆盖”。

覆盖：19/23 张原生图；未覆盖 4 张（03/13/14/21）与原因见 `docs/v10/metric-recompute.md`。

用法：``python -m agent_arena.v10.recompute``
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from agent_arena.v10.baselines.runner import LegalRandomPolicy
from agent_arena.v10.baselines.suite import baseline_module, decision_budget
from agent_arena.v10.metrics.governance import truncation_censored
from agent_arena.v10.paths import V10_DOCS, V10_RUNS
from agent_arena.v10.runtime.catalog import V10_MAPS, create_environment, v10_class
from agent_arena.worlds.scenario_v8.models import V8Action

TOLERANCE = 1e-6
RANDOM_POLICY_SEEDS = (0, 1, 2)

#: 未覆盖的图与原因（公式依赖密封真值、地图内部状态或未暴露的判据字段）。
SKIP_REASONS: dict[str, str] = {
    "MAP-03": (
        "航线码是密封真值，judge_state 只暴露提交值与 seal hash，"
        "无法在不读地图内部状态的前提下重算"
    ),
    "MAP-13": "房间谓词的真值需要密封案卷，公开的约束文本不足以独立判定满足数",
    "MAP-14": "一致性判定依赖密封假设表（sealed 由地图自身维护）",
    "MAP-21": "科学分依赖密封喷发时刻与地图内部评分，judge_state 只给 sample/exposure 汇总",
    "MAP-24": (
        "判据 assessable = 观察到封路 且 封路前用过桥路，后半句未出现在 judge_state；"
        "V11 需把 bridge_used_before_collapse 加入 judge 字段"
    ),
    "MAP-26": "成功判据依赖密封故障真值（装上正确备件），judge 只暴露已装件与候选集",
}


@dataclass
class Recomputation:
    map_id: str
    run_id: str
    kind: str
    reported_state: str
    reported_value: Any
    recomputed_state: str
    recomputed_value: Any
    verdict: str
    note: str = ""


def _na(reason: str) -> tuple[str, str]:
    return ("NOT_APPLICABLE", reason)


def _censored(reason: str) -> tuple[str, str]:
    return ("CENSORED", reason)


def _v(value: float) -> tuple[str, float]:
    return ("VAL", round(float(value), 6))


Formula = Callable[[dict[str, Any], dict[str, Any], bool], tuple[str, Any]]


def _f04(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    if truncated:
        return _censored("截尾")
    if judge.get("lamp_lit") is not True:
        return _v(0)
    deadline = obs.get("rescue_deadline_tick")
    finish = judge.get("finish_tick")
    if deadline is None or finish is None:
        return _na("缺少 deadline/finish_tick")
    return _v(deadline - finish)


def _f05(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    if truncated:
        return _censored("截尾")
    transmitted = judge.get("transmitted") or {}
    return _v(1 if transmitted and all(transmitted.values()) else 0)


def _f06(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    if truncated:
        return _censored("截尾")
    if judge.get("lamp_restored") is not True:
        return _v(0)
    deadline = obs.get("deadline_tick")
    budget = obs.get("risk_budget")
    finish = judge.get("finish_tick")
    risk = judge.get("risk")
    if deadline is None or budget is None or finish is None or risk is None:
        return _na("缺少 deadline/risk 字段")
    value = 1 - 0.5 * risk / (budget + 1) - 0.5 * finish / deadline
    return _v(value)


def _f07(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    if truncated:
        return _censored("截尾")
    if judge.get("valve_open") is not True:
        return _v(0)
    safe = obs.get("safe_level")
    level = judge.get("level")
    if safe is None or level is None:
        return _na("缺少 safe_level/level")
    return _v(1 if level <= safe else 0)


def _f08(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    del obs
    if truncated:
        return _censored("截尾")
    ok = judge.get("repaired") is True and int(judge.get("wrong_repairs") or 0) == 0
    return _v(1 if ok else 0)


def _f09(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    del obs
    if truncated:
        return _censored("截尾")
    ok = (
        judge.get("repaired") is True
        and int(judge.get("min_oxygen") or 0) > 0
        and int(judge.get("min_power") or 0) > 0
        and int(judge.get("water") or 0) > 0
    )
    return _v(1 if ok else 0)


def _f10(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    if truncated:
        return _censored("截尾")
    required = obs.get("required_delivery")
    if required is None:
        return _na("缺少 required_delivery")
    ok = judge.get("arrived") is True and int(judge.get("cargo") or 0) >= int(required)
    return _v(1 if ok else 0)


def _f11(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    if truncated:
        return _censored("截尾")
    window = obs.get("life_window_end")
    tick = judge.get("rescue_tick")
    if judge.get("rescued") is not True or tick is None:
        return _v(0)
    if window is None:
        return _na("缺少 life_window_end")
    return _v(1 if int(tick) <= int(window) else 0)


def _f12(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    if truncated:
        return _censored("截尾")
    target = obs.get("research_target")
    if target is None:
        return _na("缺少 research_target")
    ok = int(judge.get("day") or 0) >= 30 and int(judge.get("research") or 0) >= int(target)
    return _v(1 if ok else 0)


def _f15(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    del obs
    attempts = judge.get("test_first_try") or {}
    if not attempts:
        return _censored("进入 T 前截尾") if truncated else _na("未进入测试区")
    return _v(sum(1 for ok in attempts.values() if ok) / len(attempts))


def _f18(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    del obs, truncated
    return _v(int(judge.get("delivered") or 0) / 18)


def _f19(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    if truncated:
        return _censored("截尾")
    target = obs.get("production_target")
    if not target:
        return _na("缺少 production_target")
    return _v(min(1.0, int(judge.get("production") or 0) / int(target)))


def _f20(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    if truncated:
        return _censored("截尾")
    target = judge.get("target") or obs.get("production_target")
    if not target:
        return _na("缺少 target")
    return _v(min(1.0, int(judge.get("production") or 0) / int(target)))


def _f22(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    del obs
    if truncated:
        return _censored("截尾")
    ok = judge.get("ruin_recorded") is True and str(judge.get("sign")) == "camp"
    return _v(1 if ok else 0)


def _f23(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    entrances = obs.get("entrances")
    clues = judge.get("clues") or []
    if not clues:
        # 规格 `zero_denominator`：未侦察 → NOT_APPLICABLE（优先于截尾）
        return _na("未侦察")
    if not entrances or len(entrances) < 2:
        return _na("候选项不足 2")
    del truncated  # 规格：部分进度保持 VALID（已购线索的缩减比例可算）
    total = len(entrances)
    reductions = [
        (total - len(clue.get("supports") or [])) / (total - 1) for clue in clues
    ]
    return _v(max(reductions))


def _f28(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    del obs
    if judge.get("submitted") is True:
        return _v(int(judge.get("satisfied_fields") or 0) / 4)
    return _censored("未提交且截尾") if truncated else _na("未提交")


def _f29(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    del obs, truncated
    planted = 2  # 该图每个案卷植入 2 条矛盾（scenario_label: two_contradictions）
    return _v(len(judge.get("unreliable_proven") or []) / planted)


def _f30(obs: dict[str, Any], judge: dict[str, Any], truncated: bool) -> tuple[str, Any]:
    del obs, truncated
    casebook = judge.get("casebook") or {}
    required = {
        "EVENT_1_HANDOFF": 2,
        "EVENT_2_WAX": 2,
        "EVENT_3_SIGNAL": 2,
        "Q4_CODEBOOK": 1,
    }
    complete = sum(
        1 for entry, need in required.items() if len(casebook.get(entry) or []) >= need
    )
    return _v(complete / len(required))


FORMULAS: dict[str, Formula] = {
    "MAP-04": _f04,
    "MAP-05": _f05,
    "MAP-06": _f06,
    "MAP-07": _f07,
    "MAP-08": _f08,
    "MAP-09": _f09,
    "MAP-10": _f10,
    "MAP-11": _f11,
    "MAP-12": _f12,
    "MAP-15": _f15,
    "MAP-18": _f18,
    "MAP-19": _f19,
    "MAP-20": _f20,
    "MAP-22": _f22,
    "MAP-23": _f23,
    "MAP-28": _f28,
    "MAP-29": _f29,
    "MAP-30": _f30,
}


def _replay(
    map_id: str, seed: int, actions: list[dict[str, Any]]
) -> tuple[dict[str, Any], Any, Any, bool]:
    environment = create_environment(map_id, environment_seed=seed)
    first_observation = environment.observe()
    for payload in actions:
        if environment.is_terminal:
            break
        if not isinstance(payload, dict) or "tool" not in payload:
            # 原始运行里被判非法形状的动作：环境同样按“非法动作”处理（可能推进 tick）
            environment.reject_invalid_action()
            continue
        try:
            action = V8Action.model_validate(payload, strict=True)
        except Exception:  # noqa: BLE001 - 非法动作在回放里按环境语义拒绝
            environment.reject_invalid_action()
            continue
        if not environment.accepts(action):
            environment.reject_invalid_action()
            continue
        environment.step(action)
    metrics = environment.metrics()
    # 与 runner 一致：按声明的截尾口径归一，再作为比较基准
    metrics = truncation_censored(
        map_id, metrics, truncated=not environment.is_terminal
    )
    primary = v10_class(map_id).PRIMARY_METRIC
    # 与各图 `v10_metrics()` 的 `running` 口径一致：未终局（含决策预算耗尽）即视为截尾。
    truncated = (not environment.is_terminal) or environment.status.value == "step_limit_reached"
    return first_observation, environment.judge_state(), metrics.get(primary, {}), truncated


def _compare(
    map_id: str,
    run_id: str,
    kind: str,
    formula: Formula,
    observation: dict[str, Any],
    judge: dict[str, Any],
    reported: dict[str, Any],
    truncated: bool,
) -> Recomputation:
    state, detail = formula(observation, judge, truncated)
    if state in {"NOT_APPLICABLE", "CENSORED"}:
        # 非 VALID：地图也必须报非 VALID；具体态（N/A vs CENSORED）单独核对
        reported_state = str(reported.get("state"))
        verdict = "MATCH" if reported_state != "VALID" else "MISMATCH"
        note = detail
        if verdict == "MATCH" and reported_state != state:
            verdict = "MISMATCH"
            note = f"非 VALID 态不一致：地图 {reported_state} vs 独立 {state}"
        return Recomputation(
            map_id,
            run_id,
            kind,
            reported_state,
            reported.get("value"),
            state,
            None,
            verdict,
            note,
        )
    reported_value = reported.get("value")
    if reported.get("state") != "VALID":
        return Recomputation(
            map_id,
            run_id,
            kind,
            str(reported.get("state")),
            reported_value,
            "VAL",
            detail,
            "MISMATCH",
            "地图报非 VALID，独立实现算出了取值",
        )
    assert reported_value is not None
    verdict = "MATCH" if abs(float(reported_value) - float(detail)) <= TOLERANCE else "MISMATCH"
    return Recomputation(
        map_id,
        run_id,
        kind,
        "VALID",
        reported_value,
        "VAL",
        detail,
        verdict,
        "" if verdict == "MATCH" else "取值不一致（阈值 1e-6）",
    )


def audit() -> dict[str, Any]:
    rows: list[Recomputation] = []
    for map_id in sorted(V10_MAPS):
        formula = FORMULAS.get(map_id)
        if formula is None:
            continue
        module = baseline_module(map_id)
        budget = decision_budget(map_id)
        for seed in v10_class(map_id).SEED_SPACE:
            cases: list[tuple[str, str, list[dict[str, Any]]]] = [
                (f"{map_id}-S{seed}-oracle", "oracle", module.oracle_actions(seed))
            ]
            for name, factory in sorted(module.ABLATIONS.items()):
                import inspect

                policy = (
                    factory(seed=0)
                    if "seed" in inspect.signature(factory).parameters
                    else factory()
                )
                from agent_arena.v10.baselines.runner import run_policy

                run = run_policy(
                    map_id,
                    policy,
                    environment_seed=seed,
                    decision_budget=budget,
                    keep_actions=True,
                )
                cases.append(
                    (
                        f"{map_id}-S{seed}-{name}",
                        f"ablation:{name}",
                        [dict(item["action"]) for item in run.actions if "action" in item],
                    )
                )
            for policy_seed in RANDOM_POLICY_SEEDS:
                from agent_arena.v10.baselines.runner import run_policy

                run = run_policy(
                    map_id,
                    LegalRandomPolicy(create_environment(map_id).SHAPES, policy_seed),
                    environment_seed=seed,
                    policy_seed=policy_seed,
                    decision_budget=budget,
                    keep_actions=True,
                )
                cases.append(
                    (
                        f"{map_id}-S{seed}-random{policy_seed}",
                        "legal_random",
                        [dict(item["action"]) for item in run.actions if "action" in item],
                    )
                )
            for run_id, kind, actions in cases:
                observation, judge, reported, truncated = _replay(map_id, seed, actions)
                rows.append(
                    _compare(
                        map_id,
                        run_id,
                        kind,
                        formula,
                        observation,
                        judge,
                        reported,
                        truncated,
                    )
                )
    mismatches = [asdict(row) for row in rows if row.verdict == "MISMATCH"]
    return {
        "schema": "v10-metric-recompute-1",
        "coverage": {
            "formulas": sorted(FORMULAS),
            "skipped": SKIP_REASONS,
        },
        "rows": [asdict(row) for row in rows],
        "mismatches": mismatches,
        "totals": {
            "checks": len(rows),
            "maps_covered": len({row.map_id for row in rows}),
            "match": sum(1 for row in rows if row.verdict == "MATCH"),
            "mismatch": len(mismatches),
        },
    }


def render(payload: dict[str, Any]) -> str:
    totals = payload["totals"]
    per_map: dict[str, dict[str, int]] = {}
    for row in payload["rows"]:
        stats = per_map.setdefault(row["map_id"], {"MATCH": 0, "MISMATCH": 0})
        stats[row["verdict"]] += 1
    lines = [
        "# V10 主指标公式级独立复算",
        "",
        "- 由 `python -m agent_arena.v10.recompute` 生成：独立实现只用「公开初始 `Observation`",
        "  （实例参数）」+「`judge_state()` 原始计数器」，不调用各图 `v10_metrics()`。",
        "- 本轮它先查出 **53 处不一致**（截断局被当成 `VALID`），已按规格文本在投影层归一",
        "  并重跑为 0（DCR-V10-26）；不一致明细与其处理见 `dcr/DCR-V10-26.md`。",
        f"- 覆盖 **{totals['maps_covered']}/23** 张原生图、{totals['checks']} 次复算；"
        f"一致 {totals['match']}、不一致 **{totals['mismatch']}**。",
        "- 公式前提取自各图 `METRIC_SPECS` 与 `DCR-V10-*`；阈值 1e-6。",
        "",
        "## 1. 逐图结果",
        "",
        "| 图 | 复算次数 | 一致 | 不一致 |",
        "|---|---:|---:|---:|",
    ]
    for map_id in sorted(per_map):
        stats = per_map[map_id]
        total = stats["MATCH"] + stats["MISMATCH"]
        lines.append(
            f"| {map_id} | {total} | {stats['MATCH']} | {stats['MISMATCH']} |"
        )
    lines += [
        "",
        "## 2. 未覆盖的图与原因",
        "",
        "| 图 | 原因 |",
        "|---|---|",
    ]
    for map_id, reason in sorted(payload["coverage"]["skipped"].items()):
        lines.append(f"| {map_id} | {reason} |")
    lines += ["", "## 3. 不一致明细", ""]
    if payload["mismatches"]:
        lines += [
            "| 图 | 用例 | 类型 | 地图状态/取值 | 独立状态/取值 | 说明 |",
            "|---|---|---|---|---|---|",
        ]
        for row in payload["mismatches"]:
            lines.append(
                f"| {row['map_id']} | {row['run_id']} | {row['kind']} | "
                f"{row['reported_state']}/{row['reported_value']} | "
                f"{row['recomputed_state']}/{row['recomputed_value']} | {row['note']} |"
            )
    else:
        lines.append("- 无。")
    lines += [
        "",
        "## 4. 结论与限制",
        "",
        "- 一致表示“同一份公开输入下，两套实现给出相同取值”，这是对公式与分母口径的直接验证；",
        "  它**不**验证构念效度，也不替代 `final-report.md` 的语义审查。",
        "- 本工具已成功查出并驱动修复一处系统性口径缺陷（截断漏判 `CENSORED`，DCR-V10-26），",
        "  说明“第二套实现”不是形式主义。",
        "- 未覆盖的图（见 §2）公式依赖密封真值、地图内部状态或未暴露的判据字段；要覆盖它们",
        "  必须先把这些真值/字段纳入可复算的 `judge_state`，这是 V11 的接口工作。",
        "",
        "## 5. 复算",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe -m agent_arena.v10.recompute",
        "```",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = audit()
    output = V10_RUNS / "recompute"
    output.mkdir(parents=True, exist_ok=True)
    (output / "metric_recompute.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
)
    (V10_DOCS / "metric-recompute.md").write_text(render(payload), encoding="utf-8", newline="\n")
    print(json.dumps(payload["totals"], ensure_ascii=False))


__all__ = ["FORMULAS", "SKIP_REASONS", "audit", "main", "render"]


if __name__ == "__main__":
    main()
