# V2 在线运行登记表

本登记表先记录计划与门禁状态；预算账本为每次真实 provider API 尝试（包括失败、重试和格式修正请求）保留一条事件。pilot 完成或 fail-closed 停止后，须将账本事件逐条核对并汇总到本表的尝试记录，benchmark episode 数不能代替 API request 数。

## S2 M1 pilot 预登记

| experiment_id | 条件 | 地图 / seed | 局部预算 | 计划 provider / model | BUDGET-01 API 尝试 | 状态 |
|---|---|---|---:|---|---:|---|
| EXP-V2-S2-M1-V2-S1 | Memory v2 baseline；E1 ON / H5 / R1 / P2(world-declared) 固定 | `lunar_escape_v2_seeded` / 1 | 100 decisions | OpenAI-compatible / `muse-spark-1.3-contributor`（启动前校验） | 2 | 已启动；第 2 次请求 provider error 后封账；无完成 episode |
| EXP-V2-S2-M1-V2-S2 | 同条件，配对 v2 复本 | `lunar_escape_v2_seeded` / 2 | 100 decisions | 同上 | 0 | 未启动；v2 命令在 seed 1 中止 |
| EXP-V2-S2-M1-V3-S1 | Memory v3 spatial/event；其余条件与 v2 配对 | `lunar_escape_v2_seeded` / 1 | 100 decisions | 同上 | 0 | 未启动；v2 退出码 2 后按序停止 |
| EXP-V2-S2-M1-V3-S2 | Memory v3 spatial/event；其余条件与 v2 配对 | `lunar_escape_v2_seeded` / 2 | 100 decisions | 同上 | 0 | 未启动；v2 退出码 2 后按序停止 |

## 共享预算与身份冻结

| 字段 | 预登记值 |
|---|---|
| 共享 budget experiment ID | `EXP-V2-S2-M1-BUDGET-01` |
| Git SHA | `0d3bb0ba0b81ca682ea714941de7b5bd17fd03f9`（包含预算门禁及跨进程稳定的 world identity；pilot 仅使用该冻结实现） |
| Provider / model | `openai` / `muse-spark-1.3-contributor`；本机配置只在启动进程内校验，不打印凭据；不匹配时在首个请求前 fail closed |
| world selector | `lunar-escape` / `lunar-escape-v2-seeded-zh` |
| world definition ID / 当前锁定依赖运行时 hash | `lunar_escape_v2_seeded` / `bd1f77eabdcd032e80dbbaaad29163e85cbea34caf7486c22babcb3b85cb8373`（修复后跨进程 `PYTHONHASHSEED=1/2/3` 稳定；seed 1 与 2 相同） |
| base prompt hash | `44229085979f4a1bfcf7a4266985e8860e2ff0b7ea6a01cb4ca152ff5c8a869c`（v2 与 v3 当前相同） |
| 总 provider request cap | 500（四个 cell 共用；重试关闭，格式修正仍计请求） |
| 总 provider token cap | 4,000,000（四个 cell 共用） |
| 单请求输出 cap | 1,024 tokens |
| 全局超时 / 并发 | 14,400 秒 / 1 |
| 单局决策步数 / seeds | 100 / 1、2 |
| 预算账本 | `results/v2-s2-m1-budget-01.json`（本地生成物，不提交） |

历史 232-action 月球 trace 的记录 hash 是 `48348629b3a2ac4119e23df4a308c2910d2b5243c76193f64b53dfcdcbbbf0d0`，与当前锁定依赖下运行时生成的 hash 不同。地图 JSON 与世界规则未修改；flex identity 序列化实现已修改，以规范化无序 milestone 字段。旧 trace 的 hash 差异原因仍未确认，因此它只用于提出假设，不视作本轮 hash-matched 对照。v2/v3 配对条件必须使用本表冻结的当前运行时 hash。

两次 CLI 前置检查分别使用旧登记值 `118e8e8f7b930aa3841d6081b5b3de7ab94d1151e5fdee2e81f26f02561a7550` 与单进程计算值 `418ccc79d48ad99b880361b3996eae4fb496cf8f6512c54de9177669e252a702`，都在 provider 调用前被门禁拒绝；API 尝试数为 0，ledger 和结果目录均未创建。原因为 milestone 的 `frozenset` JSON 数组顺序依赖进程 hash seed。修复后 hash 为 `bd1f77eabdcd032e80dbbaaad29163e85cbea34caf7486c22babcb3b85cb8373`，在 `PYTHONHASHSEED=1/2/3` 和 seed 1、2 下保持一致；后续执行仅使用此值。

## 本次执行记录

2026-10-13 按冻结命令启动 Memory v2（episodes=2，从 seed 1 开始）。seed 1 episode 在第 2 次 provider 请求失败后中断；CLI exit code 2，v2 汇总为 0/2 完成，benchmark JSON `337d9837-eea8-40bd-8bf4-86c94d81f24b` 有 0 行，CSV 仅有表头，没有完成 trace。预算门禁关闭共享账本，随后 v2 的 seed 2 与 v3 两个 seed 均未启动。

| 请求 ID | 状态 | 记账 tokens | provider usage |
|---|---|---:|---|
| `af4ea921-3723-477a-b5e9-2b5a44d9d76e` | completed | 1,509 | input 749 + output 760 |
| `087ee418-82cf-4a67-8cad-7e2f6bd21c33` | unknown_spend_after_provider_error | 22,577（完整预留额） | 未知；原始 provider error 未落入 ledger |

