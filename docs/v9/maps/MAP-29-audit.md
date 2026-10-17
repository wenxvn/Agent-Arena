# MAP-29 不可靠的证人：V9 逐图审计

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-29 / castle / 中等 |
| condition | `default` |
| `scenario_hash` | `6ea1b4f0f4812258081c15ad2f062c3c3bf81141748c25a3216894d13007d5da` |
| `rule_hash` | `9549fbc011f9d9aa9352e3ad12219700d08ac6c22a060dac3a297d642753d3e8` |
| 决策预算 | 38 |
| 问询预算 | 8（全图共享） |
| V8 三局 | 0/3 成功；三局均 `decision_budget_reached`；决策数 38/38/38 |
| V8 主指标 | `contradiction_detection_rate` 0/2（三局）；`evidence_supported_testimony_ratio` N/A（三局）；`query_budget_overruns` 0；`single_witness_trust` 0 |

数据来源：`runs/v9/evidence/MAP-29.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-29-final.md`、`worlds/v4/MAP-29/{map_spec.yaml,DESIGN.md,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map29.py`。

## 1. 能力构念

一句话：**在有限问询预算里做证词分诊，并用独立物证/档案把“谁记错、谁隐瞒、谁只是不知道”区分开**。

- 成功行为：查事件簿得到 23:40 / Y，查停钟证明甲的时间依据失效，查庭院撞针独立复核，对甲或乙完成一次被规则证实的比对，回 H 提交时刻、地点与一名已证不可靠证人。
- 明确反例：把甲错记的 00:05 当事实（时间错）；明知乙把地点说成 L 仍提交 L（地点错）；只凭丙的“双音”就把丙当说谎者（`NO_PROVEN_UNRELIABLE_WITNESS` 或质量下降）；把“同一模板重复问”当新证据（预算被吃掉、答案不变）。
- 递进位置：本图是同世界的中等图。比 MAP-28 多出**证人可靠性**这一层推断（证据全部可靠 → 证词部分不可靠），比 MAP-30 少掉案卷与长间隔召回。难点是“证词只是线索，必须被非证词来源核验”。

## 2. 机制与因果链

起始 H（`local_neighbors=["G","K","L","Y"]`，`npc_locations={"A":"L","B":"K","C":"Y","D":"G"}`）→ 到 G 对丁用 `ARCHIVE_CROSS_INDEX` 得 `ARCHIVE_EVENT_2340_Y`（23:40、Y）→ 到 L 问甲 `OPEN_ACCOUNT`（00:05、Y）与 `TIME_BASIS`（“书房那只钟…停在00:00”）并调查 `study_clock`（`STUDY_CLOCK_STOPPED_0000`）→ 到 Y 调查 `courtyard_bell_trace`（`YARD_BELL_MARK_2340`，23:40）→ 用 `compare_testimony(A, ...)` 把甲的 00:05 与停钟/档案对上，得到 `TIME_CLAIM_CONTRADICTED_AND_EXPLAINED`（`unreliable_proven=["A"]`）→ 回 H `submit(event_time="23:40", event_location="Y", unreliable_npc_id="A", support_ids=[档案, 撞针], unreliability_proof_ids=[...])` → `ALL_OBJECTIVES_COMPLETE`。

