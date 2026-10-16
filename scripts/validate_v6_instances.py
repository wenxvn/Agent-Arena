"""Replay, verify, and manifest every V6 instance against the real environment.

Offline only: no provider is created and no paid API is called. Writes machine
readable manifests, Oracle traces, and solver results under the ignored
``runs/v6`` directory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v6.catalog import (  # noqa: E402
    build_environment,
    get_scene,
    instance_manifest,
)
from agent_arena.v6.scenes import all_scenes  # noqa: E402
from agent_arena.v6.solvers import solve  # noqa: E402
from agent_arena.worlds.scenario_v4 import ScenarioV4Action  # noqa: E402

OUTPUT_ROOT = ROOT / "runs" / "v6" / "instances"

# One illegal action per map that must be rejected without changing judge state.
_BOUNDARY_ACTIONS: dict[str, dict[str, Any]] = {
    "MAP-08": {"tool": "move", "edge_id": "NOT_AN_EDGE"},
    "MAP-16": {"tool": "set_route", "train_id": "a", "next_node": "NOWHERE"},
    "MAP-18": {"tool": "set_timetable", "tick": 99, "operations": {}},
    "MAP-22": {"tool": "move", "bearing": "UP"},
    "MAP-26": {"tool": "replace", "part_id": "not_a_part"},
    "MAP-30": {
        "tool": "formal_accuse",
        "person_id": "nobody",
        "event_claims": [],
        "cited_entry_ids": [],
    },
}


def _seeds(scene: Any) -> list[int]:
    if scene.map_id == "MAP-08":
        return sorted(scene.leak_by_seed)
    return [0]


def _replay(instance_id: str, condition_id: str, seed: int, actions: tuple[dict[str, Any], ...]):
    scene = get_scene(instance_id)
    environment = build_environment(scene, condition_id, seed=seed)
    observations = [environment.observe().model_dump(mode="json")]
    results: list[str] = []
    for payload in actions:
        action = ScenarioV4Action.model_validate(payload, strict=True)
        step = environment.step(action)
        results.append(step.result)
        observations.append(step.observation.model_dump(mode="json"))
    return environment, results, observations


def _write_instance(instance_id: str, seed: int, result: Any, state_hash: str) -> None:
    directory = OUTPUT_ROOT / instance_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "oracle_trace.json").write_text(
        json.dumps(list(result.actions), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (directory / "solver_result.json").write_text(
        json.dumps(
            {
                "instance_id": result.instance_id,
                "seed": seed,
                "optimum": result.optimum,
                "lower_bound": result.lower_bound,
                "note": result.note,
                "final_state_hash": state_hash,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    failures: list[str] = []
    checked = 0
    for instance_id, scene in sorted(all_scenes().items()):
        manifest = instance_manifest(scene)
        for seed in _seeds(scene):
            checked += 1
            condition = scene.paired_conditions[0]
            result = solve(instance_id, seed=seed)
            if not result.actions:
                failures.append(f"{instance_id} seed{seed}: solver produced no actions")
                continue
            environment, _, _ = _replay(instance_id, condition, seed, result.actions)
            if not environment.is_success:
                failures.append(
                    f"{instance_id} seed{seed}: oracle replay status {environment.status.value} "
                    f"reason {environment.terminal_reason}"
                )
                continue
            # Determinism: a second replay must match the first exactly.
            environment2, _, observations2 = _replay(instance_id, condition, seed, result.actions)
            _, _, observations1 = _replay(instance_id, condition, seed, result.actions)
            if (
                observations1 != observations2
                or environment.state_hash() != environment2.state_hash()
            ):
                failures.append(f"{instance_id} seed{seed}: replay is not deterministic")
                continue
            # Solver agreement for maps with a provable optimum.
            metrics = environment.metrics()
            if scene.map_id == "MAP-16" and result.optimum is not None:
                if metrics["makespan_ticks"] != result.optimum:
                    failures.append(
                        f"{instance_id}: makespan {metrics['makespan_ticks']} "
                        f"!= optimum {result.optimum}"
                    )
            if scene.map_id == "MAP-22" and result.optimum is not None:
                if metrics["movement_steps"] != result.optimum:
                    failures.append(
                        f"{instance_id}: movement {metrics['movement_steps']} "
                        f"!= optimum {result.optimum}"
                    )
            # Boundary: one illegal action must be rejected without a state change.
            boundary_env = build_environment(scene, condition, seed=seed)
            before = boundary_env.state_hash()
            boundary = ScenarioV4Action.model_validate(
                _BOUNDARY_ACTIONS[scene.map_id], strict=True
            )
            outcome = boundary_env.step(boundary)
            if boundary_env.status.value == "running" and boundary_env.state_hash() != before:
                failures.append(f"{instance_id}: a rejected action mutated the judge state")
            if not outcome.result.startswith(("INVALID", "TICK", "COURTROOM", "NO", "ACTION")):
                failures.append(
                    f"{instance_id}: boundary action returned unexpected result {outcome.result}"
                )
            # Terminal immutability.
            final_env, _, _ = _replay(instance_id, condition, seed, result.actions)
            terminal_hash = final_env.state_hash()
            final_env.step(ScenarioV4Action.model_validate(result.actions[-1], strict=True))
            if final_env.state_hash() != terminal_hash:
                failures.append(f"{instance_id}: terminal state mutated after termination")
            _write_instance(instance_id, seed, result, terminal_hash)
        (OUTPUT_ROOT / instance_id / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if failures:
        print("V6 instance validation FAILED:")
        for failure in failures:
            print(" -", failure)
        raise SystemExit(1)
    print(f"V6 instance validation passed: {checked} instance/seed oracle replays verified.")


if __name__ == "__main__":
    main()
