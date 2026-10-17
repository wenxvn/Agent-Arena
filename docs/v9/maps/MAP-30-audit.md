# MAP-30 三层庭审：V9 逐图审计

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-30 / castle / 困难（V4 适配图） |
| condition | `history5_casebook`（`casebook_visible=True`，见 `src/agent_arena/v6/catalog.py:31,104-107`） |
| `scenario_hash` | `a6826866eba03a4ab06a4b81d35120c537d97ca35db20658fa7ee2b445fa5914`（V6 实例 `map30_l3_original`） |
| `rule_hash` | `f53fe656d63daa23fc2dea7aefa765bf8a4272104aa9b300b7a69ac60f6af810` |
| 决策预算 | 46 |
| 环境 horizon | 40 tick（`Map30Case.deadline = 40`，`map30.py:256,386-393`） |
| V8 三局 | 0/3 成功；三局均 `decision_budget_reached`；决策数 46/46/46（实际 tick 37/37/37） |
| V8 主指标 | `evidence_chain_coverage` 0/4 ×3；`investigation_progress` 0/4、2/4、2/4；`chain_reconciled` 0 ×3；`accusation_claim_precision` N/A、N/A、2/3；`q4_recall_accuracy` N/A、N/A、0 |
| 合法动作率 | 37/46、37/46、39/46 |

数据来源：`runs/v9/evidence/MAP-30.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-30-final.md`、`worlds/v4/MAP-30/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v4/map30.py`、`src/agent_arena/worlds/scenario_v8/v4_adapter.py`、`src/agent_arena/v7/metrics/map30.py`。

> **证据包缺陷（先记）**：`src/agent_arena/v9/evidence.py::_compact_action` 的字段白名单不含 `event_claims`、`citations_by_claim`、`shown_evidence_ids`、`shown_casebook_entry_ids`。因此 `runs/v9/evidence/MAP-30.json` 里所有 `interview` 都显示“没有出示任何证据/案卷条目”，R2 决策 18 的 `formal_accuse` 也丢了 `event_claims`。这些结论与原始 `runs/v8/supplement_005/experiments/episodes/V8-MAP-30-R*/agent_trace.jsonl` 矛盾，本节一律以原始 Trace 为准。

## 1. 能力构念

一句话：**跨 5 条近期事件窗口与 40 tick 听证边界，把“一次性观察”沉淀成可引用的案卷，再用案卷解锁证人记忆并完成一次有据指控**。

- 成功行为：取证与证人确认成对写入 4 个固定条目，`compare_records` 得到 `CHAIN_COHERENT`，在 J 提交 3 条事件主张与 Q4 条目，且人名是 `MARA_VENN`。
- 明确反例：只记录物证不记录证人确认（`evidence_chain_coverage` 0）；把 Q4 索引看到却不入卷（`q4_recall_accuracy=0`）；把五条窗口外的证据当作仍可引用（`EVIDENCE_NOT_AVAILABLE`）；在非 J 提交（`COURTROOM_REQUIRED`）；第二次无据指控（`ACCUSATION_LIMIT_EXCEEDED`）。
- 递进位置：同世界最难的一图。MAP-28 只考“双来源交叉”，MAP-29 只考“证词分诊”，本图同时叠加：近期窗口、结构化案卷、条件化证人、事件顺序、单次可恢复指控。它是唯一有“记忆结构”而不只是“记忆长度”的图。

## 2. 机制与因果链

