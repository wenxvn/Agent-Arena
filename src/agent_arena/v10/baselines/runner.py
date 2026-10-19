"""V10 公开策略执行器。

与 V9 ``run_policy`` 的差异：

- 使用 V10 catalog，显式区分 ``environment_seed`` 与 ``policy_seed``；
- 策略收到的 history 默认只有最近 ``HISTORY_WINDOW=5`` 条（与 MiMo runner 的模型
  可见窗口一致），因此“记忆”只能来自 Observation 中公开的 agent-owned 通道；
- 记录 ``scenario_hash``、``mechanism_triggered`` 与主指标五态。
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from agent_arena.v10.metrics.governance import truncation_censored
from agent_arena.v10.runtime.base import V10Map
from agent_arena.v10.runtime.catalog import create_environment, scenario_hash
from agent_arena.worlds.scenario_v8.models import V8Action

HISTORY_WINDOW = 5
REJECT_MARKERS = (
    "INVALID",
    "NO_",
    "TICK_MISMATCH",
    "TARGET_",
    "EDGE_",
    "ALREADY",
    "PHASE_OUT_OF_ORDER",
    "UNKNOWN",
    "OFF_ROUTE",
    "DISPATCH_WINDOW",
    "COMPLETED_TRAIN",
    "MEMORY_FACT",
    "EVA_SORTIE_REFUSED",
    "MANIFEST_SEALED",
    "ACTION_NOT",
)


class Policy(Protocol):
    name: str

    def reset(self) -> None: ...

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]: ...


@dataclass
class V10PolicyRun:
    map_id: str
    policy: str
    environment_seed: int
    policy_seed: int
    scenario_hash: str
    status: str
    success: bool
    terminal_reason: str | None
    decision_budget: int
    decisions: int
    invalid_actions: int
    rejected_actions: int
    mechanism_triggered: bool | None
    primary_metric: str
    primary_state: str
    primary_value: Any
    metrics: dict[str, Any] = field(default_factory=dict)
    actions: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("actions")
        return payload

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


def _status(environment: Any) -> str:
    value = environment.status.value
    return {
        "scenario_success": "success",
        "scenario_failure": "failure",
        "step_limit_reached": "censored",
    }.get(value, "decision_budget_reached")


def run_actions(
    map_id: str,
    actions: list[dict[str, Any]],
    *,
    environment_seed: int,
    name: str = "oracle",
) -> V10PolicyRun:
    """回放固定动作列表（Oracle / fixture）。"""

    queue = list(actions)

    class _Script:
        def __init__(self) -> None:
            self.name = name

        def reset(self) -> None:
            return None

        def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
            del observation, history
            return queue.pop(0) if queue else {"tool": "__end__"}

    return run_policy(
        map_id,
        _Script(),
        environment_seed=environment_seed,
        decision_budget=len(actions),
    )


def run_policy(
    map_id: str,
    policy: Policy,
    *,
    environment_seed: int = 0,
    policy_seed: int = 0,
    decision_budget: int = 46,
    history_window: int = HISTORY_WINDOW,
    keep_actions: bool = True,
) -> V10PolicyRun:
    environment = create_environment(map_id, environment_seed=environment_seed)
    observation = environment.observe()
    policy.reset()
    history: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    invalid = rejected = decisions = 0
    while not environment.is_terminal and decisions < decision_budget:
        visible = json.loads(json.dumps(observation, ensure_ascii=False))
        window = [dict(item) for item in history[-history_window:]] if history_window else []
        payload = policy.act(visible, window)
        if not isinstance(payload, dict) or not isinstance(payload.get("tool"), str):
            payload = {"tool": "__invalid__"}
        try:
            action: V8Action | None = V8Action.model_validate(payload, strict=True)
        except Exception:  # noqa: BLE001 - invalid policy output is a legal outcome
            action = None
        if action is None or not environment.accepts(action):
            result = environment.reject_invalid_action()
            invalid += 1
            record: dict[str, Any] = {"invalid_shape": payload}
        else:
            result = environment.step(action)
            if str(result.result).startswith(REJECT_MARKERS):
                rejected += 1
            record = action.model_dump(mode="json", exclude_none=True)
        observation = environment.observe()
        entry = {"action": record, "result": result.result, "observation_after": observation}
        history.append(entry)
        if keep_actions:
            actions.append({"decision": decisions + 1, **entry})
        decisions += 1
    metrics = environment.metrics()
    if isinstance(environment, V10Map):
        metrics = truncation_censored(
            map_id, metrics, truncated=not environment.is_terminal
        )
        primary = environment.PRIMARY_METRIC
        value = metrics.get(primary, {})
        primary_state = str(value.get("state"))
        primary_value = value.get("value")
        triggered: bool | None = environment.mechanism_triggered()
    else:
        primary, primary_state, primary_value, triggered = "", "UNAVAILABLE", None, None
    return V10PolicyRun(
        map_id=map_id,
        policy=policy.name,
        environment_seed=environment_seed,
        policy_seed=policy_seed,
        scenario_hash=scenario_hash(map_id, environment_seed),
        status=_status(environment),
        success=environment.is_success,
        terminal_reason=environment.terminal_reason,
        decision_budget=decision_budget,
        decisions=decisions,
        invalid_actions=invalid,
        rejected_actions=rejected,
        mechanism_triggered=triggered,
        primary_metric=primary,
        primary_state=primary_state,
        primary_value=primary_value,
        metrics=metrics,
        actions=actions,
    )


class LegalRandomPolicy:
    """从地图公开 SHAPES 采样形状合法的动作；字段值只取当前 Observation 中的字符串/数字。"""

    name = "legal_random"

    def __init__(self, shapes: dict[str, set[frozenset[str]]], seed: int) -> None:
        self.shapes = {
            tool: [sorted(shape - {"tool"}) for shape in sorted(variants, key=sorted)]
            for tool, variants in sorted(shapes.items())
        }
        self.seed = seed
        self.rng = random.Random(seed)

    def reset(self) -> None:
        self.rng = random.Random(self.seed)

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        del history
        tool = self.rng.choice(sorted(self.shapes))
        fields = self.rng.choice(self.shapes[tool])
        tokens = _tokens(observation)
        action: dict[str, Any] = {"tool": tool}
        for name in fields:
            action[name] = self._value(name, observation, tokens)
        return action

    def _value(self, name: str, observation: dict[str, Any], tokens: list[str]) -> Any:
        rng = self.rng
        if name in {"turns", "ticks"}:
            return rng.randint(1, 3)
        if name == "tick":
            current = observation.get("tick")
            return (
                int(current)
                if isinstance(current, int) and rng.random() < 0.8
                else rng.randint(0, 12)
            )
        if name == "facts":
            return [
                {"key": rng.choice(tokens or ["note"]), "value": rng.choice(tokens or ["x"])[:24]}
            ]
        if name == "operations":
            trains = sorted((observation.get("train_positions") or {}).keys())
            nodes = sorted(
                {
                    node
                    for route in (observation.get("task_routes") or {}).values()
                    for node in route
                }
            )
            operations: dict[str, Any] = {}
            for train in trains:
                roll = rng.random()
                if roll < 0.45 and nodes:
                    operations[train] = {"op": "release", "to": rng.choice(nodes)}
                elif roll < 0.5:
                    operations[train] = {
                        "op": "cancel_service",
                        "task_id": rng.choice(tokens or ["x"]),
                    }
            return operations
        return rng.choice(tokens) if tokens else "unknown"


def _tokens(observation: dict[str, Any]) -> list[str]:
    found: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, str):
            if value and len(value) <= 40:
                found.add(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                found.add(str(key))
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(observation)
    return sorted(found)


__all__ = [
    "HISTORY_WINDOW",
    "LegalRandomPolicy",
    "Policy",
    "V10PolicyRun",
    "run_actions",
    "run_policy",
]
