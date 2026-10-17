# MAP-04 定稿：潮汐密道

| 字段 | 值 |
|---|---|
| 世界 | lighthouse |
| 难度 | 简单 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `3cd4b7fafdaf0c9ffa1d487dffb7123bf5da2a968315e52db3de67bce5478050` |
| rule_hash | `88500e992c3bdd695f1c02e005e96c48739b0d147a24f284144847f52b53157d` |
| prompt_hash | `f2f87b80539c780946b341d5e82a514cb4ad8ac97ad3b81aead7a2042f4fe328` |
| metric_schema_hash | `9129f28178e46c6f7245dfacfef4749f35c91ddd8270e15fa350e4b37b467dfa` |
| oracle_hash | `211f7bf7d41e61bff5bc6c7c9c8381336f5ab804cc3513ccb61816c6df990fb2` |
| commit | `a13ba1e11e267447fbb3c8a4c6b1f5319a313806` |

## 1. 设计意图与独特机制

本图只测周期预测与跨动作时序。潮汐规则公开，Agent 需要根据当前相位推算能否进入和离开狭窄潮道；不加入随机天气或隐藏的相位变化。

MAP-04｜潮汐密道：周期相位预测与短窗/长绕行的时序权衡。

## 2. 与同世界另两图的区别

- **MAP-05**（中等）：单路共享供电下的跨塔校准与窗口排程。
- **MAP-06**（困难）：80% 条件预报、风险预算与加固决策。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`goal`, `inventory`, `lamp_lit`, `lamp_wick_fitted`, `location`, `open_phases`, `rescue_deadline_tick`, `tide_period`, `tide_phase`, `visible_edges`, `wick_location`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`crossing_attempts`, `crossing_successes`, `first_crossing_tick`, `high_tide_entries`, `inventory`, `lamp_lit`, `lamp_wick_fitted`, `location`, `tide_phase`, `wait_ticks`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `inspect`：`target`
- `interact`：`choice`, `target`
- `move`：`edge_id`
- `pickup`：`item_id`
- `wait`：`turns`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：潮汐相位按动作成本推进；`wait` 成本等于 turns；救援截止 tick 到达仍未点灯即失败。

- 成功码：`SIGNAL_LIT`
- 失败码：`RESCUE_SIGNAL_WINDOW_EXPIRED`
- 机制失败路径：
  - 错过救援窗口 → `RESCUE_SIGNAL_WINDOW_EXPIRED`
  - 高相位过桥 → `high_tide_entries` 护栏上升
  - 绕行耗时至截止 → 窗口过期

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map04.earliest_safe_crossing_delay` | primary | lower_is_better | actual_cross_tick - earliest_feasible_tick | 成功穿越的 episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map04.high_tide_entries` | guardrail | lower_is_better | count(HIGH_TIDE_ENTRY) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map04.stranded_ticks` | diagnostic | lower_is_better | Σ stranded_ticks + rollback_cost | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map04.wait_ticks` | diagnostic | lower_is_better | count(wait) + ticks waiting for tide window | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map04.window_hit_rate` | primary | higher_is_better | in_window_crossings / crossing_attempts | 穿越尝试数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：tide_window（14 步）, detour（15 步）
- 手算 fixture：ticks_and_phase（2 步）, wait_to_safe_phase（3 步），补充冻结后失败用例 `rescue_window_expires`（18 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-04` → `MAP-04: OK`。

## 9. MiMo 三次正式运行

正式 90 局尚未生成；本节由 `scripts/report_v8_maps.py` 在运行结束后回填。

## 10. 未决问题与边界说明

最早可行过桥 tick 固定为 5（V8-DCR-004）；该常量是地图规则的一部分。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`pending`；最终状态：`runtime_verified`。
