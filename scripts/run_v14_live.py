"""V14 LIVE 执行器（方案 A：钉住配置的 6 个父实验）。

用法：

    # 1) 预检（零请求）：打印矩阵、费用与批准要求
    uv run python scripts/run_v14_live.py

    # 2) Pilot（最少成本，取自 54 局之内）：seed 0 × 1 次重复 = 6 局
    uv run python scripts/run_v14_live.py --pilot \
        --i-have-budget-approval --approval-cap 5.00 --submit

    # 3) 主矩阵（54 局）：在 Pilot 通过后再执行
    uv run python scripts/run_v14_live.py \
        --i-have-budget-approval --approval-cap 5.00 --submit

硬约束（与 `docs/v14/experiment-plan` / `docs/v13/live-budget-proposal.md` 一致）：

- 默认 ``preflight_only``：零请求，不会创建实验；
- 真实提交必须同时给 ``--i-have-budget-approval`` 与 ``--approval-cap``；
- 账本独立：``runs/v14/live/{web,lab}``，不与 V12/V13 账本混用；
- 单 worker 串行；每个父实验提交后立即摘要，失败立即停；
- 真实 MiMo（``mimo-v2.6-flash``）单价按 ``v10.ledger.PRICE_SHEETS["CNY"]``。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.contracts import (  # noqa: E402
    ExperimentMode,
    ExperimentSpec,
    LiveApproval,
)
from agent_arena.lab.experiment import (  # noqa: E402
    ExperimentBusy,
    ExperimentService,
    LiveApprovalRequired,
    preflight,
)
from agent_arena.lab.v13.history import load_v12_history  # noqa: E402
from agent_arena.lab.v14.data_audit import map_unit_costs  # noqa: E402
from agent_arena.lab.v14.live_plan import (  # noqa: E402
    PER_RUN_LIMITS,
    plan_a_single_factor_checks,
    plan_a_specs,
)
from agent_arena.web.service import RunService  # noqa: E402

LIVE_DIR = ROOT / "runs" / "v14" / "live"
DEFAULT_MODEL = "mimo-v2.6-flash"
DEFAULT_PROVIDER = "openai_compatible"

def _limits(args: argparse.Namespace) -> dict[str, Any]:
    """单局预算覆盖（空字典 = 用默认 90 请求 / 200k token / ¥0.50）。"""

    limits: dict[str, Any] = {}
    if args.request_cap:
        limits["per_run_request_cap"] = int(args.request_cap)
    if args.decision_cap:
        limits["per_run_decision_cap"] = int(args.decision_cap)
    if args.token_cap:
        limits["per_run_input_token_cap"] = int(args.token_cap)
    if args.per_run_cost:
        limits["per_run_cost_cap_cny"] = Decimal(str(args.per_run_cost))
    return limits

def _approval(args: argparse.Namespace) -> LiveApproval:
    approved = bool(args.i_have_budget_approval)
    return LiveApproval(
        approved=approved,
        approved_by=str(args.approved_by or "user") if approved else "",
        approved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if approved else None,
        max_cost_cny=Decimal(str(args.approval_cap)) if approved else None,
        note=(
            f"V14 方案 A；模型 {args.model}；"
            f"{'Pilot 6 局' if args.pilot else '主矩阵 54 局'}；"
            f"单局上限 {PER_RUN_LIMITS['per_run_request_cap']} 请求 / "
            f"{PER_RUN_LIMITS['per_run_input_token_cap']} token / "
            f"¥{PER_RUN_LIMITS['per_run_cost_cap_cny']}；"
            "unknown_spend 立即封账；单 worker 串行。"
        )
        if approved
        else "",
    )

def _specs(args: argparse.Namespace) -> list[dict[str, Any]]:
    approval = _approval(args)
    seeds = [int(seed) for seed in args.seeds]
    seeds = seeds[:1] if args.pilot else seeds
    replicates = 1 if args.pilot else int(args.replicates)
    limits = _limits(args)
    maps = None
    if args.map_override:
        maps = {"E1-a": ["MAP-22"], "E2-a": ["MAP-16"], "E3": ["MAP-22"]}
        for item in args.map_override:
            group, _, map_id = item.partition("=")
            maps[group.strip()] = [map_id.strip()]
    specs = plan_a_specs(
        maps=maps,
        seeds=seeds,
        replicates=replicates,
        mode=ExperimentMode.LIVE,
        provider_id=args.provider,
        model=args.model,
        limits=limits or None,
        experiment_cost_cap_cny=Decimal(str(args.approval_cap)),
        experiment_kind=args.kind,
        name_prefix=f"v14-{args.phase}" if args.phase else "v14",
    )
    if args.e1_write_every:
        from agent_arena.lab.contracts import AgentArm

        control_every, treatment_every = args.e1_write_every
        for item in specs:
            if item["group"] != "E1-a":
                continue
            is_control = item["arm_id"].endswith("control")
            spec = item["spec"]
            arm = spec.agent_arms[0]
            config = {
                **arm.config,
                "route_log": True,
                "route_mode": "context_only",
                "route_write_every": control_every if is_control else treatment_every,
            }
            item["spec"] = spec.model_copy(
                update={
                    "agent_arms": [
                        AgentArm(
                            agent_id=arm.agent_id, config=config, label=arm.label
                        )
                    ]
                }
            )
            item["config_hash"] = item["spec"].agent_arms[0].config_hash
    if args.e3_control == "trigger_only":
        from agent_arena.lab.contracts import AgentArm

        for item in specs:
            if item["group"] != "E3" or not item["arm_id"].endswith("control"):
                continue
            spec = item["spec"]
            arm = spec.agent_arms[0]
            config = {**arm.config, "enabled": True, "trigger_only": True}
            item["spec"] = spec.model_copy(
                update={
                    "agent_arms": [
                        AgentArm(
                            agent_id=arm.agent_id, config=config, label=arm.label
                        )
                    ]
                }
            )
            item["config_hash"] = item["spec"].agent_arms[0].config_hash
    if args.groups:
        wanted = {item.strip() for item in args.groups}
        specs = [item for item in specs if item["group"] in wanted]
        if not specs:
            raise SystemExit(f"--groups 没有匹配任何组：{sorted(wanted)}")
    for item in specs:
        spec: ExperimentSpec = item["spec"]
        item["spec"] = spec.model_copy(
            update={"approval": approval, "preflight_only": not approval.approved}
        )
        item["runs"] = len(spec.maps) * len(seeds) * replicates
        item["seeds"] = seeds
        item["replicates"] = replicates
    return specs

def _print_matrix(specs: list[dict[str, Any]], args: argparse.Namespace) -> None:
    print("== V14 方案 A 矩阵 ==")
    total = 0
    for item in specs:
        spec = item["spec"]
        total += item["runs"]
        print(
            f"  {item['group']:<6} {item['arm_id']:<18} {spec.maps[0]:<7} "
            f"seed={item['seeds']} rep={item['replicates']} "
            f"runs={item['runs']:<3} cfg={item['config_hash'][:8]} "
            f"mode={spec.mode.value} approved={spec.approval.approved}"
        )
    costs = map_unit_costs(load_v12_history())
    estimate = 0.0
    upper = 0.0
    for item in specs:
        map_id = item["spec"].maps[0]
        unit = float(costs.get(map_id, {}).get("cost_cny") or 0.0)
        estimate += item["runs"] * unit * 1.5
        upper += item["runs"] * float(PER_RUN_LIMITS["per_run_cost_cap_cny"])
    print(
        f"  合计 {total} 局；预估 ¥{round(estimate, 2)}（V12 实测单价×1.5）；"
        f"上界 ¥{round(upper, 2)}；本次批准上限 ¥{args.approval_cap}"
    )
    for check in plan_a_single_factor_checks():
        flag = "单因子" if check["ok"] else "**非单因子**"
        print(f"  {check['group']}: {check['manipulated_variable']} → {flag}")

def _audit(service: ExperimentService, experiment_id: str) -> dict[str, Any]:
    summary = service.summary(experiment_id)
    records = service.records(experiment_id)
    settled = Decimal("0")
    unknown = 0
    requests = 0
    for record in records:
        requests += int(record.get("requests") or 0)
        if record.get("cost_known") and record.get("cost_cny") is not None:
            settled += Decimal(str(record["cost_cny"]))
        else:
            unknown += 1
    return {
        "experiment_id": experiment_id,
        "state": summary.get("state"),
        "executed": summary.get("executed"),
        "valid_denominator": summary.get("valid_denominator"),
        "successes": summary.get("successes"),
        "categories": summary.get("categories"),
        "requests": requests,
        "settled_cny": str(settled),
        "unknown_cost_runs": unknown,
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--pilot", action="store_true", help="seed 0 × 1 次重复（6 局）")
    parser.add_argument(
        "--groups",
        nargs="+",
        default=None,
        help="只跑这些消融组（默认全部）。E3 在 Pilot 零暴露后应被排除",
    )
    parser.add_argument("--approval-cap", default="5.00")
    parser.add_argument("--approved-by", default="user")
    parser.add_argument("--i-have-budget-approval", action="store_true")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--wait-timeout", type=float, default=0.0)
    parser.add_argument("--out", type=Path, default=LIVE_DIR)
    parser.add_argument(
        "--phase",
        default="",
        help="补充实验的阶段名（同时写入实验名与幂等键），例如 supplement-e2",
    )
    parser.add_argument(
        "--kind",
        default="ablation",
        choices=["ablation", "supplement", "replicate", "budget_extension", "matrix"],
        help="实验类别（预算扩展必须用 budget_extension，不能与 90 请求批配对）",
    )
    parser.add_argument("--request-cap", type=int, default=None)
    parser.add_argument("--decision-cap", type=int, default=None)
    parser.add_argument("--token-cap", type=int, default=None)
    parser.add_argument("--per-run-cost", default=None)
    parser.add_argument(
        "--e3-control",
        choices=["disabled", "trigger_only"],
        default="disabled",
        help="E3 的对照臂：disabled=完全不反思；trigger_only=只判定触发不请求（单因子问法）",
    )
    parser.add_argument(
        "--e1-write-every",
        nargs=2,
        type=int,
        default=None,
        metavar=("CONTROL", "TREATMENT"),
        help="E1 改为 route_write_every 的单因子对照（两臂都 route_log=True）",
    )
    parser.add_argument(
        "--map-override",
        nargs="+",
        default=None,
        help="覆盖某组的测试地图，例如 E3=MAP-19（候选图需先通过离线触发诊断）",
    )
    args = parser.parse_args()

    specs = _specs(args)
    _print_matrix(specs, args)

    results = []
    for item in specs:
        result = preflight(item["spec"])
        results.append({"arm_id": item["arm_id"], **result.as_dict()})
    ok = all(entry["ok"] for entry in results)
    print(json.dumps({"preflight_ok": ok, "preflights": results}, ensure_ascii=False, indent=1))
    if not ok:
        print("预检未通过：不会创建或提交实验。", file=sys.stderr)
        return 1
    if not args.submit:
        print("仅预检完成（零请求）。加 --submit 且带批准参数才会真正提交。")
        return 0
    if not args.i_have_budget_approval:
        print("拒绝提交：缺少 --i-have-budget-approval。", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    runs = RunService(args.out / "web", recover=False)
    service = ExperimentService(args.out / "lab", run_service=runs, recover=False)
    created: list[dict[str, Any]] = []
    stop_reason = ""
    try:
        for item in specs:
            spec = item["spec"]
            phase = args.phase or ("pilot" if args.pilot else "main")
            key = f"v14:{phase}:{item['arm_id']}:{spec.fingerprint()[:12]}"
            experiment_id = service.create_experiment(spec, idempotency_key=key)
            try:
                service.submit(experiment_id)
            except (LiveApprovalRequired, ExperimentBusy) as exc:
                stop_reason = f"提交被拒绝：{exc}"
                break
            while True:
                manifest = service.store.load_manifest(experiment_id)
                thread = service._threads.get(experiment_id)
                if manifest.terminal and not (thread is not None and thread.is_alive()):
                    break
                if args.wait_timeout and args.wait_timeout > 0:
                    if time.monotonic() > args.wait_timeout:
                        stop_reason = "等待超时"
                        break
                time.sleep(2.0)
            audit = _audit(service, experiment_id)
            created.append(audit)
            print(json.dumps(audit, ensure_ascii=False))
            if audit["unknown_cost_runs"]:
                stop_reason = "出现未知消费（unknown_spend）：按停止规则封账"
                break
    finally:
        state = {
            "mode": args.phase or ("pilot" if args.pilot else "main"),
            "kind": args.kind,
            "limits": {key: str(value) for key, value in _limits(args).items()},
            "model": args.model,
            "provider": args.provider,
            "approval_cap_cny": args.approval_cap,
            "approved_by": args.approved_by,
            "experiments": created,
            "stop_reason": stop_reason,
        }
        summary_name = (
            f"{args.phase}-summary.json"
            if args.phase
            else ("pilot-summary.json" if args.pilot else "main-summary.json")
        )
        (args.out / summary_name).write_text(
            json.dumps(state, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(
        json.dumps(
            {"stop_reason": stop_reason or "none", "experiments": len(created)},
            ensure_ascii=False,
        )
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())