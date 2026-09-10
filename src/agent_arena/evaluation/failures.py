"""Rule-based failure signals for PlanningAgent trace analysis."""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_arena.arena import Action, Observation, ToolResult, ToolStatus
from agent_arena.evaluation.progress import ProgressDetector, ProgressEvent
from agent_arena.evaluation.public_facts import extract_public_facts
from agent_arena.evaluation.trace import EpisodeTrace, StepTrace, TraceEvent
from agent_arena.safety import sanitize_text


class FailureCategory(StrEnum):
    PLANNING = "planning"
    GROUNDING = "grounding"
    MEMORY_STATE = "memory_state"
    EXPLORATION = "exploration"
    RECOVERY = "recovery"
    PROTOCOL = "protocol"
    UNKNOWN = "unknown"


class FailureType(StrEnum):
    VAGUE_SUBGOAL = "vague_subgoal"
    WRONG_SUBGOAL = "wrong_subgoal"
    PLAN_DRIFT = "plan_drift"
    WRONG_ACTION = "wrong_action"
    WRONG_TARGET = "wrong_target"
    MISSED_AFFORDANCE = "missed_affordance"
    FORGOTTEN_FACT = "forgotten_fact"
    IGNORED_FACT = "ignored_fact"
    REPEATED_INSPECTION = "repeated_inspection"
    REPEATED_NAVIGATION = "repeated_navigation"
    INSUFFICIENT_EXPLORATION = "insufficient_exploration"
    REPEATED_FAILURE = "repeated_failure"
    INEFFECTIVE_REPLAN = "ineffective_replan"
    LOOP = "loop"
    INVALID_OUTPUT = "invalid_output"
    INVALID_ACTION = "invalid_action"
    UNKNOWN = "unknown"


class FailureAnnotation(BaseModel):
    """One rule or manually assigned failure annotation."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    episode_id: str
    step: int = Field(ge=1)
    category: FailureCategory
    failure_type: FailureType
    current_subgoal: str | None = Field(default=None, max_length=240)
    action: str | None = Field(default=None, max_length=240)
    evidence: str = Field(min_length=1, max_length=500)
    confidence: Literal["high", "medium", "low"]
    annotation_source: Literal["rule", "manual"]


class AutomaticFailureSignals(BaseModel):
    """Counts produced without an LLM judge."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    repeated_inspection: int = Field(default=0, ge=0)
    repeated_navigation: int = Field(default=0, ge=0)
    repeated_failure: int = Field(default=0, ge=0)
    invalid_output: int = Field(default=0, ge=0)
    rejected_action: int = Field(default=0, ge=0)


