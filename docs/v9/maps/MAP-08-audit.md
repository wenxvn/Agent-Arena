# MAP-08 审计：看不见的裂缝（abyss / 中等，V4 适配图）

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-08 / abyss / 中等 |
| condition | `hypothesis_table`（V4 适配） |
| `rule_hash` | `9a3827c2f5fe75bd6368e98035fde35a2048fedb73d0f150bbc64eda13e6ddd2` |
| `scenario_hash` | `14daf6879328c3c86e2280809b061b1f11501ede87f9f8c98910440120d09050` |
| `prompt_hash` | `6ce88b04d9faa155804a6c8b116f217f9820e8f43a74d306283676e569ad6390` |
| 决策预算 | 38（`BUDGETS["中等"]`）；环境 `step_limit=160` |
| V8 三局 | 0/3 成功；R0/R1/R2 均 `decision_budget_reached`，决策 38 / 38 / 38，非法 schema 0 |
| 费用（正式行） | 0.02169032 / 0.01801644 / 0.01830844 CNY |
| 证据包 | `runs/v9/evidence/MAP-08.json` |
| Trace 索引 | `docs/v9/run-index.csv` 第 23–25 行（trace sha256 `c44abe79…`、`b4ad4314…`、`1c31c663…`） |
| 规则资料 | `docs/v8/maps/MAP-08-final.md`、`worlds/v4/MAP-08/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}` |
| 源码 | `src/agent_arena/worlds/scenario_v4/map08.py`、`src/agent_arena/worlds/scenario_v8/v4_adapter.py`、`src/agent_arena/v6/scenes.py::map08_l3_original` |
| 公开词表 | `src/agent_arena/v8/prompts.py::_VOCABULARY["MAP-08"]` |
| 基线 | `runs/v9/baselines/MAP-08.json` |

## 1. 能力构念

这张图想测的是：**Agent 能否用最少的主动压力测试把隐藏漏点从三个候选里消减到一个，并在测试代价（每次 2 tick、水位持续上涨）耗尽安全裕量之前停手去密封**。

- 成功行为：移动到一个测试站（X 或 Y），执行合法 `pressure_test_*`，用公开签名表过滤候选；当候选唯一时前往该候选点执行 `repair_leak`，返回 `LEAK_SEALED`。
- 明确反例：把唯一一支密封剂用在错误候选上 → `SEALANT_MISUSED`；或一直测试到 `water > 7.0` → `CORE_WATER_LIMIT_EXCEEDED`。注意“不做测试直接修”在 seed=0 会因 `true_leak=B` 与候选顺序重合而蒙中（见 §2 旁路），它**不是**本图认可的成功行为。
- 本图在简单/中等/困难递进中的位置（只写本图）：它是 abyss 唯一的**信息获取题**——MAP-07 的水位全公开，MAP-09 的难点是资源耦合；本图的难点是“观测需要花 tick，而 tick 会淹水”。

## 2. 机制与因果链

起始状态（`runs/v9/evidence/MAP-08.json` 初始 Observation 原文）：

```json
"current_core_water": 1.0, "current_tick": 0, "location": "A",
"published_candidate_set": ["B", "D", "F"],
"published_prior": {"B": 0.3333333333333333, "D": 0.3333333333333333, "F": 0.3333333333333333},
"baseline_sensor_reading": "flat",
"known_test_semantics": {
  "X": "B 读数为 pulse_amber；D 读数为 pulse_slate；F 读数为 pulse_slate",
  "Y": "B 读数为 pulse_slate；D 读数为 pulse_cobalt；F 读数为 pulse_slate"},
"test_results": {}, "sealant_count": 1,
"visible_edges": ["A_B:B", "F_A:F", "X_A:X"]
```

因果链：

