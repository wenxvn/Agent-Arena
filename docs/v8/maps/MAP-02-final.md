# MAP-02 定稿：双重警报

| 字段 | 值 |
|---|---|
| 世界 | spaceship |
| 难度 | 中等 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `16dd9b625da0404a1aa9ca0491bbb4d3ca61bf68a441a30babc507f6354d1536` |
| rule_hash | `f48f10bc47fd68c0565a5dbd9f945602695eb0e3fae3a9eff554c3549532f5d4` |
| prompt_hash | `8dc15046113630b39c77ce20d1e7c131c39d54fa855b9569a9924889f6affdbd` |
| metric_schema_hash | `8a5efbdb9af9a3c7c8ade5af2979a312f40145207df6489d0f9589a1706d8e50` |
| oracle_hash | `885f67a317f42969cb3ca57a79a24c2cccece36166d437ffb747874a52278ea9` |
| commit | `a13ba1e11e267447fbb3c8a4c6b1f5319a313806` |

## 1. 设计意图与独特机制

本图测的是事件发生后是否及时换计划；它不以是否预测到事故作为成功条件。运行时与观察过滤仍待后续实现。

MAP-02｜双重警报：动作序号触发的泄漏事件与在线目标重排。

## 2. 与同世界另两图的区别

- **MAP-01**（简单）：生命支持、互斥供电与船壳修补的依赖规划。
- **MAP-03**（困难）：五阶段里程碑与一次性远期代码召回。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`center_gate`, `crew_escorted`, `crew_in_escape_pod`, `crew_location`, `crew_pressure_ticks`, `deadline_tick`, `goal`, `leak_active`, `leak_location`, `location`, `nav_core_location`, `nav_core_secured`, `navigation_alarm`, `repair_pack_available`, `spread_contained`, `visible_edges`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`action_index`, `center_gate`, `crew_escorted`, `crew_in_escape_pod`, `crew_pressure_ticks`, `leak_active`, `location`, `nav_core_secured`, `spread_ticks`, `stale_actions_after_leak`

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

本图结算要点：动作计数到 4 触发泄漏；触发当 tick 不扣扩散/压力；之后先判成功，再结算扩散与船员压力。

- 成功码：`DUAL_OBJECTIVE_COMPLETE`
- 失败码：`CREW_PRESSURE_LOST`, `GLOBAL_DEADLINE`, `NAV_CORE_FLOODED`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map02.completion_ticks` | diagnostic | lower_is_better | terminal_tick if success else N/A | 成功局 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map02.crew_decompression` | guardrail | lower_is_better | count(CREW_DECOMPRESSION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map02.dual_objective_completion` | primary | higher_is_better | (w_rescue * rescue_done + w_nav * nav_secured) / (w_rescue + w_nav) | 两目标权重和 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map02.event_response_latency` | primary | lower_is_better | tick(first plan-changing action after leak) - tick(leak public) | 观察到泄漏的 episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map02.stale_plan_actions_after_leak` | diagnostic | lower_is_better | count(stale_goal_actions after leak) | 泄漏后动作数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：core_first（11 步）, crew_first（14 步）
- 手算 fixture：nav_core_then_pod_success（9 步）, secure_core_but_lose_crew（13 步），补充冻结后失败用例 `ignore_leak_nav_core_floods`（6 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-02` → `MAP-02: OK`。

## 9. MiMo 三次正式运行

正式 90 局尚未生成；本节由 `scripts/report_v8_maps.py` 在运行结束后回填。

## 10. 未决问题与边界说明

双目标完成度只作报告比例，不作加权胜负；成功仍要求导航核与救生舱同时达成。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`pending`；最终状态：`runtime_verified`。
