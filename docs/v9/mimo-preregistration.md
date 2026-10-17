# V9 MiMo 有界验证预登记

- 机器可读：`docs/v9/mimo-preregistration.json`（含 `manifest_hash` 与逐图 runtime hash）
- 补充账本：`docs/v9/mimo-supplement-001.json`
- 账本：`runs/v9/ledger.jsonl`（主）、`runs/v9/supplement_001/ledger.jsonl`（补充）
- 执行器：`scripts/run_v9_mimo.py`
- 模型：`mimo-v2.6-flash` / provider `openai` / temperature 0 / 同一实例 seed
- 预算：CNY **10** 硬上限；请求前预留；unknown spend 立即封账
- 样本：主 29 局 + 补充 16 局；每条件 2 次重复（4 张主修复图）或 1 次（接口/地板/旁路图）

## 1. 目的

只回答 Batch 1–6 离线不能回答的问题：

1. 补公开信息后，0/3 是否从“未知规则导致的秒失败”转为可归因的能力/资源失败；
2. 同一实例、同一模型、同一预算下，`v8_compat` 与 `v9_fixed` 的差异是否与离线基线一致；
3. 三张 3/3 图（06/15/21）的旁路是否在真实模型上重复；
4. 地板图（07/08/26）在补枚举后是否进入机制层。

## 2. 两臂定义

| arm | prompt | 用途 |
|---|---|---|
| `v8_compat` | 与 V8 正式 90 局逐字相同 | 同期对照（不是 V8 历史数据） |
| `v9_fixed` | V8 prompt + `V9_PUBLIC_ADDENDA` 的登记补充 | 修复后条件 |

规则、动作集、预算、模型、temperature、实例 seed 完全相同；唯一差异是公开信息文本。`prompt_hash` 逐局记录。

## 3. 地图与假设

| 地图 | 假设 |
|---|---|
| MAP-09 | 补短路阈值后，首步/第二步封舱可被理性选择，失败从 2 决策 `SHORT_CIRCUIT` 后移 |
| MAP-10 | 补燃料分仓后，失败从“未装载”转为资源规划/路径选择 |
| MAP-11 | 补补给消耗后，首段移动不再必死，救援链被触发 |
| MAP-12 | 补 transfer 边后，维修链可执行，研究分成为主要失败点 |
| MAP-07/08/26 | 补枚举后，阀门/诊断/修复链真正启动 |
| MAP-14/18/22/29 | 地板/截尾机制的重复性 |
| MAP-06 seed 5 | 长风暴下直达修复应按设计失败（seed 0 旁路对照） |
| MAP-15/21 | goal 泄露与直达撤离旁路的重复性 |

## 4. 停止规则

- `unknown_spend`：立即封账，停止全部后续请求；不重开该账本；
- 连续 3 次 provider 错误：封账；
- 预算投影 > ¥10：拒绝下一请求；
- 只对确认未计费的 `provider_error` 重试一次，新 run_id；
- 不“试到成功为止”；失败、截尾、provider 异常全部保留。

## 5. 分析计划

- 主分析：同图同实例的 `v8_compat` vs `v9_fixed` 描述性对照（成功数、终止码、决策数、overlay 指标）。
- 次分析：地板/旁路图的机制事件与随机基线对照。
- 统计：n 很小，不做显著性/因果断言；不把不同图的主指标相加。
- 费用：逐局 usage + 账本 settled，单独报告。

## 6. 与 V8 的关系

V8 90 局只作历史参考，**不**作为 V9 的同期对照；V9 的 `v8_compat` 臂是重新调用的。V8 账本、Trace、hash 未修改。
