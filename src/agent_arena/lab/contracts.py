"""V12 Lab 版本化数据契约。

设计要点：

- ``schema_version = v12-lab-1``；V11 ``v11-web-1`` manifest/result 保持原样可读，
  旧结果缺少 V12 provenance 时由上层标记 ``legacy``，不反向补写；
- 实验是**父**，单局是**子**：``ExperimentSpec`` 冻结矩阵，``MatrixCell`` 给每个
  子局稳定的 ``matrix_index`` 与 ``condition_key``；
- 版本指纹齐全：``agent_config_hash`` / ``prompt_hash`` / ``scenario_hash`` /
  ``rule_hash`` / ``metric_hash`` / ``metric_schema_hash``；缺字段只标 unknown；
- 任何取值都不得包含密钥、隐藏真值或完整思维链。
"""

from __future__ import annotations

import json
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_arena.v10.runtime.catalog import MAP_IDS, seed_space
from agent_arena.web.clock import utc_now
from agent_arena.web.schemas import (
    LIVE_PROVIDERS,
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
)

SCHEMA_VERSION = "v12-lab-1"
AGENT_CONTRACT_VERSION = "agent_policy_v1"

#: V12 的模拟执行通道：与 V11 ``OFFLINE``（公开启发式策略）语义完全隔离。
#: 常量定义在 ``web.schemas``，由 Lab 复用，避免两处漂移。

#: 第二阶段固定重点六图。
DEFAULT_LAB_MAPS: tuple[str, ...] = (
    "MAP-08",
    "MAP-16",
    "MAP-18",
    "MAP-22",
    "MAP-26",
    "MAP-30",
)

#: 指标五态（与 V10 治理口径一致；``MISSING`` 只用于导出缺失，不伪造取值）。
METRIC_STATES: tuple[str, ...] = (
    "VALID",
    "CENSORED",
    "NOT_APPLICABLE",
    "MISSING",
    "INVALID_TRACE",
    "UNAVAILABLE",
)

MAX_EXPERIMENT_RUNS = 600
SEED_SOURCE_EXPLICIT = "explicit"
SEED_SOURCE_AUTO = "auto-common-three"


class ExperimentMode(StrEnum):
    """执行通道。``LIVE`` 才可能产生真实费用。"""

    LIVE = "live"
    SIMULATED = "simulated"


class ExperimentState(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


EXPERIMENT_TERMINAL_STATES: frozenset[ExperimentState] = frozenset(
    {
        ExperimentState.COMPLETED,
        ExperimentState.PARTIAL,
        ExperimentState.CANCELLED,
        ExperimentState.FAILED,
    }
)

EXPERIMENT_TRANSITIONS: dict[ExperimentState, frozenset[ExperimentState]] = {
    ExperimentState.CREATED: frozenset(
        {ExperimentState.QUEUED, ExperimentState.CANCELLED, ExperimentState.FAILED}
    ),
    ExperimentState.QUEUED: frozenset(
        {
            ExperimentState.RUNNING,
            ExperimentState.STOPPING,
            ExperimentState.CANCELLED,
            ExperimentState.FAILED,
        }
    ),
    ExperimentState.RUNNING: frozenset(
        {
            ExperimentState.STOPPING,
            ExperimentState.COMPLETED,
            ExperimentState.PARTIAL,
            ExperimentState.CANCELLED,
            ExperimentState.FAILED,
        }
    ),
    ExperimentState.STOPPING: frozenset(
        {
            ExperimentState.PARTIAL,
            ExperimentState.CANCELLED,
            ExperimentState.FAILED,
        }
    ),
}


def config_hash(payload: dict[str, Any]) -> str:
    """配置指纹：只对公开可序列化字段做 canonical hash。"""

    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(text.encode("utf-8")).hexdigest()


class AgentIdentity(BaseModel):
    """策略身份：注册表提供，写进每一局的 provenance。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=32)
    display_name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=600)
    capabilities: tuple[str, ...] = ()
    #: 是否可能额外产生模型请求（Planner / Reflection）。
    extra_model_requests: bool = False
    #: 空元组表示适用于全部 30 图。
    maps: tuple[str, ...] = ()
    contract_version: str = AGENT_CONTRACT_VERSION

    def applies_to(self, map_id: str) -> bool:
        return not self.maps or map_id in self.maps

    def as_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["capabilities"] = list(self.capabilities)
        payload["maps"] = list(self.maps)
        return payload


class AgentArm(BaseModel):
    """实验臂：一个策略 + 一组显式配置（消融开关通过配置表达）。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str = Field(min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)
    label: str = Field(default="", max_length=80)

    @property
    def config_hash(self) -> str:
        return config_hash({"agent_id": self.agent_id, "config": self.config})

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "config": dict(self.config),
            "label": self.label,
            "config_hash": self.config_hash,
        }


