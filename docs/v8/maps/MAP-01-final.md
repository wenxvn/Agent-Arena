# MAP-01 定稿：破损的曙光号

| 字段 | 值 |
|---|---|
| 世界 | spaceship |
| 难度 | 简单 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `e130d30cf7b59738fbff1d7016cab5fe920bf376fb220f6bf0f7cabba92ed987` |
| rule_hash | `b0b4cf2c14e981f2ff4f561be50266f235e8e021fea00d01857ed2ceea7c248f` |
| prompt_hash | `65fb8d0bdc4d80d2da962ea4dde959a0932c3119ff6c69230bca5978a96dd4a3` |
| metric_schema_hash | `31c2795d2a3ac4e6f9cb8a623099ac4d17dba0a4a59bef2a8be39742daa26305` |
| oracle_hash | `753f601461a743c03b294d0c9c3997565c4b205b30d60aee8ab3d0e0f4c1f8e6` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

测量 Agent 是否先保护持续生命支持，再安排互斥电路、修补船壳，最后恢复主电源。成功不是“拿齐三个东西”：供氧、维修臂、动力母线之间有真实前置关系，错误上电会造成明确安全后果。

MAP-01｜破损的曙光号：生命支持、互斥供电与船壳修补的依赖规划。

## 2. 与同世界另两图的区别

- **MAP-02**（中等）：动作序号触发的泄漏事件与在线目标重排。
- **MAP-03**（困难）：五阶段里程碑与一次性远期代码召回。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`airlock_sealed`, `goal`, `hull_intact`, `inventory`, `location`, `main_bus`, `oxygen_output`, `oxygen_reserve`, `pressure_test`, `repair_arm`, `routed_branch`, `service_edge_open`, `visible_edges`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`confirmed`, `dependencies`, `hull_intact`, `inventory`, `location`, `main_bus`, `oxygen_off_ticks`, `oxygen_output`, `oxygen_reserve`, `pressure_test`, `violations`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `inspect`：`target`
- `interact`：`choice`, `target`
- `move`：`edge_id`
- `pickup`：`item_id`
- `wait`：`turns`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：每 tick 未供氧则扣氧气余量并累计断供；超过 3 tick 失败。修补、复位、压力测试各有前置。

- 成功码：`REPAIR_CONFIRMED`
- 失败码：`BUS_RESET_WITH_HULL_OPEN`, `OXYGEN_RESERVE_EXHAUSTED`, `OXYGEN_SUPPLY_INTERRUPTION_LIMIT`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map01.completion_ticks` | diagnostic | lower_is_better | terminal_tick if success else N/A | 成功局 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map01.dependency_satisfaction_rate` | primary | higher_is_better | completed_required_edges / required_edges | 必需边数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map01.dependency_violations` | diagnostic | lower_is_better | count(ILLEGAL_PREREQUISITE_ORDER) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map01.longest_oxygen_outage_ticks` | primary | lower_is_better | max consecutive ticks with oxygen_output=False | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map01.oxygen_guardrail_violations` | guardrail | lower_is_better | count(OXYGEN_RESERVE_EXHAUSTED) + count(OXYGEN_SUPPLY_INTERRUPTION_LIMIT) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：default（18 步）
- 手算 fixture：pickup_denied_without_oxygen（3 步）, four_tick_support_interruption_fails（4 步），补充冻结后失败用例 `bus_reset_before_hull_patch_fails`（3 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-01` → `MAP-01: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | failure | False | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 11 | 0.00758384 | `V8-MAP-01-R0-20261017T073248Z-ca460a38` | `dependency_satisfaction_rate`=0.666667; `dependency_violations`=1; `longest_oxygen_outage_ticks`=4; `oxygen_guardrail_violations`=1 |
| 1 | failure | False | BUS_RESET_WITH_HULL_OPEN | 22 | 0.00941168 | `V8-MAP-01-R1-20261017T073346Z-48162592` | `dependency_satisfaction_rate`=0.166667; `dependency_violations`=4; `longest_oxygen_outage_ticks`=3; `oxygen_guardrail_violations`=0 |
| 2 | failure | False | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 4 | 0.00158872 | `V8-MAP-01-R2-20261017T073606Z-b3547066` | `dependency_satisfaction_rate`=0.0; `dependency_violations`=0; `longest_oxygen_outage_ticks`=4; `oxygen_guardrail_violations`=1 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

`oxygen_off_ticks` 仍为私有；公开只给氧气余量，断供阈值需由失败归因推断。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
