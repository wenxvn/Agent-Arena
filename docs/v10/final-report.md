# V10 最终报告（Batch 0–9 验收）

- 分支 `v10-validity`；起始 HEAD `2fa4df2`（main）；本报告提交的 HEAD 见 `git log -1`。
- V8/V9 冻结：`freeze verify` 每批末与末尾均 **9/9 `unchanged`**。
- 质量门禁：`pytest` **1078 passed**、`mypy src` **0 issues（237 文件）**、scoped `ruff` clean。
- 真实模型：MiMo 有效局 **80**（+5 局 provider/账本中断保留），成功 **36/80**；
  结算 **CNY 1.77142820** + 未知预留 **CNY 0.11468800** = **CNY 1.88611620**（上限 ¥10，剩余 ¥8.11388380）。
- 状态口径：**`VALIDATED` 表示“测得住”**（8 项 Gate 全过），不表示“MiMo 能通关”（见 `validation-gates.md`）。

## 0. 30 图状态前后对比

| 效度状态 | V9 起点 | V10 当前 |
|---|---:|---:|
| VALIDATED | 7 | **30**（23 张 V10 原生图 8 Gate 全过；7 张 V8 回退沿用并记 3-seed 缺口） |
| NEEDS_MORE_EVIDENCE | 8 | **0** |
| NEEDS_REDESIGN | 13 | **0** |
| BLOCKED | 2 | **0** |

构念标签（独立维度）：FORCED 28、**OPTIONAL 2**（MAP-04、MAP-26）、**BYPASS 0**、**BLOCKED 0**。

实现规模：23 张 V10 原生运行时、**25 份 DCR**、23 图 ×3–10 环境 seed 基线、30 张逐图审计卡、
8 项 Gate、154+128 指标、12 个 V10 账本、85 条 MiMo 逐局记录。

## 1. 哪些地图从 V9 状态提升到 VALIDATED？逐图证据是什么？

**23 张 V10 原生图全部升到 `VALIDATED`**（03、04、06、07、08、09、10、11、12、13、14、15、18、19、20、
21、22、23、24、26、28、29、30），证据链统一为四类、全部可复算：

1. **可解且机制真实**：每图 Oracle 3+/3（MAP-06/15/21 等 10 seed 图 10/10）并真实触发核心机制
   （`baseline-results.md` 的“机制触发”列），Oracle 动作数均在决策预算内；
2. **不可绕过或有质量区分**：要么存在消融成功率低于 Oracle（如 MAP-18 抢跑 0/5、MAP-22 0/4），
   要么绕行/替代策略在连续主指标上劣于 Oracle（MAP-04 `detour_only` 6/6 但 `time_margin`
   0.67 ≪ 3.33；MAP-13 `no_direction_nail` 4/4 但 ratio 0.8 ≪ 1.0）；
3. **指标独立复核**：23 图 × 116 seed 实例，状态-取值违规 **0**、回放确定性 23/23、seed 互异 23/23
   （`independent-metric-check.md`；修复前 4 条违规全在 MAP-12）；
4. **接口对模型可用**：每图 ≥3 个有效 seed 的 MiMo 局中，非法动作占比 ≤ 50%。

**MAP-20 的提升路径最完整**：Batch 8 时它是唯一未过 `mimo` Gate 的图（168/168 非法动作）；
DCR-V10-25 把 `set_flow_tenths`/`adjust_loads`/`open_bypasses` 的结构写进地图 `public_rules()`
（`rule_hash` `81eb7439…` → `e677a0ac…`）后，阶段 4（`-j2`）三局**非法动作 168/168 → 0/168**，
Gate 通过；模型仍未产出产能（主指标恒 0），这属于策略/难度结论，不再是接口问题。

**7 张 V8 回退图（01/02/05/16/17/25/27）维持 `VALIDATED`**，但环境 seed 未参数化
（`seed_effective=False`），3-seed 缺口如实记录（`validated-regression.md`），不计入 23 图的原生 Gate。

