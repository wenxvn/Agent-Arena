"""V8 三十图离线统一门禁。

覆盖范围：注册表与哈希、30 图 Oracle 真实 step 回放、同初态确定性、
公开/裁判边界与泄漏扫描、指标 id/形状/非恒定检查、手算 fixture、
终止后不变性、Runner smoke（FakeProvider）与 90 局费用 dry-run。

用法：python scripts/validate_v8_offline.py
输出：runs/v8/offline_gate.json（机器可读）与控制台摘要。
"""

from __future__ import annotations

import importlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.config import RuntimeSettings  # noqa: E402
from agent_arena.llm.fake import FakeDecisionProvider  # noqa: E402
from agent_arena.llm.protocol import ProviderResponse  # noqa: E402
from agent_arena.v7.metrics.registry import specs_for  # noqa: E402
from agent_arena.v8.budget import (  # noqa: E402
    MAX_COST_CNY,
    MAX_INPUT_TOKENS_PER_REQUEST,
    MAX_OUTPUT_TOKENS_PER_REQUEST,
    V8BudgetLedger,
)
from agent_arena.v8.metrics import metric_schema_hash, project_metrics, summarize  # noqa: E402
from agent_arena.v8.prompts import system_prompt  # noqa: E402
from agent_arena.v8.runner import (  # noqa: E402
    DECISION_BUDGETS,
    V8EpisodeSpec,
    V8Runner,
    registered_specs,
)
from agent_arena.worlds.scenario_v8 import adapter_cases, create_environment  # noqa: E402
from agent_arena.worlds.scenario_v8.catalog import (  # noqa: E402
    CONDITIONS,
    LEVEL_OF,
    MAP_IDS,
    WORLD_OF,
    rule_hash,
    scenario_hash,
    source_hash,
)
from agent_arena.worlds.scenario_v8.models import V8Action  # noqa: E402
from agent_arena.worlds.scenario_v8.oracle import (  # noqa: E402
    load_oracle_groups,
    normalize_action_payload,
)

OUTPUT = ROOT / "runs" / "v8" / "offline_gate.json"
CORE_KEYS = {"map_id", "terminal", "terminal_reason", "last_action_result"}
V4_RUNTIME_MAPS = frozenset(CONDITIONS)
METRIC_ID = re.compile(r"^map\d{2}\.[a-z0-9_]+$")


class Gate:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.rows: dict[str, dict[str, Any]] = {}

    def require(self, condition: bool, message: str) -> bool:
        if not condition:
            self.failures.append(message)
            prefix = message.split(":", 1)[0]
            if prefix in self.rows:
                self.rows[prefix]["problems"].append(message)
        return condition

    def row(self, map_id: str) -> dict[str, Any]:
        return self.rows.setdefault(map_id, {"map_id": map_id, "problems": []})

    def problem(self, map_id: str, message: str) -> None:
        self.rows[map_id]["problems"].append(message)
        self.failures.append(f"{map_id}: {message}")


def module_for(map_id: str) -> Any | None:
    try:
        return importlib.import_module(f"agent_arena.worlds.scenario_v8.maps.map{map_id[-2:]}")
    except ModuleNotFoundError:
        return None


def oracle_cases(map_id: str) -> list[dict[str, Any]]:
    module = module_for(map_id)
    custom = getattr(module, "ORACLE_CASES", None) if module else None
    if custom:
        return [dict(case) for case in custom]
    if map_id in V4_RUNTIME_MAPS:
        return [dict(case) for case in adapter_cases.oracle_cases(map_id)]
    return [
        {
            "trace_id": trace_id,
            "seed": 0,
            "actions": [row["action"] for row in rows],
            "expect_success": True,
        }
        for trace_id, rows in load_oracle_groups(map_id).items()
    ]


def replay(map_id: str, actions: list[dict[str, Any]], seed: int = 0) -> Any:
    environment = create_environment(map_id, seed=seed)
    hashes: list[str] = []
    observations: list[dict[str, Any]] = []
    for payload in actions:
        environment.step(V8Action.model_validate(normalize_action_payload(payload), strict=True))
        hashes.append(environment.state_hash())
        observations.append(environment.observe())
    return environment, hashes, observations


