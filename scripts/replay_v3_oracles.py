"""Replay the offline V3 public-observation policies and write a compact audit."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from agent_arena.arena import ScenarioAction, ScenarioObservation, ScenarioStatus
from agent_arena.worlds.scenario.base import ScenarioEnvironment
from agent_arena.worlds.scenario.catalog import SCENARIO_REGISTRY
from agent_arena.worlds.scenario.oracle import public_oracle_action


def replay(world: str, version: str, seed: int, limit: int) -> dict[str, Any]:
    factory = SCENARIO_REGISTRY[(world, version)]
    environment = factory(world, seed)
    if not isinstance(environment, ScenarioEnvironment):
        raise TypeError(f"{world}/{version} is not a ScenarioEnvironment")
    observation = environment.reset(seed=seed)
    if not isinstance(observation, ScenarioObservation):
        raise TypeError("Scenario reset returned a non-scenario observation")

    events: list[str] = []
    tool_counts: Counter[str] = Counter()
    signature = sha256()
    rejected_actions = 0
    for _ in range(limit):
        before = observation
        action: ScenarioAction = public_oracle_action(before)
        result, observation = environment.step(action)
        tool_counts[action.tool] += 1
        rejected_actions += result.status.value == "rejected"
        event = environment.step_metadata.scenario_event
        if event:
            events.append(event)
        step = {
            "observation": before.model_dump(mode="json"),
            "action": action.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
            "next_observation": observation.model_dump(mode="json"),
            "event": event,
        }
        signature.update(
            json.dumps(step, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        if environment.terminal_status.status is not ScenarioStatus.RUNNING:
            break

    terminal = environment.terminal_status
    if terminal.status is not ScenarioStatus.SUCCESS:
        raise RuntimeError(
            f"{environment.scenario_id} ended as {terminal.status.value}: "
            f"{terminal.failure_reason or 'step limit reached'}"
        )
    if rejected_actions:
        raise RuntimeError(
            f"{environment.scenario_id} oracle had {rejected_actions} rejected actions"
        )
    return {
        "scenario_id": environment.scenario_id,
        "family": environment.family,
        "difficulty": environment.difficulty,
        "world": world,
        "world_version": version,
        "seed": seed,
        "actions": sum(tool_counts.values()),
        "tool_counts": dict(sorted(tool_counts.items())),
        "events": events,
        "status": terminal.status.value,
        "failure_reason": terminal.failure_reason,
        "score_components": environment.step_metadata.score_components,
        "definition_sha256": environment.definition_hash,
        "ruleset_sha256": environment.ruleset_sha,
        "replay_sha256": signature.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--step-limit", type=int, default=100)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/world-design-v3/oracle-acceptance.md"),
    )
    args = parser.parse_args()
    if args.step_limit < 1:
        parser.error("--step-limit must be positive")

    rows = [
        replay(world, version, args.seed, args.step_limit)
        for world, version in sorted(SCENARIO_REGISTRY)
    ]
    if len(rows) != 30 or len({row["scenario_id"] for row in rows}) != 30:
        raise RuntimeError("Expected exactly 30 unique V3 scenarios")

    lines = [
        "# V3 离线 Oracle 验收",
        "",
        f"- Replay seed：`{args.seed}`；单关上限：`{args.step_limit}` 个公开动作。",
        "- 每一步决策仅接收 `ScenarioObservation`；脚本在终止后读取公开终态和安全评分字段。",
        "- 30/30 完整成功，Oracle 拒绝动作 0。Replay hash 用于重播比对，不是模型结果。",
        "- 每条定义、规则集和动作回放均记录 SHA-256；Trace 不记录答案或隐藏状态。",
        "",
        "| ID | Group | Steps | Tools | Score | Definition hash | Rules hash | Replay hash |",
        "|---|---|---:|---|---|---|---|---|",
    ]
    for row in rows:
        counts = ", ".join(f"{tool}×{count}" for tool, count in row["tool_counts"].items())
        score = json.dumps(row["score_components"], ensure_ascii=False, sort_keys=True)
        lines.append(
            f"| {row['scenario_id']} | {row['family']} / {row['difficulty']} | "
            f"{row['actions']} | {counts} | `{score}` | `{row['definition_sha256']}` | "
            f"`{row['ruleset_sha256']}` | `{row['replay_sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## 重复性",
            "",
            "再次执行相同 seed 和规则版本时，每关 `Replay SHA-256` 应逐项一致。",
            "该回放用于核实脚本参考策略与公开动作接口，不证明真实 LLM 行为、最短解或统计显著性。",
            "",
        ]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.output}: {len(rows)}/30 scenario successes")


if __name__ == "__main__":
    main()