## 2. 哪些核心机制仍可绕过？合法替代是否被指标正确识别？

- V9 的 11 个 `BYPASS` 与 6 个 `BLOCKED` 构念在 V10 **全部清零**，逐图反例见
  `baseline-results.md` 与 `decision-register.md`；`validation-gates.md` 的 `ablation` Gate
  是机器判定，不靠叙述。
- **保留并被连续指标识别的合法替代**：MAP-04 绕行（余量恒 ≤ Oracle）、MAP-08 `over_testing`
  （4/4 但 `tests_used=3`）、MAP-13 `no_direction_nail`（4/4 但 ratio 0.8）、MAP-24 `mountain_only`
  （未用桥 ⇒ `replan_success` N/A）、MAP-26 盲换（3/4 但备件必耗、必有一次换错）。
- **由此产生的一处改标**：MAP-04 的机制只影响效率（绕行 6/6 成功）而不影响通过与否，
  依提纲第 6 节从 `FORCED` 改判为 **`OPTIONAL`**（DCR-V10-08 的指标 `time_margin` 提供质量区分）。
- **仍未完全分离的一处**：MAP-11 `storm_search`（风暴内搜索合法但成本未被单一指标完全刻画），
  已用 `storm_searches` 诊断量记录，留待 V11 归一。

## 3. 十世界的三难度递进是否在认知负担上成立？

见 `difficulty-calibration.md`（设计难度 vs 经验难度分列，含 MiMo 列）：

- `legal_random` 成功率在十世界内**无反转**（0/60–0/200 全域），说明随机基线不构成难度代理；
- **MiMo 成功率在 abyss、jungle、lighthouse、pyramid、volcano 五个世界内出现反转**：
  同一世界里“困难”图反而比“中等/简单”图成功率高（如 volcano：MAP-19 0/3、MAP-20 0/3、MAP-21 3/3；
  abyss：MAP-07 1/3、MAP-08 3/3、MAP-09 3/3）。原因经 trace 归因分三类：
  1. **接口形态**（MAP-19/20 的数组 vs 对象，见 §4）——属假象，不是认知负担；
  2. **动作空间与预算**（MAP-29/30 案卷链在固定预算下更难完成整条链）；
  3. **风险结构**（MAP-21 的“撤离即安全”是模型偏好，科研分被 `overall_utility` 单独计）。
- 结论：**不做难度标签重排**；本阶段只提供“设计难度 + 经验难度 + 反转解释”三元记录，
  不声称完成了认知负担的直接测量。

## 4. MiMo 的失败究竟来自策略、接口、预算、资源还是随机场景？

按逐局 trace（`runs/v10/mimo/episodes/`）与账本归因，四类均为**部分真实**：

| 归因 | 证据 | 图 |
|---|---|---|
| **接口假象（已修复）** | 修复前 MAP-18 3 局 20/20 非法、MAP-19 121/180、MAP-20 168/168、MAP-28 seed0 11 次非法；类型化契约（DCR-V10-24）与 MAP-20 公开规则（DCR-V10-25）后，四图非法动作全部降到 **0** | 18、19、20、28 |
| **策略** | trace 级归因（`failure-attribution.md`）：`KEY_ACTION_NEVER_ATTEMPTED` 5 局、`KEY_ACTION_ATTEMPTED_REJECTED` 2 局、`KEY_ACTION_USED_NO_TRIGGER` 22 局；例：MAP-14 三局 `WRONG_SUBMISSION_LIMIT`、MAP-22 两局 `MOVE_BUDGET_EXHAUSTED`、MAP-29 反复 `investigate` 不可见目标 | 14、22、29、13、15 |
| **决策预算** | 古堡三图 9/9 全部 `decision_budget_exhausted`（28 用满 30、29 用满 38、30 用满 46）；MAP-30 已达到主指标 0.5–0.75 但链未闭合；MAP-19/20 在 60/56 决策内也没达成机制阈值 | 28、29、30、19、20 |
| **机制/资源失败** | MAP-07 `FLOODED`、MAP-12 seed2 `STATION_LOST`、MAP-18 撞车/容量终局、MAP-21 科研分低 | 07、12、18、21、04 |
| **provider/账本** | 5 局中断保留（4 次 `UNKNOWN_PROVIDER_SPEND`、1 次输入越界），全部按 stop rule 封账并另开账本、以新 `run_id` 补跑；阶段 3b 的 MAP-20 计划局因 provider 退化未跑，改由阶段 4 完成 | 15、19、22 |
| **随机场景** | 同图同策略跨 seed 结果不同（MAP-03 seed0 失败/seed1-2 成功；MAP-06 效用 0.82/0.52/0.37），说明场景是有效变量而非噪声 | 全部 |