起始 H（`local_neighbors=["B","J","L"]`）→ B 检查 `B_KEY_STUB_2310`（23:10 / K7 / M-4）→ `record(EVENT_1_HANDOFF, [stub])` → 对 `BANQUET_CLERK` 出示 stub 得 `B_WITNESS_HANDOFF` → 记录进 EVENT_1（此时条目才“完整”）→ K 检查蜡板 → 记录 EVENT_2 物证 → 对 `KITCHEN_COOK` 出示**完整的** EVENT_1 条目得 `K_WITNESS_WAX_ROUTE` → 记录 → T 检查链轮 → 记录 EVENT_3 → 对 `TOWER_WATCH` 出示完整 EVENT_2 得 `T_WITNESS_SIGNAL_ROUTE` → 记录 → A 检查 Q4 封套 → 对 `ARCHIVE_CLERK` 出示封套得 `Q4_CODE_INDEX`（M-4 ↔ MARA_VENN）→ 记录 Q4 条目 → `compare_records([Q4, E1, E2, E3])` → `CHAIN_COHERENT` → 经 L/H 到 J → `formal_accuse(MARA_VENN, 三条 event_claims, 四个 cited_entry_ids)` → `ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN`。

- **可绕过点**：`submit_intermediate_hypothesis` 对胜负完全无效（`hypotheses_adjudicated=False`，`map30.py:622`），只花 tick；R1 用了 2 次、R2 用了 1 次，属于纯开销。案卷不能绕过：`formal_accuse` 的 `complete` 要求 4 个条目都被引用、`chain_reconciled=True`、且每个条目的 `entry_required ⊆ casebook[entry]`（`map30.py:511-519`）。
- **三条轨迹是否触发核心机制**：
  - `record` 被调用 19 次，仅 4 次成功（R1 2 次、R2 2 次），R0 的 6 次全失败。
  - “出示案卷条目解锁证人”只被尝试 1 次（R2 决策 21，给 `KITCHEN_COOK` 出示 `["EVENT_2_WAX"]`，但 `topic_id` 用了 `EVENT_1_HANDOFF`），仍返回 `K_GENERIC_OVEN_MEMORY`。
  - `compare_records` 被调用 3 次（都在 R1），全部 `CASEBOOK_ENTRY_NOT_FOUND` 或 `CODE_KEY_NOT_RECORDED`，从未 CHAIN_COHERENT。
  - `formal_accuse` 只调用 1 次（R2 决策 18），在 A 被判 `COURTROOM_REQUIRED`。
  - 结论：机制在 3×46 步里**从未完整执行一次**。
- **最小动作数**：Oracle 25 步；公开启发式 24 步（24 tick）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| 节点、局部邻边 | 是 | `current_node`、`local_neighbors` | 是（需自己走出全图） |
| 节点上的物证 ID | 是 | `visible_local_evidence`（看过即消失） | 是 |
| 五条近期事件窗口与其中 payload | 是 | `recent_action_window`（最多 5 条） | 部分：窗口滚动规则未明说 |
| 案卷内容（entry_id、evidence_ids、fact、rendered_text） | **是**（`casebook`，本条件公开且持久） | 每次 `record` 后 | 是 |
| `topic_id` 四值 | 是 | prompt 词表 | 是 |
| **`record` 的 `entry_id` 合法值** | **否** | 仅 `map30.py:37-42`；恰好与 `topic_id` 同名但未说明 | 否；只能靠 4 次 `INVALID_CASEBOOK_ENTRY` 猜 |
| **条目 ↔ 证据的允许映射**（EVENT_1 只收 B 侧两件；Q4 只收 `Q4_CODE_INDEX`） | **否** | 仅 `map30.py:37-42` | 否 |
| **每个事件条目必须“物证 + 证人确认”成对才算完整** | **否** | `entry_required = entry_allowed`（`map30.py:43,260-262`），`compare_records` 只在满足时 CHAIN_COHERENT | 否 |
| **`formal_accuse` 必须在 J** | **否** | `map30.py:504-505`；`public_alert="MIDNIGHT_TRIAL_PENDING"` 只暗示“午夜审判” | 否；`J` 从初始邻接里可见，但没有“J=法庭”的说明 |
| **`event_claims` 必须按 1→2→3 顺序且四字段精确相等** | 部分 | action 契约公开子字段 `event_id/time/location/duty_code`；顺序要求未写 | 部分 |
| 40 tick 截止 | 否 | `Map30Case.deadline`；只有失败码 `DEADLINE_REACHED` 会暴露 | 否 |
| 真值 MARA_VENN / 三事件时间地点 | 否 | judge；但可由 Q4 索引与各物证 fact 推出 | 是（无需隐藏真值） |

