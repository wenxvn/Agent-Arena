# MiMo V5 六图 Pilot 报告

状态：**真实 API pilot 已在 Stage B 停止，Stage C 未启动**。冻结 offline gate 在运行 commit `e440cc1b599a5de4a57650f418d78b03c4746399` 通过后，MiMo smoke 首局连续出现系统性 `INVALID_ACTION_SCHEMA`。提纲要求系统接口失败时停止；随后中断时有一个已预留请求未返回 usage，唯一 V5 ledger 已按 unknown-spend 规则关闭。39 局矩阵没有完成。

停止后的离线加固：prompt 现在明确列出顶层 JSON 键和假设表类型；runner 在连续 3 次 schema 拒绝时 fail-closed。全量 513 项测试和 26 项 V5 定向测试通过，Ruff/mypy 通过。这些改动发生在真实运行之后，没有再次连接 MiMo 验证；运行 artifacts 仍准确绑定原始 commit `e440cc1`。

## 登记配置

- Model: `mimo-v2.6-flash`，本机 OpenAI-compatible Xiaomi Responses API。
- 价格来源：[MiMo 官方模型价格页](https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash)，复核日 2026-10-16，费率未变。真实 ledger 记录所用缓存/未缓存费率和账单币种。
- 账单币种：CNY；硬上限 ¥37.50。USD $5.25 是替代币种预算，不叠加。
- 注册矩阵：39 episode；MAP-08 seed 0/4/8；MAP-16、18、22 seed label 0/1/2；MAP-30 完整历史、最近 5 步、最近 5 步加案卷三个条件各用 seed label 0/1/2；MAP-26 三个 free-diagnosis seed 和 seed 0 的三个恢复反馈条件。
- Smoke：MAP-08/no_hypothesis_table/0、MAP-16/react/0、MAP-18/alert_off/0、MAP-22/history5/0、MAP-26/free_diagnosis/0、MAP-30/history5/0，与完整矩阵复用。
- 最大预留：3,662 request attempts、33,748,992 token、单局 12 分钟、Provider 总时钟 240 分钟。CNY 最大预留 ¥37.49888；USD 最大预留 $5.2498432，二选一。

## 真实运行结果

以下数据只来自本次唯一 V5 ledger 和生成的 trace；离线 Fake、Oracle 和求解结果不作为模型能力证据。

| Map | Condition | Seed | Outcome | Decisions | Input/output/cache tokens | Reported cost | Failure codes |
|---|---|---:|---|---:|---:|---:|---|
| MAP-08 | no_hypothesis_table | 0 | incomplete / stopped | 70 次均无合法 Action | 38,976 / 2,936 / 34,176* | ¥0.01135552** | `INVALID_ACTION_SCHEMA` ×70 |

\* 上述 70 个已结算请求中缓存 token 合计 34,176；并非每个 settled usage 都提供缓存字段。\
\*\* 这是 70 个已结算响应按报告 usage 计算的费用，不是最终账单确认；第 71 个请求的 usage 未知。

## 账务与完成审计

- Run/experiment ID：`d3f3d7be-c928-4433-b6aa-9a269d97f593`。
- Run manifest：`runs/v5/experiments/pilot_20261015T231840Z_82ab580089c94bd3887b9dc56569d213/run_manifest.json`；V5 ledger：`runs/v5/ledgers/pilot_20261015T231840Z_82ab580089c94bd3887b9dc56569d213.jsonl`。
- 完成 episode 数：0/39。
- 请求账务：71 次预留，70 次已结算、1 次未结算；已结算 usage 为 input 38,976、output 2,936、reported cached input 34,176 tokens。缓存字段并非 70 次请求全部报告。
- Smoke gate：未通过；第一个 smoke episode 未完成，六局 artifacts/usage/manifest 验收没有运行到完整判定点，Stage C 0/33。
- 费用：70 个已结算 usage 计算为 ¥0.01135552；总保留额度 ¥0.72704（71 × ¥0.01024），其中第 71 次的实际扣费未知。单币种上限为 ¥37.50，未超过预留上限。
- 停止原因：70 次连续决策都记录为 `INVALID_ACTION_SCHEMA`。依提纲“若出现系统性接口失败，立即停机修复”停止；中断中的第 71 次请求由 ledger 审计记为 `UNKNOWN_SPEND_AFTER_INTERRUPTED_REQUEST`，pilot 已 fail-closed。不得恢复或新建 successor ledger。

Trace 未保存原始模型文本，因此目前不能区分是响应字段形状、Action 参数还是输出格式导致校验失败。MiMo JSON mode 文档要求完整定义字段层级与数据类型，并建议提供示例；运行时使用的旧 prompt 顶层示意含 `...`，已在运行后离线修正为明确字段约束，但这只是待验证的审计线索，不是已确认根因（[MiMo Structured Output 文档](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/structured-output)）。报告保留固定场景重复 seed 的解释边界；本次数据不构成能力比较或通关结论。
