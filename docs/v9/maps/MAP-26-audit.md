# MAP-26 逐图审计：失败的维修计划

> 本文件由 V9 Batch 1 依据 Trace、证据包、源码与本次离线复算重新推导；不复制 `docs/v8` 结论，不声称人工审核。V8 文件保持只读。

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-26 失败的维修计划 / lunar / 中等 |
| condition | `free_diagnosis`（V6 侧映射为 `feedback_mode="full"`） |
| `rule_hash` | `a0de5a1957c0a82cff7636ba86f8ce513c85d7ec30edee810885dcd882cc595e` |
| `scenario_hash` | `3a292dd03e01fb8fdd588e2b08dbdc3cf0b08cf975e3633e37750d9f4d612c0c` |
| 决策预算 | 38 |
| V8 三局 | 0/3 成功；`decision_budget_reached` ×3；决策 38 / 38 / 38 |
| 主指标 | `legal_action_rate` = 15/38（0.394737）、17/38（0.447368）、14/38（0.368421）；`tests_run` = 0 / 0 / **4**；`spares_remaining` = 2 / 2 / 2；`repair_success` = 0 / 0 / 0；`diagnosis_accuracy`、`recovery_latency`、`repeat_error_rate` 三局全 `not_applicable` |

数据来源：`runs/v9/evidence/MAP-26.json`、`docs/v9/run-index.csv`、`runs/v9/baselines/MAP-26.json`、`docs/v8/maps/MAP-26-final.md`、`worlds/v4/MAP-26/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v4/map26.py`、`src/agent_arena/worlds/scenario_v8/v4_adapter.py`、`src/agent_arena/worlds/scenario_v8/adapter_cases.py`、`src/agent_arena/v8/prompts.py`、`src/agent_arena/v7/metrics/map26.py`、`src/agent_arena/v9/policies/world_lunar.py`。

## 1. 能力构念

**一句话**：面对同一个“通信中断”报警、一段**不足以定位故障**的历史日志和三个可重复的确定测试，能否用有限的证据把 3 个候选部件收敛到 1 个，并在只剩 2 枚备件的预算内完成更换与重启。

- 成功行为：`communication_restored=true` 且至少剩 1 枚未安装备件（`ALL_OBJECTIVES_COMPLETE`）。
- 明确反例：不看任何测试就盲换两个不同部件（F01）、同一错误部件反复重试（F02）、无视两条已确定的阴性读数（F03）——三条都以 `SPARES_EXHAUSTED` 结束。
- 递进位置：本图是 lunar 三图里唯一的**隐藏故障 + 反馈纠错**题。MAP-25 的故障固定且公开（检查→诊断→维修），MAP-27 没有隐藏故障（中继 OFFLINE 是公开状态），只有资源与路线取舍。本图只考“证据 → 假设 → 更换 → 反馈 → 回滚/改测”的闭环。

## 2. 机制与因果链

起始状态（tick 0）：`current_node=T`、`alert=COMMUNICATION_LOST`、`log_readings=[]`、`test_readings={}`、`installed_candidates={}`、`spare_units_at_B=2`、`carried_spare_units=[]`、`communication_restored=false`。隐藏侧：seed 0 的 `fault_part=antenna_coupler`。

必需观察 → 关键决策 → 立即后果 → 终局：

1. `move D` 进入诊断室；`read_log(log_id=COMM_LOSS_LAST_TRANSMIT)` 只得到 `TRANSMIT_SURGE_BEFORE_LINK_LOSS_POWER_OR_DOWNSTREAM`——**电源与下游都解释得通**，单独不能定位。
2. `test(test_id)` 三项各返回 seed 稳定的类型化读数：`bus_load→BUS_VOLTAGE_STABLE/DROOP`、`antenna_loopback→ANTENNA_LOOPBACK_OPEN/OK`、`software_checksum→IMAGE_CHECKSUM_MISMATCH/VALID`。一正两负即定位故障。
3. `move A → move B → take_spare(part_id)`：消耗 1 枚库存、占 1 格随身（容量 2）。
4. `move A → replace(part_id)`：换对部件返回 `SELECTED_COMPONENT_REPLACED_RESTART_REQUIRED`；换错返回 `*_SELF_TEST_OK_LINK_STILL_DOWN`，**消耗 1 枚备件**，且同件第 n 次重试耗时 `1+n`。
5. `rollback` 可把错误件退回随身并恢复原槽位，但**不退 tick、不清重试计数**。
6. `restart`：只有故障件在位才 `COMMUNICATION_RESTORED`；此时若未安装备件 ≥1 才算成功，否则 `SPARES_EXHAUSTED`。

