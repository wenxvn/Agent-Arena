"""V10 有界 MiMo 复测（Batch 8）。

- 账本：``runs/v10/mimo/ledger_v10_001.jsonl``（V10 独立 append-only 账本），
  与 V10 早期补充账本共享 **CNY 10** 全局额度；任何拆分账本都会被 ``prior_spend`` 计入；
- 矩阵：P0 五图 × 3 seed（15）+ 古堡三图 × 3 seed（9）+ 接口七图 × 3 seed（21）= 45 局；
- 每局保存 ``episodes/<run_id>/agent_trace.jsonl``（agent-visible）、``judge.json``
  （密封真值与指标）、``manifest.json``（身份与成本）；
- 失败/中断保留；``UNKNOWN_PROVIDER_SPEND``、usage 越界或连续 3 次 provider 错误立即封账停止；
- 已完成的 ``run_id`` 不会重复调用；补跑必须使用新 ``run_id`` 并在 ``RETRIES`` 中登记原因。

用法：
    python scripts/run_v10_mimo.py --dry-run
    python scripts/run_v10_mimo.py --maps MAP-18 MAP-21 --limit 2
    python scripts/run_v10_mimo.py                 # 剩余矩阵
"""

from __future__ import annotations

import argparse
import json
import subprocess
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
from agent_arena.llm.openai import OpenAIDecisionProvider  # noqa: E402
from agent_arena.llm.protocol import DecisionRequest  # noqa: E402
from agent_arena.v10.baselines.suite import decision_budget  # noqa: E402
from agent_arena.v10.ledger import (  # noqa: E402
    CAP_CNY,
    V10BudgetClosed,
    V10BudgetLedger,
    global_spend,
)
from agent_arena.v10.metrics.governance import schema_hash  # noqa: E402
from agent_arena.v10.runtime.catalog import (  # noqa: E402
    LEVEL_OF,
    WORLD_OF,
    create_environment,
    metric_hash,
    rule_hash,
    scenario_hash,
)
from agent_arena.worlds.scenario_v8.models import V8Action, V8Observation  # noqa: E402

MIMO_ROOT = ROOT / "runs" / "v10" / "mimo"
EPISODE_ROOT = MIMO_ROOT / "episodes"
RESULTS_PATH = MIMO_ROOT / "results.json"
PREREG = ROOT / "docs" / "v10" / "mimo-preregistration.json"
LEDGER_PATH = MIMO_ROOT / "ledger_v10_001.jsonl"
LEDGER_EXT_PATH = MIMO_ROOT / "ledger_v10_002.jsonl"
LEDGER_I2_PATH = MIMO_ROOT / "ledger_v10_004.jsonl"
LEDGER_J2_PATH = MIMO_ROOT / "ledger_v10_008.jsonl"
PHASE_LEDGERS = {
    "main": LEDGER_PATH,
    "ext": LEDGER_EXT_PATH,
    "i2": LEDGER_I2_PATH,
    "j2": LEDGER_J2_PATH,
}
MODEL_NAME = "mimo-v2.6-flash"
MAX_CONSECUTIVE = 3
HISTORY_WINDOW = 5

P0 = ("MAP-03", "MAP-06", "MAP-15", "MAP-18", "MAP-21")
CASTLE = ("MAP-28", "MAP-29", "MAP-30")
INTERFACE = ("MAP-07", "MAP-08", "MAP-09", "MAP-10", "MAP-11", "MAP-12", "MAP-26")
#: 阶段 2 扩展：其余 8 张 V10 原生图 × 3 环境 seed，把 MiMo 覆盖补齐到 23 张原生图。
EXTENSION = (
    "MAP-04",
    "MAP-13",
    "MAP-14",
    "MAP-19",
    "MAP-20",
    "MAP-22",
    "MAP-23",
    "MAP-24",
)
PHASE_GROUPS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "main": (("p0", P0), ("castle", CASTLE), ("interface", INTERFACE)),
    "ext": (("ext", EXTENSION),),
    #: 阶段 3：接口修复（DCR-V10-24，带类型的公开动作契约）后的补测，覆盖 Batch 8 中
    #: 确有“形状被误解”证据的图。整图全 seed 重跑，不按单局成败挑选。
    "i2": (("i2", ("MAP-18", "MAP-19", "MAP-20", "MAP-28")),),
    #: 阶段 4：MAP-20 公开接口补全（DCR-V10-25）后的重测。
    "j2": (("j2", ("MAP-20",)),),
}

