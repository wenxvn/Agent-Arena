"""Strict public contracts for the isolated V8 thirty-map runtime.

V8 keeps the same ``Action -> Environment -> Observation -> Trace`` shape as
V3/V4, but every map declares the exact action shapes it accepts. The shared
model only fixes field *types*; the per-map ``SHAPES`` table decides which
fields a tool may carry, so a map cannot silently accept another map's action.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class V8Status(StrEnum):
    RUNNING = "running"
    SUCCESS = "scenario_success"
    FAILURE = "scenario_failure"
    CENSORED = "step_limit_reached"


class V8EventClaim(BaseModel):
    """One event claim in the MAP-28/30 accusation contract."""

    model_config = ConfigDict(extra="forbid", strict=True)

    event_id: str
    time: str
    location: str
    duty_code: str


class V8Action(BaseModel):
    """One flattened action; legality is decided by the target map."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool: str
    edge_id: str | None = None
    to: str | None = None
    bearing: str | None = None
    target: str | None = None
    target_id: str | None = None
    evidence_id: str | None = None
    entry_id: str | None = None
    choice: str | None = None
    operation: str | None = None
    item_id: str | None = None
    part_id: str | None = None
    log_id: str | None = None
    test_id: str | None = None
    npc_id: str | None = None
    topic_id: str | None = None
    turns: int | None = Field(default=None, ge=1, le=8)
    day: int | None = Field(default=None, ge=1, le=60)
    slot: str | None = None
    value: int | None = None
    answer: str | None = None
    station: str | None = None
    ticks: int | None = Field(default=None, ge=1, le=8)
    train_id: str | None = None
    section_id: str | None = None
    from_node: str | None = None
    to_node: str | None = None
    next_node: str | None = None
    direction: str | None = None
    area: str | None = None
    room: str | None = None
    name: str | None = None
    item: str | None = None
    quantity: int | None = None
    slot_index: int | None = None
    sample_id: str | None = None
    device_id: str | None = None
    clue_id: str | None = None
    entrance: str | None = None
    question_template_id: str | None = None
    layout_by_room: dict[str, Any] | None = None
    configuration: list[int] | None = None
    configuration_candidate: list[int] | None = None
    claim_id: str | None = None
    forecast_next: list[int] | None = None
    read_temperature: str | None = None
    set_cooling: list[int] | None = None
    adjust_loads: list[Any] | None = None
    open_bypasses: dict[str, Any] | None = None
    set_flow_tenths: list[int] | None = None
    reinforced: bool | None = None
    loaded_return: bool | None = None
    rule_id: str | None = None
    record_id: str | None = None
    statement_ids: list[str] | None = None
    support_ids: list[str] | None = None
    against_evidence_ids: list[str] | None = None
    unreliability_proof_ids: list[str] | None = None
    unreliable_npc_id: str | None = None
    event_time: str | None = None
    event_location: str | None = None
    witness_id: str | None = None
    citations_by_claim: dict[str, Any] | None = None
    tool_ids: list[str] | None = None
    diagnosis_code: str | None = None
    arguments: dict[str, Any] | None = None
    truthful_priest_candidate: list[str] | None = None
    support_evidence_ids: list[str] | None = None
    supporting_sample_ids: list[str] | None = None
    commodity: str | None = None
    crop: str | None = None
    slots: int | None = None
    plan: list[str] | None = None
    cost_choice: Literal["fast", "safe"] | None = None
    entries: list[str] | None = None
    claims: list[dict[str, Any]] | None = None
    evidence_ids: list[str] | None = None
    entry_ids: list[str] | None = None
    shown_evidence_ids: list[str] | None = None
    shown_casebook_entry_ids: list[str] | None = None
    person_id: str | None = None
    candidate_person: str | None = None
    confidence: Literal["low", "tentative"] | None = None
    event_ids_known: list[str] | None = None
    event_claims: list[V8EventClaim] | None = None
    cited_entry_ids: list[str] | None = None
    facts: list[dict[str, Any]] | None = None
    operations: dict[str, dict[str, Any]] | None = None
    tick: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_non_null_fields(self) -> V8Action:
        if not self.tool.strip():
            raise ValueError("tool 不得为空。")
        for field in self.model_fields_set:
            if field == "tool":
                continue
            if getattr(self, field) is None:
                raise ValueError("动作的可选字段一经提交不得为空。")
        return self


class V8Observation(BaseModel):
    """Common observation core plus map-declared public fields.

    Extra fields are the map's own public state. They must come from an
    explicit allowlist in the map module; no judge-only value may be added.
    """

    model_config = ConfigDict(extra="allow", frozen=True, strict=True)

    map_id: str
    terminal: bool
    terminal_reason: str | None
    last_action_result: str

    def as_public_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class V8StepResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result: str
    status: V8Status
    observation: dict[str, Any]
    error_code: str | None = None


__all__ = [
    "V8Action",
    "V8EventClaim",
    "V8Observation",
    "V8Status",
    "V8StepResult",
]
