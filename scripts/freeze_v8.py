"""冻结 V8 三十图的规则、prompt、指标与 Oracle 身份。

前置条件：`runs/v8/offline_gate.json` 必须为 30/30 通过。
输出：`runs/v8/freeze_manifest.json`。之后任何运行时文件变化都会使
`rule_hash` / `runtime_tree_hash` 不一致，必须重新冻结后才能正式运行。
"""

from __future__ import annotations

import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.config import RuntimeSettings  # noqa: E402
from agent_arena.v8.metrics import metric_schema_hash  # noqa: E402
from agent_arena.v8.prompts import system_prompt  # noqa: E402
from agent_arena.v8.runner import DECISION_BUDGETS  # noqa: E402
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
from agent_arena.worlds.scenario_v8.oracle import load_oracle_groups  # noqa: E402

GATE_PATH = ROOT / "runs" / "v8" / "offline_gate.json"
OUTPUT = ROOT / "runs" / "v8" / "freeze_manifest.json"
MODEL_NAME = "mimo-v2.6-flash"
ALLOWED_ENDPOINT = ("https", "api.xiaomimimo.com", "/v1")
V4_RUNTIME_MAPS = frozenset(CONDITIONS)


def _sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _git_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _oracle_payload(map_id: str) -> list[dict[str, Any]]:
    if map_id in V4_RUNTIME_MAPS:
        return [dict(case) for case in adapter_cases.oracle_cases(map_id)]
    module_name = f"agent_arena.worlds.scenario_v8.maps.map{map_id[-2:]}"
    module = __import__(module_name, fromlist=["ORACLE_CASES"])
    custom = getattr(module, "ORACLE_CASES", None)
    if custom:
        return [dict(case) for case in custom]
    return [
        {
            "trace_id": trace_id,
            "actions": [row["action"] for row in rows],
        }
        for trace_id, rows in load_oracle_groups(map_id).items()
    ]


def _tree_hash() -> str:
    roots = [
        ROOT / "src" / "agent_arena" / "v8",
        ROOT / "src" / "agent_arena" / "worlds" / "scenario_v8",
        ROOT / "scripts" / "run_v8_90.py",
        ROOT / "scripts" / "summarize_v8.py",
        ROOT / "scripts" / "freeze_v8.py",
        ROOT / "scripts" / "validate_v8_offline.py",
    ]
    digest = sha256()
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in files:
            if "__pycache__" in path.parts:
                continue
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    if gate.get("failure_count") != 0 or gate.get("maps_ok") != len(MAP_IDS):
        raise SystemExit("离线门禁未通过，禁止冻结。")

    configured = RuntimeSettings.load(env_file=ROOT / ".env")
    if configured.provider != "openai" or configured.model_name != MODEL_NAME:
        raise SystemExit("本地 provider/model 与 V8 预登记的 MiMo 不一致。")
    if configured.base_url is None:
        raise SystemExit("缺少 MiMo endpoint 配置。")

    commit = _git_commit()
    dirty = _git_dirty()
    maps: dict[str, Any] = {}
    for map_id in MAP_IDS:
        level = LEVEL_OF[map_id]
        budget = DECISION_BUDGETS[level]
        environment = create_environment(map_id, step_limit=160)
        prompt = system_prompt(environment, decision_budget=budget)
        oracle = _oracle_payload(map_id)
        maps[map_id] = {
            "world": WORLD_OF[map_id],
            "difficulty": level,
            "condition_id": CONDITIONS.get(map_id, "default"),
            "decision_budget": budget,
            "step_limit": 160,
            "scenario_hash": scenario_hash(map_id),
            "rule_hash": rule_hash(map_id),
            "source_hash": source_hash(map_id),
            "prompt_hash": _sha256(prompt.encode()),
            "metric_schema_hash": metric_schema_hash(map_id),
            "oracle_hash": _sha256(_canonical(oracle)),
            "oracle_case_count": len(oracle),
            "commit": commit,
        }

    payload = {
        "schema_version": "v8_freeze_manifest_v1",
        "stage": "formal_freeze",
        "model_id": MODEL_NAME,
        "provider": "openai",
        "endpoint_host": "api.xiaomimimo.com",
        "endpoint_path": "/v1",
        "temperature": 0,
        "seed": 0,
        "replicate_ids": [0, 1, 2],
        "decision_budgets": DECISION_BUDGETS,
        "step_limit": 160,
        "currency": "CNY",
        "max_cost": "10",
        "commit": commit,
        "tree_dirty_before_freeze": dirty,
        "runtime_tree_hash": _tree_hash(),
        "offline_gate": {
            "maps_ok": gate["maps_ok"],
            "failure_count": gate["failure_count"],
            "expected_cost_cny_at_900_120": gate["cost_dry_run"]["expected_cost_cny_at_900_120"],
        },
        "maps": maps,
    }
    payload["freeze_hash"] = _sha256(_canonical(payload))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"commit={commit} dirty={dirty}")
    print(f"runtime_tree_hash={payload['runtime_tree_hash']}")
    print(f"freeze_hash={payload['freeze_hash']}")
    print(f"maps={len(maps)} output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
