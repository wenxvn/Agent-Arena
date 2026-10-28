# V13 文档索引（Agent Arena Lab 1.1）

> **历史版本。** V13 本轮确实没有付费请求，但它在 `docs/v13/` 里标记为 `WAITING_USER_APPROVAL`
> 的真实模型验证**已由 V14 承接**：`memory.v2` / `planning.v2` / `reflection.v2` 已于 2026-10-27/28
> 在 MiMo 上执行 308 局（¥5.55809328）。本文与各 study 文件中的 `WAITING_USER_APPROVAL`
> 保留为**当时状态**，当前结论看 [V14 收尾声明](../v14/stage2-closure.md)。

- **状态**：`LAB_1_1_ENGINEERING_READY`
- **真实付费请求**：0 局 / CNY 0（`WAITING_USER_APPROVAL`；**后续由 V14 承接**）
- **起始 HEAD**：`32e27826eab33093d2d5d640d08f47bbd4974df3`

## 先读哪一篇

| 你想知道 | 读这个 |
|---|---|
| V13 到底做了什么、能说什么 | [final-report.md](final-report.md) |
| 哪些任务完成、哪些没完成 | [gap-audit.md](gap-audit.md) |
| 比较口径怎么定（先冻结） | [experiment-protocol.md](experiment-protocol.md) |
| V12 基线复核与 17 项缺口 | [audit.md](audit.md) |
| 架构决策与被拒方案 | [decisions.md](decisions.md) |
| 逐批次进度与证据 | [progress.md](progress.md) |
| 全部命令的实际结果 | [validation-report.md](validation-report.md) |

## 研究结论

| 主题 | 文件 | 结论强度 |
|---|---|---|
| Memory（路线记忆） | [memory-study.md](memory-study.md) | 机制 `SUPPORTED`；收益 `WAITING_USER_APPROVAL` |
| Planning（节流与重规划） | [planning-study.md](planning-study.md) | 机制 `SUPPORTED`；收益 `WAITING_USER_APPROVAL` |
| Reflection（真触发） | [reflection-study.md](reflection-study.md) | 触发 `SUPPORTED`；收益 `WAITING_USER_APPROVAL` |
| MAP-16/18/22 证据包 | [core-evidence.md](core-evidence.md) | 描述性 `SUPPORTED` |
| 六图构念效度 | [map-validity.md](map-validity.md) | 标签 + 选图建议 |
| MAP-30 预算阶梯 | [map30-budget-ladder.md](map30-budget-ladder.md) | `INSUFFICIENT`（截尾为主） |
| 失败归因分层 | [diagnosis-taxonomy.md](diagnosis-taxonomy.md) | 七层 + 8 个 fixture |
| 机制级能力画像 | [capability-profile.md](capability-profile.md) | `agent_reviewed` |
| 重复稳定性 | [repeat_variability.md](repeat_variability.md) | 翻转率 25%（描述性） |

## 数据与工程

| 文件 | 内容 |
|---|---|
| [data-and-cost-audit.md](data-and-cost-audit.md) | 本地账本 159/159 配对、0 孤儿、0 重复结算；外部对账 `NO_EXTERNAL_BILL_PROVIDED` |
| [performance-report.md](performance-report.md) | 1 000 / 5 000 条合成历史的分页、筛选、聚合、内存 |
| [live-budget-proposal.md](live-budget-proposal.md) | 三档 LIVE 预算申请（**未批准**） |
| [sdk-guide.md](sdk-guide.md) | 第三方插件接入、8 项自检、受信任边界 |
| [release-checklist.md](release-checklist.md) | 交付清单、复现命令、回滚办法 |

## 机器可读产物

| 文件 | 用途 |
|---|---|
| `repeat_variability.csv/json` | 逐条件重复稳定性（可复算） |
| `data-and-cost-audit.json` | 账本审计与对账结果 |
| `performance-report.json` | 压测原始数字 |
| `demo/` | SIMULATED 演示包（含 `DEMO_SIMULATED.txt` 声明） |

## 一句话边界

> V13 的成果是**让结论可审计**，不是让分数更好看。
> 真实模型是否因这些策略变强，仍是 `WAITING_USER_APPROVAL`。
