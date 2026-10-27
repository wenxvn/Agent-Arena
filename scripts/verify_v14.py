"""V14 离线验收（零外部请求）。

用法：
    uv run python scripts/verify_v14.py
    uv run python scripts/verify_v14.py --report runs/v14/selfcheck.json

检查的是 **V14 新增的事实边界**，不是"再跑一遍 V13"：

1. `UNKNOWN` 不得渲染成 `0/N`；
2. 跨协议不得静默合并；
3. seed 与重复必须分开计数；
4. 未批准时 LIVE 只能是 `PLANNED_ONLY`；
5. CI 证据必须登记在 `docs/v14/ci-evidence.md`；
6. 导出必须同口径（行数/分母/模式/空值）；
7. 诊断必须有锚点；
8. Memory/Planning/Reflection 的机制证据可复算；
9. MAP-30 阶梯与保守区间可复算；
10. 能力画像的 `UNAVAILABLE` 不被写成 0；
11. 结论强度三字段与禁区措辞；
12. SDK 与账本复算；
13. 交付文档与截图齐备。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

RESULTS: list[dict[str, Any]] = []

def check(name: str, function: Callable[[], tuple[bool, str]]) -> None:
    started = time.perf_counter()
    try:
        ok, detail = function()
    except Exception as exc:  # noqa: BLE001 - 验收脚本要报告失败而不是崩溃
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    RESULTS.append(
        {
            "name": name,
            "ok": bool(ok),
            "detail": detail[:400],
            "seconds": round(time.perf_counter() - started, 4),
        }
    )

def _history():
    from agent_arena.lab.v13.history import load_v12_history

    return load_v12_history()

# --------------------------------------------------------------------- checks
def check_unknown_semantics() -> tuple[bool, str]:
    from agent_arena.lab.v13.validity import (
        mechanism_triggered_summary,
        six_map_audit,
        validity_markdown,
    )

    records = _history()
    summary = mechanism_triggered_summary(records)
    if summary["available"]:
        return False, "历史 CSV 不应有 mechanism_triggered，可用性判断有误"
    text = validity_markdown(six_map_audit(records))
    if "UNKNOWN (0 observed" not in text:
        return False, "markdown 没有渲染 UNKNOWN (0 observed)"
    if "| 0/9 |" in text or "| 0/35 |" in text:
        return False, "markdown 仍把未知渲染成 0/N"
    return True, f"全部 {summary['unknown']} 条记录的机制触发为 UNKNOWN，未渲染成 0"

def check_protocol_isolation() -> tuple[bool, str]:
    from agent_arena.lab.v14.data_audit import six_map_protocol_audit

    audit = six_map_protocol_audit(_history())
    pooled = audit["pooled_maps"]
    if not pooled:
        return False, "没有检测到多协议图（MAP-22 至少应有 3 个分组）"
    flagged = {
        item["map_id"]: item["pooling_allowed"] for item in audit["maps"]
    }
    if any(flag for map_id, flag in flagged.items() if map_id in pooled):
        return False, "多协议图仍被标记为可合并"
    return True, f"多协议图禁止合并：{pooled}"

def check_seed_and_replicates() -> tuple[bool, str]:
    from agent_arena.lab.v14.conditions import seed_coverage, validate_seed

    records = _history()
    coverage = seed_coverage(records)
    if coverage["illegal_seeds"]:
        return False, f"出现非法 seed：{coverage['illegal_seeds'][:3]}"
    ok_rows = [row for row in coverage["maps"] if row["replicates_are_not_seeds"]]
    if len(ok_rows) != len(coverage["maps"]):
        return False, "有地图把重复当成 seed"
    bad = validate_seed("MAP-22", 99)
    if bad["valid"]:
        return False, "越界 seed 未被拒绝"
    projects = {
        row["map_id"]: (row["independent_seed_count"], row["max_replicates"])
        for row in coverage["maps"]
    }
    return True, f"seed/重复分开计数：{projects}"

def check_approval_blocked() -> tuple[bool, str]:
    from agent_arena.lab.v14.live_plan import (
        LIVE_PENDING,
        STATUS_PLANNED,
        plan_a_preflight,
        plan_a_specs,
    )

    plan = plan_a_preflight({})
    if plan["status"] != STATUS_PLANNED or plan["live_status"] != LIVE_PENDING:
        return False, f"状态不是 PLANNED_ONLY/LIVE_PENDING：{plan['status']}/{plan['live_status']}"
    for item in plan_a_specs():
        spec = item["spec"]
        if spec.mode.value != "simulated":
            return False, f"{item['arm_id']} 默认不是 SIMULATED"
        if spec.approval.approved:
            return False, f"{item['arm_id']} 未经批准却带 approved=True"
    return True, "6 个规格默认 SIMULATED，无 LiveApproval，状态 PLANNED_ONLY"

def check_ci_evidence() -> tuple[bool, str]:
    path = ROOT / "docs" / "v14" / "ci-evidence.md"
    if not path.is_file():
        return False, "缺少 docs/v14/ci-evidence.md"
    text = path.read_text(encoding="utf-8")
    required = ("40435185866", "40482235016", "40477841302", "continue-on-error")
    missing = [item for item in required if item not in text]
    if missing:
        return False, f"CI 证据缺少：{missing}"
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    if "continue-on-error" in workflow:
        return False, "ci.yml 仍保留 continue-on-error"
    return True, "CI 证据已登记，lab-e2e 为阻断门禁"

def check_export_consistency() -> tuple[bool, str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from audit_v14_engineering import _export_consistency_sample

    sample = _export_consistency_sample()
    if not sample["ok"]:
        return False, f"导出一致性失败：{sample['problems']}"
    return True, f"导出 {sample['files']} 行数/分母/模式一致"

def check_diagnostics_anchor() -> tuple[bool, str]:
    from agent_arena.lab.v14.failure_capability import (
        ANCHOR_COMPLETE,
        ANCHOR_MISSING,
        audit_findings,
        failure_fixtures,
        finding_anchor,
    )

    fixtures = failure_fixtures()
    layers = {item["fixture"]: item["expected_layer"] for item in fixtures["fixtures"]}
    if layers.get("REJECTED_NO_PROGRESS") != "POLICY_BEHAVIOUR":
        return False, "被拒无进展 fixture 的层不对"
    if layers.get("PROGRESS_THEN_BUDGET_CENSORED") != "BUDGET_CENSORED":
        return False, "有进展但预算耗尽 fixture 的层不对"
    if layers.get("INTERFACE_ARTEFACT") != "INTERFACE_CONTRACT":
        return False, "接口假象 fixture 的层不对"
    anchored = finding_anchor(
        {
            "category": "repeated_action_loop",
            "run_id": "r1",
            "evidence_steps": (3,),
            "action": {"tool": "move"},
            "public_result": "BEARING_NOT_AVAILABLE",
        }
    )
    if anchored["status"] != ANCHOR_COMPLETE:
        return False, "完整锚点未被识别"
    unanchored = finding_anchor({"category": "no_progress_window"})
    if unanchored["status"] != ANCHOR_MISSING:
        return False, "无锚点未被识别"
    audit = audit_findings([{"category": "no_progress_window"}])
    if audit["unanchored"] != 1:
        return False, "锚点统计不正确"
    return True, "锚点三态 + 三个 fixture 层级正确"

def check_agent_mechanisms() -> tuple[bool, str]:
    from agent_arena.lab.v14.agent_studies import memory_study_report
    from agent_arena.lab.v14.planning_study import planning_study_report
    from agent_arena.lab.v14.reflection_study import (
        exposure_gate,
        reflection_study_report,
    )

    memory = memory_study_report()
    probe = memory["probes"]["context_only_on"]
    if not probe["route_matches_expected"] or probe["memory_block_leaks"]:
        return False, "memory probe 的路线/泄漏检查失败"
    if not memory["arms"]["all_single_factor"]:
        return False, "memory 臂不是单因子"

    planning = planning_study_report()
    adaptive = planning["probes"]["adaptive"]
    if adaptive["planner_requests"] == 0:
        return False, "planning probe 没有触发 Planner"
    if adaptive["total_requests"] != adaptive["decisions"] + adaptive["planner_requests"]:
        return False, "Planner 请求没有计入总请求"
    if not planning["arms"]["all_single_factor"]:
        return False, "planning 臂不是单因子"

    reflection = reflection_study_report()
    no_trigger = reflection["probes"]["no_trigger_on"]
    gate = exposure_gate(no_trigger)
    if gate["status"] != "NO_TREATMENT_EXPOSURE":
        return False, "零触发没有被标成 NO_TREATMENT_EXPOSURE"
    if reflection["probes"]["reflection_on"]["triggered"] == 0:
        return False, "reflection_on 没有触发"
    return True, (
        f"memory route_matches_expected=True；planning planner_requests="
        f"{adaptive['planner_requests']}；reflection 零触发→NO_TREATMENT_EXPOSURE"
    )

def check_map30_ladder() -> tuple[bool, str]:
    from agent_arena.lab.v14.map_audit import (
        map30_conservative_interval,
        map30_three_axis,
    )

    axis = map30_three_axis(_history())
    if len(axis["tiers"]) < 3:
        return False, f"MAP-30 预算档位不足：{len(axis['tiers'])}"
    interval = map30_conservative_interval(axis)
    available = [item for item in interval["intervals"] if item.get("available")]
    if not available:
        return False, "没有可用的保守区间"
    for item in available:
        low, high = item["supported_decisions"]
        if low > high:
            return False, f"区间下界大于上界：{item}"
    axes = [tier["bottleneck_axis"] for tier in axis["tiers"]]
    if "REQUESTS" not in axes:
        return False, "第一档没有识别出请求瓶颈"
    return True, f"3 档瓶颈轴 {axes}；区间 {[i['supported_decisions'] for i in available]}"

def check_capability_gaps() -> tuple[bool, str]:
    from agent_arena.lab.v14.failure_capability import capability_with_gaps

    profile = capability_with_gaps(_history())
    by_dim = {row["dimension"]: row for row in profile["dimensions"]}
    if len(by_dim) != 6:
        return False, "维度数不是 6"
    for row in profile["dimensions"]:
        if row["status"] == "UNAVAILABLE" and row["success_rate"] is not None:
            return False, f"{row['dimension']} 标 UNAVAILABLE 却给了成功率"
        if "independent_seeds" not in row:
            return False, f"{row['dimension']} 缺独立 seed 字段"
    unavailable = profile["unavailable"]
    if "failure_recovery" not in unavailable:
        return False, "failure_recovery 应为 UNAVAILABLE（V12 无该维度数据）"
    return True, f"6 维画像齐全；UNAVAILABLE：{unavailable}"

def check_conclusion_strength() -> tuple[bool, str]:
    from agent_arena.lab.v14.failure_capability import conclusion_strength

    item = conclusion_strength(
        evidence_level="SUPPORTED",
        mechanism_exposure="NO_TREATMENT_EXPOSURE",
        effect_direction="NOT_MEASURABLE",
    )
    text = " ".join(item["forbidden_claims"])
    if "不等于显著改善" not in text:
        return False, "缺少「SUPPORTED ≠ 显著改善」的禁区"
    if "干预从未发生" not in text:
        return False, "零暴露时没有禁止「策略无效」的说法"
    try:
        conclusion_strength(
            evidence_level="PROVEN",
            mechanism_exposure="EXPOSED",
            effect_direction="IMPROVED",
        )
    except ValueError:
        return True, "三字段独立 + 非法取值被拒绝"
    return False, "非法 evidence_level 没有被拒绝"

def check_sdk_and_ledger() -> tuple[bool, str]:
    from agent_arena.lab.v14.engineering import sdk_hardening

    sdk = sdk_hardening()
    if not sdk["ok"]:
        failed = [item["name"] for item in sdk["base_checks"] if not item["ok"]]
        return False, f"SDK 自检失败：{failed}"
    ledger_path = ROOT / "runs" / "web" / "_ledger" / "web_ledger.jsonl"
    if ledger_path.is_file():
        from agent_arena.lab.v14.engineering import ledger_recompute

        report = ledger_recompute(_history())
        if not report["matches_v13_record"]:
            return False, f"账本复算与 V13 记录不一致：{report['open_ledger']}"
        return True, "SDK 全通过；账本 159/5641/¥5.43680012 复算一致"
    return True, "SDK 全通过；本机无账本文件，账本项记为未复算（不伪造）"

def check_docs() -> tuple[bool, str]:
    required = [
        "README.md",
        "baseline-audit.md",
        "experiment-protocol.md",
        "ci-evidence.md",
        "data-validity.md",
        "agent-studies.md",
        "live-plan.md",
        "map-audit.md",
        "failure-and-capability.md",
        "validation-report.md",
        "gap-audit.md",
        "release-checklist.md",
        "final-report.md",
        "decisions.md",
        "progress.md",
        "engineering-boundaries.md",
    ]
    missing = [name for name in required if not (ROOT / "docs" / "v14" / name).is_file()]
    if missing:
        return False, f"缺少交付文档：{missing}"
    shots = list((ROOT / "docs" / "v14" / "screenshots").glob("*.png"))
    if len(shots) < 5:
        return False, f"截图不足：{len(shots)}"
    return True, f"{len(required)} 份文档 + {len(shots)} 张截图齐备"

def check_no_frozen_changes() -> tuple[bool, str]:
    import subprocess

    try:
        output = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
    except Exception as exc:  # noqa: BLE001
        return False, f"无法检查工作区：{exc}"
    frozen = [
        line
        for line in output.splitlines()
        if any(
            marker in line
            for marker in (
                "worlds/scenario_v8",
                "src/agent_arena/v10/runtime",
                "docs/v12/real-runs",
            )
        )
    ]
    if frozen:
        return False, f"冻结资产被修改：{frozen[:3]}"
    return True, "冻结世界/运行时/历史 CSV 无改动"

CHECKS: tuple[tuple[str, Callable[[], tuple[bool, str]]], ...] = (
    ("unknown_semantics", check_unknown_semantics),
    ("protocol_isolation", check_protocol_isolation),
    ("seed_and_replicates", check_seed_and_replicates),
    ("approval_blocked", check_approval_blocked),
    ("ci_evidence", check_ci_evidence),
    ("export_consistency", check_export_consistency),
    ("diagnostics_anchor", check_diagnostics_anchor),
    ("agent_mechanisms", check_agent_mechanisms),
    ("map30_ladder", check_map30_ladder),
    ("capability_gaps", check_capability_gaps),
    ("conclusion_strength", check_conclusion_strength),
    ("sdk_and_ledger", check_sdk_and_ledger),
    ("docs_present", check_docs),
    ("frozen_assets", check_no_frozen_changes),
)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    for name, function in CHECKS:
        check(name, function)

    failed = [item["name"] for item in RESULTS if not item["ok"]]
    payload = {
        "schema": "v14-selfcheck-1",
        "ok": not failed,
        "checks": RESULTS,
        "failed": failed,
        "external_requests": 0,
    }
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if not args.quiet:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        print(f"V14 selfcheck: {'ok' if payload['ok'] else 'FAILED'} ({len(RESULTS)} checks)")
    return 0 if payload["ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())