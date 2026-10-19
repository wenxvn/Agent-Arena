# MAP-15｜金字塔 · 会变化的迷宫（困难）

- 运行时：`v10 原生`
- 构念标签：`FORCED`；效度状态：`NEEDS_MORE_EVIDENCE`（均为 `agent_reviewed`）
- DCR：`DCR-V10-04`
- `rule_hash`：`0222e338ddf18bfdd271a28fbc7e50bf92c8616832c6f8564a4e5f630ab38030`
- `metric_hash`：`b04f8160cda8cfe6ecacf724a82c302b065907f377f6368cc4b80666a5953f87`

## 1. 目标构念与最小可观察行为

- 本轮裁定：Batch 2：删除 goal 泄露；6 规律家族；训练/测试墙色分离；record_rule 提交假设；消除相位自愈；四消融均 ≤1/10，启发式 10/10

- 主指标：`map15.v10.test_gate_first_try_accuracy`, `map15.v10.rule_generalization`
  - `map15.v10.test_gate_first_try_accuracy`：T1/T2 首次选择即正确的门数 / 已首次尝试的测试门数（方向：higher）
  - `map15.v10.rule_generalization`：recorded rule (period, offsets) == 密封家族（方向：higher）

规格里声明的核心机制是否被真实触发由各图 `mechanism_triggered()` 判定；
Oracle 各 seed 的触发率为 10/10。

## 2. 公开信息边界

### 公开规则（写进 system prompt）

1. 区域依次为 A → B → C（训练区）→ T1 → T2（测试区）→ EXIT；每区有若干门，choose_door(slot_index) 选第几扇门（从 1 开始）。
2. 色环顺序 red → gold → blue → green → red。每次选门时，正确门的颜色 = 当前墙色沿色环前进 k 格；k 只取决于当前 tick 除以某个周期的余数，周期为 2 或 3，k ∈ {0,1,2,3}。这条规律在所有区域相同，但具体周期与各余数下的 k 未知，需要从样例推断。
3. inspect_symbols(area=当前区域) 不耗 tick，显示墙色与各门颜色（按槽位顺序）。
4. training_sample_log 含 2 条往期档案样例；在训练区每次选门（对或错）都追加一条样例。训练区选错：耗 1 tick、留在原区、不扣容错。选对：耗 1 tick、前进一区。
5. 离开 C 进入测试区前，必须先 record_rule(rule_id, supporting_sample_ids)，rule_id 格式 'period=P;offsets=k0,k1[,k2]'（offsets 依次对应余数 0,1,2）；环境只校验格式，不告诉对错。supporting_sample_ids 只能引用 training_sample_log 中的 id。
6. 测试区：T1 与 T2 的墙色在训练中从未出现。选对耗 1 tick 前进；选错不耗 tick、扣 1 次容错，共 2 次错误即失败；测试区内 wait 被拒且不推进 tick。
7. predict_transition(answer=颜色) 只在测试区可用、不耗 tick，预测下一次选门时的正确门色，单独计分。

### Observation 公开字段

`area`、`color_wheel`、`current_door_colors_if_inspected`、`current_tick`、`current_wall_color_if_inspected`、`gate_open`、`goal`、`inspected_current_area`、`pending_prediction`、`recorded_rule_hypothesis`、`test_wrong_attempts`、`test_wrong_attempts_remaining`、`training_sample_log`

### 随 seed 变化的公开实例参数（`scenario_descriptor` 键）

`archive_base_tick`、`doors`、`test_walls`、`training_walls`

### 密封真值（只列键名，真值只在 judge 与 hash 中）

`family`、`rule_id`

## 3. 合法动作契约（`SHAPES`）

| tool | 合法字段集合 |
|---|---|
| `choose_door` | {slot_index,tool} |
| `inspect_symbols` | {area,tool} |
| `predict_transition` | {answer,tool} |
| `record_rule` | {rule_id,supporting_sample_ids,tool} |
| `wait` | {ticks,tool} |

## 4. 环境 seed 与实例差异性

- 预登记 seed：`0, 1, 2, 3, 4, 5, 6, 7, 8, 9`（10 个）
- 实例指纹各不相同：`是`
- 不同 `scenario_hash` 数：`10`

| seed | scenario_hash（前 16 位） |
|---:|---|
| 0 | `aca0742b45cfd981` |
| 1 | `a08b2d68c80d1be6` |
| 2 | `825b587ab2e5f522` |
| 3 | `9236494a8f330cc8` |
| 4 | `05573a8ea8bd4ac9` |
| 5 | `eb2bd08789151de1` |
| 6 | `7359b6d9d8c6e1d6` |
| 7 | `dd153515b7217f7b` |
| 8 | `06d6837dba972dc1` |
| 9 | `32912c55527454a6` |