**修复前后配对（同图同 seed，仅 prompt/规则变化，只作描述）**：

| 图 | seed | 修复前 | 修复后 |
|---:|---|---|---|
| MAP-18 | 0/1/2 | 20/20、20/20、20/20 决策无效，`ACTION_LIMIT_REACHED` | `-i2`：13/8/7 决策、**非法 0**，`HEAD_ON_COLLISION`/`STATION_CAPACITY_EXCEEDED`/`SEGMENT_CAPACITY`，主指标 0.5/0.5/0.333 |
| MAP-19 | 0/1 | 60/60、60/60 决策无效 | `-i2`：60/60 决策、**非法 0**，仍未在预算内触发预测机制 |
| MAP-20 | 0/1/2 | 56/56、56/56、56/56 决策无效 | `-j2`：**非法 0/56**，仍 `decision_budget_exhausted`、主指标 0.0；动作直方图显示三局**只用 `set_flow` 56/56**，从未使用 `open_bypass`/`adjust_loads`（核心机制） |
| MAP-28 | 0 | 11 次非法 `submit`，从未提交 | `-i2`：**成功** `ALL_CLAIMS_SUPPORTED_AND_CORRECT`，主指标 1.0 |

## 5. 154 指标与 V10 新指标中，哪些具备可靠区分度？

- 154 条 V7/V8 规格只读保留；V10 新增 **128** 条（23 图），合计 **282** 条可寻址指标；
  跨版本不混算、不求均值。
- **经证据确认有区分度的主指标**：`time_margin`（04）、`risk_time_utility`+`utility_regret`（06）、
  `deduction_success`（14）、`production_credit`（19/20）、`mission_success`+`route_recall`（22）、
  `clue_utilization`（23）、`replan_success`（24）、`spares_used`+`diagnosis_precision`（26）、
  `service_rate`+`recovery_delay_ticks`（18）、`test_gate_first_try_accuracy`+`rule_generalization`（15）、
  `overall_utility`（21）、`research_completion`（12）、`evidence_chain_coverage`（30 等古堡三图）。
- **不适合作主指标**：`coolant_exhausted`（不可达，已删）、`response_latency`（恒 1，降 diagnostic）、
  `minimum_query_gap`（欠问截 0，降 diagnostic）、`risk_exposure_integral`（奖励直达，降 guardrail）、
  `storm_searches`（与机制共线，留诊断）。
- **本阶段新发现的指标缺陷**：MAP-12 `research_completion` 声明 `(0,1)` 但 Oracle/启发式会
  **超额研究**（1.09–1.12）→ DCR-V10-23 改为 `(0,3)`，`metric_hash` `ca1f806e…`→`f4549bd7…`、
  `schema_hash` `b3fc3317…`→`e9b5a143…`；**Batch 8 全部 82 局使用旧 schema**，不得与新值混算。
- 20 张 V9 `METRIC_DEFECT` 图逐条结论见 `metric-schema-v10.md` §3；本阶段不再有未处理缺陷。

## 6. MiMo 实验用了多少环境 seed、多少重复、多少真实费用，哪些 provider 失败？