## 4. 可解性与可观察性

- Oracle：1 个用例 `MAP-30-solver-success`，25 动作，`ok=True`、`scenario_success`。
- **仅凭公开信息是否存在可执行策略**：存在，且已验证。`world_castle.Map30Heuristic` 只用 `current_node/local_neighbors/visible_local_evidence/recent_action_window/casebook`，24 步成功：`evidence_chain_coverage` 4/4、`chain_reconciled` 1、`q4_recall_accuracy` 1、`accusation_claim_precision` 3/3、`legal_action_rate` 24/24。
- 但该策略编码了两处**设计知识**：`ENTRY_OF`（证据→条目名）与 `NODE_OF`/邻接表。前者不可从 Observation 推出（`record` 失败时只回 `INVALID_CASEBOOK_ENTRY`，不列合法值），后者可通过移动探索得到。
- 因此本图判 `INTERFACE_BLOCKED`（部分）：没有 `entry_id` 词表与“成对完整”规则，模型只能用“段名换个写法”盲试；三局 19 次 `record` 中 14 次是 `INVALID_CASEBOOK_ENTRY`。
- `BUDGET_BLOCKED` 判定：**不成立**。46 决策 / 40 tick，Oracle 25、启发式 24；三局实际只推进到 tick 37 就耗尽决策，且 37 个 tick 里没有一次进入“条目完整”的状态。

## 5. 预算可行性

- Oracle 25 / 预算 46；启发式 24。全合法路线最多只能走 40 tick（`deadline`），所以 46 决策里最多 40 个“有效”动作，其余必须是 0 tick 的拒绝动作——三局的 9/9/7 个拒绝动作正好解释了 46 决策只到 tick 37。
- `legal_random` 20 seeds：成功 0/20；16 局 `decision_budget_reached`、4 局 `ACCUSATION_LIMIT_EXCEEDED`；决策数 `[20,26,29,34,46×16]`；拒绝动作 233 次、非法形状 0。
- 公开启发式：24 决策、0 拒绝、成功。
- 消融 `no_casebook`（不 record、不展示案卷条目，只靠近期窗口）：12 决策，`ACCUSATION_LIMIT_EXCEEDED`，`evidence_chain_coverage` 0/4、`accusation_claim_precision` 0/3。
- 判定：**不是预算不够，是案卷纪律 + 接口词表没做对**。三局分别有 6/7/6 次 `record`，说明模型知道要记录，但 14 次写错条目名、2 次被近期窗口判失效、3 次只写了物证一半。

## 6. 指标

| 指标 | 事件 | 分母 | 缺失/截尾 | 三局取值 |
|---|---|---|---|---|
| `map30.evidence_chain_coverage` | `entry_required[entry] ⊆ casebook[entry]` 的条目数 | 4 | casebook 字段缺失 → UNAVAILABLE | 0/4 ×3 |
| `map30.investigation_progress` | `len(casebook)` | 4 | 同上 | 0、2/4、2/4 |
| `map30.accusation_claim_precision` | `max(0, matched_expected - extra) / 3` | 3 | 无指控 → N/A | N/A、N/A、2/3 |
| `map30.q4_recall_accuracy` | `person==culprit and Q4_CODEBOOK ∈ cited_entry_ids` | 提交过 formal_accuse 的 episode | 无指控 → N/A | N/A、N/A、0 |
| `map30.chain_reconciled` | 任一 `CHAIN_COHERENT` | 每局 | — | 0 ×3 |
| `map30.legal_action_rate` | 被接受决策 / 提交决策 | 决策数 | — | 37/46、37/46、39/46 |
| `map30.unsupported_accusations` | 最终无据指控数 | 每局 | — | 0 ×3 |