- 可绕过核心机制的动作：**没有**。`restart` 需要故障件在位；备件耗尽且未恢复即失败。`read_log` 可跳过（它只是模糊线索），但 `test` 不能全省——3 候选、2 备件，盲换最多只能覆盖 2 个假设。
- 机制是否在三条真实轨迹中实际触发：**否**。三局共 0 次成功 `test`（`test_readings` 始终为 `{}`），0 次 `replace`，`spares_at_B` 始终为 2；R1 的 1 次 `take_spare(part_id="SPARE_1")` 直接 `INVALID_PART_ID`。核心链路“测试→取件→更换→反馈→回滚/重启”一次都没激活。
- 触发所需最小动作数：**9**（`move D` + 2 个测试 + `move A` + `move B` + `take_spare` + `move A` + `replace` + `restart`）。V6 solver 的 `MAP-26-solver-success` 正是 9 步，finish tick 9，`tests_run=2`、`diagnosis_accuracy=1`、`spares_remaining=1`。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `current_node` / `current_tick` / `alert` | 是（Observation） | tick 0 起 | 是 |
| `spare_units_at_B` / `carried_spare_units` / `installed_candidates` | 是（Observation） | tick 0 起 | 是（能看到只剩 2 枚） |
| `log_readings` / `test_readings` | 是（Observation） | 执行后追加 | 是（读数一到手就能定位） |
| `communication_restored` / `last_action_error_code` | 是（Observation） | tick 0 起 / 每次动作后 | 是 |
| 3 个节点名 `D/A/B` | 是（`_VOCABULARY["MAP-26"]`） | 每步 | 是 |
| 动作名与字段形状 | 是（prompt 动作契约） | 每步 | 形状可提交，但**取值域缺失** |
| **`log_id` 的具体取值**（`COMM_LOSS_LAST_TRANSMIT`） | **否** | 无任何公开来源 | 否——`worlds/v4/MAP-26/map_spec.yaml` 第 53 行有，运行时未暴露 |
| **`test_id` 的 3 个取值**（`bus_load` / `antenna_loopback` / `software_checksum`） | **否** | 无 | 否——`map_spec.yaml` 第 54 行有，词表只写 `test(test_id)` |
| **`part_id` 的 3 个取值**（`power_regulator` / `antenna_coupler` / `software_image`） | **否** | 无 | 否——`map_spec.yaml` 第 32 行有，词表只写 `part_id` |
| 错误更换后的部件自检反馈（full 模式） | 只有成功执行一次 `replace` 后 | 换错之后 | 不能事前获得；而 `replace` 又需要 `part_id` |
| 同件重试耗时 `1+n`、回滚不退 tick/计数 | 否 | 只能由耗时与反馈反推 | 不影响可解性，但对预算规划重要 |
| 故障件真值（`antenna_coupler`） | 否 | — | 否（这是本图要测的隐藏量） |
| `judge_state`（`fault_part`、`failed_by_part`、`seed`） | 否 | — | 否 |
| Oracle 路径/用例 | 否 | — | 否 |

补充事实：`free_diagnosis` 在 `_CONDITION_NOTES` 里是公开的——“本条件要求从初始状态自主诊断，测试与维修按当前公开反馈选择。” 但该条件**只说明“要诊断”，没有给出任何可提交的字符串**。

## 4. 可解性与可观察性

- Oracle：1 个用例（`MAP-26-solver-success`，来自 V6 solver `solve("map26_l1_antenna_fault")`，经 V8 adapter 重放），9 动作，`scenario_success / ALL_OBJECTIVES_COMPLETE`，`tests_run=2`、`diagnosis_accuracy=1`、`spares_remaining=1`。`runs/v9/baselines/MAP-26.json` 记 `oracle_ok=1 / oracle_cases=1`。
- **仅凭公开信息是否存在可执行策略：不存在；但只要允许脚本基线编码地图设计常量，就存在。** 三个参数域（`log_id`、`test_id`、`part_id`）在整局公开面里没有任何一个合法取值：
  - 初始 Observation 只有 `current_node=T`、`alert=COMMUNICATION_LOST` 与空读数；
  - `test_readings` 的键只有在**成功执行测试后**才出现，而执行测试又需要合法的 `test_id`——循环依赖；
  - `installed_candidates` 同理，需要先成功 `replace`。