## 5. 主次指标（`METRIC_SPECS`）

| metric_id | role | direction | 公式 | 分母 | 零分母 | 截尾 | 单位 | valid_range |
|---|---|---|---|---|---|---|---|---|
| `map15.v10.test_gate_first_try_accuracy` | primary | higher | T1/T2 首次选择即正确的门数 / 已首次尝试的测试门数 | 已尝试的测试门（1–2） | NOT_APPLICABLE | 进入 T 前截尾 → CENSORED；进入 T 前失败 → NOT_APPLICABLE | ratio | (0.0, 1.0) |
| `map15.v10.rule_generalization` | primary | higher | recorded rule (period, offsets) == 密封家族 | 记录过规则的局（1） | 从未记录 → NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map15.v10.prediction_accuracy` | secondary | higher | 显式 predict_transition 正确数 / 已结算预测数 | 已结算预测 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map15.v10.sample_phase_coverage` | secondary | higher | record_rule 引用样例覆盖真实周期相位数 / period | 记录过规则的局 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ratio | (0.0, 1.0) |
| `map15.v10.training_errors` | diagnostic | none | 训练区错误选门次数（探索成本） | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 200.0) |
| `map15.v10.test_errors` | guardrail | lower | 测试区错误选门次数 | — | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | count | (0.0, 2.0) |
| `map15.v10.exploration_ticks` | diagnostic | lower | 进入 T1 时的 tick | 进入 T1 的局 | NOT_APPLICABLE | 部分进度保持 VALID；未发生的终点事件为 CENSORED | ticks | (0.0, 200.0) |

## 6. 反事实消融（逐 seed，成功率与主指标均值）

| 消融 | 成功率 | 主指标均值 |
|---|---|---|
| `fixed_route` | 1/10 | 0.3333 |
| `no_probe` | 0/10 | 0.25 |
| `no_transfer` | 0/10 | 0.0 |
| `random_rule` | 0/10 | 0.3333 |

- Oracle：10/10（机制触发 10/10）
- 公开启发式：10/10（主指标均值 1.0）
- legal_random：0/200（主指标均值 None）
- Oracle 是否在决策预算内：`True`

- 观测到的终止码：`GATE_OPENED`、`TEST_WRONG_LIMIT`

## 7. MiMo 证据（Batch 8，单 replicate 描述性）

| seed | run_id | 结局 | 决策数 | 主指标 | 成本 CNY | 有效 |
|---:|---|---|---:|---|---:|---|
| 0 | `V10-MAP-15-S0-p0` | TEST_WRONG_LIMIT（decision_budget_exhausted） | 21 | 0.0 | 0.2895698 | 是 |
| 1 | `V10-MAP-15-S1-p0` | GATE_OPENED（decision_budget_exhausted） | 13 | 0.5 | 0.31902676 | 是 |
| 2 | `V10-MAP-15-S2-p0` | settle_closed:供应商 usage 超出登记上限。（settle_closed:供应商 usage 超出登记上限。） | 32 | None | 0.45549592 | 否（中断保留） |
| 2 | `V10-MAP-15-S2-p0-r2` | GATE_OPENED（success） | 22 | 0.5 | 0.01823088 | 是 |

- 有效局成功：2/3；另有 1 局 provider/账本中断（保留但不计入）
- 结算成本合计 CNY 1.08232336（含中断局的已结算部分）。
- 单 seed、单 replicate，只作描述，不作统计推断。

## 8. 结论、剩余风险与下一步

- 缺陷与待证事项：离线门禁通过；6 家族 10 seed
- 当前裁定：Batch 2：删除 goal 泄露；6 规律家族；训练/测试墙色分离；record_rule 提交假设；消除相位自愈；四消融均 ≤1/10，启发式 10/10
- 剩余风险：公式级独立复算已覆盖 30/30 图（见 `metric-recompute.md`）；五态核对、回放确定性与 MiMo 单 replicate 的边界仍按报告披露。
- 提升到 `VALIDATED` 的条件：Batch 8 MiMo 复测有真实局 + 指标复算无越界。

## 9. 证据索引

- `docs/v10/dcr/DCR-V10-04.md`
- `runs/v10/baselines/MAP-15.json`（若存在）
- `runs/v10/baselines/summary.json`
- `docs/v10/validated-regression.md`（V9 防回归与 seed 差异）
- `runs/v10/mimo/episodes/` 下该图逐局 trace/judge