- **可绕过点**：`single_witness_trust` 可以靠“提交时把两件独立来源都塞进 support/proof”压低，但 `unreliable_npc_id` 必须真的在 `unreliable_proven` 里（`map29.py:438`），所以不能绕过比对；丙/丁的 `TESTIMONY_CONSISTENT` 无法替代甲的证明。
- **三条轨迹是否触发核心机制**：**没有**。三局合计 34 次 `compare_testimony`，0 次得到 `*_CONTRADICTED_AND_EXPLAINED`；三局均未出现 `unreliable_proven` 非空（DCR 0/2）。提交机制只被触发 3 次（R0 1 次、R1 2 次、R2 0 次），全部因位置错误被拒。
- **最小动作数**：Oracle 13 步（3 问）；公开启发式 17 步（4 问）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| 星形图 `H-L/K/Y/G` 与四名 NPC 位置 | 是 | 初始 `local_neighbors` + `npc_locations` | 是 |
| 五种问询模板 ID | 是 | prompt 词表 | 是 |
| 问题预算 8、重复扣预算 | 是 | 词表写“预算”，`questions_remaining` 每问递减；重复扣预算未写 | 部分：重复问代价要靠 `questions_used` 观察 |
| 每问的 `answer_id/source_ids/typed_payload/rendered_text` | 是 | `heard_answers` | 是（甲 00:05、乙 23:40+L、丙 UNKNOWN、丁 23:40/Y 都可读） |
| 物证 ID 与 fact | 是 | `physical_evidence` | 是 |
| `compare_testimony` 结果码 | 是 | `comparison_results`（按 NPC 覆盖） | 是（但只给成功/不足两态） |
| **`compare_testimony` 的完整性判定**（必须同时给“陈述 ID + 依据 ID + 两件指定证据”） | **否** | 仅 `map29.py:379-411`、`map_spec.yaml:64-65` 的 `A_unreliable_requires`/`B_unreliable_requires` | 否；公开词表只写参数名 |
| **`submit` 必须在 H** | **否** | 仅 `map29.py:429`、`map_spec.yaml:53`（`location: H`） | 否；`goal` 只写“提交准确的事件时刻与地点”，未写位置 |
| 真值 23:40 / Y | 否（judge） | 可由丁的档案与撞针推出 | 是（无需隐藏真值） |
| 提交是单次终局 | 部分 | 词表写“submit”；`DESIGN.md` 写明错误提交一次终结 | 否（prompt 未写“失败不可重试”） |

## 4. 可解性与可观察性

- Oracle：2 个用例，`high_information_first`（13 动作）与 `broad_then_narrow`（23 动作），均 `ok=True`、`scenario_success`。
- **仅凭公开信息是否存在可执行策略**：存在，且已验证。`world_castle.Map29Heuristic` 只用 `heard_answers`/`physical_evidence`/`comparison_results`/`location`：先问丁 `ARCHIVE_CROSS_INDEX`，再问乙 `OPEN_ACCOUNT`、甲 `OPEN_ACCOUNT`+`TIME_BASIS`，查停钟与撞针，然后对 A、B 各做一次“**把该场景全部已知陈述与全部已知证据一起提交**”的比对，17 步成功、DCR 2/2、采信比 3/3。
- 这个超集写法说明私有完整性规则是**子集检验**（`complete` 只查必需项 ∈ 集合，多给不罚）。它是公开合法的动作，但公开文本没有提示“多给无害”，因此模型无法从契约推断。
- `compare_testimony` 契约可理解性判定：**不可理解，但不致命**。证据：三局 34 次比对里 30 次是 `COMPARE_INSUFFICIENT_EVIDENCE`（另 2 次 `EVIDENCE_NOT_OBSERVED`、1 次 `INVALID_STATEMENT_ID`、1 次 `TESTIMONY_CONSISTENT`），模型每次只提交“一条陈述 + 一件物证”的子集（R0 决策 12/17/25/36/37/38，R1 决策 15/17/33，R2 决策 9/15/19/27），结果码不指出缺哪一项，形成无梯度试错。
- `BUDGET_BLOCKED` 判定：**不成立**。问询预算 0 次超支（`query_budget_overruns=0`），实际只用 7/7/6 问（上限 8）；决策预算 38，Oracle 13、启发式 17。

## 5. 预算可行性