- 两个实证（同一 `observation` 契约、同一预算 38）：
  1. **纯公开面探测版**（本文件 20:59 之前的 `Map26Heuristic`）：把 Observation 中出现过的字符串当作 `log_id`/`test_id`/`part_id`，38 决策全部被拒（`legal_action_rate=1/38`），`tests_run` 被记成 9 而 `test_readings={}`（一次测试都没执行），`repair_success=0`。这说明“只靠公开字符串”不可解。
  2. **编码设计常量版**（当前 `Map26Heuristic`）：`log_id=COMM_LOSS_LAST_TRANSMIT`、三个 `test_id`、三个 `part_id` 来自 `worlds/v4/MAP-26/map_spec.yaml`，路线 T→D→A→B 来自公开词表与 `move` 探测。结果 **11 决策成功**：`read_log` 1 次 + 三个 `test`（`BUS_VOLTAGE_STABLE` / `ANTENNA_LOOPBACK_OPEN` / `IMAGE_CHECKSUM_VALID`）+ 取 `antenna_coupler` + `replace` + `restart`，`repair_success=1`、`diagnosis_accuracy=1`、`spares_remaining=1`、`legal_action_rate=11/11`。
- 结论：**公开面标 `INTERFACE_BLOCKED`，但地图本身可解且只需 11 步**。失败不是预算（Oracle 9、脚本 11）也不是规则（Oracle/脚本都通过），而是三个必需字符串没有公开来源；脚本基线之所以成功，是因为它使用了设计常量，这条必须在报告里与“模型能力”分开。

## 5. 预算可行性

| 策略 | 决策数 | 终局 | 关键指标 |
|---|---|---|---|
| Oracle `MAP-26-solver-success` | 9 | `ALL_OBJECTIVES_COMPLETE` | tests 2、诊断 1、余备件 1、合法率 1.0 |
| 公开启发式 `Map26Heuristic`（编码设计常量） | **11** | `ALL_OBJECTIVES_COMPLETE` | tests 3（均执行）、诊断 1、修复 1、余备件 1、合法率 11/11 |
| 消融 `no_diagnosis`（盲换后纠错） | **10** | `ALL_OBJECTIVES_COMPLETE` | tests 0、诊断 1、修复 1、`recovery_latency` 1 tick、`repeat_error_rate` 0/1、余备件 1 |
| 纯公开面探测版（已被替换，历史运行） | 38 | `decision_budget_reached` | tests_run 9（全部被拒）、余备件 2、合法率 1/38 |
| V8 R0 / R1 / R2 | 38 / 38 / 38 | `decision_budget_reached` ×3 | 合法率 0.395 / 0.447 / 0.368；tests_run 0 / 0 / 4；余备件 2 / 2 / 2 |

`legal_random`（20 seed）：0 成功，20/20 `decision_budget_reached`，`invalid_actions=0`，38 次决策**全部被拒**（`legal_action_rate=0/38`），`tests_run` 3–12（同样全是未执行的测试事件），`spares_remaining` 恒 2。

**判定：不是预算不够。** 正确路线 9 步（Oracle）/ 11 步（脚本，多跑一个测试与一次日志），预算 38；V8 与纯公开探测版都用了 38 步却一次有效动作都没做成。38 步里能做 2–3 次完整“测试→取件→更换→重启”还有富余，真正缺的是“能提交什么字符串”。

## 6. 指标

| 指标 | 计算事件 | 分母 | 三局取值 | 缺失/截尾 |
|---|---|---|---|---|
| `map26.repair_success` | 终局 `communication_restored` | episode | 0 / 0 / 0 | 三局 valid |
| `map26.diagnosis_accuracy` | 最后一次 `replace` 的 `part_id == fault_part` | “提交过 replace 的 episode” | N/A / N/A / N/A | 三局都未提交 `replace` → **真分母 0**，不是投影口径 |
| `map26.recovery_latency` | 首个错误反馈后到首个有效调整的 tick 差 | “至少发生一次错误替换的 episode” | N/A / N/A / N/A | **真分母 0**（没有任何错误替换反馈） |
| `map26.repeat_error_rate` | 同件重复错误更换 / 错误更换总数 | “错误替换尝试数；0 则 N/A” | N/A / N/A / N/A | **真分母 0** |
| `map26.spares_remaining` | `spare_units_at_B + len(carried_spare_units)` | episode | 2 / 2 / 2 | valid |
| `map26.tests_run` | `count(test)` | episode | 0 / 0 / **4** | valid，但见下 |
| `map26.legal_action_rate` | 被接受决策 / 提交决策 | 模型决策数 | 0.394737 / 0.447368 / 0.368421 | valid |

