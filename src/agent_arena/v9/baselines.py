"""V9 基线执行器：Oracle、legal_random、public_heuristic、no_key_mechanism。

- Oracle 只用于离线可解性证明，不作为公开策略基线；
- legal_random 只从公开 Observation 与动作 schema 采样，语义非法由环境裁决；
- public_heuristic 是运行时只看公开信息的脚本策略；
- no_key_mechanism 是显式消融，定义在具体地图的 policy 模块里。
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agent_arena.v9.policies.base import PolicyRun, PublicPolicy, public_observation
from agent_arena.worlds.scenario_v8.catalog import create_environment
from agent_arena.worlds.scenario_v8.models import V8Action

PolicyFactory = Callable[[], PublicPolicy]

_TERMINAL_MARKERS = ("INVALID", "NO_", "TICK_MISMATCH", "TARGET_", "EDGE_", "ALREADY")


def run_policy(
    map_id: str,
    policy: PublicPolicy,
    *,
    seed: int = 0,
    policy_seed: int = 0,
    step_limit: int = 160,
    decision_budget: int = 30,
    condition_id: str | None = None,
) -> PolicyRun:
    environment = create_environment(
        map_id, seed=seed, step_limit=step_limit, condition_id=condition_id
    )
    observation = environment.observe()
    policy.reset()
    history: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    invalid = 0
    rejected = 0
    decisions = 0
    status = "decision_budget_reached"
    while not environment.is_terminal and decisions < decision_budget:
        safe_observation = public_observation(observation)
        payload = policy.act(safe_observation, [dict(item) for item in history])
        if not isinstance(payload, dict) or not isinstance(payload.get("tool"), str):
            payload = {"tool": "__invalid__"}
        try:
            action = V8Action.model_validate(payload, strict=True)
        except Exception:  # noqa: BLE001 - the policy produced an invalid shape
            action = None
        if action is None:
            result = environment.reject_invalid_action()
            invalid += 1
            action_record: dict[str, Any] = {"invalid_shape": payload}
        else:
            result = environment.step(action)
            if str(result.result).startswith(_TERMINAL_MARKERS):
                rejected += 1
            action_record = action.model_dump(mode="json", exclude_none=True)
        observations_after = environment.observe()
        actions.append(
            {
                "decision": decisions + 1,
                "action": action_record,
                "result": result.result,
                "status": result.status.value,
                "observation_after": observations_after,
            }
        )
        history.append(
            {
                "action": action_record,
                "result": result.result,
                "observation_after": observations_after,
            }
        )
        observation = observations_after
        decisions += 1
        if result.status.value == "scenario_success":
            status = "success"
        elif result.status.value == "scenario_failure":
            status = "failure"
        elif result.status.value == "step_limit_reached":
            status = "censored"
    if environment.is_success:
        status = "success"
    elif environment.status.value == "scenario_failure":
        status = "failure"
    elif environment.status.value == "step_limit_reached":
        status = "censored"
    return PolicyRun(
        map_id=map_id,
        policy=policy.name,
        seed=seed,
        status=status,
        success=environment.is_success,
        terminal_reason=environment.terminal_reason,
        decision_budget=decision_budget,
        decisions=decisions,
        invalid_actions=invalid,
        rejected_actions=rejected,
        policy_seed=policy_seed,
        actions=actions,
        metrics=environment.metrics(),
        failure_codes=failure_codes(status, environment, invalid),
    )


def failure_codes(status: str, environment: Any, invalid: int) -> list[str]:
    codes: list[str] = []
    if status in {"censored", "decision_budget_reached"}:
        codes.append("CENSORED")
    if invalid:
        codes.append("INVALID_ACTION")
    if environment.terminal_reason:
        codes.append(str(environment.terminal_reason))
    if not codes:
        codes.append("SUCCESS" if status == "success" else "UNCLASSIFIED_OUTCOME")
    return sorted(set(codes))


@dataclass(frozen=True)
class ShapeSampler:
    """从公开动作 schema 采样形状合法、语义未必合法的动作。

    字段值只来自当前 Observation 中出现过的字符串/数字，因此不会读取隐藏状态。
    """

    shapes: dict[str, list[set[str]]]
    vocabulary: dict[str, tuple[str, ...]]

    @classmethod
    def from_environment(
        cls, environment: Any, vocabulary: dict[str, tuple[str, ...]]
    ) -> ShapeSampler:
        # 动作形状来自 set，必须显式排序；否则跨进程的 PYTHONHASHSEED 会改变
        # 随机策略的采样序列，使基线不可重放。
        shapes = {
            tool: [set(shape) for shape in sorted(variants, key=lambda item: sorted(item))]
            for tool, variants in sorted(environment.SHAPES.items())
        }
        return cls(shapes=shapes, vocabulary=vocabulary)

    def sample(self, observation: dict[str, Any], rng: random.Random) -> dict[str, Any]:
        tool = rng.choice(sorted(self.shapes))
        shape = rng.choice(self.shapes[tool])
        fields = sorted(shape - {"tool"})
        action: dict[str, Any] = {"tool": tool}
        tokens = _string_tokens(observation)
        numbers = _numbers(observation)
        for field in fields:
            action[field] = self._value(field, tokens, numbers, rng)
        return action

    def _value(
        self,
        field: str,
        tokens: list[str],
        numbers: list[int],
        rng: random.Random,
    ) -> Any:
        if field in {"turns", "ticks"}:
            return rng.randint(1, 3)
        if field in {"quantity", "slots", "value"}:
            return rng.randint(1, 3)
        if field in {"tick"}:
            return rng.randint(0, 3)
        if field in {"day"}:
            return rng.randint(1, 3)
        if field in {"slot_index"}:
            return rng.randint(1, 4)
        if field in {"configuration", "forecast_next", "set_cooling", "set_flow_tenths"}:
            return [rng.randint(0, 2) for _ in range(3)]
        if field in {
            "adjust_loads",
            "operations",
            "layout_by_room",
            "open_bypasses",
            "facts",
            "claims",
            "arguments",
            "citations_by_claim",
        }:
            return {}
        if field in {
            "evidence_ids",
            "entry_ids",
            "statement_ids",
            "support_ids",
            "tool_ids",
            "event_ids_known",
            "cited_entry_ids",
            "against_evidence_ids",
            "unreliability_proof_ids",
            "plan",
            "entries",
            "shown_evidence_ids",
            "shown_casebook_entry_ids",
        }:
            return [rng.choice(tokens)] if tokens else []
        if field in {"event_claims"}:
            return []
        if field == "confidence":
            return rng.choice(["low", "tentative"])
        if field == "cost_choice":
            return rng.choice(["fast", "safe"])
        if field in {"reinforced", "loaded_return"}:
            return bool(rng.getrandbits(1))
        if field == "direction":
            return rng.choice(["north", "south", "east", "west"])
        if tokens:
            return rng.choice(tokens)
        return "unknown"


def _string_tokens(observation: dict[str, Any]) -> list[str]:
    tokens: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, str):
            if value not in {"", "READY"} and len(value) <= 40:
                tokens.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                tokens.append(str(key))
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(observation)
    return sorted(set(tokens))


def _numbers(observation: dict[str, Any]) -> list[int]:
    values: list[int] = []

    def visit(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int):
            values.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(observation)
    return values


class RandomPolicy:
    """公开 Observation + 动作 schema 的合法形状随机基线。"""

    name = "legal_random"

    def __init__(self, sampler: ShapeSampler, seed: int = 0) -> None:
        self.sampler = sampler
        self.seed = seed
        self.rng = random.Random(seed)

    def reset(self) -> None:
        self.rng = random.Random(self.seed)

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        del history
        return self.sampler.sample(observation, self.rng)


__all__ = ["PolicyFactory", "RandomPolicy", "ShapeSampler", "run_policy"]
