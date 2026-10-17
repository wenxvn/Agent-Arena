# MAP-08 定稿：看不见的裂缝

| 字段 | 值 |
|---|---|
| 世界 | abyss |
| 难度 | 中等 |
| 条件 | `hypothesis_table` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `14daf6879328c3c86e2280809b061b1f11501ede87f9f8c98910440120d09050` |
| rule_hash | `9a3827c2f5fe75bd6368e98035fde35a2048fedb73d0f150bbc64eda13e6ddd2` |
| prompt_hash | `6ce88b04d9faa155804a6c8b116f217f9820e8f43a74d306283676e569ad6390` |
| metric_schema_hash | `f89bbd9503fe2a7e16fa6188e727df26fda47f0af794fe31fe4ba9d21c5113df` |
| oracle_hash | `b086a8e9d0b7b3ccf4388a0f39e300e7a0640eeacf4f31d4affda7054b8c60a8` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

本图测 Agent 如何选择能最大幅度缩小故障假设集合的压力实验，并判断何时证据足够、何时应停下实验去修复。三个候选点水位曲线、传感器底噪和房间描述起初完全相同；唯一可分辨来源是主动执行 X/Y 测试。

运行时的状态机、动作前置与失败码见本文件第 4–5 节。

## 2. 与同世界另两图的区别

- **MAP-07**（简单）：本图与同世界另两图的机制差异：MAP-08 用主动测试缩小隐藏漏点的假设集合，MAP-09 是漏水/电量/供氧/通信的跨系统资源耦合；本图没有行走图，Agent 始终在控制台 P 远程操作，因果难度来自“一个 tick 内可变水位按固定次序级联”以及单向回流 v4（C→A）——给 C 降压会把水送回 A，而不是排掉。
- **MAP-09**（困难）：本图与同世界另两图的机制差异：MAP-07 只有单一水路内部的顺序转移，水位直接可见、动作只改变水量；MAP-08 用主动测试缩小隐藏漏点假设集。本图没有隐藏故障位置，难点是同一 tick 内的资源循环——E-P 漏水会把泵房水推进动力舱并短路，抽水消耗刚好够发报的电量，断电只影响供氧线路而不回充电池，供氧稳定计数又决定能否发报。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`baseline_sensor_reading`, `current_core_water`, `current_tick`, `known_test_semantics`, `location`, `published_candidate_set`, `published_prior`, `sealant_count`, `test_results`, `visible_edges`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`location`, `map_id`, `sealant_count`, `sealed`, `seed`, `status`, `terminal_reason`, `test_results`, `tick`, `true_leak`, `water`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `inspect`：`target_id`
- `interact`：`operation`, `target_id`
- `move`：`edge_id`
- `wait`：`turns`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：复用 V4 规则：压力测试耗 2 tick；泄漏水位逐 tick 上升；错误密封剂立即失败。

- 成功码：`LEAK_SEALED`
- 失败码：`SEALANT_MISUSED`, `CORE_WATER_LIMIT_EXCEEDED`
- 机制失败路径：
  - 错误密封剂 → `SEALANT_MISUSED`
  - 不测试直接修 → `diagnosis_accuracy=0`
  - 等待过久 → `CORE_WATER_LIMIT_EXCEEDED`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map08.candidate_reduction` | primary | higher_is_better | (N_initial - N_final) / N_initial | 初始公开候选数 N_initial | known_test_semantics 无法解析 → UNAVAILABLE；无测试 → 0（合法） | 过程量不因终局失败而删除，只标注同局 outcome |
| `map08.diagnosis_accuracy` | primary | higher_is_better | 1 if repair_leak(target)==true_leak else 0 | 提交过 repair_leak 的 episode；未提交则 N/A | 无 repair 动作 → N/A；无离线真漏 → UNAVAILABLE | episode 因 step-limit 截尾 → CENSORED（未观察到结论性修复） |
| `map08.information_gain_bits` | diagnostic | higher_is_better | Σ_t [H_t - H_{t+1}], H=log2|consistent candidates|（本实例等先验） | 实际执行的合法测试数 | 签名表不可解析 → UNAVAILABLE；0 次测试 → 0 bit | 按已发生事件计算，不因截尾删除 |
| `map08.legal_action_rate` | diagnostic | higher_is_better | accepted decisions / submitted decisions | 模型提交的 decision 数；prefix 不计 | 0 次决策 → N/A | 按已提交决策计算 |
| `map08.peak_core_water` | guardrail | lower_is_better | max_t(current_core_water_t) | episode | 无任何观测 → UNAVAILABLE | 截尾时按已观察值计算并标注 CENSORED |
| `map08.tests_run` | diagnostic | lower_is_better | count(legal pressure_test_X/Y) | episode | 无 → 0 | 按已发生事件计算 |
| `map08.wrong_repair` | guardrail | lower_is_better | 1 if terminal_reason==SEALANT_MISUSED else 0 | 提交过 repair 的 episode | 未提交 repair → N/A | 截尾且未修复 → CENSORED |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：MAP-08-solver-success（5 步）
- 手算 fixture：x-first-success（5 步）, y-first-boundary-7-0（10 步），补充冻结后失败用例 `core-water-limit-boundary`（13 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-08` → `MAP-08: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | decision_budget_reached | False | None | 38 | 0.02169032 | `V8-MAP-08-R0-20261017T080241Z-fe1a5b93` | `candidate_reduction`=0.0; `information_gain_bits`=0.0; `legal_action_rate`=0.105263; `peak_core_water`=3.0 |
| 1 | decision_budget_reached | False | None | 38 | 0.01801644 | `V8-MAP-08-R1-20261017T080618Z-4b45160b` | `candidate_reduction`=0.0; `information_gain_bits`=0.0; `legal_action_rate`=0.157895; `peak_core_water`=4.0 |
| 2 | decision_budget_reached | False | None | 38 | 0.01830844 | `V8-MAP-08-R2-20261017T081119Z-446e53fc` | `candidate_reduction`=0.0; `information_gain_bits`=0.0; `legal_action_rate`=0.157895; `peak_core_water`=4.0 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

复用 V6 `map08_l3_original`；V7 已确认的天花板保留，V8 不为降低通过率改规则。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `7/7`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