- 三条 N/A 的成因已逐条核实：`src/agent_arena/v7/metrics/map26.py` 在“没有 replace / 没有错误反馈 / 没有错误替换”时返回 `MetricValue.not_applicable`，V8 侧 `project_metrics()` 走 `metric_values()` 分支，原样保留 `not_applicable`。**不是** `v8/metrics.py::_empty_status` 把 `censored` 降级成 N/A 的那类投影问题（该问题在本图不成立）。
- **未通关仍有意义的连续主指标**：`legal_action_rate` 是唯一三局可比的连续量。它能区分“全拒”（随机/启发式 0–1/38）与“会移动、会重启”（V8 15–17/38），但**不测能力**——它测的是“有多少决策撞在接口缺口上”。
- **`tests_run` 口径缺陷（事实）**：R2 的 4 次 `test` 全部返回 `INVALID_LOCATION`（决策 19 在 A、27 在 A、29 在 B、37 在 A），`test_readings` 始终为 `{}`；指标却记 `tests_run=4`。原因是 `map26.py` 的 `result["map26.tests_run"] = counted(..., sum(1 for event in record.events if event.tool == "test"))` 只按工具名计数，不检查结果码。已替换的纯公开探测版把同一缺陷放大到 `tests_run=9`（9 次全是 `INVALID_TEST_ID`/`INVALID_LOCATION`），随机基线 3–12 亦是如此。当前脚本版 3 次 `test` 都返回 `TEST_COMPLETED:*`，`tests_run=3` 与执行数一致。
- **`diagnosis_accuracy` 分母缺陷（事实，代码阅读）**：`map26.py` 收集 `replaces` 时只要求 `event.tool=="replace"` 且 `part_id` 是字符串，**不检查动作是否被执行**。因此任何在错误节点提交 `replace(part_id=<任意字符串>)` 的策略都会被记成“换过错件”（0），而不是“从未更换”（N/A）；已替换的探测版在非 A 节点提交了 8 次 `replace`，正是这一路径。当前脚本版只在 A 成功 `replace` 一次，`diagnosis_accuracy=1` 不受影响。
- **区分能力**：Oracle（repair 1、tests 2、备件 1）、脚本版（repair 1、tests 3、备件 1）、消融（repair 1、tests 0、`recovery_latency` 1）与随机/探测版（repair 0、备件 2）能区分；`tests_run` 与 `recovery_latency` 能把“诊断后维修”与“盲换后纠错”分开。但 V8 三局因接口缺口停在同一点，对本图的构念仍是 `LOW_DISCRIMINATION`（模型侧无法产生有效 `test`/`replace`）。
- 文档一致性补充：`adapter_cases._FIRST_FIXTURES["MAP-26"]["expect"]["recovery_latency"] = None`，而同一局在 V7 extractor 里的状态是 `censored`（`tests/test_v7_hand_traces.py` 第 800 行用 `_CEN` 断言）。V8 投影保留 `censored`；两处“都是没有数字”，但状态语义不同，建议 Batch 6 统一，不影响本次结论。

## 7. 三次轨迹归因

### R0（`V8-MAP-26-R0-20261017T101026Z-5011be58`，38 决策，`decision_budget_reached`）

- 决策 1 `{"tool":"read_log"}` → `INVALID_LOCATION`；观察变化 `{"last_action_error_code":"INVALID_LOCATION"}`。
- 决策 6 `{"tool":"move","to":"D"}` → `MOVE_SUCCEEDED`；观察变化 `{"current_node":"D","current_tick":1,"last_action_error_code":null}`。
- 决策 7 `{"tool":"read_log"}` → `INVALID_LOCATION`；观察变化 `{"last_action_error_code":"INVALID_LOCATION"}`（**已经在 D，仍然 `INVALID_LOCATION`**）。
- 决策 12 `{"tool":"move","to":"B"}` → `MOVE_SUCCEEDED`；观察变化 `{"current_node":"B","current_tick":3,"last_action_error_code":null}`。
- 决策 38 `{"tool":"move","to":"D"}` → `MOVE_SUCCEEDED`；末态 `current_node=D`、`current_tick=15`、`spare_units_at_B=2`、`test_readings={}`。

