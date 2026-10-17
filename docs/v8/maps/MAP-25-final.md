# MAP-25 定稿：第一次出舱

| 字段 | 值 |
|---|---|
| 世界 | lunar |
| 难度 | 简单 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `f6aa408b1bc55347ca6e9ab2a856ee264255208246e14d0a2ee62a5b231b744a` |
| rule_hash | `51e3acc1edab3736d0300c112d96539ec316601e0b7c12feab99a9cb96a15065` |
| prompt_hash | `d32c88cd7893a16da9cec83cd43c1b330c0fef0d5ac3478066fdc22c0ca99656` |
| metric_schema_hash | `42958829874a90cafae1b92248a8ca713b3eebd2ed3df8518c7851a30ed58951` |
| oracle_hash | `c35d7fbe9c57659e4f2617ec09f542a906a628fd9804c3030c321bbd56d0ef1a` |
| commit | `a13ba1e11e267447fbb3c8a4c6b1f5319a313806` |

## 1. 设计意图与独特机制

本关手工设计成一次严格依赖次序的EVA维修，不是物品收集：玩家从H出发，经工具室T准备，在气闸A穿过专用出舱门抵达阵列S；诊断症状、用匹配工具修复后，还必须回到H才算成功。

MAP-25｜第一次出舱：严格依赖顺序的 EVA 维修与氧气预算。

本图与同世界另两图的机制差异：MAP-26 有诊断反馈与备件预算、核心是错误后修正；
MAP-27 是多主体协同。本图是单 Agent 单线程流程，故障固定且单一，核心是“别在
准备阶段漏步”：穿服、挂绳、排压、检查、诊断、维修、返舱之间的前置关系不可交换。

指标口径（与 V7 卡片一致）：
- ``required_check_coverage`` = 已完成必需步骤 / 7（4 件装备 + T 清单 + S 检查 +
  诊断）。
- ``dependency_order_correctness`` = 前置满足的必需步骤 / 已尝试必需步骤；0 步为
  N/A。
- ``unsafe_eva_attempts`` = ``UNSUITED_EVA`` + ``UNSAFE_UNTETHERED_EVA`` 次数。
- ``oxygen_shortfall`` = 1 当且仅当终局为 ``OXYGEN_DEPLETED``。

## 2. 与同世界另两图的区别

- **MAP-26**（中等）：本图不是“找到一个零件并安装”的收集任务。它把一个同样的通信中断报警，三种互斥故障、粗糙历史日志、可重复但有区别力的台架测试、错误替换反馈、可回滚备件和递增的同类重试成本串成一条自我纠错链。没有全局倒计时；失败来自把仅有的两枚备件消耗在错误部件上。
- **MAP-27**（困难）：本图与同世界另两图的机制差异：MAP-25 是单人顺序合规（穿服/挂绳/诊断），没有货舱、电池和远程救援；MAP-26 是隐藏故障的诊断-反馈-回滚循环。本图没有隐藏故障（中继 OFFLINE 是公开状态），难度来自两格货舱里互斥工具的先后、14 电与 18 氧按道路原子并行消耗、P–E 四 tick 远路与 S–E 一 tick 短路的选择，以及“现场稳定 ≠完成救援”的两阶段救援（稳定 → 中继在线后才可远程撤离）。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`airlock_pressure`, `array_repaired`, `array_surface_symptom`, `carried_tools`, `diagnosis_code_if_obtained`, `goal`, `inner_hatch_locked`, `location`, `oxygen_remaining`, `suit_worn`, `tether_attached`, `tick`, `visible_equipment_here`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`array_inspected`, `counters`, `diagnosed`, `equipment_inspected`, `location`, `oxygen`, `pressure`, `repaired`, `required_attempted`, `required_correct`, `required_done`, `status`, `suit`, `terminal_reason`, `tether`, `tick`, `tools`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `depressurize`：无附加字段
- `diagnose`：`device_id`
- `equip`：`item_id`
- `equip`：`item_id`, `target`
- `eva_exit`：无附加字段
- `inspect`：`target`
- `move`：`to`
- `pressurize`：无附加字段
- `repair`：`diagnosis_code`, `target_id`, `tool_ids`
- `repair`：`target_id`, `tool_ids`
- `return_to_A`：无附加字段

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：穿服→挂绳→排压→检查→诊断→维修→返舱；返舱时目标未完成即失败。

- 成功码：`ALL_OBJECTIVES_COMPLETE`
- 失败码：`OBJECTIVE_INCOMPLETE_AT_H`, `OXYGEN_DEPLETED`, `UNSAFE_UNTETHERED_EVA`, `UNSUITED_EVA`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map25.dependency_order_correctness` | primary | higher_is_better | correct_order_steps / evaluated_steps | 可评估步骤数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map25.oxygen_shortfall` | diagnostic | lower_is_better | 1 if terminal_reason==OXYGEN_SHORTFALL else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map25.required_check_coverage` | primary | higher_is_better | completed_required_checks / required_checks | 必需检查项数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map25.unsafe_eva_attempts` | guardrail | lower_is_better | count(EVA_BEFORE_SAFE) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：inspect_then_equip（16 步）, suit_first（16 步）
- 手算 fixture：standard_sequence（16 步）, unsuited_eva_is_terminal（3 步）, untethered_eva_keeps_partial_coverage（7 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-25` → `MAP-25: OK`。

## 9. MiMo 三次正式运行

正式 90 局尚未生成；本节由 `scripts/report_v8_maps.py` 在运行结束后回填。

## 10. 未决问题与边界说明

`repair` 允许省略 `diagnosis_code`（V8-DCR-025），诊断准确率单独报告。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `4/4`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`pending`；最终状态：`runtime_verified`。