class ExperimentBudget(BaseModel):
    """实验级 + 单局级硬门禁；任何额外 Planner/Reflection 请求都计入。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    per_run_request_cap: int = Field(default=60, ge=1, le=200)
    #: 单局决策上限；为空则使用该地图登记的决策预算。
    per_run_decision_cap: int | None = Field(default=None, ge=1, le=200)
    per_run_input_token_cap: int = Field(default=200_000, ge=1_000, le=2_000_000)
    per_run_output_token_cap: int = Field(default=8_000, ge=64, le=200_000)
    per_run_cost_cap_cny: Decimal = Field(default=Decimal("1.00"), gt=0, le=Decimal("20"))
    experiment_request_cap: int = Field(default=1_200, ge=1, le=20_000)
    experiment_cost_cap_cny: Decimal = Field(default=Decimal("5.00"), gt=0, le=Decimal("200"))
    wall_clock_cap_seconds: int = Field(default=7_200, ge=60, le=86_400)
    unknown_spend_policy: Literal["stop"] = "stop"

    def as_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["per_run_cost_cap_cny"] = str(self.per_run_cost_cap_cny)
        payload["experiment_cost_cap_cny"] = str(self.experiment_cost_cap_cny)
        return payload


class LiveApproval(BaseModel):
    """真实付费实验的显式批准记录。默认未批准。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approved: bool = False
    approved_by: str = Field(default="", max_length=120)
    approved_at: str | None = None
    max_cost_cny: Decimal | None = Field(default=None, gt=0, le=Decimal("200"))
    note: str = Field(default="", max_length=600)

    def as_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "max_cost_cny": None if self.max_cost_cny is None else str(self.max_cost_cny),
            "note": self.note,
        }