- **未通关仍有意义的连续指标**：`investigation_progress` 0 → 0.5 已经能区分“案卷全空”与“写进两个条目”；`evidence_chain_coverage` 在三局恒 0，是因为它要求“成对完整”，比 `investigation_progress` 严格一档——这正是本图想测的差别，不是指标坏死。
- `not_applicable`：R0/R1 的 `accusation_claim_precision` 与 `q4_recall_accuracy` 是 N/A，原因是**没有 `formal_accuse`**（真分母 0）。R2 有指控动作，所以给出 2/3 与 0。
- **两处指标缺陷（事实，可复现）**：
  1. `accusation_claim_precision` 取的是**最后一条 `formal_accuse` 事件的动作**（`v7/metrics/map30.py:198-203`），不检查该动作是否被接受。R2 决策 18 的动作结果是 `COURTROOM_REQUIRED`（人在 A，指控根本没有进入法庭），仍被算成 2/3。
  2. `q4_recall_accuracy` 只检查“人名对 + 引用了 `Q4_CODEBOOK` 这个条目名”（`v7/metrics/map30.py:251-257`），不要求该条目真的记录过、也不要求 `chain_reconciled`。消融 `no_casebook` 在 `evidence_chain_coverage=0` 的情况下仍得到 `q4_recall_accuracy=1`。
- 区分度：`investigation_progress` 与 `legal_action_rate` 能区分启发式（4/4、24/24）、消融（0/4、9/12）与三局（0–2/4）；`accusation_claim_precision` 因上述缺陷会**高估**未进入法庭的指控。

## 7. 三次轨迹归因

### R0（`V8-MAP-30-R0-20261017T110714Z-a635ed01`，46 决策，tick 37）

- 决策 3 `{"entry_id": "E1_KEY_HANDOFF", "evidence_ids": ["B_KEY_STUB_2310"], "tool": "record"}` → `INVALID_CASEBOOK_ENTRY`，观察变化 `{}`（连 tick 都不涨）：`E1_KEY_HANDOFF` 不是合法条目名。
- 决策 10（原始 Trace）`{"npc_id": "TOWER_WATCH", "shown_casebook_entry_ids": [], "shown_evidence_ids": ["T_CHAIN_REGISTER_2340"], "tool": "interview", "topic_id": "EVENT_3_SIGNAL"}` → `ANSWER_RECEIVED:T_GENERIC_NIGHT_MEMORY`，`recent_action_window` 里出现 `condition_key="SIGNAL_without_event_2"` 与“午夜前有人经过塔楼，但我记不清是哪一次巡更。”：守塔人需要的是**事件 2 的完整案卷条目**，出示物证不够。
- 决策 31 `{"npc_id": "ARCHIVE_CLERK", "shown_casebook_entry_ids": [], "shown_evidence_ids": ["Q4_ARCHIVE_DOCKET"], "tool": "interview", "topic_id": "Q4_CODEBOOK"}` → `NPC_NOT_HERE`，`{}`：它把 Q4 封套留到了 H，人在 H 问 A 的档案员。
- 决策 39 `{"to": "K", "tool": "move"}` → `INVALID_MOVE`，`{}`：H 只连 B/J/L。
- 首次偏离：决策 3——它已经拿到正确证据，但条目名取错，之后 5 次 `record` 继续在 `E1_KEY_HANDOFF/E2_WAX_SEAL/E3_SIGNAL/E2_WAX` 上打转（6 次 `INVALID_CASEBOOK_ENTRY`）。
- 失败链：条目名错 → 案卷恒空 → 条件化证人全部退化为 generic → 30 次 move 空转 → 从未 compare/accuse。`casebook` 的最终观察是 `[]`。
- 替代解释：记忆不足？不成立（本局案卷为空，是“写不进去”而非“想不起来”）。

### R1（`V8-MAP-30-R1-20261017T111157Z-c722a70c`，46 决策，tick 37）