1. **起始**：水位 1.0，候选 B/D/F 等先验；底噪 `flat` 对三者完全相同，**不提供任何区分信息**。
2. **必需观察**：`known_test_semantics`（签名表）+ 走到 X 或 Y 后的 `test_results`。注意这张表在初始 Observation 里就是公开的，所以这是一个“已知信息结构、未知一次读数”的主动学习问题。
3. **关键决策**：先在 A→X（1 tick），执行 `pressure_test_X`（2 tick，水位 +1.0）；`pulse_amber` 唯一指向 B，`pulse_slate` 把候选缩到 {D,F}，再用 Y 区分（D=`pulse_cobalt`，F=`pulse_slate`）。
4. **立即后果**：每次移动 +0.5 水位、每次测试 +1.0、正确密封 +0.5；水位 >7.0 立即 `CORE_WATER_LIMIT_EXCEEDED`。唯一一支密封剂用错立即 `SEALANT_MISUSED`。
5. **终局**：`repair_leak(target)==true_leak` → `LEAK_SEALED`；否则失败。

- **可绕过核心机制的动作**：
  1. **盲修第一个候选**。seed=0 的 `true_leak="B"`（`LEAK_BY_SEED` 的 0–3 → B），而 `published_candidate_set` 的第一个元素也是 B。`A→B` + `repair_leak(B)` 两个动作即可成功，完全跳过诊断。这是 1/3 的构造旁路（seed 4/8 会 `SEALANT_MISUSED`）。
  2. **无效动作不耗水位**。V4 适配层里 `_reject` 不推进 `current_tick`（`map08.py:203-205`）；只有 `move`/`inspect`/`wait`/合法 `interact` 才调用 `_advance_pressure`。因此模型可以无限次提交错误边名而水位不涨，只会消耗决策预算。原生 V8 地图对被拒动作仍计 1 tick，这是适配带来的风险语义差异。
- **机制是否在三条真实轨迹中实际触发**：**没有**。三局 `tests_run=0`、`candidate_reduction=0`、`information_gain_bits=0.0`；`test_results` 始终是 `{}`。水位只随 4–6 次成功移动上升到 3.0–4.0，远未触及 7.0。
- **触发所需的最小动作数**：5（X 测试 + 返回 + 去 B + 修）；两测试路线 8–10 步。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `published_candidate_set` / `published_prior` | 是 | 初始 | 是 |
| `known_test_semantics`（完整签名表） | 是 | 初始 | 是。X 与 Y 的**信息增益对称**（amber/cobalt 各能锁定一个候选，slate 都剩两个）；X 只因为与起点 A 相邻（1 tick）而更便宜 |
| `test_results` | 是 | 测试后 | 是 |
| `current_core_water` / `current_tick` / `sealant_count` | 是 | 每步 | 是 |
| `visible_edges` | 是，但格式为 `"A_B:B"`（边 + 目的地复合字符串） | 每步 | **部分**：`move` 需要裸边名 `A_B`，公开词表未说明如何切分 |
| `true_leak` | 否，只在 hidden `judge_state` | 不可见 | 不用于公开策略 |
| `inspect` 的合法 target | **否**。词表写 `inspect(target_id): X, Y`，运行时只接受 `ordinary_sensor` | 不可见 | **否**：按词表 inspect 必被拒 |
| `move` 动作 | **词表完全没有列出**，但动作契约里有 `move/edge_id` | 契约可见、词表缺失 | 部分：只能靠契约与 `visible_edges` 猜 |
| 水位上限 7.0、测试 2 tick、错修 4 tick | 否（只在 `map08.py` 常量/`map_spec`） | 不可见 | 不需要精确值也能解，但无法判断“还能测几次” |
| `hypothesis_table` 机制 | **形式上有提示，实际无字段**：V8 system prompt 只要求 `{"decision_reason","action"}`；V8 以 `response_format=json_object` 运行，未启用 `llm/protocol.py` 里那个含 `agent_hypothesis_table` 的 strict schema；runner 也只解析 `candidate["action"]` | 每步 | 否：该条件在 V8 里不可操作 |
| Oracle 路径 | 否（`adapter_cases` 只在离线基线里调用） | 不可见 | 不用于公开策略 |