- Oracle 13（3 问）/ 23（7 问）动作 / 预算 38；启发式 17 动作 / 4 问。
- `legal_random` 20 seeds：成功 0/20；19 局 `failure`（`CASE_REJECTED`），1 局 `decision_budget_reached`；决策数分布 `[1,1,1,1,2,2,3,3,4,4,4,5,5,5,7,8,8,13,15,38]`；拒绝动作 110 次、非法形状 0 次。随机基线大量“秒提交”被拒，说明本图对乱提交有强惩罚。
- 公开启发式：17 决策、0 拒绝、`ALL_OBJECTIVES_COMPLETE`，DCR 2/2、采信比 3/3、超支 0、单证人 0。
- 消融 `no_compare`：15 决策，`CASE_REJECTED`（未证明任何不可靠证人），DCR 0/2、采信比 2/3。
- 判定：**不是预算不够，是模型没做对**。三局分别有 38/38/38 步，其中 15/8/11 步用于比对，却没有一次把“陈述 + 依据 + 档案 + 物证”凑齐；同时三局只有 R0 在决策 35 才拿到 `ARCHIVE_EVENT_2340_Y`（唯一一次问到丁的索引模板）。

## 6. 指标

| 指标 | 事件 | 分母 | 缺失/截尾 | 三局取值 |
|---|---|---|---|---|
| `map29.contradiction_detection_rate` | `unreliable_proven` 中属于 A/B 的个数 | 2（植入矛盾数） | 未比对 → 0（合法） | 0/2 ×3 |
| `map29.evidence_supported_testimony_ratio` | 提交时被采信的 3 项（时刻、地点、不可靠证人）中由 ≥1 独立非证词来源支持的数量 | 3 | 未提交 → `None`（N/A） | N/A ×3 |
| `map29.query_budget_overruns` | `QUESTION_BUDGET_EXHAUSTED` 次数 | 每局 | — | 0 ×3 |
| `map29.single_witness_trust` | 三项采信各自的独立非证词来源 <2 的次数（0–3） | 每局 | 未提交 → 0 | 0 ×3 |

- **未通关仍有意义的连续指标**：`contradiction_detection_rate` 是纯过程量，0/2、1/2、2/2 都能出现，三局 0 说明“比对机制从未成功”，这是有信息量的失败信号。
- 三局的 `not_applicable`：`evidence_supported_testimony_ratio` 三局全 N/A 的原因**是真分母为 0**——`metrics()` 在 `self.submitted is False` 时返回 `None`（`map29.py:507-512`），三局都没有一次被接受的提交（R0/R1 的提交被 `INVALID_LOCATION` 挡下，R2 没有提交动作）。这是“未提交”而不是“投影口径丢失”。
- 区分度：DCR 能区分启发式（2/2）、`no_compare` 消融（0/2）与随机（0/2）；采信比能区分启发式（3/3）与 `no_compare`（2/3）；但 V8 三局与随机基线在 DCR 上同值 0，说明**当前模型与随机基线在这条主指标上不可区分**。

## 7. 三次轨迹归因

### R0（`V8-MAP-29-R0-20261017T105544Z-260b1802`，38 决策，`decision_budget_reached`）

