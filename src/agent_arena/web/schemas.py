"""V11 服务层的数据契约。

设计要点：

- ``RunConfig`` 不可变，字段全部有范围；地图与 seed 必须命中 V10 catalog。
- 状态机显式声明，避免把 ``CENSORED``（指标五态）与运行状态混为一谈。
- ``RunStatus``/``RunSummary`` 只包含可安全展示的字段，不携带密钥。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_arena.web.clock import utc_now

SCHEMA_VERSION = "v11-web-1"

OFFLINE_PROVIDER = "offline_public_policy"
OFFLINE_MODEL = "public-heuristic-policy"
LIVE_PROVIDERS = ("openai_compatible", "ollama")

#: V12 新增的模拟通道。与 ``OFFLINE`` 完全隔离：``OFFLINE`` 仍是公开启发式策略，
#: 这里跑的是受控 Fake/Scripted Provider 下的 Lab Agent，成绩只能标 SIMULATED。
SIMULATED_PROVIDER = "simulated_scripted"
SIMULATED_MODEL = "simulated-agent-policy"

#: V11 唯一的内置真实执行器 id；V12 的 Lab 策略使用 ``<name>.v1`` 形式。
LEGACY_LIVE_AGENT = "v10_action_loop"


class RunMode(StrEnum):
    OFFLINE = "offline"
    LIVE = "live"
    SIMULATED = "simulated"


class RunState(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BUDGET_REACHED = "BUDGET_REACHED"
    CANCELLED = "CANCELLED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INTERRUPTED = "INTERRUPTED"


TERMINAL_STATES: frozenset[RunState] = frozenset(
    {
        RunState.SUCCEEDED,
        RunState.FAILED,
        RunState.BUDGET_REACHED,
        RunState.CANCELLED,
        RunState.PROVIDER_ERROR,
        RunState.INTERRUPTED,
    }
)

#: 合法的状态迁移；服务层在写入前检查，测试直接覆盖。
ALLOWED_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset({RunState.QUEUED, RunState.CANCELLED, RunState.INTERRUPTED}),
    RunState.QUEUED: frozenset(
        {RunState.RUNNING, RunState.CANCELLED, RunState.INTERRUPTED}
    ),
    RunState.RUNNING: frozenset(
        {
            RunState.SUCCEEDED,
            RunState.FAILED,
            RunState.BUDGET_REACHED,
            RunState.CANCELLED,
            RunState.PROVIDER_ERROR,
            RunState.INTERRUPTED,
        }
    ),
}


class RunConfig(BaseModel):
    """一局挑战的完整、不可变配置。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    map_id: str
    environment_seed: int = Field(ge=0, le=9_999)
    mode: RunMode
    provider_id: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=120)
    agent: str = Field(default="v10_action_loop", min_length=1, max_length=64)
    #: V12 Lab 策略的显式配置（消融开关在这里表达；空 dict = 用注册表默认值）。
    agent_config: dict[str, Any] = Field(default_factory=dict)
    #: 父实验与矩阵位置（V11 单局为空）。
    experiment_id: str | None = Field(default=None, max_length=80)
    matrix_index: int | None = Field(default=None, ge=0, le=10_000)
    #: V13：第几次独立重复（0 = 原始观测）；旧 manifest 缺省按 0 读取。
    replicate_index: int = Field(default=0, ge=0, le=10)
    policy_seed: int = Field(default=0, ge=0, le=9_999)
    max_decisions: int = Field(ge=1, le=200)
    max_requests: int = Field(ge=1, le=200)
    max_input_tokens: int = Field(ge=1_000, le=2_000_000)
    max_output_tokens: int = Field(ge=64, le=200_000)
    max_cost_cny: Decimal = Field(default=Decimal("1.00"), gt=0, le=Decimal("20"))
    created_at: str = Field(default_factory=utc_now)
    idempotency_key: str | None = Field(default=None, max_length=200)

    @field_validator("map_id")
    @classmethod
    def _known_map(cls, value: str) -> str:
        from agent_arena.v10.runtime.catalog import MAP_IDS

        if value not in MAP_IDS:
            raise ValueError(f"未注册的地图：{value}")
        return value

    @field_validator("model")
    @classmethod
    def _bounded_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or any(character.isspace() for character in cleaned):
            raise ValueError("模型名不能为空或包含空白字符。")
        if "://" in cleaned:
            raise ValueError("模型名不能是 URL；自定义地址请写入本机 .env。")
        return cleaned

    @model_validator(mode="after")
    def _mode_contract(self) -> RunConfig:
        from agent_arena.v10.runtime.catalog import seed_space

        if self.environment_seed not in seed_space(self.map_id):
            allowed = ", ".join(str(seed) for seed in seed_space(self.map_id))
            raise ValueError(f"{self.map_id} 只登记了环境 seed：{allowed}")
        if self.mode is RunMode.OFFLINE:
            if self.provider_id != OFFLINE_PROVIDER or self.model != OFFLINE_MODEL:
                raise ValueError("离线模式必须使用公开规则策略，不得伪装成模型挑战。")
            if self.agent != "public_heuristic_policy":
                raise ValueError("离线模式的 agent 必须是 public_heuristic_policy。")
        elif self.mode is RunMode.SIMULATED:
            if self.provider_id != SIMULATED_PROVIDER or self.model != SIMULATED_MODEL:
                raise ValueError(
                    "模拟模式必须使用 simulated_scripted / simulated-agent-policy。"
                )
            from agent_arena.lab.registry import get_agent

            try:
                registration = get_agent(self.agent)
            except KeyError:
                raise ValueError(f"模拟模式只接受已注册的 Lab 策略：{self.agent}") from None
            registration.normalize_config(self.agent_config)
        else:
            if self.provider_id not in LIVE_PROVIDERS:
                raise ValueError(f"真实模式只支持 {', '.join(LIVE_PROVIDERS)}。")
            from agent_arena.lab.registry import get_agent

            if self.agent != LEGACY_LIVE_AGENT:
                # V11 只实现了一种真实执行器；显式拒绝未知 agent，避免静默按
                # ``v10_action_loop`` 运行而让结果被误读成别的架构。
                try:
                    registration = get_agent(self.agent)
                except KeyError:
                    raise ValueError(f"未注册的 agent：{self.agent}") from None
                registration.normalize_config(self.agent_config)
        if self.max_output_tokens > self.max_input_tokens:
            raise ValueError("max_output_tokens 不能大于 max_input_tokens。")
        return self

    def public_dict(self) -> dict[str, Any]:
        """导出到页面/结果文件的配置（不含任何密钥字段）。"""

        return self.model_dump(mode="json")


