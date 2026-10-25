"""V12 矩阵 CLI：预检、提交与结果查看（与网页走同一服务层）。

用法：

    # 只预检（零请求）
    uv run python scripts/run_v12_matrix.py --maps MAP-22 MAP-26 \
        --agents basic.v1 memory.v1 planning.v1

    # 提交离线模拟矩阵并等待完成
    uv run python scripts/run_v12_matrix.py --submit --seeds 0

    # 从 JSON 规格文件提交（字段见 docs/v12/experiment-protocol.md）
    uv run python scripts/run_v12_matrix.py --spec my-spec.json --submit

真实付费实验必须显式加 ``--i-have-budget-approval`` 并设置 ``--approval-cap``；
默认 ``preflight_only=True``，不会发出任何请求。
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
    AgentArm,
    ComparisonPolicy,
    ExperimentBudget,
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
from agent_arena.lab.paths import LAB_RUNS, WEB_RUNS  # noqa: E402
from agent_arena.web.schemas import (  # noqa: E402
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
)
from agent_arena.web.service import RunService  # noqa: E402


def _spec_from_args(args: argparse.Namespace) -> ExperimentSpec:
    if args.spec:
        payload = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        return ExperimentSpec.model_validate(payload)
    simulated = args.provider == SIMULATED_PROVIDER
    approved = bool(args.i_have_budget_approval)
    return ExperimentSpec(
        name=args.name,
        notes=args.notes,
        maps=args.maps,
        agent_arms=[AgentArm(agent_id=agent) for agent in args.agents],
        environment_seeds=args.seeds,
        provider_id=args.provider,
        model=SIMULATED_MODEL if simulated else args.model,
        mode=ExperimentMode.SIMULATED if simulated else ExperimentMode.LIVE,
        budget=ExperimentBudget(
            per_run_request_cap=args.requests,
            per_run_decision_cap=args.decisions,
            per_run_cost_cap_cny=Decimal(str(args.per_run_cost)),
            experiment_request_cap=args.experiment_requests,
            experiment_cost_cap_cny=Decimal(str(args.experiment_cost)),
        ),
        comparison=ComparisonPolicy(),
        preflight_only=not simulated and not approved,
        approval=LiveApproval(
            approved=approved,
            approved_by="cli" if approved else "",
            max_cost_cny=Decimal(str(args.approval_cap)) if approved else None,
            note="由 CLI 显式确认" if approved else "",
        ),
    )


def _wait(service: ExperimentService, experiment_id: str, timeout: float) -> Any:
    """等待父实验进入终态；``timeout<=0`` 表示不设上限。

    为什么默认不设上限：父实验的执行线程是进程内的 daemon 线程。CLI 一旦退出，
    线程随之被杀，父实验会停在 RUNNING 且留下一个孤儿 QUEUED 子局。宁可等，
    也不要让调用方"以为跑完了"。
    """

    if timeout and timeout > 0:
        return service.wait(experiment_id, timeout=timeout)
    interval = 2.0
    while True:
        manifest = service.store.load_manifest(experiment_id)
        thread = service._threads.get(experiment_id)
        if manifest.terminal and not (thread is not None and thread.is_alive()):
            return manifest
        time.sleep(interval)


def _resume(args: argparse.Namespace) -> int:
    """续跑已有实验：只排尚未执行的子局；已结束/未知消费的子局不自动重跑。"""

    runs = RunService(WEB_RUNS, recover=False)
    service = ExperimentService(LAB_RUNS, run_service=runs, recover=False)
    try:
        before = service.status(args.resume)
        print(
            json.dumps(
                {
                    "experiment_id": args.resume,
                    "state_before": before.state.value,
                    "counts_before": before.counts,
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        if not args.submit:
            print("仅查看状态；加 --submit 才会续跑。")
            return 0
        service.submit(args.resume, resume=True)
        manifest = _wait(service, args.resume, args.timeout)
        summary = service.summary(args.resume)
        print(
            json.dumps(
                {
                    "experiment_id": args.resume,
                    "state": manifest.state.value,
                    "counts": manifest.counts,
                    "budget": manifest.budget,
                    "executed": summary["executed"],
                    "valid_denominator": summary["valid_denominator"],
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        return 0 if manifest.state.value in {"COMPLETED", "PARTIAL"} else 1
    finally:
        runs.shutdown()


def _supplement(args: argparse.Namespace) -> int:
    """补充实验：列出候选 / 新建并提交（原始实验不动）。"""

    runs = RunService(WEB_RUNS, recover=False)
    service = ExperimentService(LAB_RUNS, run_service=runs, recover=False)
    try:
        plan = service.supplement_candidates(args.supplement_of)
        print(json.dumps(plan, ensure_ascii=False, indent=1))
        if args.list_candidates or not args.submit:
            if plan["count"] == 0:
                print("没有需要补充的子局。")
            else:
                print(f"候选 {plan['count']} 局；加 --submit 才会创建并提交补充实验。")
            return 0
        experiment_id = service.create_supplement(
            args.supplement_of,
            reason=args.notes,
            conditions=args.conditions,
        )
        service.submit(experiment_id)
        manifest = _wait(service, experiment_id, args.timeout)
        summary = service.summary(experiment_id)
        print(
            json.dumps(
                {
                    "supplement_experiment_id": experiment_id,
                    "source_experiment_id": args.supplement_of,
                    "state": manifest.state.value,
                    "counts": manifest.counts,
                    "budget": manifest.budget,
                    "executed": summary["executed"],
                    "valid_denominator": summary["valid_denominator"],
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        return 0 if manifest.state.value in {"COMPLETED", "PARTIAL"} else 1
    finally:
        runs.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=None)
    parser.add_argument("--name", default="cli-matrix")
    parser.add_argument("--notes", default="")
    parser.add_argument("--maps", nargs="+", default=["MAP-22", "MAP-26"])
    parser.add_argument(
        "--agents", nargs="+", default=["basic.v1", "memory.v1", "planning.v1"]
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=[0])
    parser.add_argument("--provider", default=SIMULATED_PROVIDER)
    parser.add_argument("--model", default="mimo-v2.6-flash")
    parser.add_argument("--decisions", type=int, default=20)
    parser.add_argument("--requests", type=int, default=60)
    parser.add_argument("--per-run-cost", type=float, default=1.0)
    parser.add_argument("--experiment-requests", type=int, default=2_000)
    parser.add_argument("--experiment-cost", type=float, default=10.0)
    parser.add_argument("--approval-cap", type=float, default=5.0)
    parser.add_argument("--i-have-budget-approval", action="store_true")
    parser.add_argument(
        "--resume",
        default=None,
        help="续跑已有实验（只排尚未执行的子局；已结束/未知消费子局不自动重跑）",
    )
    parser.add_argument(
        "--supplement-of",
        default=None,
        help="从该实验新建补充实验（只重跑中断/Provider 错误/未知消费/取消/未执行子局）",
    )
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=None,
        help="补充实验只跑这些 condition_key（默认全部候选）",
    )
    parser.add_argument(
        "--list-candidates",
        action="store_true",
        help="只列出需要补充的子局，不创建实验",
    )
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--idempotency-key", default=None)
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.0,
        help="等待秒数；0 表示一直等到父实验进入终态（推荐用于长矩阵）",
    )
    args = parser.parse_args()

    if args.resume:
        return _resume(args)
    if args.supplement_of or args.list_candidates:
        if not args.supplement_of:
            parser.error("--list-candidates 需要同时给出 --supplement-of")
        return _supplement(args)

    spec = _spec_from_args(args)
    result = preflight(spec)
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=1))
    if not result.ok:
        print("预检未通过：不会创建或提交实验。", file=sys.stderr)
        return 1
    if not args.submit:
        print("仅预检完成（未创建实验）。加 --submit 才会入队。")
        return 0

    runs = RunService(WEB_RUNS, recover=False)
    service = ExperimentService(LAB_RUNS, run_service=runs, recover=False)
    try:
        key = args.idempotency_key or f"cli:{spec.fingerprint()[:12]}"
        experiment_id = service.create_experiment(spec, idempotency_key=key)
        try:
            service.submit(experiment_id)
        except LiveApprovalRequired as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except ExperimentBusy as exc:
            print(str(exc), file=sys.stderr)
            return 2
        manifest = _wait(service, experiment_id, args.timeout)
        summary = service.summary(experiment_id)
        comparison = service.comparison(experiment_id)
        print(
            json.dumps(
                {
                    "experiment_id": experiment_id,
                    "state": manifest.state.value,
                    "counts": manifest.counts,
                    "budget": manifest.budget,
                    "verdict": comparison["verdict"],
                    "reasons": comparison["reasons"],
                    "executed": summary["executed"],
                    "valid_denominator": summary["valid_denominator"],
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        return 0 if manifest.state.value in {"COMPLETED", "PARTIAL"} else 1
    finally:
        runs.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
