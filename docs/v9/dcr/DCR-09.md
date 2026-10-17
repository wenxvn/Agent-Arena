# DCR-09：指标叠加修正（MAP-02 / MAP-04 / MAP-05 / MAP-21 / MAP-25）

- 状态：`accepted`（V9 只读叠加；不改 V8 指标实现）
- 地图：MAP-02、MAP-04、MAP-05、MAP-21、MAP-25
- 关联审计：各图 §6
- 影响面：`overlay_schema_hash`；旧值保留

## 1. 证据

| 地图 | 旧指标问题 | 证据 |
|---|---|---|
| MAP-02 | `event_response_latency` 把任何非 wait/inspect 动作算作响应，MiMo/启发式/随机全部 = 1 | `docs/v9/maps/MAP-02-audit.md` §6 |
| MAP-04 | `stranded_ticks` 在 `map04.py` 直接返回 `high_tide_entries`；唯一成功局两条 primary 全 N/A | MAP-04 §6 |
| MAP-05 | `window_utilization` 与 `effective_signals` 分子分母完全相同；`power_overcommit` 硬编码 0 | MAP-05 §6 |
| MAP-21 | `evacuation_coverage` 分母是“已投入单位”，直达撤离仍得 1.0 | MAP-21 §6 |
| MAP-25 | 被拒 `diagnose` 被记为完成，R2 7/7 与 `diagnosed=False` 矛盾 | MAP-25 §6 |

## 2. 修复定义

`src/agent_arena/v9/metric_overlay.py` 新增：

- `map02.adaptive_response_within_2`：泄漏公开后 2 个决策内是否出现 `nav_core`/`center_gate` 计划变更（0/1）。
- `map04.tide_route_used`：是否尝试过 `S_G`（0/1）。
- `map04.stranded_ticks_status`：`unavailable`（运行时无该计数器，不伪造）。
- `map05.window_utilization_corrected`：`effective_signals/3`（明确与旧指标同义，避免被当成独立指标）。
- `map05.power_overcommit_status`：`unavailable`（硬编码 0，不伪造）。
- `map21.scientific_units_evacuated`：成功时 `1 + sample + measurement`，分母 3。
- `map25.required_check_coverage_corrected`：不把被拒诊断计入完成。
- `map13.illegal_door_attempts_corrected`：只统计 `ILLEGAL_DOOR`，不含 `STATE_RESET`。
- `map14.query_gap_signed`：`queries_used - minimum_queries`，允许负值，避免“不问最优”。
- `map19.exceedance_area_per_tick`：按已结算 tick 归一，解决跨局不可比。

## 3. 预期与风险

- 预期：每张图至少有一个连续指标能区分“通关但绕过”与“真正完成机制”（MAP-21 直达=1/3，带样品+测量=3/3；MAP-02 自适应=0/1）。
- 风险：叠加指标不是 V7 登记指标，不能与 V8 原值直接相加；V9 报告必须并列新旧两列。
- 不改变 V8 `v8_metrics.json`；仅写入 V9 `v9_metrics.json.overlay` 与 `runs/v9/overlay/`。

## 4. 验证

`tests/test_v9_overlay.py::test_map21_overlay_discriminates_direct_evacuation`、
`test_map25_overlay_does_not_credit_rejected_diagnosis`、
`test_overlay_schema_hash_is_stable_and_map_specific`。

## 5. 结论

`accepted` 为 V9 只读叠加；是否把这些定义提升为 V10 正式指标，需要用户确认。
