# MAP-28 消失的王冠：V9 逐图审计

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-28 / castle / 简单 |
| condition | `default` |
| `scenario_hash` | `42ae98aa24e90202b931fa381b4fc6d953abcbc3ab74755b74a8f524f642648b` |
| `rule_hash` | `ce443167b19df2c528eaeff66adb7196129eb116d15d59f1e933afeb13a612ee` |
| 决策预算 | 30 |
| 环境步数上限 | 160 tick |
| V8 三局 | 0/3 成功；三局均 `decision_budget_reached`；决策数 30/30/30 |
| V8 主指标 | `key_evidence_coverage` 0.25 / 0.75 / 0.25；`timeline_constraint_satisfaction` 0.0 / 0.0 / 0.0；`time_contradictions` 0；`unsupported_accusations` 0 |

数据来源：`runs/v9/evidence/MAP-28.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-28-final.md`、`worlds/v4/MAP-28/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map28.py`。

> V9 证据包把 `submit` 的 `citations_by_claim` 过滤掉了（`src/agent_arena/v9/evidence.py::_compact_action` 白名单不含该字段）。本节所有提交内容引自原始 `runs/v8/**/agent_trace.jsonl`，不从证据包推断。

## 1. 能力构念

一句话：**在一条短证据链上把“猜中真相”变成“可交叉证明的真相”**——人物、入口门、进入分钟、离开分钟四个字段，每个都必须有 ≥2 个不同来源类别且值正确，一次提交终局。

- 成功行为：先到 V/S/K/A 取证并 `record`，回 H 提交四字段，结果码 `ALL_CLAIMS_SUPPORTED_AND_CORRECT`。
- 明确反例：值全对但某栏只引用一类来源（`ACCUSATION_WITHOUT_TWO_SOURCES`）；引用未 `record` 的证据（该类证据被静默忽略，等价于单源）；用某个“时间窗”分钟代替锁芯精确分钟（`CLAIM_CONTRADICTS_RECORDED_EVIDENCE`）；厨师的人名误认被当成人物结论（`WITNESS_BASIL_S_WINDOW` 只支持路径与时间窗，不支持人名）。
- 递进位置：本图是同世界最简单的一图（单案、四字段、来源全部可靠）。中等 MAP-29 引入不可靠证人与 8 问预算，困难 MAP-30 引入案卷与 40 tick 听证边界。本图的难度只来自**交叉证明纪律**，不来自欺骗。

## 2. 机制与因果链

起始 H（`local_neighbors=["V"]`）→ 到 V 调查 `vault_lock_events` 得到 `LOCK_ENTRY_K3_2106`（21:06 从 S 侧开锁）与 `LOCK_EXIT_S_2114`（21:14 退出）→ 到 S 调查 `footprint_trail` 得 `PRINT_C7_ROUTE_SV`（Celine、S-V 方向、时间窗）→ 到 K 访谈 `kitchen_cook` 得 `WITNESS_BASIL_S_WINDOW`（人名误认 Basil，但路径与时间窗有效）→ 经 G 到 A 读 `key_registry` 得 `KEY_REGISTER_K3_CELINE` → 对每个已观察证据执行 `record` → 回 H `submit(claims, citations_by_claim)` → 四栏各 ≥2 类且值全对则 `ALL_CLAIMS_SUPPORTED_AND_CORRECT`，否则一次性 `CASE_REJECTED`。

