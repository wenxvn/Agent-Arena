"""V8 正式 90 局 MiMo 运行器（可恢复、按世界 checkpoint、fail-closed）。

前置条件：
1. `runs/v8/offline_gate.json` 为 30/30 通过；
2. `runs/v8/freeze_manifest.json` 存在，且 30 图 hash 与当前运行时一致；
3. `.env` 指向预登记的 Xiaomi MiMo endpoint 与 `mimo-v2.6-flash`。

账本：`runs/v8/ledger.jsonl`（append-only，¥10 硬上限）。
结果：`runs/v8/experiments/episodes/<run_id>/`，每局不可覆盖。
补跑：仅 `provider_error`（传输类且确认未计费）允许一次新 run_id 补跑；
模型正常失败不补跑；unknown spend 立即封账停机。
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
from agent_arena.v8.budget import V8BudgetClosed, V8BudgetLedger  # noqa: E402
from agent_arena.v8.metrics import metric_schema_hash  # noqa: E402
from agent_arena.v8.prompts import system_prompt  # noqa: E402
from agent_arena.v8.runner import (  # noqa: E402
    V8EpisodeSpec,
    V8Runner,
    registered_specs,
)
from agent_arena.worlds.scenario_v8 import create_environment  # noqa: E402
from agent_arena.worlds.scenario_v8.catalog import (  # noqa: E402
    MAP_IDS,
    WORLD_OF,
    rule_hash,
    scenario_hash,
)

V8_ROOT = ROOT / "runs" / "v8"
EXPERIMENT_ROOT = V8_ROOT / "experiments"
EPISODE_ROOT = EXPERIMENT_ROOT / "episodes"
LEDGER_PATH = V8_ROOT / "ledger.jsonl"
FREEZE_PATH = V8_ROOT / "freeze_manifest.json"
GATE_PATH = V8_ROOT / "offline_gate.json"
RUN_MANIFEST_PATH = EXPERIMENT_ROOT / "run_manifest.json"
CHECKPOINT_DIR = EXPERIMENT_ROOT / "checkpoints"
MODEL_NAME = "mimo-v2.6-flash"
ALLOWED_ENDPOINT = ("https", "api.xiaomimimo.com", "/v1")
MAX_SUPPLEMENTS = 15
NON_RETRYABLE_OUTCOMES = {
    "success",
    "failure",
    "censored",
    "decision_budget_reached",
    "episode_timeout",
    "schema_fault_limit",
}
FATAL_OUTCOMES = {
    "unknown_provider_spend",
    "provider_error_limit",
    "budget_closed",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def settings_for_run() -> RuntimeSettings:
    configured = RuntimeSettings.load(env_file=ROOT / ".env")
    if configured.provider != "openai" or configured.model_name != MODEL_NAME:
        raise SystemExit("本地 provider/model 与 V8 预登记不一致。")
    settings = RuntimeSettings.load(
        {
            "provider": "openai",
            "world": "scenario_v8",
            "world_version": "V8",
            "agent": "react",
            "seed": 0,
            "runs_dir": V8_ROOT,
            "results_dir": ROOT / "results" / "v8",
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
    if not settings.openai_api_key:
        raise SystemExit("缺少 MiMo API 凭据。")
    if not settings.base_url:
        raise SystemExit("缺少 MiMo endpoint。")
    endpoint = urlparse(settings.base_url)
    if (
        endpoint.scheme != ALLOWED_ENDPOINT[0]
        or endpoint.hostname != ALLOWED_ENDPOINT[1]
        or endpoint.path.rstrip("/") != ALLOWED_ENDPOINT[2]
        or endpoint.query
        or endpoint.fragment
    ):
        raise SystemExit("endpoint 不是预登记的 Xiaomi MiMo Responses API。")
    return settings


def verify_freeze(freeze: dict[str, Any]) -> None:
    gate = read_json(GATE_PATH)
    if gate.get("failure_count") != 0 or gate.get("maps_ok") != len(MAP_IDS):
        raise SystemExit("离线门禁未通过，禁止正式运行。")
    if freeze.get("model_id") != MODEL_NAME or freeze.get("provider") != "openai":
        raise SystemExit("冻结清单的模型/供应商与运行器不一致。")
    maps = freeze.get("maps")
    if not isinstance(maps, dict) or set(maps) != set(MAP_IDS):
        raise SystemExit("冻结清单不是完整的 30 图。")
    for map_id in MAP_IDS:
        entry = maps[map_id]
        environment = create_environment(map_id, step_limit=160)
        prompt = system_prompt(environment, decision_budget=entry["decision_budget"])
        if entry["rule_hash"] != rule_hash(map_id):
            raise SystemExit(f"{map_id} rule_hash 已变化，必须重新冻结。")
        if entry["scenario_hash"] != scenario_hash(map_id):
            raise SystemExit(f"{map_id} scenario_hash 已变化，必须重新冻结。")
        if entry["metric_schema_hash"] != metric_schema_hash(map_id):
            raise SystemExit(f"{map_id} metric_schema_hash 已变化，必须重新冻结。")
        if entry["prompt_hash"] != sha256(prompt.encode()).hexdigest():
            raise SystemExit(f"{map_id} prompt_hash 已变化，必须重新冻结。")


def formal_plan() -> list[dict[str, Any]]:
    plan = []
    for spec in registered_specs():
        budget = 60 if spec.map_id == "MAP-12" else spec.decision_budget
        plan.append(
            {
                "map_id": spec.map_id,
                "world": spec.world,
                "difficulty": spec.level,
                "condition_id": spec.condition_id,
                "seed": spec.seed,
                "replicate_id": spec.replicate_id,
                "decision_budget": budget,
            }
        )
    return plan


def scan_attempts() -> dict[tuple[str, int], list[dict[str, Any]]]:
    attempts: dict[tuple[str, int], list[dict[str, Any]]] = {}
    if not EPISODE_ROOT.is_dir():
        return attempts
    for path in sorted(EPISODE_ROOT.glob("*/episode_manifest.json")):
        manifest = read_json(path)
        key = (str(manifest.get("map_id")), int(manifest.get("replicate_id", 0)))
        attempts.setdefault(key, []).append(manifest)
    return attempts


def formal_outcome(attempts: list[dict[str, Any]]) -> dict[str, Any] | None:
    for manifest in attempts:
        if manifest.get("status") in NON_RETRYABLE_OUTCOMES:
            return manifest
    return None


def ledger_source_hashes() -> dict[str, str]:
    return {map_id: rule_hash(map_id) for map_id in MAP_IDS}


def run_manifest(freeze: dict[str, Any], ledger: V8BudgetLedger) -> dict[str, Any]:
    plan = formal_plan()
    return {
        "schema_version": "v8_run_manifest_v1",
        "experiment_id": ledger.experiment_id,
        "freeze_hash": freeze["freeze_hash"],
        "runtime_tree_hash": freeze["runtime_tree_hash"],
        "commit": freeze["commit"],
        "model_id": MODEL_NAME,
        "provider": "openai",
        "temperature": 0,
        "currency": "CNY",
        "max_cost": "10",
        "planned_episodes": len(plan),
        "supplement_slots": MAX_SUPPLEMENTS,
        "plan": plan,
        "created_at": utc_now(),
    }


def checkpoint(
    world: str,
    attempts: dict[tuple[str, int], list[dict[str, Any]]],
    ledger: V8BudgetLedger,
) -> None:
    world_maps = [map_id for map_id in MAP_IDS if WORLD_OF[map_id] == world]
    rows = []
    for map_id in world_maps:
        for replicate in range(3):
            manifests = attempts.get((map_id, replicate), [])
            chosen = formal_outcome(manifests)
            rows.append(
                {
                    "map_id": map_id,
                    "replicate_id": replicate,
                    "attempts": len(manifests),
                    "run_id": chosen.get("run_id") if chosen else None,
                    "status": chosen.get("status") if chosen else "missing",
                    "success": chosen.get("success") if chosen else None,
                }
            )
    write_json(
        CHECKPOINT_DIR / f"{world}.json",
        {
            "world": world,
            "updated_at": utc_now(),
            "ledger": ledger.snapshot(),
            "rows": rows,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", action="append", default=[], help="只运行指定世界")
    parser.add_argument("--dry-run", action="store_true", help="只校验冻结与预算，不发请求")
    parser.add_argument("--max-episodes", type=int, default=0, help="调试用：限制本次运行局数")
    args = parser.parse_args()

    freeze = read_json(FREEZE_PATH)
    verify_freeze(freeze)
    settings = settings_for_run()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "freeze_hash": freeze["freeze_hash"],
                    "runtime_tree_hash": freeze["runtime_tree_hash"],
                    "planned_episodes": len(formal_plan()),
                    "model": settings.model_name,
                    "budget": "10 CNY",
                },
                ensure_ascii=False,
            )
        )
        return 0

    EXPERIMENT_ROOT.mkdir(parents=True, exist_ok=True)
    EPISODE_ROOT.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    resume = LEDGER_PATH.is_file()
    try:
        ledger = V8BudgetLedger(
            LEDGER_PATH,
            currency="CNY",
            model=MODEL_NAME,
            source_hashes=ledger_source_hashes(),
            resume=resume,
        )
    except (V8BudgetClosed, FileExistsError, FileNotFoundError) as exc:
        print(f"BLOCKED: ledger cannot be opened: {exc}")
        return 2

    manifest_payload = run_manifest(freeze, ledger)
    if RUN_MANIFEST_PATH.is_file():
        prior = read_json(RUN_MANIFEST_PATH)
        if (
            prior.get("freeze_hash") != manifest_payload["freeze_hash"]
            or prior.get("experiment_id") != manifest_payload["experiment_id"]
        ):
            print("BLOCKED: 现有 run_manifest 与冻结/账本身份不一致。")
            return 2
    else:
        write_json(RUN_MANIFEST_PATH, {**manifest_payload, "status": "running"})

    attempts = scan_attempts()
    provider = OpenAIDecisionProvider(settings)
    worlds = args.world or list(dict.fromkeys(WORLD_OF[map_id] for map_id in MAP_IDS))
    supplements_used = sum(
        max(0, len(items) - 1) for items in attempts.values()
    )
    ran = 0
    consecutive_schema_faults = 0

    for world in worlds:
        if ledger.closed:
            print(f"STOP: ledger closed before world={world}")
            break
        world_maps = [map_id for map_id in MAP_IDS if WORLD_OF[map_id] == world]
        for map_id in world_maps:
            for replicate in range(3):
                key = (map_id, replicate)
                if formal_outcome(attempts.get(key, [])) is not None:
                    continue
                need_supplement = bool(attempts.get(key))
                if need_supplement and supplements_used >= MAX_SUPPLEMENTS:
                    print(f"SKIP supplement limit reached for {map_id} R{replicate}")
                    continue
                spec = V8EpisodeSpec(
                    map_id,
                    replicate,
                    freeze["maps"][map_id]["decision_budget"],
                )
                runner = V8Runner(
                    provider=provider,
                    settings=settings,
                    ledger=ledger,
                    output_dir=EXPERIMENT_ROOT,
                    commit=freeze["commit"],
                    progress=lambda row: print(json.dumps(row, ensure_ascii=False), flush=True),
                )
                print(
                    f"RUN {map_id} R{replicate} world={world}"
                    f" budget={spec.decision_budget} supplement={need_supplement}",
                    flush=True,
                )
                try:
                    episode = runner.run(spec)
                except V8BudgetClosed as exc:
                    print(f"STOP: budget closed during {map_id} R{replicate}: {exc}")
                    ledger.close("RUNTIME_BUDGET_CLOSED", map_id=map_id)
                    checkpoint(world, attempts, ledger)
                    write_json(
                        RUN_MANIFEST_PATH,
                        {
                            **manifest_payload,
                            "status": "blocked",
                            "blocked_reason": "runtime_budget_closed",
                            "updated_at": utc_now(),
                        },
                    )
                    return 2
                attempts.setdefault(key, []).append(episode)
                if need_supplement:
                    supplements_used += 1
                ran += 1
                print(
                    f"DONE {map_id} R{replicate} status={episode['status']}"
                    f" success={episode['success']} cost={episode['usage']['cost']}",
                    flush=True,
                )
                if episode["status"] == "schema_fault_limit":
                    consecutive_schema_faults += 1
                else:
                    consecutive_schema_faults = 0
                if episode["status"] in FATAL_OUTCOMES:
                    print(f"STOP: fatal outcome {episode['status']}")
                    checkpoint(world, attempts, ledger)
                    write_json(
                        RUN_MANIFEST_PATH,
                        {
                            **manifest_payload,
                            "status": "blocked",
                            "blocked_reason": episode["status"],
                            "updated_at": utc_now(),
                        },
                    )
                    return 2
                if consecutive_schema_faults >= 3:
                    print("STOP: three consecutive schema-fault episodes; audit required.")
                    checkpoint(world, attempts, ledger)
                    write_json(
                        RUN_MANIFEST_PATH,
                        {
                            **manifest_payload,
                            "status": "blocked",
                            "blocked_reason": "three_consecutive_schema_faults",
                            "updated_at": utc_now(),
                        },
                    )
                    return 2
                if args.max_episodes and ran >= args.max_episodes:
                    checkpoint(world, attempts, ledger)
                    print(f"STOP: --max-episodes {args.max_episodes} reached")
                    return 0
        checkpoint(world, attempts, ledger)
        snapshot = ledger.snapshot()
        print(
            f"CHECKPOINT {world} settled={snapshot['settled_cost']}"
            f" projected={snapshot['projected_cost']} warnings={snapshot['warnings']}",
            flush=True,
        )
        if ledger.closed:
            break

    completed = sum(
        1 for key in attempts if formal_outcome(attempts[key]) is not None
    )
    write_json(
        RUN_MANIFEST_PATH,
        {
            **manifest_payload,
            "status": "completed" if completed == len(manifest_payload["plan"]) else "incomplete",
            "formal_episodes_completed": completed,
            "supplements_used": supplements_used,
            "ledger": ledger.snapshot(),
            "updated_at": utc_now(),
        },
    )
    print(
        json.dumps(
            {
                "formal_episodes_completed": completed,
                "planned": len(manifest_payload["plan"]),
                "supplements_used": supplements_used,
                "ledger": ledger.snapshot(),
            },
            ensure_ascii=False,
        )
    )
    return 0 if completed == len(manifest_payload["plan"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
