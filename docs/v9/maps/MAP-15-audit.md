# MAP-15 逐图审计（会变化的迷宫）

## 0. 元数据

| 项 | 值 |
|---|---|
| 地图 / 世界 / 难度 | `MAP-15` / pyramid / 困难 |
| condition | `default` |
| `rule_hash` | `7d8322b90d7c67cf77d8cd39bc98bc8327c56097de34c5ffa35310fa3cf12e4f` |
| `scenario_hash` | `99b6ee5cd8aa556143afd35c095fc319d448a8c0c14864704246c005326c9e90` |
| `prompt_hash` | `54fa0fb08673fd5eb63b412fc0fabc2c68c317b577ee658dbf0db9e498da4efc` |
| `metric_schema_hash` | `5294368961d55a133851ae06f72438a2b6ea9cab0a233795436af1e9e8173f44` |
| 决策预算 | 46 |
| V8 三局 | 3/3 成功，`GATE_OPENED`，11 / 12 / 14 步 |

| rep | run_id | status | 决策 | `probes_to_target` | `invalid_transitions` | `loop_states` | `reset_losses` | `unseen_transition_accuracy` |
|---|---|---|---|---|---|---|---|---|
| 0 | `V8-MAP-15-R0-20261017T090948Z-551115e9` | success | 11 | 5 | 1 | 0 | 2 | 1/1 = 1.0 |
| 1 | `V8-MAP-15-R1-20261017T091043Z-8ae2681f` | success | 12 | 5 | 1 | 0 | 2 | 0/1 = 0.0 |
| 2 | `V8-MAP-15-R2-20261017T091131Z-9d9d9075` | success | 14 | 7 | 3 | 0 | 6 | 0/1 = 0.0 |

数据来源：`runs/v9/evidence/MAP-15.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-15-final.md`、`worlds/v4/MAP-15/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map15.py`、`runs/v9/baselines/MAP-15.json`。

> 溯源说明：MAP-15 R0 另有一条**未进入 90 行**的旧尝试 `V8-MAP-15-R0-20261017T085151Z-a8381a55`（只有 header、0 决策，`status=unknown_provider_spend`）。V9 只用 `551115e9`；旧尝试原样保留。
>
> 证据管线限制：`_compact_action` 的保留字段白名单不含 `area` 与 `slot_index`，证据包里所有 `inspect_symbols` 都被写成 `{"tool": "inspect_symbols"}`、所有 `choose_door` 都被写成 `{"tool": "choose_door"}`，看不出看了哪个区、选了几个号。本审计的动作引用取自原始 `agent_trace.jsonl`（例如 `{"area": "A", "tool": "inspect_symbols"}`、`{"slot_index": 1, "tool": "choose_door"}`），`delta` 取自证据包原文。

## 1. 能力构念

一句话：从 A/B/C 三个训练区的成功样例归纳"偶数 tick 目标色 = 墙色、奇数 tick = 墙色的互补色"，并把互补对迁移到 T 的四色未见布局。

- 成功行为：`GATE_OPENED`。理想轨迹是 A(t0 偶)→B(t1 奇)→C(t2 偶)→T(t3 奇) 四步全对，`invalid_transitions=0`、`reset_losses=0`、T 的首次选择即正确。
- 明确反例：
  - 只背训练区的槽位序列（1,2,2），到 T 直接套用会错；
  - 把"奇数 = 与墙色不同"当成规则（选了"第三种颜色"而不是互补色）——这正是三局里 5 次失误的共同形态；
  - 完全不观察门色就选。
- 同世界递进位置：pyramid 的**困难档**。它比 MAP-13（静态全真约束）多了"规则随全局相位变化"，比 MAP-14（不可靠证词）少了"信息本身不可信"。本图是三图里唯一要求"把学到的规则迁移到没见过的区域/颜色"的关卡。

## 2. 机制与因果链

本图专属因果链：

```
起始 A（tick 0，偶数，墙 red，门 [red, blue, gold]）
  → 必需观察：inspect_symbols(area=A)（0 tick）→ 公开当前墙色与门色顺序
  → 关键决策：按"偶数=墙色"选 slot 1（red）→ 通过，tick→1，进入 B
  → B（tick 1，奇数，墙 red，门 [green, blue, red]）→ 目标 = 互补(red)=blue → slot 2
  → C（tick 2，偶数，墙 gold，门 [blue, gold, green]）→ 目标 = gold → slot 2
  → T（tick 3，奇数，墙 gold，门 [gold, red, green, blue]）→ 目标 = 互补(gold)=green → slot 3
  → 终局：GATE_OPENED；错误则资源-1、tick+1、留在原区；T 区第 2 次错误 → TEST_WRONG_LIMIT
```

