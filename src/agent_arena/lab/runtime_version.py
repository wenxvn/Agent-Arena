"""V12 运行时版本指纹：把"代码/契约版本"纳入实验身份。

为什么需要它：

``ExperimentSpec.fingerprint()`` 只覆盖**配置**（地图、实验臂、seed、预算、模式）。
但同一份配置在不同**代码/契约版本**下会产出不同行为（prompt 补丁、动作契约、
策略实现都会变）。如果版本复跑的幂等键只依赖配置指纹，那么"修完契约再复跑"
会静默返回旧实验——看起来跑过了，其实是旧数据。

因此把运行时版本写进 spec，并参与指纹：

- ``schema_version``：实验契约版本；
- ``CONTRACT_AUGMENTATION_VERSION``：公开契约补丁版本；
- ``AGENT_CONTRACT_VERSION``：策略接口版本。
"""

from __future__ import annotations

from agent_arena.lab.contract_v12 import CONTRACT_AUGMENTATION_VERSION
from agent_arena.lab.contracts import AGENT_CONTRACT_VERSION, SCHEMA_VERSION


def current_runtime_version() -> str:
    return "+".join(
        (SCHEMA_VERSION, AGENT_CONTRACT_VERSION, CONTRACT_AUGMENTATION_VERSION)
    )


__all__ = ["current_runtime_version"]
