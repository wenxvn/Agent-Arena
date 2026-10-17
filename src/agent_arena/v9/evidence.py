"""V9 每图证据包：把 3 条 V8 正式 Trace 压缩成可复核的逐决策事件表。

压缩规则：
- 保留初始 Observation；
- 每个决策只保留动作、结果码、`invalid_output_reason` 与 Observation 的变化字段；
- 保留 judge 指标、失败码、终止原因与 usage；
- 不写入任何隐藏 judge_state。

输出：``runs/v9/evidence/MAP-XX.json``。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_arena.v7.metrics.registry import specs_for
from agent_arena.v8.prompts import action_contract, map_docstring, vocabulary
from agent_arena.v9.audit import REPO_ROOT, V9_ROOT, official_rows
from agent_arena.worlds.scenario_v8.catalog import (
    CONDITIONS,
    LEVEL_OF,
    MAP_IDS,
    WORLD_OF,
    create_environment,
)

_DIFF_SKIP = {"last_action_result"}


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for key, value in after.items():
        if key in _DIFF_SKIP:
            continue
        if before.get(key) != value:
            changed[key] = value
    removed = [key for key in before if key not in after]
    if removed:
        changed["_removed"] = removed
    return changed


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _compact_action(action: dict[str, Any] | None) -> dict[str, Any] | None:
    if not action:
        return action
    keep = {
        key: value
        for key, value in action.items()
        if value is not None and key in {
            "tool",
            "edge_id",
            "to",
            "bearing",
            "target",
            "target_id",
            "operation",
            "item_id",
            "part_id",
            "choice",
            "tick",
            "station",
            "train_id",
            "section_id",
            "next_node",
            "from_node",
            "to_node",
            "day",
            "slot",
            "turns",
            "ticks",
            "quantity",
            "sample_id",
            "device_id",
            "clue_id",
            "entrance",
            "question_template_id",
            "answer",
            "rule_id",
            "record_id",
            "npc_id",
            "topic_id",
            "person_id",
            "candidate_person",
            "confidence",
            "entry_id",
            "evidence_id",
            "evidence_ids",
            "entry_ids",
            "statement_ids",
            "support_ids",
            "against_evidence_ids",
            "unreliability_proof_ids",
            "cited_entry_ids",
            "event_ids_known",
            "event_time",
            "event_location",
            "unreliable_npc_id",
            "layout_by_room",
            "configuration",
            "forecast_next",
            "set_cooling",
            "set_flow_tenths",
            "adjust_loads",
            "open_bypasses",
            "arguments",
            "operations",
            "claims",
            "event_claims",
            "citations_by_claim",
            "slots",
            "crop",
            "commodity",
            "plan",
            "cost_choice",
            "reinforced",
            "loaded_return",
            "facts",
            "value",
            "witness_id",
            "diagnosis_code",
            "tool_ids",
            "claim_id",
            "room",
            "slot_index",
            "area",
        }
    }
    for key, value in list(keep.items()):
        text = json.dumps(value, ensure_ascii=False)
        if len(text) > 400:
            keep[key] = text[:400] + "…"
    return keep


def _metric_specs(map_id: str) -> list[dict[str, Any]]:
    return [
        {
            "metric_id": spec.metric_id,
            "kind": spec.kind.value,
            "unit": spec.unit,
            "direction": spec.direction.value,
            "formula": spec.formula,
            "denominator": spec.denominator,
            "valid_range": list(spec.valid_range) if spec.valid_range else None,
            "missing_rule": spec.missing_rule,
        }
        for spec in specs_for(map_id)
    ]


def build_map_pack(map_id: str, rows: list[Any]) -> dict[str, Any]:
    environment = create_environment(map_id)
    runs: list[dict[str, Any]] = []
    for row in rows:
        trace_path = Path(row.agent_trace_path)
        trace = _read_jsonl(trace_path)
        header = trace[0]
        decisions = [item for item in trace[1:] if item.get("event") == "decision"]
        judge = json.loads(Path(row.judge_metrics_path).read_text(encoding="utf-8"))
        metrics = json.loads(Path(row.v8_metrics_path).read_text(encoding="utf-8"))
        steps: list[dict[str, Any]] = []
        for item in decisions:
            steps.append(
                {
                    "i": item.get("decision_index"),
                    "action": _compact_action(item.get("action")),
                    "result": item.get("result"),
                    "invalid_reason": item.get("invalid_output_reason"),
                    "delta": _diff(
                        item.get("observation_before") or {},
                        item.get("observation_after") or {},
                    ),
                }
            )
        runs.append(
            {
                "run_id": row.run_id,
                "replicate_id": row.replicate_id,
                "status": row.status,
                "success": row.success,
                "termination_reason": row.termination_reason,
                "decision_budget": row.decision_budget,
                "decision_rows": len(decisions),
                "failure_codes": judge.get("failure_codes"),
                "invalid_action_count": judge.get("invalid_action_count"),
                "judge_metrics": judge.get("metrics"),
                "projected_metrics": {
                    metric_id: value.get("value")
                    for metric_id, value in (metrics.get("metrics") or {}).items()
                },
                "metric_statuses": {
                    metric_id: value.get("status")
                    for metric_id, value in (metrics.get("metrics") or {}).items()
                },
                "usage": judge.get("usage"),
                "initial_observation": decisions[0]["observation_before"] if decisions else None,
                "final_observation": decisions[-1]["observation_after"] if decisions else None,
                "steps": steps,
                "prompt_hash": header.get("prompt_hash"),
                "commit": header.get("commit"),
            }
        )
    return {
        "map_id": map_id,
        "world": WORLD_OF[map_id],
        "difficulty": LEVEL_OF[map_id],
        "condition_id": CONDITIONS.get(map_id, "default"),
        "title": environment.title,
        "docstring": map_docstring(environment),
        "public_fields": sorted(environment.PUBLIC_FIELDS),
        "action_shapes": {
            tool: [sorted(shape) for shape in sorted(shapes, key=lambda item: sorted(item))]
            for tool, shapes in sorted(environment.SHAPES.items())
        },
        "action_contract": action_contract(environment),
        "vocabulary": vocabulary(environment),
        "metric_specs": _metric_specs(map_id),
        "runs": runs,
    }


def build() -> dict[str, Any]:
    rows = official_rows()
    output = V9_ROOT / "evidence"
    output.mkdir(parents=True, exist_ok=True)
    index: dict[str, Any] = {}
    for map_id in MAP_IDS:
        map_rows = [row for row in rows if row.map_id == map_id]
        pack = build_map_pack(
            map_id,
            [row for row in rows if row.map_id == map_id],
        )
        path = output / f"{map_id}.json"
        path.write_text(
            json.dumps(pack, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        index[map_id] = {
            "path": str(path.relative_to(REPO_ROOT)),
            "runs": [row.run_id for row in map_rows],
            "steps": [len(pack_run["steps"]) for pack_run in pack["runs"]],
            "successes": sum(1 for row in map_rows if row.success),
            "statuses": [row.status for row in map_rows],
        }
    (output / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return index


def main() -> None:
    index = build()
    print(json.dumps({key: value["steps"] for key, value in index.items()}, indent=2))
    print(f"maps={len(index)} official_runs={len({row.run_id for row in official_rows()})}")
    print(f"episodes={len(list((V9_ROOT / 'evidence').glob('MAP-*.json')))}")


if __name__ == "__main__":
    main()