- 决策 1 `{"npc_id": "D", "question_template_id": "TIME_BASIS", "tool": "ask"}` → `INVALID_LOCATION`，`{"tick": 1}`：人在 H 问 G 的丁。
- 决策 3 `{"npc_id": "D", "question_template_id": "TIME_BASIS", "tool": "ask"}` → `NO_ADDITIONAL_KNOWLEDGE`，`heard_answers` 首次出现 `D_NO_ADDITIONAL_KNOWLEDGE`（“档案里没有这类索引。”），`questions_remaining` 8→7、`questions_used` 0→1：模板猜错，白扣 1 问。
- 决策 8 `{"against_evidence_ids": ["study_clock", "courtyard_bell_trace"], "npc_id": "A", "statement_ids": ["A_TIME_CLAIM_0005", "A_LOCATION_CLAIM_Y"], "tool": "compare_testimony"}` → `EVIDENCE_NOT_OBSERVED`，`{"tick": 8}`：把目标名（`study_clock`）当证据 ID。
- 决策 12 `{"against_evidence_ids": ["STUDY_CLOCK_STOPPED_0000"], "npc_id": "A", "statement_ids": ["A_TIME_CLAIM_0005"], "tool": "compare_testimony"}` → `COMPARE_INSUFFICIENT_EVIDENCE`，`{"comparison_results": {"A": "COMPARE_INSUFFICIENT_EVIDENCE"}, "tick": 12}`。
- 决策 28 `{"event_location": "Y", "event_time": "23:40", "support_ids": ["YARD_BELL_MARK_2340", "C_SOUND_ONLY"], "tool": "submit", "unreliability_proof_ids": ["STUDY_CLOCK_STOPED_0000", "YARD_BELL_MARK_2340"], "unreliable_npc_id": "A"}` → `INVALID_LOCATION`，`{"tick": 28}`：人在 Y 提交；且证据 ID 拼错一位（`STOPED`），若当时在 H 会直接 `CASE_REJECTED`。
- 决策 35 `{"npc_id": "D", "question_template_id": "ARCHIVE_CROSS_INDEX", "tool": "ask"}` → `ANSWER_RECEIVED:ARCHIVE_EVENT_2340_Y`，`heard_answers` 追加丁的“交叉索引记载：23:40，庭院Y银铃撞击一次。”——**这是三局中唯一一次拿到档案真值，发生在第 35 步**，此时已无法再补比对与提交。
- 首次偏离：决策 1（未到 NPC 位置就问）与决策 3（把 `TIME_BASIS` 用在丁身上）。失败链：模板盲试 → 早问错人 → 比对反复用子集 → 直到 35 步才拿到档案 → 38 步耗尽。
- 替代解释：预算不足？否（7 问、38 步）。接口误导？是（比对完整性、提交位置）。

### R1（`V8-MAP-29-R1-20261017T105936Z-ec83d220`，38 决策，`decision_budget_reached`）

- 决策 8 `{"npc_id": "B", "question_template_id": "OPEN_ACCOUNT", "tool": "ask"}` → `ANSWER_RECEIVED:B_OPEN_ACCOUNT`，`heard_answers` 新增“那声铃大约在23:40，我记得是在书房L。”，`source_ids=["B_LOCATION_CLAIM_L"]`。
- 决策 9 `{"against_evidence_ids": ["study_clock", "courtyard_bell_trace"], "npc_id": "B", "statement_ids": ["B_LOCATION_CLAIM_L"], "tool": "compare_testimony"}` → `EVIDENCE_NOT_OBSERVED`，`{"tick": 9}`（同一类“目标名 vs 证据 ID”错误）。
- 决策 15 `{"against_evidence_ids": ["STUDY_CLOCK_STOPPED_0000"], "npc_id": "B", "statement_ids": ["B_LOCATION_CLAIM_L"], "tool": "compare_testimony"}` → `COMPARE_INSUFFICIENT_EVIDENCE`，`{"comparison_results": {"B": "COMPARE_INSUFFICIENT_EVIDENCE"}, "tick": 15}`：乙的地点矛盾需要“档案 + 撞针”，模型只给停钟。
- 决策 17 → `COMPARE_INSUFFICIENT_EVIDENCE`，`comparison_results` 同时出现 A、B 两项不足。
- 决策 27 `{"event_location": "L", "event_time": "23:40", "support_ids": ["B_LOCATION_CLAIM_L"], "tool": "submit", "unreliability_proof_ids": ["A_TIME_BASIS_STOPPED_0000", "STUDY_CLOCK_STOPPED_0000"], "unreliable_npc_id": "A"}` → `INVALID_LOCATION`，`{"tick": 27}`：人在 L；且提交地点沿用乙的假地点 L。
- 首次偏离：决策 9（把 `study_clock` 当证据 ID）；决策 27（位置与地点同时错）。
- 失败链：只拿到 B 的开放叙述与 A 的时间依据 → 8 次比对全部子集 → 两次在 L 提交 → 38 步耗尽。合计 5 次 `INVALID_LOCATION`、6 次 `NO_ADDITIONAL_KNOWLEDGE`。
- 替代解释：模型是否“知道”乙在说谎？它确实问出了 L 的说法，但从未拿到档案去证伪；R1 全程没有问丁的 `ARCHIVE_CROSS_INDEX`。

### R2（`V8-MAP-29-R2-20261017T110340Z-482b3e69`，38 决策，`decision_budget_reached`）

