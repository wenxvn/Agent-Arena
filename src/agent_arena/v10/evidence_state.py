"""V10 状态矩阵的证据更新：逐图裁定 + 基线套件摘要。

``DECISIONS`` 是 Agent 依据证据作出的逐图裁定（``agent_reviewed``）；Oracle、基线、
消融与 seed 列由 ``runs/v10/baselines/summary.json`` 实时填充，不手填数字。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agent_arena.v10.paths import V10_RUNS


@dataclass(frozen=True)
class Decision:
    construct_status: str
    validity_status: str
    defect: str
    dcr_id: str
    decision: str


DECISIONS: dict[str, Decision] = {
    "MAP-03": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过",
        "DCR-V10-01",
        "Batch 1：码 seed 化、goal 去泄露、清单封存、write_memory、EVA 对齐；"
        "三消融 0/6，启发式 6/6",
    ),
    "MAP-18": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过",
        "DCR-V10-02",
        "Batch 1：时钟分离、发车窗口强制、5 个故障变体；抢跑 0/5，no_replan 1/5，"
        "greedy 3/5，启发式 5/5",
    ),
    "MAP-06": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；10 seed cohort",
        "DCR-V10-03",
        "Batch 2：10-seed 分层天气 cohort；短风暴计入风险；截止随 seed 公开；"
        "always_direct 5/10（长风暴全死），启发式 9/10 且效用均值 0.4228 > 三条固定策略",
    ),
    "MAP-15": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；6 家族 10 seed",
        "DCR-V10-04",
        "Batch 2：删除 goal 泄露；6 规律家族；训练/测试墙色分离；record_rule 提交假设；"
        "消除相位自愈；四消融均 ≤1/10，启发式 10/10",
    ),
    "MAP-21": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；安全/科研分离评分",
        "DCR-V10-05",
        "Batch 2：safety_science 分离；10 seed 覆盖三种喷发时刻；always_evac 0.5（科研 0）、"
        "always_collect 3 灾难、risk_aware 0 灾难且均值 0.6886 最高",
    ),
    "MAP-04": Decision(
        "OPTIONAL",
        "NEEDS_MORE_EVIDENCE",
        "Batch 9 改标：绕行是合法替代（detour_only 6/6），但主指标 time_margin 0.67 ≪ Oracle 3.33，"
        "机制影响效率而非通过与否",
        "DCR-V10-08",
        "Batch 4：盲撞计 3 tick 代价；绕行保留但余量恒 ≤ Oracle；"
        "blind_retry 1/6（仅开局安全相位的对照实例），excess_wait/fixed_phase_script 0/6",
    ),
    "MAP-07": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 实例",
        "DCR-V10-19",
        "Batch 5：面板只公开因果不公开开向、拧错进水 +1、水位预测进入成败；"
        "fixed_clockwise 2/4（固定脚本假设被证伪）、never_open/late_open 0/4",
    ),
    "MAP-08": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 个分区实例",
        "DCR-V10-16",
        "Batch 5：封存诊断成为修复前提、测试必须缩小假设集；"
        "no_hypothesis 0/4（V9 旁路）、blind_repairs 0/4、single_test 1/4；"
        "over_testing 4/4 但 tests_used 3（合法但更慢）",
    ),
    "MAP-09": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 实例",
        "DCR-V10-21",
        "Batch 5：修复需水位与供氧双门槛、三链同时结算、漏速递增；"
        "skip_pump 0/4（FLOODED）、skip_vent 1/4（LOST_POWER）、seal_only 0/4（LOST_OXYGEN）",
    ),
    "MAP-10": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 实例",
        "DCR-V10-20",
        "Batch 5：油耗 = burn_base + ceil(cargo/2)、容量与库存双约束；"
        "max_load 1/4（烧光油）、underload 0/4（货不够）、no_move 0/4",
    ),
    "MAP-11": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 实例（含晴稳对照）",
        "DCR-V10-18",
        "Batch 5：救援需先有信号、风暴窗口公开且漏检 0.5–0.7、生命窗；"
        "blind_rescue 0/4（V9 旁路）、storm_search 有风暴搜索但合法、"
        "single_search_giveup/waste_window 2/4；启发式风暴搜索 0 次",
    ),
    "MAP-12": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 实例；补上 V9 缺失的离线跨期证据",
        "DCR-V10-22",
        "Batch 5：30 天 × 槽位排班、每日双结算、双归零失败；"
        "all_research/all_forage/no_research/waste_slots 全 0/4；启发式研究 38/35/40/75",
    ),
    "MAP-13": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 道不同约束题；方向钉仍为 OPTIONAL（质量 4/5）",
        "DCR-V10-15",
        "Batch 5：记录成为出手前提（试排需 ≥1 条、验证需 ≥4 条）；"
        "no_record 0/4（V9 为 15 步满分）、blind_guess/record_only_nail 0/4；"
        "no_direction_nail 4/4 但 ratio 恒 0.8",
    ),
    "MAP-14": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；6 实例",
        "DCR-V10-09",
        "Batch 4：公开推理规则；开门需要相容封存假设；6 实例；"
        "blind_two_submissions 0/6（V9 为 2/3 开门）、no_seal 0/6、one_question 2/6",
    ),
    "MAP-19": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 实例",
        "DCR-V10-10",
        "Batch 4：预测成为产能的必要条件；精确温度与误差反馈公开；"
        "no_forecast 0/4、fixed_vector_no_lag 0/4、naive_forecast 1/4（容差 2 对照实例）",
    ),
    "MAP-20": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 实例",
        "DCR-V10-11",
        "Batch 4：产能与热量解耦、动态热点公开；区阀 C 30→35；"
        "static_allocation 0/4、no_bypass 0/4、bypass_overuse 0/4；Oracle bypass_used 10/10 tick",
    ),
    "MAP-22": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 迷宫",
        "DCR-V10-12",
        "Batch 4：遮蔽（只给当前路标与方位）+ 死胡同分岔 + 跨阶段返程；"
        "no_memory_write 0/4（V9 为 12 决策成功）、fixed_bearings/no_return/random_walk 0/4；"
        "公开记忆 DFS 3/4（seed 1 因贪心方位顺序超预算，属策略弱点）",
    ),
    "MAP-23": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 入口 4 真值",
        "DCR-V10-13",
        "Batch 4：出手需要已购线索 + 相容 mark；4 入口 × 3 侦察站使线索价格与信息量错开；"
        "no_scout 0/4（V9 为 12 决策成功）、ignore_counterevidence 0/4、"
        "scout_everything 0/4、single_clue 2/4",
    ),
    "MAP-24": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 实例",
        "DCR-V10-14",
        "Batch 4：山路拉长、封路时刻隐藏且不瞬杀、公开 collapse_observed；"
        "两条 primary 重定义；no_replan 0/4（replan_success 0）、mountain_only 记为 N/A 合法替代",
    ),
    "MAP-26": Decision(
        "OPTIONAL",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；诊断 OPTIONAL 但质量可区分",
        "DCR-V10-17",
        "Batch 5：换错耗备件并 +1 磨损（达 2 即不可恢复）、rollback 不返还备件；"
        "no_diagnosis 3/4 但备件 2/2/1/2 且均有换错、test_but_ignore 0/4；"
        "启发式 4/4 且 spares 恒 1、precision 1",
    ),
    "MAP-28": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 案卷",
        "DCR-V10-06",
        "Batch 3：公开 person/path 枚举；4 案卷依赖图不同；引用自洽规则；"
        "no_record 0/4、single_source 0/4、blind_submit 0/4、cite_all 3/4",
    ),
    "MAP-29": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 案卷",
        "DCR-V10-06",
        "Batch 3：公开 compare 语义；角色分配随 seed 轮换且不公开；部分真实证人；"
        "四消融 0/4，启发式 8–9 问 4/4",
    ),
    "MAP-30": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；3 案卷含诱饵；指标偏置已纠",
        "DCR-V10-07",
        "Batch 3：公开条目 ID/成对规则/法庭节点/窗口语义；诱饵事件；"
        "两处指标偏置纠正；四消融 0/3，window_delay 触发 window_pressure",
    ),
}


#: Batch 5 防回归：7 张 V9 VALIDATED 图的复跑通过，但环境 seed 未参数化（3-seed 未达标）。
#: 证据见 ``docs/v10/validated-regression.md``；不撤销 VALIDATED，但在最终报告中记为缺口。
for _map_id in ("MAP-01", "MAP-02", "MAP-05", "MAP-16", "MAP-17", "MAP-25", "MAP-27"):
    DECISIONS.setdefault(
        _map_id,
        Decision(
            "FORCED",
            "VALIDATED",
            "V8 实例对 seed 不敏感（3-seed 未达标，见 validated-regression.md）",
            "",
            "Batch 5 防回归：V9 Oracle 在当前运行时可复跑；多 seed 覆盖缺口已明确记录",
        ),
    )


def _summary() -> dict[str, Any]:
    path = V10_RUNS / "baselines" / "summary.json"
    if not path.exists():
        return {}
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


INTERRUPTED_OUTCOMES = ("unknown_provider_spend", "provider_error_limit")


def is_interrupted(row: dict[str, Any]) -> bool:
    """provider/账本中断导致本局不完整：保留记录但不计入该 seed 的有效证据。"""

    outcome = str(row.get("outcome") or "")
    return outcome in INTERRUPTED_OUTCOMES or outcome.startswith("settle_closed")


def mimo_rows() -> list[dict[str, Any]]:
    """Batch 8 的全部 MiMo 逐局记录（含中断局与重跑局，按 run_id 排序）。"""

    path = V10_RUNS / "mimo" / "results.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = list(payload.values()) if isinstance(payload, dict) else list(payload)
    return sorted(
        rows,
        key=lambda row: (
            str(row["map_id"]),
            int(row.get("environment_seed", 0)),
            str(row["run_id"]),
        ),
    )


def _run_priority(row: dict[str, Any]) -> tuple[bool, int]:
    """同一 (map, seed) 多条记录时，选“完整优先、阶段新优先”的一条。

    完整未中断 > 中断；``-i2``（接口修复后）> ``-r2``（中断补跑）> 首次运行。
    """

    run_id = str(row.get("run_id", ""))
    if run_id.endswith("-i2"):
        phase = 3
    elif run_id.endswith("-r2"):
        phase = 2
    else:
        phase = 1
    return (not is_interrupted(row), phase)


def effective_mimo_rows() -> dict[str, list[dict[str, Any]]]:
    """逐图的有效 MiMo 局：每个 (map, seed) 只保留优先级最高的一条。"""

    selected: dict[tuple[str, int], dict[str, Any]] = {}
    for row in mimo_rows():
        key = (str(row["map_id"]), int(row.get("environment_seed", 0)))
        current = selected.get(key)
        if current is None or _run_priority(row) > _run_priority(current):
            selected[key] = row
    grouped: dict[str, list[dict[str, Any]]] = {}
    for (map_id, _seed), row in sorted(selected.items()):
        grouped.setdefault(map_id, []).append(row)
    return grouped


def mimo_summary() -> dict[str, dict[str, Any]]:
    """Batch 8 逐图 MiMo 证据（有效局 = 每个 seed 的最新一局）。"""

    rows = mimo_rows()
    effective = effective_mimo_rows()
    all_by_map: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        all_by_map.setdefault(str(row["map_id"]), []).append(row)
    summary: dict[str, dict[str, Any]] = {}
    for map_id, items in all_by_map.items():
        chosen = effective.get(map_id, [])
        extra = len(items) - len(chosen)
        cost = sum(float(item.get("cost_settled") or 0) for item in items)
        summary[map_id] = {
            "runs": len(chosen),
            "successes": sum(1 for item in chosen if item.get("success")),
            "interrupted": sum(1 for item in items if is_interrupted(item)),
            "superseded": extra,
            "cost": cost,
            "unknown": any(item.get("cost_unknown") for item in items),
            "seeds": ",".join(str(item.get("environment_seed")) for item in chosen),
            "outcomes": sorted({str(item.get("outcome")) for item in chosen}),
        }
    return summary


def apply(state: dict[str, Any]) -> None:
    from agent_arena.v10.validation import evaluate

    summary = _summary()
    mimo = mimo_summary()
    gates = evaluate()
    for map_id, decision in DECISIONS.items():
        row = state[map_id]
        row.construct_status = decision.construct_status
        row.validity_status = decision.validity_status
        row.defect = decision.defect
        row.dcr_id = decision.dcr_id
        row.decision = decision.decision
        gate = gates.get(map_id)
        if gate is not None and gate.native:
            # Batch 9：V10 原生图的效度状态由 8 项 Gate 机器判定（见 validation-gates.md）。
            row.validity_status = gate.verdict
            if gate.verdict == "VALIDATED":
                row.defect = f"{decision.defect}；Batch 9：8 Gate 全过"
            else:
                row.defect = f"{decision.defect}；Batch 9 未过：" + "；".join(gate.reasons)
        item = summary.get(map_id)
        if item:
            seeds = item["environment_seeds"]
            row.environment_seeds = f"{len(seeds)}（{','.join(str(seed) for seed in seeds)}）"
            row.oracle = f"{item['oracle']}（机制触发 {item['oracle_mechanism_triggered']}）"
            row.baseline = f"启发式 {item['public_heuristic']}；随机 {item['legal_random']}"
            row.ablation = "；".join(
                f"{name} {rate}" for name, rate in sorted(item["ablations"].items())
            )
        evidence = mimo.get(map_id)
        if evidence:
            unknown = "；含未知消费" if evidence["unknown"] else ""
            extra = (
                f"；另有 {evidence['superseded']} 局重跑/中断保留"
                if evidence.get("superseded")
                else ""
            )
            row.mimo = (
                f"V10 {evidence['successes']}/{evidence['runs']}"
                f"（seed {evidence['seeds']}；CNY {evidence['cost']:.8f}{unknown}{extra}）"
            )
        else:
            row.mimo = "V10 未运行"


__all__ = [
    "DECISIONS",
    "Decision",
    "apply",
    "effective_mimo_rows",
    "is_interrupted",
    "mimo_rows",
    "mimo_summary",
]
