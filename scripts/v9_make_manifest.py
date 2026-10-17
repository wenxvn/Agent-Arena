"""生成 V9 MiMo 有界验证的预登记 manifest（含 runtime hash 与 manifest hash）。"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v8.metrics import metric_schema_hash  # noqa: E402
from agent_arena.v9.prompts import prompt_hashes  # noqa: E402
from agent_arena.worlds.scenario_v8.catalog import (  # noqa: E402
    LEVEL_OF,
    create_environment,
    rule_hash,
    scenario_hash,
    source_hash,
)

BUDGETS = {"简单": 30, "中等": 38, "困难": 46}
OUTPUT = ROOT / "docs" / "v9" / "mimo-preregistration.json"


def budget(map_id: str) -> int:
    if map_id == "MAP-12":
        return 60
    return BUDGETS[LEVEL_OF[map_id]]


def episode(
    map_id: str,
    replicate: int,
    arm: str,
    hypothesis: str,
    seed: int = 0,
) -> dict[str, Any]:
    return {
        "map_id": map_id,
        "replicate_id": replicate,
        "decision_budget": budget(map_id),
        "arm": arm,
        "hypothesis": hypothesis,
        "seed": seed,
    }


def episodes() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    fixed_primary = {
        "MAP-09": "补公开短路阈值后，封舱窗口可被理性选择，0/3 应至少出现一次存活/成功。",
        "MAP-10": "补公开燃料分仓后，失败应从'未装载'转为资源规划/路径选择错误。",
        "MAP-11": "补公开补给消耗后，首段移动不再因未知规则必死，救援链应被触发。",
        "MAP-12": "补公开 transfer 边后，维修链可执行，研究分应成为主要失败点。",
    }
    for map_id, hypothesis in fixed_primary.items():
        for arm in ("v8_compat", "v9_fixed"):
            for replicate in range(2):
                items.append(episode(map_id, replicate, arm, hypothesis))
    fixed_secondary = {
        "MAP-07": "公开 control_panel 后，阀门操作是否真正发生（区分接口与预判）。",
        "MAP-08": "公开复合边名与 inspect 目标后，诊断链是否启动。",
        "MAP-26": "公开 log/test/part 枚举后，诊断→修复→重启是否可执行。",
    }
    for map_id, hypothesis in fixed_secondary.items():
        for arm in ("v8_compat", "v9_fixed"):
            items.append(episode(map_id, 0, arm, hypothesis))
    floors = {
        "MAP-14": "3 锁盲交 5 步是否仍能通关（检验 CONSTRUCT_BYPASS 的重复性）。",
        "MAP-18": "12 决策硬上限与窗口旁路是否稳定复现（D/CONSTRUCT 证据）。",
        "MAP-22": "公开记忆 schema 下 30 决策是否仍不足（B/D 边界）。",
        "MAP-29": "补齐比对/提交语义后，证词分诊是否仍为 0。",
    }
    for map_id, hypothesis in floors.items():
        items.append(episode(map_id, 0, "v9_fixed", hypothesis))
    bypass = [
        ("MAP-06", 5, "seed=5 长风暴下，直达修复是否按设计失败（检验 seed 0 旁路）。"),
        ("MAP-15", 0, "goal 仍泄露规则时，短策略是否继续 100% 通关（基线重复）。"),
        ("MAP-21", 0, "直达 O_E 是否继续 1 决策通关（旁路重复）。"),
    ]
    for map_id, seed, hypothesis in bypass:
        items.append(episode(map_id, 0, "v9_fixed", hypothesis, seed=seed))
    return items


def runtime_hashes(map_ids: set[str]) -> dict[str, Any]:
    hashes: dict[str, Any] = {}
    for map_id in sorted(map_ids):
        environment = create_environment(map_id)
        limit = budget(map_id)
        hashes[map_id] = {
            "scenario_hash": scenario_hash(map_id),
            "rule_hash": rule_hash(map_id),
            "source_hash": source_hash(map_id),
            "metric_schema_hash": metric_schema_hash(map_id),
            **prompt_hashes(environment, decision_budget=limit),
        }
    return hashes


def build() -> dict[str, Any]:
    items = episodes()
    manifest: dict[str, Any] = {
        "experiment_label": "V9-PILOT-001",
        "created_at": datetime.now(UTC).isoformat(),
        "commit": "35e37117e890c8e165a708d89204a01cf1801466",
        "model": "mimo-v2.6-flash",
        "provider": "openai",
        "temperature": 0,
        "budget_cny": "10",
        "max_episodes": len(items),
        "stop_rules": {
            "unknown_spend": "立即封账并停止全部后续请求",
            "consecutive_provider_errors": 3,
            "global_cost": "¥10 硬上限；请求前预留",
            "retry": "仅确认未计费的 provider_error 重试一次，新 run_id",
        },
        "analysis_plan": {
            "primary": "同图同实例、同模型、同预算的 v8_compat vs v9_fixed 描述性对照",
            "n": "每条件 2 次重复；floors/bypass 各 1 次；不做显著性断言",
            "metrics": "V8 旧指标 + V9 overlay（censored 投影、map12 研究分等）并列",
        },
        "episodes": items,
        "runtime_hashes": runtime_hashes({item["map_id"] for item in items}),
        "decision_budgets": {item["map_id"]: item["decision_budget"] for item in items},
    }
    payload = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    manifest["manifest_hash"] = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return manifest


def main() -> None:
    manifest = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)
    print(f"episodes={len(manifest['episodes'])}")
    print(f"manifest_hash={manifest['manifest_hash']}")
    print(f"maps={sorted({item['map_id'] for item in manifest['episodes']})}")


if __name__ == "__main__":
    main()