首次偏离：决策 1——没有提供 `log_id` 就调用 `read_log`；契约里 `read_log` 的形状是 `{"tool","log_id"}`。
失败链：缺参数 → 环境返回 `INVALID_LOCATION`（而不是“缺字段 / 日志 id 不对”）→ 模型判断“位置不对”→ 全图游走 T/D/A/B → 19 次 `read_log` + 19 次 `move` → 预算耗尽。全程没有 `test`，也没有 `take_spare`。
替代解释：这不是“不会诊断”，而是**无法表达诊断**。模型确实在找日志、也确实到了 D；它缺的是 `COMM_LOSS_LAST_TRANSMIT` 这个字符串。

### R1（`V8-MAP-26-R1-20261017T101301Z-dfe20208`，38 决策，`decision_budget_reached`）

- 决策 3 `{"tool":"move","to":"D"}` → `MOVE_SUCCEEDED`；观察变化 `{"current_node":"D","current_tick":1,"last_action_error_code":null}`。
- 决策 4 `{"tool":"read_log"}` → `INVALID_LOCATION`；观察变化 `{"last_action_error_code":"INVALID_LOCATION"}`。
- 决策 11 `{"tool":"restart"}` → `RESTART_LINK_STILL_DOWN`；观察变化 `{"current_tick":5,"last_action_error_code":null}`（在 A 空手重启）。
- 决策 15 `{"tool":"take_spare","part_id":"SPARE_1"}` → `INVALID_PART_ID`；观察变化 `{"last_action_error_code":"INVALID_PART_ID"}`。
- 末态 `current_node=A`、`current_tick=17`、`spare_units_at_B=2`、`carried_spare_units=[]`。

首次机制相关偏离：决策 15 的 `part_id="SPARE_1"`——模型**自己编了一个占位符**。这是“参数词表缺失”最直接的证据：它知道要去 B 取备件，但没有任何合法零件名可用。（更早的偏离是决策 1 的 `read_log` 缺 `log_id`。）
失败链：缺 `part_id` → 唯一一次取件被拒 → 无法 `replace` → `restart` 只能得到 `RESTART_LINK_STILL_DOWN` → 余下 23 步又回到读日志/移动。
替代解释：这一局同时证明“模型理解了备件机制”（它先 `restart` 再 `take_spare`），失败点纯粹在命名接口，不在规划。

### R2（`V8-MAP-26-R2-20261017T103232Z-16e3d421`，38 决策，`decision_budget_reached`，`tests_run=4`）

- 决策 8 `{"tool":"move","to":"D"}` → `MOVE_SUCCEEDED`；观察变化 `{"current_node":"D","current_tick":1,"last_action_error_code":null}`。
- 决策 19 `{"tool":"test"}` → `INVALID_LOCATION`；观察变化 `{}`（在 A，且没有 `test_id`）。
- 决策 29 `{"tool":"test"}` → `INVALID_LOCATION`；观察变化 `{"last_action_error_code":"INVALID_LOCATION"}`（在 B）。
- 决策 37 `{"tool":"test"}` → `INVALID_LOCATION`；观察变化 `{"last_action_error_code":"INVALID_LOCATION"}`。
- 末态 `test_readings={}`，但 `map26.tests_run=4`。

首次偏离：决策 19——`test` 不带 `test_id`。此后 15 次 `read_log` + 19 次 `move` 与 4 次 `test` 交替，全部被拒。
失败链：缺 `test_id` → `INVALID_LOCATION` 被误读为“位置不对” → 在 A/B/D 反复试 `test` → `tests_run` 被记成 4 → 预算耗尽。
替代解释：本局是“错误码误导”的教科书案例：同一动作在 D（正确房间）与 A/B（错误房间）都返回**完全相同**的 `INVALID_LOCATION`，模型没有任何信号能区分“换房间”与“补参数”。
**重复证据有限**：三局结构相同（读日志 + 游走），差异只是 R1 多了一次 `restart`/`take_spare`、R2 多了 4 次 `test`。n=3 不能区分个体差异与固定陷阱；但三局都没有产生任何测试读数或备件消耗，说明这是**固定的接口天花板**，不是采样波动。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | B 公开信息不足：`log_id`/`test_id`/`part_id` 三个取值域完全未公开 | C 接口误导：缺参数返回 `INVALID_LOCATION` | B 高 / C 高 | 决策 1、7、38；`_VOCABULARY["MAP-26"]`；`map26.py:140-147` |
| R1 | B（`part_id` 无词表，模型只能编 `SPARE_1`） | C（`INVALID_PART_ID` 不提示合法集合） | B 高 / C 高 | 决策 11、15 |
| R2 | B（`test_id` 无词表） | C（同一 `INVALID_LOCATION` 同时表示“错地点”和“错/缺参数”）；M 指标（`tests_run` 记 4） | B 高 / C 高 / M 高 | 决策 19、29、37；`map26.py` tests 计数 |