- 决策 4（原始 Trace）`{"npc_id": "BANQUET_CLERK", "shown_casebook_entry_ids": [], "shown_evidence_ids": ["B_KEY_STUB_2310"], "tool": "interview", "topic_id": "EVENT_1_HANDOFF"}` → `ANSWER_RECEIVED:B_WITNESS_HANDOFF`，`recent_action_window` 新增 `B_WITNESS_HANDOFF`（“核对回执后，我确认23:10是M-4本人取走K7。”）。
- 决策 5 `{"entry_id": "E1_HANDOFF", "evidence_ids": ["B_KEY_STUB_2310", "B_WITNESS_HANDOFF"], "tool": "record"}` → `INVALID_CASEBOOK_ENTRY`，`{}`：证据已经成对，只是条目名差一个前缀。
- 决策 15 `{"entry_id": "EVENT_2_WAX", "evidence_ids": ["K_WAX_PLATE_2322"], "tool": "record"}` → `ENTRY_RECORDED:EVENT_2_WAX`，`casebook` 首次出现 `{"entry_id": "EVENT_2_WAX", "evidence_ids": ["K_WAX_PLATE_2322"], "recorded_evidence": [{"evidence_id": "K_WAX_PLATE_2322", "fact": {"duty_code": "M4", "location": "K", "object": "wax_plate", "time": "23:22"}, ...}]}`。
- 决策 19 `{"entry_ids": ["EVENT_2_WAX", "EVENT_3_SIGNAL"], "tool": "compare_records"}` → `CODE_KEY_NOT_RECORDED`，`{"current_tick": 12, ...}`：Q4 没入卷。
- 决策 22 → `ANSWER_RECEIVED:ARCHIVE_Q4_INDEX_CONFIRMED`，`recent_action_window` 出现 `Q4_CODE_INDEX`（`fact={"M4": "MARA_VENN", "document_id": "Q4"}`）——**得到了召回靶子，却没有 `record(Q4_CODEBOOK, [Q4_CODE_INDEX])`**。
- 首次偏离：决策 5（条目名），第二处是决策 22 之后的“只看到不记录”。
- 失败链：EVENT_1 写不进去 → 厨师永远 generic（决策 9 `K_GENERIC_OVEN_MEMORY`）→ E2/E3 只有物证一半 → compare 失败 → 24 次 move 收尾。最终 `casebook` 只有 `EVENT_2_WAX`、`EVENT_3_SIGNAL` 两个不完整条目。

### R2（`V8-MAP-30-R2-20261017T111639Z-e8be28b2`，46 决策，tick 37）

