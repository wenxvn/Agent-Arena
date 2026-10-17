# MAP-06｜灯塔｜困难｜暴风眼

```yaml
map_id: MAP-06
world: lighthouse
nominal_level: 困难
capability_primary: value_of_information_and_risk_decision
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 12cfbc8dcb00b68ece4abd3bdbddcd4e6ab56639d0e6923e82cbdcae493951d4
source_design_hash: 649ae0a3b73459df930f46a2a73892bbcc9fdb5bfa2804956b60203eefc3b4b0
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“不确定天气下，为减少风险愿意花多少时间换信息或准备防护”。天气隐藏且整局固定；预报查询耗 2 tick，且有成本与误差；加固耗 3 tick，给下一次维修一次性 `storm_shield`，但**不遮蔽道路**。未加固维修在长暴风每 tick +3 风险，短暴风 +0；`G-P` 在长暴风每旅行 tick +1。风险预算 4，超过立即失败；截止 tick 14。核心不是“猜中天气”，而是“问、赌、加固”三者的期望值。

## 2. 真实规则字段

- 初始：`tick=0, location=Q, risk=0, lamp_restored=false, storm_shield=false`。
- 拓扑：`M-Q` 1 tick 遮蔽；`Q-P` 1 tick 暴露；`M-G` 2 tick 遮蔽；`G-P` 2 tick 暴露。
- 先验：`P(短)=P(长)=0.5`。固定 10 seed：0–3 短/预短、4 短/预长、5–8 长/预长、9 长/预短 → 80% 条件准确率。
- 成本：查预报 2 tick；加固 3 tick；维修 2 tick；普通动作 1 tick；移动按边。
- 风险：长暴风未加固维修每 tick +3；`G-P` 长暴风每 tick +1；加固后的下一次维修风险增量 0（一次性）。
- 成功：`lamp_restored && tick<=14 && risk<=4`。硬失败：`risk>4`、tick 14 未修复。
- 公开：位置、邻居、tick、风险点、风险预算、灯状态、先验、预报准确率、查询后的读数。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map06.task_success_rate` | primary | 成功的配对 episode 数 / 总 episode | 比例 / 高 | 预登记 episode 数 | 无终局 → CENSORED |
| `map06.value_of_information` | primary | `loss(最佳无观测策略) − loss(有观测策略)` | 效用单位 / 高 | 配对 episode 对 | 无配对 → UNAVAILABLE |
| `map06.high_risk_exposure_ticks` | guardrail | 高风险窗口内暴露 tick | tick / 低 | episode | 0 合法 |
| `map06.resource_exhausted` | diagnostic | `1[risk>4]` | 0/1 / 低 | episode | 终局缺失 → CENSORED |
| `map06.observation_cost` | diagnostic | 查询次数 × 2 tick | tick / 低 | episode | 0 合法 |

`value_of_information` 的预登记比较对象是**最佳无观测策略**（先加固，期望效用 27.0）与**查预报分支**（27.3），不是“立即修”（24.9）。同时报告三者，避免挑选对照。

## 4. 能力混淆分析

- 高成功率可能只来自“永远先加固”（10/10 成功），不需要读预报；因此必须报信息价值与查询成本。
- 高信息价值可能来自“预报恰好准”的 seed 分布，而非策略；固定 10 seed 的 80% 准确率必须冻结。
- 低分可能由风险计算顺序（多 tick 动作内逐 tick 结算）造成；用 `resource_exhausted` 与终止 tick 区分。
- 期望效用权重 `100×success − 7.2×tick − 1.0×risk` 是设计选择；必须做权重/先验敏感性，不能把 0.3 分差当稳健结论。

## 5. 两条手算轨迹

**短暴风，立即修（seed 0，3 tick）**：Q→P（1，短暴风风险 0）→维修 2 tick（tick 3，风险 0）→成功。指标：成功 1；暴露 tick 0；风险 0；观测成本 0。