- 可以绕过核心机制的动作：
  - `inspect_symbols`、`record_rule`、`predict_transition` 全部 0 tick，且**都不是通关必需**：不 inspect 的 4 步固定序列、不建规则模型的 13 步"只选墙色 + 重试"都能通关（§5）。
  - 规则本身在 system prompt 里已直接写出（"本图机制：从 A/B/C 归纳'偶数同色、奇数互补'的规则，并在 T 通过四色门"），`goal` 字段又重复一次"从 A/B/C 归纳'偶数同色、奇数互补'的规则"。所谓"归纳"在公开面上已经被给出，只剩"互补对"要迁移。
- 机制在三局中的实际触发计数：

  | 事件 | R0 | R1 | R2 | 合计 |
  |---|---|---|---|---|
  | `choose_door`（每次按当前相位结算目标色） | 5 | 5 | 7 | 17 |
  | 首答与相位规则不符 | 1 | 1 | 3 | 5 |
  | 有效 `inspect_symbols` | 4 | 4 | 5 | 13 |
  | `INSPECTION_OUT_OF_SCOPE`（非当前区域） | 2 | 2 | 1 | 5 |
  | `INVALID_TRANSITION` | 1 | 1 | 3 | 5 |
  | `record_rule` | 0 | 1 | 1 | 2 |
  | `predict_transition`（显式预测） | 0 | 0 | 0 | 0 |

- 5 次规则误判**全部发生在奇数 tick**，且选中颜色都是"既不是墙色、也不是墙色互补色"的第三种颜色：R0 决策 6 在 B（墙 red，目标 blue）选 green；R1 决策 11 与 R2 决策 13 在 T（墙 gold，目标 green）选 blue；R2 决策 9 在 C（墙 gold，目标 green）选 blue；R2 决策 6 在 B 选 green。这说明模型掌握了"奇数 ≠ 墙色"，但没有掌握互补配对。
- 触发所需最小动作数：**4**（只需 4 次 `choose_door`，序列 1→2→2→3）；带观察的 Oracle 是 9；公开启发式 10。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| "偶数同色、奇数互补" | **是** | 开局 system prompt + `goal` | 部分（缺互补对定义） |
| `current_tick` / `current_tick_parity` | 是 | 每步 | 是 |
| `current_wall_symbol_color_if_inspected` | 是 | 当前区域 inspect 后 | 是（只当前区） |
| `current_door_colors_in_ephemeral_slot_order_if_inspected` | 是 | 当前区域 inspect 后 | 是（只当前区） |
| `training_sample_log`（含 `parity_before_choice`、`wall_color`、`chosen_door_color`） | 是 | 每次通过后 | 是（可学 red↔blue） |
| 互补对 `red↔blue / gold↔green` | **否（未公开）** | 需从样例 + 配对推断 | 可推断：red 已配 blue，剩下 gold/green 必互配 |
| `wrong_attempt_resources` / `test_wrong_attempts_remaining` | 是 | 每步 | 是 |
| 未来区域的墙色/门色 | 否 | 进入并 inspect 后才公开 | 需要迁移 |
| `WALLS` / `DOORS` 常量、`gate_open` 隐藏判据 | 否 | 永不 | — |
| Oracle 路径、指标 id | 否 | 永不 | — |

结论：规则主干已公开；未公开的只有"互补对"和未来区域布局。因此本图公开面**足以**推出解法（互补对可由"red 已与 blue 配对，四色必须两两配对"推出），也足以解释为什么三局都成功。

## 4. 可解性与可观察性

- Oracle：2 个用例（`explicit_rule_zero_error` 9 步、`implicit_one_test_error_recovery` 9 步），`oracle_ok=2/2`。
- 仅凭公开信息是否存在可执行策略：存在，`public_heuristic` 10 步 0 错通关。它从不硬编码墙色/门色：每区先 `inspect_symbols`，再用 `training_sample_log` 的奇数成功样例学互补对，最后用"剩下两色必互配"推出 gold→green，迁移到 T。
- 更强的事实：**不需要任何知识也能通过**（见 §5 三条旁路）。
- 不标 `INTERFACE_BLOCKED` / `BUDGET_BLOCKED`：9 步 Oracle vs 46 步预算，且规则在 prompt 里。

## 5. 预算可行性

