# V12 文档索引

`docs/v12/` 是 Agent Arena Lab 1.0 的完整记录。**先看本页选你需要的文件**，
不必按顺序读完全部 13 份。

- **状态**：`LAB_1_0_READY`（P0 + P1 + P2 已交付，真实矩阵已执行）
- **真实实验**：20 个实验 / 159 局 / 5 641 请求 / 结算 ¥5.43680012 / 未知消费 ¥0（批准 ¥6.00）
- **一句话结论**：能测出差异，但同条件重复的结局翻转率 22.2%（2 次观测 4/18）/ 25.0%（3 次观测 3/12），
  所以 **1 次/条件不足以为架构排名**

## 按目的选文件

| 你想知道 | 读这个 |
|---|---|
| 交付了什么、结论是什么、哪些不能断言 | `final-report.md` |
| 每个真实实验的逐局结果、费用、失败归因 | `mimo-results.md` |
| Memory / Planning / Reflection 开关消融 | `ablations.md` |
| **提纲里哪些没做、为什么** | `gap-audit.md` |
| 测量口径、指标定义、`v12.projection` 与 V10 的区别 | `metrics-and-attribution.md` |
| 实验如何预登记、四类衍生实验与消融怎么配对 | `experiment-protocol.md` |
| 命令与预期输出（质量门禁、E2E、可访问性） | `validation-report.md` |
| P0/P1/P2 与交付物 A–I 的勾选状态 | `release-checklist.md` |
| 每个 Batch 的任务编号与证据 | `progress.md` |
| 架构取舍（为什么父 Experiment + 子 Run） | `architecture-decision.md` |
| 第三方 Agent 怎么接 | `adapter-api.md` |
| 风险清单与当前状态 | `risk-register.md` |
| 起点审计快照（不可改） | `00-audit.md` |
| 已知缺陷的证据链 | `dcr/DCR-V12-01…06.md` |
| 原始逐局数据（脱敏） | `real-runs/`（`*-runs.csv` 是机器可读真值） |

## 阅读顺序建议

1. **只想看结论**：`final-report.md` 的 `RESULT` 与 `KNOWN ISSUES` 两节。
2. **想复核数据**：`mimo-results.md` → 对应 `real-runs/<实验>-runs.csv` → `runs/web/<run_id>/result.json`。
3. **想接着做**：`gap-audit.md`（未做项）+ `final-report.md` 的 `NEXT`。
4. **想改测量口径**：`metrics-and-attribution.md` + `dcr/`。

## 一致性约定

- 所有数字以 `runs/web/_ledger/web_ledger.jsonl`（append-only）与各实验 `manifest.json` 为准；
  文档里的汇总都能回溯到具体 `experiment_id`。
- `real-runs/*.md` 是导出快照，可能不含最新一轮；**以 `mimo-results.md` 的汇总表为准**。
- 模拟结果（`mode=simulated`）不写付费账本，也不与真实成绩合并统计。
