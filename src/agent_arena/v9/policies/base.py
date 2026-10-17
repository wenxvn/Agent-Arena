"""V9 公开策略基线框架。

策略在运行时只接收公开 Observation、公开动作 schema 与自己的历史记录；
不得访问 Environment、judge_state、Oracle 动作或指标内部状态。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol, cast


class PublicPolicy(Protocol):
    name: str

    def reset(self) -> None: ...

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]: ...


@dataclass
class PolicyRun:
    """一次公开策略 episode 的可复算记录。"""

    map_id: str
    policy: str
    seed: int
    status: str
    success: bool
    terminal_reason: str | None
    decision_budget: int
    decisions: int
    invalid_actions: int
    rejected_actions: int = 0
    policy_seed: int = 0
    actions: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    failure_codes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "policy": self.policy,
            "seed": self.seed,
            "policy_seed": self.policy_seed,
            "status": self.status,
            "success": self.success,
            "terminal_reason": self.terminal_reason,
            "decision_budget": self.decision_budget,
            "decisions": self.decisions,
            "invalid_actions": self.invalid_actions,
            "rejected_actions": self.rejected_actions,
            "actions": self.actions,
            "metrics": self.metrics,
            "failure_codes": self.failure_codes,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True)


def public_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Deep copy so a policy cannot mutate the environment's observation."""

    return cast(dict[str, Any], json.loads(json.dumps(observation, ensure_ascii=False)))


__all__ = ["PolicyRun", "PublicPolicy", "public_observation"]
