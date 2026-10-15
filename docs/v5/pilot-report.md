# MiMo V5 六图 Pilot 报告

状态：**真实 API 矩阵尚未启动**。只有冻结 offline gate 全绿后，才执行一次 6 episode smoke；通过完整 artifacts、usage、manifest、source hash 和账本检查后，才启动矩阵余下 33 局。

## 登记配置

- Model: `mimo-v2.6-flash`，本机 OpenAI-compatible Xiaomi Responses API。
- 价格来源：[MiMo 官方模型价格页](https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash)，复核日 2026-10-16，费率未变。真实 ledger 记录所用缓存/未缓存费率和账单币种。
- 账单币种：CNY；硬上限 ¥37.50。USD $5.25 是替代币种预算，不叠加。
- 注册矩阵：39 episode；MAP-08 seed 0/4/8；MAP-16、18、22 seed label 0/1/2；MAP-30 完整历史、最近 5 步、最近 5 步加案卷三个条件各用 seed label 0/1/2；MAP-26 三个 free-diagnosis seed 和 seed 0 的三个恢复反馈条件。
- Smoke：MAP-08/no_hypothesis_table/0、MAP-16/react/0、MAP-18/alert_off/0、MAP-22/history5/0、MAP-26/free_diagnosis/0、MAP-30/history5/0，与完整矩阵复用。
- 最大预留：3,662 request attempts、33,748,992 token、单局 12 分钟、Provider 总时钟 240 分钟。CNY 最大预留 ¥37.49888；USD 最大预留 $5.2498432，二选一。

## 真实运行结果

待冻结 gate 和真实运行完成后填写。不得从 dry-run、Oracle 或设计路线复制模型 success/失败或 usage。

| Map | Condition | Seed | Outcome | Decisions | Input/output/cache tokens | Reported cost | Failure codes |
|---|---|---:|---|---:|---:|---:|---|
| — | 尚无 API episode | — | — | — | — | — | — |

## 账务与完成审计

- Run/experiment ID：未创建。
- Run manifest / V5 ledger：未创建。
- 完成 episode 数：0/39。
- Smoke gate：未运行。
- 账单报告费用 / 保留额度：无 API 请求。
- 停止原因：尚未运行。

本节在真实运行后以 ledger 的 request-level reservation/settlement 和 episode artifacts 更新，保留所有失败/中断记录，并报告固定场景重复 seed 的解释边界。