| 对象 | 步数 | 结果 | 说明 |
|---|---|---|---|
| Oracle `explicit_rule_zero_error` | 9 | `GATE_OPENED` | 4 inspect + 1 record + 4 choose |
| Oracle `implicit_one_test_error_recovery` | 9 | `GATE_OPENED` | 在 T 错一次再纠正 |
| `public_heuristic` | 10 | `GATE_OPENED`，`acc=1.0`，`probes=4`，`invalid=0` | 多一次 `predict_transition` |
| 消融 `no_probe`（固定序列 1→2→2→3，零观察） | **4** | `GATE_OPENED`，`acc=1.0`，`probes=4`，`invalid=0` | 旁路证据 |
| 消融 `no_rule_transfer`（只选墙色 + 错后重试） | 13 | `GATE_OPENED`，`acc=0.0`，`probes=7`，`invalid=3` | 公开可推的旁路 |
| `legal_random` 20 seed | 13–46 | **5/20 成功** | 12 `RESOURCE_DEPLETED`、1 `TEST_WRONG_LIMIT`、2 预算耗尽 |
| MiMo R0/R1/R2 | 11/12/14 | 3/3 成功 | 见 §7 |

对应 fixture 的指标（`map15.FIXTURES`）：`zero_error_with_recorded_rule` 9 步 `acc=1.0`、`probes=4`、`invalid=0`、`losses=0`；`one_test_error_then_recalculate_parity` 7 步 `acc=0.0`、`probes=5`、`invalid=1`、`losses=2`。

判定：**预算远远够，成功率高到无法区分能力**。三条互不相同的策略都能通关，其中一条（`no_probe`）只花 4 步、完全不看 Observation。

随机基线细节（`runs/v9/baselines/MAP-15.json`）：`invalid_transitions` 1–4（中位 4）、`loop_states` 0–2（中位 0）、`reset_losses` 2–8（中位 8）、`probes_to_target` 5–7（仅 5 个成功局有值）、`unseen_transition_accuracy` 10 个有值且全是 0.0（另 10 局从未到 T → N/A）。一个"困难"图的形状合法随机基线能拿 25% 成功率，本身说明成功判据的区分度不足。

三局相对预算的余量：11/46、12/46、14/46，最多用掉 30%。

## 6. 指标

| 指标 | kind | 公式（登记） | 分母 | 三局取值 | 状态 |
|---|---|---|---|---|---|
| `map15.unseen_transition_accuracy` | primary | correct_unseen_predictions / evaluable_unseen_predictions | 可评估预测数 | 1.0 / 0.0 / 0.0 | valid |
| `map15.probes_to_target` | primary | count(probe actions before target) | episode | 5 / 5 / 7 | valid |
| `map15.invalid_transitions` | guardrail | count(INVALID_TRANSITION) | episode | 1 / 1 / 3 | valid |
| `map15.loop_states` | diagnostic | count(visited state re-entered) | episode | 0 / 0 / 0 | valid |
| `map15.reset_losses` | diagnostic | resource_units_lost + extra_ticks | episode | 2 / 2 / 6 | valid |

- 计算事件：`unseen_transition_accuracy` 的分子分母来自 `predictions`（显式预测优先，否则用 T 的首次 `choose_door` 当代理）；`probes_to_target` = `door_choices if success else None`。
- **未通关仍有意义的连续主指标**：`invalid_transitions` / `loop_states` / `reset_losses` 是连续量，但都是 lower_is_better 的负向计数；`unseen_transition_accuracy` 只有在进入 T 之后才有值。
- `not_applicable` / `censored`：三局都 `valid`，没有 N/A。但随机基线里 10/20 局 `unseen_transition_accuracy` 为 N/A（从未到 T），5/20 局 `probes_to_target` 为 None（失败局）——**失败局被系统性剔除出两个主指标**。
- 缺陷：
  1. **主指标不能区分"迁移"与"固定路径"**。`no_probe`（零观察、4 步）与 `public_heuristic`（学互补对、10 步）给出**完全相同**的 `acc=1.0, probes=4, invalid=0, losses=0`。
  2. **代理口径把"第一次猜中"当成"预测正确"**。整局没有显式 `predict_transition` 时，T 的首次选择即分数；三局只有 R0 在 T 一次命中（1.0），R1/R2 首次选错（0.0）。这既不是"规则是否被理解"的充分条件，也不是必要条件（`no_probe` 也拿 1.0）。
  3. **失败局无主指标**。`probes_to_target` 在失败局返回 `None`（N/A，登记规则如此），`unseen_transition_accuracy` 在未到 T 时分母为 0。随机基线的 15 个失败局里 10 个在两个主指标上都没有值 → 生存偏差。
  4. **`reset_losses` 是派生量**：等于 `2 × invalid_transitions`，没有独立信息。
