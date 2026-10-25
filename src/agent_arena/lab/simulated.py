"""``SIMULATED`` 通道：确定性脚本 Provider（零网络、零费用）。

用途与边界：

- 让 Basic/Memory/Planning/Reflection 的**完整调用链**（含 Planner/Reflection 额外
  请求）在没有 API Key、没有任何付费请求的情况下跑通；
- 结果必须显式标注 ``mode=simulated``，绝不混入真实模型成绩；
- 只读取公开 ``Observation`` 与地图**公开**动作契约（``SHAPES`` 已写进 prompt），
  不使用 Oracle 动作序列，也不读取任何隐藏真值；
- 行为确定：同一 (map, seed, request_index) 永远给出同一候选。

两种策略：

- ``deterministic_cycle``（默认）：按工具名字典序循环，用公开 Observation 中的词元
  填充字段，产出形状合法但**不保证正确**的动作；
- ``scripted``：由测试显式传入动作脚本，用于覆盖成功/失败/截断等通路。
"""

from __future__ import annotations

import json
from typing import Any

from agent_arena.llm.protocol import DecisionRequest, ProviderResponse
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER, RunConfig
from agent_arena.worlds.scenario_v8.models import V8Action, V8Observation

STRATEGY_CYCLE = "deterministic_cycle"
STRATEGY_SCRIPTED = "scripted"

_NUMERIC_DEFAULTS: dict[str, int] = {
    "turns": 1,
    "ticks": 1,
    "tick": 0,
    "day": 1,
    "value": 1,
    "quantity": 1,
    "slot_index": 0,
}


def _tokens(payload: Any) -> list[str]:
    """收集公开观察里的短词元，用于填字段值（与 V10 合法随机策略同思路）。"""

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

    visit(payload)
    return sorted(found)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.encode("utf-8")) // 4)


class SimulatedDecisionProvider:
    """确定性脚本 Provider；接口与真实 Provider 完全一致。"""

    provider_id = SIMULATED_PROVIDER
    model = SIMULATED_MODEL

    def __init__(
        self,
        *,
        map_id: str,
        shapes: dict[str, set[frozenset[str]]],
        strategy: str = STRATEGY_CYCLE,
        script: list[dict[str, Any]] | None = None,
        policy_seed: int = 0,
    ) -> None:
        self.map_id = map_id
        self.shapes = {
            tool: [sorted(shape - {"tool"}) for shape in sorted(variants, key=sorted)]
            for tool, variants in sorted(shapes.items())
        }
        self.tools = sorted(self.shapes)
        self.strategy = strategy
        self.script = list(script or [])
        self.policy_seed = policy_seed
        self.requests = 0
        #: 供测试与自检核对请求文本；有界，避免长局占用内存。
        self.calls: list[DecisionRequest] = []

    # -------------------------------------------------------------------- decide
    def decide(self, request: DecisionRequest) -> ProviderResponse:
        observation = request.observation
        self.calls.append(request)
        if len(self.calls) > 400:
            self.calls = self.calls[-400:]
        payload = (
            observation.model_dump(mode="json")
            if isinstance(observation, V8Observation)
            else {}
        )
        candidate = self._candidate(payload, request)
        self.requests += 1
        input_text = (request.system_prompt or "") + json.dumps(
            payload, ensure_ascii=False, sort_keys=True
        )
        output_text = json.dumps(candidate, ensure_ascii=False, sort_keys=True)
        return ProviderResponse(
            candidate=candidate,
            input_tokens=_estimate_tokens(input_text),
            output_tokens=_estimate_tokens(output_text),
            cached_input_tokens=0,
        )

    def _candidate(
        self, observation: dict[str, Any], request: DecisionRequest
    ) -> dict[str, Any]:
        if self.strategy == STRATEGY_SCRIPTED:
            index = self.requests
            if index < len(self.script):
                return dict(self.script[index])
            # 脚本用完后回到确定性循环，避免把“脚本结束”伪装成契约失败。
        return self._cycle(observation)

    def _cycle(self, observation: dict[str, Any]) -> dict[str, Any]:
        if not self.tools:
            return {"tool": "__no_tool__"}
        index = self.requests + self.policy_seed
        tool = self.tools[index % len(self.tools)]
        variants = self.shapes[tool]
        fields = variants[index % len(variants)]
        tokens = _tokens(observation)
        action: dict[str, Any] = {"tool": tool}
        for position, name in enumerate(fields):
            action[name] = self._value(name, observation, tokens, index + position)
        return action

    def _value(
        self,
        name: str,
        observation: dict[str, Any],
        tokens: list[str],
        index: int,
    ) -> Any:
        if name in _NUMERIC_DEFAULTS:
            current = observation.get(name)
            if name == "tick" and isinstance(current, int):
                return current
            return _NUMERIC_DEFAULTS[name]
        if name == "facts":
            token = tokens[index % len(tokens)] if tokens else "note"
            return [{"key": token, "value": token[:24]}]
        if name == "operations":
            return {}
        if name == "plan":
            return []
        if name in {"evidence_ids", "entry_ids", "support_ids", "tool_ids"}:
            return []
        if name in {"claims", "event_claims", "entries"}:
            return []
        if name in {"layout_by_room", "citations_by_claim", "open_bypasses", "arguments"}:
            return {}
        if name in {"configuration", "configuration_candidate", "forecast_next"}:
            return []
        if name == "cost_choice":
            return "safe"
        if name == "confidence":
            return "low"
        if name == "reinforced" or name == "loaded_return":
            return False
        if name == "slots":
            return 1
        return tokens[index % len(tokens)] if tokens else "unknown"


def build_simulated_provider(config: RunConfig) -> SimulatedDecisionProvider:
    """按 ``RunConfig`` 构造模拟 Provider（只读公开 ``SHAPES``）。"""

    from agent_arena.v10.runtime.catalog import create_environment

    environment = create_environment(config.map_id, environment_seed=config.environment_seed)
    return SimulatedDecisionProvider(
        map_id=config.map_id,
        shapes=environment.SHAPES,
        policy_seed=config.policy_seed,
    )


def scripted_provider(
    map_id: str, actions: list[dict[str, Any]], *, policy_seed: int = 0
) -> SimulatedDecisionProvider:
    """测试/演示用脚本 Provider；动作来自调用方，不是 Oracle。"""

    from agent_arena.v10.runtime.catalog import create_environment

    environment = create_environment(map_id, environment_seed=0)
    return SimulatedDecisionProvider(
        map_id=map_id,
        shapes=environment.SHAPES,
        strategy=STRATEGY_SCRIPTED,
        script=actions,
        policy_seed=policy_seed,
    )


def validate_candidate_shapes(
    map_id: str, actions: list[dict[str, Any]]
) -> list[str]:
    """自检工具：脚本动作是否至少形状合法（返回问题列表）。"""

    from agent_arena.v10.runtime.catalog import create_environment

    environment = create_environment(map_id, environment_seed=0)
    problems: list[str] = []
    for index, action in enumerate(actions, start=1):
        try:
            parsed = V8Action.model_validate(action, strict=True)
        except Exception:  # noqa: BLE001 - 自检要把问题列出来
            problems.append(f"#{index} 不是合法 V8Action：{action}")
            continue
        if not environment.accepts(parsed):
            problems.append(f"#{index} 形状不被 {map_id} 接受：{sorted(action)}")
    return problems


__all__ = [
    "STRATEGY_CYCLE",
    "STRATEGY_SCRIPTED",
    "SimulatedDecisionProvider",
    "build_simulated_provider",
    "scripted_provider",
    "validate_candidate_shapes",
]
