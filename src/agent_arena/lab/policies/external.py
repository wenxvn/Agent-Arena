"""``external``：第三方 Python Agent 接入适配器。

安全边界（明确不在范围的是“公网任意代码沙箱”）：

- 只加载**本机受信任**模块路径，通过显式 allowlist 注册；
- 插件只能拿到 ``PublicObservation`` / ``AgentContext``（含网关），拿不到
  Environment、私有状态或隐藏真值；
- 插件返回的动作仍走同一个 ``V8Action`` 校验与同一个预算网关；
- 插件异常被归类成 ``policy_error``，不会让服务进程崩溃，也不会绕过计费。
"""

from __future__ import annotations

from typing import Any, Protocol

from agent_arena.lab.adapters import (
    AgentContext,
    PublicActionResult,
    PublicEpisodeContext,
    PublicObservation,
)
from agent_arena.lab.contracts import AgentDecision, AgentIdentity
from agent_arena.lab.policies.base import call_hook, extract_action_candidate
from agent_arena.lab.registry import AgentRegistration, get_agent, register_agent


#: 第三方插件最小接口（比内置策略更宽松：只需要 ``act``）。
class CallablePlugin(Protocol):
    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]: ...


class ExternalPolicyAdapter:
    """把第三方对象适配成统一的 ``AgentPolicy``。"""

    def __init__(
        self,
        agent_id: str,
        plugin: Any,
        *,
        config: dict[str, Any] | None = None,
        identity: AgentIdentity | None = None,
    ) -> None:
        self.agent_id = agent_id
        self._plugin = plugin
        self.config = dict(config or {})
        self._identity = identity or get_agent(agent_id).identity
        self._history: list[dict[str, Any]] = []

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def reset(self, context: PublicEpisodeContext) -> None:
        self._history = []
        hook = getattr(self._plugin, "reset", None)
        if callable(hook):
            call_hook(hook, context)

    def decide(
        self, observation: PublicObservation, context: AgentContext
    ) -> AgentDecision:
        payload = observation.as_dict()
        result: Any
        decide = getattr(self._plugin, "decide", None)
        if callable(decide):
            result = decide(payload, context)
        else:
            act = getattr(self._plugin, "act", None)
            if not callable(act):
                raise TypeError(
                    "插件必须实现 decide(observation, context) 或 act(observation, history)"
                )
            result = act(payload, list(self._history[-5:]))
        requests = 0
        if isinstance(result, AgentDecision):
            return result
        if isinstance(result, dict) and "action" in result and "tool" not in result:
            action = extract_action_candidate(result.get("action"))
            requests = int(result.get("requests") or 0)
            return AgentDecision(action=action, requests=requests)
        return AgentDecision(action=extract_action_candidate(result))

    def observe_result(self, outcome: PublicActionResult) -> None:
        self._history.append(outcome.history_entry())
        hook = getattr(self._plugin, "observe_result", None)
        if callable(hook):
            call_hook(hook, outcome)

    def close(self) -> None:
        hook = getattr(self._plugin, "close", None)
        if callable(hook):
            call_hook(hook)


def register_external_plugin(
    *,
    agent_id: str,
    module: str,
    attribute: str = "make_policy",
    version: str = "0.1.0",
    display_name: str = "",
    description: str = "",
    capabilities: tuple[str, ...] = (),
    maps: tuple[str, ...] = (),
    default_config: dict[str, Any] | None = None,
    allowed_config_keys: tuple[str, ...] = (),
    extra_model_requests: bool = False,
) -> AgentRegistration:
    """注册一个本机受信任插件；返回登记项供调用方复用。"""

    identity = AgentIdentity(
        agent_id=agent_id,
        version=version,
        display_name=display_name or agent_id,
        description=description or "第三方本地策略（受信任 allowlist 加载）。",
        capabilities=capabilities or ("public_observation", "external_plugin"),
        extra_model_requests=extra_model_requests,
        maps=maps,
    )
    registration = AgentRegistration(
        identity=identity,
        default_config=dict(default_config or {}),
        allowed_config_keys=allowed_config_keys,
        module=module,
        attribute=attribute,
        trusted_local=True,
    )
    register_agent(registration)
    return registration


__all__ = [
    "CallablePlugin",
    "ExternalPolicyAdapter",
    "register_external_plugin",
]