- 决策 11 `{"entry_id": "EVENT_1_HANDOFF", "evidence_ids": ["B_KEY_STUB_2310", "B_WITNESS_HANDOFF"], "tool": "record"}` → `EVIDENCE_NOT_AVAILABLE`，`{}`：条目名这次对了、两件证据也对，但 `B_WITNESS_HANDOFF` 是决策 4 的产物，已被 5 条近期事件窗口挤出（`_available_evidence` = `recent_events[-5:] ∪ casebook`，`map30.py:364-371`）。**这是三局中唯一一次真正的“长间隔召回”被触发。**
- 决策 12/13 `record(EVENT_3_SIGNAL, [T_CHAIN_REGISTER_2340])` → `ENTRY_RECORDED:EVENT_3_SIGNAL`，`casebook` 出现该条目；随后 `ENTRY_RECORDED:EVENT_2_WAX`，`casebook` 变为两条。
- 决策 18（原始 Trace）`{"cited_entry_ids": ["EVENT_2_WAX", "EVENT_3_SIGNAL"], "event_claims": [{"duty_code": "M4", "event_id": "EVENT_2_WAX", "location": "K", "time": "23:22"}, {"duty_code": "M4", "event_id": "EVENT_3_SIGNAL", "location": "T", "time": "23:40"}], "person_id": "MARA_VENN", "tool": "formal_accuse"}` → `COURTROOM_REQUIRED`，`{}`：人在 A；指控没有发生，但指标仍按这条动作算了 2/3（见 §6）。
- 决策 21 `{"npc_id": "KITCHEN_COOK", "shown_casebook_entry_ids": ["EVENT_2_WAX"], "shown_evidence_ids": ["K_WAX_PLATE_2322"], "tool": "interview", "topic_id": "EVENT_1_HANDOFF"}` → `ANSWER_RECEIVED:K_GENERIC_OVEN_MEMORY`：它终于用案卷条目去解锁证人，但 `topic_id` 用错（问厨师的是事件 1），所以没有触发 `WAX_with_event_1`。
- 首次偏离：决策 11（没有在拿到证人确认的当步就记录，5 步后被窗口判失效）。
- 失败链：EVENT_1 丢失 → 厨师无法解锁 → 事件 2 只有物证 → 4 个条目都不完整 → compare 不可能成立 → 在错误节点指控 → 30 次 move 空转到预算上限。
- 重复证据说明：R1 与 R2 都是“条目写一半 + Q4 不入卷”的同一模式；R0 是“条目名全错 + 案卷全空”。**n=3 只覆盖了两种失败形态，不能区分个体差异与固定接口陷阱。**

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | C schema/接口误导（`entry_id` 合法值未公开，6 次全部写错） | E 策略错误（Q4 封套留到 H 才用、30 次 move 空转） | 高 | 决策 3/6/9/11/13/17/31 |
| R1 | C 接口误导（`entry_id` 词表） | G 记忆/推理（Q4 索引看到不入卷；EVENT_1 成对证据写不进） | 高 | 决策 5/10/22；`casebook` 只有 2 条不完整条目 |
| R2 | G 记忆/推理（证人确认未即时入卷，5 条窗口后失效） | C 接口误导（成对完整规则、法庭节点 J 未公开）+ E（topic 用错） | 高 | 决策 11/18/21 |

没有 A（规则缺陷）、D（预算）、F（资源）、H（运行异常）。`investigation_progress=2/4` 说明 R1/R2 的**调查**部分成功，`evidence_chain_coverage=0` 说明**案卷纪律**失败——两者必须分开报告。

## 9. 标签

- `MEASUREMENT_VALID`：Oracle 25、公开启发式 24、消融可区分（4/4 vs 0/4），且 40 tick 内可完成。
- `INTERFACE_BLOCKED`（部分）：`entry_id` 词表、条目↔证据映射、“物证+证人成对完整”、`formal_accuse` 仅在 J，四项都只存在于实现/私有 spec。
- `METRIC_DEFECT`：`accusation_claim_precision` 统计未进入法庭的指控（R2 2/3）；`q4_recall_accuracy` 不要求 Q4 真的入卷（消融里出现 1）。
- 不标 `BUDGET_BLOCKED`：46 决策 vs 24 步可解；不标 `RULE_DEFECT`：规则自洽，fixture 覆盖 single-fault。

## 10. 最小可证伪修复（无证据不修改）

