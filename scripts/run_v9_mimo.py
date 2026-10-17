"""V9 有界 MiMo 验证执行器（预登记、可恢复、fail-closed）。

用法：
    python scripts/run_v9_mimo.py --dry-run
    python scripts/run_v9_mimo.py --manifest docs/v9/mimo-preregistration.json

硬性约束：
- 只读预登记 manifest；manifest hash 不匹配则拒绝执行；
- 独立账本 ``runs/v9/ledger.jsonl``，¥10 硬上限；
- 只对 provider_error（确认未计费）做一次新 run_id 重试；
- unknown spend / 连续 3 次 provider 错误 / 预算关闭 → 立即停止；
- 每局输出到 ``runs/v9/experiments/episodes/<run_id>/``。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.config import RuntimeSettings  # noqa: E402
from agent_arena.llm.openai import OpenAIDecisionProvider  # noqa: E402
from agent_arena.v8.metrics import metric_schema_hash  # noqa: E402
from agent_arena.v9.budget import V9BudgetClosed, V9BudgetLedger  # noqa: E402
from agent_arena.v9.prompts import prompt_hashes  # noqa: E402
from agent_arena.v9.runner import V9EpisodeSpec, V9Runner  # noqa: E402
from agent_arena.worlds.scenario_v8.catalog import (  # noqa: E402
    MAP_IDS,
    create_environment,
    rule_hash,
    scenario_hash,
    source_hash,
)

V9_ROOT = ROOT / "runs" / "v9"
EXPERIMENT_ROOT = V9_ROOT / "experiments"
LEDGER_PATH = V9_ROOT / "ledger.jsonl"
DEFAULT_MANIFEST = ROOT / "docs" / "v9" / "mimo-preregistration.json"
MODEL_NAME = "mimo-v2.6-flash"
ALLOWED_ENDPOINT = ("https", "api.xiaomimimo.com", "/v1")
FATAL_OUTCOMES = {"unknown_provider_spend", "provider_error_limit", "budget_closed"}
RETRYABLE = {"provider_error"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def manifest_hash(manifest: dict[str, Any]) -> str:
    payload = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    return sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def settings_for_run() -> RuntimeSettings:
    configured = RuntimeSettings.load(env_file=ROOT / ".env")
    if configured.provider != "openai" or configured.model_name != MODEL_NAME:
        raise SystemExit(
            f"本地 provider/model 与 V9 预登记不一致：{configured.provider}/{configured.model_name}"
        )
    if not configured.openai_api_key or not configured.base_url:
        raise SystemExit("缺少 MiMo API 凭据或 endpoint。")
    endpoint = urlparse(configured.base_url)
    if (
        endpoint.scheme,
        endpoint.netloc,
        endpoint.path,
    ) != ALLOWED_ENDPOINT:
        raise SystemExit(f"endpoint 与预登记不一致：{configured.base_url}")
    return RuntimeSettings.load(
        {
            "provider": "openai",
            "world": "scenario_v8",
            "world_version": "V9",
            "agent": "react",
            "seed": 0,
            "runs_dir": V9_ROOT,
            "results_dir": ROOT / "results" / "v9",
            "step_limit": 160,
            "request_timeout_seconds": 45,
            "retry_count": 0,
            "retry_backoff_seconds": [],
            "enable_thinking": False,
            "reasoning_effort": "none",
            "response_format": "json_object",
            "model_name": MODEL_NAME,
        },
        env_file=ROOT / ".env",
    )


def ledger_source_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for map_id in MAP_IDS:
        environment = create_environment(map_id)
        hashes[map_id] = "|".join(
            [
                scenario_hash(map_id),
                rule_hash(map_id),
                source_hash(map_id),
                metric_schema_hash(map_id),
                *prompt_hashes(environment, decision_budget=_budget(map_id)).values(),
            ]
        )
    return hashes


def _budget(map_id: str) -> int:
    index = int(map_id.split("-")[1])
    level = ("简单", "中等", "困难")[(index - 1) % 3]
    if map_id == "MAP-12":
        return 60
    return {"简单": 30, "中等": 38, "困难": 46}[level]


def verify_manifest(manifest: dict[str, Any]) -> None:
    expected = manifest_hash(manifest)
    if manifest.get("manifest_hash") != expected:
        raise SystemExit("manifest hash 不匹配；拒绝执行。")
    if manifest.get("model") != MODEL_NAME:
        raise SystemExit("manifest 模型与 V9 预登记不一致。")
    if float(manifest.get("budget_cny", 99)) > 10:
        raise SystemExit("manifest 预算超过 ¥10 硬上限。")
    episodes = manifest.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise SystemExit("manifest 没有 episode 列表。")
    for index, episode in enumerate(episodes):
        if episode.get("map_id") not in MAP_IDS:
            raise SystemExit(f"episode {index} 的 map_id 非法。")
        if episode.get("arm") not in {"v8_compat", "v9_fixed"}:
            raise SystemExit(f"episode {index} 的 arm 非法。")
        if not 1 <= int(episode.get("decision_budget", 0)) <= 60:
            raise SystemExit(f"episode {index} 的 decision_budget 非法。")


def verify_runtime_hashes(manifest: dict[str, Any]) -> None:
    registered = manifest.get("runtime_hashes") or {}
    drift: list[str] = []
    for map_id, expected in registered.items():
        environment = create_environment(map_id)
        current = {
            "scenario_hash": scenario_hash(map_id),
            "rule_hash": rule_hash(map_id),
            "source_hash": source_hash(map_id),
            "metric_schema_hash": metric_schema_hash(map_id),
            **prompt_hashes(
                environment,
                decision_budget=int(manifest["decision_budgets"].get(map_id, 30)),
            ),
        }
        for key, value in expected.items():
            if current.get(key) != value:
                drift.append(f"{map_id}.{key}")
    if drift:
        raise SystemExit(f"运行时 hash 与 manifest 不一致：{drift}")


def dry_run(manifest: dict[str, Any]) -> dict[str, Any]:
    episodes = manifest["episodes"]
    budgets = [int(item["decision_budget"]) for item in episodes]
    estimate = sum(min(budget, 46) for budget in budgets) * 0.00065 + len(episodes) * 0.0006
    return {
        "episodes": len(episodes),
        "decisions_upper_bound": sum(budgets),
        "estimated_cost_cny_upper_bound": round(estimate, 4),
        "hard_cap_cny": manifest["budget_cny"],
        "maps": sorted({item["map_id"] for item in episodes}),
        "arms": sorted({item["arm"] for item in episodes}),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    args = parser.parse_args()

    manifest = read_json(args.manifest)
    verify_manifest(manifest)
    if args.dry_run:
        print(json.dumps(dry_run(manifest), ensure_ascii=False, indent=2))
        return 0
    verify_runtime_hashes(manifest)
    settings = settings_for_run()

    ledger = V9BudgetLedger(
        args.ledger,
        currency="CNY",
        model=MODEL_NAME,
        source_hashes=ledger_source_hashes(),
        resume=args.ledger.exists(),
    )
    ledger.record(
        "v9_preregistration_loaded",
        manifest_path=str(args.manifest),
        manifest_hash=manifest["manifest_hash"],
        experiment_label=manifest.get("experiment_label"),
    )
    provider = OpenAIDecisionProvider(settings)
    results: list[dict[str, Any]] = []
    queue: list[dict[str, Any]] = [dict(item) for item in manifest["episodes"]]
    retries_used: dict[str, int] = {}
    while queue:
        episode = queue.pop(0)
        spec = V9EpisodeSpec(
            map_id=str(episode["map_id"]),
            replicate_id=int(episode.get("replicate_id", 0)),
            decision_budget=int(episode["decision_budget"]),
            arm=str(episode["arm"]),
            hypothesis=str(episode.get("hypothesis", "")),
            seed=int(episode.get("seed", 0)),
        )
        key = f"{spec.map_id}-R{spec.replicate_id}-{spec.arm}"
        print(
            f"[{len(results) + 1}] {spec.map_id} R{spec.replicate_id} "
            f"arm={spec.arm} budget={spec.decision_budget}",
            flush=True,
        )
        runner = V9Runner(
            provider=provider,
            settings=settings,
            ledger=ledger,
            output_dir=EXPERIMENT_ROOT,
            commit=manifest.get("commit", ""),
            progress=lambda row: print(json.dumps(row, ensure_ascii=False), flush=True),
        )
        try:
            result = runner.run(spec)
        except V9BudgetClosed as exc:
            print(f"STOP: {exc}", flush=True)
            ledger.close("RUNTIME_BUDGET_CLOSED", reason=str(exc))
            return 2
        results.append(
            {
                "map_id": spec.map_id,
                "replicate_id": spec.replicate_id,
                "arm": spec.arm,
                "status": result["status"],
                "success": result["success"],
                "termination_reason": result["termination_reason"],
                "decision_count": result["decision_count"],
                "run_id": result["run_id"],
                "cost": result["usage"]["cost"],
            }
        )
        write_json(V9_ROOT / "mimo_results.json", {"results": results, "partial": True})
        if result["status"] in FATAL_OUTCOMES:
            ledger.close("FATAL_PROVIDER_OUTCOME", map_id=spec.map_id)
            break
        if result["status"] in RETRYABLE and retries_used.get(key, 0) < 1:
            retries_used[key] = retries_used.get(key, 0) + 1
            print(f"pre-registered provider retry: {key}", flush=True)
            queue.insert(0, episode)
            continue
    summary = {
        "manifest": str(args.manifest),
        "manifest_hash": manifest["manifest_hash"],
        "finished_at": utc_now(),
        "results": results,
        "ledger": ledger.snapshot(),
    }
    write_json(V9_ROOT / "mimo_results.json", summary)
    print(json.dumps(summary["ledger"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