排除：A（规则自洽，Oracle 9 步通过；`fault_part` 正确隐藏）、D（预算 38 vs 需要 9）、E（模型三次都主动寻找日志/备件/重启，规划方向正确）、F（备件一枚未动）、H（0 schema 非法、0 provider 错误）、I（证据完整）。

## 9. 标签

- `INTERFACE_BLOCKED`：三个必需参数域在公开面没有任何合法取值，且 `map_spec.yaml` 里明明写着 `log_id: COMM_LOSS_LAST_TRANSMIT`、三个 `test_id`、三个 `part_id`，只是没有进入 prompt/Observation。脚本基线必须编码这些常量才能在 11 步内成功。
- `MEASUREMENT_VALID`（限定）：一旦允许脚本使用设计常量，构念是可测的——Oracle 9 步、脚本 11 步、消融 10 步都能通关，`tests_run`/`recovery_latency` 可区分诊断与盲换。它不适用于“只给模型公开面”的当前 V8 prompt。
- `METRIC_DEFECT`：`tests_run` 统计被拒的 `test`（R2 的 4 次全部未执行）；`diagnosis_accuracy` 的分母把被拒的 `replace` 也算作“提交过更换”。
- `INCONCLUSIVE`：本图的核心构念（错误归因与自我纠错）在三局里从未被激活，`diagnosis_accuracy`/`recovery_latency`/`repeat_error_rate` 全 N/A，无法据此判断模型能力。
- 不选 `BUDGET_BLOCKED`（9–11 vs 38）、不选 `RULE_DEFECT`（规则与 Oracle、脚本基线均正常）。

## 10. 最小可证伪修复（无证据不修改）