**适配带来的三个边界（本图专属）**：

1. **公开机制文案错误**。`goal` 字段缺失时 `system_prompt` 回退到类 docstring，而 V8 适配类只有 `"A V4 environment behind the V8 public contract."`。所以送给模型的“本图机制”是适配层说明，不是 V4 设计意图（“三个候选点水位曲线、传感器底噪和房间描述起初完全相同；唯一可分辨来源是主动执行 X/Y 测试”）。这是 B/C 类信息缺陷。
2. **`condition=hypothesis_table` 是空壳**。`Map08Environment` 没有 condition 参数，也不读取 `condition_id`；`V4HypothesisTable` 只被 V5/V6 runner 使用。V8 的 system prompt 只要求 `{"decision_reason","action"}`，runner 的 `_parse_action` 只读 `candidate["action"]`，且 V8 以 `response_format=json_object` 运行、没有启用 `llm/protocol.py::decision_response_schema("scenario_v4")` 中那个包含 `agent_hypothesis_table` 的 strict schema（该 schema 只在 `json_schema` 模式下生效）。因此 V8 的 `hypothesis_table` 与 `no_hypothesis_table` 在运行时**完全等价**，只在 prompt 里多一句“本条件启用 Agent 自己的假设表”。V8 的 MAP-08 结果不能用来声称“假设表条件有效果”。
3. **种子边界**。V4 试点只注册 seed ∈ {0,4,8}（`scenario_v4/catalog.py`），V6 实例 `map08_l3_original` 的 `leak_by_seed` 覆盖 0–11；V8 适配层直接调用 `build_v6_environment`，绕过 V4 的 {0,4,8} 限制。V8 正式三局都用 seed=0，因此三次重复的 `true_leak` 恒为 B，**不构成三个独立场景**。

## 4. 可解性与可观察性

- Oracle：1 条（`MAP-08-solver-success`，来自 V6 独立求解器），5 个动作，`ok=true`，终态 `LEAK_SEALED`（`runs/v9/baselines/MAP-08.json`）。
- Oracle 文件 `worlds/v4/MAP-08/oracle_trace.jsonl` 另有 4 条纸面路线（x_first_B 5 步、x_then_y_F 8 步、y_first_D 5 步、y_then_x_B 10 步），但 `adapter_cases` 只把求解器的 1 条纳入 V8 Oracle。
- **仅凭公开信息是否存在可执行策略：存在**。本批 `Map08Heuristic` 只读公开字段：把 `visible_edges` 的 `"EDGE:OTHER"` 按 `:` 切出 `EDGE`，用签名表过滤 `published_candidate_set`，X 先测、必要时再测 Y，最后修。seed=0 时 5 个决策成功，指标 `candidate_reduction=2/3`、`tests_run=1`、`diagnosis_accuracy=1`；seed=4/8 各 8 个决策成功（见 §11）。
- 因此本图**不构成 `INTERFACE_BLOCKED`**：公开信息足够，但需要一次“复合边名切分”的推断，且公开词表没有提示。这是 C 类摩擦而非封死。
- 需要注意：该结论依赖 seed=0 的 X→amber→B 路径；换成 seed=4/8 需要额外探索，但仍然可解（策略在 C 处按无信息 tie-break 选择 D 方向）。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| Oracle 动作数 | 5 |
| 决策预算 | 38 |
| `legal_random` 20 seed | 0 成功；20/20 `decision_budget_reached`，决策 38；测试 0 次；被拒 32–38 次/局（合计 694）。注意环境 seed 固定为 0，变动的只是策略 RNG 种子 |
| 公开启发式 | 5 决策，`LEAK_SEALED`（seed 0）；seed 4/8 各 8 决策成功 |
| 消融 `no_hypothesis` | 2 决策成功（seed 0）；seed 4/8 `SEALANT_MISUSED` |
| 三局 MiMo | 38/38/38，全部耗尽 |

