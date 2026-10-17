# MAP-13 逐图审计（四神之门）

## 0. 元数据

| 项 | 值 |
|---|---|
| 地图 / 世界 / 难度 | `MAP-13` / pyramid / 简单 |
| condition | `default` |
| `rule_hash` | `0481b734b73d7d3786a7fb2c68bcdb1cb5e4d309e517f5135a52a359db519229` |
| `scenario_hash` | `93e7b639bd2fe8a3129a1f7cae4724eb47ea9af7a72abb6958a4d910f44a2cdd` |
| `prompt_hash` | `198e1a24658d16472d1b83c7493741a96e24272c90e83ef214e285fb0f53970e` |
| `metric_schema_hash` | `6c7e42f604f3f1b674efe3307b331d079744f9422d5932d205c5a4f3764a83a4` |
| 决策预算 | 30（`LEVEL_OF["MAP-13"]="简单"`，`baseline_run.BUDGETS`） |
| V8 三局 | R0 `decision_budget_reached` 30 步；R1 `success` 27 步 `GATE_OPENED`；R2 `success` 19 步 `GATE_OPENED` |

| rep | run_id | status | 决策 | `constraint_satisfaction_ratio` | `correct_sequence` | `illegal_door_attempts` | `state_resets` | `completion_ticks` |
|---|---|---|---|---|---|---|---|---|
| 0 | `V8-MAP-13-R0-20261017T083403Z-a0b524e9` | decision_budget_reached | 30 | 1/5 = 0.2 | 0 | 3 | 2 | None → V9 `censored` |
| 1 | `V8-MAP-13-R1-20261017T083612Z-3c577add` | success | 27 | 4/5 = 0.8 | 1 | 0 | 0 | 27 |
| 2 | `V8-MAP-13-R2-20261017T084003Z-2a5b828c` | success | 19 | 4/5 = 0.8 | 1 | 0 | 0 | 19 |

> 溯源说明：MAP-13 R2 另有一条**未进入 90 行**的旧尝试 `V8-MAP-13-R2-20261017T083750Z-787ade08`（`runs/v8/experiments/episodes/`，`status=unknown_provider_spend`，16 决策，`failed_requests=1`，`environment_status=running`）。它既不终止也不计分，V9 只用上表的 `2a5b828c`；旧尝试原样保留，未覆盖。

数据来源：`runs/v9/evidence/MAP-13.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-13-final.md`、`worlds/v4/MAP-13/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map13.py`、`runs/v9/baselines/MAP-13.json`。

> 证据管线限制（影响本图引用方式）：`src/agent_arena/v9/evidence.py::_compact_action` 的保留字段白名单不含 `room`，所以证据包里的 `read_inscription` 动作被写成 `{"tool": "read_inscription"}`。本审计引用动作时以 `runs/v8/*/experiments/episodes/<run_id>/agent_trace.jsonl` 的原始行 为准（已逐条核对），引用 `delta` 时以证据包为准。这是 **V9 证据层的缺陷**，不是 V8 场景行为（见 §10 候选 D）。

## 1. 能力构念

一句话：在固定的星形移动图上，把"四条槽位谓词 + 一条阅读序钉"传播成一个唯一排列，并在两次非致命试排内验证成功。

- 成功行为：`GATE_OPENED`，且最后一次被验证的排列等于唯一解（`correct_sequence=1`）；理想情况下读满 5 条信息再试排（`ratio=1.0`、`state_resets=0`）。
- 明确反例：
  - 未读满约束就枚举猜排（R0：读了 4 条但缺方向钉，两次错排后容错只剩 1 次）；
  - 把"移动邻接"当成"碑文阅读序"（本图的核心区分点）；
  - 反复 `verify_layout` 而无完整试排（R0 决策 22）。
- 同世界递进位置：本图是 pyramid 的**简单档**，也是三图里唯一的"全真、静态、无不可靠信息"关卡。中等档 MAP-14 换成不可靠证词，困难档 MAP-15 换成随相位变化的规则。因此本图承担的是同世界的 **CSP 下限**：如果模型连静态全真约束都做不出来，后续两图的失败不能归因于"说谎/规则变化"。

## 2. 机制与因果链

因果链（本图专属）：