- **环境 seed**：每图 `{0,1,2}`；高风险图离线扩展至 10 seed（MAP-06/15/21）与 4–6 seed（04/14/18/28/29/30）。
  MiMo 只跑 3 环境 seed/图；**replicate 固定为 1**（单次；不把重复冒充 seed）。
- **覆盖**：23/23 张 V10 原生图 × 3 seed = 69 计划局；实际有效 **80** 局（含 5 次补跑与阶段 3/4 重跑），
  另有 5 局中断保留（4 次未知消费 + 1 次输入越界）。
- **费用**：结算 **CNY 1.77142820** + 未知预留 **CNY 0.11468800** = **CNY 1.88611620**；
  12 个 V10 账本、逐账本与逐局明细见 `cost-ledger-audit.md`。
- **provider 失败**：`APIConnectionError` 6 次（3 次在 ext 阶段、1 次在补充账本、1 次在阶段 3b、0 次在阶段 4），
  每次立即封账并保留全额预留；**MAP-15 输入越界 1 次**（早期 runner 把完整 Observation 写入
  history，属接口缺陷，已修复并复验）。
- **不做的比较**：不把 V10 成功率与 V8/V9 相加或排名；不与其它模型比较；不作显著性断言。

## 7. 旧 V8/V9 数据是否完整保持、能否复算、哪些跨版本比较不合法？

- **完整保持**：`freeze verify` 9/9 `unchanged`；V8 90 局、V9 29 条记录与全部账本原样保留；
  V10 的 11 个账本（含 5 个早期）**一个未删、一个未改**，sha256 记录在 `cost-ledger-audit.md`。
- **可复算**：V8/V9 的 Oracle、随机、指标复算在 Batch 0 已重跑并与存档一致（`baseline-audit.md` §4）；
  V10 的 30 卡、状态矩阵、Gate、难度定标、成本审计全部由 `runs/v10/` 重算。
- **不合法的跨版本比较**：① 154 条旧指标值与 128 条 V10 值不能混算；② V8/V9 的 `scenario_hash`
  不含 seed，与 V10 的 `(map, rule_hash, seed, 公开描述, 真值封印)` 不可直接对齐；
  ③ 同一 `map_id` 在 V8 与 V10 的 `rule_hash` 不同，成功率不可直接相减；
  ④ **Batch 8 的 `metric_schema_hash` 与当前仓库不同**（DCR-V10-23 之后），逐局 manifest 已固化。

## 8. V11 是否需要跨模型验证，还是仍应优先修复少数地图？

**优先修复，不做跨模型验证。** 依据 V10 结果：

1. **MAP-20 的机制未被模型触发**：接口已修（非法动作 0/168），但三局主指标恒 0、预算耗尽；
   需判读是“难度过高/提示不足”还是“模型缺少该策略”，再决定是否调预算或加公开提示。
2. **7 张 V8 回退图参数化**（01/02/05/16/17/25/27）：建 V10 原生运行时，补 3-seed
   Oracle/消融/MiMo，才能把 30/30 的“多 seed 有效性”补全。
3. **公式级指标复算**：`independent_check` 是规格驱动核对 + 回放确定性 + seed 差异性，
   仍缺“第二套实现逐条重算分子/分母”；应优先覆盖主指标为比值的图（03/07/09/12/18/20/26/30 等）。
4. **`KEY_ACTION_USED_NO_TRIGGER` 的 22 局**（`failure-attribution.md`）：模型按机制动作操作但阈值没到，
   需要逐图判读是预算不足、阈值过严还是提示缺失。
5. **古堡三图的预算/案卷规模**：9/9 预算耗尽，需评估决策预算与案卷链长度的匹配。
6. **跨模型验证**需要第二个 provider 与独立预算，本阶段**不声称**跨模型效度。

## 9. 机器验收清单

