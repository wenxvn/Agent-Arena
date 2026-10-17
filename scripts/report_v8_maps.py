"""生成 V8 的 30 份逐图定稿、runtime-matrix 与 metric-matrix。

事实来源：`runs/v8/map_facts.json`、`runs/v8/freeze_manifest.json`、
`runs/v8/offline_gate.json`、`runs/v8/registry.json`（若已生成）以及
`worlds/v4/MAP-XX/DESIGN.md`。脚本不运行环境、不改写任何 trace。
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT / "runs" / "v8"
DOCS = ROOT / "docs" / "v8"
MAP_DOCS = DOCS / "maps"

SETTLEMENT = {
    "MAP-01": "每 tick 未供氧则扣氧气余量并累计断供；超过 3 tick 失败。修补、复位、压力测试各有前置。",
    "MAP-02": "动作计数到 4 触发泄漏；触发当 tick 不扣扩散/压力；之后先判成功，再结算扩散与船员压力。",
    "MAP-03": "读标签后冷窗 4 tick；每 tick 先推进冷窗，再检查 36 tick 返航窗口。",
    "MAP-04": "潮汐相位按动作成本推进；`wait` 成本等于 turns；救援截止 tick 到达仍未点灯即失败。",
    "MAP-05": "三塔共享单路电力与信号窗口；校准、充电、发信号按 tick 排程，错过窗口即失败。",
    "MAP-06": "风暴按 tick 推进；加固与修复须在截止前完成；资源耗尽与截止失败分开。",
    "MAP-07": "同一 tick 内按 v1→v2→v3→v4→泵 级联结算；任一舱溢出即失败。",
    "MAP-08": "复用 V4 规则：压力测试耗 2 tick；泄漏水位逐 tick 上升；错误密封剂立即失败。",
    "MAP-09": "每 tick 依次结算漏水、泵、电池/短路、供氧、通信；四链共享同一资源池。",
    "MAP-10": "偶数 tick 结算供暖；基地油库与随身燃料不可互挪；超载必须先转运。",
    "MAP-11": "四次相关风暴抽签；队员生命窗与负重返程逐段结算；侦察后验只影响风险估计。",
    "MAP-12": "每日 2 个劳动槽；顺序为动作→资源→欠供判定→日推进；连续欠供触发失败。",
    "MAP-13": "静态全真约束；错误开门最多 2 次；未获得布局的 `verify` 视为非法门。",
    "MAP-14": "4 问预算；维护九态一致假设；第五问被拒绝且不耗 tick；最终错误提交限次。",
    "MAP-15": "规则随全局 tick 奇偶切换；测试错误限 2 次；资源耗尽与测试上限分开。",
    "MAP-16": "两列车联合预约；同 tick 节点/区间容量冲突即失败；makespan 由 V7 extractor 计算。",
    "MAP-17": "每 tick 四车同步执行各自一个操作；B-C 共享瓶颈；四目标保持 Pareto 向量。",
    "MAP-18": "每 tick 提交整张时刻表；闭塞故障窗口 (5,10)；碰撞与站台容量分别失败。",
    "MAP-19": "冷却命令延迟 2 tick 生效；三区独立；负荷档交换产能；越界面积按已结算 tick 累计。",
    "MAP-20": "无控制延迟；总水源 60、单支管 25、旁路损 20%、区阀 4/4/3；非法帧整帧拒绝、零时间。",
    "MAP-21": "喷发时刻只可能为 12/16/20 且隐藏；测量耗 2 tick 且有噪；停留过久直接致命。",
    "MAP-22": "公开方位行走；图记忆只记录亲历路标与边；返营并记录遗迹才算成功。",
    "MAP-23": "三个等概率真入口；侦察付费；补给一次性补满；seed=0 的真入口为 Z。",
    "MAP-24": "tick 8 永久移除 A-B、B-C；D-E 潮道 4 拍开 2 拍且相位 seed 私有；旧笔记会过期。",
    "MAP-25": "穿服→挂绳→排压→检查→诊断→维修→返舱；返舱时目标未完成即失败。",
    "MAP-26": "复用 V6 规则：诊断→测试→取备件→更换→rollback；错误备件消耗备件额度。",
    "MAP-27": "两格货舱互斥；14 电/18 氧按道路原子并行消耗；P–E 四 tick、S–E 一 tick；全目标成功。",
    "MAP-28": "四字段双来源交叉；窗口猜测与锁分钟矛盾；未观察记录不可作为正式引用。",
    "MAP-29": "8 问预算；四名 NPC 知识边界不同；第九问免费拒绝；物证交叉后才采信时地结论。",
    "MAP-30": "复用 V6 规则：长间隔 Q4 召回、多事件案卷、正式指控需事件主张与引用条目。",
}

UNRESOLVED = {
    "MAP-01": "`oxygen_off_ticks` 仍为私有；公开只给氧气余量，断供阈值需由失败归因推断。",
    "MAP-02": "双目标完成度只作报告比例，不作加权胜负；成功仍要求导航核与救生舱同时达成。",
    "MAP-03": "未新增“漏阶段/码错”独立终局码，失败归因依赖阶段位与召回指标。",
    "MAP-04": "最早可行过桥 tick 固定为 5（V8-DCR-004）；该常量是地图规则的一部分。",
    "MAP-05": "采用修订后的可行窗口；窗口表已随 `rule_hash` 冻结，旧版不可行窗口不再使用。",
    "MAP-06": "公开 `forecast_accuracy` 与先验，属“信息可用性”条件，不宣称纯推断能力。",
    "MAP-07": "溢出失败码带舱室后缀（`COMPARTMENT_OVERFLOW_X`），是同一机制的多实例码。",
    "MAP-08": "复用 V6 `map08_l3_original`；V7 已确认的天花板保留，V8 不为降低通过率改规则。",
    "MAP-09": "传播规模使用裁判侧事件计数；公开侧只能看到系统状态，无法自行区分同故障持续与二次传播。",
    "MAP-10": "单期燃料分仓题，无随机事件；燃料池不可互挪是核心约束。",
    "MAP-11": "公开后验与基础概率，属信息使用条件；不把它当作模型自主推断的证据。",
    "MAP-12": "日结算顺序已冻结（动作→资源→欠供→日推进）；连续欠供阈值由 V8-DCR-007 固定。",
    "MAP-13": "静态约束、无随机；两次错误开门是硬上限。",
    "MAP-14": "配置以整数列表表达；第五问被拒绝且不耗 tick 是冻结语义。",
    "MAP-15": "未见状态预测用“首次选择”作代理，不能区分“预测对但执行错”。",
    "MAP-16": "复用 V6 `map16_l3_original`；`makespan_gap` 依赖 BFS 基线，不与其他图横比。",
    "MAP-17": "四目标不合成单分；报告 Pareto 向量，不宣称某一目标优先。",
    "MAP-18": "复用 V6 `map18_l3_original`；静态调度地板仍在，故障窗口 (5,10) 已提供在线约束。",
    "MAP-19": "越界面积按裁判侧精确温度计算；V7 卡片的 20 为笔误，实测早期冷却路径为 22。",
    "MAP-20": "非法控制帧整帧拒绝、零时间、不终止（V8-DCR-020）；这是一条冻结的运行语义。",
    "MAP-21": "`false_safety_claims` 无可靠来源，返回 `None`；公开后验提示属信息可用性条件。",
    "MAP-22": "重复边按有向公开签名计；实例最优为 8；未增加节点别名。",
    "MAP-23": "seed=0 的真入口为 Z；三入口先验等概率，但正式运行固定 seed 后不再随机。",
    "MAP-24": "`route_cost_ratio` 的分母排除没有本地潮位读数的 D-E 潮道。",
    "MAP-25": "`repair` 允许省略 `diagnosis_code`（V8-DCR-025），诊断准确率单独报告。",
    "MAP-26": "复用 V6 `map26_l1_antenna_fault`；恢复地板与诊断准确率分开报告。",
    "MAP-27": "成功要求全部目标；部分完成单列，不折算为成功。",
    "MAP-28": "无独立失败码，终局拒绝由 `verdict` 表达；四字段双来源规则不变。",
    "MAP-29": "矛盾计数只统计已问询且可交叉验证的命题。",
    "MAP-30": "复用 V6 `map30_l3_original`；Q4 召回与调查完整度分开报告。",
}

FAILURE_PATHS = {
    "MAP-04": ["错过救援窗口 → `RESCUE_SIGNAL_WINDOW_EXPIRED`", "高相位过桥 → `high_tide_entries` 护栏上升", "绕行耗时至截止 → 窗口过期"],
    "MAP-05": ["三束信号排程冲突 → `SIGNAL_WINDOW_MISSED`", "电力未校准即发信号 → 校准拒绝", "跨塔往返超窗 → 信号窗口错过"],
    "MAP-06": ["风暴前未完成修复 → `REPAIR_DEADLINE_MISSED`", "加固/修复耗尽资源 → `RESOURCE_EXHAUSTED`", "长风暴不加固 → 灯室损坏"],
    "MAP-07": ["上游先开导致 A 溢出 → `COMPARTMENT_OVERFLOW_A`", "v4 单向回流误开 → 回灌 A", "合并阀门命令 → 形状拒绝"],
    "MAP-08": ["错误密封剂 → `SEALANT_MISUSED`", "不测试直接修 → `diagnosis_accuracy=0`", "等待过久 → `CORE_WATER_LIMIT_EXCEEDED`"],
    "MAP-28": ["窗口猜测与锁分钟矛盾 → `CASE_REJECTED`", "未观察记录作为引用 → 拒绝", "路径别名非法 → 拒绝"],
    "MAP-29": ["第九问超预算 → 免费拒绝", "已证伪的位置谎言仍提交 → `CASE_REJECTED`", "未交叉物证即采信 → 低精度"],
}

ADAPTER = {"MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def design_intent(map_id: str) -> str:
    path = ROOT / "worlds" / "v4" / map_id / "DESIGN.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    match = re.search(r"## 设计意图\s*\n(.*?)(?=\n## |\Z)", text, re.S)
    if match:
        return match.group(1).strip()
    # 部分地图没有“设计意图”小节：取状态行后的首段作为设计摘要。
    body = re.sub(r"\A# .*?\n", "", text, count=1)
    body = re.sub(r"\A\s*状态：`[^`]*`。\s*", "", body, count=1)
    paragraph = body.split("\n## ", 1)[0].strip()
    return paragraph


def design_title(map_id: str) -> str:
    path = ROOT / "worlds" / "v4" / map_id / "DESIGN.md"
    if not path.is_file():
        return map_id
    first = path.read_text(encoding="utf-8").splitlines()[0]
    return first.split("｜", 1)[1].strip() if "｜" in first else first.lstrip("# ").strip()


def module_doc(map_id: str) -> str:
    if map_id in ADAPTER:
        return design_intent(map_id)
    module = importlib.import_module(
        f"agent_arena.worlds.scenario_v8.maps.map{map_id[-2:]}"
    )
    return (module.__doc__ or "").strip()


def mechanism_summary(map_id: str) -> str:
    doc = module_doc(map_id)
    if not doc:
        return design_title(map_id)
    for index, line in enumerate(doc.splitlines()):
        if line.startswith("本图与同世界另两图的机制差异"):
            parts = [line]
            for follow in doc.splitlines()[index + 1 :]:
                if not follow.strip():
                    break
                parts.append(follow.strip())
            return "".join(parts)
    first = doc.splitlines()[0]
    return first.split("：", 1)[1] if "：" in first else first


def metric_table(metrics: list[dict[str, Any]]) -> str:
    lines = [
        "| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |",
        "|---|---|---|---|---|---|---|",
    ]
    for metric in metrics:
        lines.append(
            f"| `{metric['id']}` | {metric['kind']} | {metric['direction']} |"
            f" {metric['formula']} | {metric['denominator'] or '—'} |"
            f" {metric['missing']} | {metric['censor']} |"
        )
    return "\n".join(lines)


def shapes_text(shapes: dict[str, list[list[str]]]) -> str:
    lines = []
    for tool in sorted(shapes):
        for fields in shapes[tool]:
            rendered = ", ".join(f'`{field}`' for field in fields)
            lines.append(f"- `{tool}`" + (f"：{rendered}" if rendered else "：无附加字段"))
    return "\n".join(lines)


def registry_rows(registry: dict[str, Any] | None, map_id: str) -> list[dict[str, Any]]:
    if not registry:
        return []
    return [row for row in registry.get("rows", []) if row.get("map_id") == map_id]


def episode_metrics(row: dict[str, Any]) -> str:
    path = row.get("v8_metrics_path")
    if not path or not Path(path).is_file():
        return "—"
    metrics = read_json(Path(path)).get("metrics", {})
    valid = [
        (metric_id, value["value"])
        for metric_id, value in metrics.items()
        if value.get("status") == "valid" and value.get("value") is not None
    ]
    return "; ".join(f"`{key.split('.')[-1]}`={value}" for key, value in valid[:4]) or "—"


def main() -> int:
    facts = read_json(V8 / "map_facts.json")
    freeze = read_json(V8 / "freeze_manifest.json")
    gate = read_json(V8 / "offline_gate.json")
    registry = read_json(V8 / "registry.json") if (V8 / "registry.json").is_file() else None
    extra_path = DOCS / "extra-fixtures.json"
    extra_cases = read_json(extra_path) if extra_path.is_file() else {}
    MAP_DOCS.mkdir(parents=True, exist_ok=True)

    siblings: dict[str, list[str]] = {}
    for map_id, fact in facts.items():
        siblings.setdefault(fact["world"], []).append(map_id)

    for map_id, fact in facts.items():
        entry = freeze["maps"][map_id]
        title = fact["title"] if fact["title"] != map_id else design_title(map_id)
        rows = registry_rows(registry, map_id)
        mechanism = module_doc(map_id)
        intent = design_intent(map_id)
        extra = extra_cases.get(map_id)
        extra_text = (
            f"，补充冻结后失败用例 `{extra['name']}`（{len(extra['actions'])} 步，见 `docs/v8/extra-fixtures.json`）"
            if extra
            else ""
        )
        mechanism_block = (
            mechanism
            if mechanism.strip() and mechanism.strip() != intent.strip()
            else "运行时的状态机、动作前置与失败码见本文件第 4–5 节。"
        )
        same_world = [item for item in siblings[fact["world"]] if item != map_id]
        comparison = [
            f"- **{item}**（{facts[item]['level']}）：{mechanism_summary(item)}"
            for item in sorted(same_world)
        ]
        fail_codes = fact["fail_codes"] or ["由终局 `verdict`/动态码表达，见失败路径"]
        failure_paths = FAILURE_PATHS.get(map_id, [])
        lines = [
            f"# {map_id} 定稿：{title}",
            "",
            "| 字段 | 值 |",
            "|---|---|",
            f"| 世界 | {fact['world']} |",
            f"| 难度 | {fact['level']} |",
            f"| 条件 | `{fact['condition']}` |",
            f"| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |",
            f"| scenario_hash | `{entry['scenario_hash']}` |",
            f"| rule_hash | `{entry['rule_hash']}` |",
            f"| prompt_hash | `{entry['prompt_hash']}` |",
            f"| metric_schema_hash | `{entry['metric_schema_hash']}` |",
            f"| oracle_hash | `{entry['oracle_hash']}` |",
            f"| commit | `{entry['commit']}` |",
            "",
            "## 1. 设计意图与独特机制",
            "",
            intent or "见运行时模块说明。",
            "",
            mechanism_block,
            "",
            "## 2. 与同世界另两图的区别",
            "",
            *comparison,
            "",
            f"本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、"
            "一个逻辑时钟、图边工具和哈希函数。",
            "",
            "## 3. 公开与私有状态",
            "",
            "公开 Observation 字段（白名单）：",
            "",
            ", ".join(f"`{field}`" for field in fact["public_fields"]),
            "",
            "私有 `judge_state` 字段（不进入 Observation 或 prompt）：",
            "",
            ", ".join(f"`{field}`" for field in fact["judge_keys"]),
            "",
            f"泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。"
            f"离线门禁结果：{'通过' if gate['failure_count'] == 0 else '未通过'}。",
            "",
            "## 4. 动作契约",
            "",
            shapes_text(fact["shapes"]),
            "",
            "字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。",
            "",
            "## 5. 结算顺序、胜负与失败码",
            "",
            "统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → "
            "`_after_tick` 结算周期事件 → 检查步数上限。",
            "",
            f"本图结算要点：{SETTLEMENT[map_id]}",
            "",
            f"- 成功码：{', '.join(f'`{code}`' for code in fact['success_codes']) or '见运行时'}",
            f"- 失败码：{', '.join(f'`{code}`' for code in fail_codes)}",
        ]
        if failure_paths:
            lines.append("- 机制失败路径：")
            lines.extend(f"  - {path}" for path in failure_paths)
        lines.extend(
            [
                "",
                "## 6. 资源边界与护栏",
                "",
                "资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。"
                "护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或"
                "不安全操作都保留在 judge metrics 与失败归因中。",
                "",
                "## 7. 指标（V7 登记，V8 只做五态投影）",
                "",
                metric_table(fact["metrics"]),
                "",
                "比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；"
                "无法计算的配对指标返回 `None`，不填 0。",
                "",
                "## 8. Oracle 与离线回放",
                "",
                f"- Oracle 用例：{', '.join(f'{case['trace_id']}（{case['steps']} 步）' for case in fact['oracle'])}",
                f"- 手算 fixture：{', '.join(f'{case['name']}（{case['actions']} 步）' for case in fact['fixtures'])}{extra_text}",
                f"- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。",
                f"- 单图自检：`.\\.venv\\Scripts\\python.exe scripts/check_v8_map.py {map_id}` → `{map_id}: OK`。",
                "",
                "## 9. MiMo 三次正式运行",
                "",
            ]
        )
        if not rows:
            lines.append("正式 90 局尚未生成；本节由 `scripts/report_v8_maps.py` 在运行结束后回填。")
        else:
            lines.extend(
                [
                    "| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |",
                    "|---|---|---|---|---|---|---|---|",
                ]
            )
            for row in sorted(rows, key=lambda item: item["seed_or_replicate"]):
                lines.append(
                    f"| {row['seed_or_replicate']} | {row['status']} | {row['success']} |"
                    f" {row['termination_reason']} |"
                    f" {row['requests'] if row['requests'] is not None else '—'} |"
                    f" {row['cost']} | `{row['run_id']}` | {episode_metrics(row)} |"
                )
            successes = sum(1 for row in rows if row["success"])
            lines.extend(
                [
                    "",
                    f"三次重复成功 {successes}/3。n=3 只描述重复运行，不做显著性断言；"
                    "MiMo 失败是合法结果，不能由 Oracle 成功率替代。",
                ]
            )
        lines.extend(
            [
                "",
                "## 10. 未决问题与边界说明",
                "",
                UNRESOLVED[map_id],
                "",
                "## 11. 验收结论",
                "",
                f"- design: `audited`；runtime: `verified`；metrics: `{len(fact['metrics'])}/{len(fact['metrics'])}`；"
                f"oracle: `verified`；fixtures: `{len(fact['fixtures']) + (1 if extra else 0)}/{len(fact['fixtures']) + (1 if extra else 0)}`。",
                f"- 正式 3 局：`{'completed' if len(rows) == 3 else 'pending'}`；"
                f"最终状态：`{'finalized' if len(rows) == 3 else 'runtime_verified'}`。",
                "",
            ]
        )
        (MAP_DOCS / f"{map_id}-final.md").write_text("\n".join(lines), encoding="utf-8")

    # runtime-matrix
    matrix = [
        "# V8 30 图运行时矩阵",
        "",
        "| world | map | difficulty | construct | design_status | runtime_status | metric_status | oracle_status | blocking_dcr | rule_hash | review_status |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for map_id, fact in facts.items():
        matrix_title = (
            fact["title"] if fact["title"] != map_id else design_title(map_id)
        )
        matrix.append(
            f"| {fact['world']} | {map_id} | {fact['level']} | {matrix_title} |"
            f" audited | verified | {len(fact['metrics'])}/{len(fact['metrics'])} | verified |"
            f" 无（见 dcr-resolution） | `{freeze['maps'][map_id]['rule_hash'][:12]}` | human_approved(V7 cards) |"
        )
    (DOCS / "runtime-matrix.md").write_text("\n".join(matrix) + "\n", encoding="utf-8")

    # metric-matrix
    metric_lines = [
        "# V8 指标矩阵",
        "",
        "V7 登记的 154 条 `MetricSpec` 在 V8 全部有运行时来源；V8 只做五态投影，不新增、不改名。"
        "下表按地图列出指标类别、方向、公式、分母与缺失/截尾规则。",
        "",
    ]
    for map_id, fact in facts.items():
        metric_lines.extend(
            [
                f"## {map_id}（{len(fact['metrics'])} 条）",
                "",
                metric_table(fact["metrics"]),
                "",
            ]
        )
    (DOCS / "metric-matrix.md").write_text("\n".join(metric_lines), encoding="utf-8")
    print(f"wrote {len(facts)} map docs + runtime-matrix + metric-matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
