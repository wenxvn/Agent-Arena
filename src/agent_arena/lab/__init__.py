"""V12 Agent Arena Lab：多架构 Agent 实验层。

模块边界：

- ``contracts``：版本化数据契约（Agent / Experiment / Comparison / Finding）；
- ``adapters``：V10 公开 Observation/Action 与 Agent 公共上下文之间的桥；
- ``gateway``：唯一的模型调用与预算出口，策略不得绕过；
- ``policies``：Basic / Memory / Planning / Reflection / External 策略；
- ``runner``：单局执行器（V10 Environment + 公开 Action 校验 + 事件落盘）；
- ``experiment``：父实验、矩阵、队列、父子状态与实验级预算；
- ``compare`` / ``diagnostics`` / ``visualization`` / ``report``：分析、诊断、视图与导出。

本包不修改 ``v10``、``v8``、``v9`` 的运行时、账本与历史 trace；也不依赖 Streamlit。
"""

from __future__ import annotations

from agent_arena.lab.contracts import (
    AGENT_CONTRACT_VERSION,
    DEFAULT_LAB_MAPS,
    SCHEMA_VERSION,
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
    AgentArm,
    AgentDecision,
    AgentEvent,
    AgentIdentity,
    ComparisonResult,
    ExperimentBudget,
    ExperimentManifest,
    ExperimentMode,
    ExperimentSpec,
    ExperimentState,
    Finding,
    LiveApproval,
    MatrixCell,
)

__all__ = [
    "AGENT_CONTRACT_VERSION",
    "DEFAULT_LAB_MAPS",
    "SCHEMA_VERSION",
    "SIMULATED_MODEL",
    "SIMULATED_PROVIDER",
    "AgentArm",
    "AgentDecision",
    "AgentEvent",
    "AgentIdentity",
    "ComparisonResult",
    "ExperimentBudget",
    "ExperimentManifest",
    "ExperimentMode",
    "ExperimentSpec",
    "ExperimentState",
    "Finding",
    "LiveApproval",
    "MatrixCell",
]
