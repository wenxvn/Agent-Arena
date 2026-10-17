# MAP-05 定稿：三束信号

| 字段 | 值 |
|---|---|
| 世界 | lighthouse |
| 难度 | 中等 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `b9201a539d66119baedf3cf9e6b6057b266b94e98ce5a564c740c0d2c0bd2560` |
| rule_hash | `4aa810269535dad84ce3ad40f5d524edaabe084ab970085b851d0e6a8dd298b4` |
| prompt_hash | `384ccc6cba165cd61e99aef961efcdb45feb4d71fb995e09a470b2c6904e5a8a` |
| metric_schema_hash | `996b31a1abc646f81b338e3e11e25af4ae986d59be798dd93acf770c6fb46db3` |
| oracle_hash | `aa308112628841678eb5b06d63da6d936b925d34e59dec3a73724261242f54e2` |
| commit | `039e25ce6503871ceb31184e85c9265451ee7486` |

## 1. 设计意图与独特机制

本图测量在单路供电约束下，如何跨越不同距离、连续校准阶段与发射窗口安排三座灯塔。路线和窗口必须共同满足；单纯少走路可能多等，提早校准远塔可能多走路却压低空等量。

MAP-05｜三束信号：单路共享供电下的跨塔校准与窗口排程。

## 2. 与同世界另两图的区别

- **MAP-04**（简单）：周期相位预测与短窗/长绕行的时序权衡。
- **MAP-06**（困难）：80% 条件预报、风险预算与加固决策。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`calibration`, `goal`, `location`, `power_target`, `schedule_chart_inspected`, `tick`, `transmitted`, `visible_edges`, `windows`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`calibration`, `idle_ticks`, `location`, `missed_windows`, `power_target`, `transmitted`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `inspect`：`target_id`
- `interact`：`operation`, `target_id`
- `move`：`edge_id`
- `switch_power`：`station`
- `wait`：`ticks`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：三塔共享单路电力与信号窗口；校准、充电、发信号按 tick 排程，错过窗口即失败。

- 成功码：`THREE_SIGNALS_SENT`
- 失败码：`SIGNAL_WINDOW_MISSED`
- 机制失败路径：
  - 三束信号排程冲突 → `SIGNAL_WINDOW_MISSED`
  - 电力未校准即发信号 → 校准拒绝
  - 跨塔往返超窗 → 信号窗口错过

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map05.effective_signals` | primary | higher_is_better | count(valid_signal emissions) | 3 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map05.idle_ticks` | diagnostic | lower_is_better | idle_ticks_on_powered_tower | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map05.missed_windows` | diagnostic | lower_is_better | count(window_end without emission) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map05.power_overcommit` | guardrail | lower_is_better | count(POWER_LIMIT_EXCEEDED) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map05.window_utilization` | primary | higher_is_better | completed_window_tasks / feasible_window_tasks | 可完成窗口任务数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：near_first（27 步）, far_first_prep（21 步）
- 手算 fixture：travel_cost_and_switch（2 步）, unpowered_calibration_is_refused（2 步），补充冻结后失败用例 `first_signal_window_missed`（19 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-05` → `MAP-05: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | failure | False | SIGNAL_WINDOW_MISSED | 19 | 0.01176612 | `V8-MAP-05-R0-20261017T074657Z-ce0bf747` | `effective_signals`=0.0; `idle_ticks`=0; `missed_windows`=1; `power_overcommit`=0 |
| 1 | failure | False | SIGNAL_WINDOW_MISSED | 20 | 0.01133772 | `V8-MAP-05-R1-20261017T074749Z-59117c83` | `effective_signals`=0.333333; `idle_ticks`=4; `missed_windows`=1; `power_overcommit`=0 |
| 2 | failure | False | SIGNAL_WINDOW_MISSED | 19 | 0.01027484 | `V8-MAP-05-R2-20261017T074855Z-9656232d` | `effective_signals`=0.333333; `idle_ticks`=5; `missed_windows`=1; `power_overcommit`=0 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

采用修订后的可行窗口；窗口表已随 `rule_hash` 冻结，旧版不可行窗口不再使用。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
