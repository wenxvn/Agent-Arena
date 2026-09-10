"""Planning contracts with lazy evaluation helpers to keep module boundaries acyclic."""

from agent_arena.planning.models import (
    Criterion,
    PlannerDecision,
    PlanningMetadata,
    PlanSignal,
    PlanSignalStatus,
    PlanState,
    SuccessCriterion,
    planner_decision_adapter,
)

__all__ = [
    "PlanMonitor",
    "PlanSignal",
    "PlanSignalStatus",
    "PlanState",
    "PlannerDecision",
    "PlanningMetadata",
    "SuccessCriterion",
    "Criterion",
    "LegacySuccessCriterionAdapter",
    "criterion_satisfied",
    "all_criteria_satisfied",
    "PublicProgressState",
    "ProgressEvent",
    "ProgressDetector",
    "planner_decision_adapter",
    "public_progress_state",
]


def __getattr__(name: str) -> object:
    if name == "PlanMonitor":
        from agent_arena.planning.monitor import PlanMonitor

        return PlanMonitor
    if name in {"LegacySuccessCriterionAdapter", "criterion_satisfied", "all_criteria_satisfied"}:
        from agent_arena.planning import criteria

        return getattr(criteria, name)
    if name in {
        "PublicProgressState",
        "ProgressEvent",
        "ProgressDetector",
        "public_progress_state",
    }:
        from agent_arena.evaluation import progress

        return getattr(progress, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