- 区分能力：能区分"规则盲"与"规则用"（`no_rule_transfer` 的 `acc=0.0 / probes=7 / invalid=3`），但**不能区分"规则用"与"固定路径旁路"**。属部分 `LOW_DISCRIMINATION`。

## 7. 三次轨迹归因

### R0（`...-551115e9`，11 步，成功）

- 决策 1：`{"area": "A", "tool": "inspect_symbols"}` → `CURRENT_WALL_AND_DOORS_VISIBLE`，`{"current_door_colors_in_ephemeral_slot_order_if_inspected": ["red", "blue", "gold"], "current_wall_symbol_color_if_inspected": "red", "inspected_current_area": true}`。
- 决策 2：`{"area": "B", "tool": "inspect_symbols"}` → `INSPECTION_OUT_OF_SCOPE`，`{}`（人在 A，不能提前看 B）。
- 决策 4：`{"slot_index": 1, "tool": "choose_door"}` → `PASSED_FORWARD_TO_B`，`{"area": "B", "current_tick": 1, "current_tick_parity": "odd", ...}`（tick 0 偶数，墙 red → 选 red 命中）。
- 决策 6：`{"slot_index": 1, "tool": "choose_door"}` → `INVALID_TRANSITION`，`{"current_tick": 2, "current_tick_parity": "even", "wrong_attempt_resources": 3}`（B 在 tick 1 奇数，目标 blue，却选了 green）。
- 决策 7：`{"slot_index": 3, "tool": "choose_door"}` → `PASSED_FORWARD_TO_C`（tick 2 偶数，目标 red，slot 3 = red）。
- 决策 9：`{"slot_index": 3, "tool": "choose_door"}` → `PASSED_FORWARD_TO_T`（tick 3 奇数，C 墙 gold，目标 green，slot 3 = green）。
- 决策 11：`{"slot_index": 1, "tool": "choose_door"}` → `GATE_OPENED`，`{"area": "EXIT", "current_tick": 5, "gate_open": true, "terminal": true, "terminal_reason": "GATE_OPENED"}`（tick 4 偶数，T 墙 gold，目标 gold，slot 1）。

首因/首次偏离：决策 6。奇数相位下它选了"第三种颜色"green，而不是互补色 blue——这是本图 5 次规则误判的统一形态。但决策 7 立刻纠正：错误让 tick 从 1 翻到 2（偶数），同区按墙色 red 直接命中。**错误被相位翻转自动修复**。

### R1（`...-8ae2681f`，12 步，成功）

- 决策 6：`{"slot_index": 2, "tool": "choose_door"}` → `PASSED_FORWARD_TO_C`（B 在 tick 1 奇数，墙 red，目标 blue，slot 2 = blue；这一手用对了互补）。
- 决策 9：`{"rule_id": "even_same_odd_complement", "supporting_sample_ids": ["SAMPLE_A_T0_ATTEMPT1", "SAMPLE_B_T1_ATTEMPT1", "SAMPLE_C_T2_ATTEMPT1"], "tool": "record_rule"}` → `RULE_RECORDED_WITHOUT_CORRECTNESS_FEEDBACK`。
- 决策 11：`{"slot_index": 4, "tool": "choose_door"}` → `INVALID_TRANSITION`，`{"current_tick": 4, "current_tick_parity": "even", "test_wrong_attempts": 1, "test_wrong_attempts_remaining": 1, "wrong_attempt_resources": 3}`（T 在 tick 3 奇数，目标 green，却选了 blue）。
- 决策 12：`{"slot_index": 1, "tool": "choose_door"}` → `GATE_OPENED`（tick 4 偶数，目标 gold，slot 1）。

首因/首次偏离：决策 11。它在决策 9 刚刚**记录**了正确规则、并在 B 用它答对一次，随后在 T 又退回"第三种颜色"的启发式。这是"规则被写出但没被用于未见状态"的直接证据。`unseen_transition_accuracy=0/1` 正是这次首选的记录。

### R2（`...-9d9d9075`，14 步，成功）