def fixture_cases(map_id: str) -> list[dict[str, Any]]:
    module = module_for(map_id)
    if module is not None:
        return [dict(case) for case in getattr(module, "FIXTURES", ())]
    return [dict(case) for case in adapter_cases.fixtures(map_id)]


def validate_map(gate: Gate, map_id: str) -> dict[str, Any]:
    row = gate.row(map_id)
    row.update(
        {
            "world": WORLD_OF[map_id],
            "level": LEVEL_OF[map_id],
            "condition_id": CONDITIONS.get(map_id, "default"),
            "scenario_hash": scenario_hash(map_id),
            "rule_hash": rule_hash(map_id),
            "source_hash": source_hash(map_id),
            "metric_schema_hash": metric_schema_hash(map_id),
        }
    )

    cases = oracle_cases(map_id)
    if not gate.require(bool(cases), f"{map_id}: 没有 Oracle 用例"):
        return row
    row["oracle_cases"] = []
    oracle_env: Any | None = None
    snapshots: list[dict[str, dict[str, Any]]] = []
    for case in cases:
        actions = case["actions"]
        environment, hashes, observations = replay(map_id, actions, case.get("seed", 0))
        again, hashes_again, observations_again = replay(map_id, actions, case.get("seed", 0))
        if case.get("expect_success", True):
            gate.require(
                environment.is_success,
                f"{map_id}:{case.get('trace_id')} Oracle 未成功"
                f"（{environment.status.value}/{environment.terminal_reason}）",
            )
        gate.require(
            hashes == hashes_again and observations == observations_again,
            f"{map_id}:{case.get('trace_id')} 同初态重放不确定",
        )
        row["oracle_cases"].append(
            {
                "trace_id": case.get("trace_id"),
                "actions": len(actions),
                "status": environment.status.value,
                "terminal_reason": environment.terminal_reason,
                "final_hash": environment.state_hash(),
            }
        )
        snapshots.append(project_metrics(environment, "success"))
        oracle_env = environment

    # 终止后不变性：终态动作不得改变状态、时钟或 Observation。
    if oracle_env is not None and oracle_env.is_terminal:
        before_hash = oracle_env.state_hash()
        before_tick = oracle_env.tick_count
        before_observation = oracle_env.observe()
        result = oracle_env.step(V8Action.model_validate({"tool": "wait", "turns": 1}, strict=True))
        gate.require(
            result.result == "ALREADY_TERMINAL",
            f"{map_id}: 终止后动作未返回 ALREADY_TERMINAL",
        )
        gate.require(oracle_env.state_hash() == before_hash, f"{map_id}: 终止后 state_hash 变化")
        gate.require(oracle_env.tick_count == before_tick, f"{map_id}: 终止后 tick 变化")
        gate.require(
            oracle_env.observe() == before_observation,
            f"{map_id}: 终止后 Observation 变化",
        )
        row["terminal_invariance"] = True
    else:
        row["terminal_invariance"] = False
        gate.problem(map_id, "Oracle 未到达终态，无法验证终止后不变性")

    # 泄漏边界：公开字段白名单 + prompt 不含裁判/指标标识。
    fresh = create_environment(map_id)
    public = set(fresh.observe())
    allowed = set(fresh.PUBLIC_FIELDS) | CORE_KEYS
    leaked = sorted(public - allowed)
    gate.require(not leaked, f"{map_id}: Observation 越界字段 {leaked}")
    prompt = system_prompt(fresh, decision_budget=DECISION_BUDGETS[LEVEL_OF[map_id]])
    forbidden = [spec.metric_id for spec in specs_for(map_id)] + [
        "judge_state",
        "oracle_trace",
        "hidden_state",
    ]
    matches = [token for token in forbidden if token in prompt]
    gate.require(not matches, f"{map_id}: prompt 泄漏内部标识 {matches}")
    row["public_field_count"] = len(public)
    row["leakage_ok"] = not leaked and not matches

    # 指标：id 精确一致、形状合法、至少一项随动作变化。
    known = [spec.metric_id for spec in specs_for(map_id)]
    gate.require(bool(known), f"{map_id}: 没有登记指标")
    for metric_id in known:
        gate.require(bool(METRIC_ID.match(metric_id)), f"{map_id}: 指标 id 不合规 {metric_id}")
    fresh_projected = project_metrics(fresh, "running")
    snapshots.insert(0, fresh_projected)
    gate.require(set(fresh_projected) == set(known), f"{map_id}: 指标 id 与登记表不一致")
    for metric_id, value in fresh_projected.items():
        status = value["status"]
        gate.require(
            status
            in {
                "valid",
                "not_applicable",
                "censored",
                "unavailable",
                "invalid_trace",
            },
            f"{map_id}:{metric_id} 状态非法 {status}",
        )
        if status == "valid":
            gate.require(value["value"] is not None, f"{map_id}:{metric_id} valid 但值为 None")
    varying = [
        metric_id
        for metric_id in known
        if len(
            {
                json.dumps(snapshot.get(metric_id, {}).get("value"), ensure_ascii=False)
                for snapshot in snapshots
            }
        )
        > 1
    ]
    gate.require(bool(varying), f"{map_id}: 所有指标在已回放路径上恒定")
    row["metric_count"] = len(known)
    row["varying_metrics"] = varying
    row["metric_summary"] = summarize(fresh_projected)

    # 手算 fixture：逐条真实回放并核对期望值。
    fixtures = fixture_cases(map_id)
    gate.require(len(fixtures) >= 2, f"{map_id}: 手算 fixture 少于 2 条")
    row["fixtures"] = []
    for fixture in fixtures:
        environment = create_environment(map_id, seed=fixture.get("seed", 0))
        for payload in fixture["actions"]:
            environment.step(V8Action.model_validate(payload, strict=True))
        metrics = environment.metrics()
        snapshots.append(project_metrics(environment, environment.status.value))
        problems = 0
        for metric_id, expected in fixture["expect"].items():
            value = metrics.get(metric_id)
            if isinstance(value, dict):
                value = (
                    round(value["numerator"] / value["denominator"], 6)
                    if value["denominator"]
                    else None
                )
            if value != expected:
                gate.problem(
                    map_id,
                    f"fixture {fixture['name']}: {metric_id} 期望 {expected} 实得 {value}",
                )
                problems += 1
        row["fixtures"].append(
            {
                "name": fixture["name"],
                "actions": len(fixture["actions"]),
                "status": environment.status.value,
                "terminal_reason": environment.terminal_reason,
                "passed": problems == 0,
            }
        )
    row["failure_or_boundary_cases"] = sum(
        1 for item in row["fixtures"] if item["status"] != "scenario_success"
    )
    return row


