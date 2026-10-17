"""运行 V9 三类公开基线并写出可复算记录。

用法：
    python -m agent_arena.v9.baseline_run                 # 全部地图
    python -m agent_arena.v9.baseline_run MAP-01 MAP-02   # 指定地图

输出：``runs/v9/baselines/MAP-XX.json``（Oracle、random、heuristic、ablations）
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from agent_arena.v8.prompts import _VOCABULARY
from agent_arena.v9.audit import REPO_ROOT, V9_ROOT
from agent_arena.v9.baselines import RandomPolicy, ShapeSampler, run_policy
from agent_arena.v9.policies import ablations, heuristics
from agent_arena.worlds.scenario_v8.catalog import (
    CONDITIONS,
    LEVEL_OF,
    MAP_IDS,
    WORLD_OF,
    create_environment,
)
from agent_arena.worlds.scenario_v8.models import V8Action
from agent_arena.worlds.scenario_v8.oracle import (
    load_oracle_groups,
    normalize_action_payload,
)

BUDGETS = {"简单": 30, "中等": 38, "困难": 46}
RANDOM_SEEDS = tuple(range(20))


def decision_budget(map_id: str) -> int:
    if map_id == "MAP-12":
        return 60
    return BUDGETS[LEVEL_OF[map_id]]


def oracle_cases(map_id: str) -> list[dict[str, Any]]:
    """与 V8 离线门禁相同的 Oracle 来源，而不是通用 jsonl 回放。"""

    if map_id in {"MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30"}:
        from agent_arena.worlds.scenario_v8 import adapter_cases

        return [dict(case) for case in adapter_cases.oracle_cases(map_id)]
    module = importlib.import_module(
        f"agent_arena.worlds.scenario_v8.maps.map{map_id[-2:]}"
    )
    custom = getattr(module, "ORACLE_CASES", None)
    if custom:
        return [dict(case) for case in custom]
    return [
        {"trace_id": trace_id, "seed": 0, "actions": actions, "expect_success": True}
        for trace_id, actions in _jsonl_actions(map_id).items()
    ]


def _jsonl_actions(map_id: str) -> dict[str, list[dict[str, Any]]]:
    groups = load_oracle_groups(map_id)
    result: dict[str, list[dict[str, Any]]] = {}
    for trace_id, rows in groups.items():
        actions = []
        for row in rows:
            payload = row.get("action") or row.get("actions")
            if isinstance(payload, dict):
                actions.append(normalize_action_payload(payload))
            elif isinstance(payload, list):
                actions.extend(
                    normalize_action_payload(item)
                    for item in payload
                    if isinstance(item, dict)
                )
        result[trace_id] = actions
    return result


def oracle_records(map_id: str) -> list[dict[str, Any]]:
    records = []
    for case in oracle_cases(map_id):
        environment = create_environment(map_id, seed=int(case.get("seed", 0)))
        failures: list[str] = []
        actions = case.get("actions") or []
        for index, payload in enumerate(actions, 1):
            try:
                action = V8Action.model_validate(
                    normalize_action_payload(payload), strict=True
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(f"action {index}: {type(exc).__name__}")
                break
            result = environment.step(action)
            if environment.is_terminal and index < len(actions):
                failures.append(f"action {index}: terminal early ({result.result})")
                break
        if case.get("expect_success", True) and not environment.is_success:
            failures.append(
                f"oracle not successful: {environment.status.value}/{environment.terminal_reason}"
            )
        records.append(
            {
                "trace_id": case.get("trace_id"),
                "actions": len(actions),
                "status": environment.status.value,
                "terminal_reason": environment.terminal_reason,
                "failures": failures,
                "ok": not failures,
            }
        )
    return records


def random_records(map_id: str) -> list[dict[str, Any]]:
    environment = create_environment(map_id)
    sampler = ShapeSampler.from_environment(environment, _VOCABULARY)
    records = []
    for policy_seed in RANDOM_SEEDS:
        policy = RandomPolicy(sampler, seed=policy_seed)
        run = run_policy(
            map_id,
            policy,
            seed=0,
            policy_seed=policy_seed,
            decision_budget=decision_budget(map_id),
            condition_id=CONDITIONS.get(map_id),
        )
        records.append(run.as_dict())
    return records


def heuristic_records(map_id: str) -> dict[str, Any] | None:
    factory = heuristics().get(map_id)
    if factory is None:
        return None
    try:
        run = run_policy(
            map_id,
            factory(),
            seed=0,
            decision_budget=decision_budget(map_id),
            condition_id=CONDITIONS.get(map_id),
        )
    except Exception as exc:  # noqa: BLE001 - policy bugs are recorded, not hidden
        return {
            "map_id": map_id,
            "policy": "public_heuristic",
            "error": f"{type(exc).__name__}: {exc}",
            "success": False,
            "status": "policy_error",
        }
    return run.as_dict()


def ablation_records(map_id: str) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for name, factory in ablations().get(map_id, {}).items():
        try:
            run = run_policy(
                map_id,
                factory(),
                seed=0,
                decision_budget=decision_budget(map_id),
                condition_id=CONDITIONS.get(map_id),
            )
        except Exception as exc:  # noqa: BLE001
            records[name] = {
                "map_id": map_id,
                "policy": name,
                "error": f"{type(exc).__name__}: {exc}",
                "success": False,
                "status": "policy_error",
            }
            continue
        records[name] = run.as_dict()
    return records


def build(map_ids: list[str]) -> dict[str, Any]:
    output = V9_ROOT / "baselines"
    output.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {}
    for map_id in map_ids:
        payload: dict[str, Any] = {
            "map_id": map_id,
            "world": WORLD_OF[map_id],
            "difficulty": LEVEL_OF[map_id],
            "condition_id": CONDITIONS.get(map_id, "default"),
            "decision_budget": decision_budget(map_id),
            "oracle": oracle_records(map_id),
            "legal_random": random_records(map_id),
            "public_heuristic": heuristic_records(map_id),
            "ablations": ablation_records(map_id),
        }
        path = output / f"{map_id}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        summary[map_id] = {
            "oracle_ok": sum(1 for item in payload["oracle"] if item["ok"]),
            "oracle_cases": len(payload["oracle"]),
            "random_success": sum(
                1 for item in payload["legal_random"] if item["success"]
            ),
            "random_invalid_actions": sum(
                item["invalid_actions"] for item in payload["legal_random"]
            ),
            "random_rejected_actions": sum(
                item["rejected_actions"] for item in payload["legal_random"]
            ),
            "heuristic_present": payload["public_heuristic"] is not None,
            "heuristic_success": bool(
                payload["public_heuristic"] and payload["public_heuristic"]["success"]
            ),
            "heuristic_terminal": (
                payload["public_heuristic"] or {}
            ).get("terminal_reason"),
            "ablations": {
                name: bool(record["success"])
                for name, record in payload["ablations"].items()
            },
        }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    map_ids = [item for item in args if item in MAP_IDS] or list(MAP_IDS)
    summary = build(map_ids)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"output={Path(REPO_ROOT) / 'runs' / 'v9' / 'baselines'}")


if __name__ == "__main__":
    main()