- 旧规则/旧公开信息：`_VOCABULARY["MAP-26"]` 只有 `read_log(log_id)；test(test_id)；take_spare(part_id)；replace(part_id)`；`_FIELD_NOTES` 对这三个字段回退成“按 Observation 类型”；adapter 不执行 `SHAPES` 校验（`V4MapAdapter.step` 直接转 `ScenarioV4Action`）；`adapter.title` 取不到 V4 场景标题，`map_docstring()` 取到的是 `"A V4 environment behind the V8 public contract."`。
- 证据与根因：R1 决策 15 的 `part_id="SPARE_1"`；R0/R2 在 D 仍得 `INVALID_LOCATION`；纯公开探测版 38 步 0 有效动作；编码设计常量的脚本版 11 步成功；Oracle 9 步。
- **候选 A（推荐，只补公开信息，不改规则）**：把设计规格里本来就公开的取值域写进 `_VOCABULARY["MAP-26"]`：`move(to): T|D|A|B`、`read_log(log_id): COMM_LOSS_LAST_TRANSMIT`、`test(test_id): bus_load|antenna_loopback|software_checksum`、`take_spare/replace(part_id): power_regulator|antenna_coupler|software_image`。**不泄漏故障件**（3 个候选仍在），只泄漏“有哪些可试的字符串”。预期：模型能真正进入测试与反馈环节；本图从测“猜字符串”回到测“诊断-反馈-回滚”。**该预期已有下界证据**：脚本版把这四个词表当作已知常量后 11 步通关；补公开信息不会让任务变简单（仍需自己跑测试定位故障）。
- **候选 B（接口一致性，不改规则）**：让 `V4MapAdapter.step` 先走 `accepts(action)`，缺字段/多余字段返回 `INVALID_ACTION_SCHEMA`；`read_log` 在 D 但 `log_id` 缺失时返回 `MISSING_LOG_ID` 一类可区分的码。预期：错误码不再把“缺参数”伪装成“错地点”。风险：`rule_hash`/旧 Trace 的 `INVALID_LOCATION` 序列会变化，必须新建 DCR 并重跑；对已冻结的 90 局只能只读重算。
- **候选 C（指标口径）**：`tests_run` 只统计结果以 `TEST_COMPLETED:` 开头的事件；`diagnosis_accuracy` 的 `replaces` 只收集**被执行**的 replace（结果不是 `INVALID_*`）。预期：R2 的 `tests_run` 回到 0，公开启发式的 `diagnosis_accuracy` 回到 N/A。风险：`metric_schema_hash` 变化，V8 历史值需只读重算；不影响胜负判定。
- **候选 D（prompt 元数据）**：给六张 V4 适配图提供真实 `title` 与一句话机制（当前 MAP-26 的系统提示是“本图机制：A V4 environment behind the V8 public contract.”）。这是纯文案修复，但它决定了模型是否知道“通信中断 + 三个候选部件”。
- 不建议：加备件、延长 38 步预算、把 3 个测试合并成 1 个、或把故障件写进 prompt。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-26.json`：

| 类别 | 结果 |
|---|---|
| Oracle | 1/1 成功（9 动作，`ALL_OBJECTIVES_COMPLETE`，tests 2、余备件 1） |
| `legal_random`（20 seed） | 0 成功；20/20 `decision_budget_reached`；38 次决策全被拒；`tests_run` 3–12（全未执行） |
| `public_heuristic` | **成功，11 决策**，`ALL_OBJECTIVES_COMPLETE`；tests 3（均执行）、`diagnosis_accuracy=1`、`repair_success=1`、余备件 1、合法率 11/11；`recovery_latency`/`repeat_error_rate` 为 N/A（无错误替换） |
| 消融 `no_diagnosis` | **成功，10 决策**；tests 0、`diagnosis_accuracy=1`、`repair_success=1`、`recovery_latency=1`、`repeat_error_rate=0/1`、余备件 1 |

独立复算（不使用 `map26.metrics()` 的 tests 计数）：

1. **执行过的测试数** = 结果以 `TEST_COMPLETED:` 开头的事件数。R2 的 4 次 `test` 结果全是 `INVALID_LOCATION` → 执行数 **0**，与 `test_readings={}` 一致；而指标给出 4。脚本版 3 次结果分别是 `TEST_COMPLETED:bus_load:BUS_VOLTAGE_STABLE`、`TEST_COMPLETED:antenna_loopback:ANTENNA_LOOPBACK_OPEN`、`TEST_COMPLETED:software_checksum:IMAGE_CHECKSUM_VALID` → 执行数 3，与 `tests_run=3` 一致。
2. **有效更换数** = 结果不是 `INVALID_*` 的 `replace` 事件数。三局 V8 均为 **0**（没有 `replace`）；脚本版 1 次 `SELECTED_COMPONENT_REPLACED_RESTART_REQUIRED`、消融版 2 次（1 次 `POWER_SELF_TEST_OK_LINK_STILL_DOWN` + 1 次 `SELECTED_COMPONENT_REPLACED_RESTART_REQUIRED`）。
3. **备件账**：初始 2，三局终局 2（`spare_units_consumed=0`）；脚本版与消融版终局 1（取 1 件并安装；消融临时取 2 件、`rollback` 收回 1 件，最终仍剩 1 件未安装）。
4. **Oracle 复算**：9 步、tick 9、`tests_run=2`（`bus_load` + `antenna_loopback` 两次真实 `TEST_COMPLETED`）、`spares_remaining=1`。与基线 JSON 一致。
5. **`recovery_latency` 复算（消融）**：首个错误反馈 `replace(power_regulator) → POWER_SELF_TEST_OK_LINK_STILL_DOWN` 的 `tick_after=7`，随后 `rollback → ROLLBACK_COMPLETED` 的 `tick_after=8` → 延迟 `8-7=1`，与 extractor 的 `1` 一致。

## 12. V9 状态

`NEEDS_REDESIGN`（P0）。理由：地图本身可解（Oracle 9 步、脚本基线 11 步、消融 10 步均成功），规则自洽、预算充裕，但 `log_id`/`test_id`/`part_id` 三个必需字符串在公开面完全缺失，导致三条真实轨迹连一次测试或更换都无法执行。脚本基线只能靠编码设计常量通关，不能当作“模型可解”的证据。最小修复是补公开词表（候选 A）与统一错误码（候选 B），不需要改规则、加预算或加备件。