```
起始 C（tick 0，无任何 clue）
  → 必需观察①：read_inscription(room=C) → ORIENTATION_ORDER（N→E→S→W 读作槽位 1–4）
  → 必需观察②：分别移动到 N/E/S/W 并 read_inscription → 四条槽位谓词
  → 关键决策：把四条谓词传播成唯一排列（24 种排列中恰 1 种满足）
  → set_trial_layout（不消耗容错，可反复覆盖）
  → verify_layout：等于唯一解 → GATE_OPENED；不等 → STATE_RESET + incorrect_attempts+1
  → 终局：GATE_OPENED / INCORRECT_ATTEMPT_LIMIT（第 3 次错排）
```

- 可以绕过核心机制的动作：
  - `record_constraint` 不被任何指标引用（`map13.metrics()` 只用 `observed` 与布局），所以"记录"这一步对成功与得分完全无影响。实测：跳过全部 `record_constraint` 的 15 步路线仍得 `ratio=5/5`、`GATE_OPENED`（§5）。
  - `set_trial_layout` 不消耗容错，只在 `verify_layout` 时计错，因此"试排次数"本身不构成机制，"验证次数"才构成。
  - 方向钉对**成功**不是必需的：四条房间谓词在默认阅读序 N→E→S→W 下已唯一确定排列（§4），不读方向钉也能开门，只是 `ratio` 上限变成 0.8。
- 机制在三条轨迹中的实际触发：
  - 方向钉（ORIENTATION_ORDER）：**0/3 触发**。三局都没有在 C 执行过成功的 `read_inscription`；R0 决策 1–2、R1 决策 1–2、R2 决策 1–2 都是 `{"room": "N"}` 在 C 读取 → `INVALID_LOCATION`。
  - 四条房间谓词：R0 读全 4/4（决策 4、9、14、26），R1 读全 4/4（决策 4、9、14、22），R2 只读 3/4（决策 4、9、14，缺 W）。
  - 错排机制：仅 R0 触发 2 次（决策 19、21）；R1/R2 从未错排。
- 触发所需最小动作数：1（读 C）+ 4×3（四室 move+read+move）= 13，加 `set_trial_layout` 与 `verify_layout` = **15 步**；加上 5 次记录 = 20 步（Oracle 与 `public_heuristic` 的长度）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `location` / `visible_edges` / `visible_neighbors` | 是 | 每步 | 是（决定能去哪） |
| `observed_clues[{clue_id,text}]` | 是 | 成功 `read_inscription` 后 | 是（文本即谓词） |
| `recorded_clue_ids` | 是 | `record_constraint` 后 | 否（无指标引用） |
| `trial_layout` | 是 | `set_trial_layout` 后 | 是（可自查） |
| `incorrect_attempts` / `remaining_incorrect_attempts` | 是 | 每步 | 部分（见 §6 歧义） |
| system prompt 的动作词表与契约 | 是 | 开局 | 是（形状层面） |
| "read 只能读所在房间、record 只能在 C" | **否（未公开）** | 只能从 `INVALID_LOCATION` 反推 | 是（试错可发现） |
| 五条碑文的**文本** | 隐藏→公开 | 读到才公开 | 是 |
| `TARGET_LAYOUT`（唯一解） | 否 | 永不 | 不需要（可推导） |
| `MAX_INCORRECT_ATTEMPTS=3` 的实际容错 | 部分 | 只能从结果码反推 | 部分 |
| Oracle 路径 / 指标 id | 否 | 永不 | — |

结论：公开面足以解题（四条文本谓词 + 默认阅读序），但"动作的位置前置条件"只写在 `worlds/v4/MAP-13/map_spec.yaml`（`record_constraint.location: C`、`read_inscription.requires: current_location_equals_room`），**system prompt 没有公开**。这是 R0/R1 各浪费 5 次决策的直接原因。

## 4. 可解性与可观察性

- Oracle：2 个用例（`constraint_propagation` 20 步、`systematic_enumeration` 20 步），`runs/v9/baselines/MAP-13.json` 中 `oracle_ok=2/2`。
- 仅凭公开信息的可执行策略：存在。`public_heuristic`（`src/agent_arena/v9/policies/world_pyramid.py::Map13Heuristic`）只做三件事——读 C、读四室、对 24 种排列做谓词暴力枚举——20 步拿到 `ratio=5/5`、`correct_sequence=1`、`GATE_OPENED`。
- 唯一性核验（独立实现，非读环境常量）：对 `日/眼/芦/甲` 的 24 种全排列按四条谓词过滤，**只有 1 个解**：

  | 槽位 | N | E | S | W |
  |---|---|---|---|---|
  | 符号 | 甲 | 日 | 芦 | 眼 |

  符合 `pos(日)∈{2,3}`、`pos(眼)>pos(芦)`、`|pos(甲)-pos(日)|=1`、`pos(芦)≠1`。任意 3 条谓词都不唯一（3 条组合分别剩 4/2/5/2 个解），所以**四条都必须读**。