判定：**不是预算不够，也不是规则太难**。最小解 5 步、预算 38 步；三局把 33–38 个决策花在边名格式与无效 `inspect` 上，水位才涨到 3.0–4.0。若只看“是否理解 X/Y 测试”，三局都没有真正开始诊断（`tests_run=0`）。

## 6. 指标

本图 7 条指标（`v7/metrics/map08.py`）：

| 指标 | 类别 | 计算事件 | 分母 | 缺失/截尾 |
|---|---|---|---|---|
| `map08.candidate_reduction` | primary | 公开测试签名逐步缩小的候选比例 `(N0-Nf)/N0` | 初始候选数 3 | 无测试 → 0（合法） |
| `map08.diagnosis_accuracy` | primary | `repair_leak(target)==true_leak` | 提交过 repair 的 episode | 无 repair → N/A（若截尾则 CENSORED） |
| `map08.information_gain_bits` | diagnostic | 每次合法测试的候选熵下降求和 | 实际测试数 | 0 次测试 → 0 bit |
| `map08.legal_action_rate` | diagnostic | 被规则接受的决策 / 提交决策 | 提交决策数 | 0 决策 → N/A |
| `map08.peak_core_water` | guardrail | `max_t current_core_water` | episode | 无观测 → UNAVAILABLE |
| `map08.tests_run` | diagnostic | 合法 `pressure_test_X/Y` 次数 | episode | 0 |
| `map08.wrong_repair` | guardrail | `terminal_reason==SEALANT_MISUSED` | 提交过 repair 的 episode | 无 repair → N/A |

- **未通关仍有意义的连续主指标**：有。`candidate_reduction` 在 0 成功时仍报 `0/3`；`peak_core_water` 报 3.0/4.0/4.0；`legal_action_rate` 报 0.105/0.158/0.158。这些都能刻画“诊断过程质量”，不依赖终局。
- **三局 N/A**：`diagnosis_accuracy` 与 `wrong_repair` 三局全 N/A。**原因是真实分母为 0**（从未提交 `repair_leak`），符合指标卡“无 repair 动作 → N/A”。`docs/v9/data-integrity.md` §4.1 把 MAP-08 的这两条列为“预算截尾投影问题”的例子，本图不成立：即使给到 380 个决策，没有 repair 也仍然 N/A。应把 MAP-08 从“投影口径待评估”名单里排除，只保留为“真实 N/A”。
- **区分度**：启发式（reduction 2/3、tests 1、info 1.585 bit、peak 4.0）与消融 `no_hypothesis`（0、0、0、2.0）可区分；但**二值成功不可区分**（seed 0 两者都成功）。因此在 seed=0 上不能只用 success 评价诊断能力，必须看 `candidate_reduction`/`tests_run`。V8 三局与消融的 `legal_action_rate` 也不同（0.105–0.158 vs 1.0），能定位“接口摩擦”。

## 7. 三次轨迹归因

### R0 `V8-MAP-08-R0-20261017T080241Z-fe1a5b93`

- 决策 1：`{"target_id":"B","tool":"inspect"}` → `INVALID_INSPECT_TARGET`；观察变化 `{}`（水位与 tick 都不动）。
- 决策 2：`{"edge_id":"A_B:B","tool":"move"}` → `INVALID_EDGE`；观察变化 `{}`。
- 决策 11：`{"edge_id":"A_B","tool":"move"}` → `MOVE_SUCCEEDED`；观察变化 `{"current_core_water":1.5,"current_tick":1,"location":"B","visible_edges":["A_B:A","B_C:C"]}`。
- 决策 20：`{"operation":"pressure_test_X","target_id":"X","tool":"interact"}`（此时在 D）→ `INVALID_TEST_LOCATION`；观察变化 `{}`。
- 决策 32：`{"operation":"pressure_test_D","target_id":"D","tool":"interact"}` → `INVALID_OPERATION`；观察变化 `{}`（合法测试站只有 X/Y）。
**首次偏离合理策略的可观测事件**：决策 2。模型在决策 1 已经拿到 `INVALID_INSPECT_TARGET`，说明“inspect 不能用于候选点”；决策 2 又直接把复合串 `A_B:B` 当边名，得到 `INVALID_EDGE`。此后它用了 9 个决策才在决策 11 猜对 `A_B`——而 `A_B` 一直就在同一个字符串的前半段。

