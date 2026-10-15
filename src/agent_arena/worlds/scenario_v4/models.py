"""Strict public contracts for the isolated V4 map runtime."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class V4Status(StrEnum):
    RUNNING = "running"
    SUCCESS = "scenario_success"
    FAILURE = "scenario_failure"
    CENSORED = "step_limit_reached"


class V4JointOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    op: Literal["release", "detour", "temporary_stop", "turnback", "cancel_service"]
    to: str | None = None
    task_id: str | None = None
    reverse_toward: str | None = None
    duration_ticks: int | None = Field(default=None, ge=1, le=2)

    @model_validator(mode="after")
    def validate_fields(self) -> V4JointOperation:
        required = {
            "release": {"op", "to"},
            "detour": {"op", "to"},
            "temporary_stop": {"op"},
            "turnback": {"op", "reverse_toward", "duration_ticks"},
            "cancel_service": {"op", "task_id"},
        }[self.op]
        if self.model_fields_set != required:
            raise ValueError("联合时刻表动作字段与操作类型不匹配。")
        if any(getattr(self, field) is None for field in required - {"op"}):
            raise ValueError("联合时刻表动作的必填字段不得为空。")
        return self


class V4MemoryFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    fact_type: Literal["node_page", "traversed_edge_page"]
    sign_id: str | None = None
    exit_bearings: list[str] | None = None
    from_sign_id: str | None = None
    departure_bearing: str | None = None
    to_sign_id: str | None = None
    arrival_reverse_bearing: str | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> V4MemoryFact:
        required = (
            {"fact_type", "sign_id", "exit_bearings"}
            if self.fact_type == "node_page"
            else {
                "fact_type",
                "from_sign_id",
                "departure_bearing",
                "to_sign_id",
                "arrival_reverse_bearing",
            }
        )
        if self.model_fields_set != required:
            raise ValueError("记忆事实只能包含当前已观察或刚经过的字段。")
        if any(getattr(self, field) is None for field in required - {"fact_type"}):
            raise ValueError("记忆事实的必填字段不得为空。")
        return self


class V4EventClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    event_id: str
    time: str
    location: str
    duty_code: str


class V4HypothesisTable(BaseModel):
    """Compact Agent-owned beliefs for MAP-08; it contains no judge state."""

    model_config = ConfigDict(extra="forbid", strict=True)

    belief_B: float = Field(ge=0, le=1)
    belief_D: float = Field(ge=0, le=1)
    belief_F: float = Field(ge=0, le=1)
    test_X_result: Literal["pulse_amber", "pulse_slate"] | None
    test_Y_result: Literal["pulse_cobalt", "pulse_slate"] | None
    next_test: Literal["X", "Y", "repair"]

    @model_validator(mode="after")
    def validate_probability_mass(self) -> V4HypothesisTable:
        total = self.belief_B + self.belief_D + self.belief_F
        if abs(total - 1.0) > 0.01:
            raise ValueError("MAP-08 hypothesis probabilities must sum to one.")
        return self


class ScenarioV4Action(BaseModel):
    """One flattened, strict action schema; environments enforce map-specific legality."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool: Literal[
        "move",
        "inspect",
        "interact",
        "wait",
        "inspect_network",
        "set_route",
        "occupy_siding",
        "release_section",
        "move_train",
        "set_timetable",
        "observe_signpost",
        "write_memory",
        "check_goal",
        "return_to_camp",
        "read_log",
        "test",
        "take_spare",
        "replace",
        "rollback",
        "restart",
        "interview",
        "record",
        "submit_intermediate_hypothesis",
        "compare_records",
        "formal_accuse",
    ]
    edge_id: str | None = None
    to: str | None = None
    bearing: str | None = None
    target_id: str | None = None
    evidence_id: str | None = None
    operation: str | None = None
    turns: Literal[1] | None = None
    train_id: Literal["a", "b", "T_R1", "T_R2", "T_R3", "T_B", "T_G", "T_X"] | None = None
    next_node: str | None = None
    section_id: str | None = None
    tick: int | None = Field(default=None, ge=0)
    operations: dict[str, V4JointOperation] | None = None
    facts: list[V4MemoryFact] | None = None
    log_id: str | None = None
    test_id: str | None = None
    part_id: str | None = None
    npc_id: str | None = None
    topic_id: str | None = None
    shown_evidence_ids: list[str] | None = None
    shown_casebook_entry_ids: list[str] | None = None
    entry_id: str | None = None
    evidence_ids: list[str] | None = None
    candidate_person: str | None = None
    confidence: Literal["low", "tentative"] | None = None
    event_ids_known: list[str] | None = None
    entry_ids: list[str] | None = None
    person_id: str | None = None
    event_claims: list[V4EventClaim] | None = None
    cited_entry_ids: list[str] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> ScenarioV4Action:
        fields = self.model_fields_set
        required_by_tool: dict[str, set[str]] = {
            "inspect_network": {"tool"},
            "move_train": {"tool"},
            "observe_signpost": {"tool"},
            "check_goal": {"tool"},
            "return_to_camp": {"tool"},
            "rollback": {"tool"},
            "restart": {"tool"},
            "move": {"tool"},
            "inspect": {"tool"},
            "interact": {"tool", "target_id", "operation"},
            "wait": {"tool", "turns"},
            "set_route": {"tool", "train_id", "next_node"},
            "occupy_siding": {"tool", "train_id", "next_node"},
            "release_section": {"tool", "train_id", "section_id"},
            "set_timetable": {"tool", "tick", "operations"},
            "write_memory": {"tool", "facts"},
            "read_log": {"tool", "log_id"},
            "test": {"tool", "test_id"},
            "take_spare": {"tool", "part_id"},
            "replace": {"tool", "part_id"},
            "interview": {
                "tool",
                "npc_id",
                "topic_id",
                "shown_evidence_ids",
                "shown_casebook_entry_ids",
            },
            "record": {"tool", "entry_id", "evidence_ids"},
            "submit_intermediate_hypothesis": {
                "tool",
                "candidate_person",
                "confidence",
                "event_ids_known",
            },
            "compare_records": {"tool", "entry_ids"},
            "formal_accuse": {"tool", "person_id", "event_claims", "cited_entry_ids"},
        }
        if self.tool in {"move", "inspect"}:
            required = {"tool", "edge_id"} if self.tool == "move" and "edge_id" in fields else None
            if self.tool == "move" and required is None:
                required = next(({"tool", key} for key in ("to", "bearing") if key in fields), None)
            if self.tool == "inspect":
                required = next(
                    ({"tool", key} for key in ("target_id", "evidence_id") if key in fields),
                    None,
                )
            if required is None or fields != required:
                raise ValueError("动作字段与 move/inspect 的地图操作不匹配。")
        elif fields != required_by_tool[self.tool]:
            raise ValueError("动作字段与工具类型不匹配。")
        required_fields = fields - {"tool"}
        if any(getattr(self, field) is None for field in required_fields):
            raise ValueError("动作的必填字段不得为空。")
        return self