- 方向钉的角色：它不改变解，只证明"槽位 1 = N、顺时针"这个映射。不读它而假设默认顺序仍能开门（`no_direction_nail` 18 步成功），但 `ratio` 上限 0.8。
- 不标 `INTERFACE_BLOCKED`：位置前置条件可试错发现，且三局都实际拿到过正确结果码（`recorded:*`、`trial_layout_set`）。也不标 `BUDGET_BLOCKED`：20 步 < 30 步。

## 5. 预算可行性

| 对象 | 步数 | 结果 |
|---|---|---|
| Oracle `constraint_propagation` | 20 | `GATE_OPENED` |
| Oracle `systematic_enumeration` | 20 | `GATE_OPENED` |
| `public_heuristic` | 20 | `GATE_OPENED`，`ratio=1.0` |
| 消融 `no_direction_nail` | 18 | `GATE_OPENED`，`ratio=0.8` |
| 手工"只读不记"路线（本地验证，未入库） | 15 | `GATE_OPENED`，`ratio=1.0` |
| `legal_random` 20 seed | 全部 30 | 0/20 成功，全 `decision_budget_reached` |
| MiMo R0 / R1 / R2 | 30 / 27 / 19 | 0 / 1 / 1 成功 |

`legal_random` 分布（`runs/v9/baselines/MAP-13.json`）：20 seed 全部耗尽 30 步；`invalid_actions=0`（形状由 `SHAPES` 采样保证），`rejected_actions=365`（语义非法）；`ratio` 20/20 都是 0.0；`illegal_door_attempts` 2–10，中位 5.5；`state_resets` 20/20 为 0——随机策略从不生成完整 `layout_by_room`（`{}` → `INVALID_LAYOUT`），所以只会打空验证，不会错排。

判定：**预算够，模型没做对**。R0 的 30 步里有 8 步 `INVALID_LOCATION`（决策 1、2、5、10、15、23、24、27）+ 1 步空验证（决策 22），再加两次未读全信息的盲猜（决策 18、20）；把这些去掉后 20 步即可解。30 步的余量是 10 步（50%），不宽裕但足够。

## 6. 指标

| 指标 | kind | 公式（登记） | 分母 | 三局取值 |
|---|---|---|---|---|
| `map13.constraint_satisfaction_ratio` | primary | satisfied_constraints / total_constraints | 5 | 0.2 / 0.8 / 0.8 |
| `map13.correct_sequence` | primary | 1 if door_order == derived_unique_order else 0 | episode | 0 / 1 / 1 |
| `map13.illegal_door_attempts` | guardrail | count(ILLEGAL_DOOR) | episode | 3 / 0 / 0 |
| `map13.state_resets` | diagnostic | count(STATE_RESET) | episode | 2 / 0 / 0 |
| `map13.completion_ticks` | diagnostic | terminal_tick if success else N/A | 成功局 | None / 27 / 19 |

- 计算事件：只在地图自己的 `metrics()` 里算，没有独立 extractor；分母固定 5，`_layout_for_metrics()` 决定用哪个布局。
- **未通关仍有意义的连续主指标**：有。`constraint_satisfaction_ratio` 在 R0（未通关）给出 0.2，在随机基线给出 0.0，在消融给出 0.8，在启发式给出 1.0——它是本图区分度最好的量。
- `not_applicable` / `censored`：R0 的 `completion_ticks` 在 V8 是 `not_applicable`，V9 按登记的重投影规则改成 `censored`（`runs/v9/rescore/MAP-13.json`）。其余 4 条在三局都是 `valid`。
- 发现的口径缺陷（都可复现）：
  1. **`illegal_door_attempts` 定义漂移**：登记公式是 `count(ILLEGAL_DOOR)`，实现里 `_verify()` 在"无完整试排"和"错排"两条路径都执行 `illegal_door_attempts += 1`。R0 的结果码只有 1 次字面 `ILLEGAL_DOOR`（决策 22），但指标报 3（另 2 次是 `STATE_RESET`）。模块 docstring 写的"被拒绝的 verify_layout 次数"才与实现一致。
  2. **`constraint_satisfaction_ratio` 的"最后一次"口径与实现不一致**：docstring 写"最后一次试排满足的房间谓词数"，实现是 `_layout_for_metrics()` = `last_attempted_layout or trial_layout`，即**最后一次被 verify 的布局**优先，会忽略之后 `set_trial_layout` 但未 verify 的布局。R0 因此报 0.2 而不是 0.6（§11 手算）。
  3. **`record_constraint` 无任何可测产出**：`recorded_clue_ids` 不进任何指标，导致设计意图"观察与记录是两件事"不可测（15 步不记录路线同样满分）。
  4. **`remaining_incorrect_attempts` 语义歧义**：值 = `MAX-1-incorrect`，R0 决策 21 后显示 0，但此时仍可再交一次错排（第 3 次才失败）。字段读作"还能错几次"时会误导。
