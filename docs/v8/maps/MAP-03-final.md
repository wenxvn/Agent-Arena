# MAP-03 定稿：最后的百步

| 字段 | 值 |
|---|---|
| 世界 | spaceship |
| 难度 | 困难 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `9c322bb5a43955af1ae85b8cb79eba8126fcdd5b0782f16b26661683de941879` |
| rule_hash | `ba6ee7abcbb1bf4fa915ca43a22985640b9378cd38c3483eed56f6e83ea8dad4` |
| prompt_hash | `8647f5409b23c375c44ba630c55f9f6d5be3b5e36d5d4c3cd6135244e3d8c998` |
| metric_schema_hash | `54cbe1b6893f87f5f236741bb92daea7c25724d8ffce4440a5ab75aa6fab0a82` |
| oracle_hash | `0ba3a97587da65b4cd8cfc4dd85a4673ddac6bb6edb4afac6dd56716a923f335` |
| commit | `039e25ce6503871ceb31184e85c9265451ee7486` |

## 1. 设计意图与独特机制

这是一张跨楼层、跨阶段的长期目标保持图。主要负担不是动作数本身，而是把早期只出现一次的航线码 K7 留到最后使用，同时不漏掉五个不同依赖的里程碑。

MAP-03｜最后的百步：五阶段里程碑与一次性远期代码召回。

## 2. 与同世界另两图的区别

- **MAP-01**（简单）：生命支持、互斥供电与船壳修补的依赖规划。
- **MAP-02**（中等）：动作序号触发的泄漏事件与在线目标重排。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`antenna`, `aux_power`, `communications_power`, `cryo_power`, `eva_active`, `eva_supply`, `goal`, `location`, `milestones`, `milestones_completed`, `return_window_end_tick`, `route_calibrated`, `route_tag_read`, `route_tag_value`, `sample_cold`, `sample_thermal_ticks`, `telemetry`, `visible_edges`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`antenna`, `aux_power`, `eva_supply`, `location`, `milestones`, `route_calibrated`, `route_tag_read`, `sample_cold`, `submissions`, `telemetry`, `thermal_ticks`, `violations`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `inspect`：`target`
- `interact`：`choice`, `target`
- `move`：`edge_id`
- `submit`：`answer`, `target`
- `wait`：`turns`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：读标签后冷窗 4 tick；每 tick 先推进冷窗，再检查 36 tick 返航窗口。

- 成功码：`ROUTE_CALIBRATED`
- 失败码：`EVA_OXYGEN_EXHAUSTED`, `RETURN_WINDOW_EXPIRED`, `ROUTE_KEY_REJECTED`, `SAMPLE_COLD_WINDOW_EXPIRED`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map03.completion_ticks` | diagnostic | lower_is_better | terminal_tick if success else N/A | 成功局 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map03.long_delay_recall_accuracy` | primary | higher_is_better | correct_early_facts / required_early_facts | 需提交事实数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map03.lost_sample` | diagnostic | lower_is_better | 1 if terminal_reason==SAMPLE_LOST else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map03.phase_completion_coverage` | primary | higher_is_better | completed_milestones / 5 | 5 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map03.phase_order_violations` | guardrail | lower_is_better | count(PHASE_OUT_OF_ORDER) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：milestone_first（30 步）, zone_first（31 步）
- 手算 fixture：early_route_submission_is_refused（1 步）, cold_window_expires_after_tag_read（21 步），补充冻结后失败用例 `return_window_expires_without_calibration`（36 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-03` → `MAP-03: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | failure | False | EVA_OXYGEN_EXHAUSTED | 28 | 0.01721744 | `V8-MAP-03-R0-20261017T073906Z-238898f5` | `long_delay_recall_accuracy`=0.0; `lost_sample`=0; `phase_completion_coverage`=0.2; `phase_order_violations`=2 |
| 1 | failure | False | EVA_OXYGEN_EXHAUSTED | 21 | 0.01235524 | `V8-MAP-03-R1-20261017T074047Z-92eadacf` | `long_delay_recall_accuracy`=0.0; `lost_sample`=0; `phase_completion_coverage`=0.2; `phase_order_violations`=1 |
| 2 | failure | False | SAMPLE_COLD_WINDOW_EXPIRED | 27 | 0.01346528 | `V8-MAP-03-R2-20261017T074226Z-a8156d63` | `long_delay_recall_accuracy`=0.0; `lost_sample`=1; `phase_completion_coverage`=0.2; `phase_order_violations`=2 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

未新增“漏阶段/码错”独立终局码，失败归因依赖阶段位与召回指标。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
