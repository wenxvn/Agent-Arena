"""Adapter that exposes the six existing V4 runtimes through the V8 contract.

The adapter does not re-implement or tune those maps. It converts the public
V8 action into the frozen ``scenario_v4`` action, copies the public observation
minus the V8 core fields, and keeps a small decision log so the six V7 metric
extractors can be reused unchanged on V8 episodes.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from agent_arena.v6.catalog import build_environment as build_v6_environment
from agent_arena.v6.catalog import get_scene
from agent_arena.v7.metrics.registry import compute_metrics
from agent_arena.v7.metrics.schema import MetricStatus, MetricValue, parse_trace_rows
from agent_arena.worlds.scenario_v4 import ScenarioV4Action
from agent_arena.worlds.scenario_v4.catalog import CONDITIONS as V4_CONDITIONS
from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.catalog import LEVEL_OF, WORLD_OF
from agent_arena.worlds.scenario_v8.models import V8Action, V8Status, V8StepResult

_CORE_KEYS = {"map_id", "terminal", "terminal_reason", "last_action_result"}

#: The six V4 runtimes share the reviewed V4 action contract, but each map only
#: advertises the tools its reviewed prompt and rule engine actually use.
V4_SHAPES_BY_MAP: dict[str, dict[str, set[frozenset[str]]]] = {
    "MAP-08": {
        "move": {frozenset({"tool", "edge_id"})},
        "inspect": {frozenset({"tool", "target_id"})},
        "interact": {frozenset({"tool", "target_id", "operation"})},
        "wait": {frozenset({"tool", "turns"})},
    },
    "MAP-16": {
        "inspect_network": {frozenset({"tool"})},
        "set_route": {frozenset({"tool", "train_id", "next_node"})},
        "occupy_siding": {frozenset({"tool", "train_id", "next_node"})},
        "release_section": {frozenset({"tool", "train_id", "section_id"})},
        "move_train": {frozenset({"tool"})},
    },
    "MAP-18": {
        "set_timetable": {frozenset({"tool", "tick", "operations"})},
    },
    "MAP-22": {
        "observe_signpost": {frozenset({"tool"})},
        "move": {frozenset({"tool", "bearing"})},
        "check_goal": {frozenset({"tool"})},
        "return_to_camp": {frozenset({"tool"})},
        "write_memory": {frozenset({"tool", "facts"})},
    },
    "MAP-26": {
        "move": {frozenset({"tool", "to"})},
        "read_log": {frozenset({"tool", "log_id"})},
        "test": {frozenset({"tool", "test_id"})},
        "take_spare": {frozenset({"tool", "part_id"})},
        "replace": {frozenset({"tool", "part_id"})},
        "rollback": {frozenset({"tool"})},
        "restart": {frozenset({"tool"})},
    },
    "MAP-30": {
        "move": {frozenset({"tool", "to"})},
        "inspect": {frozenset({"tool", "evidence_id"})},
        "interview": {
            frozenset(
                {
                    "tool",
                    "npc_id",
                    "topic_id",
                    "shown_evidence_ids",
                    "shown_casebook_entry_ids",
                }
            )
        },
        "record": {frozenset({"tool", "entry_id", "evidence_ids"})},
        "submit_intermediate_hypothesis": {
            frozenset(
                {
                    "tool",
                    "candidate_person",
                    "confidence",
                    "event_ids_known",
                }
            )
        },
        "compare_records": {frozenset({"tool", "entry_ids"})},
        "formal_accuse": {
            frozenset({"tool", "person_id", "event_claims", "cited_entry_ids"})
        },
    },
}

V4_SHAPES: dict[str, set[frozenset[str]]] = {
    tool: set(shapes)
    for shapes_by_tool in V4_SHAPES_BY_MAP.values()
    for tool, shapes in shapes_by_tool.items()
}

_STATUS_MAP = {
    "running": "running",
    "scenario_success": "success",
    "scenario_failure": "failure",
    "step_limit_reached": "censored",
}

#: The reviewed V6 instance each V8 adapter map reproduces. V7 extractors use
#: this id for frozen reference values (for example the MAP-16 BFS optimum).
V8_INSTANCE_ID: dict[str, str] = {
    "MAP-08": "map08_l3_original",
    "MAP-16": "map16_l3_original",
    "MAP-18": "map18_l3_original",
    "MAP-22": "map22_l3_original",
    "MAP-26": "map26_l1_antenna_fault",
    "MAP-30": "map30_l3_original",
}


class V4MapAdapter(MapEnvironment):
    """A V4 environment behind the V8 public contract."""

    SHAPES = V4_SHAPES

    def __init__(
        self,
        map_id: str,
        *,
        seed: int = 0,
        step_limit: int = 160,
        condition_id: str | None = None,
    ) -> None:
        self.map_id = map_id
        self.world = WORLD_OF[map_id]
        self.level = LEVEL_OF[map_id]
        self.SHAPES = V4_SHAPES_BY_MAP[map_id]
        condition = (
            condition_id
            if condition_id in V4_CONDITIONS[map_id]
            else V4_CONDITIONS[map_id][0]
        )
        self.map_id_condition = condition
        # Build the exact frozen V6 instance so the V7 extractor reference
        # values, fault windows and judge metrics stay valid.
        scene = get_scene(V8_INSTANCE_ID[map_id])
        self._inner = build_v6_environment(
            scene, condition, seed=seed, step_limit=step_limit
        )
        self.title = getattr(self._inner, "title", map_id)
        self.PUBLIC_FIELDS = self._inner_public_fields()
        super().__init__(seed=seed, step_limit=step_limit, condition_id=condition)

    # ------------------------------------------------------------------ contract
    def _inner_public_fields(self) -> frozenset[str]:
        observation_model = getattr(self._inner, "ObservationModel", None)
        fields: set[str] = set()
        if observation_model is not None:
            fields = set(observation_model.model_fields)
        else:  # fall back to the current observation payload
            fields = set(self._inner.observe().model_dump(mode="json"))
        return frozenset(fields - _CORE_KEYS)

    def _reset_state(self, seed: int) -> None:
        self._inner.reset(seed)
        self._trace_rows: list[dict[str, Any]] = []
        self._decision_index = 0
        self._observation_before: dict[str, Any] = self._inner.observe().model_dump(
            mode="json"
        )
        self.sync_from_inner()

    def sync_from_inner(self) -> None:
        self.status = V8Status(self._inner.status.value)
        self.terminal_reason = self._inner.terminal_reason
        self.tick_count = self._inner.step_count
        self.node = getattr(
            self._inner,
            "location",
            getattr(self._inner, "current_node", self.node),
        )

    @property
    def is_terminal(self) -> bool:
        return self._inner.is_terminal

    @property
    def is_success(self) -> bool:
        return self._inner.is_success

    def _public(self) -> dict[str, Any]:
        observation = self._inner.observe().model_dump(mode="json")
        return {key: value for key, value in observation.items() if key not in _CORE_KEYS}

    def _apply(self, action: V8Action) -> str:  # pragma: no cover - step is overridden
        raise AssertionError("V4MapAdapter.step is overridden and never calls _apply.")

    # ------------------------------------------------------------------ stepping
    def step(self, action: V8Action) -> V8StepResult:
        if self._inner.is_terminal:
            return V8StepResult(
                result="ALREADY_TERMINAL",
                status=self.status,
                observation=self.observe(),
            )
        payload = action.model_dump(mode="json", exclude_none=True)
        try:
            converted = ScenarioV4Action.model_validate(payload, strict=True)
        except (ValidationError, TypeError, ValueError):
            return self.reject_invalid_action()
        result = self._inner.step(converted)
        self.sync_from_inner()
        self.last_result = result.result
        self._record(payload, result.result)
        return V8StepResult(
            result=result.result,
            status=self.status,
            observation=self.observe(),
        )

    def reject_invalid_action(self) -> V8StepResult:
        if self._inner.is_terminal:
            return V8StepResult(
                result="ALREADY_TERMINAL",
                status=self.status,
                observation=self.observe(),
            )
        result = self._inner.reject_invalid_action()
        self.sync_from_inner()
        self.last_result = result.result
        self._record({}, result.result, invalid=True)
        return V8StepResult(
            result=result.result,
            status=self.status,
            observation=self.observe(),
        )

    def _record(
        self, payload: dict[str, Any], result: str, *, invalid: bool = False
    ) -> None:
        after = self._inner.observe().model_dump(mode="json")
        self._trace_rows.append(
            {
                "event": "decision",
                "decision_index": self._decision_index,
                "action": payload,
                "result": result,
                "observation_before": self._observation_before,
                "observation_after": after,
                "invalid_output_reason": "INVALID_ACTION_SCHEMA" if invalid else None,
            }
        )
        self._decision_index += 1
        self._observation_before = after

    # ------------------------------------------------------------------ exports
    def judge_state(self) -> dict[str, Any]:
        return dict(self._inner.judge_state())

    def metric_values(self) -> dict[str, MetricValue]:
        """Reuse the frozen V7 extractors on the adapter's decision log."""

        header = {
            "event": "trace_header",
            "map_id": self.map_id,
            "instance_id": V8_INSTANCE_ID.get(self.map_id, f"{self.map_id}-v8"),
            "condition_id": self.condition_id,
            "seed": self.seed,
            "scenario_hash": self.source_hash,
            "provider": "offline",
            "model": "runtime",
        }
        rows = [header, *self._trace_rows]
        record = parse_trace_rows(
            rows,
            judge={
                "status": _STATUS_MAP[self.status.value],
                "judge_state": self._inner.judge_state(),
                "metrics": self._inner.metrics(),
            },
            source=f"v8-adapter:{self.map_id}",
        )
        return compute_metrics(record)

    def metrics(self) -> dict[str, Any]:
        return {
            metric_id: _to_v8_value(value)
            for metric_id, value in self.metric_values().items()
        }

    def state_hash(self) -> str:
        return str(self._inner.state_hash())


def _to_v8_value(value: MetricValue) -> Any:
    if value.status is not MetricStatus.VALID:
        return None
    if value.denominator is not None:
        raw = value.value
        if not isinstance(raw, (int, float)):
            return None
        return {
            "numerator": int(round(float(raw) * value.denominator)),
            "denominator": value.denominator,
        }
    return value.value


__all__ = ["V4MapAdapter", "V4_SHAPES"]
