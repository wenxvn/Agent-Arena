# ruff: noqa: E501 - 状态表是数据行，保持一图一行便于审阅
"""V10 30 图机器可读状态矩阵。

``V9_BASELINE`` 记录 V9 的起点（只读事实，来自 docs/v9）；``V10_STATE`` 由各
Batch 依据证据更新。``write()`` 输出 ``docs/v10/map-status-matrix.csv`` 与
``.md``。哈希列由 V10 运行时实时计算，不手填。
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from agent_arena.v10.paths import V10_DOCS

FIELDS = (
    "map_id",
    "world",
    "difficulty",
    "claimed_construct",
    "construct_status",
    "validity_status",
    "defect",
    "dcr_id",
    "rule_hash",
    "metric_hash",
    "environment_seeds",
    "oracle",
    "baseline",
    "ablation",
    "mimo",
    "decision",
)


@dataclass(frozen=True)
class V9Row:
    world: str
    difficulty: str
    construct: str
    construct_status: str
    validity_status: str
    defect: str
    dcr: str


#: V9 起点（docs/v9/map-status-matrix.md “修复后状态”列 + construct-validity.md 判定）。
V9_BASELINE: dict[str, V9Row] = {
    "MAP-01": V9Row("飞船", "简单", "生命支持优先 + 互斥支路依赖链", "FORCED", "VALIDATED", "", ""),
    "MAP-02": V9Row(
        "飞船", "中等", "事件触发的双目标重排", "FORCED", "VALIDATED", "latency 恒 1", "DCR-09"
    ),
    "MAP-03": V9Row(
        "飞船",
        "困难",
        "五阶段里程碑 + 远期代码召回",
        "BYPASS",
        "BLOCKED",
        "tag 可最后读；无记忆通道；EVA 退出不扣氧",
        "DCR-12",
    ),
    "MAP-04": V9Row(
        "灯塔",
        "简单",
        "潮汐相位预测 + 回程时机",
        "BYPASS",
        "NEEDS_REDESIGN",
        "绕行/盲撞均成功；stranded_ticks 错误",
        "DCR-09",
    ),
    "MAP-05": V9Row("灯塔", "中等", "三窗口共享供电排程", "FORCED", "VALIDATED", "", "DCR-02"),
    "MAP-06": V9Row(
        "灯塔",
        "困难",
        "80% 条件预报 + 风险预算",
        "BYPASS",
        "NEEDS_REDESIGN",
        "seed0 无风暴两步直达；VOI 硬编码 None",
        "DCR-10",
    ),
    "MAP-07": V9Row(
        "深海",
        "简单",
        "阀门方向与水位预判",
        "BLOCKED",
        "NEEDS_MORE_EVIDENCE",
        "control_panel 已公开，待新证据",
        "DCR-14",
    ),
    "MAP-08": V9Row(
        "深海",
        "中等",
        "主动测试缩小漏点假设集",
        "BYPASS",
        "NEEDS_MORE_EVIDENCE",
        "no_hypothesis 成功；hypothesis_table 空转",
        "DCR-14",
    ),
    "MAP-09": V9Row(
        "深海",
        "困难",
        "漏水-电力-供氧-通信连锁",
        "BLOCKED",
        "NEEDS_MORE_EVIDENCE",
        "阈值已公开；skip_pump 成功",
        "DCR-03",
    ),
    "MAP-10": V9Row(
        "极地",
        "简单",
        "双仓燃料运输与时间成本",
        "BLOCKED",
        "NEEDS_MORE_EVIDENCE",
        "燃料规则已公开，待新证据",
        "DCR-04",
    ),
    "MAP-11": V9Row(
        "极地",
        "中等",
        "风暴/噪声下的搜索与生命窗",
        "BYPASS",
        "NEEDS_MORE_EVIDENCE",
        "seed0 无风暴；补给规则已公开",
        "DCR-05",
    ),
    "MAP-12": V9Row(
        "极地",
        "困难",
        "30 天跨期库存与劳动槽",
        "BLOCKED",
        "NEEDS_MORE_EVIDENCE",
        "v9_fixed 无有效 MiMo 局",
        "DCR-06",
    ),
    "MAP-13": V9Row(
        "金字塔",
        "简单",
        "约束满足 + 唯一序列",
        "OPTIONAL",
        "NEEDS_MORE_EVIDENCE",
        "illegal_door_attempts/ratio 口径",
        "",
    ),
    "MAP-14": V9Row(
        "金字塔", "中等", "真假证词推理", "BYPASS", "NEEDS_REDESIGN", "盲交 2/3 通关", ""
    ),
    "MAP-15": V9Row(
        "金字塔",
        "困难",
        "从训练样例归纳变化规则",
        "BYPASS",
        "NEEDS_REDESIGN",
        "goal 泄露规则；错误后相位翻转",
        "DCR-11",
    ),
    "MAP-16": V9Row("地铁", "简单", "会车/侧线/死锁", "FORCED", "VALIDATED", "", "DCR-07"),
    "MAP-17": V9Row(
        "地铁",
        "中等",
        "瓶颈下的四车多目标排程",
        "FORCED",
        "VALIDATED",
        "overcapacity_events 口径；line 枚举",
        "",
    ),
    "MAP-18": V9Row(
        "地铁",
        "困难",
        "封锁后的在线恢复",
        "BYPASS",
        "BLOCKED",
        "step_limit=min(.,12)；抢跑旁路",
        "",
    ),
    "MAP-19": V9Row(
        "火山",
        "简单",
        "2 tick 时滞热控 + 预测",
        "OPTIONAL",
        "NEEDS_REDESIGN",
        "forecast 无反馈/指标",
        "",
    ),
    "MAP-20": V9Row(
        "火山",
        "中等",
        "多区热上限 + 有损旁路分配",
        "OPTIONAL",
        "NEEDS_REDESIGN",
        "旁路被直供支配",
        "",
    ),
    "MAP-21": V9Row(
        "火山",
        "困难",
        "隐藏喷发时刻下的停手决策",
        "BYPASS",
        "NEEDS_REDESIGN",
        "1 步直达撤离满分",
        "DCR-13",
    ),
    "MAP-22": V9Row(
        "丛林",
        "简单",
        "无地图空间记忆与返程",
        "BYPASS",
        "NEEDS_REDESIGN",
        "无记忆策略 12 步成功",
        "",
    ),
    "MAP-23": V9Row(
        "丛林",
        "中等",
        "线索推断真入口 + 补给",
        "OPTIONAL",
        "NEEDS_REDESIGN",
        "no_scout 成功；cost_per_discovery 分母",
        "",
    ),
    "MAP-24": V9Row(
        "丛林",
        "困难",
        "坍塌后重规划",
        "BYPASS",
        "NEEDS_REDESIGN",
        "成功轨迹未改路；replanning_latency 反向",
        "",
    ),
    "MAP-25": V9Row(
        "月球",
        "简单",
        "出舱依赖顺序 + 工具匹配",
        "FORCED",
        "VALIDATED",
        "覆盖率计入被拒诊断",
        "DCR-08/25",
    ),
    "MAP-26": V9Row(
        "月球",
        "中等",
        "诊断→修复→回滚",
        "OPTIONAL",
        "NEEDS_MORE_EVIDENCE",
        "no_diagnosis 成功；tests_run 计入被拒",
        "DCR-14/26",
    ),
    "MAP-27": V9Row("月球", "困难", "电量/氧气/多目标协调", "FORCED", "VALIDATED", "", "DCR-27"),
    "MAP-28": V9Row(
        "古堡",
        "简单",
        "证据收集 + 时间线",
        "FORCED",
        "NEEDS_REDESIGN",
        "枚举未公开；timeline 未区分 N/A",
        "",
    ),
    "MAP-29": V9Row(
        "古堡", "中等", "证词可靠性分诊", "BLOCKED", "NEEDS_REDESIGN", "compare 语义未公开", ""
    ),
    "MAP-30": V9Row(
        "古堡",
        "困难",
        "跨阶段案卷推理",
        "BLOCKED",
        "NEEDS_REDESIGN",
        "条目映射未公开；记录≠证据",
        "",
    ),
}


@dataclass
class V10Row:
    """V10 每图当前状态；Batch 依据证据更新，不得手填哈希。"""

    construct_status: str
    validity_status: str
    defect: str
    dcr_id: str = ""
    environment_seeds: str = "0"
    oracle: str = "pending"
    baseline: str = "pending"
    ablation: str = "pending"
    mimo: str = "not_run"
    decision: str = "pending"
    review: str = "agent_reviewed"
    extra: dict[str, Any] = field(default_factory=dict)


def initial_state() -> dict[str, V10Row]:
    """Batch 0 起点：完全继承 V9，尚未有 V10 证据。"""

    return {
        map_id: V10Row(
            construct_status=row.construct_status,
            validity_status=row.validity_status,
            defect=row.defect,
            dcr_id=row.dcr,
            environment_seeds="0（V8/V9 仅 seed0；见 baseline-audit §5）",
            oracle="V9 seed0",
            baseline="V9 seed0",
            ablation="V9 seed0",
            mimo="V8 3 rep / V9 pilot",
            decision="Batch 0 继承 V9，待 V10 证据",
        )
        for map_id, row in V9_BASELINE.items()
    }


def _hashes(map_id: str) -> tuple[str, str]:
    import importlib

    try:
        catalog = importlib.import_module("agent_arena.v10.runtime.catalog")
        return str(catalog.rule_hash(map_id))[:12], str(catalog.metric_hash(map_id))[:12]
    except ModuleNotFoundError:
        from agent_arena.v8.metrics import metric_schema_hash
        from agent_arena.worlds.scenario_v8.catalog import rule_hash as v8_rule_hash

        return f"v8:{v8_rule_hash(map_id)[:12]}", f"v8:{metric_schema_hash(map_id)[:12]}"


def rows(state: dict[str, V10Row]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for map_id, base in V9_BASELINE.items():
        current = state[map_id]
        rule, metric = _hashes(map_id)
        output.append(
            {
                "map_id": map_id,
                "world": base.world,
                "difficulty": base.difficulty,
                "claimed_construct": base.construct,
                "construct_status": current.construct_status,
                "validity_status": current.validity_status,
                "defect": current.defect,
                "dcr_id": current.dcr_id,
                "rule_hash": rule,
                "metric_hash": metric,
                "environment_seeds": current.environment_seeds,
                "oracle": current.oracle,
                "baseline": current.baseline,
                "ablation": current.ablation,
                "mimo": current.mimo,
                "decision": current.decision,
            }
        )
    return output


def write(state: dict[str, V10Row], *, title_note: str = "") -> None:
    table = rows(state)
    V10_DOCS.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(table)
    (V10_DOCS / "map-status-matrix.csv").write_text(buffer.getvalue(), encoding="utf-8")
    (V10_DOCS / "map-status-matrix.json").write_text(
        json.dumps(
            {map_id: asdict(item) for map_id, item in state.items()},
            ensure_ascii=False,
            sort_keys=True,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    lines = [
        "# V10 30 图状态矩阵",
        "",
        "- 由 `python -m agent_arena.v10.status` 生成；CSV 同目录 `map-status-matrix.csv`。",
        "- `construct_status`（FORCED/OPTIONAL/BYPASS/BLOCKED）与 `validity_status`"
        "（VALIDATED/NEEDS_MORE_EVIDENCE/NEEDS_REDESIGN/BLOCKED）是两个独立维度。",
        "- 全部为 `agent_reviewed`，没有 `human_approved`。",
    ]
    if title_note:
        lines.append(f"- {title_note}")
    lines += [
        "",
        "| map | 难度 | 构念 | V9 效度 | V10 构念 | V10 效度 | seeds | Oracle | 基线 | 消融 | MiMo | DCR | 结论 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in table:
        base = V9_BASELINE[row["map_id"]]
        lines.append(
            "| {map_id} | {world}{difficulty} | {claimed_construct} | {v9} | {construct_status} "
            "| {validity_status} | {environment_seeds} | {oracle} | {baseline} | {ablation} "
            "| {mimo} | {dcr_id} | {decision} |".format(
                v9=f"{base.construct_status}/{base.validity_status}", **row
            )
        )
    counts: dict[str, list[str]] = {}
    for row in table:
        counts.setdefault(row["validity_status"], []).append(row["map_id"][-2:])
    construct: dict[str, list[str]] = {}
    for row in table:
        construct.setdefault(row["construct_status"], []).append(row["map_id"][-2:])
    lines += ["", "## 汇总", "", "| 维度 | 状态 | 图数 | 地图 |", "|---|---|---:|---|"]
    for name in ("VALIDATED", "NEEDS_MORE_EVIDENCE", "NEEDS_REDESIGN", "BLOCKED"):
        maps = counts.get(name, [])
        lines.append(f"| 效度 | {name} | {len(maps)} | {'、'.join(maps)} |")
    for name in ("FORCED", "OPTIONAL", "BYPASS", "BLOCKED"):
        maps = construct.get(name, [])
        lines.append(f"| 构念 | {name} | {len(maps)} | {'、'.join(maps)} |")
    (V10_DOCS / "map-status-matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def current_state() -> dict[str, V10Row]:
    """读取最新的 V10 状态；各 Batch 的证据模块在这里登记更新。"""

    state = initial_state()
    import importlib

    try:
        evidence_state = importlib.import_module("agent_arena.v10.evidence_state")
    except ModuleNotFoundError:
        return state
    evidence_state.apply(state)
    return state


def main() -> None:
    write(current_state())
    print(V10_DOCS / "map-status-matrix.md")


if __name__ == "__main__":
    main()