class FailureAnalysis(BaseModel):
    """A serializable, evidence-backed analysis of one episode."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: str = "failure_analysis_v1"
    trace_schema_version: int = 2
    unavailable_metrics: tuple[str, ...] = ()
    episode_id: str
    agent: str
    provider: str
    model: str
    world: str | None
    world_version: str
    seed: int
    outcome: str
    steps: int
    automatic_failure_signals: AutomaticFailureSignals
    state_progress_count: int = Field(ge=0)
    epistemic_progress_count: int = Field(ge=0)
    total_progress_count: int = Field(ge=0)
    no_progress_action_count: int = Field(ge=0)
    unique_public_fact_count: int = Field(ge=0)
    new_fact_rate: float | None = None
    repeated_known_fact_action_count: int = Field(ge=0)
    planner_call_count: int = Field(ge=0)
    planner_call_ratio: float = Field(ge=0)
    replan_count: int = Field(ge=0)
    generated_subgoal_count: int = Field(ge=0)
    completed_subgoal_count: int = Field(ge=0)
    subgoal_completion_rate: float | None = None
    unique_subgoal_count: int = Field(ge=0)
    mean_actions_per_subgoal: float | None = None
    subgoal_switch_count: int = Field(ge=0)
    same_subgoal_repeated_action_count: int = Field(ge=0)
    same_subgoal_rejected_action_count: int = Field(ge=0)
    unique_room_count: int = Field(ge=0)
    unique_object_interaction_count: int = Field(ge=0)
    manual_annotation_required_steps: tuple[int, ...] = ()
    annotations: tuple[FailureAnnotation, ...] = ()


def analyze_trace(trace: EpisodeTrace) -> FailureAnalysis:
    """Analyze automatic failure and progress signals in one persisted trace."""

    records = _records(trace.steps)
    unavailable_metrics: list[str] = []
    if trace.provenance.trace_contract_version == "legacy":
        if any(
            step.action is not None
            and step.result is not None
            and step.next_observation is None
            for step in trace.steps
        ):
            unavailable_metrics.extend(("progress", "knowledge"))
        if trace.agent == "planning" and not any(
            step.plan_id is not None or step.current_subgoal is not None for step in trace.steps
        ):
            unavailable_metrics.append("planning_lifecycle")
    detector = ProgressDetector()
    progress_records: list[tuple[int, StepTrace, ProgressEvent]] = []
    unique_facts: set[tuple[str, str, str | None]] = set()
    repeated_known_fact_action_count = 0
    for index, step, action, result, after in records:
        before = step.observation
        event = detector.evaluate(before, action, result, after)
        # The extractor is intentionally represented by the detector's new
        # facts. A repeated known fact is identified by replaying the detector
        # knowledge before/after the same public result below.
        unique_facts.update(fact.canonical_key() for fact in event.new_facts)
        progress_records.append((index, step, event))

    # Replay once more to distinguish a newly discovered fact from a known one.
    detector = ProgressDetector()
    for _, step, action, result, after in records:
        before_knowledge = detector.knowledge
        observed = extract_public_facts(after, action, result)
        event = detector.evaluate(step.observation, action, result, after)
        if observed and not event.new_facts and all(
            before_knowledge.contains(fact) for fact in observed
        ):
            repeated_known_fact_action_count += 1

    actions = len(records)
    state_progress_count = sum(item[2].state_progress for item in progress_records)
    epistemic_progress_count = sum(item[2].epistemic_progress for item in progress_records)
    total_progress_count = sum(item[2].progress for item in progress_records)
    no_progress_action_count = sum(not item[2].progress for item in progress_records)
    planner_calls = sum(step.planner_called for _, step, *_ in records)
    completed_subgoals = sum(step.subgoal_completed for _, step, *_ in records)
    subgoals = [step.current_subgoal for _, step, *_ in records if step.current_subgoal]
    unique_subgoals = tuple(dict.fromkeys(subgoals))
    switches = sum(
        first != second for first, second in zip(subgoals, subgoals[1:], strict=False)
    )

    same_subgoal_repeated = _same_subgoal_repeated_actions(records)
    same_subgoal_rejected = sum(
        step.current_subgoal is not None
        and result.status is ToolStatus.REJECTED
        for _, step, _, result, _ in records
    )
    rooms = {
        observation.current_room
        for _, step, _, _, after in records
        for observation in (step.observation, after)
    }
    interactions = {
        (action.tool, _action_target(action))
        for _, _, action, _, _ in records
        if action.tool in {"inspect", "read_terminal", "pickup", "use"}
    }
    annotations, signals = _automatic_annotations(trace, progress_records)
    annotated_steps = {annotation.step for annotation in annotations}
    manual_steps = tuple(index for index, step, *_ in records if index not in annotated_steps)
    return FailureAnalysis(
        trace_schema_version=trace.trace_schema_version,
        unavailable_metrics=tuple(unavailable_metrics),
        episode_id=str(trace.episode_id),
        agent=trace.agent,
        provider=trace.provider,
        model=trace.provenance.model_name,
        world=trace.provenance.world,
        world_version=trace.world_version,
        seed=trace.seed,
        outcome=trace.outcome.value,
        steps=trace.executed_action_count,
        automatic_failure_signals=signals,
        state_progress_count=state_progress_count,
        epistemic_progress_count=epistemic_progress_count,
        total_progress_count=total_progress_count,
        no_progress_action_count=no_progress_action_count,
        unique_public_fact_count=len(unique_facts),
        new_fact_rate=epistemic_progress_count / actions if actions else None,
        repeated_known_fact_action_count=repeated_known_fact_action_count,
        planner_call_count=planner_calls,
        planner_call_ratio=planner_calls / actions if actions else 0.0,
        replan_count=max(0, planner_calls - 1),
        generated_subgoal_count=planner_calls,
        completed_subgoal_count=completed_subgoals,
        subgoal_completion_rate=completed_subgoals / planner_calls if planner_calls else None,
        unique_subgoal_count=len(unique_subgoals),
        mean_actions_per_subgoal=actions / len(unique_subgoals) if unique_subgoals else None,
        subgoal_switch_count=switches,
        same_subgoal_repeated_action_count=same_subgoal_repeated,
        same_subgoal_rejected_action_count=same_subgoal_rejected,
        unique_room_count=len(rooms),
        unique_object_interaction_count=len(interactions),
        manual_annotation_required_steps=manual_steps,
        annotations=tuple(annotations),
    )


def write_failure_analysis(
    analyses: list[FailureAnalysis], output_dir: Path
) -> tuple[Path, Path]:
    """Write the JSON and CSV report for one or more analyzed traces."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "failure_analysis.json"
    csv_path = output_dir / "failure_analysis.csv"
    payload = {
        "schema_version": "failure_analysis_v1",
        "analysis_count": len(analyses),
        "analyses": [analysis.model_dump(mode="json") for analysis in analyses],
        "failure_distribution": _failure_distribution(analyses),
    }
    _atomic_write(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    rows = [_flat_analysis(analysis) for analysis in analyses]
    fields = list(rows[0]) if rows else list(_flat_analysis_template())
    _atomic_write_csv(csv_path, fields, rows)
    return json_path, csv_path


def _failure_distribution(analyses: list[FailureAnalysis]) -> dict[str, int]:
    distribution: defaultdict[str, int] = defaultdict(int)
    for analysis in analyses:
        for annotation in analysis.annotations:
            distribution[annotation.failure_type.value] += 1
    return dict(sorted(distribution.items()))


def _flat_analysis(analysis: FailureAnalysis) -> dict[str, object]:
    row = {
        key: value
        for key, value in analysis.model_dump(mode="json").items()
        if key not in {"automatic_failure_signals", "annotations"}
    }
    row.update(
        {
            f"{key}_count": value
            for key, value in analysis.automatic_failure_signals.model_dump().items()
        }
    )
    row["manual_annotation_required_steps"] = ",".join(
        str(step) for step in analysis.manual_annotation_required_steps
    )
    row["annotation_count"] = len(analysis.annotations)
    return row


def _flat_analysis_template() -> dict[str, object]:
    fields: dict[str, object] = {
        key: ""
        for key in FailureAnalysis.model_fields
        if key not in {"automatic_failure_signals", "annotations"}
    }
    fields.update({f"{key}_count": "" for key in AutomaticFailureSignals.model_fields})
    fields["manual_annotation_required_steps"] = ""
    fields["annotation_count"] = ""
    return fields


def _atomic_write(destination: Path, contents: str) -> None:
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        raise


def _atomic_write_csv(
    destination: Path, fields: list[str], rows: list[dict[str, object]]
) -> None:
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        raise


def _records(
    steps: tuple[StepTrace, ...],
) -> list[tuple[int, StepTrace, Action, ToolResult, Observation]]:
    return [
        (index, step, step.action, step.result, step.next_observation)
        for index, step in enumerate(steps, start=1)
        if step.action is not None and step.result is not None and step.next_observation is not None
    ]


def _automatic_annotations(
    trace: EpisodeTrace,
    progress_records: list[tuple[int, StepTrace, ProgressEvent]],
) -> tuple[list[FailureAnnotation], AutomaticFailureSignals]:
    annotations: list[FailureAnnotation] = []
    inspection_counts: defaultdict[str, int] = defaultdict(int)
    failure_counts: defaultdict[str, int] = defaultdict(int)
    navigation_transitions: list[tuple[str, str, int, StepTrace, ProgressEvent]] = []
    repeated_inspection = repeated_navigation = repeated_failure = 0
    rejected_action = sum(
        step.result is not None and step.result.status is ToolStatus.REJECTED
        for step in trace.steps
    )
    invalid_output = sum(step.event is TraceEvent.ACTION_INVALID for step in trace.steps)

    for index, step, event in progress_records:
        action = step.action
        result = step.result
        after = step.next_observation
        assert action is not None and result is not None and after is not None
        if action.tool == "inspect" and not event.epistemic_progress:
            key = json.dumps(
                {
                    "room": step.observation.current_room,
                    "objects": sorted(step.observation.visible_objects),
                    "exits": sorted(step.observation.available_exits),
                    "inventory": sorted(step.observation.inventory),
                    "action": action.model_dump(mode="json"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            inspection_counts[key] += 1
            if inspection_counts[key] >= 2:
                repeated_inspection += 1
                annotations.append(
                    _annotation(
                        trace,
                        index,
                        FailureCategory.EXPLORATION,
                        FailureType.REPEATED_INSPECTION,
                        step,
                        "同一公开状态下重复 inspect，且没有新的公开事实。",
                    )
                )

        if result.status is ToolStatus.REJECTED:
            key = json.dumps(
                {
                    "room": after.current_room,
                    "objects": sorted(after.visible_objects),
                    "exits": sorted(after.available_exits),
                    "inventory": sorted(after.inventory),
                    "action": action.model_dump(mode="json"),
                    "reason": result.reason.value,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            failure_counts[key] += 1
            if failure_counts[key] >= 2:
                repeated_failure += 1
                annotations.append(
                    _annotation(
                        trace,
                        index,
                        FailureCategory.RECOVERY,
                        FailureType.REPEATED_FAILURE,
                        step,
                        f"相同公开状态、Action 和失败原因重复至少 {failure_counts[key]} 次。",
                    )
                )

        if action.tool == "move":
            navigation_transitions.append(
                (step.observation.current_room, after.current_room, index, step, event)
            )
            if len(navigation_transitions) >= 4:
                cycle = navigation_transitions[-4:]
                sources = [item[0] for item in cycle]
                destinations = [item[1] for item in cycle]
                if (
                    sources[0] == sources[2]
                    and sources[1] == sources[3]
                    and destinations[0] == sources[1]
                    and destinations[1] == sources[2]
                    and destinations[2] == sources[3]
                    and destinations[3] == sources[0]
                    and all(not item[4].new_facts for item in cycle)
                    and len({tuple(item[3].observation.inventory) for item in cycle}) == 1
                ):
                    repeated_navigation += 1
                    annotations.append(
                        _annotation(
                            trace,
                            index,
                            FailureCategory.EXPLORATION,
                            FailureType.REPEATED_NAVIGATION,
                            step,
                            "公开房间轨迹出现 A→B→A→B 循环，且没有新的公开事实或物品。",
                        )
                    )

    for index, step in enumerate(trace.steps, start=1):
        if step.event is TraceEvent.ACTION_INVALID:
            annotations.append(
                _annotation(
                    trace,
                    index,
                    FailureCategory.PROTOCOL,
                    FailureType.INVALID_OUTPUT,
                    step,
                    "Provider 输出未通过统一 Action schema。",
                )
            )
        elif step.result is not None and step.result.status is ToolStatus.REJECTED:
            annotations.append(
                _annotation(
                    trace,
                    index,
                    FailureCategory.PROTOCOL,
                    FailureType.INVALID_ACTION,
                    step,
                    "Action schema 合法，但 Environment 公开拒绝了该 Action。",
                )
            )
    return annotations, AutomaticFailureSignals(
        repeated_inspection=repeated_inspection,
        repeated_navigation=repeated_navigation,
        repeated_failure=repeated_failure,
        invalid_output=invalid_output,
        rejected_action=rejected_action,
    )


def _same_subgoal_repeated_actions(
    records: list[tuple[int, StepTrace, Action, ToolResult, Observation]],
) -> int:
    seen: set[tuple[str, str]] = set()
    repeated = 0
    for _, step, action, _, _ in records:
        if step.current_subgoal is None:
            continue
        key = (step.current_subgoal, action.model_dump_json())
        if key in seen:
            repeated += 1
        seen.add(key)
    return repeated


def _annotation(
    trace: EpisodeTrace,
    step_number: int,
    category: FailureCategory,
    failure_type: FailureType,
    step: StepTrace,
    evidence: str,
) -> FailureAnnotation:
    return FailureAnnotation(
        episode_id=str(trace.episode_id),
        step=step_number,
        category=category,
        failure_type=failure_type,
        current_subgoal=(
            sanitize_text(step.current_subgoal, max_length=240)
            if step.current_subgoal
            else None
        ),
        action=step.action.tool if step.action is not None else None,
        evidence=sanitize_text(evidence, max_length=500),
        confidence="high",
        annotation_source="rule",
    )


def _action_target(action: Action) -> str | None:
    data = action.model_dump(mode="python")
    for key in ("target", "item", "destination"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return None