- 区分能力：能区分 ≥4 种策略（随机 0.0、MiMo R0 0.2、消融 0.8、启发式 1.0），不是 `LOW_DISCRIMINATION`。

## 7. 三次轨迹归因

### R0（`...-a0b524e9`，30 步，预算耗尽，0/1）

引用（动作来自原始 Trace，`delta` 来自证据包原文）：

- 决策 1：`{"room": "N", "tool": "read_inscription"}` → `INVALID_LOCATION`，`{"current_tick": 1}`（人在 C，却读 N）。
- 决策 4：`{"room": "N", "tool": "read_inscription"}` → `inscription:日神不得居于两端。`，`observed_clues` 新增 `{"clue_id": "N_SUN_NOT_END", "text": "日神不得居于两端。"}`。
- 决策 19：`{"tool": "verify_layout"}` → `STATE_RESET`，`{"current_tick": 19, "incorrect_attempts": 1, "remaining_incorrect_attempts": 1, "trial_layout": null}`。
- 决策 21：`{"tool": "verify_layout"}` → `STATE_RESET`，`{"current_tick": 21, "incorrect_attempts": 2, "remaining_incorrect_attempts": 0, "trial_layout": null}`。
- 决策 22：`{"tool": "verify_layout"}` → `ILLEGAL_DOOR`，`{"current_tick": 22}`（无试排，纯空验证）。
- 决策 30：`{"layout_by_room": {"E": "日", "N": "甲", "S": "眼", "W": "芦"}, "tool": "set_trial_layout"}` → `trial_layout_set`；预算在此结束，没有第 31 步的 verify。

**首次偏离合理策略的可观测事件**：决策 1（在 C 读 N）。它同时暴露两个问题——不知道 `read_inscription` 的位置约束，以及把"读碑文"当成"读任意房间"。真正的代价出现在决策 18–21：只读了 4 条房间谓词、从未读方向钉，就凭直觉排了两次。

失败链：位置错误 8 次（决策 1、2、5、10、15、23、24、27）→ 信息不全（缺方向钉；W 直到决策 26 才读）→ 两次盲排（18/20）→ 容错用尽（21）→ 空验证（22）→ 决策 30 只是设置布局，预算结束。

替代解释：
- "预算不足"——不成立：20 步可解，R0 的 30 步里只有 8 步是位置空转，仍有 22 步可用于读全信息。
- "接口误导"——部分成立：`read/record` 的位置前置条件未公开，8 次 `INVALID_LOCATION` 是它的直接后果。
- "模型策略错误"——主要成立：读全 4 条后仍未去 C 读方向钉，也没有用 24 种排列枚举，而是凭直觉排。

### R1（`...-3c577add`，27 步，成功）

- 决策 5：`{"clue_id": "N_SUN_NOT_END", "tool": "record_constraint"}` → `INVALID_LOCATION`，`{"current_tick": 5}`（人在 N，record 只能在 C）。
- 决策 15–20：`record_constraint` 在 S → `INVALID_LOCATION`（决策 15）；`move C_S` → `ARRIVED:C`（16）；`move C_S` → `ARRIVED:S`（17）；`record_constraint` 再次 `INVALID_LOCATION`（18）；`move C_S` → `ARRIVED:C`（19）；决策 20 才 `recorded:S_ARMOR_ADJACENT_TO_SUN`。一条线索花掉 6 步。
- 决策 26：`{"layout_by_room": {"E": "日", "N": "甲", "S": "芦", "W": "眼"}, "tool": "set_trial_layout"}` → `trial_layout_set`。
- 决策 27：`{"tool": "verify_layout"}` → `GATE_OPENED`，`{"current_tick": 27, "gate_open": true, "terminal": true, "terminal_reason": "GATE_OPENED"}`。