- **可绕过点**：没有。`submit` 只认 `recorded_ids` 中的引用（`map28.py:330`），观察过但没记录的证据不计入来源类别；`record` 只能记录已观察 ID（`map28.py:281-283`）。所以“调查 → 记录 → 提交”是不可压缩的三段。
- **三条轨迹是否触发核心机制**：只有 R1 部分触发——决策 7/14 分别拿到锁芯与脚印，决策 21 读到登记，决策 22 发起唯一一次 `submit`，但不在 H，被判 `INVALID_LOCATION`（非终局）。R0/R2 从未发起 `submit`：机制在两次运行里**完全没有被执行**。
- **最小动作数**：实测 16 步可成功（H→V 调查→S 调查→K→G→A 读→4 次 `record`→G→V→H 提交，`key_evidence_coverage` 3/4）。带厨师访谈与证词记录的 18 步策略同样成功（见 §5）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| 房间图 `H_V/V_G/G_K/K_S/S_V/A_G` | 是 | 初始只有 `H_V`，之后逐房间由 `visible_edges`/`local_neighbors` 展开 | 是 |
| 四件证据 ID 与 `fact` 原文 | 是 | 到达对应房间并 `investigate`/`read_record`/`interview` 后进入 `observed_evidence` | 是（时间与人物可从 fact 正则读出） |
| `recorded_evidence_ids` | 是 | 每次 `record` 后 | 是 |
| “四字段各需 ≥2 个不同来源类别” | 是 | `goal` 文本 | 是（但未说明“类别”指 `source_class`） |
| “提交必须在 H” | 是 | `goal` 文本“在 H 提交…” | 是 |
| “引用必须是**已 record** 的证据，观察过不算” | **否** | 仅存在于 `map28.py:330` 的实现 | 否——只能靠失败码反推，而提交是单次终局 |
| `person_id` 合法枚举大写 `ADA/CELINE/BASIL` | **否** | 仅 `map28.py:127`、私有 docstring | 否；Observation 只出现 `Celine`/`Basil` |
| `entry_path_id` 合法枚举 `BANQUET_H_V/GUARD_G_V/SECRET_S_V` | **否** | 仅 `map28.py:128` 与设计 YAML | 否；Observation 只出现“S 侧 / S 路径”和边 ID `S_V` |
| 真值 `CELINE/SECRET_S_V/21:06/21:14` | 否 | 仅 `judge_state.truth` | 不需要：可由证据推出（除路径拼写） |
| Oracle 路线与用例数 | 否 | `ORACLE_CASES` | 不适用 |

## 4. 可解性与可观察性

- Oracle：1 个用例 `evidence_first_two_source`，20 个动作，`ok=True`，`scenario_success`（`runs/v9/baselines/MAP-28.json`）。
- **仅凭公开信息是否存在可执行策略**：策略骨架存在且已验证——`world_castle.Map28Heuristic` 只用 `location/local_neighbors/observed_evidence/recorded_evidence_ids` 决定下一步，18 步成功。但它把 `SECRET_S_V` 作为常量：该拼写无法从 Observation 推出（只能看到边 ID `S_V` 与“S 侧”），这是本图唯一真正缺口的公开信息。
- 补充实验（离线，只读）：把提交值改为 `Celine` / `S-V`，在 H 提交会得到 `INVALID_ACTION_ENUM`，且**消耗 0 tick、不消耗唯一提交**（`map28.py:305-308`、`_pending_cost = 0`），可以重试；但结果码不告诉模型枚举空间，只能盲试。因此本条判为“公开信息不足，可试探但无信息梯度”，不是秒失败。
- 另一处遮蔽：`_submit` 先判位置（`map28.py:346`）再解析 claims，所以 R1 决策 22 在 A 提交同时带有非法的 `Celine`/`S-V`，只返回 `INVALID_LOCATION`，两个真实缺陷都被掩盖。
- 不存在“只有知道隐藏规则才能避免秒失败”的情形（没有一步终局的环境陷阱），因此不标 `INTERFACE_BLOCKED`。

## 5. 预算可行性

- Oracle 20 动作 / 预算 30；可行最短路 16 动作（实测成功，`key_evidence_coverage=3/4`）；公开启发式 18 动作成功。
- `legal_random` 20 seeds：成功 0/20，全部 `decision_budget_reached`，决策数全为 30，非法形状动作 87 次、被环境拒绝动作 508 次。随机基线在这张图上完全没有概率触达成功。
- 公开启发式：18 决策、0 非法、0 拒绝、`ALL_CLAIMS_SUPPORTED_AND_CORRECT`，四项指标 4/4、0、4/4、0。
- 消融 `no_record`（只观察不记录，直接引用已观察证据）：13 决策，`CASE_REJECTED`，`key_evidence_coverage` 0/4、`unsupported_accusations` 1。说明“record 前置”是决定性的隐藏条件。
- 判定：**不是预算不够，是模型没做对**。三局合计 90 决策，其中只有 R1 的一步是 `submit`；R0/R2 共 60 决策里有 39 次 `move`、14 次 `TARGET_NOT_VISIBLE`，连“收集 4 件证据”都没完成。

## 6. 指标

| 指标 | 事件 | 分母 | 缺失/截尾 | 三局取值 |
|---|---|---|---|---|
| `map28.key_evidence_coverage` | `recorded_ids` ∩ 4 件关键证据（K3 登记、K3 锁日志、C7 脚印、厨师证词） | 4 | 未调查 → 0（合法） | 0.25 / 0.75 / 0.25 |
| `map28.timeline_constraint_satisfaction` | 值等于 truth 且引用 ≥2 类来源的字段数 | 4 | 未提交 → 0（合法） | 0 / 0 / 0 |
| `map28.unsupported_accusations` | 提交时任一字段来源类别 <2 记 1 | 每局 | 未提交 → 0 | 0 / 0 / 0 |
| `map28.time_contradictions` | 被已记录证据排除的 entry/exit 字段数 + 时序倒置 | 每局 | 未提交 → 0 | 0 / 0 / 0 |

