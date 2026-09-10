"""Public-data plan monitoring for PlanningAgent v1 and Evaluation v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from agent_arena.arena import Action, Observation, ToolResult, ToolStatus
from agent_arena.planning.models import PlanSignal, PlanState

if TYPE_CHECKING:
    from agent_arena.evaluation.progress import ProgressDetector, ProgressEvent, PublicProgressState
    from agent_arena.evaluation.public_facts import EpisodeKnowledge


def __getattr__(name: str) -> object:
    """Keep the v1 monitor import path for public progress helpers."""

    if name in {"PublicProgressState", "public_progress_state"}:
        from agent_arena.evaluation.progress import PublicProgressState, public_progress_state

        return {
            "PublicProgressState": PublicProgressState,
            "public_progress_state": public_progress_state,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _new_progress_detector() -> ProgressDetector:
    from agent_arena.evaluation.progress import ProgressDetector

    return ProgressDetector()


@dataclass
class PlanMonitor:
    """Detect public completion, repeated failure, and sustained no-progress.

    The monitor owns an episode-local ``ProgressDetector``. Counters reset when
    a plan signal is emitted, while discovered public facts remain available to
    evaluate later structured criteria in the same episode.
    """

    no_progress_threshold: int = 3
    _no_progress_count: int = 0
    _failure_key: tuple[object, ...] | None = None
    _failure_count: int = 0
    _progress_detector: Any = field(default_factory=_new_progress_detector, init=False)
    _last_progress_event: Any = field(default=None, init=False)

    def reset(self) -> None:
        """Reset all episode-local state, including discovered public facts."""

        self._no_progress_count = 0
        self._failure_key = None
        self._failure_count = 0
        self._progress_detector.reset()
        self._last_progress_event = None

    @property
    def last_progress_event(self) -> ProgressEvent | None:
        return cast("ProgressEvent | None", self._last_progress_event)

    @property
    def knowledge(self) -> EpisodeKnowledge:
        """Return the public facts discovered in this episode."""

        return cast("EpisodeKnowledge", self._progress_detector.knowledge)

    @property
    def no_progress_count(self) -> int:
        """Expose the bounded counter for evaluation tests and diagnostics."""

        return self._no_progress_count

    def evaluate(
        self,
        plan: PlanState,
        before: Observation,
        action: Action,
        result: ToolResult,
        after: Observation,
    ) -> PlanSignal:
        """Return a signal based solely on public before/after data."""

        from agent_arena.evaluation.progress import public_progress_state
        from agent_arena.planning.criteria import all_criteria_satisfied

        progress_event = self._progress_detector.evaluate(before, action, result, after)
        self._last_progress_event = progress_event

        if all_criteria_satisfied(
            plan.success_criteria, after, result, self._progress_detector.knowledge
        ):
            self._reset_counters()
            return PlanSignal(status="subgoal_completed", reason="success_criteria_met")

        after_public = public_progress_state(after, result)
        failure_key = (
            _persistent_key(after_public),
            action.model_dump_json(),
            result.status.value,
            result.reason.value,
        )

        if progress_event.progress:
            self._no_progress_count = 0
        else:
            self._no_progress_count += 1

        if result.status is ToolStatus.REJECTED:
            if failure_key == self._failure_key:
                self._failure_count += 1
            else:
                self._failure_key = failure_key
                self._failure_count = 1
            if self._failure_count >= 2:
                self._no_progress_count = 0
                return PlanSignal(status="repeated_failure", reason="repeated_failure")
        else:
            self._failure_key = None
            self._failure_count = 0

        if self._no_progress_count >= self.no_progress_threshold:
            return PlanSignal(status="no_progress", reason="no_progress")
        return PlanSignal(status="continue")

    def _reset_counters(self) -> None:
        self._no_progress_count = 0
        self._failure_key = None
        self._failure_count = 0


def _persistent_key(state: PublicProgressState) -> tuple[object, ...]:
    return (
        state.current_room,
        state.visible_objects,
        state.available_exits,
        state.inventory,
    )