**首次偏离**：决策 5 的"就地记录"。它是纯效率损失（R1 为同一条 S 线索花了决策 15–20 共 6 步），但没有破坏信息收集，所以仍在 27 步内读完 4 条谓词并开门。R1 全程 7 次 `INVALID_LOCATION`（决策 1、2、5、10、15、18、23）。

失败链：无失败。可归因的成功要素是"读全 4 条房间谓词 + 默认阅读序恰好正确"；方向钉仍未读，所以 `ratio=0.8`。

### R2（`...-2a5b828c`，19 步，成功）

- 决策 1–2：`{"room": "N", "tool": "read_inscription"}` → `INVALID_LOCATION`，`{"current_tick": 1}` / `{"current_tick": 2}`（与 R0/R1 同一错误）。
- 决策 18：`{"layout_by_room": {"E": "日", "N": "甲", "S": "芦", "W": "眼"}, "tool": "set_trial_layout"}` → `trial_layout_set`，`{"current_tick": 18, "trial_layout": {"E": "日", "N": "甲", "S": "芦", "W": "眼"}}`。
- 决策 19：`{"tool": "verify_layout"}` → `GATE_OPENED`，`{"current_tick": 19, "gate_open": true, "terminal": true, "terminal_reason": "GATE_OPENED"}`。

**首次偏离**：决策 1 的同类位置错误。R2 是"只读 3 条谓词（N/E/S，缺 W）就提交"的局。按独立枚举，只读这 3 条时仍有 **4 个**满足排列，所以决策 18 的排列不是被约束推出来的，而是在 4 个候选里命中（若均匀先验，概率 1/4）。这一点很重要：R2 的 `correct_sequence=1` **不能**当作约束传播能力的证据。

重复证据的限度：三局在决策 1–2 犯同一个错误（固定陷阱），但 R0 之后走向盲猜、R1/R2 走向读全/读三，说明位置错误本身不决定结局；n=3 不足以区分"个体差异"与"固定陷阱"。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **E 策略规划错误**（信息不全即试排、未读方向钉） | **C schema/接口误导**（位置前置条件未公开，8 次 `INVALID_LOCATION`） | 高 | 决策 1/2/5/10/15/23/24/27、18–22 |
| R1 | 无失败；若计效率则 E（记录位置未内化，6 步折返） | C（同上，7 次 `INVALID_LOCATION`） | 高 | 决策 5、10、15–20、23 |
| R2 | 无失败；成功含运气成分（3 条谓词剩 4 解） | E（信息不足即提交） | 中 | 决策 4/9/14/18/19 |

不采用 D（决策预算）：Oracle 20 步、启发式 20 步、15 步路线均成功，30 步不构成硬约束。

## 9. 标签

- `MEASUREMENT_VALID`：成功判据与环境一致（`GATE_OPENED`），主指标能区分 4 种策略（0.0 / 0.2 / 0.8 / 1.0），三次轨迹的结果码可逐条复算。
- `METRIC_DEFECT`：`illegal_door_attempts` 的登记公式与实现不符（R0 报 3，字面 `ILLEGAL_DOOR` 只有 1）；`constraint_satisfaction_ratio` 的"最后一次试排"与实现（最后一次被 verify）不符（R0 0.2 vs 0.6）。
- 不选 `CONSTRUCT_BYPASS`：24 种排列 + 最多 2 次非致命错排，盲猜命中率 ≤ 2/24，没有"固定路径直接通关"的证据。
- 不选 `BUDGET_BLOCKED` / `INTERFACE_BLOCKED`：20 步可解，且位置约束可试错发现。
- 不选 `RULE_DEFECT`：运行时行为与 `worlds/v4/MAP-13/map_spec.yaml` 一致（`incorrect_attempts_gte_3` 失败、`set_trial_layout` 不耗容错）。

## 10. 最小可证伪修复（无证据不修改）

**旧规则/旧公开信息**：`read_inscription` 需 `current_location_equals_room`；`record_constraint` 需在 C；prompt 只给动作名与形状，不给位置前置条件。

**证据与根因**：三局合计 20 次 `INVALID_LOCATION`（R0 8、R1 7、R2 5），全部来自位置前置条件未公开；同时 `record_constraint` 没有任何指标消费。

