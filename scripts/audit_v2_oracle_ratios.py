"""Compare successful V2 traces with spec-declared shortest public paths."""
from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from agent_arena.worlds import create_environment

ORACLE_PATHS = (
    # Original nine fixed maps; spec 0012, D2 table.
    ("spaceship-escape", "spaceship-escape-v2-zh", 20, "0012"),
    ("spaceship-escape", "spaceship-escape-v3-zh", 19, "0012"),
    ("spaceship-escape", "spaceship-escape-v4-zh", 21, "0012"),
    ("lighthouse-escape", "lighthouse-escape-v1-zh", 15, "0012"),
    ("lighthouse-escape", "lighthouse-escape-v2-zh", 16, "0012"),
    ("lighthouse-escape", "lighthouse-escape-v3-zh", 20, "0012"),
    ("abyss-escape", "abyss-escape-v1-zh", 13, "0012"),
    ("abyss-escape", "abyss-escape-easy-zh", 19, "0012"),
    ("abyss-escape", "abyss-escape-hard-zh", 21, "0012"),
    # Seven new worlds; spec 0011, difficulty table.
    ("polar-escape", "polar-escape-easy-zh", 11, "0011"),
    ("polar-escape", "polar-escape-v1-zh", 19, "0011"),
    ("polar-escape", "polar-escape-hard-zh", 21, "0011"),
    ("pyramid-escape", "pyramid-escape-easy-zh", 11, "0011"),
    ("pyramid-escape", "pyramid-escape-v1-zh", 15, "0011"),
    ("pyramid-escape", "pyramid-escape-hard-zh", 17, "0011"),
    ("subway-escape", "subway-escape-easy-zh", 13, "0011"),
    ("subway-escape", "subway-escape-v1-zh", 15, "0011"),
    ("subway-escape", "subway-escape-hard-zh", 21, "0011"),
    ("volcano-escape", "volcano-escape-easy-zh", 13, "0011"),
    ("volcano-escape", "volcano-escape-v1-zh", 19, "0011"),
    ("volcano-escape", "volcano-escape-hard-zh", 17, "0011"),
    ("jungle-escape", "jungle-escape-easy-zh", 13, "0011"),
    ("jungle-escape", "jungle-escape-v1-zh", 20, "0011"),
    ("jungle-escape", "jungle-escape-hard-zh", 22, "0011"),
    ("lunar-escape", "lunar-escape-easy-zh", 12, "0011"),
    ("lunar-escape", "lunar-escape-v1-zh", 14, "0011"),
    ("lunar-escape", "lunar-escape-hard-zh", 16, "0011"),
    ("castle-escape", "castle-escape-easy-zh", 13, "0011"),
    ("castle-escape", "castle-escape-v1-zh", 19, "0011"),
    ("castle-escape", "castle-escape-hard-zh", 21, "0011"),
    # Nine redesigned maps; spec 0013, new-map table.
    ("spaceship-escape", "spaceship-escape-easy-zh", 20, "0013"),
    ("spaceship-escape", "spaceship-escape-v1-zh", 22, "0013"),
    ("spaceship-escape", "spaceship-escape-hard-zh", 24, "0013"),
    ("lighthouse-escape", "lighthouse-escape-v4-zh", 13, "0013"),
    ("lighthouse-escape", "lighthouse-escape-v5-zh", 21, "0013"),
    ("lighthouse-escape", "lighthouse-escape-v6-zh", 19, "0013"),
    ("abyss-escape", "abyss-escape-v2-zh", 12, "0013"),
    ("abyss-escape", "abyss-escape-v3-zh", 16, "0013"),
    ("abyss-escape", "abyss-escape-v4-zh", 17, "0013"),
    # Three fixed flex pilot maps; spec 0012, D1 table.
    ("lunar-escape", "lunar-escape-v2-zh", 19, "0012"),
    ("castle-escape", "castle-escape-v2-zh", 22, "0012"),
    ("pyramid-escape", "pyramid-escape-v2-zh", 16, "0012"),
)

IDENTITY_FIELDS = (
    "world_version",
    "world_definition_id",
    "world_definition_hash",
)
CONDITION_FIELDS = (
    "experiment_bucket",
    *IDENTITY_FIELDS,
    "configuration_signature",
    "oracle_spec",
)
TRACE_FIELDS = (
    "episode_id",
    *CONDITION_FIELDS,
    "seed_role",
    "seed",
    "recorded_attempt_index",
    "recorded_action_count",
    "reference_min_actions",
    "actions_per_reference_min",
    "excess_actions",
)


