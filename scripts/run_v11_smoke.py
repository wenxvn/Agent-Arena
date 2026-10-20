"""V11 真实 MiMo 冒烟（默认 2 局，最多 3 局，独立 ¥3 总预算）。

规则：
- 只接受模型名包含 ``mimo`` 的 OpenAI-compatible 配置（有登记价，金额门禁可执行）；
- 使用 ``runs/v11/web`` 独立运行目录与全局账本，不动 V10 账本；
- 每局单独 run_id，不自动重试；未知消费或 provider 错误立即停止；
- 正式执行必须显式 ``--yes``。

用法：
    uv run python scripts/run_v11_smoke.py --dry-run
    uv run python scripts/run_v11_smoke.py --yes --episodes 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.config import RuntimeSettings  # noqa: E402
from agent_arena.v10.baselines.suite import decision_budget  # noqa: E402
from agent_arena.web.schemas import RunConfig, RunMode  # noqa: E402
from agent_arena.web.service import TOTAL_BUDGET_ENV, RunService  # noqa: E402

DEFAULT_PLAN: tuple[tuple[str, int], ...] = (("MAP-01", 0), ("MAP-19", 0), ("MAP-30", 0))


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal(0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=2, choices=[1, 2, 3])
    parser.add_argument("--maps", nargs="*", default=[])
    parser.add_argument("--model", default="")
    parser.add_argument("--max-cost-per-run", default="0.90")
    parser.add_argument("--total-cap", default="3.00")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = RuntimeSettings.load()
    model = args.model or settings.model_name
    if "mimo" not in model.lower():
        print(
            json.dumps(
                {
                    "ok": False,
                    "detail": "冒烟只允许 MiMo 模型（有登记价，金额门禁可执行）。",
                    "model": model,
                },
                ensure_ascii=False,
            )
        )
        return 2
    if not settings.openai_api_key or not settings.base_url:
        print(json.dumps({"ok": False, "detail": "缺少 OPENAI_API_KEY / OPENAI_BASE_URL。"}))
        return 2

    plan = list(DEFAULT_PLAN)
    if args.maps:
        selected = set(args.maps)
        plan = [item for item in plan if item[0] in selected]
    plan = plan[: args.episodes]
    per_run = Decimal(args.max_cost_per_run)
    total_cap = Decimal(args.total_cap)
    session = _stamp()
    planned = [
        {
            "map_id": map_id,
            "environment_seed": seed,
            "decision_budget": decision_budget(map_id),
            "max_cost_cny": str(per_run),
        }
        for map_id, seed in plan
    ]
    print(
        json.dumps(
            {
                "ok": True,
                "dry_run": args.dry_run,
                "model": model,
                "base_url_host": urlparse(settings.base_url or "").hostname or "",
                "total_cap": str(total_cap),
                "planned": planned,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    if args.dry_run:
        return 0
    if not args.yes:
        print(json.dumps({"ok": False, "detail": "正式执行需要 --yes。"}))
        return 2

    os.environ[TOTAL_BUDGET_ENV] = str(total_cap)
    base = ROOT / "runs" / "v11" / "web"
    service = RunService(base, recover=True)
    rows: list[dict[str, Any]] = []
    unknown = False
    try:
        for index, (map_id, seed) in enumerate(plan, start=1):
            spend = service.diagnostics()["total_spend"]
            settled, pending, unknown_spend = (Decimal(item) for item in spend)
            projected = settled + pending + unknown_spend
            if projected >= total_cap:
                print(json.dumps({"stop": "total_cap_reached", "projected": str(projected)}))
                break
            config = RunConfig(
                map_id=map_id,
                environment_seed=seed,
                mode=RunMode.LIVE,
                provider_id="openai_compatible",
                model=model,
                agent="v10_action_loop",
                max_decisions=decision_budget(map_id),
                max_requests=decision_budget(map_id) + 5,
                max_input_tokens=1_000_000,
                max_output_tokens=60_000,
                max_cost_cny=per_run,
            )
            run_id = service.create_run(
                config, idempotency_key=f"v11-smoke-{session}-{map_id}-S{seed}"
            )
            status = service.wait(run_id, timeout=3_600)
            replay = service.load_replay(run_id)
            result = replay["result"] or {}
            usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
            row = {
                "run_id": run_id,
                "map_id": map_id,
                "environment_seed": seed,
                "state": status.state.value,
                "outcome": status.outcome,
                "termination": status.termination,
                "success": bool(result.get("success")),
                "decisions": status.decisions,
                "requests": usage.get("requests"),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "cost_settled_cny": usage.get("cost_settled_cny"),
                "cost_unknown": usage.get("cost_unknown"),
                "primary_metric": result.get("primary_metric"),
                "primary_metric_state": result.get("primary_metric_state"),
                "primary_metric_value": result.get("primary_metric_value"),
                "message": result.get("message"),
            }
            rows.append(row)
            print(json.dumps({"episode": index, **row}, ensure_ascii=False), flush=True)
            if row["cost_unknown"]:
                unknown = True
                print(json.dumps({"stop": "unknown_provider_spend", "run_id": run_id}))
                break
            if row["state"] == "PROVIDER_ERROR":
                print(json.dumps({"stop": "provider_error", "run_id": run_id}))
                break
    finally:
        service.shutdown()

    settled_total = sum((_money(row["cost_settled_cny"]) for row in rows), Decimal(0))
    payload = {
        "schema": "v11-smoke-1",
        "session": session,
        "model": model,
        "total_cap_cny": str(total_cap),
        "episodes": len(rows),
        "successes": sum(1 for row in rows if row["success"]),
        "settled_cny": str(settled_total),
        "unknown_spend": unknown,
        "rows": rows,
    }
    output = ROOT / "runs" / "v11" / "smoke-summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(output), **payload}, ensure_ascii=False, indent=1))
    return 0 if not unknown else 1


if __name__ == "__main__":
    raise SystemExit(main())