**失败链**：错误 inspect → 错误边名 → 无效动作零成本（水位不涨）→ 模型没有把“拒绝”当成强反馈，继续试 `X_A:X`、`F_A:F`、`B_C:C` 等复合串 → 到达 B/C/D 后仍用 `target_id` 指向站点而不是候选点 → `pressure_test_*` 从未在合法位置执行 → 38 决策耗尽。

**替代解释**：预算不足（否，5 步可解）；模型策略错误（是次因，探索低效）；接口误导（首因：公开词表没有 `move`，`visible_edges` 是复合格式）；规则缺陷（否，Oracle 与启发式都成功）。

### R1 `V8-MAP-08-R1-20261017T080618Z-4b45160b`

- 决策 1：`{"target_id":"X","tool":"inspect"}` → `INVALID_INSPECT_TARGET`；`{}`。
- 决策 3：`{"operation":"pressure_test_X","target_id":"X","tool":"interact"}`（此时仍在 A）→ `INVALID_TEST_LOCATION`；`{}`。
- 决策 7：`{"edge_id":"A_B","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_core_water":1.5,"current_tick":1,"location":"B","visible_edges":["A_B:A","B_C:C"]}`。
- 决策 20：`{"edge_id":"Y_D","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_core_water":3.0,"current_tick":4,"location":"Y","visible_edges":["Y_D:D","Y_F:F"]}`。
- 决策 23：`{"operation":"pressure_test_D","target_id":"D","tool":"interact"}`（在 Y）→ `INVALID_OPERATION`；`{}`。

**首次偏离**：决策 3。模型已经知道“要去 X 才能测 X”，但在 A 就提交了测试；被拒后没有立即移动，而是先去 B、C、D，决策 20 才到 Y。**它在决策 20 已经站在合法测试站 Y 上，却在决策 21/23 去 inspect D、提交 `pressure_test_D`，始终没有执行 `pressure_test_Y`**。这是本局最接近成功的一步：只要在决策 21 调用 `pressure_test_Y`，就能拿到 `pulse_slate` 并把候选缩到 {B,F}，再测 X 或直接去 F。

**失败链**：错误 inspect → 提前测试 → 到站不测 → 用站点名当测试目标 → 预算耗尽。**替代解释**：词表写的是 `X|Y/pressure_test_X|pressure_test_Y`，模型可能把它理解成“target 与 operation 都是站点”，但它从未在 Y 上试过 `pressure_test_Y`，所以更像“忘记在正确位置执行”而不是纯接口问题。

### R2 `V8-MAP-08-R2-20261017T081119Z-446e53fc`

- 决策 1：`{"target_id":"X","tool":"inspect"}` → `INVALID_INSPECT_TARGET`；`{}`。
- 决策 3：`{"edge_id":"X_A:X","tool":"move"}` → `INVALID_EDGE`；`{}`。
- 决策 15：`{"edge_id":"F_A","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_core_water":1.5,"current_tick":1,"location":"F","visible_edges":["E_F:E","F_A:A","Y_F:Y"]}`。
- 决策 23：`{"operation":"pressure_test_Y","target_id":"Y","tool":"interact"}`（此时在 D）→ `INVALID_TEST_LOCATION`；`{}`。
- 决策 37：`{"edge_id":"C_D","tool":"move"}` → `MOVE_SUCCEEDED`；`{"current_core_water":4.0,"current_tick":6,"location":"C","visible_edges":["B_C:B","C_D:D","X_C:X"]}`。

**首次偏离**：决策 3（复合边名）。R2 的路线绕到 F→E→D→C，决策 23 在 D 提交 `pressure_test_Y`——**测试站 Y 与当前点 D 相邻（`Y_D`），只差一次移动**；模型没有移动，而是继续在 D/C 之间来回。