- **未通关仍有意义的连续指标**：`key_evidence_coverage` 是过程量，三局 0.25/0.75/0.25 已经能区分“摸了门”和“走完证据链”。`timeline_constraint_satisfaction` 在本图未通关时只能为 0，因为它只在提交时写；三局全 0 是**真分母为 0（没有提交）**，不是投影造成的 N/A。
- 三局没有 `not_applicable` / `censored`：V8 把 `decision_budget_reached` 投影成“有值就报值”，本图四项都有值。
- 区分度：Oracle/启发式（4/4, 4/4）↔ `no_record` 消融（0/4, 0/4）↔ 随机（0/20 成功）↔ V8 三局（0.25–0.75, 0）。`key_evidence_coverage` 能区分四种，`timeline_constraint_satisfaction` 只能区分“提交且全对/其他”。

## 7. 三次轨迹归因

通用背景：三次重复使用同一 seed（`seed=0`，`replicate_id=0/1/2`）。R0/R2 属于同一种“在 H↔V 之间空转”的模式，R1 是唯一接近成功的一次。

### R0（`V8-MAP-28-R0-20261017T104822Z-d62a592d`，30 决策，`decision_budget_reached`）

- 决策 1 `{"target_id": "vault_lock_events", "tool": "investigate"}` → `TARGET_NOT_VISIBLE`，观察变化 `{"tick": 1}`：在 H 调查宝库锁，房间不对，白花 1 tick。
- 决策 2 `{"to": "V", "tool": "move"}` → `MOVE_SUCCEEDED`，`{"local_neighbors": ["G", "H", "S"], "location": "V", "tick": 2, "visible_edges": ["H_V", "S_V", "V_G"]}`；紧接着决策 3 `{"to": "H", "tool": "move"}` → `MOVE_SUCCEEDED`，立刻退回 H。
- 决策 6 才第一次 `investigate` 成功：`LOCK_EVIDENCE_FOUND`，`observed_evidence` 出现 `LOCK_ENTRY_K3_2106`（“K3 于 21:06 从 S 侧开启 V 锁舌”）与 `LOCK_EXIT_S_2114`（“21:14 从 S 侧退出并关闭 V 锁舌”）；决策 7–8 记录这两条。
- 决策 19 `{"target_id": "footprint_trail", "tool": "investigate"}` → `TARGET_NOT_VISIBLE`，`{"tick": 19}`：脚印在 S，模型却在 V 调查。
- 决策 30 `{"record_id": "key_registry", "tool": "read_record"}` → `TARGET_NOT_VISIBLE`，结束：登记在 A，模型在 H 读。
- 首次偏离：决策 1（未移动就调查）与决策 3（到达 V 后立即折返）。失败链：无目的往返 → 只拿到 2 条锁日志 → 从未读登记/未记录 → 从未提交。合计 16 次 move、10 次 `TARGET_NOT_VISIBLE`。
- 替代解释：预算不足？不成立（Oracle 20、最短路 16）。接口误导？部分成立（房间与目标的对应关系只能靠 `TARGET_NOT_VISIBLE` 逐个试），但 30 步足够走完六个房间。

### R1（`V8-MAP-28-R1-20261017T105046Z-8ad773ef`，30 决策，`decision_budget_reached`）

