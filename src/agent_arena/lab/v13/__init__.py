"""V13 深化层：可比性、重复稳定性、消融、效度、归因、画像、报告与账本审计。

设计边界（与 V12 一致）：

- 本包**只读**：消费 V12/V13 已落盘的 run record、导出 CSV 与本地账本，
  不创建环境、不发 Provider 请求、不修改任何历史文件；
- 所有输出都带来源标签（``HISTORICAL`` / ``SIMULATED`` / ``LIVE``）与结论等级
  （``SUPPORTED`` / ``TENTATIVE`` / ``INSUFFICIENT`` / ``NOT_TESTED``）；
- 不补零、不跨版本硬并、不用重复次数伪造样本量。
"""

from __future__ import annotations

__all__ = ["CONTRACT_VERSION"]


CONTRACT_VERSION = "v13-lab-1"