**重复证据有限**：三局都卡在 `visible_edges` 的复合格式与 `pressure_test_*` 的位置约束上，动作分布高度相似（R1/R2 都以 inspect X 开头，R0 以 inspect B 开头）。n=3 且 seed=0 固定，**不能区分“个体策略差异”与“接口固定陷阱”**；但结合 20 个 seed 的随机基线同样 0 次测试，可以判断这不是单局偶然。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **C**（`visible_edges` 复合格式 + 词表缺 `move` + inspect 目标错误） | E（9 步才猜对边名；到站不测） | 高 | 决策 1/2/11/20/32 |
| R1 | **C** | E（站在 Y 上不执行 `pressure_test_Y`） | 高 | 决策 1/3/20/23 |
| R2 | **C** | E（在 D 时不走到相邻 Y；环形漫游） | 高 | 决策 1/3/15/23/37 |

B（公开信息不足）在“机制文案”和“`move` 缺失”上部分成立，但公开签名表完整、启发式可解，所以不列为首因。D 不成立（5 vs 38）。A 不成立（规则与 Oracle 自洽）。H 不成立（无 provider 错误）。I 成立（n=3、seed=0）。

## 9. 标签

- **`MEASUREMENT_VALID`**：规则确定、Oracle 通过、公开启发式 5 步成功、指标可计算；本图的失败是真实的“接口摩擦 + 探索低效”，不是规则坏掉。主指标 `candidate_reduction`/`tests_run`/`legal_action_rate` 能有效区分启发式与消融。
- **`CONSTRUCT_BYPASS`**：`no_hypothesis` 消融在 seed=0 上用 2 个动作盲修 B 成功（`candidate_reduction=0`、`tests_run=0`），说明本图在唯一正式 seed 上存在 1/3 的“猜第一个候选”旁路；单 seed 的 success 不能证明诊断能力。
- **`INCONCLUSIVE`（条件层面）**：`condition=hypothesis_table` 在 V8 运行时没有对应字段/机制，V8 的 MAP-08 结果不能归因于“假设表条件”。

（不选 `INTERFACE_BLOCKED`：公开信息可解，启发式已证明。）

## 10. 最小可证伪修复（无证据不修改）

**旧公开信息**：

1. `visible_edges` 发布 `"A_B:B"`，而 `move.edge_id` 只接受 `"A_B"`；
2. MAP-08 公开词表没有 `move`，且 `inspect(target_id): X, Y` 与运行时 `ordinary_sensor` 不符；
3. `system_prompt` 的“本图机制”回退为适配层 docstring；
4. `hypothesis_table` 条件在 V8 prompt 中没有对应输出字段。

**证据与根因**：三局共 98 次被拒动作（R0 34、R1 32、R2 32）、0 次测试；R0 决策 2 与 R1 决策 7 是同一条边的两种写法，后者才成功；决策 20/23 已站在合法测试站却未执行合法测试。

**候选 A（首选，只补公开信息）**：适配层把 `visible_edges` 改为裸边名列表（`["A_B","F_A","X_A"]`），或额外发布 `visible_edge_ids` 字段；同时在 MAP-08 词表补一行 `move(edge_id)`。预期：`legal_action_rate` 从 0.1–0.16 升到接近 1，模型能把 38 个决策用于诊断而不是猜格式。

**候选 B（接口正名，仍不改规则）**：删除 `inspect(target_id): X, Y`，改为 `inspect(target_id): ordinary_sensor`（或在 Observation 中发布 `inspect_targets`）；把“本图机制”改为 V4 设计原句。

**候选 C（条件对齐）**：若确实要测 `hypothesis_table`，V8 的 prompt 与动作契约必须加入 `agent_hypothesis_table`（`belief_B/D/F`、`test_X_result`、`test_Y_result`、`next_test`），否则把 condition 改回 `default` 并在文档中登记“V8 不支持该条件”。**不建议**为了让它“看起来有效”而改 V4 环境或水位阈值。