- 决策 6：`{"slot_index": 1, "tool": "choose_door"}` → `INVALID_TRANSITION`，`{"current_tick": 2, "current_tick_parity": "even", "wrong_attempt_resources": 3}`（B 奇数选 green）。
- 决策 9：`{"slot_index": 1, "tool": "choose_door"}` → `INVALID_TRANSITION`，`{"current_tick": 4, "current_tick_parity": "even", "wrong_attempt_resources": 2}`（C 奇数选 blue）。
- 决策 13：`{"slot_index": 4, "tool": "choose_door"}` → `INVALID_TRANSITION`，`{"current_tick": 6, "current_tick_parity": "even", "test_wrong_attempts": 1, "test_wrong_attempts_remaining": 1, "wrong_attempt_resources": 1}`（T 奇数选 blue）。
- 决策 14：`{"slot_index": 1, "tool": "choose_door"}` → `GATE_OPENED`（tick 6 偶数，目标 gold）。

首因/首次偏离：决策 6，与 R0 同型。三次误判后资源只剩 1、T 区容错剩 1；仍然靠"错误→相位翻转→同区按墙色命中"的循环通关。

三局共性：**5 次首答误判全部在奇数相位、全部选"第三种颜色"**；每次误判后的下一步都在偶数相位命中。三局的 `loop_states` 都是 0，因为每个 `(area, parity)` 只错一次。

重复证据的限度：三局都在同一机制上犯同类错误，n=3 只能说明这是系统性偏差（互补配对没学会），不能区分个体差异；而 3/3 的成功也不能当作"迁移能力"的证据，因为它同时可由"错误自动纠正"解释。

## 8. 失败分类

本图三局都是成功，因此下表记录**过程性错误**而非终局失败：

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **G 推理错误**（奇数相位用"第三种颜色"代替互补色） | A 规则缺陷（相位翻转使该错误零成本自愈） | 高 | 决策 6→7 |
| R1 | **G**（记录正确规则后在 T 又用错） | A（同上） | 高 | 决策 9、11→12 |
| R2 | **G**（3 次同型误判） | A（同上） | 高 | 决策 6、9、13 |

**A（环境规则缺陷）的证据**：错误选择只把 tick 推进 1，目标色因此从"墙色"翻到"互补色"或反之；而墙色本身永远属于 `{墙色, 互补色}` 这个二元素集合。所以任何"选墙色"的策略，错一次后**在同一区域再选同一槽位必然命中**。`no_rule_transfer`（13 步、3 次 `INVALID_TRANSITION`、`reset_losses=6`、资源剩 1）就是这条性质的直接实证；随机基线 5/20 成功也来自同一性质。

不采用 D（预算）：11/46 步，最多用掉 30%。

## 9. 标签

- `CONSTRUCT_BYPASS`（主标签）：
  - 固定路径 1→2→2→3 在 **4 步**内通关、零观察、零预测（`ablations.no_probe`）；
  - "只选墙色 + 错后重试"在 13 步内通关（`ablations.no_rule_transfer`），这条策略**完全公开可推**，不需要互补对也不需要相位模型；
  - 形状合法随机基线 5/20（25%）成功。
  三条证据共同说明：成功判据不要求"更新世界模型"，本图的核心构念（规则迁移）不是通关的必要条件。
- `RULE_DEFECT`：错误选择推进 1 tick，使相位翻转、目标色切换，导致"错后重选同槽"必然命中；容错额度（4 资源、T 区 2 次）足以覆盖 A/B/C/T 各错一次。这是规则层面的自愈机制，不是接口问题。
- `METRIC_DEFECT`：`unseen_transition_accuracy` 用 T 首次选择作代理，使固定路径与真迁移同分；`probes_to_target` 在失败局为 None、`unseen_transition_accuracy` 在未到 T 时分母为 0，失败局被剔除出两个主指标。
- 不选 `MEASUREMENT_VALID`：成功判定本身正确（与 `GATE_OPENED` 一致），但构念不可测。
- 不选 `BUDGET_BLOCKED` / `INTERFACE_BLOCKED`。

## 10. 最小可证伪修复（无证据不修改）

**旧规则**：`choose_door` 正确则前进、错误则资源-1 且 tick+1；目标色 = 偶数墙色 / 奇数补色；T 区第 2 次错误失败。

**证据与根因**：相位随每次选门翻转，使"错误"与"下一次正确"绑定；`no_rule_transfer` 与随机基线都能通关，说明规则迁移不是必需。