- 决策 7 `{"npc_id": "A", "question_template_id": "TIME_BASIS", "tool": "ask"}` → `ANSWER_RECEIVED:A_TIME_BASIS`，`heard_answers` 新增“我看的是书房那只钟；后来才发现它停在00:00。”，`source_ids=["A_TIME_BASIS_STOPPED_0000"]`。
- 决策 9 `{"against_evidence_ids": ["STUDY_CLOCK_STOPPED_0000"], "npc_id": "A", "statement_ids": ["A_TIME_BASIS_STOPPED_0000"], "tool": "compare_testimony"}` → `COMPARE_INSUFFICIENT_EVIDENCE`，`{"comparison_results": {"A": "COMPARE_INSUFFICIENT_EVIDENCE"}, "tick": 9}`：只给“依据 + 停钟”，缺 `A_TIME_CLAIM_0005` 与 `ARCHIVE_EVENT_2340_Y`。
- 决策 13 `{"against_evidence_ids": ["STUDY_CLOCK_STOPPED_0000"], "npc_id": "B", "statement_ids": ["B_TIME_BASIS"], "tool": "compare_testimony"}` → `INVALID_STATEMENT_ID`，`{"tick": 13}`：编造了一个不存在的陈述 ID。
- 决策 24 `{"target_id": "study_clock", "tool": "investigate"}` → `EVIDENCE_FOUND:STUDY_CLOCK_STOPPED_0000`，`{"tick": 24}`：重复调查已发现的物证（观察不再变化，只涨 tick）。
- 结局：46 次工具调用里没有一次 `submit`（`tools` 统计：ask 9、move 11、investigate 7、compare 11、submit 0），38 步耗尽。
- 首次偏离：决策 9（缺少“陈述 ID”这一半）；决策 13 编造 ID 说明模型不清楚陈述 ID 必须来自 `heard_answers.source_ids`。
- 失败链：只问 A 的 `TIME_BASIS`、B 的 `LOCATION_BASIS` → 11 次子集比对 → 从未问丁档案、从未提交。
- 重复证据说明：三局都是“子集比对 + 无档案 + 位置错”的同一模式（R2 连提交都没做）。**n=3 不能区分个体差异与固定接口陷阱**。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | C schema/接口误导（`compare_testimony` 完整性规则私有、错误码无梯度） | E 策略规划错误（先问错 NPC 模板、35 步才问档案）+ B（提交位置未公开） | 高 | 决策 3/8/12/28/35 |
| R1 | C 接口误导（同一比对规则） | E 策略错误（沿用乙的 L、两次在 L 提交）+ B | 高 | 决策 9/15/27 |
| R2 | C 接口误导（陈述 ID 来源不明确） | E 策略错误（不问丁、不提交） | 高 | 决策 9/13；`submit` 0 次 |

没有 A（规则缺陷）、D（预算）、F（资源）、H（运行异常）。G（记忆/推理）只有弱证据：模型多次忘记自己已问过谁，但这不足以解释 34 次比对全败。

## 9. 标签

- `MEASUREMENT_VALID`：Oracle 13 步、公开启发式 17 步都成功，DCR 与采信比能区分启发式/消融/随机。
- `INTERFACE_BLOCKED`（部分）：`compare_testimony` 的完整性判定与 `submit` 的 H 位置都未公开（`map_spec.yaml:53,64-65`、`map29.py:379-411,429`）；三局 34 次比对无一得到矛盾判定。
- 不标 `BUDGET_BLOCKED`：问询预算只用 6–7/8，决策 38 vs Oracle 13。
- 不标 `METRIC_DEFECT`：采信比 N/A 是真分母 0（无提交）。
- 不标 `RULE_DEFECT`：比对与提交规则自洽，fixture 覆盖了“证明乙说谎仍提交 L”的失败路径。

## 10. 最小可证伪修复（无证据不修改）

候选只改公开信息，不改规则：