#: 逐图格式澄清（只写公开结构，不含真值/答案）；随 prompt_hash 一起冻结。
CONTRACT_HINTS: dict[str, tuple[str, ...]] = {
    "MAP-18": (
        "operations 是对象（不是数组）：键为列车 id，值为对象；"
        '值的 op 只能是 "release"/"detour"/"temporary_stop"/"cancel_service"，'
        'release/detour 用 "to" 给目标站，cancel_service 用 "task_id" 给任务。',
    ),
    "MAP-28": (
        "claims 是对象数组（不是对象映射）：每个元素形如 "
        '{"claim_id": <四个字段之一>, "value": <该字段的取值>}；'
        'citations_by_claim 是对象：键为四个字段名，值为已记录证据 ID 的数组。',
    ),
    "MAP-19": (
        "forecast_next 与 set_cooling 都是长度为 3 的整数数组，顺序固定为区 A、B、C"
        "（不是以区名为键的对象）。",
    ),
}

#: 已完成的局（V10 早期账本，保留不覆盖）。续跑时跳过。
EARLY_RUN_IDS = {
    "V10-MAP-03-S0-p0",
    "V10-MAP-03-S1-p0",
    "V10-MAP-03-S2-p0",
    "V10-MAP-06-S0-p0",
    "V10-MAP-06-S1-p0",
    "V10-MAP-06-S2-p0",
    "V10-MAP-15-S0-p0",
    "V10-MAP-15-S1-p0",
    "V10-MAP-15-S2-p0",
}