- 决策 7 `{"target_id": "vault_lock_events", "tool": "investigate"}` → `LOCK_EVIDENCE_FOUND`，`observed_evidence` 从空变为两条 instrument_log；决策 14 `footprint_trail` → `FOOTPRINT_EVIDENCE_FOUND`，新增 `PRINT_C7_ROUTE_SV`（“C7 靴纹匹配 Celine；连续 S-V 方向痕迹；进入 21:05-21:07、离开 21:13-21:15”）。
- 决策 21 `{"record_id": "key_registry", "tool": "read_record"}` → `REGISTER_READ`，观察里出现 `KEY_REGISTER_K3_CELINE`（“K3 于 20:58 登记给 Celine，案发时段无转交”），但**没有 record 它**，此时 `recorded_evidence_ids` 仍只有 3 条。
- 决策 22（原始 Trace，非证据包）：`{"citations_by_claim": {"entry_path_id": ["PRINT_C7_ROUTE_SV", "LOCK_ENTRY_K3_2106"], ..., "person_id": ["KEY_REGISTER_K3_CELINE", "LOCK_ENTRY_K3_2106", "PRINT_C7_ROUTE_SV"]}, "claims": [{"claim_id": "person_id", "value": "Celine"}, {"claim_id": "entry_path_id", "value": "S-V"}, {"claim_id": "entry_time", "value": "21:06"}, {"claim_id": "exit_time", "value": "21:14"}], "tool": "submit"}` → `INVALID_LOCATION`，观察变化仅 `{"tick": 22}`。
- 首次偏离：决策 22——人在 A 却直接提交（`goal` 写的是“在 H 提交”）；同时三个隐性问题被这一次结果码合并掩盖：未 record 的登记引用、`Celine` 非枚举、`S-V` 非枚举。
- 失败链：位置错误 → 之后 8 步在 K/G/S 之间往返，决策 28 才补记证词（覆盖率升到 3/4）→ 预算耗尽，未第二次提交。合计 15 move、6 `TARGET_NOT_VISIBLE`、4 次 `read_record`（其中 3 次不在 A）。
- 替代解释：模型“策略错误”是首因；但即便它当时在 H，`Celine`/`S-V` 也只会换来 `INVALID_ACTION_ENUM`（0 tick）——那天它没有信息去寻找 `CELINE`/`SECRET_S_V` 的正确拼写，所以接口缺口是真实的第二因。

### R2（`V8-MAP-28-R2-20261017T105321Z-7ce91398`，30 决策，`decision_budget_reached`）

- 决策 1–24 是 H↔V 往返（23 次 move），决策 25 才 `LOCK_EVIDENCE_FOUND`，观察出现两条锁日志。
- 决策 26–27 记录两条锁日志，`recorded_evidence_ids` 变为 `["LOCK_ENTRY_K3_2106", "LOCK_EXIT_S_2114"]`。
- 决策 28 `{"target_id": "footprint_trail", "tool": "investigate"}` → `TARGET_NOT_VISIBLE`（人在 V）；决策 29 移到 S，决策 30 又移回 V，**从未在 S 调查**，30 决策结束。
- 首次偏离：决策 1 之后没有“到房间就调查”的纪律；23/30 步是 `MOVE_SUCCEEDED`。失败链：空转 → 证据链只到 2 条 → 从未提交。
- 重复证据说明：R0 与 R2 是同一失败模式的两份重复（16/23 次 move、10/4 次 `TARGET_NOT_VISIBLE`、都只记录 2 条锁日志）。**n=3 只能说明该模式可重复，不能区分个体差异与固定陷阱。**

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | E 策略规划错误（到达房间不调查、无目的往返） | C 接口误导（`TARGET_NOT_VISIBLE` 不指出正确房间） | 高 | 决策 1/3/19/30；16 move、10 次 `TARGET_NOT_VISIBLE` |
| R1 | E 策略规划错误（在 A 提交而非 H；未在 A 记录登记） | B 公开信息不足（人物/路径枚举未公开）+ C 错误码优先级把两类错误合并成 `INVALID_LOCATION` | 高 | 决策 21/22；原始 Trace 的 claims 值 `Celine`/`S-V` |
| R2 | E 策略规划错误（H↔V 空转，23/30 步在移动） | I 证据不足（30 步内只看到一类来源） | 高 | 决策 1–24、25–30 |

没有 H（采样/运行异常）：三局均 30/30 决策、0 非法形状动作、0 provider 错误。D（预算）不成立：16–20 步足够成功。

## 9. 标签

- `MEASUREMENT_VALID`（有条件）：公开启发式 18 步成功、最短路 16 步成功、Oracle 20 步成功，说明构念在预算内可实现。
- `INTERFACE_BLOCKED`（部分，非全图）：`person_id` 与 `entry_path_id` 的合法拼写未公开，且“引用必须已 record”只在实现里；没有这些知识，模型只能靠 0 tick 的 `INVALID_ACTION_ENUM` 盲试和一次性终局提交。证据：`map28.py:127-128`、`:330`，`prompt` 词表（`runs/v9/evidence/MAP-28.json.vocabulary`）。
- 不标 `BUDGET_BLOCKED`：预算 30 ≫ 最短路 16。
- 不标 `RULE_DEFECT`：规则自洽，`ACCEPTANCE` 与 fixture 覆盖了单源拒绝与矛盾拒绝。

## 10. 最小可证伪修复（无证据不修改）

旧规则/旧公开信息：不改规则。候选修复全部是“补公开信息”，且**只提候选，本批不落地**。

