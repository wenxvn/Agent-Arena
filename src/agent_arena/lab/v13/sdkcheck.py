"""第三方 SDK 自检与故障隔离（P2-5 / V13-11-02 … 11-06）。

自检覆盖八项（全部离线、零费用）：

1. 契约版本：``agent_policy_v1`` 仍然有效，旧插件不需要改动；
2. 公开观察：插件只拿到 ``PublicObservation`` 的字段，看不到隐藏真值；
3. 动作校验：非法动作 → ``invalid_action``，不会击穿服务；
4. 生命周期：``reset`` / ``observe_result`` / ``close`` 都会被调用；
5. 预算：插件无法绕过 ``DecisionGateway``（只能通过 context.gateway 发请求）；
6. 异常隔离：插件抛异常 → 本局 ``policy_error``，**其他 run 不受影响**；
7. 模式：SIMULATED 下不写付费账本、不产生费用；
8. 版本标识：结果里带 ``agent_version`` 与契约版本，便于报告引用。

安全边界：这只是**本机受信任插件**，不是沙箱；不支持把任意 Python 代码上传到
公网运行（``docs/v13/sdk-guide.md`` 有完整说明）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from agent_arena.lab.adapters import FORBIDDEN_PUBLIC_KEYS
from agent_arena.lab.contracts import AGENT_CONTRACT_VERSION
from agent_arena.lab.policies.external import (
    ExternalPolicyAdapter,
    register_external_plugin,
)
from agent_arena.lab.registry import clear_external_agents
from agent_arena.lab.runner import run_lab_episode
from agent_arena.lab.simulated import SimulatedDecisionProvider
from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.web.schemas import (
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
    RunConfig,
    RunMode,
)


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


class _RecordingPlugin:
    """记录钩子调用与可见字段的最小插件。"""

    def __init__(self, *, bad_action: bool = False, raise_on: int | None = None) -> None:
        self.calls: list[str] = []
        self.seen_keys: set[str] = set()
        self.bad_action = bad_action
        self.raise_on = raise_on
        self.decisions = 0

    def reset(self) -> None:
        self.calls.append("reset")

    def close(self) -> None:
        self.calls.append("close")

    def observe_result(self, outcome: Any) -> None:
        self.calls.append("observe_result")

    def decide(self, observation: dict[str, Any], context: Any) -> dict[str, Any]:
        self.calls.append("decide")
        self.decisions += 1
        self.seen_keys.update(str(key) for key in observation)
        if self.raise_on is not None and self.decisions >= self.raise_on:
            raise RuntimeError("plugin exploded with secret sk-should-not-leak-0123456789")
        if self.bad_action:
            return {"tool": "definitely_not_a_tool", "payload": "x"}
        return {"tool": "wait"}


def _config(map_id: str, agent: str) -> RunConfig:
    return RunConfig(
        map_id=map_id,
        environment_seed=0,
        mode=RunMode.SIMULATED,
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        agent=agent,
        max_decisions=6,
        max_requests=20,
        max_input_tokens=200_000,
        max_output_tokens=4_000,
        max_cost_cny=Decimal("0.10"),
    )


#: 自检期间"当前插件"（串行执行，避免为每个检查动态生成模块）。
_CURRENT_PLUGIN: Any = None
_CURRENT_AGENT_ID = ""


def _make_plugin(config: dict[str, Any] | None = None) -> Any:
    # 走真实的第三方适配器路径：插件只看到 dict 观察，动作仍走同一校验。
    return ExternalPolicyAdapter(
        _CURRENT_AGENT_ID, _CURRENT_PLUGIN, config=dict(config or {})
    )


def _install(plugin: Any, *, agent_id: str) -> None:
    global _CURRENT_PLUGIN, _CURRENT_AGENT_ID
    _CURRENT_PLUGIN = plugin
    _CURRENT_AGENT_ID = agent_id
    register_external_plugin(
        agent_id=agent_id,
        module=__name__,
        attribute="_make_plugin",
        version="0.2.0",
        display_name="SDK 自检插件",
        description="只用于离线自检，不参与任何真实实验。",
    )


def _run(plugin: Any, *, map_id: str = "MAP-22", agent_id: str = "sdkcheck.v1") -> Any:
    clear_external_agents()
    _install(plugin, agent_id=agent_id)
    environment = create_environment(map_id, environment_seed=0)
    provider = SimulatedDecisionProvider(map_id=map_id, shapes=environment.SHAPES)
    return run_lab_episode(_config(map_id, agent_id), provider=provider)


def run_sdk_checks() -> dict[str, Any]:
    """跑完整自检，返回可序列化报告。"""

    results: list[CheckResult] = []

    # 1. 契约版本
    results.append(
        CheckResult(
            "contract_version",
            AGENT_CONTRACT_VERSION == "agent_policy_v1",
            f"agent_contract_version={AGENT_CONTRACT_VERSION}（旧插件无需改动）",
        )
    )

    # 2-4. 公开观察 / 生命周期 / 动作校验（正常插件）
    plugin = _RecordingPlugin()
    outcome = _run(plugin)
    forbidden = [
        key
        for key in plugin.seen_keys
        if any(hint in key.lower() for hint in FORBIDDEN_PUBLIC_KEYS)
    ]
    results.append(
        CheckResult(
            "public_observation_only",
            not forbidden,
            f"插件可见字段 {len(plugin.seen_keys)} 个；隐藏键 {forbidden or '无'}",
        )
    )
    hooks = {"reset", "decide", "observe_result", "close"} - set(plugin.calls)
    results.append(
        CheckResult(
            "lifecycle_hooks",
            not hooks,
            f"缺失钩子：{sorted(hooks) or '无'}",
        )
    )
    results.append(
        CheckResult(
            "version_identity",
            bool(outcome.result.get("agent_version"))
            and outcome.result.get("agent_contract_version") == AGENT_CONTRACT_VERSION,
            f"agent_version={outcome.result.get('agent_version')}",
        )
    )

    # 3. 非法动作：本局继续但计入 invalid，而不是崩溃。
    bad = _RecordingPlugin(bad_action=True)
    bad_outcome = _run(bad)
    results.append(
        CheckResult(
            "invalid_action_isolated",
            bad_outcome.state.value in {"FAILED", "BUDGET_REACHED"}
            and int(bad_outcome.result.get("invalid_actions") or 0) > 0,
            f"state={bad_outcome.state.value}, invalid_actions="
            f"{bad_outcome.result.get('invalid_actions')}",
        )
    )

    # 5. 预算：插件只能通过 gateway；SIMULATED 下不产生费用。
    usage = outcome.result.get("usage") or {}
    results.append(
        CheckResult(
            "budget_and_simulated",
            str(usage.get("cost_settled_cny") or "0") in {"0", "0.0", "0.00"}
            and not usage.get("cost_unknown"),
            f"cost={usage.get('cost_settled_cny')}, requests={usage.get('requests')}",
        )
    )

    # 6. 异常隔离 + 敏感信息截断。
    boom = _RecordingPlugin(raise_on=2)
    boom_outcome = _run(boom)
    message = str(boom_outcome.result.get("message") or "")
    leaked = "sk-should-not-leak" in message
    results.append(
        CheckResult(
            "exception_isolated",
            boom_outcome.state.value == "FAILED"
            and boom_outcome.result.get("outcome") == "policy_error"
            and not leaked,
            f"state={boom_outcome.state.value}, outcome={boom_outcome.result.get('outcome')}, "
            f"leaked={leaked}",
        )
    )

    # 7. 适配器仍然接受旧式 act(observation, history)。
    class LegacyAct:
        def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
            del observation, history
            return {"tool": "wait"}

    clear_external_agents()
    _install(LegacyAct(), agent_id="sdkcheck.legacy.v1")
    adapter = ExternalPolicyAdapter("sdkcheck.legacy.v1", LegacyAct())
    results.append(
        CheckResult(
            "legacy_act_signature",
            adapter.identity.agent_id == "sdkcheck.legacy.v1",
            "act(observation, history) 旧签名仍被适配",
        )
    )

    clear_external_agents()
    failed = [item for item in results if not item.ok]
    return {
        "schema": "v13-sdk-selfcheck-1",
        "ok": not failed,
        "failed": len(failed),
        "checks": [item.as_dict() for item in results],
    }


#: 常见错误 → 可操作提示（示例 README 与 UI 共用）。
COMMON_ERRORS: dict[str, str] = {
    "TypeError: 插件必须实现": (
        "插件需要 decide(observation, context) 或 act(observation, history)。"
    ),
    "policy_error": "插件抛了异常；检查是否读取了 observation 里不存在的字段。",
    "invalid_action": "返回的动作必须是平铺对象且 tool 合法；不要包成 {'action': {...}}。",
    "ModuleNotFoundError": (
        "模块不在 allowlist；设置 AGENT_ARENA_LAB_PLUGIN_ALLOWLIST 或放到 examples/。"
    ),
    "PluginLoadError": (
        "模块不在 allowlist；设置 AGENT_ARENA_LAB_PLUGIN_ALLOWLIST 或放到 examples/ 下。"
    ),
}


def error_hint(message: str) -> str:
    for key, hint in COMMON_ERRORS.items():
        if key in message:
            return hint
    return ""


def check_plugin_factory(factory: Callable[[], Any]) -> list[str]:
    """最小接入检查：工厂必须返回带 decide/act 的对象。"""

    problems: list[str] = []
    try:
        plugin = factory()
    except Exception as exc:  # noqa: BLE001 - 自检要把问题列出来
        return [f"工厂调用失败：{type(exc).__name__}"]
    if not (hasattr(plugin, "decide") or hasattr(plugin, "act")):
        problems.append("插件缺少 decide(observation, context) 或 act(observation, history)。")
    if hasattr(plugin, "decide") and not callable(plugin.decide):
        problems.append("decide 不可调用。")
    return problems


__all__ = [
    "COMMON_ERRORS",
    "CheckResult",
    "check_plugin_factory",
    "error_hint",
    "run_sdk_checks",
]