def _oracle_registry() -> dict[tuple[str, str, str], dict[str, Any]]:
    registry: dict[tuple[str, str, str], dict[str, Any]] = {}
    for world, selector, steps, spec in ORACLE_PATHS:
        identity = create_environment(world, selector).identity
        key = (identity[1], identity[2], identity[3])
        record = {"reference_min_actions": steps, "oracle_spec": spec}
        if key in registry and registry[key] != record:
            raise ValueError(f"conflicting reference path for {identity[1:3]}")
        registry[key] = record
    return registry


def _distribution(values: list[float | int]) -> dict[str, float | int]:
    ordered = sorted(values)

    def nearest_index(probability: float) -> int:
        return max(0, int(probability * (len(ordered) - 1) + 0.5))

    return {
        "n": len(ordered),
        "p50": statistics.median(ordered),
        "p75": ordered[nearest_index(0.75)],
        "p90": ordered[nearest_index(0.90)],
        "max": ordered[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="按精确 world identity 对照 V2 成功 Trace 与 spec 最短公开路径"
    )
    parser.add_argument(
        "--input", type=Path, default=Path("docs/research/v2/assets/trace-audit.csv")
    )
    parser.add_argument(
        "--traces-output",
        type=Path,
        default=Path("docs/research/v2/assets/oracle-optimality-traces.csv"),
    )
    parser.add_argument(
        "--conditions-output",
        type=Path,
        default=Path("docs/research/v2/assets/oracle-optimality-conditions.csv"),
    )
    args = parser.parse_args()

    registry = _oracle_registry()
    with args.input.open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    exact_identity_rows = 0
    unmatched_successes = 0
    below_reference: list[str] = []
    matched: list[dict[str, Any]] = []
    for row in source_rows:
        key = tuple(row[field] for field in IDENTITY_FIELDS)
        oracle = registry.get(key)
        if oracle is None:
            unmatched_successes += row["outcome"] == "success"
            continue
        exact_identity_rows += 1
        if row["outcome"] != "success":
            continue
        action_count = int(row["recorded_action_count"])
        reference = int(oracle["reference_min_actions"])
        if action_count < reference:
            below_reference.append(row["episode_id"])
        record = {field: row.get(field, "") for field in TRACE_FIELDS}
        record.update(oracle)
        record["recorded_action_count"] = action_count
        record["actions_per_reference_min"] = round(action_count / reference, 6)
        record["excess_actions"] = action_count - reference
        matched.append(record)

    if below_reference:
        raise ValueError(
            "successful traces fall below their spec-declared minimum: "
            + ", ".join(below_reference[:10])
        )
    if not matched:
        parser.error("没有与已登记 spec 最短路径精确匹配的成功 Trace")

    for path in (args.traces_output, args.conditions_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.traces_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(TRACE_FIELDS))
        writer.writeheader()
        writer.writerows(matched)

    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in matched:
        grouped[tuple(str(row[field]) for field in CONDITION_FIELDS)].append(row)
    summary_fields = [*CONDITION_FIELDS, "successes"]
    for metric in ("actions_per_reference_min", "excess_actions"):
        summary_fields.extend(f"{metric}_{stat}" for stat in ("n", "p50", "p75", "p90", "max"))
    with args.conditions_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields)
        writer.writeheader()
        for key, rows in sorted(grouped.items()):
            summary: dict[str, Any] = dict(zip(CONDITION_FIELDS, key, strict=True))
            summary["successes"] = len(rows)
            for metric in ("actions_per_reference_min", "excess_actions"):
                values = [row[metric] for row in rows]
                summary.update(
                    {
                        f"{metric}_{stat}": value
                        for stat, value in _distribution(values).items()
                    }
                )
            writer.writerow(summary)

    print(
        f"matched {len(matched)} successes across {len(grouped)} conditions; "
        f"{exact_identity_rows}/{len(source_rows)} rows have exact map identity; "
        f"{unmatched_successes} successes lack an exact spec-hash match"
    )


if __name__ == "__main__":
    main()
