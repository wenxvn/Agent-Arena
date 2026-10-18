# V10 最终报告（Batch 0–7 验收；Batch 8/9 部分）

- 分支 `v10-validity`，报告生成时 HEAD 见 git log；起始 HEAD `2fa4df2`（main）
- V8/V9 冻结：`freeze verify` 每次批末 9/9 `unchanged`
- 质量门禁：`pytest` 1036 passed、`mypy src` 0 issues、scoped `ruff` clean
- 付费调用：**0 次，累计结算 CNY 0**（`mimo-preregistration.json` 已声明未执行）

## 0. 30 图状态

| 效度状态 | V9 起点 | V10 当前 |
|---|---:|---:|
| VALIDATED | 7 | 7（防回归通过，记 3-seed 缺口） |
| NEEDS_MORE_EVIDENCE | 8 | 23 |
| NEEDS_REDESIGN | 13 | 0 |
| BLOCKED | 2 | 0 |

构念标签（独立维度）：FORCED 29、OPTIONAL 1、**BYPASS 0**、**BLOCKED 0**。

实现规模：**23 张 V10 原生运行时**、**22 份 DCR**、7 张接口/证据图 + 7 张 NEEDS_REDESIGN 图 + 古堡 3 图 + P0 5 图全部落地。

## 1. 哪些地图从 V9 状态提升到 VALIDATED？

**没有一张被提升。** 所有新完成图停在 `NEEDS_MORE_EVIDENCE`：离线 Gate（Oracle 多 seed、消融、反旁路）已过，但 **Batch 8 的 MiMo 复测未执行**，按本阶段规则不得声称 VALIDATED。V9 的 7 张 VALIDATED 保持原标，并补了防回归（见 §3 与 `validated-regression.md`）。

## 2. 哪些核心机制仍可绕过？合法替代是否被指标识别？

V9 的 11 个 BYPASS 与 6 个 BLOCKED 构念在 V10 **全部清零**，逐条证据：

| 图 | V9 旁路 | V10 反例 |
|---|---|---|
| MAP-03 | 码可最后读 | 三消融 0/6 |
| MAP-06 | seed0 两步直达 | `always_direct` 5/10（长风暴全死） |
| MAP-08 | `no_hypothesis` 成功 | **0/4**（`CONSEQUENCE`：封存诊断是前提） |
| MAP-11 | 无风暴 + 盲救 | `blind_rescue` **0/4** |
| MAP-13 | 只读不记 15 步满分 | `no_record` **0/4** |
| MAP-14 | 盲交 2/3 开门 | **0/6** |
| MAP-15 | goal 泄露 + 相位自愈 | 四消融 ≤1/10 |
| MAP-18 | 抢跑跳过恢复 | 抢跑 0/5 |
| MAP-19 | 预测 0 次也成功 | `no_forecast` 0/4 |
| MAP-20 | 旁路被直供支配 | `no_bypass` 0/4 |
| MAP-21 | 1 步直达满分 | `always_evac` 科研 0 |
| MAP-22 | 0 写记忆 12 步通关 | `no_memory_write` **0/4** |
| MAP-23 | 不侦察逐个试 | `no_scout` **0/4** |
| MAP-24 | 不走桥就不会改路 | `no_replan` 0/4（`mountain_only` 记为 N/A） |
| MAP-28/29/30 | 枚举/比较语义未公开 | 三图消融 0/4、0/4、0/3 |

**仍然保留为“合法替代”并被连续指标识别**：MAP-04 绕行（余量恒 ≤ Oracle）、MAP-19 `naive_forecast`（仅在容差 2 对照实例通过）、MAP-24 `mountain_only`（未用桥 ⇒ `replan_success` N/A）、MAP-26 盲换（3/4 成功但备件 2/2/1/2 且必有换错）、MAP-08 `over_testing`（成功但 `tests_used=3`）、MAP-11 `storm_search`（成功但风暴内搜索 1–3 次）。

## 3. 十世界的三难度递进是否成立？

见 `difficulty-calibration.md`。设计难度与经验难度**分开标注**：设计难度沿用 V8 标签，经验难度用 `legal_random` 成功率与“最易绕过消融成功率区间”两个代理量。多处出现反转（例如 MAP-08 的消融区间 0.0–1.0 因为 `over_testing` 是合法替代），**不据此重排难度标签**，并在文档中解释反转来源（动作空间大小、是否易误触成功终点）。