class V4ObservationBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    map_id: str
    terminal: bool
    terminal_reason: str | None


class V4Map08Observation(V4ObservationBase):
    map_id: Literal["MAP-08"] = "MAP-08"
    location: str
    visible_edges: tuple[str, ...]
    current_tick: int
    current_core_water: float
    baseline_sensor_reading: str
    published_candidate_set: tuple[str, ...]
    published_prior: dict[str, float]
    known_test_semantics: dict[str, str]
    sealant_count: int
    test_results: dict[str, str]
    last_action_result: str


class V4Map16Observation(V4ObservationBase):
    map_id: Literal["MAP-16"] = "MAP-16"
    tick: int
    topology: dict[str, tuple[str, ...]]
    train_route_directions: dict[str, dict[str, tuple[str, ...]]]
    train_positions: dict[str, str]
    train_goals: dict[str, str]
    segment_capacities: dict[str, int]
    node_capacities: dict[str, int]
    occupied_nodes: tuple[str, ...]
    pending_route_reservations: dict[str, str]


class V4Map18Observation(V4ObservationBase):
    map_id: Literal["MAP-18"] = "MAP-18"
    tick: int
    ticks_remaining: int
    topology: dict[str, Any]
    train_positions: dict[str, str]
    station_berths: dict[str, int]
    task_passenger_counts: dict[str, int]
    delivered_tasks: tuple[str, ...]
    canceled_tasks: tuple[str, ...]
    delivered_passengers: int
    canceled_passengers: int
    closed_segments: tuple[str, ...]
    current_train_locks: dict[str, int]
    published_dispatch_windows: dict[str, dict[str, int | tuple[int, ...]]]
    alert_message_if_any: dict[str, str] | None
    recovery_status: str


class V4Map22Observation(V4ObservationBase):
    map_id: Literal["MAP-22"] = "MAP-22"
    movement_steps: int
    current_coarse_silhouette: str
    visible_exit_bearings: tuple[str, ...]
    inspected_current_sign_detail: dict[str, str] | None
    active_goal_marker: str
    agent_authored_memory_journal: tuple[V4MemoryFact, ...]


class V4Map26Observation(V4ObservationBase):
    map_id: Literal["MAP-26"] = "MAP-26"
    current_tick: int
    current_node: str
    alert: str
    log_readings: tuple[str, ...]
    test_readings: dict[str, str]
    spare_units_at_B: int
    carried_spare_units: tuple[str, ...]
    installed_candidates: dict[str, str]
    last_action_result: str
    communication_restored: bool
    last_action_error_code: str | None


class V4Map30Observation(V4ObservationBase):
    map_id: Literal["MAP-30"] = "MAP-30"
    current_tick: int
    current_node: str
    local_neighbors: tuple[str, ...]
    public_alert: str
    visible_local_evidence: tuple[str, ...]
    recent_action_window: tuple[dict[str, Any], ...]
    casebook: tuple[dict[str, Any], ...]
    current_hypothesis: dict[str, Any] | None
    unsupported_formal_accusations: int
    last_action_result: str