- 候选 A（**补公开信息**，首选）：在 system prompt 增加两句——"`read_inscription` 只能读你所在房间的碑文；`record_constraint` 只能在 C 记录已读碑文"。预期：消除 R0 那类 5 次空转，R1 的 6 步折返消失；不改变解的唯一性、难度和构念（这不是探索类地图）。反例/风险：会削弱"从结果码反推前置条件"的探索成分，但本图的构念是约束传播而非动作发现，可接受。
- 候选 B（**修指标口径**）：把 `illegal_door_attempts` 的公式改成"被拒绝的 `verify_layout` 次数"（与实现一致），或把错排单独计为 `state_resets` 且 `illegal_door_attempts` 只数字面 `ILLEGAL_DOOR`；把 `constraint_satisfaction_ratio` 的布局选择改成"最后一次 `set_trial_layout` 的布局"并同步 docstring。预期：R0 的 3→1、0.2→0.6。反例/风险：改口径后 V8 的 90 局数值不可直接比较，必须走 DCR 并对全部 Trace 重算。
- 候选 C（**让记录可测**）：新增一条 diagnostic（`recorded_clue_ids` 覆盖率）或删除 `record_constraint`。风险低，但只影响诊断层。
- 候选 D（**V9 证据层**）：在 `_compact_action` 的保留字段白名单补 `room`（以及 `claim_id`、`slot_index`），否则 MAP-13/14/15 的证据包都无法复原关键动作字段。风险：只影响 `runs/v9/evidence/*` 的重生成，不改 V8。
- 优先级：A（P1）> B（P1，需跨图重算）> D（P1，影响三图引用）> C（P2）。**不建议加预算或加容错。**

## 11. 基线与独立复算

`runs/v9/baselines/MAP-13.json`：

| 基线 | 成功 | 步数 | `ratio` | `correct_sequence` | `illegal_door_attempts` | `state_resets` |
|---|---|---|---|---|---|---|
| Oracle ×2 | 2/2 | 20 / 20 | 1.0 | 1 | 0 | 0 |
| `legal_random` ×20 | 0/20 | 30（全部耗尽） | 0.0（20/20） | 0（20/20） | 2–10（中位 5.5） | 0（20/20） |
| `public_heuristic` | 1/1 | 20 | 1.0 | 1 | 0 | 0 |
| 消融 `no_direction_nail` | 1/1 | 18 | 0.8 | 1 | 0 | 0 |

独立复算（不调用 `map13.metrics()`，按登记定义手算）：

- R1 的最终布局 `{"N":"甲","E":"日","S":"芦","W":"眼"}` → 位置 `日=2, 眼=4, 芦=3, 甲=1`：`日∈{2,3}` ✓、`眼>芦` ✓、`|甲-日|=1` ✓、`芦≠1` ✓，方向钉未读 ✗ ⇒ **4/5 = 0.8**，与报告值一致。
- R0 按实现口径取决策 21 被 verify 的布局 `{"N":"甲","E":"眼","S":"芦","W":"日"}` → `日=4` ✗、`眼2>芦3` ✗、`|甲1-日4|=3` ✗、`芦3≠1` ✓、方向钉 ✗ ⇒ **1/5 = 0.2**，与报告值一致。
- R0 按 docstring 口径取决策 30 的最后试排 `{"N":"甲","E":"日","S":"眼","W":"芦"}` → `日=2` ✓、`眼3>芦4` ✗、`|甲1-日2|=1` ✓、`芦4≠1` ✓、方向钉 ✗ ⇒ **3/5 = 0.6**。同一局两个合法读法给出 0.2 与 0.6，证明 §6 的口径漂移不是纸面问题。
- 唯一性复算：24 排列 × 四条谓词 = 1 解（见 §4 表），任意 3 条谓词都不能唯一确定。

判别力：主指标在 0.0（随机）、0.2（R0）、0.8（消融/R1/R2）、1.0（启发式/Oracle）四档上都出现过，**不是** `LOW_DISCRIMINATION`。

## 12. V9 状态

`NEEDS_REDESIGN`，优先级 **P2**。

一句话理由：场景规则、成功判据与主指标都可测且能区分 4 种策略，但 `constraint_satisfaction_ratio` 与 `illegal_door_attempts` 两个口径与实现不一致（同一局可算出 0.2 与 0.6），修正口径前不能把数值直接并入 V9 汇总。