@dataclass(frozen=True)
class RunStatus:
    run_id: str
    state: RunState
    config: dict[str, Any]
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    attempt_id: str | None = None
    decisions: int = 0
    decision_budget: int = 0
    outcome: str | None = None
    termination: str | None = None
    message: str | None = None
    budget: dict[str, Any] = field(default_factory=dict)
    progress: float = 0.0

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> RunStatus:
        config = manifest.get("config")
        budget = manifest.get("budget")
        return cls(
            run_id=str(manifest.get("run_id", "")),
            state=RunState(str(manifest.get("state", RunState.CREATED.value))),
            config=dict(config) if isinstance(config, dict) else {},
            created_at=str(manifest.get("created_at", "")),
            updated_at=str(manifest.get("updated_at", "")),
            started_at=_optional_str(manifest.get("started_at")),
            finished_at=_optional_str(manifest.get("finished_at")),
            attempt_id=_optional_str(manifest.get("attempt_id")),
            decisions=int(manifest.get("decisions") or 0),
            decision_budget=int(manifest.get("decision_budget") or 0),
            outcome=_optional_str(manifest.get("outcome")),
            termination=_optional_str(manifest.get("termination")),
            message=_optional_str(manifest.get("message")),
            budget=dict(budget) if isinstance(budget, dict) else {},
            progress=float(manifest.get("progress") or 0.0),
        )

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL_STATES


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    map_id: str
    world: str
    mode: str
    provider_id: str
    model: str
    environment_seed: int
    state: str
    outcome: str | None
    success: bool
    decisions: int
    created_at: str
    finished_at: str | None
    cost_settled_cny: float | None
    cost_unknown: bool
    rule_hash: str | None
    metric_hash: str | None
    metric_schema_hash: str | None = None
    display_title: str = ""
    decision_budget: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "map_id": self.map_id,
            "world": self.world,
            "mode": self.mode,
            "provider_id": self.provider_id,
            "model": self.model,
            "environment_seed": self.environment_seed,
            "state": self.state,
            "outcome": self.outcome,
            "success": self.success,
            "decisions": self.decisions,
            "decision_budget": self.decision_budget,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "cost_settled_cny": self.cost_settled_cny,
            "cost_unknown": self.cost_unknown,
            "rule_hash": self.rule_hash,
            "metric_hash": self.metric_hash,
            "metric_schema_hash": self.metric_schema_hash,
            "display_title": self.display_title,
        }


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


__all__ = [
    "ALLOWED_TRANSITIONS",
    "LEGACY_LIVE_AGENT",
    "LIVE_PROVIDERS",
    "OFFLINE_MODEL",
    "OFFLINE_PROVIDER",
    "SCHEMA_VERSION",
    "SIMULATED_MODEL",
    "SIMULATED_PROVIDER",
    "TERMINAL_STATES",
    "RunConfig",
    "RunMode",
    "RunState",
    "RunStatus",
    "RunSummary",
]