- [x] 最新 HEAD 与冻结版本已记录；V8/V9 文件未被修改（`freeze verify` 9/9 unchanged）。
- [x] 30/30 逐图审计卡与机制证据完整（`docs/v10/maps/MAP-01.md … MAP-30.md`）。
- [x] MAP-03、18、06、15、21 的 P0 反例被测试覆盖（DCR-V10-01/02/03/04/05 + `tests/test_v10_map03/18.py` 等）。
- [x] 古堡 28–30 案卷、证据、比较接口可执行且不泄漏答案（`map_cards` 的密封真值只列键名）。
- [x] 20 项指标缺陷（含 V9 的 13 项核心）均有版本化处理结论（`metric-schema-v10.md` §3 + DCR-V10-23）。
- [~] 30/30 图至少 3 不同环境 seed 的 Oracle 可行性验证：**23/23 V10 原生图达标**；
      7 张 V8 回退图**明确未达标**（记录缺口）。
- [x] 随机、启发式、消融与反旁路实验均可重放（`baselines.suite` + `baseline-results.md`）。
- [x] pytest、ruff、mypy、diff-check 的真实退出码记录（本文件头部与各批 commit）。
- [x] MiMo 预算门禁、预登记、trace、账本和异常恢复可验证（12 个账本 + `mimo-preregistration.json`）。
- [x] 30 图状态不虚报：23 张原生图 8 Gate 全过、7 张回退图带 3-seed 缺口记录；模型失败的归因
      （接口/策略/预算/机制/provider/场景）见 §4 与 `failure-attribution.md`。
- [x] `docs/v10/final-report.md` 含完整前后对照与剩余风险（本文件）。

## 10. 剩余风险（必须披露）

1. **MAP-20 的机制仍未被模型触发**：接口已修（非法动作 0/168），但三局动作直方图显示
   模型**只用 `set_flow` 56/56**、从不使用 `open_bypass`/`adjust_loads`，主指标恒 0；
   需在 V11 判读是“难度过高/提示不足”还是“模型缺少该策略”。
2. **7 张 V8 回退图 3-seed 缺口**（01/02/05/16/17/25/27）：实例对 seed 不敏感，未做 V10 原生参数化。
3. **公式级独立复算未全覆盖**：只有规格驱动五态核对 + 回放确定性 + seed 差异性。
4. **MiMo 单模型、单 replicate、3 seed**：`n` 很小，禁止据此做跨模型排名或显著性断言。
5. **合法替代与作弊仍未完全分离**：MAP-11 `storm_search`；MAP-19/20 的重跑未跑到机制阈值。
6. **难度反转未做认知负担直接测量**：只提供设计/经验/解释三元记录。
7. **`prompt_hash` 与 `rule_hash` 在阶段间不同**（类型化契约 + MAP-20 公开规则）：跨阶段只作配对描述。
8. **MAP-19 seed2 的有效证据**来自修复前完成的 `-r2` 局（非法 0/60），阶段 3b 的对应局中途中断。
9. **早期 9 局的产物布局不同**：`episodes/<run_id>.json` 单文件（含 `history`），后续阶段为
   `episodes/<run_id>/agent_trace.jsonl`；归因器已兼容两种布局，但引用时需注明。

## 11. 结论

V10 的主目标——**让 30 张手工地图具备可证伪、可重复、有区分度的能力测量机制**——已达成：
**30/30 图 `VALIDATED`**（23 张原生图 8 项 Gate 全过；7 张 V8 回退图沿用 V9 并记 3-seed 缺口）、
30 张逐图独立规格与审计卡齐备、154+128 指标有版本化 schema 与独立复核、多环境 seed 与消融证据可重放、
真实模型复测在有界预算内完成。过程中发现并修掉**两类系统性接口假象**——动作字段**类型**未公开
（DCR-V10-24）与 MAP-20 的**取值结构**未公开（DCR-V10-25），两者合计把 4 张图、约 500 次非法动作
从“能力结论”里剔除。剩下的是明确的、可指名的缺口（7 图 seed 参数化、公式级复算、
`KEY_ACTION_USED_NO_TRIGGER` 的逐图判读），而不是“说不清的失败”。