class ComparisonPolicy(BaseModel):
    """配对比较口径；不可比时不得生成排名。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    paired_by: tuple[str, ...] = ("map_id", "environment_seed")
    require_same_versions: bool = True
    descriptive_only_for_small_samples: bool = True
    min_paired_samples: int = Field(default=3, ge=1, le=50)

    def as_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["paired_by"] = list(self.paired_by)
        return payload


class ExperimentSpec(BaseModel):
    """冻结的实验规格：矩阵、预算、版本口径一次写定，中途改策略必须另开实验。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    experiment_id: str = Field(default="", max_length=80)
    name: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=2_000)
    maps: list[str] = Field(min_length=1, max_length=30)
    agent_arms: list[AgentArm] = Field(min_length=1, max_length=12)
    environment_seeds: list[int] | None = None
    seed_source: str = SEED_SOURCE_EXPLICIT
    provider_id: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=120)
    mode: ExperimentMode
    execution: Literal["sequential"] = "sequential"
    budget: ExperimentBudget = Field(default_factory=ExperimentBudget)
    comparison: ComparisonPolicy = Field(default_factory=ComparisonPolicy)
    preflight_only: bool = True
    approval: LiveApproval = Field(default_factory=LiveApproval)
    created_at: str = Field(default_factory=utc_now)
    #: 只运行这些条件（`condition_key`）。空表示整张矩阵；补充实验用它挑子集。
    only_conditions: list[str] = Field(default_factory=list)
    #: 补充实验的来源：原始 `experiment_id`；普通实验为 None。
    supplement_of: str | None = Field(default=None, max_length=80)
    supplement_reason: str = Field(default="", max_length=600)
    #: 代码/契约版本指纹（由服务层写入当前值）；参与实验身份，避免"改完代码复跑
    #: 却命中旧实验"。
    runtime_version: str = Field(default="unset", max_length=120)

    # ---------------------------------------------------------------- validators
    @field_validator("maps")
    @classmethod
    def _known_maps(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("地图列表不得重复。")
        unknown = [item for item in value if item not in MAP_IDS]
        if unknown:
            raise ValueError(f"未注册的地图：{', '.join(unknown)}")
        return value

    @field_validator("agent_arms")
    @classmethod
    def _normalize_arms(cls, value: list[AgentArm]) -> list[AgentArm]:
        """把注册表默认值合并进实验臂，保证 ``config_hash`` 与运行时一致。"""

        from agent_arena.lab.registry import get_agent

        normalized: list[AgentArm] = []
        for arm in value:
            try:
                registration = get_agent(arm.agent_id)
            except KeyError:
                raise ValueError(f"未注册的策略：{arm.agent_id}") from None
            config = registration.normalize_config(arm.config)
            normalized.append(arm.model_copy(update={"config": config}))
        keys = [(arm.agent_id, arm.config_hash) for arm in normalized]
        if len(set(keys)) != len(keys):
            raise ValueError("实验臂重复：同一策略 + 同一配置只能出现一次。")
        return normalized

    @model_validator(mode="after")
    def _mode_and_seed_contract(self) -> ExperimentSpec:
        if self.mode is ExperimentMode.SIMULATED:
            if self.provider_id != SIMULATED_PROVIDER or self.model != SIMULATED_MODEL:
                raise ValueError(
                    "模拟执行必须使用 simulated_scripted / simulated-agent-policy，"
                    "不得冒充真实模型成绩。"
                )
        else:
            if self.provider_id not in LIVE_PROVIDERS:
                raise ValueError(f"真实模式只支持 {', '.join(LIVE_PROVIDERS)}。")
            if self.provider_id == SIMULATED_PROVIDER:
                raise ValueError("真实模式不能使用模拟 Provider。")
        if self.environment_seeds is not None:
            for seed in self.environment_seeds:
                for map_id in self.maps:
                    if seed not in seed_space(map_id):
                        allowed = ", ".join(str(item) for item in seed_space(map_id))
                        raise ValueError(
                            f"{map_id} 只登记了环境 seed：{allowed}（收到 {seed}）。"
                        )
        if self.budget.per_run_cost_cap_cny > self.budget.experiment_cost_cap_cny:
            raise ValueError("单局费用上限不能大于实验费用上限。")
        if self.budget.per_run_request_cap > self.budget.experiment_request_cap:
            raise ValueError("单局请求上限不能大于实验请求上限。")
        return self

    # ------------------------------------------------------------------ derived
    def resolved_seeds(self) -> tuple[int, ...]:
        """显式 seed 原样返回；否则取所有地图共同可用的前 3 个合法 seed。"""

        if self.environment_seeds is not None:
            return tuple(self.environment_seeds)
        common: set[int] | None = None
        for map_id in self.maps:
            space = set(seed_space(map_id))
            common = space if common is None else common & space
        ordered = sorted(common or set())
        if len(ordered) < 3:
            raise ValueError("这些地图没有 3 个共同可用的环境 seed；请显式指定。")
        return tuple(ordered[:3])

    def matrix(self) -> tuple[MatrixCell, ...]:
        cells: list[MatrixCell] = []
        seeds = self.resolved_seeds()
        wanted = set(self.only_conditions)
        for map_id in self.maps:
            for seed in seeds:
                for arm in self.agent_arms:
                    cell = MatrixCell(
                        matrix_index=len(cells),
                        map_id=map_id,
                        environment_seed=seed,
                        agent_id=arm.agent_id,
                        agent_version="",
                        agent_config=dict(arm.config),
                        agent_config_hash=arm.config_hash,
                    )
                    if wanted and cell.condition_key not in wanted:
                        continue
                    cells.append(cell.model_copy(update={"matrix_index": len(cells)}))
        return tuple(cells)

    def with_agent_versions(
        self, versions: dict[tuple[str, str], str]
    ) -> tuple[MatrixCell, ...]:
        """把注册表里的策略版本写进矩阵（保持 matrix_index 不变）。"""

        cells = []
        for cell in self.matrix():
            version = versions.get((cell.agent_id, cell.agent_config_hash), "")
            cells.append(cell.model_copy(update={"agent_version": version}))
        return tuple(cells)

    def fingerprint(self) -> str:
        return config_hash(
            {
                "schema_version": self.schema_version,
                "maps": list(self.maps),
                "arms": [arm.as_dict() for arm in self.agent_arms],
                "seeds": list(self.resolved_seeds()),
                "provider_id": self.provider_id,
                "model": self.model,
                "mode": self.mode.value,
                "budget": self.budget.as_dict(),
                "comparison": self.comparison.as_dict(),
                "only_conditions": sorted(self.only_conditions),
                "supplement_of": self.supplement_of,
                "runtime_version": self.runtime_version,
            }
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            **self.model_dump(mode="json"),
            "seeds": list(self.resolved_seeds()),
            "seed_source": SEED_SOURCE_EXPLICIT
            if self.environment_seeds is not None
            else SEED_SOURCE_AUTO,
            "budget": self.budget.as_dict(),
            "comparison": self.comparison.as_dict(),
            "approval": self.approval.as_dict(),
            "arms": [arm.as_dict() for arm in self.agent_arms],
            "fingerprint": self.fingerprint(),
            "only_conditions": list(self.only_conditions),
        }


class MatrixCell(BaseModel):
    """一个子局的冻结条件；``condition_key`` 是配对键的稳定来源。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    matrix_index: int = Field(ge=0)
    map_id: str
    environment_seed: int = Field(ge=0, le=9_999)
    agent_id: str
    agent_version: str = ""
    agent_config: dict[str, Any] = Field(default_factory=dict)
    agent_config_hash: str

    @property
    def condition_key(self) -> str:
        return f"{self.map_id}|seed={self.environment_seed}|{self.agent_id}"

    @property
    def pairing_key(self) -> str:
        return f"{self.map_id}|seed={self.environment_seed}"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> MatrixCell:
        """从落盘 dict 还原；忽略派生的 ``condition_key``。"""

        return cls.model_validate(
            {key: value for key, value in payload.items() if key != "condition_key"}
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "matrix_index": self.matrix_index,
            "map_id": self.map_id,
            "environment_seed": self.environment_seed,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "agent_config": dict(self.agent_config),
            "agent_config_hash": self.agent_config_hash,
            "condition_key": self.condition_key,
        }


class ChildRunLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    matrix_index: int
    run_id: str
    map_id: str
    environment_seed: int
    agent_id: str
    state: str = "CREATED"
    outcome: str | None = None
    success: bool = False
    requests: int = 0
    cost_settled_cny: str | None = None
    cost_unknown: bool = False

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ExperimentManifest(BaseModel):
    """父实验状态文件（``runs/lab/<experiment_id>/manifest.json``）。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    experiment_id: str
    name: str
    state: ExperimentState = ExperimentState.CREATED
    mode: str
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    started_at: str | None = None
    finished_at: str | None = None
    message: str | None = None
    spec: dict[str, Any] = Field(default_factory=dict)
    matrix: list[dict[str, Any]] = Field(default_factory=list)
    children: list[dict[str, Any]] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    approval: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str = ""
    idempotency_key: str | None = None

    @property
    def terminal(self) -> bool:
        return self.state in EXPERIMENT_TERMINAL_STATES

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AgentEvent(BaseModel):
    """策略侧结构化事件（计划/记忆/反思）；只含公开信息与有限摘要。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["plan", "memory", "reflection", "ablation"]
    event: str = Field(min_length=1, max_length=64)
    decision_index: int = Field(ge=0)
    summary: str = Field(default="", max_length=600)
    payload: dict[str, Any] = Field(default_factory=dict)
    requests: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AgentDecision(BaseModel):
    """一次决策：动作候选 + 可选公开摘要 + 可选结构化事件。"""

    model_config = ConfigDict(extra="forbid")

    action: dict[str, Any] | None = None
    decision_reason: str | None = Field(default=None, max_length=280)
    plan_event: AgentEvent | None = None
    memory_event: AgentEvent | None = None
    reflection_event: AgentEvent | None = None
    extra_events: list[AgentEvent] = Field(default_factory=list)
    requests: int = Field(default=0, ge=0)

    def events(self) -> list[AgentEvent]:
        found = [
            item
            for item in (
                self.plan_event,
                self.memory_event,
                self.reflection_event,
            )
            if item is not None
        ]
        return [*found, *self.extra_events]

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": None if self.action is None else dict(self.action),
            "decision_reason": self.decision_reason,
            "events": [event.as_dict() for event in self.events()],
            "requests": self.requests,
        }


class Finding(BaseModel):
    """证据驱动的结构化诊断；不含对模型内部心理的断言。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str = Field(min_length=1, max_length=64)
    severity: Literal["info", "warning", "critical"] = "warning"
    map_id: str
    run_id: str = ""
    evidence_event_ids: tuple[str, ...] = ()
    evidence_steps: tuple[int, ...] = ()
    summary: str = Field(min_length=1, max_length=600)
    detail: str = Field(default="", max_length=1_200)
    source: str = "deterministic_trace_rule"
    confidence_scope: str = "behavior_observed_not_internal_cause"
    suggested_check: str = Field(default="", max_length=600)

    def as_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["evidence_event_ids"] = list(self.evidence_event_ids)
        payload["evidence_steps"] = list(self.evidence_steps)
        return payload


class PairwiseDiff(BaseModel):
    """两条配对轨迹的事件序列对照。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pairing_key: str
    left_run_id: str
    right_run_id: str
    left_agent: str
    right_agent: str
    verdict: str = "COMPARABLE"
    reasons: tuple[str, ...] = ()
    first_divergence_step: int | None = None
    first_divergence_anchor: str = ""
    first_divergence_summary: str = ""
    left_decisions: int = 0
    right_decisions: int = 0
    left_success: bool = False
    right_success: bool = False
    stage_deltas: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["reasons"] = list(self.reasons)
        payload["stage_deltas"] = [dict(item) for item in self.stage_deltas]
        return payload


class ArmAggregate(BaseModel):
    """一个实验臂的聚合结果；五态指标不补零。"""

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    agent_version: str = ""
    runs: int = 0
    valid_denominator: int = 0
    successes: int = 0
    mechanism_failures: int = 0
    budget_censored: int = 0
    cancelled: int = 0
    provider_errors: int = 0
    interrupted: int = 0
    invalid_runs: int = 0
    success_rate: float | None = None
    mean_decisions: float | None = None
    mean_requests: float | None = None
    mean_cost_cny: float | None = None
    cost_known_runs: int = 0
    mean_latency_ms: float | None = None
    rejected_actions: int = 0
    invalid_actions: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ComparisonResult(BaseModel):
    """配对比较结果：每个实验臂 × 地图的聚合 + 逐对判定。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    experiment_id: str
    generated_at: str = Field(default_factory=utc_now)
    verdict: str = "INCOMPARABLE"
    reasons: tuple[str, ...] = ()
    arms: list[dict[str, Any]] = Field(default_factory=list)
    per_map: list[dict[str, Any]] = Field(default_factory=list)
    pairs: list[dict[str, Any]] = Field(default_factory=list)
    excluded_runs: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["reasons"] = list(self.reasons)
        return payload


__all__ = [
    "AGENT_CONTRACT_VERSION",
    "DEFAULT_LAB_MAPS",
    "EXPERIMENT_TERMINAL_STATES",
    "EXPERIMENT_TRANSITIONS",
    "MAX_EXPERIMENT_RUNS",
    "METRIC_STATES",
    "SCHEMA_VERSION",
    "SEED_SOURCE_AUTO",
    "SEED_SOURCE_EXPLICIT",
    "SIMULATED_MODEL",
    "SIMULATED_PROVIDER",
    "AgentArm",
    "AgentDecision",
    "AgentEvent",
    "AgentIdentity",
    "ArmAggregate",
    "ChildRunLink",
    "ComparisonPolicy",
    "ComparisonResult",
    "ExperimentBudget",
    "ExperimentManifest",
    "ExperimentMode",
    "ExperimentSpec",
    "ExperimentState",
    "Finding",
    "LiveApproval",
    "MatrixCell",
    "PairwiseDiff",
    "config_hash",
]