- **候选 A（首选，补公开信息）**：在 MAP-30 公开词表补三句——`record(entry_id)` 的合法值就是四个 `topic_id`；每个事件条目需要“现场记录 + 证人确认”两件证据；`formal_accuse` 只能在 J 提交。证据：14/19 次 `INVALID_CASEBOOK_ENTRY`、R2 决策 11 与 18、`entry_required == entry_allowed`。预期变化：`investigation_progress` 与 `evidence_chain_coverage` 的差距开始反映“记忆纪律”而不是“猜词能力”。
- **候选 B（补公开信息）**：明确“近期窗口只有 5 条事件，案卷是唯一跨窗口可引用的记忆”。证据：R2 决策 11 的 `EVIDENCE_NOT_AVAILABLE`。预期变化：模型会在拿到证人确认的当步记录，而不是攒着。
- **候选 C（指标修复，优先于 A/B 评审）**：`accusation_claim_precision` 只统计被接受的 `formal_accuse`（排除 `COURTROOM_REQUIRED` 等拒绝）；`q4_recall_accuracy` 要求 `Q4_CODEBOOK` 条目已记录且被引用，否则 N/A。证据：R2 2/3 来自被拒动作；消融 `q4=1, coverage=0`。预期变化：主指标不再高估“没进法庭的指控”。
- 反例与回归风险：候选 A 若把“成对完整”写得过细，会让 `compare_records` 退化为照抄；建议只写“需要现场记录与证人确认”，不写具体证据 ID。候选 C 会让 R2 的 precision 从 2/3 变成 N/A，需要同步更新 `docs/v8/maps/MAP-30-final.md` 的指标口径（V8 不改，V9 内说明差异）。
- 若不做修改：本图仍是 `MEASUREMENT_VALID`（24 步可复现），但“案卷/长期召回失败”与“调查失败”在当前 0/4 覆盖率里无法区分，必须靠 `investigation_progress` 辅助。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-30.json`：

| 基线 | 结果 | 决策 | 主指标 |
|---|---|---|---|
| Oracle `MAP-30-solver-success` | `scenario_success` | 25 | — |
| legal_random（20 seeds） | 0/20 成功（16 预算耗尽 + 4 指控超限） | 20–46 | — |
| public_heuristic | `ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN` | 24 | 覆盖 4/4、进度 4/4、CHAIN 1、Q4 1、precision 3/3 |
| ablation `no_casebook` | `ACCUSATION_LIMIT_EXCEEDED` | 12 | 覆盖 0/4、进度 0/4、CHAIN 0、Q4 1、precision 0/3 |

**独立复算**（不调用 `v7` extractor）：从 `public_heuristic.actions` 的最终 `casebook` 按 `worlds/v4/MAP-30/evidence_or_rules.yaml` 与 `entry_required`（`v7/metrics/references.py:111-119` 与 `map30.py:37-43` 同源）重算：

- 逐条目检查 `required ⊆ recorded`：`EVENT_1={B_KEY_STUB_2310, B_WITNESS_HANDOFF}`、`EVENT_2={K_WAX_PLATE_2322, K_WITNESS_WAX_ROUTE}`、`EVENT_3={T_CHAIN_REGISTER_2340, T_WITNESS_SIGNAL_ROUTE}`、`Q4={Q4_CODE_INDEX}` 全部满足 → 4/4，与 extractor 一致。
- 消融 `no_casebook`：4 个条目全空 → 0/4，与 extractor 一致。
- V8 三局：R0 `casebook=[]` → 0/4；R1 `{EVENT_2_WAX:[K_WAX_PLATE_2322], EVENT_3_SIGNAL:[T_CHAIN_REGISTER_2340]}` → 两条都缺证人确认 → 0/4；R2 同 R1 → 0/4。与 judge 的 0/4 ×3 一致。
- `q4_recall_accuracy` 独立口径（人名 == `MARA_VENN` 且 `Q4_CODEBOOK ∈ cited_entry_ids`）：R2 引用 `["EVENT_2_WAX","EVENT_3_SIGNAL"]` → 0；消融引用四个条目名（虽未记录）→ 1。后者暴露提取口径问题，不是复算错误。

区分度：`investigation_progress`、`legal_action_rate`、`evidence_chain_coverage` 三者组合能把启发式、消融、三局分开；`q4_recall_accuracy` 在“只抄条目名”时会给假阳性，`accusation_claim_precision` 会给未发生的指控打分，两者目前**低区分度且有偏**。

## 12. V9 状态

**`NEEDS_REDESIGN`，P1。** 理由：24 步公开策略可成功，说明构念成立；0/3 的首因是 `entry_id`/条目映射/成对完整/法庭节点四处未公开（14/19 次记录被拒，R2 还实测到一次窗口失效），再叠加两项指标偏置（未生效指控被打分、Q4 只看引用不看记录）。先修接口与指标，再判断“长间隔召回”是否真的缺失。
