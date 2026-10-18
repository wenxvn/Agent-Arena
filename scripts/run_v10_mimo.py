"""V10 有界 MiMo 复测（Batch 8）。

- 账本：``runs/v10/mimo/ledger.jsonl``，全局 CNY 10 硬上限（复用 V9 的 append-only 账本）；
- 矩阵：P0 五图 × 3 seed（15）+ 古堡三图 × 3 seed（9）+ 接口七图 × 3 seed（21）= 45 局；
- 每局保存 trace（agent-visible 部分）与 judge（含密封真值）到 ``runs/v10/mimo/episodes``；
- 失败/中断保留；`UNKNOWN_PROVIDER_SPEND` 或连续 5xx 立即封账停止。

用法：
    python scripts/run_v10_mimo.py --dry-run
    python scripts/run_v10_mimo.py --limit 2      # 先小批
    python scripts/run_v10_mimo.py                # 全矩阵
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.config import RuntimeSettings  # noqa: E402
from agent_arena.llm.bailian import DecisionProviderError  # noqa: E402
from agent_arena.llm.protocol import DecisionRequest  # noqa: E402
from agent_arena.llm.openai import OpenAIDecisionProvider  # noqa: E402
from agent_arena.v10.baselines.suite import decision_budget  # noqa: E402
from agent_arena.v10.metrics.governance import schema_hash  # noqa: E402
from agent_arena.v10.runtime.catalog import (  # noqa: E402
    LEVEL_OF,
    WORLD_OF,
    create_environment,
    metric_hash,
    rule_hash,
    scenario_hash,
)
from agent_arena.v9.budget import V9BudgetClosed, V9BudgetLedger  # noqa: E402
from agent_arena.worlds.scenario_v8.models import V8Action, V8Observation  # noqa: E402

MIMO_ROOT = ROOT / "runs" / "v10" / "mimo"
LEDGER_PATH = MIMO_ROOT / "ledger.jsonl"
EPISODE_ROOT = MIMO_ROOT / "episodes"
PREREG = ROOT / "docs" / "v10" / "mimo-preregistration.json"
MODEL_NAME = "mimo-v2.6-flash"
CAP_CNY = Decimal("10")
MAX_CONSECUTIVE = 3

P0 = ("MAP-03", "MAP-06", "MAP-15", "MAP-18", "MAP-21")
CASTLE = ("MAP-28", "MAP-29", "MAP-30")
INTERFACE = ("MAP-07", "MAP-08", "MAP-09", "MAP-10", "MAP-11", "MAP-12", "MAP-26")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _contract(environment: Any) -> str:
    lines = ["可用动作（严格 JSON，字段必须与下列集合完全一致）："]
    for tool, shapes in sorted(environment.SHAPES.items()):
        variants = ["{" + ",".join(sorted(shape)) + "}" for shape in sorted(shapes, key=sorted)]
        lines.append(f"- {tool}: " + " | ".join(variants))
    lines.append("只输出一个 JSON 对象；不要输出解释。")
    return "\n".join(lines)


def _system_prompt(map_id: str, environment: Any) -> str:
    rules = "\n".join(f"- {item}" for item in environment.public_rules())
    return (
        f"你在玩一个确定性回合制解密关卡（{map_id}）。每回合必须从允许动作里选一个。\n"
        "输出必须是一个 JSON 对象：字段 tool 加上该 tool 允许的字段；"
        "禁止输出 command/target/args 等旧格式。示例：tool=move 且 to=B。\n"
        f"公开规则：\n{rules}\n\n{_contract(environment)}"
    )


def _episodes() -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for group, maps in (("p0", P0), ("castle", CASTLE), ("interface", INTERFACE)):
        for map_id in maps:
            for seed in (0, 1, 2):
                plan.append(
                    {
                        "run_id": f"V10-{map_id}-S{seed}-{group}",
                        "map_id": map_id,
                        "world": WORLD_OF[map_id],
                        "difficulty": LEVEL_OF[map_id],
                        "environment_seed": seed,
                        "replicate": 0,
                        "group": group,
                        "decision_budget": decision_budget(map_id),
                    }
                )
    return plan


def _manifest_hash(episodes: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        {"episodes": episodes, "model": MODEL_NAME, "cap": str(CAP_CNY), "schema": schema_hash()},
        ensure_ascii=False,
        sort_keys=True,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _settings() -> RuntimeSettings:
    settings = RuntimeSettings(response_format="json_object")
    if not settings.openai_api_key:
        raise SystemExit("缺少 OPENAI_API_KEY")
    return settings


def run_episode(
    episode: dict[str, Any],
    *,
    provider: OpenAIDecisionProvider,
    ledger: V9BudgetLedger,
) -> dict[str, Any]:
    map_id = str(episode["map_id"])
    seed = int(episode["environment_seed"])
    budget = int(episode["decision_budget"])
    environment = create_environment(map_id, environment_seed=seed)
    system = _system_prompt(map_id, environment)
    run_id = str(episode["run_id"])
    ledger.start_episode(run_id, map_id=map_id, seed=seed, condition_id="v10")
    observation = environment.observe()
    history: list[dict[str, Any]] = []
    decisions = invalid = rejected = 0
    outcome = "decision_budget_exhausted"
    cost = Decimal("0")
    tokens_in = tokens_out = 0
    while not environment.is_terminal and decisions < budget:
        request_hash = sha256(
            json.dumps(
                {"run": run_id, "index": decisions, "obs": observation, "history": history[-5:]},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        try:
            request_id = ledger.reserve_request(
                run_id, decision_index=decisions, request_hash=request_hash
            )
        except V9BudgetClosed:
            outcome = "budget_closed"
            break
        request = DecisionRequest(
            observation=V8Observation(**observation),
            system_prompt=system,
            correction=invalid > 0,
            invalid_output_reason="schema" if invalid else None,
            recent_history=(
                json.dumps(history[-5:], ensure_ascii=False, sort_keys=True) if history else None
            ),
            runtime_feedback=None,
            max_output_tokens=700,
            action_contract_version="scenario_v4",
        )
        started = time.monotonic()
        try:
            response = provider.decide(request)
        except DecisionProviderError as exc:
            latency = max(0, round((time.monotonic() - started) * 1000))
            ledger.fail_request(
                request_id,
                error_category=exc.error_category[:80],
                latency_ms=latency,
                retryable=exc.retryable,
                unknown_spend=exc.unknown_spend,
            )
            if exc.unknown_spend:
                ledger.close("UNKNOWN_PROVIDER_SPEND", run_id=run_id)
                outcome = "unknown_provider_spend"
                break
            if ledger.consecutive_provider_errors() >= MAX_CONSECUTIVE:
                ledger.close("THREE_CONSECUTIVE_PROVIDER_ERRORS", run_id=run_id)
                outcome = "provider_error_limit"
                break
            outcome = "provider_error"
            break
        except Exception as exc:  # noqa: BLE001 - unconfirmed transport outcome
            latency = max(0, round((time.monotonic() - started) * 1000))
            ledger.fail_request(
                request_id,
                error_category=type(exc).__name__[:80],
                latency_ms=latency,
                retryable=False,
                unknown_spend=True,
            )
            ledger.close("UNKNOWN_PROVIDER_SPEND", run_id=run_id)
            outcome = "unknown_provider_spend"
            break
        latency = max(0, round((time.monotonic() - started) * 1000))
        try:
            ledger.settle_request(
                request_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_input_tokens=response.cached_input_tokens,
                latency_ms=latency,
                decision_payload={"candidate": response.candidate},
            )
        except V9BudgetClosed as exc:
            outcome = f"settle_closed:{exc}"
            break
        tokens_in += int(response.input_tokens or 0)
        tokens_out += int(response.output_tokens or 0)
        cost = ledger.projected_cost()
        candidate = response.candidate
        try:
            action = V8Action.model_validate(candidate, strict=True)
        except Exception:  # noqa: BLE001 - invalid model output is a legal outcome
            action = None
        if action is None or not environment.accepts(action):
            result = environment.reject_invalid_action()
            invalid += 1
            entry = {"invalid_output": candidate}
        else:
            result = environment.step(action)
            if str(result.result).startswith(("INVALID", "NO_", "NOT_", "UNKNOWN", "ALREADY")):
                rejected += 1
            entry = action.model_dump(mode="json", exclude_none=True)
        observation = environment.observe()
        history.append({"action": entry, "result": result.result, "observation_after": observation})
        decisions += 1
    metrics = environment.metrics()
    judge = environment.judge_state()
    return {
        "run_id": run_id,
        "map_id": map_id,
        "world": WORLD_OF[map_id],
        "difficulty": LEVEL_OF[map_id],
        "environment_seed": seed,
        "replicate": episode["replicate"],
        "model_id": MODEL_NAME,
        "temperature": 0.2,
        "scenario_hash": scenario_hash(map_id, seed),
        "rule_hash": rule_hash(map_id),
        "metric_schema_hash": schema_hash(),
        "metric_hash": metric_hash(map_id),
        "code_commit": _head(),
        "termination": environment.terminal_reason or outcome,
        "success": environment.is_success,
        "decision_count": decisions,
        "invalid_actions": invalid,
        "rejected_actions": rejected,
        "mechanism_triggered": environment.mechanism_triggered(),
        "primary_metric": environment.PRIMARY_METRIC,
        "primary_metric_state": metrics.get(environment.PRIMARY_METRIC, {}).get("state"),
        "primary_metric_value": metrics.get(environment.PRIMARY_METRIC, {}).get("value"),
        "token_input": tokens_in,
        "token_output": tokens_out,
        "cost_settled": float(cost) if cost else 0.0,
        "outcome": outcome,
        "metrics": metrics,
        "judge": judge,
        "history": history,
    }


def _head() -> str:
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    args = parser.parse_args()
    episodes = _episodes()
    if args.limit:
        episodes = episodes[: args.limit]
    manifest = {
        "schema": "v10-mimo-manifest-1",
        "created_at": utc_now(),
        "model": MODEL_NAME,
        "cap_cny": str(CAP_CNY),
        "schema_hash": schema_hash(),
        "manifest_hash": _manifest_hash(episodes),
        "episodes": episodes,
    }
    (MIMO_ROOT).mkdir(parents=True, exist_ok=True)
    (MIMO_ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    if args.dry_run:
        print(
            json.dumps(
                {
                    "episodes": len(episodes),
                    "maps": sorted({item["map_id"] for item in episodes}),
                    "manifest_hash": manifest["manifest_hash"][:16],
                    "estimated_upper_cny": round(
                        sum(min(item["decision_budget"], 46) for item in episodes) * 0.00065
                        + len(episodes) * 0.0006,
                        4,
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    settings = _settings()
    ledger = V9BudgetLedger(
        args.ledger,
        currency="CNY",
        model=MODEL_NAME,
        source_hashes={"manifest": manifest["manifest_hash"], "schema": schema_hash()},
        resume=args.ledger.exists(),
        max_cost=CAP_CNY,
    )
    ledger.record("v10_manifest_loaded", manifest_hash=manifest["manifest_hash"])
    provider = OpenAIDecisionProvider(settings)
    results: list[dict[str, Any]] = []
    EPISODE_ROOT.mkdir(parents=True, exist_ok=True)
    for index, episode in enumerate(episodes, start=1):
        print(f"[{index}/{len(episodes)}] {episode['run_id']}", flush=True)
        try:
            result = run_episode(episode, provider=provider, ledger=ledger)
        except V9BudgetClosed as exc:
            ledger.close("RUNTIME_BUDGET_CLOSED", reason=str(exc))
            print(f"STOP: {exc}", flush=True)
            break
        path = EPISODE_ROOT / f"{result['run_id']}.json"
        path.write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        results.append(result)
        print(
            json.dumps(
                {
                    "run_id": result["run_id"],
                    "success": result["success"],
                    "termination": result["termination"],
                    "decisions": result["decision_count"],
                    "primary": result["primary_metric_value"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        (MIMO_ROOT / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
            encoding="utf-8",
        )
        if result["outcome"] in {"unknown_provider_spend", "provider_error_limit"}:
            print("STOP: provider anomaly", flush=True)
            break
    settled = ledger.projected_cost()
    print(json.dumps({"episodes": len(results), "projected_cny": str(settled)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
