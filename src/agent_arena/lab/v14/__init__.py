"""V14 只读分析层（Lab 1.2 / Stage II Final）。

设计原则：

- **只增不改**：不修改 V8/V9/V10 冻结资产、不修改历史 trace 与账本、
  不改 V12/V13 已发布数字；V14 只增加投影、口径校验与证据登记。
- **零外部请求**：本包不包含任何模型调用；所有 LIVE 路径由 V12 的
  ``LiveApproval`` 与 ``DecisionGateway`` 控制，默认 ``PLANNED_ONLY``。
- **可复算**：每个结论都能用 ``docs/v12/real-runs/*.csv`` 或本机
  ``runs/`` 中的只读记录重新算出来。

模块：

| 模块 | 职责 |
|---|---|
| ``data_audit`` | 未知/零分离、协议隔离、V13→V14 标签差异、预算表算术复核 |
| ``conditions`` | 8 维观测条件身份、预算/采样画像、seed 白名单、配对结果字段 |
"""

from __future__ import annotations

SCHEMA = "v14-analysis-1"

__all__ = ["SCHEMA"]
