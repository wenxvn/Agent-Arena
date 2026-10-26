"""Lab 策略与可视化注册表。

设计要点：

- 注册表**只保存元数据**（``AgentIdentity`` + 默认配置 + 懒加载工厂路径），
  顶层不导入策略实现，避免 ``web.schemas`` ↔ ``lab`` 的循环导入；
- 网页与 CLI 通过本注册表取策略清单，不在 UI 里硬编码 if/else 分支；
- 第三方插件只能通过显式 allowlist 的本地模块路径注册，不提供任意代码沙箱。
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agent_arena.lab.contracts import AgentIdentity

#: 策略工厂签名：``factory(config: dict) -> AgentPolicy``。
PolicyFactory = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class AgentRegistration:
    """一个可运行的策略：身份、默认配置、配置约束与懒加载工厂。"""

    identity: AgentIdentity
    default_config: dict[str, Any] = field(default_factory=dict)
    #: 允许出现在配置里的键；空元组表示不限制（第三方插件自检）。
    allowed_config_keys: tuple[str, ...] = ()
    module: str = ""
    attribute: str = ""
    trusted_local: bool = True

    @property
    def agent_id(self) -> str:
        return self.identity.agent_id

    def factory(self) -> PolicyFactory:
        if not self.module or not self.attribute:
            raise LookupError(f"策略 {self.agent_id} 没有可加载的工厂。")
        module = importlib.import_module(self.module)
        factory: PolicyFactory = getattr(module, self.attribute)
        return factory

    def normalize_config(self, config: dict[str, Any] | None) -> dict[str, Any]:
        """合并默认配置并拒绝未知键；配置变化必然改变 ``config_hash``。"""

        merged = {**self.default_config, **dict(config or {})}
        if self.allowed_config_keys:
            unknown = sorted(set(merged) - set(self.allowed_config_keys))
            if unknown:
                raise ValueError(
                    f"{self.agent_id} 不认识的配置项：{', '.join(unknown)}"
                )
        return merged


def _identity(
    agent_id: str,
    display_name: str,
    description: str,
    capabilities: tuple[str, ...],
    *,
    version: str = "1.0.0",
    extra_model_requests: bool = False,
    maps: tuple[str, ...] = (),
) -> AgentIdentity:
    return AgentIdentity(
        agent_id=agent_id,
        version=version,
        display_name=display_name,
        description=description,
        capabilities=capabilities,
        extra_model_requests=extra_model_requests,
        maps=maps,
    )


BUILTIN_AGENTS: tuple[AgentRegistration, ...] = (
    AgentRegistration(
        identity=_identity(
            "basic.v1",
            "Basic · 基线行动循环",
            "沿用 V10 公开提示、动作契约与最近 5 条历史窗口的单次决策循环；"
            "作为与其它架构对照的基线锚点。",
            ("public_observation", "five_step_history", "single_request_per_decision"),
        ),
        default_config={"history_window": 5},
        allowed_config_keys=("history_window",),
        module="agent_arena.lab.policies.basic",
        attribute="BasicPolicy",
    ),
    AgentRegistration(
        identity=_identity(
            "memory.v1",
            "Memory · 结构化公开记忆",
            "在 episode 内维护结构化公开事实（当前状态、已发现事实、被拒动作、"
            "关键里程碑），按容量与窗口淘汰；默认不增加模型请求，可关闭做消融。",
            (
                "public_observation",
                "structured_memory",
                "memory_ablation",
                "five_step_history",
            ),
        ),
        default_config={
            "enabled": True,
            "capacity": 24,
            "history_window": 5,
            "max_chars": 1_200,
            # 路线日志（DCR-V12-03）：按步把走过的方位写成 path_state。
            # 这是**策略变量**，不是环境改动；关闭时与原 memory.v1 完全一致。
            "route_log": False,
            "route_write_every": 2,
            "route_write_limit": 24,
        },
        allowed_config_keys=(
            "enabled",
            "capacity",
            "history_window",
            "max_chars",
            "route_log",
            "route_write_every",
            "route_write_limit",
        ),
        module="agent_arena.lab.policies.memory",
        attribute="MemoryPolicy",
    ),
    AgentRegistration(
        identity=_identity(
            "planning.v1",
            "Planning · 高层子目标",
            "由公开事实生成子目标与完成条件，事件触发重规划；Planner 只建议目标，"
            "不执行动作，额外请求全部计入预算与账本。",
            (
                "public_observation",
                "planner_requests",
                "plan_monitor",
                "replan_on_stall",
                "planning_ablation",
            ),
            extra_model_requests=True,
        ),
        default_config={
            "enabled": True,
            "replan_every": 6,
            "max_plans": 8,
            "history_window": 5,
        },
        allowed_config_keys=("enabled", "replan_every", "max_plans", "history_window"),
        module="agent_arena.lab.policies.planning",
        attribute="PlanningPolicy",
    ),
    AgentRegistration(
        identity=_identity(
            "reflection.v1",
            "Reflection · 条件反思",
            "由连续无进展、重复被拒动作、关键阶段回退等**公开触发器**触发的有限次"
            "反思；输出公开改进建议与重规划事件，不读取隐藏进度。",
            (
                "public_observation",
                "reflection_triggers",
                "bounded_reflection_requests",
                "reflection_ablation",
            ),
            extra_model_requests=True,
        ),
        default_config={
            "enabled": True,
            "max_reflections": 3,
            "cooldown_steps": 4,
            "stall_threshold": 3,
            "reject_threshold": 2,
            "history_window": 5,
        },
        allowed_config_keys=(
            "enabled",
            "max_reflections",
            "cooldown_steps",
            "stall_threshold",
            "reject_threshold",
            "history_window",
        ),
        module="agent_arena.lab.policies.reflection",
        attribute="ReflectionPolicy",
    ),
    # ------------------------------------------------------------ V13 新增版本
    AgentRegistration(
        identity=_identity(
            "memory.v2",
            "Memory v2 · 可审计路线记忆",
            "在 v1 的结构化记忆之上，默认开启按步路线日志（只累积被接受的 move），"
            "并记录循环/折返/被拒、压缩与相关性排序、以及三类记忆瓶颈分类；"
            "路线写入机制（环境动作 vs 纯上下文）显式区分，默认行为与 v1 不同。",
            (
                "public_observation",
                "structured_memory",
                "route_log",
                "memory_ablation",
                "five_step_history",
            ),
            version="2.0.0",
        ),
        default_config={
            "enabled": True,
            "capacity": 32,
            "history_window": 5,
            "max_chars": 1_600,
            "route_log": True,
            "route_mode": "env_write",
            "route_write_every": 2,
            "route_write_limit": 24,
            "compress": True,
            "dedupe": True,
            "relevance": True,
        },
        allowed_config_keys=(
            "enabled",
            "capacity",
            "history_window",
            "max_chars",
            "route_log",
            "route_mode",
            "route_write_every",
            "route_write_limit",
            "compress",
            "dedupe",
            "relevance",
        ),
        module="agent_arena.lab.policies.memory_v2",
        attribute="make_memory_v2",
    ),
    AgentRegistration(
        identity=_identity(
            "planning.v2",
            "Planning v2 · 可配置规划节流",
            "把重规划拆成三个可分别开关的因子（initial_only / periodic / adaptive），"
            "加入 TTL 下限、预算感知与逐请求成本记录；Planner 仍只输出非执行性计划字段。",
            (
                "public_observation",
                "planner_requests",
                "plan_monitor",
                "replan_on_stall",
                "planning_ablation",
                "plan_cost_ledger",
            ),
            version="2.0.0",
            extra_model_requests=True,
        ),
        default_config={
            "enabled": True,
            "planner_mode": "adaptive",
            "min_steps_between_plans": 4,
            "stall_threshold": 4,
            "reject_threshold": 2,
            "max_plans": 6,
            "budget_aware": True,
            "history_window": 5,
        },
        allowed_config_keys=(
            "enabled",
            "planner_mode",
            "min_steps_between_plans",
            "stall_threshold",
            "reject_threshold",
            "max_plans",
            "budget_aware",
            "history_window",
        ),
        module="agent_arena.lab.policies.planning_v2",
        attribute="make_planning_v2",
    ),
    AgentRegistration(
        identity=_identity(
            "reflection.v2",
            "Reflection v2 · 可验证激活",
            "把触发、可触发（eligible）、真正触发（triggered）、冷却/额度阻挡、"
            "误触发与触发后恢复分开计数；支持 trigger-only 对照臂；"
            "零触发时输出 NO_TREATMENT_EXPOSURE 而不是「反思无效」。",
            (
                "public_observation",
                "reflection_triggers",
                "activation_rate",
                "recovery_rate",
                "trigger_only_control",
                "bounded_reflection_requests",
            ),
            version="2.0.0",
            extra_model_requests=True,
        ),
        default_config={
            "enabled": True,
            "trigger_only": False,
            "max_reflections": 3,
            "cooldown_steps": 4,
            "stall_threshold": 3,
            "reject_threshold": 2,
            "recovery_window": 3,
            "history_window": 5,
        },
        allowed_config_keys=(
            "enabled",
            "trigger_only",
            "max_reflections",
            "cooldown_steps",
            "stall_threshold",
            "reject_threshold",
            "recovery_window",
            "history_window",
        ),
        module="agent_arena.lab.policies.reflection_v2",
        attribute="make_reflection_v2",
    ),
)

_EXTERNAL: dict[str, AgentRegistration] = {}


def register_agent(registration: AgentRegistration, *, allow_override: bool = False) -> None:
    """注册本地受信任策略；默认不允许覆盖内置策略。"""

    if not registration.trusted_local:
        raise ValueError("只允许注册本机受信任策略；公网代码沙箱不在 V12 范围。")
    builtin = {item.agent_id for item in BUILTIN_AGENTS}
    if registration.agent_id in builtin and not allow_override:
        raise ValueError(f"不能覆盖内置策略：{registration.agent_id}")
    _EXTERNAL[registration.agent_id] = registration


def clear_external_agents() -> None:
    """测试与卸载入口：移除全部第三方注册（内置策略不受影响）。"""

    _EXTERNAL.clear()


def all_agents() -> tuple[AgentRegistration, ...]:
    return (*BUILTIN_AGENTS, *_EXTERNAL.values())


def registered_agent_ids() -> tuple[str, ...]:
    return tuple(item.agent_id for item in all_agents())


def get_agent(agent_id: str) -> AgentRegistration:
    for item in all_agents():
        if item.agent_id == agent_id:
            return item
    raise KeyError(agent_id)


def agent_catalog() -> list[dict[str, Any]]:
    """网页/CLI 用的策略目录：只含公开元数据与默认配置。"""

    rows: list[dict[str, Any]] = []
    for item in all_agents():
        rows.append(
            {
                **item.identity.as_dict(),
                "default_config": dict(item.default_config),
                "config_keys": list(item.allowed_config_keys),
                "builtin": item.agent_id in {entry.agent_id for entry in BUILTIN_AGENTS},
            }
        )
    return rows


__all__ = [
    "BUILTIN_AGENTS",
    "AgentRegistration",
    "PolicyFactory",
    "agent_catalog",
    "all_agents",
    "clear_external_agents",
    "get_agent",
    "register_agent",
    "registered_agent_ids",
]
