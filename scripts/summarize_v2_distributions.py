"""Summarize V2 trace distributions without merging experimental conditions."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

GROUP_FIELDS = ("experiment_bucket", "world_version", "configuration_signature")
OUTCOME_NAMES = ("success", "step_limit", "provider_error", "invalid_action_limit")
EVENT_FIELDS = (
    ("first_panel_opened_step", "panel"),
    ("first_power_restored_step", "power"),
    ("first_code_read_step", "code"),
    ("first_escape_step", "escape"),
)
INTERVALS = (
    ("panel_to_power", "first_panel_opened_step", "first_power_restored_step"),
    ("power_to_code", "first_power_restored_step", "first_code_read_step"),
    ("code_to_escape", "first_code_read_step", "first_escape_step"),
)
COUNT_FIELDS = (
    "progress_observed_steps",
    "no_progress_actions",
    "state_progress_actions",
    "epistemic_progress_actions",
    "wrong_terminal_target_reads",
    "repeated_code_reads",
    "post_code_navigation_actions",
    "repeated_failed_action_attempts",
    "repeated_look_actions",
    "navigation_two_cycle_count",
)


def _number(value: str | None) -> int | float | None:
    if value in (None, "", "None"):
        return None
    try:
        return int(value)
    except ValueError:
        return float(value)


def _percentiles(values: list[int | float]) -> dict[str, int | float | None]:
    if not values:
        return {"n": 0, "p50": None, "p75": None, "p90": None, "max": None}
    ordered = sorted(values)

    def nearest_index(probability: float) -> int:
        return max(0, int(probability * (len(ordered) - 1) + 0.5))

    return {
        "n": len(ordered),
        "p50": median(ordered),
        "p75": ordered[nearest_index(0.75)],
        "p90": ordered[nearest_index(0.90)],
        "max": ordered[-1],
    }


def _append_distribution(
    output: dict[str, Any], prefix: str, values: list[int | float]
) -> None:
    for key, value in _percentiles(values).items():
        output[f"{prefix}_{key}"] = value


def summarize_group(rows: list[dict[str, str]]) -> dict[str, Any]:
    successes = [row for row in rows if row["outcome"] == "success"]
    outcomes = Counter(row["outcome"] for row in rows)
    output: dict[str, Any] = {field: rows[0].get(field, "") for field in GROUP_FIELDS}
    output["attempts"] = len(rows)
    for name in OUTCOME_NAMES:
        output[f"{name}_count"] = outcomes[name]

    actions = [
        int(value)
        for row in successes
        if (value := _number(row.get("recorded_action_count"))) is not None
    ]
    _append_distribution(output, "success_actions", actions)

    token_pairs = [
        int(input_tokens) + int(output_tokens)
        for row in rows
        if (input_tokens := _number(row.get("input_tokens"))) is not None
        and (output_tokens := _number(row.get("output_tokens"))) is not None
    ]
    success_token_pairs = [
        int(input_tokens) + int(output_tokens)
        for row in successes
        if (input_tokens := _number(row.get("input_tokens"))) is not None
        and (output_tokens := _number(row.get("output_tokens"))) is not None
    ]
    output["executor_token_pair_attempt_coverage"] = len(token_pairs)
    output["executor_token_pair_success_coverage"] = len(success_token_pairs)
    output["known_executor_tokens_per_recorded_success"] = (
        round(sum(token_pairs) / len(successes), 2) if successes else None
    )
    _append_distribution(output, "success_trace_executor_tokens", success_token_pairs)

    success_latencies = [
        value
        for row in successes
        if (value := _number(row.get("latency_ms"))) is not None
    ]
    _append_distribution(output, "success_trace_latency_ms", success_latencies)

    for field in COUNT_FIELDS:
        output[field] = sum(int(_number(row.get(field)) or 0) for row in rows)
    denominator = output["progress_observed_steps"]
    output["no_progress_ratio"] = (
        round(output["no_progress_actions"] / denominator, 6) if denominator else None
    )

    event_orders: Counter[str] = Counter()
    all_event_count = 0
    canonical_event_count = 0
    code_before_panel = 0
    code_before_power = 0
    for row in successes:
        events = [
            (int(value), label)
            for field, label in EVENT_FIELDS
            if (value := _number(row.get(field))) is not None
        ]
        if len(events) != len(EVENT_FIELDS):
            continue
        all_event_count += 1
        events.sort()
        order = ">".join(label for _, label in events)
        event_orders[order] += 1
        canonical_event_count += order == "panel>power>code>escape"
        steps = {label: step for step, label in events}
        code_before_panel += steps["code"] < steps["panel"]
        code_before_power += steps["code"] < steps["power"]
    output["success_with_all_milestones"] = all_event_count
    output["canonical_milestone_order"] = canonical_event_count
    output["code_before_panel"] = code_before_panel
    output["code_before_power"] = code_before_power
    output["milestone_order_counts"] = json.dumps(
        dict(sorted(event_orders.items())), ensure_ascii=False, sort_keys=True
    )

    for name, earlier_field, later_field in INTERVALS:
        intervals: list[int] = []
        reversed_count = 0
        for row in successes:
            earlier = _number(row.get(earlier_field))
            later = _number(row.get(later_field))
            if earlier is None or later is None:
                continue
            if later < earlier:
                reversed_count += 1
            else:
                intervals.append(int(later - earlier))
        output[f"{name}_reversed"] = reversed_count
        _append_distribution(output, name, intervals)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="按 experiment bucket/world/config 汇总 V2 离线分布"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("docs/research/v2/assets/trace-audit.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/research/v2/assets/condition-distributions.csv"),
    )
    args = parser.parse_args()
    with args.input.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        parser.error(f"输入 CSV 没有数据行：{args.input}")
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(field, "") for field in GROUP_FIELDS)].append(row)
    summaries = [summarize_group(groups[key]) for key in sorted(groups)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    success_count = sum(int(row["success_count"]) for row in summaries)
    print(f"summarized {len(summaries)} conditions and {success_count} successes")


if __name__ == "__main__":
    main()