- **候选 A（首选）**：在 `submit` 的公开词表补“只能在 H 提交，一次终局”，并在 `compare_testimony` 的描述里补语义：“把陈述与其依据、以及 ≥2 件独立证据一起提交；比对只看必需项是否被覆盖，多余项不影响结果”。证据：三局 34 次比对全为子集、30 次 `COMPARE_INSUFFICIENT_EVIDENCE`；R0/R1 在非 H 提交。预期变化：DCR 从 0 有机会变成 1–2；不泄漏哪一位 NPC 不可靠（仍需自己选）。
- **候选 B（次选）**：让 `COMPARE_INSUFFICIENT_EVIDENCE` 附一带宽度的公开提示（如“缺少 2 类来源中的 1 类”），不列具体 ID。证据：决策 12/17/25 反复用同一子集，说明零梯度会诱发重复尝试。风险：提示过细会让“分诊”退化成照抄。
- **候选 C（不推荐）**：直接把 `A_unreliable_requires`/`B_unreliable_requires` 贴进 prompt。**反例**：MAP-29 的核心构念是“在有限预算里自己决定问什么、拿什么证据去证伪”，直接给集合等于给答案，会把本图变成 MAP-28 的低配复制。
- 若不做修改：本图仍是 `MEASUREMENT_VALID`（有 17 步可复现策略），但模型侧失败会把“接口不可理解”误读成“证人可靠性推断能力不足”，报告必须分开。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-29.json`：

| 基线 | 结果 | 决策 | 主指标 |
|---|---|---|---|
| Oracle `high_information_first` | `scenario_success` | 13 | — |
| Oracle `broad_then_narrow` | `scenario_success` | 23 | — |
| legal_random（20 seeds） | 0/20 成功（19 failure + 1 预算耗尽） | 1–38 | — |
| public_heuristic | `ALL_OBJECTIVES_COMPLETE` | 17 | DCR 2/2、采信比 3/3、超支 0、单证人 0 |
| ablation `no_compare` | `CASE_REJECTED` | 15 | DCR 0/2、采信比 2/3、单证人 0 |

**独立复算**：不调用 `v7` extractor，只用最终 Observation 的公开 `comparison_results` 计数（`TIME_CLAIM_CONTRADICTED_AND_EXPLAINED` 或 `LOCATION_CLAIM_CONTRADICTED_AND_EXPLAINED` 的条目数 / 2）。

- 启发式最终 `comparison_results = {"A": "TIME_CLAIM_CONTRADICTED_AND_EXPLAINED", "B": "LOCATION_CLAIM_CONTRADICTED_AND_EXPLAINED"}` → 2/2，与 extractor 一致。
- V8 三局最终 `comparison_results` 分别为 `{"A": "COMPARE_INSUFFICIENT_EVIDENCE", "C": "TESTIMONY_CONSISTENT"}`（R0）、`{"A": "COMPARE_INSUFFICIENT_EVIDENCE", "B": "COMPARE_INSUFFICIENT_EVIDENCE"}`（R1）、`{"A": "COMPARE_INSUFFICIENT_EVIDENCE", "B": "COMPARE_INSUFFICIENT_EVIDENCE"}`（R2）→ 0/2，与 judge 一致。
- 采信比独立口径：三局无被接受提交 → 分母 0 → 判 N/A（与 extractor 的 `None` 一致）；启发式 `support_ids=[ARCHIVE_EVENT_2340_Y, YARD_BELL_MARK_2340]` 与 `unreliability_proof_ids` 含 A 的时间陈述、依据、停钟、档案 → 3/3。

区分度：DCR 在“启发式 vs 其余”上有区分，但在“模型 vs 随机”上同为 0 → 该主指标对当前模型**不可区分**，需配合“比对成功率（31/34 失败）”这类过程量才能定位问题。

## 12. V9 状态

**`NEEDS_REDESIGN`，P1。** 理由：构念与预算都成立（13/17 步可复现成功，问询预算未触顶），0/3 与 DCR=0 的主因是比对完整性规则和提交位置未公开、且错误码无梯度；补公开语义（候选 A/B）后可直接验证“证词分诊”能力是否真的缺失。