#: 补跑登记：新 run_id + 原因。不得以“失败”为理由重试，只允许接口/账本缺陷修复后补跑。
RETRIES: tuple[dict[str, Any], ...] = (
    {
        "run_id": "V10-MAP-15-S2-p0-r2",
        "phase": "main",
        "map_id": "MAP-15",
        "environment_seed": 2,
        "group": "p0",
        "reason": (
            "早期 runner 把完整 Observation 写进 5 条 history，导致第 31 步输入 8136 token 触发"
            "登记上限并封账；已把 history 收敛为 action+result，按补跑规则用新 run_id 重跑"
        ),
    },
    {
        "run_id": "V10-MAP-19-S2-ext-r2",
        "phase": "ext",
        "map_id": "MAP-19",
        "environment_seed": 2,
        "group": "ext",
        "reason": (
            "第 2 步 provider APIConnectionError（结果未确认）按规则封账止损；补跑新 run_id，"
            "旧局 V10-MAP-19-S2-ext 原样保留"
        ),
    },
    {
        "run_id": "V10-MAP-22-S0-ext-r2",
        "phase": "ext",
        "map_id": "MAP-22",
        "environment_seed": 0,
        "group": "ext",
        "reason": (
            "第 34 步 provider APIConnectionError（结果未确认）按规则封账止损；补跑新 run_id，"
            "旧局 V10-MAP-22-S0-ext 原样保留"
        ),
    },
    {
        "run_id": "V10-MAP-22-S2-ext-r2",
        "phase": "ext",
        "map_id": "MAP-22",
        "environment_seed": 2,
        "group": "ext",
        "reason": (
            "第 10 步 provider APIConnectionError（结果未确认）按规则封账止损；补跑新 run_id，"
            "旧局 V10-MAP-22-S2-ext 原样保留"
        ),
    },
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _contract(environment: Any, map_id: str) -> str:
    from agent_arena.v10.contract import action_contract

    hint_lines = CONTRACT_HINTS.get(map_id, ())
    hints = "".join(f"\n注意：{item}" for item in hint_lines)
    return action_contract(environment.SHAPES) + hints


def _system_prompt(map_id: str, environment: Any) -> str:
    rules = "\n".join(f"- {item}" for item in environment.public_rules())
    return (
        f"你在玩一个确定性回合制解密关卡（{map_id}）。每回合必须从允许动作里选一个。\n"
        "输出必须是一个 JSON 对象：字段 tool 加上该 tool 允许的字段；"
        "禁止输出 command/target/args 等旧格式。示例：tool=move 且 to=B。\n"
        f"公开规则：\n{rules}\n\n{_contract(environment, map_id)}"
    )


def _episodes(phase: str = "main") -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for group, maps in PHASE_GROUPS[phase]:
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
    for retry in RETRIES:
        if retry.get("phase", "main") != phase:
            continue
        plan.append(
            {
                "run_id": retry["run_id"],
                "map_id": retry["map_id"],
                "world": WORLD_OF[retry["map_id"]],
                "difficulty": LEVEL_OF[retry["map_id"]],
                "environment_seed": retry["environment_seed"],
                "replicate": 0,
                "group": retry["group"],
                "decision_budget": decision_budget(retry["map_id"]),
                "retry_reason": retry["reason"],
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


def _prior_ledgers(exclude: Path) -> list[Path]:
    return sorted(
        path
        for path in MIMO_ROOT.glob("ledger*.jsonl")
        if path.resolve() != exclude.resolve()
    )


def _settings() -> RuntimeSettings:
    settings = RuntimeSettings(response_format="json_object")
    if not settings.openai_api_key:
        raise SystemExit("缺少 OPENAI_API_KEY")
    return settings


def _head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _prereg_hash() -> str:
    return sha256(PREREG.read_bytes()).hexdigest() if PREREG.is_file() else ""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _episode_dir(run_id: str) -> Path:
    path = EPISODE_ROOT / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _already_done(run_id: str) -> bool:
    return (EPISODE_ROOT / run_id / "manifest.json").is_file()


def _episode_costs(ledger: V10BudgetLedger, run_id: str) -> tuple[float, bool]:
    events = ledger.read_events()
    settled = sum(
        (
            Decimal(str(event.get("actual_cost", "0")))
            for event in events
            if event["event"] == "request_settled" and event.get("episode_id") == run_id
        ),
        Decimal(0),
    )
    unknown = any(
        event["event"] == "request_failed"
        and event.get("episode_id") == run_id
        and event.get("unknown_spend")
        for event in events
    )
    return float(settled), unknown


def run_episode(
    episode: dict[str, Any],
    *,
    provider: OpenAIDecisionProvider,
    ledger: V10BudgetLedger,
    manifest_hash: str,
    commit: str,
) -> dict[str, Any]:
    map_id = str(episode["map_id"])
    seed = int(episode["environment_seed"])
    budget = int(episode["decision_budget"])
    run_id = str(episode["run_id"])
    environment = create_environment(map_id, environment_seed=seed)
    system = _system_prompt(map_id, environment)
    prompt_hash = sha256(system.encode("utf-8")).hexdigest()
    episode_dir = _episode_dir(run_id)
    trace_path = episode_dir / "agent_trace.jsonl"
    trace_path.write_text("", encoding="utf-8")
    header = {
        "event": "trace_header",
        "schema": "v10-mimo-trace-1",
        "experiment_id": ledger.experiment_id,
        "run_id": run_id,
        "map_id": map_id,
        "world": WORLD_OF[map_id],
        "difficulty": LEVEL_OF[map_id],
        "environment_seed": seed,
        "replicate": episode["replicate"],
        "scenario_hash": scenario_hash(map_id, seed),
        "rule_hash": rule_hash(map_id),
        "metric_hash": metric_hash(map_id),
        "metric_schema_hash": schema_hash(),
        "prompt_hash": prompt_hash,
        "preregistration_hash": _prereg_hash(),
        "manifest_hash": manifest_hash,
        "code_commit": commit,
        "model_id": MODEL_NAME,
        "temperature": 0,
        "decision_budget": budget,
        "history_window": HISTORY_WINDOW,
        "agent_visible_only": True,
    }
    _append_jsonl(trace_path, header)

    ledger.start_episode(run_id, map_id=map_id, seed=seed, condition_id="v10")
    observation = environment.observe()
    history: list[dict[str, Any]] = []
    decisions = invalid = rejected = 0
    outcome = "decision_budget_exhausted"
    provider_error: str | None = None
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
        except V10BudgetClosed:
            outcome = "budget_closed"
            break
        request = DecisionRequest(
            observation=V8Observation(**observation),
            system_prompt=system,
            correction=invalid > 0,
            invalid_output_reason="schema" if invalid else None,
            recent_history=(
                json.dumps(history[-HISTORY_WINDOW:], ensure_ascii=False, sort_keys=True)
                if history
                else None
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
            provider_error = exc.error_category
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
            provider_error = type(exc).__name__
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
        except V10BudgetClosed as exc:
            outcome = f"settle_closed:{exc}"
            break
        candidate = response.candidate
        try:
            action = V8Action.model_validate(candidate, strict=True)
        except Exception:  # noqa: BLE001 - invalid model output is a legal outcome
            action = None
        if action is None or not environment.accepts(action):
            result = environment.reject_invalid_action()
            invalid += 1
            entry: dict[str, Any] = {"invalid_output": candidate}
        else:
            result = environment.step(action)
            if str(result.result).startswith(("INVALID", "NO_", "NOT_", "UNKNOWN", "ALREADY")):
                rejected += 1
            entry = action.model_dump(mode="json", exclude_none=True)
        observation = environment.observe()
        history.append({"action": entry, "result": result.result})
        decisions += 1
        _append_jsonl(
            trace_path,
            {
                "event": "decision",
                "run_id": run_id,
                "decision_index": decisions,
                "request_id": request_id,
                "action": entry,
                "result": result.result,
                "status": result.status.value,
                "observation_after": observation,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "latency_ms": latency,
                "state_hash_after": environment.state_hash(),
            },
        )
    if environment.is_terminal:
        outcome = "success" if environment.is_success else "failure"
    metrics = environment.metrics()
    judge = environment.judge_state()
    cost_settled, cost_unknown = _episode_costs(ledger, run_id)
    result_row = {
        "run_id": run_id,
        "map_id": map_id,
        "world": WORLD_OF[map_id],
        "difficulty": LEVEL_OF[map_id],
        "environment_seed": seed,
        "replicate": episode["replicate"],
        "group": episode["group"],
        "model_id": MODEL_NAME,
        "temperature": 0,
        "scenario_hash": scenario_hash(map_id, seed),
        "rule_hash": rule_hash(map_id),
        "metric_hash": metric_hash(map_id),
        "metric_schema_hash": schema_hash(),
        "prompt_hash": prompt_hash,
        "preregistration_hash": _prereg_hash(),
        "manifest_hash": manifest_hash,
        "code_commit": commit,
        "termination": environment.terminal_reason or outcome,
        "outcome": outcome,
        "success": environment.is_success,
        "decision_count": decisions,
        "invalid_actions": invalid,
        "rejected_actions": rejected,
        "mechanism_triggered": environment.mechanism_triggered(),
        "primary_metric": environment.PRIMARY_METRIC,
        "primary_metric_state": metrics.get(environment.PRIMARY_METRIC, {}).get("state"),
        "primary_metric_value": metrics.get(environment.PRIMARY_METRIC, {}).get("value"),
        "cost_settled": cost_settled,
        "cost_unknown": cost_unknown,
        "provider_error": provider_error,
        "trace_path": str(trace_path.relative_to(ROOT)),
        "judge_path": str((episode_dir / "judge.json").relative_to(ROOT)),
        "retry_reason": episode.get("retry_reason"),
    }
    _write_json(
        episode_dir / "judge.json",
        {
            "run_id": run_id,
            "map_id": map_id,
            "environment_seed": seed,
            "scenario_hash": result_row["scenario_hash"],
            "rule_hash": result_row["rule_hash"],
            "metric_hash": result_row["metric_hash"],
            "status": outcome,
            "success": environment.is_success,
            "termination_reason": environment.terminal_reason,
            "judge_state_hash": environment.state_hash(),
            "judge_state": judge,
            "metrics": metrics,
            "mechanism_triggered": result_row["mechanism_triggered"],
            "primary_metric": result_row["primary_metric"],
            "primary_metric_state": result_row["primary_metric_state"],
            "primary_metric_value": result_row["primary_metric_value"],
            "decision_count": decisions,
            "invalid_actions": invalid,
            "rejected_actions": rejected,
            "cost_settled": cost_settled,
            "cost_unknown": cost_unknown,
            "finished_at": utc_now(),
        },
    )
    if not ledger.closed:
        ledger.complete_episode(
            run_id,
            status=outcome,
            success=environment.is_success,
            decision_count=decisions,
        )
    _write_json(episode_dir / "manifest.json", {**header, **result_row, "finished_at": utc_now()})
    return result_row


def _load_results() -> dict[str, dict[str, Any]]:
    if not RESULTS_PATH.is_file():
        return {}
    rows = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        return {str(key): value for key, value in rows.items()}
    return {str(row["run_id"]): row for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--maps", nargs="*", default=[])
    parser.add_argument("--phase", choices=sorted(PHASE_GROUPS), default="main")
    parser.add_argument("--ledger", type=Path, default=None)
    args = parser.parse_args()
    ledger_path = args.ledger or PHASE_LEDGERS[args.phase]

    episodes = _episodes(args.phase)
    if args.maps:
        episodes = [item for item in episodes if item["map_id"] in set(args.maps)]
    pending = [
        item
        for item in episodes
        if item["run_id"] not in EARLY_RUN_IDS and not _already_done(item["run_id"])
    ]
    if args.limit:
        pending = pending[: args.limit]
    manifest = {
        "schema": "v10-mimo-manifest-1",
        "created_at": utc_now(),
        "phase": args.phase,
        "model": MODEL_NAME,
        "temperature": 0,
        "cap_cny": str(CAP_CNY),
        "schema_hash": schema_hash(),
        "preregistration_hash": _prereg_hash(),
        "manifest_hash": _manifest_hash(episodes),
        "planned_episodes": len(episodes),
        "episodes": episodes,
    }
    MIMO_ROOT.mkdir(parents=True, exist_ok=True)
    (MIMO_ROOT / f"manifest_{args.phase}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )
    if args.phase == "main":
        _write_json(MIMO_ROOT / "manifest.json", manifest)

    prior_paths = _prior_ledgers(ledger_path)
    prior_settled, prior_pending, prior_requests = global_spend(prior_paths)
    prior_spend = prior_settled + prior_pending
    if args.dry_run:
        print(
            json.dumps(
                {
                    "pending_episodes": len(pending),
                    "maps": sorted({item["map_id"] for item in pending}),
                    "manifest_hash": manifest["manifest_hash"][:16],
                    "prior_ledgers": [path.name for path in prior_paths],
                    "prior_settled_cny": str(prior_settled),
                    "prior_pending_cny": str(prior_pending),
                    "prior_spend_cny": str(prior_spend),
                    "remaining_cny": str(CAP_CNY - prior_spend),
                    "estimated_upper_cny": round(
                        sum(min(item["decision_budget"], 46) for item in pending) * 0.0028,
                        4,
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    settings = _settings()
    ledger = V10BudgetLedger(
        ledger_path,
        currency="CNY",
        model=MODEL_NAME,
        source_hashes={
            "manifest": manifest["manifest_hash"],
            "schema": schema_hash(),
            "preregistration": manifest["preregistration_hash"],
        },
        prior_spend=prior_spend,
        prior_requests=prior_requests,
        resume=ledger_path.exists(),
    )
    ledger.record("v10_manifest_loaded", manifest_hash=manifest["manifest_hash"])
    provider = OpenAIDecisionProvider(settings)
    results = _load_results()
    commit = _head()
    EPISODE_ROOT.mkdir(parents=True, exist_ok=True)
    with (MIMO_ROOT / f"run_{args.phase}.log").open(
        "a", encoding="utf-8", newline="\n"
    ) as log:
        log.write(f"=== resume {utc_now()} pending={len(pending)} ===\n")
        for index, episode in enumerate(pending, start=1):
            log.write(f"[{index}/{len(pending)}] {episode['run_id']}\n")
            log.flush()
            try:
                row = run_episode(
                    episode,
                    provider=provider,
                    ledger=ledger,
                    manifest_hash=manifest["manifest_hash"],
                    commit=commit,
                )
            except V10BudgetClosed as exc:
                ledger.close("RUNTIME_BUDGET_CLOSED", detail=str(exc))
                log.write(f"STOP: {exc}\n")
                break
            results[row["run_id"]] = row
            _write_json(RESULTS_PATH, {k: results[k] for k in sorted(results)})
            log.write(
                json.dumps(
                    {
                        "run_id": row["run_id"],
                        "success": row["success"],
                        "termination": row["termination"],
                        "decisions": row["decision_count"],
                        "primary": row["primary_metric_value"],
                        "cost": row["cost_settled"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            log.flush()
            print(
                json.dumps(
                    {
                        "run_id": row["run_id"],
                        "success": row["success"],
                        "decisions": row["decision_count"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            if row["outcome"] in {"unknown_provider_spend", "provider_error_limit"}:
                log.write("STOP: provider anomaly\n")
                break
            if ledger.closed:
                log.write("STOP: ledger closed\n")
                break
        snapshot = ledger.snapshot()
        log.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    print(json.dumps({"episodes": len(results), "ledger": ledger.snapshot()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
