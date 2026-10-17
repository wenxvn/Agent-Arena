# MAP-06 定稿：暴风眼

| 字段 | 值 |
|---|---|
| 世界 | lighthouse |
| 难度 | 困难 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `f7ed000d38c6c5d74b3d947bc314c3560c26ec71259d6eee930a38599b2ee9ac` |
| rule_hash | `2adb4f3322d07b95fb81113a52d0b3e2a818fd464ada905ad630ae5b8c0e508f` |
| prompt_hash | `bdcc3971b243c4284aea5d37db437ee248fc08a2b5ee16afb325e57744a8c123` |
| metric_schema_hash | `231eeb42db153e168379291687e3095002fa92fdd26ab71f399f2f4b30274c18` |
| oracle_hash | `48944ae9757caf5bda1259998416767872bac58af3e11487230eeaa6f382b751` |
| commit | `a13ba1e11e267447fbb3c8a4c6b1f5319a313806` |

## 1. 设计意图与独特机制

本图测“为了减少风险，要花多少时间换信息或准备防护”，而不是只看某一次猜中天气。天气由 seed 固定，预报在每个固定种子上也固定为对/错；期望值按预先定义的 seed 分布计算，不从单次结果推断能力。

MAP-06｜暴风眼：80% 条件预报、风险预算与加固决策。

## 2. 与同世界另两图的区别

- **MAP-04**（简单）：周期相位预测与短窗/长绕行的时序权衡。
- **MAP-05**（中等）：单路共享供电下的跨塔校准与窗口排程。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`deadline_tick`, `forecast_accuracy`, `forecast_queries`, `forecast_reading`, `goal`, `lamp_restored`, `location`, `prior_long`, `prior_short`, `risk`, `risk_budget`, `storm_shield`, `tick`, `visible_edges`, `weather_observable`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`forecast_queries`, `forecast_reading`, `high_risk_ticks`, `lamp_restored`, `location`, `risk`, `storm_shield`, `weather`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `inspect`：`target_id`
- `interact`：`operation`, `target_id`
- `move`：`edge_id`
- `wait`：`ticks`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：风暴按 tick 推进；加固与修复须在截止前完成；资源耗尽与截止失败分开。

- 成功码：`LAMP_RESTORED`
- 失败码：`REPAIR_DEADLINE_MISSED`, `RESOURCE_EXHAUSTED`
- 机制失败路径：
  - 风暴前未完成修复 → `REPAIR_DEADLINE_MISSED`
  - 加固/修复耗尽资源 → `RESOURCE_EXHAUSTED`
  - 长风暴不加固 → 灯室损坏

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map06.high_risk_exposure_ticks` | guardrail | lower_is_better | Σ ticks in high-risk window | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map06.observation_cost` | diagnostic | lower_is_better | query_count * 2 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map06.resource_exhausted` | diagnostic | lower_is_better | 1 if terminal_reason==RESOURCE_EXHAUSTED else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map06.task_success_rate` | primary | higher_is_better | completed_tasks / required_tasks | 必需任务数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map06.value_of_information` | primary | higher_is_better | loss(no_observation) - loss(with_observation) | 配对 episode 对 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：immediate_short（2 步）, harden_long（5 步）, forecast_short_correct（3 步）, forecast_long_correct（6 步）
- 手算 fixture：short_storm_direct_repair（2 步）, long_storm_repair_without_shield（2 步），补充冻结后失败用例 `deadline_missed_without_repair`（14 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-06` → `MAP-06: OK`。

## 9. MiMo 三次正式运行

正式 90 局尚未生成；本节由 `scripts/report_v8_maps.py` 在运行结束后回填。

## 10. 未决问题与边界说明

公开 `forecast_accuracy` 与先验，属“信息可用性”条件，不宣称纯推断能力。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`pending`；最终状态：`runtime_verified`。