def runner_smoke(gate: Gate) -> dict[str, Any]:
    map_id = "MAP-01"
    case = oracle_cases(map_id)[0]
    actions = case["actions"]
    root = Path(tempfile.mkdtemp(prefix="v8-offline-smoke-"))
    ledger = V8BudgetLedger(
        root / "ledger.jsonl",
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={item: source_hash(item) for item in MAP_IDS},
    )
    settings = RuntimeSettings().model_copy(update={"response_format": "json_object"})
    provider = FakeDecisionProvider(
        [
            ProviderResponse(
                candidate={"decision_reason": "offline smoke", "action": action},
                input_tokens=900,
                output_tokens=120,
            )
            for action in actions
        ]
    )
    runner = V8Runner(
        provider=provider,
        settings=settings,
        ledger=ledger,
        output_dir=root,
        commit="offline-smoke",
    )
    manifest = runner.run(V8EpisodeSpec(map_id, 0, len(actions)))
    required = {
        "experiment_id",
        "map_id",
        "world",
        "difficulty",
        "scenario_hash",
        "rule_hash",
        "prompt_hash",
        "metric_schema_hash",
        "commit",
        "model_id",
        "provider",
        "temperature",
        "seed",
        "replicate_id",
        "run_id",
        "condition_id",
        "decision_budget",
        "status",
        "success",
        "termination_reason",
        "agent_trace_path",
        "judge_metrics_path",
        "v8_metrics_path",
        "provider_error",
        "unknown_spend",
        "usage",
    }
    missing = sorted(required - set(manifest))
    gate.require(not missing, f"runner smoke manifest 缺少字段 {missing}")
    gate.require(manifest.get("status") == "success", "runner smoke 未成功")
    usage = manifest.get("usage") or {}
    gate.require(int(usage.get("requests", 0)) == len(actions), "runner smoke 请求数不符")
    gate.require(float(usage.get("cost", 0)) > 0, "runner smoke 成本未结算")
    trace = Path(manifest["agent_trace_path"]).read_text(encoding="utf-8").splitlines()
    gate.require(len(trace) == len(actions) + 1, "runner smoke trace 行数不符")
    v8_metrics = json.loads(Path(manifest["v8_metrics_path"]).read_text(encoding="utf-8"))
    gate.require(
        set(v8_metrics["metrics"]) == {spec.metric_id for spec in specs_for(map_id)},
        "runner smoke V8 metrics 不完整",
    )
    return {
        "run_id": manifest["run_id"],
        "status": manifest["status"],
        "requests": usage.get("requests"),
        "cost": usage.get("cost"),
        "ledger": ledger.snapshot(),
    }


