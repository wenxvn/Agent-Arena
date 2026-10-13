# V2 在线运行登记表

本登记表先记录计划与门禁状态；预算账本为每次真实 provider API 尝试（包括失败、重试和格式修正请求）保留一条事件。pilot 完成或 fail-closed 停止后，须将账本事件逐条核对并汇总到本表的尝试记录，benchmark episode 数不能代替 API request 数。

## S2 M1 pilot 预登记

| experiment_id | 条件 | 地图 / seed | 局部预算 | 计划 provider / model | API 尝试 | 状态 |
|---|---|---|---:|---|---:|---|
| EXP-V2-S2-M1-V2-S1 | Memory v2 baseline；E1 ON / H5 / R1 / P2(world-declared) 固定 | `lunar_escape_v2_seeded` / 1 | 100 decisions | OpenAI-compatible / `muse-spark-1.3-contributor`（启动前校验） | 0 | 已预登记；等待门禁验证、提交与代码 SHA 冻结 |
| EXP-V2-S2-M1-V2-S2 | 同条件，配对 v2 复本 | `lunar_escape_v2_seeded` / 2 | 100 decisions | 同上 | 0 | 已预登记；等待门禁验证、提交与代码 SHA 冻结 |
| EXP-V2-S2-M1-V3-S1 | Memory v3 spatial/event；其余条件与 v2 配对 | `lunar_escape_v2_seeded` / 1 | 100 decisions | 同上 | 0 | 已预登记；等待门禁验证、提交与代码 SHA 冻结 |
| EXP-V2-S2-M1-V3-S2 | Memory v3 spatial/event；其余条件与 v2 配对 | `lunar_escape_v2_seeded` / 2 | 100 decisions | 同上 | 0 | 已预登记；等待门禁验证、提交与代码 SHA 冻结 |

## 共享预算与身份冻结

| 字段 | 预登记值 |
|---|---|
| 共享 budget experiment ID | `EXP-V2-S2-M1-BUDGET-01` |
| Git SHA | 门禁验证后提交时填写；提交前不得发起真实请求 |
| Provider / model | `openai` / `muse-spark-1.3-contributor`；本机配置只在启动进程内校验，不打印凭据；不匹配时在首个请求前 fail closed |
| world selector | `lunar-escape` / `lunar-escape-v2-seeded-zh` |
| world definition ID / 当前锁定依赖运行时 hash | `lunar_escape_v2_seeded` / `118e8e8f7b930aa3841d6081b5b3de7ab94d1151e5fdee2e81f26f02561a7550`（seed 1 与 2 当前均解析为此值） |
| base prompt hash | `44229085979f4a1bfcf7a4266985e8860e2ff0b7ea6a01cb4ca152ff5c8a869c`（v2 与 v3 当前相同） |
| 总 provider request cap | 500（四个 cell 共用；重试关闭，格式修正仍计请求） |
| 总 provider token cap | 4,000,000（四个 cell 共用） |
| 单请求输出 cap | 1,024 tokens |
| 全局超时 / 并发 | 14,400 秒 / 1 |
| 单局决策步数 / seeds | 100 / 1、2 |
| 预算账本 | `results/v2-s2-m1-budget-01.json`（本地生成物，不提交） |

历史 232-action 月球 trace 的记录 hash 是 `48348629b3a2ac4119e23df4a308c2910d2b5243c76193f64b53dfcdcbbbf0d0`，与当前锁定依赖下运行时生成的 hash 不同。当前地图 JSON 和 flex 源文件未修改；差异原因尚未确认，因此旧长尾 trace 只用于提出假设，不视作本轮 hash-matched 对照。v2/v3 配对条件必须使用本表冻结的当前运行时 hash。

## 执行命令

两次 benchmark 顺序执行并共享账本。预算或 provider 门禁失败后脚本停止；不得手动重置账本继续同一 experiment ID。

```powershell
$budgetArgs = @(
  "--provider", "openai",
  "--world", "lunar-escape",
  "--world-version", "lunar-escape-v2-seeded-zh",
  "--step-limit", "100",
  "--provider-request-budget", "500",
  "--provider-token-budget", "4000000",
  "--provider-output-token-cap", "1024",
  "--provider-budget-timeout-seconds", "14400",
  "--provider-budget-experiment-id", "EXP-V2-S2-M1-BUDGET-01",
  "--provider-budget-expected-provider", "openai",
  "--provider-budget-expected-model", "muse-spark-1.3-contributor",
  "--provider-budget-expected-world-hash", "118e8e8f7b930aa3841d6081b5b3de7ab94d1151e5fdee2e81f26f02561a7550",
  "--provider-budget-expected-prompt-hash", "44229085979f4a1bfcf7a4266985e8860e2ff0b7ea6a01cb4ca152ff5c8a869c",
  "--provider-budget-ledger", "results/v2-s2-m1-budget-01.json",
  "--autonomous", "--stuck-recovery", "--recent-history", "5", "--phase-context"
)

uv run agent-arena benchmark --episodes 2 --agent memory --memory-version v2 --seed 1 @budgetArgs --output-dir results/v2-s2-m1-v2
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run agent-arena benchmark --episodes 2 --agent memory --memory-version v3_spatial_event --seed 1 @budgetArgs --output-dir results/v2-s2-m1-v3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

## 门禁与解除条件

- 截至 2026-10-13，本登记的新增真实模型 API 尝试数为 0；本轮没有读取或输出 `.env` 内容。
- fail-closed budget guard 已进入实现和离线验证；S2 pilot 仅在 Ruff、mypy、pytest 通过且代码提交 SHA 写入本表后启动。
- 首个决策请求本身兼作受限 gateway probe：若 gateway 不接受输出 cap，provider error 将按整笔预留记账、关闭账本，且不会自动重试。
- 任一 usage 缺失、usage 超过预留、provider error、账本不匹配或预算触顶均停止后续请求。中断 cell 与已完成 cell 分别报告；不把未完成运行写成最终 Episode Trace。
- 本 pilot 仍只有四个 cell，单模型、单地图家族、两个 seeds。即使全部结束，也只作小样本方向性结果；token/成功和行为指标必须基于完成运行的真实 trace/ledger 计算，不能根据预算 cap 推测。

本表是预登记，不代表实验已运行、模型收益已成立或本机 provider 配置已经核验。
