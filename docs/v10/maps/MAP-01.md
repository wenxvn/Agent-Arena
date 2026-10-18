# MAP-01｜飞船 · 破损的曙光号（简单）

- 运行时：`v8 回退（V10 无原生运行时）`
- 构念标签：`FORCED`；效度状态：`VALIDATED`（均为 `agent_reviewed`）
- DCR：`—`
- `rule_hash`：`v8:b0b4cf2c14e981f2ff4f561be50266f235e8e021fea00d01857ed2ceea7c248f`
- `metric_hash`：`v8:31c2795d2a3ac4e6f9cb8a623099ac4d17dba0a4a59bef2a8be39742daa26305`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 5 防回归：V9 Oracle 在当前运行时可复跑；多 seed 覆盖缺口已明确记录

- 该图在 V10 未重建运行时，三分量（目标构念/最小行为/消融）沿用 V9 构念证据；
  V10 只做防回归与环境 seed 复核（见 `docs/v10/validated-regression.md`）。

## 2. 公开信息边界

- V8 回退图的 Observation 与公开动作沿用 `worlds/scenario_v8` 只读实现；
  V10 未新增或减少其公开字段。

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `inspect` | {target,tool} |
| `interact` | {choice,target,tool} |
| `move` | {edge_id,tool} |
| `pickup` | {item_id,tool} |
| `wait` | {tool,turns} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2`（3 个）
- 实例指纹各不相同：`否`
- 不同 `scenario_hash` 数：`3`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `c481427b85fca3f9` |
| 1 | `9039732a5bde4c36` |
| 2 | `2fcf352f970700ac` |

> V8 回退图对 seed 不敏感（`seed_effective=False`）：3-seed 未达标，已在
> `validated-regression.md` 记为缺口。
> 注意：`scenario_hash` 把 `environment_seed` 计入身份，所以三个 hash 不同
> **不等于**三个环境实例不同；实例是否不同由 `seed_effective` 判定。

## 5. 指标

- 该图指标沿用 V7/V8 的 154 条注册规格（只读）；V10 未新增 v10 指标。
- V10 新增的其余 23 图指标见 `docs/v10/metric-schema-v10.md`。

## 6. 反事实消融

- 无 V10 基线产物（V8 回退图沿用 V9 存档消融）。

## 7. MiMo 证据

- 未纳入 Batch 8 矩阵：无真实模型证据（仍为 `NEEDS_MORE_EVIDENCE` 或 `VALIDATED`）。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：V8 实例对 seed 不敏感（3-seed 未达标，见 validated-regression.md）
- 当前裁定：Batch 5 防回归：V9 Oracle 在当前运行时可复跑；多 seed 覆盖缺口已明确记录
- 剩余风险：无 V10 原生运行时 ⇒ 不能在本阶段声称 3-seed 达成；V11 需先参数化该图实例。
- 防回归复跑：`通过`；V9 Oracle 记录：`1/1`；V9 消融：`{'no_support_handoff': False}`

## 9. 证据索引

- 无 DCR（沿用 V9 规则）
- `runs/v10/baselines/MAP-01.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（回退图）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

