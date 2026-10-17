# MAP-30｜古堡｜困难｜30 午夜审判

```yaml
map_id: MAP-30
world: castle
nominal_level: 困难
capability_primary: long_gap_evidence_recall
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 3913ca2f2898cb3278ac413bc574ae08454dfe2c379085cefc40ad90fbc58388
source_design_hash: 9fa618228569778e1bb06006377baa8c2b517e8f0919a18a9be5e5a74a20d11b
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: runtime
metric_status: implemented_offline_validated
```

## 1. 测量构念与不可替代玩法

测“长间隔后的证据召回与审慎指控”。三件事件（23:10 钥匙交接 / 23:22 封蜡加热 / 23:40 铃链信号）的物证都只写暗码 `M-4`；早期档案 `Q4_CODE_INDEX` 才能把它解回玛拉·维恩。Observation 只保留**最近 5 条动作**，案卷只有 4 格且只能追加；NPC 必须先看到上游完整条目才解锁下一段记忆。第 40 tick 是午夜听证关闭点。核心不是“搜完”，而是**把早期 Q4 在离开近期窗口前写进案卷，并在庭审时仍能正确引用**。

## 2. 真实规则字段

- 结构：一层 `H—B—K—Y`、二层 `L—A—T`、`K—T` 单 tick 密道、`H—J` 入口、`H—L` 楼梯。
- 四段链：`Q4_CODEBOOK`（封套→档案员→`Q4_CODE_INDEX`：M-4 = 玛拉·维恩）；`EVENT_1_HANDOFF`（`B_KEY_STUB_2310` + `B_WITNESS_HANDOFF`）；`EVENT_2_WAX`（`K_WAX_PLATE_2322` + `K_WITNESS_WAX_ROUTE`）；`EVENT_3_SIGNAL`（`T_CHAIN_REGISTER_2340` + `T_WITNESS_SIGNAL_ROUTE`）。
- 依赖：厨师必须先看到完整的 `EVENT_1_HANDOFF` 才回忆细节；守塔人必须先看到 `EVENT_2_WAX`。相同 NPC/问题/证据状态总返回相同 answer ID 与文本。
- 动作各耗 1 tick；近期窗口 5 条；案卷 4 格、只追加；每件事件条目必须先物证、后条件证词；Q4 需在离开近期窗口前记入。
- `compare_records`：只比对已记录条目，确认四格齐备、每事件双来源、M-4 可由 Q4 解码、时间严格递增。
- 庭审：必须在 J；正式指控的人、三事件时间/地点/暗码与四条目都正确；**至多一次**未获支持递交（`ACCUSATION_NOT_SUSTAINED`），第二次 `ACCUSATION_LIMIT_EXCEEDED` 终局失败。
- 时限：第 40 tick 完成的正确指控先于超时结算；第 40 tick 结束仍未解决 → `DEADLINE_REACHED`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map30.q4_recall_accuracy` | primary | `1[person==culprit 且 formal_accuse 引用 code_entry]` | 0/1 / 高 | 提交过指控 | 无指控 → N/A；截尾 → CENSORED；无案情 → UNAVAILABLE |
| `map30.evidence_chain_coverage` | primary | 必需证据齐全的条目数 / 条目总数（3 或 4） | 比例 / 高 | 案卷条目数 | casebook 缺失 → UNAVAILABLE |
| `map30.accusation_claim_precision` | primary | `max(0, matched − extra) / 应提交事件数` | 比例 / 高 | 冻结应提交数 | 无指控 → N/A/CENSORED |
| `map30.chain_reconciled` | diagnostic | `1[任一 compare_records 返回 CHAIN_COHERENT]` | 0/1 / 高 | episode | 无比对 → 0（合法） |
| `map30.investigation_progress` | diagnostic | 已记录条目数 / 条目总数 | 比例 / 高 | 条目总数 | casebook 缺失 → UNAVAILABLE |
| `map30.unsupported_accusations` | guardrail | 终局未获支持指控数 | 次 / 低 | episode | 字段缺失 → UNAVAILABLE |
| `map30.legal_action_rate` | diagnostic | 接受决策 / 提交决策 | 比例 / 高 | 决策数；0 → N/A | — |

实现：`src/agent_arena/v7/metrics/map30.py`，共 7 条 `implemented=True`。`evidence_chain_coverage` 与 `investigation_progress` 必须分报：前者要“必需证据齐全”，后者只数“有没有记这个条目”。

## 4. 能力混淆分析

- 高 `investigation_progress` 可能靠“把四格随便填满”：覆盖率仍可能是 0/4；必须并列。
- 高 `q4_recall_accuracy` 在**纯召回变体**上只测“一步提交”，不测调查流程；完整调查与召回变体必须分开报告（V6 已如此）。
- `chain_reconciled=1` 只说明对齐成功，不说明指控正确；必须与事实精确率并列。
- `accusation_claim_precision` 用“匹配 − 多余”惩罚乱塞事件；少提交也不会自动满分（分母固定为应提交数）。
- `unsupported_accusations=1` 仍可能最终成功（B01 一次失手可恢复）；0 也不代表审慎，可能只是没提交。

## 5. 两条手算轨迹

**A. 分事件归档（25 tick）**：`H→L→A` 保存 Q4；依次在 B、K、T 完成事件 1/2/3 的现场物证与条件证词；`compare_records` 确认四格齐备、双来源、M-4 可解码、时间递增；到 `J` 正式指控。指标：`q4_recall_accuracy=1`；`evidence_chain_coverage=4/4=1.0`；`accusation_claim_precision=3/3=1.0`；`chain_reconciled=1`；`investigation_progress=4/4=1.0`；`unsupported=0`。

**B. 人物线索/物证先行（32 tick）**：先保存 Q4；由 K、T 各自先登记本地物证，再去 B 完成钥匙交接；回 K 出示事件 1、回 T 出示事件 2 逐个访谈补齐案卷；比对后到 J 指控。指标：四项主指标同 A（1 / 1.0 / 1.0 / 1）；`chain_reconciled=1`；`unsupported=0`。轨迹更长但同样完整，证明“先物证后访谈”不破坏依赖链。

> 第三条“先构建时间线”（34 tick）先写低置信假设、完成 B/K 后各更新一次、最后补 T；假设没有真伪反馈，必须自己用证据纠正。三条轨迹是独立手写，不是同一模板换序。

## 6. 三个机制特有失败

1. **F01 连续猜人**：未访谈未归档就到 J 指控 Orin、再指控 Pell；两次未获支持，第二次触发 `ACCUSATION_LIMIT_EXCEEDED`。覆盖 0/4、进度 0/4、`unsupported=2`。
2. **F02 忘记早期 Q4**：完整收集三件事件的物证与证词却不保存 Q4；M-4 无法解码，连续两次用 Mara 提交无完整来源的指控 → 失败。覆盖 3/4、进度 3/4、`q4_recall=0`。
3. **F03 调换时间顺序**：收齐并正确比对案卷，却在提交时把厨房 23:22 与塔楼 23:40 交换；通用拒绝后仍重复错误陈述，第二次未获支持递交。`chain_reconciled=1`、覆盖 4/4，但事实精确率降到 **0.0**（匹配 1 项、额外 2 项，按 `max(0, 1−2)/3` 计）。

## 7. 两个边界

- **一次失手可恢复（B01）**：完整证据链下先错告一次、再正确指控，恰好一次失败递交仍成功；第二次才终局失败。`unsupported_accusations` 的阈值是 **2**，不是 1。
- **第 40 tick 端点（B03）**：第 39 tick 开始正确指控、第 40 tick 结束 → 成功；同一时刻执行未解决行动 → `DEADLINE_REACHED`。另 B02 验证 Q4 跨近期窗口后 Observation 不再重列、但案卷仍可引用。

## 8. 信息泄漏负例

若 Observation/prompt 直接给真凶、`Q4_CODE_INDEX` 内容、三事件时间表或“该指控谁”，长间隔召回被替代。V7 只允许公开已搜索记录、已触发 NPC 回答、最近 5 条动作、案卷、假设与庭审接口；裁判真相、未来事件、未触发对话只在 `judge_state`/`planning`。`ACCUSATION_NOT_SUSTAINED` 不得指出哪一项错。

## 9. Oracle/求解状态

`oracle_trace.jsonl`（26 行，SHA-256 `D35E73E4…3DDBE4`）有三条独立手写成功（25/32/34 tick）与三条失败（3/19/26 tick 终止）；`planning/private_seed_reference.yaml` 固定 seed0 案情；离线审计断言单次错告恢复、Q4 跨窗口保留、条件证词固定与第 40 tick 胜负顺序。V6 真实 API 6 局：**完整调查 0/3**（0 案卷条目）、**纯召回 1/3**（`history5_casebook` 一步成功、Q4 召回 True、事实 3/3）。**单次证据，不能外推。**

## 10. 与同世界另两图差异

**vs MAP-28**：MAP-28 是单案短链、四字段双来源，核心是来源独立性；MAP-30 有长间隔、多事件、条件访谈与正式庭审，核心是**召回与顺序**。MAP-28 没有“最近 5 条”窗口，也没有指控额度。

**vs MAP-29**：MAP-29 是固定证人的可靠性分诊（8 问预算）；MAP-30 的 NPC 不改口，只有“出示上游证据才解锁”，核心不是判断谁说谎，而是**记住早期事实**。MAP-29 的指标是矛盾检测，MAP-30 是 Q4 召回与证据链覆盖。

## 11. 可计算性来源

需要的公开字段：`current_tick, current_node, local_neighbors, visible_local_evidence, recent_action_window, casebook, current_hypothesis, unsupported_formal_accusations, terminal_reason`，以及 `formal_accuse` 的 `person_id / cited_entry_ids / event_claims` 与 `compare_records` 结果。覆盖率按冻结 `entry_required` 子集判定；精确率按冻结三事件事实；召回率要求 `person==culprit` 且引用 `code_entry`。真凶与必需证据集合只在离线侧（`references.MAP30_CASES`）。

## 12. 难度定位与对照

D=(2,3,1,1,3,3)。相对 MAP-29 提升 **D↑（三事件 + Q4 的四段依赖）与 M↑（长间隔、跨近期窗口召回）**；E 保持 1（事件固定，无随机）。不会与 MAP-29 混淆：MAP-29 无长间隔案卷，MAP-30 无问询预算与说谎者。

预登记对照：**完整历史 vs 最近 5 条 vs 4 格结构化案卷**（V6 三条件），共享同一起点、动作与上下文预算。另设 **纯召回变体**（固定调查前缀 + 一步提交），它只测召回，不测调查流程，必须与完整调查分开报告。

## 13. 未决

- V6 完整调查 0/3 均“0 案卷条目”，属流程地板而非记忆地板；纯召回 1/3 才是记忆信号。当前样本不足以判断能力。
- `accusation_claim_precision` 的 `extra` 惩罚对“多提交一个不同事件”很重（可能直接归零）；是否需要按事件对齐而非计数，待人工决定（`V7-DCR` 候选）。
- `unsupported_accusations` 的终局字段若在第二次失败时未写入，会漏报；需运行时确认终局快照包含该计数。
- V6 三条件（`history_full / history5 / casebook`）均为单次、每条件 1 局；所有实例 `pending_human_review`。