ledger 最终为 2/500 requests、24,086/4,000,000 tokens，`closed_reason=provider_error_unknown_spend`，无 in-flight request。24,086 是本地预算记账值，其中第二次请求按预留额记账，不代表 provider 确认消耗。结果和账本保留在本地 `results/`；同一 budget experiment ID 不重试、不重置。只读源码核查确认 OpenAI adapter 与 budget wrapper 都把异常转换为通用错误，ledger 按 spec 不保存响应或异常元数据；因此当前证据无法确定 provider error 根因。

## Recovery run 预登记

原 BUDGET-01 已封账，绝不重置或复用。为在不超过原共享上限的前提下继续同一四 cell 配对矩阵，独立登记 BUDGET-02；seed 1 的部分失败仍保留为单独运行证据，Recovery 从新 episode 开始，不把旧 partial episode 当结果。

| 字段 | BUDGET-02 预登记值 |
|---|---|
| Budget experiment ID | `EXP-V2-S2-M1-BUDGET-02` |
| 实现 SHA | `e884688e48c357eafc27251b994e3f6c805acb64`（安全 error 分类与 fail-closed 负例测试） |
| Provider/model、world/prompt hash | 完全复用上方冻结值 |
| Recovery request cap | 498（BUDGET-01 已记账 2；两账本合计不超过 500） |
| Recovery token cap | 3,975,914（BUDGET-01 已记账 24,086；两账本合计不超过 4,000,000） |
| 每请求输出 cap / 并发 | 1,024 tokens / 1 |
| 全局截止 | 不晚于 BUDGET-01 原始绝对截止 `2026-10-13 20:55:33 +08:00`；启动命令前计算 `floor(deadline_epoch - current_epoch - 60)` 秒作为 BUDGET-02 timeout，低于 1 秒时不启动 |
| Episode 条件 | 原四 cell、每 cell 100 decisions、seed 1/2、E1 ON / H5 / R1 / P2(world-declared)，串行；v2 完成且 exit 0 后才运行 v3 |
| Ledger | `results/v2-s2-m1-budget-02.json`，与 BUDGET-01 分开 |
| 输出目录 | `results/v2-s2-m1-recovery-v2`、`results/v2-s2-m1-recovery-v3`，保留原 partial 输出 |

两 ledger 的 cap 总和保持为原登记值；BUDGET-02 发生任一 provider error 或 unknown spend 后立即停止，不再自动创建第三账本。执行前须确认 BUDGET-02 ledger 与两个 recovery 输出目录不存在，并核对代码 SHA、剩余 timeout 与 provider/model gate。以下命令是预登记模板，只有 SHA 写入本表并提交推送后才可执行：

```powershell
$original = Get-Content results/v2-s2-m1-budget-01.json -Raw | ConvertFrom-Json
$recoveryTimeout = [Math]::Floor($original.deadline_epoch - [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - 60)
if ($recoveryTimeout -lt 1) { throw 'Original global deadline expired; do not launch recovery.' }
$recoveryBudgetArgs = @(
  '--provider','openai','--world','lunar-escape','--world-version','lunar-escape-v2-seeded-zh',
  '--step-limit','100','--provider-request-budget','498','--provider-token-budget','3975914',
  '--provider-output-token-cap','1024','--provider-budget-timeout-seconds',"$recoveryTimeout",
  '--provider-budget-experiment-id','EXP-V2-S2-M1-BUDGET-02',
  '--provider-budget-expected-provider','openai','--provider-budget-expected-model','muse-spark-1.3-contributor',
  '--provider-budget-expected-world-hash','bd1f77eabdcd032e80dbbaaad29163e85cbea34caf7486c22babcb3b85cb8373',
  '--provider-budget-expected-prompt-hash','44229085979f4a1bfcf7a4266985e8860e2ff0b7ea6a01cb4ca152ff5c8a869c',
  '--provider-budget-ledger','results/v2-s2-m1-budget-02.json',
  '--autonomous','--stuck-recovery','--recent-history','5','--phase-context'
)
uv run agent-arena benchmark --episodes 2 --agent memory --memory-version v2 --seed 1 @recoveryBudgetArgs --output-dir results/v2-s2-m1-recovery-v2
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run agent-arena benchmark --episodes 2 --agent memory --memory-version v3_spatial_event --seed 1 @recoveryBudgetArgs --output-dir results/v2-s2-m1-recovery-v3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

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
  "--provider-budget-expected-world-hash", "bd1f77eabdcd032e80dbbaaad29163e85cbea34caf7486c22babcb3b85cb8373",
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

- 截至 2026-10-13，本登记新增真实模型 API 尝试数为 2；本轮没有读取或输出 `.env` 内容。
- fail-closed budget guard 已提交并通过 Ruff、mypy、pytest 与 `uv lock --check` 离线验证；pilot 已启动并因 `provider_error_unknown_spend` fail closed，明细见上方执行记录。
- 首个决策请求本身兼作受限 gateway probe：若 gateway 不接受输出 cap，provider error 将按整笔预留记账、关闭账本，且不会自动重试。
- 任一 usage 缺失、usage 超过预留、provider error、账本不匹配或预算触顶均停止后续请求。本次未知 spend 已关闭账本；不得重置账本或复用同一 experiment ID。中断 cell 与已完成 cell 分别报告；不把未完成运行写成最终 Episode Trace。
- 本 pilot 仍只有四个 cell，单模型、单地图家族、两个 seeds。即使全部结束，也只作小样本方向性结果；token/成功和行为指标必须基于完成运行的真实 trace/ledger 计算，不能根据预算 cap 推测。

本表保留预登记和实际执行记录；运行完成不代表模型收益已成立，也不代表本机 provider 配置长期有效。