**预期变化**：候选 A+B 后，模型应能在 5–10 步内完成至少一次测试，`candidate_reduction>0`；`success` 仍可能因单 seed 旁路而虚高，因此必须同时报告 `tests_run` 与 `candidate_reduction`。

**反例与回归风险**：
- 若只修 A 不修 B，模型仍可能被 `inspect(X)` 误导，浪费决策。
- 若把 `move` 目标直接写成中文描述，可能改变动作契约；必须保持 `edge_id` 字符串。
- 改 `prompt_hash` 后旧 Trace 不可与修复后直接比较；需要新的 run_id/账本。
- 单 seed 的旁路不会因 A/B 修复而消失；要消除它必须增加 seed 覆盖或要求“测试后才允许 repair”，后者属于规则修改，需主控 DCR。

**若无需修改**：不成立——三局都有可定位的公开信息与运行时不一致。

## 11. 基线与独立复算

来自 `runs/v9/baselines/MAP-08.json`：

| 策略 | 结果 | 决策 | 关键指标 |
|---|---|---|---|
| Oracle `MAP-08-solver-success` | `scenario_success` / `LEAK_SEALED` | 5 | ok=true |
| `legal_random` × 20 | 0 成功，20/20 `decision_budget_reached` | 38 | 测试 0，拒绝 694（环境 seed 固定 0） |
| `public_heuristic`（本批，seed 0） | `scenario_success` / `LEAK_SEALED` | 5 | reduction 2/3、tests 1、info 1.584963 bit、peak 4.0、legal 5/5 |
| `public_heuristic`（离线探针 seed 4 / seed 8） | 均 `scenario_success` | 8 / 8 | tests 2、reduction 2/3、peak 6.0（`scripts/v9_try_policy.py`，非 baseline JSON） |
| 消融 `no_hypothesis`（seed 0） | `scenario_success` / `LEAK_SEALED` | 2 | reduction 0、tests 0、peak 2.0 |
| 消融 `no_hypothesis`（离线探针 seed 4 / 8） | `scenario_failure` / `SEALANT_MISUSED` | 2 | wrong_repair 1、diagnosis_accuracy 0（`scripts/v9_try_policy.py`） |

**独立复算 1（`legal_action_rate`）**：按 Trace 逐行数“结果不以拒绝标记开头”的决策。R0 只有决策 11/15/19/37 四次 `MOVE_SUCCEEDED`，其余 34 条是 `INVALID_*`，故 4/38 = 0.105263；R1 有决策 7/12/16/20/34/35 共 6 次移动，6/38 = 0.157895；R2 有 15/19/22/29/33/37 共 6 次，6/38 = 0.157895。与 extractor 输出逐位一致。

**独立复算 2（`candidate_reduction`）**：三局 `test_results` 均为 `{}`，没有可复演的测试事件，剩余候选仍为 {B,D,F}，故 `(3-3)/3 = 0`，与 judge 输出一致。启发式 seed 0 只有 X 一次测试、读数 `pulse_amber`，签名表把候选缩到 {B}，`(3-1)/3 = 0.666667`，与 `runs/v9/baselines/MAP-08.json` 的 `numerator=2, denominator=3` 一致。

**区分度**：指标能区分启发式与盲修消融（reduction 2/3 vs 0、tests 1 vs 0、peak 4.0 vs 2.0）；但 seed=0 的 `success` 不能区分二者，记 **`LOW_DISCRIMINATION`（仅限二值成功）**，并建议报告连续指标。

## 12. V9 状态

**`NEEDS_REDESIGN`（P1）**。理由：规则与指标本身可用，但 V4 适配层把 `visible_edges` 的复合格式、缺失的 `move` 词表、错误的 `inspect` 目标与空壳 `hypothesis_table` 一起暴露给模型，导致 0/3 的失败主要发生在接口层而非诊断层；在修复公开信息并扩大 seed 覆盖前，MAP-08 的成功率不能解释为“主动诊断能力”。
