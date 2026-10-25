"""Lab 内置策略包。

- ``basic``：基线行动循环；
- ``memory``：结构化公开记忆；
- ``planning``：高层子目标 + 计划监控；
- ``reflection``：条件反思；
- ``external``：第三方本地插件适配。

策略通过 ``agent_arena.lab.registry`` 注册；本模块不导出实现，避免策略实现之间
的循环导入。
"""

from __future__ import annotations

__all__: list[str] = []
