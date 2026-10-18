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
        "离线门禁通过；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-01",
        "Batch 1：码 seed 化、goal 去泄露、清单封存、write_memory、EVA 对齐；"
        "三消融 0/6，启发式 6/6",
    ),
    "MAP-18": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-02",
        "Batch 1：时钟分离、发车窗口强制、5 个故障变体；抢跑 0/5，no_replan 1/5，"
        "greedy 3/5，启发式 5/5",
    ),
    "MAP-06": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；10 seed cohort；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-03",
        "Batch 2：10-seed 分层天气 cohort；短风暴计入风险；截止随 seed 公开；"
        "always_direct 5/10（长风暴全死），启发式 9/10 且效用均值 0.4228 > 三条固定策略",
    ),
    "MAP-15": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；6 家族 10 seed；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-04",
        "Batch 2：删除 goal 泄露；6 规律家族；训练/测试墙色分离；record_rule 提交假设；"
        "消除相位自愈；四消融均 ≤1/10，启发式 10/10",
    ),
    "MAP-21": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；安全/科研分离评分；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-05",
        "Batch 2：safety_science 分离；10 seed 覆盖三种喷发时刻；always_evac 0.5（科研 0）、"
        "always_collect 3 灾难、risk_aware 0 灾难且均值 0.6886 最高",
    ),
    "MAP-04": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；6 seed；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-08",
        "Batch 4：盲撞计 3 tick 代价；绕行保留但余量恒 ≤ Oracle；"
        "blind_retry 1/6（仅开局安全相位的对照实例），excess_wait/fixed_phase_script 0/6",
    ),
    "MAP-14": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；6 实例；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-09",
        "Batch 4：公开推理规则；开门需要相容封存假设；6 实例；"
        "blind_two_submissions 0/6（V9 为 2/3 开门）、no_seal 0/6、one_question 2/6",
    ),
    "MAP-19": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 实例；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-10",
        "Batch 4：预测成为产能的必要条件；精确温度与误差反馈公开；"
        "no_forecast 0/4、fixed_vector_no_lag 0/4、naive_forecast 1/4（容差 2 对照实例）",
    ),
    "MAP-20": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 实例；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-11",
        "Batch 4：产能与热量解耦、动态热点公开；区阀 C 30→35；"
        "static_allocation 0/4、no_bypass 0/4、bypass_overuse 0/4；Oracle bypass_used 10/10 tick",
    ),
    "MAP-23": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 入口 4 真值；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-13",
        "Batch 4：出手需要已购线索 + 相容 mark；4 入口 × 3 侦察站使线索价格与信息量错开；"
        "no_scout 0/4（V9 为 12 决策成功）、ignore_counterevidence 0/4、"
        "scout_everything 0/4、single_clue 2/4",
    ),
    "MAP-28": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 案卷；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-06",
        "Batch 3：公开 person/path 枚举；4 案卷依赖图不同；引用自洽规则；"
        "no_record 0/4、single_source 0/4、blind_submit 0/4、cite_all 3/4",
    ),
    "MAP-29": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；4 案卷；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-06",
        "Batch 3：公开 compare 语义；角色分配随 seed 轮换且不公开；部分真实证人；"
        "四消融 0/4，启发式 8–9 问 4/4",
    ),
    "MAP-30": Decision(
        "FORCED",
        "NEEDS_MORE_EVIDENCE",
        "离线门禁通过；3 案卷含诱饵；指标偏置已纠；待 V10 指标独立复算与 MiMo 复测",
        "DCR-V10-07",
        "Batch 3：公开条目 ID/成对规则/法庭节点/窗口语义；诱饵事件；"
        "两处指标偏置纠正；四消融 0/3，window_delay 触发 window_pressure",
    ),
}


def _summary() -> dict[str, Any]:
    path = V10_RUNS / "baselines" / "summary.json"
    if not path.exists():
        return {}
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def apply(state: dict[str, Any]) -> None:
    summary = _summary()
    for map_id, decision in DECISIONS.items():
        row = state[map_id]
        row.construct_status = decision.construct_status
        row.validity_status = decision.validity_status
        row.defect = decision.defect
        row.dcr_id = decision.dcr_id
        row.decision = decision.decision
        item = summary.get(map_id)
        if not item:
            continue
        seeds = item["environment_seeds"]
        row.environment_seeds = f"{len(seeds)}（{','.join(str(seed) for seed in seeds)}）"
        row.oracle = f"{item['oracle']}（机制触发 {item['oracle_mechanism_triggered']}）"
        row.baseline = f"启发式 {item['public_heuristic']}；随机 {item['legal_random']}"
        row.ablation = "；".join(
            f"{name} {rate}" for name, rate in sorted(item["ablations"].items())
        )
        row.mimo = "V10 未运行"


__all__ = ["DECISIONS", "Decision", "apply"]
