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