- **候选 A（首选）**：在 MAP-28 的公开词表补两行——`person_id ∈ ADA|BASIL|CELINE`、`entry_path_id ∈ BANQUET_H_V|GUARD_G_V|SECRET_S_V`，并在 `submit` 描述里写明“引用必须是已 `record` 的证据”。证据：R1 决策 22 用 `Celine`/`S-V`；`no_record` 消融证明未记录引用被判单源。预期变化：枚举类 `INVALID_ACTION_ENUM` 从“盲试”变为“可读”，单次终局的隐藏前置条件消失。能力构念不变（仍考四字段双来源），只是去掉与构念无关的拼写猜谜。
- **候选 B（次选）**：调整 `_submit` 的错误优先级——先解析 claims（0 tick 的 `INVALID_ACTION_ENUM`），再判位置。证据：R1 决策 22 在 A 提交，`INVALID_LOCATION` 掩盖了两个枚举错误。预期变化：模型能在不损失 tick 的前提下先修枚举；反例风险：会多一次“位置错误但枚举合法”的提交尝试（仍 1 tick，不消耗唯一提交），不改变成功条件。
- 反例与回归风险：候选 A 会提高所有人（含随机基线）的成功上限，需要在 Batch 6 用同一 20 seed 随机基线复核“是否变成随机可过”；若随机成功率显著上升，则本图区分度下降，应改为“只公开路径枚举、保留人物推断”。
- 若不做任何修改：本图仍可作 `MEASUREMENT_VALID`（有 16 步可复现策略），但“模型失败”中混有一部分与构念无关的拼写噪声，报告时必须分开。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-28.json`：

| 基线 | 结果 | 决策 | 主指标 |
|---|---|---|---|
| Oracle `evidence_first_two_source` | `scenario_success` | 20 | 4/4、4/4、0、0 |
| legal_random（20 seeds） | 0/20 成功，全部预算耗尽 | 30×20 | —（未提交） |
| public_heuristic | `ALL_CLAIMS_SUPPORTED_AND_CORRECT` | 18 | 4/4、4/4、0、0 |
| ablation `no_record` | `CASE_REJECTED` | 13 | 0/4、0/4、1、0 |
| 补充：无访谈最短路 | `ALL_CLAIMS_SUPPORTED_AND_CORRECT` | 16 | 3/4、4/4、0、0 |

**独立复算**（不复用 `v7` extractor，不读 `judge_state`）：从 `runs/v9/baselines/MAP-28.json` 的 `public_heuristic.actions` 取最终 `recorded_evidence_ids` 与唯一一次 `submit`，按 `worlds/v4/MAP-28/evidence_or_rules.yaml` 的来源类别与取值约束重算：

1. 覆盖率 = `|recorded ∩ {KEY_REGISTER_K3_CELINE, LOCK_ENTRY_K3_2106, PRINT_C7_ROUTE_SV, WITNESS_BASIL_S_WINDOW}| / 4` = 4/4 = 1.0（extractor 同值）。
2. 四栏满足度：`person_id` 来源类别 `{documentary_register, instrument_log, physical_trace}`；`entry_path_id` `{instrument_log, physical_trace, testimony}`；`entry_time`、`exit_time` 同为 `{instrument_log, physical_trace, testimony}` → 4/4（extractor 同值）。
3. 消融 `no_record`：同一算法得 0 个类别、0/4 满足（extractor 同值）。
4. V8 R0/R1/R2 的覆盖率用同一定义复算：R0 记录 `{LOCK_ENTRY_K3_2106, LOCK_EXIT_S_2114}` 命中 1 件关键证据（1/4）；R1 记录 4 条命中 `{LOCK_ENTRY_K3_2106, PRINT_C7_ROUTE_SV, WITNESS_BASIL_S_WINDOW}`（3/4）；R2 记录 2 条命中 1 件（1/4），与 judge 的 1/4、3/4、1/4 完全一致。

区分度结论：`key_evidence_coverage` 能区分 Oracle / 启发式 / 消融 / 随机四类；`timeline_constraint_satisfaction` 只能区分“成功提交”与“未提交或错”，属于**单点门槛**而非连续信号，不构成 `LOW_DISCRIMINATION`（因为另有覆盖率作连续过程量）。

## 12. V9 状态

**`NEEDS_REDESIGN`，P1。** 理由：构图、规则与预算都成立（16/18/20 步可复现成功），但公开信息里缺 `person_id`/`entry_path_id` 枚举与“引用必须已记录”的前置条件，导致 0/3 的失败中混入与构念无关的拼写猜谜；补公开信息（候选 A/B）后本图可直接升为 `VALIDATED`。