**长暴风，先加固（seed 5，10 tick）**：Q→M（1）→M→G（2 tick，tick 3）→`harden` 3 tick（tick 6）→G→P（2 tick，tick 8，长暴风 +2 风险）→维修 2 tick（tick 10，shield 使维修风险 0）→成功。指标：成功 1；风险 2；暴露 tick 2（G-P）；观测成本 0。

**长暴风误报短（seed 9，失败）**：查预报 2 tick → 预测短 → Q→P（1，长暴风 +1）→维修 2 tick（+6）→风险 7 > 4，在第二次维修 tick 终止。指标：成功 0；风险 7（或按截尾规则记到越界时）；观测成本 2。

> 10-seed 期望（设计表）：立即修 0.50 成功 / 平均 tick 3.0 / 平均风险 3.5 / U=24.9；先加固 1.00 / 10.0 / 1.0 / U=27.0；查预报 0.90 / 8.5 / 1.5 / U=27.3。信息价值（对先加固）= 0.3 效用单位；对立即修 = 2.4。

## 6. 三个机制特有失败

1. **长暴风裸修**：不加固直接维修，两个维修 tick 共 +6，加旅行风险后超过 4，`risk>4` 终止。
2. **误报后仍按短暴风直修**：seed 9 的预报为短但真值为长；Agent 若完全信预报，风险预算被击穿。
3. **过度查询**：反复查预报（每次 2 tick）直到 tick 14，灯仍未修复，时间失败；查询成本被计入 `observation_cost`。

## 7. 两个边界

- **风险恰为 4**：规则是“超过 4 才失败”，`risk=4` 仍可继续；下一次 +1 即失败。必须用同一路径只改一个暴露 tick 验证。
- **tick 14 修复完成**：维修最后 tick 落在 14 时可成功；落在 15 则时间失败。动作效果先结算，再检查截止。

## 8. 信息泄漏负例

若 prompt/Observation 直接给 `storm_type`、seed 真值或“本次预报一定正确”，Agent 不需要权衡信息成本。V7 只允许公开先验、准确率与查询后的读数；真值与 seed 联合表只在离线裁判侧。对照组“给实际天气但不给预报”必须隔离，不能进入基线 Observation。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有短天气立即修、长天气先加固、预测正确后的短/长两条分支；`failure_traces/cases.yaml` 有三类失败。期望值由 10 个固定 seed 手算，**不是 Agent 实验**；没有运行时求解器。

## 10. 与同世界另两图差异

**vs MAP-04**：MAP-04 的潮汐规则完全公开、确定、无噪声；Agent 只需算相位，不需要为信息付费。MAP-06 的天气隐藏、预报有成本且 80% 准确，风险预算可被越过；失败来自风险积分与信息价值，而不是相位误判。把 MAP-04 的相位表藏起来只会变成信息缺失，不会产生 MAP-06 的“查询成本 vs 加固成本”权衡。

**vs MAP-05**：MAP-05 是三座塔的确定性共享供电排程，窗口、校准、旅行成本都公开；MAP-06 只有一个维修目标，但天气与预报不确定，核心是“问、赌、加固”的期望值。MAP-05 的空等是排程成本，MAP-06 的查询是信息成本；两者的状态变量、失败模式和主指标不同。

## 11. 可计算性来源

需要逐 tick 的 `risk_points`、`tick`、`location`、`lamp_restored`、`storm_shield`、预报查询事件与读数、`terminal_reason`。信息价值由配对条件（可观测/不可观测）的预登记损失差计算；损失函数与权重必须冻结在实验登记中，不能事后调参。

## 12. 难度定位与对照

D=(2,2,3,3,2,3)。相对 MAP-05 提升 V（隐藏天气）、E（随机天气）与 R（风险预算+加固资源）。预登记对照：**同天气轨迹配对“可做天气观测/不可观测”**；控制额外动作预算。若观测组额外获得天气真值，标为信息可用性实验。

## 13. 未决

公开字段 `known_forecast_accuracy` 可能已替代部分推断（`V7-DCR-005`）。运行时接入前需确认预报读数是地图计算值还是 Agent 可写字段，并冻结 10 seed 分布。