## 4. MiMo 的失败来自策略、接口、预算、资源还是随机场景？

**本阶段无法回答**：V10 的 MiMo 复测未执行（0 次调用）。V9 的 29 条记录已逐图归因（见 `docs/v9/`），V10 只做了**离线**归因：凡 V9 归因为“接口/公开信息”的 7 张图（07/08/09/10/11/12/26）都已重建运行时并给出反旁路证据；真正的模型行为仍需 Batch 8。

## 5. 154 指标与 V10 新指标：哪些有可靠区分度？

- 154 条 V7/V8 规格原样保留；V10 新增 **128** 条（23 图），合计 282 条可寻址指标。
- 每图 1–2 条主指标，跨图只比较语义同构量（成功率、时间/资源余量、覆盖率）。
- 经证据确认有区分度的主指标：`time_margin`（04）、`risk_time_utility`+`utility_regret`（06）、`deduction_success`（14）、`production_credit`（19/20）、`mission_success`+`route_recall`（22）、`clue_utilization`（23）、`replan_success`（24）、`spares_used`+`diagnosis_precision`（26）。
- **不适合作主指标**：`coolant_exhausted`（不可达，已删）、`response_latency`（恒 1，降 diagnostic）、`minimum_query_gap`（欠问截 0，降 diagnostic）、`risk_exposure_integral`（奖励直达，降 guardrail）。
- 20 张 V9 `METRIC_DEFECT` 图的逐条结论见 `metric-schema-v10.md` §3。

## 6. MiMo 实验用了多少 seed/重复/费用？

**0 局、0 seed、0 重复、CNY 0。** 预登记已写（`mimo-preregistration.json`：¥10 全局上限、3 环境 seed、目标上限 90 局、stop rules、逐局字段），但**未发起调用**。

## 7. 旧 V8/V9 数据是否完整保持、能否复算、哪些跨版本比较不合法？

- 完整保持：`freeze verify` 9/9 `unchanged`；V8 90 局、V9 29 条记录本机可访问。
- 可复算：V8/V9 的 Oracle、随机、指标复算在 Batch 0 已重跑并与存档逐字节一致（见 `baseline-audit.md` §4）。
- **不合法的跨版本比较**：V8/V9 的 154 条指标值不能与 V10 的 128 条混算或求均值；V8/V9 的 `scenario_hash` 不含 seed，与 V10 的 `(map, rule_hash, seed, 公开描述, 真值封印)` 不可直接对齐；同一 `map_id` 在 V8 与 V10 的 `rule_hash` 不同，成功率不可直接相减。

## 8. 剩余风险与 V11 建议

**剩余缺陷（必须披露）**：

1. **7 张 VALIDATED 图的 3-seed 缺口**：01/02/05/16/17/25/27 的 V8 实例对 seed 不敏感（`seed_effective=False`），防回归通过但多 seed 未达标。
2. **MiMo 未复测**：所有 V10 新图只有离线证据，无法回答真实模型行为。
3. **指标公式级独立复算未全覆盖**：Batch 6 交付的是**规格驱动的五态核对**（VALID 越界、非 VALID 取值非空、未注册指标），覆盖 5 图 × 2 seed；23 图的公式级逐条复算仍待补。
4. **少数合法替代仍未在指标上完全分离**：MAP-11 `storm_search`、MAP-19 `naive_forecast`（容差实例）、MAP-26 盲换。
5. **`docs/v10/maps/MAP-XX.md` 30 张逐图审计卡未建**（现为 22 份 DCR + 3 份横切报告）。
6. **10 世界难度递进存在反转**，暂以“设计/经验分离 + 解释”处理，未做认知负担的直接测量。

**V11 建议**：

1. 先做 **MiMo 有界复测**（预登记已就绪）：P0 五图 + 古堡三图 + 7 张接口图，3 环境 seed，一次不超过 ¥10；用真实数据回答 §4。
2. 补 **7 张 VALIDATED 图的 seed 参数化**（把 01/02/05/16/17/25/27 建成 V10 原生运行时），再跑 3-seed Oracle/消融。
3. 补 **23 图的公式级独立复算**（不是只看五态），并建 `docs/v10/maps/MAP-XX.md` 30 张卡。
4. 若 V11 仍以 MiMo 单模型为主，**不应**声称跨模型效度；跨模型验证需要第二个 provider 与独立预算。
5. 优先修复“合法替代与作弊仍不可分”的三处（11/19/26），而不是继续加图。
