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

### 39 局登记矩阵状态

| Map | Condition | Seed labels | 当前状态 |
|---|---|---|---|
| MAP-08 | no_hypothesis_table | 0, 4, 8 | seed 0 部分运行后停止；seed 4、8 未启动 |
| MAP-08 | hypothesis_table | 0, 4, 8 | 未启动 |
| MAP-16 | react | 0, 1, 2 | 未启动 |
| MAP-16 | constraint_table | 0, 1, 2 | 未启动 |
| MAP-18 | alert_off | 0, 1, 2 | 未启动 |
| MAP-18 | alert_on | 0, 1, 2 | 未启动 |
| MAP-22 | history5 | 0, 1, 2 | 未启动 |
| MAP-22 | history5_graph_memory | 0, 1, 2 | 未启动 |
| MAP-26 | free_diagnosis | 0, 1, 2 | 未启动 |
| MAP-26 | recovery_full | 0 | 未启动 |
| MAP-26 | recovery_hidden | 0 | 未启动 |
| MAP-26 | recovery_structured | 0 | 未启动 |
| MAP-30 | history_full | 0, 1, 2 | 未启动 |
| MAP-30 | history5 | 0, 1, 2 | 未启动 |
| MAP-30 | history5_casebook | 0, 1, 2 | 未启动 |

矩阵共 39 个 episode ID：1 个开始但未完成，38 个未启动，0 个完成。Stage B smoke 的其他五局没有启动；Stage C 不能通过 smoke gate。

## 账务与完成审计

### Pilot 封账后的一次用户授权诊断（不计入 39 局）

2026-10-16 在用户明确批准后，对 MAP-08/no_hypothesis_table/seed 0 发出 1 次诊断请求；此请求不续跑 pilot、不新建或修改 V5 ledger，也不计入预登记矩阵。请求使用当时已修正顶层 JSON 说明、`json_object`、reasoning `none`，输入上界 2,046 bytes、输出上限 1,024 tokens；SDK 重试为 0。

该响应顶层三个键符合约定，但 `action` 校验发现缺少 `tool` 且包含额外字段 `verb`，因此没有产生可执行 Action。Usage 为 input 510、output 48、cached input 0 tokens；按 [MiMo 官方价格](https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash)计算为 ¥0.000606，低于单次最坏预留 ¥0.01024。完整模型回复未保存；去标识化的调用与校验摘要保存在 ignored 文件 `runs/v5/diagnostics/authorized_map08_probe_20261016T004942Z.json`。

原 70 次 Trace 未保存模型原文，故不能断言它们都由同一 `verb`/`tool` 错配造成。一次探针把问题定位到提示词与 Action 字段契约的边界；现有证据不支持 MAP-08 转移规则缺陷。探针后提示词已明确要求 Action 使用 `tool` 字段并禁止改写成 `verb`。定向离线回归 29 项通过；本次交付前全量 pytest 为 514 passed，scoped Ruff 和 diff check 通过。最新提示词尚未再次用 MiMo 验证。正式 pilot 仍为 0/39 局完成、Stage C 未启动，原 ledger 仍封闭。

- Run/experiment ID：`d3f3d7be-c928-4433-b6aa-9a269d97f593`。
- Run manifest：`runs/v5/experiments/pilot_20261015T231840Z_82ab580089c94bd3887b9dc56569d213/run_manifest.json`；V5 ledger：`runs/v5/ledgers/pilot_20261015T231840Z_82ab580089c94bd3887b9dc56569d213.jsonl`。
- 完成 episode 数：0/39。
- 请求账务：71 次预留，70 次已结算、1 次未结算；已结算 usage 为 input 38,976、output 2,936、reported cached input 34,176 tokens。缓存字段并非 70 次请求全部报告。
- Smoke gate：未通过；第一个 smoke episode 未完成，六局 artifacts/usage/manifest 验收没有运行到完整判定点，Stage C 0/33。
- 费用：70 个已结算 usage 计算为 ¥0.01135552；总保留额度 ¥0.72704（71 × ¥0.01024），其中第 71 次的实际扣费未知。单币种上限为 ¥37.50，未超过预留上限。
- 停止原因：70 次连续决策都记录为 `INVALID_ACTION_SCHEMA`。依提纲“若出现系统性接口失败，立即停机修复”停止；中断中的第 71 次请求由 ledger 审计记为 `UNKNOWN_SPEND_AFTER_INTERRUPTED_REQUEST`，pilot 已 fail-closed。不得恢复或新建 successor ledger。

Trace 未保存原始模型文本，因此目前不能区分是响应字段形状、Action 参数还是输出格式导致校验失败。MiMo JSON mode 文档要求完整定义字段层级与数据类型，并建议提供示例；运行时使用的旧 prompt 顶层示意含 `...`，已在运行后离线修正为明确字段约束，但这只是待验证的审计线索，不是已确认根因（[MiMo Structured Output 文档](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/structured-output)）。报告保留固定场景重复 seed 的解释边界；本次数据不构成能力比较或通关结论。
