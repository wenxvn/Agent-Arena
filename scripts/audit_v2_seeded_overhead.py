"""Analyze seeded V2 long-tail traces and generator instance coverage."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from copy import deepcopy
from heapq import heappop, heappush
from itertools import count
from pathlib import Path
from typing import Any

from agent_arena.arena.models import ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.flex import (
    FlexEnvironment,
    FlexSeededDefinition,
    build_seeded_items,
    load_lunar_v2_seeded_definition,
    load_pyramid_v2_seeded_definition,
)

WORLD_SELECTORS = {
    "lunar-escape-v2-seeded-zh": "lunar-escape",
    "pyramid-escape-v2-seeded-zh": "pyramid-escape",
}
PHASE_REASONS = {"panel_closed", "code_unread"}
TRACE_FIELDS = (
    "episode_id",
    "experiment_bucket",
    "world_version",
    "world_definition_id",
    "seed",
    "trace_world_definition_hash",
    "stable_world_definition_hash",
    "stable_hash_matches_trace",
    "observed_item_layout_matches_seed",
    "recorded_actions",
    "minimum_actions",
    "action_overhead",
    "minimum_action_route_moves",
    "observed_move_actions",
    "move_action_delta",
    "tool_room_entry_counts",
    "tool_room_returns_after_first_visit",
    "look_actions",
    "repeated_look_actions",
    "rejected_actions",
    "phase_rejections",
    "repeated_failed_action_retries",
    "states_expanded",
)
COVERAGE_FIELDS = (
    "world_version",
    "seed_range",
    "seed_population",
    "distinct_layouts",
    "representative_seed",
    "seeds_with_layout",
    "stable_world_definition_hash",
    "tool_layout",
    "minimum_actions",
    "minimum_action_route_moves",
    "states_expanded",
    "difficulty_label_declared",
)
SEEDED_DEFINITIONS = {
    "lunar-escape-v2-seeded-zh": load_lunar_v2_seeded_definition,
    "pyramid-escape-v2-seeded-zh": load_pyramid_v2_seeded_definition,
}


def _state_key(environment: FlexEnvironment) -> tuple[Any, ...]:
    state = environment._state
    return (
        state.seed,
        state.current_room,
        tuple(sorted(state.inventory)),
        tuple(sorted(state.revealed_items)),
        tuple(sorted(state.blocked_objects)),
        state.reactor_panel_open,
        state.main_power,
        state.authorization_code_read,
        state.control_terminal_blocked,
        state.escaped,
        tuple(sorted(environment._open_panels)),
        tuple(sorted(environment._done_cells)),
    )


def _candidate_actions(environment: FlexEnvironment) -> list[dict[str, str]]:
    observation = environment.observe()
    actions = [
        {"tool": "move", "destination": destination}
        for destination in observation.available_exits
    ]
    actions.extend(
        {"tool": "inspect", "target": target}
        for target in observation.visible_objects
    )
    actions.extend({"tool": "pickup", "item": item_id} for item_id in environment._items)

    item_ids = [*environment._items, environment.definition.authorization_code]
    target_ids = [
        *environment._panels,
        *environment._cells,
        environment.definition.escape_vehicle,
    ]
    actions.extend(
        {"tool": "use", "item": item_id, "target": target_id}
        for item_id in item_ids
        for target_id in target_ids
    )
    actions.append(
        {"tool": "read_terminal", "target": environment.definition.code_terminal}
    )
    return actions


def _minimum_route(
    initial_environment: FlexEnvironment,
) -> tuple[int, int, int]:
    """Return min actions, min moves among such routes, and expanded states."""
    start_key = _state_key(initial_environment)
    serial = count()
    queue: list[tuple[int, int, int, tuple[Any, ...]]] = []
    heappush(queue, (0, 0, next(serial), start_key))
    best_cost: dict[tuple[Any, ...], tuple[int, int]] = {start_key: (0, 0)}
    environments = {start_key: deepcopy(initial_environment)}
    expanded = 0

    while queue:
        actions_so_far, moves_so_far, _, current_key = heappop(queue)
        cost = (actions_so_far, moves_so_far)
        if cost != best_cost.get(current_key):
            continue
        current = environments[current_key]
        if current.is_success():
            return actions_so_far, moves_so_far, expanded

        expanded += 1
        for payload in _candidate_actions(current):
            next_environment = deepcopy(current)
            result, _ = next_environment.step(action_adapter.validate_python(payload))
            next_key = _state_key(next_environment)
            if next_key == current_key:
                continue

            next_cost = (
                actions_so_far + 1,
                moves_so_far + int(payload["tool"] == "move"),
            )
            if next_cost >= best_cost.get(next_key, (10**9, 10**9)):
                continue
            best_cost[next_key] = next_cost
            environments[next_key] = next_environment
            heappush(queue, (*next_cost, next(serial), next_key))

    raise ValueError(f"no successful route for {initial_environment.identity[1]}")


def _item_layout_evidence(
    trace: dict[str, Any], environment: FlexEnvironment
) -> tuple[bool, dict[str, str]]:
    expected = {item.id: item.container_id for item in environment.definition.items}
    observed: dict[str, str] = {}
    object_by_id = {item.id: item for item in environment.definition.objects}
    pickup_mismatches = 0

    for step in trace["steps"]:
        action = step.get("action", {})
        result = step.get("result", {})
        if not isinstance(action, dict) or not isinstance(result, dict):
            continue
        if (
            action.get("tool") == "inspect"
            and action.get("target") in environment.definition.containers
            and result.get("status") == ToolStatus.SUCCESS.value
        ):
            next_observation = step.get("next_observation", {})
            visible = set(next_observation.get("visible_objects", ()))
            container_id = action["target"]
            for item_id in expected:
                if item_id in visible:
                    observed[item_id] = container_id

        if action.get("tool") == "pickup" and result.get("status") == ToolStatus.SUCCESS.value:
            picked_item_id = action.get("item")
            observation = step.get("observation", {})
            item = next(
                (
                    entry
                    for entry in environment.definition.items
                    if entry.id == picked_item_id
                ),
                None,
            )
            container = object_by_id.get(item.container_id) if item is not None else None
            if container is None or observation.get("current_room") != container.room_id:
                pickup_mismatches += 1

    return observed == expected and pickup_mismatches == 0, observed


def _trace_metrics(
    row: dict[str, str], trace: dict[str, Any], environment: FlexEnvironment
) -> dict[str, Any]:
    minimum_actions, minimum_moves, states_expanded = _minimum_route(environment)
    definition = environment.definition
    expected_layout = {item.id: item.container_id for item in definition.items}
    layout_matches, observed_layout = _item_layout_evidence(trace, environment)
    if not layout_matches:
        raise ValueError(
            f"seeded item layout is not fully corroborated by trace {row['episode_id']}: "
            f"observed={observed_layout!r}, expected={expected_layout!r}"
        )

    steps = trace["steps"]
    observed_moves = sum(step.get("action", {}).get("tool") == "move" for step in steps)
    look_actions = sum(step.get("action", {}).get("tool") == "look" for step in steps)
    rejected = [
        step
        for step in steps
        if step.get("result", {}).get("status") == ToolStatus.REJECTED.value
    ]
    repeated_failures: Counter[tuple[str, str]] = Counter()
    phase_rejections = 0
    for step in rejected:
        action = step.get("action", {})
        result = step.get("result", {})
        reason = result.get("reason", "")
        action_key = json.dumps(action, ensure_ascii=False, sort_keys=True)
        repeated_failures[(action_key, reason)] += 1
        if reason in PHASE_REASONS or (
            reason == "no_power"
            and (
                (
                    action.get("tool") == "read_terminal"
                    and action.get("target") == definition.code_terminal
                )
                or (
                    action.get("tool") == "use"
                    and action.get("target") == definition.escape_vehicle
                )
            )
        ):
            phase_rejections += 1

    container_rooms = {
        next(obj.room_id for obj in definition.objects if obj.id == container_id)
        for container_id in expected_layout.values()
    }
    room_entries: Counter[str] = Counter()
    if definition.start_room in container_rooms:
        room_entries[definition.start_room] += 1
    for step in steps:
        if (
            step.get("action", {}).get("tool") == "move"
            and step.get("result", {}).get("status") == ToolStatus.SUCCESS.value
        ):
            room = step.get("next_observation", {}).get("current_room")
            if room in container_rooms:
                room_entries[room] += 1
    room_returns = sum(max(visits - 1, 0) for visits in room_entries.values())
    action_count = len(steps)
    if action_count != int(row["recorded_action_count"]):
        raise ValueError(f"action count mismatch for {row['episode_id']}")
    if action_count < minimum_actions:
        raise ValueError(f"trace beats computed minimum for {row['episode_id']}")

    return {
        "episode_id": row["episode_id"],
        "experiment_bucket": row["experiment_bucket"],
        "world_version": row["world_version"],
        "world_definition_id": row["world_definition_id"],
        "seed": row["seed"],
        "trace_world_definition_hash": row["world_definition_hash"],
        "stable_world_definition_hash": environment.identity[3],
        "stable_hash_matches_trace": str(
            row["world_definition_hash"] == environment.identity[3]
        ).lower(),
        "observed_item_layout_matches_seed": str(layout_matches).lower(),
        "recorded_actions": action_count,
        "minimum_actions": minimum_actions,
        "action_overhead": action_count - minimum_actions,
        "minimum_action_route_moves": minimum_moves,
        "observed_move_actions": observed_moves,
        "move_action_delta": observed_moves - minimum_moves,
        "tool_room_entry_counts": json.dumps(
            dict(sorted(room_entries.items())), ensure_ascii=False
        ),
        "tool_room_returns_after_first_visit": room_returns,
        "look_actions": look_actions,
        "repeated_look_actions": row.get("repeated_look_actions", ""),
        "rejected_actions": len(rejected),
        "phase_rejections": phase_rejections,
        "repeated_failed_action_retries": sum(
            occurrences - 1 for occurrences in repeated_failures.values() if occurrences > 1
        ),
        "states_expanded": states_expanded,
    }


def _layout_coverage(seed_population: int) -> list[dict[str, Any]]:
    coverage: list[dict[str, Any]] = []
    for version, loader in SEEDED_DEFINITIONS.items():
        definition: FlexSeededDefinition = loader()
        seeds_by_layout: dict[tuple[tuple[str, str], ...], list[int]] = {}
        for seed in range(seed_population):
            items = build_seeded_items(definition, seed)
            layout = tuple((item.id, item.container_id) for item in items)
            repeated_layout = tuple(
                (item.id, item.container_id)
                for item in build_seeded_items(definition, seed)
            )
            if layout != repeated_layout:
                raise ValueError(f"same-seed layout changed for {version} seed {seed}")
            seeds_by_layout.setdefault(layout, []).append(seed)

        hashes_seen: set[str] = set()
        distinct_layouts = len(seeds_by_layout)
        for layout, seeds in sorted(seeds_by_layout.items()):
            representative_seed = seeds[0]
            placed = definition.model_copy(
                update={"items": build_seeded_items(definition, representative_seed)}
            )
            environment = FlexEnvironment(placed, representative_seed)
            if environment.identity[1] != version:
                raise ValueError(f"version mismatch while scoring {version}")
            instance_hash = environment.identity[3]
            if instance_hash in hashes_seen:
                raise ValueError(f"different layouts share a hash for {version}")
            hashes_seen.add(instance_hash)
            minimum_actions, minimum_moves, states_expanded = _minimum_route(environment)
            coverage.append(
                {
                    "world_version": version,
                    "seed_range": f"0-{seed_population - 1}",
                    "seed_population": seed_population,
                    "distinct_layouts": distinct_layouts,
                    "representative_seed": representative_seed,
                    "seeds_with_layout": len(seeds),
                    "stable_world_definition_hash": instance_hash,
                    "tool_layout": json.dumps(
                        dict(layout), ensure_ascii=False, sort_keys=True
                    ),
                    "minimum_actions": minimum_actions,
                    "minimum_action_route_moves": minimum_moves,
                    "states_expanded": states_expanded,
                    "difficulty_label_declared": "false",
                }
            )
        if len(hashes_seen) != distinct_layouts:
            raise ValueError(f"layout/hash coverage mismatch for {version}")
    return coverage


def main() -> None:
    parser = argparse.ArgumentParser(
        description="分解 seeded Trace 行为开销并盘点 lunar/pyramid 布局覆盖"
    )
    parser.add_argument(
        "--input", type=Path, default=Path("docs/research/v2/assets/trace-audit.csv")
    )
    parser.add_argument("--trace-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path, default=Path("docs/research/v2/assets/seeded-overhead.csv")
    )
    parser.add_argument("--coverage-seeds", type=int, default=1000)
    parser.add_argument(
        "--coverage-output",
        type=Path,
        default=Path("docs/research/v2/assets/seeded-layout-coverage.csv"),
    )
    args = parser.parse_args()
    if args.coverage_seeds < 1:
        parser.error("--coverage-seeds must be positive")

    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    output_rows: list[dict[str, Any]] = []
    for row in source_rows:
        version = row.get("world_version", "")
        if version not in WORLD_SELECTORS or row.get("outcome") != "success":
            continue
        if row.get("seed_role") != "seeded_instance":
            raise ValueError(f"unexpected seed role for {row['episode_id']}")

        environment = create_environment(
            WORLD_SELECTORS[version], version, seed=int(row["seed"])
        )
        if not isinstance(environment, FlexEnvironment):
            raise TypeError(f"{version} did not resolve to FlexEnvironment")
        if environment.identity[1:3] != (version, row["world_definition_id"]):
            raise ValueError(f"world identity mismatch for {row['episode_id']}")

        trace_path = args.trace_root / row["source"] / row["source_path"]
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        if (
            trace.get("episode_id") != row["episode_id"]
            or trace.get("world_version") != version
            or int(trace.get("seed", -1)) != int(row["seed"])
            or trace.get("outcome") != "success"
        ):
            raise ValueError(f"trace metadata mismatch for {row['episode_id']}")
        provenance = trace.get("provenance", {})
        if (
            provenance.get("world_definition_id") != row["world_definition_id"]
            or provenance.get("world_definition_hash") != row["world_definition_hash"]
        ):
            raise ValueError(f"trace provenance mismatch for {row['episode_id']}")
        output_rows.append(_trace_metrics(row, trace, environment))

    if not output_rows:
        raise ValueError("no successful lunar/pyramid seeded traces found")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACE_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)

    coverage_rows = _layout_coverage(args.coverage_seeds)
    args.coverage_output.parent.mkdir(parents=True, exist_ok=True)
    with args.coverage_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COVERAGE_FIELDS)
        writer.writeheader()
        writer.writerows(coverage_rows)

    print(f"写入 {args.output}: {len(output_rows)} 条成功 Trace")
    print(f"写入 {args.coverage_output}: {len(coverage_rows)} 种可达工具布局")
    for version in WORLD_SELECTORS:
        group = [row for row in output_rows if row["world_version"] == version]
        if not group:
            continue
        print(
            f"{version}: n={len(group)}, actions P50/max="
            f"{statistics.median(row['recorded_actions'] for row in group):g}/"
            f"{max(row['recorded_actions'] for row in group)}, "
            f"minimum P50/max="
            f"{statistics.median(row['minimum_actions'] for row in group):g}/"
            f"{max(row['minimum_actions'] for row in group)}"
        )


if __name__ == "__main__":
    main()