- 候选 A（**规则改动，P0，需 DCR**）：错误选择后 tick 前进 **2**（或错误不推进 tick）。预期：同一槽位在错误后不再自动变正确，`no_rule_transfer` 与随机基线成功率显著下降，必须真正算出互补色。反例/风险：改 `rule_hash`，V8 Trace 不可回放，Oracle/fixtures/三图基线都要重跑；`implicit_one_test_error_recovery` 这个"错一次再算相位"的用例会失效，需要重写。
- 候选 B（**规则改动，P1，需 DCR**）：把 T 的容错改为"连续两次正确"或把颜色从 4 扩到 6（互补对变成 3 对）。预期：降低盲通与半懂通关的概率。风险同上，且会拉高难度，需重新标定"困难"档。
- 候选 C（**指标口径，P1**）：`unseen_transition_accuracy` 改为在 T 的**两个相位各评估一次**（显式 `predict_transition` 才计分，代理只作 diagnostic）；对未到 T 的局记 `censored` 而不是 N/A；`probes_to_target` 保留登记口径但在汇总层单列成功局。预期：固定路径不再拿满分的 `acc`。风险：需要重算 V8 的 90 局投影。
- 候选 D（**减少提示**，P1）：把 system prompt 第一段的"偶数同色、奇数互补"改成只写"规则随 tick 奇偶切换，需要从训练样例归纳"，`goal` 同步。预期：恢复"归纳"构念，不改变规则本身。风险：prompt hash 变更，需要新 arm 对照；可能让成功率下降（这正是想要的）。
- 优先级：A（P0）> D（P1）> C（P1）> B（P2）。**不建议加预算**——本图问题恰好相反：太容易。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-15.json`：

| 基线 | 成功 | 步数 | `acc` | `probes` | `invalid` | `losses` |
|---|---|---|---|---|---|---|
| Oracle ×2（动作数来自 `replay_all`） | 2/2 | 9 / 9 | — | — | — | — |
| 对应 fixture `zero_error_with_recorded_rule` | — | 9 | 1.0 | 4 | 0 | 0 |
| 对应 fixture `one_test_error_then_recalculate_parity` | — | 7 | 0.0 | 5 | 1 | 2 |
| `legal_random` ×20 | 5/20 | 13–46 | 0.0（10 个有值） | 5–7（5 个有值） | 1–4（中位 4） | 2–8（中位 8） |
| `public_heuristic` | 1/1 | 10 | 1.0 | 4 | 0 | 0 |
| `no_probe` | 1/1 | 4 | 1.0 | 4 | 0 | 0 |
| `no_rule_transfer` | 1/1 | 13 | 0.0 | 7 | 3 | 6 |

独立复算（从原始 Trace 手数，不调用 `map15.metrics()`）：

- `probes_to_target` = `choose_door` 次数：R0 决策 4/6/7/9/11 = 5；R1 决策 3/6/8/11/12 = 5；R2 决策 4/6/7/9/10/13/14 = 7。与报告值 5/5/7 一致。
- `unseen_transition_accuracy` 手算：
  - R0：T 首次选择在 tick 4（偶数），墙 gold → 目标 gold，选 slot 1（gold）→ 1/1。
  - R1：T 首次选择在 tick 3（奇数），墙 gold → 目标 green，选 slot 4（blue）→ 0/1。
  - R2：T 首次选择在 tick 5（奇数），墙 gold → 目标 green，选 slot 4（blue）→ 0/1。
  与报告值 1.0 / 0.0 / 0.0 一致。
- `reset_losses` = `2 × invalid_transitions`：2/2/6 ✓（R0 2×1、R1 2×1、R2 2×3）。
- 最短路径复算：从 tick 0 起，A(偶,red)→slot1、B(奇,red→blue)→slot2、C(偶,gold)→slot2、T(奇,gold→green)→slot3。实测 `no_probe` 4 步通关。
- 规则盲路径复算：每区选"墙色槽位"，奇数相位必错、下一步偶数相位必中；A 不错（tick 0 偶数），B/C/T 各错一次 → 3 次非法、资源 4-3=1、T 区 test_errors=1 < 2 → 13 步通关。实测一致。
- 判别力：`LOW_DISCRIMINATION`（`no_probe` 与 `public_heuristic` 的 5 条指标完全相同；`no_rule_transfer` 只在 `acc/probes/invalid` 上被区分）。

## 12. V9 状态

`NEEDS_REDESIGN`，优先级 **P0**。

一句话理由：4 步固定路径（零观察）与 13 步规则盲策略（公开可推）都能通关，随机基线也有 25% 成功率——"规则迁移"不是通关必要条件，且现有主指标无法把固定路径与真迁移分开。