def cost_dry_run(gate: Gate) -> dict[str, Any]:
    specs = registered_specs()
    requests = sum(spec.decision_budget for spec in specs)
    reserve = (
        MAX_INPUT_TOKENS_PER_REQUEST * 1 + MAX_OUTPUT_TOKENS_PER_REQUEST * 2
    ) / 1_000_000
    observed_mean = (900 * 1 + 120 * 2) / 1_000_000
    expected = requests * observed_mean
    gate.require(requests <= 4_200, "90 局请求上限超出账本登记")
    gate.require(expected <= float(MAX_COST_CNY), "按 900/120 token 预估费用超过 ¥10")
    return {
        "episodes": len(specs),
        "max_requests": requests,
        "reserve_cost_per_inflight_request": round(reserve, 8),
        "expected_cost_cny_at_900_120": round(expected, 6),
        "hard_cap_cny": str(MAX_COST_CNY),
    }


def main() -> int:
    gate = Gate()
    gate.require(len(MAP_IDS) == 30, "V8 地图不是 30 张")
    gate.require(set(CONDITIONS) <= set(MAP_IDS), "条件映射含未注册地图")
    for map_id in MAP_IDS:
        validate_map(gate, map_id)
    smoke = runner_smoke(gate)
    dry_run = cost_dry_run(gate)
    per_map_ok = sum(1 for row in gate.rows.values() if not row["problems"])
    payload = {
        "schema_version": "v8_offline_gate_v1",
        "map_count": len(MAP_IDS),
        "maps_ok": per_map_ok,
        "failure_count": len(gate.failures),
        "failures": gate.failures,
        "runner_smoke": smoke,
        "cost_dry_run": dry_run,
        "maps": gate.rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    for map_id in MAP_IDS:
        row = gate.rows.get(map_id, {})
        status = "OK" if not row.get("problems") else "FAIL"
        print(
            f"{map_id} {row.get('level', ''):<2} world={row.get('world', ''):<9}"
            f" metrics={row.get('metric_count', 0):>2} fixtures={len(row.get('fixtures', []))}"
            f" oracle={len(row.get('oracle_cases', []))} {status}"
        )
        for problem in row.get("problems", []):
            print("   -", problem)
    print("runner smoke:", json.dumps(smoke, ensure_ascii=False))
    print("cost dry-run:", json.dumps(dry_run, ensure_ascii=False))
    print()
    if gate.failures:
        print(f"OFFLINE GATE FAILED: {len(gate.failures)} 个问题")
        return 1
    print("V8 OFFLINE GATE: OK (30/30 maps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
