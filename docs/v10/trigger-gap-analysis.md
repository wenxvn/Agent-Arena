# V10 未触发机制局的逐局判读

- 由 `python -m agent_arena.v10.trigger_gap` 生成；只读既有 MiMo trace 与基线产物。
- 覆盖 **35** 局（15 张图），
  全部是“有效但 `mechanism_triggered=False`”。
- 判读规则：`BUDGET`（预算用尽）｜`THRESHOLD`（撞规则阈值）｜
`ENTRY_NOT_ATTEMPTED`（没尝试机制动作）｜`ENTRY_REJECTED`（机制动作全被拒）｜
`USED_NO_THRESHOLD`（用了但没达成）。

## 1. 分布

| 判读 | 局数 |
|---|---:|
| `BUDGET` | 15 |
| `ENTRY_REJECTED` | 1 |
| `THRESHOLD` | 13 |
| `USED_NO_THRESHOLD` | 6 |

## 2. 逐图

| 图 | 未触发局 | 判读 | 决策预算 | Oracle 动作 | 预算余量 | 决策数 |
|---|---:|---|---:|---:|---:|---|
| MAP-01 | 3 | `THRESHOLD`×3 | 30 | 15 | 15 | 4, 4, 5 |
| MAP-03 | 1 | `THRESHOLD`×1 | 46 | 31 | 15 | 39 |
| MAP-05 | 1 | `THRESHOLD`×1 | 38 | 19 | 19 | 19 |
| MAP-06 | 1 | `USED_NO_THRESHOLD`×1 | 46 | 5 | 41 | 3 |
| MAP-07 | 2 | `THRESHOLD`×2 | 30 | 10 | 20 | 2, 4 |
| MAP-11 | 1 | `USED_NO_THRESHOLD`×1 | 38 | 4 | 34 | 3 |
| MAP-14 | 3 | `THRESHOLD`×3 | 38 | 12 | 26 | 24, 35, 35 |
| MAP-17 | 3 | `USED_NO_THRESHOLD`×3 | 38 | 14 | 24 | 12, 12, 12 |
| MAP-19 | 3 | `BUDGET`×3 | 60 | 38 | 22 | 60, 60, 60 |
| MAP-20 | 3 | `BUDGET`×3 | 56 | 40 | 16 | 56, 56, 56 |
| MAP-22 | 3 | `ENTRY_REJECTED`×1；`THRESHOLD`×1；`USED_NO_THRESHOLD`×1 | 80 | 24 | 56 | 28, 58, 59 |
| MAP-25 | 3 | `BUDGET`×3 | 30 | 16 | 14 | 30, 30, 30 |
| MAP-27 | 3 | `BUDGET`×1；`THRESHOLD`×2 | 46 | 17 | 29 | 20, 27, 46 |
| MAP-28 | 2 | `BUDGET`×2 | 30 | 18 | 12 | 30, 30 |
| MAP-29 | 3 | `BUDGET`×3 | 38 | 22 | 16 | 38, 38, 38 |

## 3. 逐局明细

| 图 | seed | run_id | 判读 | 决策/预算 | 终止 |
机制动作（尝试/被拒） | 最后动作 → 结果 |
|---|---:|---|---|---|---|---|---|
| MAP-01 | 0 | `V10-MAP-01-S0-o2` | `THRESHOLD` | 4/30 | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | `interact` 0/0、`pickup` 0/0、`move` 1/0 | `inspect` → DIAGRAM:capacity=6,fixed=3,support=2,arm=2 |
| MAP-01 | 1 | `V10-MAP-01-S1-o2` | `THRESHOLD` | 4/30 | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | `interact` 0/0、`pickup` 0/0、`move` 1/0 | `inspect` → DIAGRAM:capacity=6,fixed=3,support=2,arm=2 |
| MAP-01 | 2 | `V10-MAP-01-S2-o2` | `THRESHOLD` | 5/30 | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | `interact` 0/0、`pickup` 0/0、`move` 2/0 | `move` → MOVED:W |
| MAP-03 | 0 | `V10-MAP-03-S0-p0` | `THRESHOLD` | 39/46 | RETURN_WINDOW_EXPIRED | `write_memory` 1/0、`submit` 0/0 | `move` → MOVED:D2 |
| MAP-05 | 2 | `V10-MAP-05-S2-m2` | `THRESHOLD` | 19/38 | SIGNAL_WINDOW_MISSED | `switch_power` 3/2、`interact` 4/0 | `interact` → SIGNAL_SENT |
| MAP-06 | 0 | `V10-MAP-06-S0-p0` | `USED_NO_THRESHOLD` | 3/46 | LAMP_RESTORED | `interact` 1/0 | `interact` → REPAIR_STARTED |
| MAP-07 | 1 | `V10-MAP-07-S1-interface` | `THRESHOLD` | 4/30 | FLOODED | `turn_valve` 1/0 | `turn_valve` → VALVE_TIGHTENED |
| MAP-07 | 2 | `V10-MAP-07-S2-interface` | `THRESHOLD` | 2/30 | FLOODED | `turn_valve` 0/0 | `inspect` → PANEL_READ |
| MAP-11 | 0 | `V10-MAP-11-S0-interface` | `USED_NO_THRESHOLD` | 3/38 | SURVIVOR_RESCUED | `search` 2/1、`rescue` 1/0 | `rescue` → SURVIVOR_RESCUED |
| MAP-14 | 0 | `V10-MAP-14-S0-ext` | `THRESHOLD` | 35/38 | WRONG_SUBMISSION_LIMIT | `compare_evidence` 4/4、`submit_configuration` 5/4 | `submit_configuration` → WRONG_SUBMISSION_LIMIT |
| MAP-14 | 1 | `V10-MAP-14-S1-ext` | `THRESHOLD` | 35/38 | WRONG_SUBMISSION_LIMIT | `compare_evidence` 4/4、`submit_configuration` 5/4 | `submit_configuration` → WRONG_SUBMISSION_LIMIT |
| MAP-14 | 2 | `V10-MAP-14-S2-ext` | `THRESHOLD` | 24/38 | WRONG_SUBMISSION_LIMIT | `compare_evidence` 2/2、`submit_configuration` 5/4 | `submit_configuration` → WRONG_SUBMISSION_LIMIT |
| MAP-17 | 0 | `V10-MAP-17-S0-q2` | `USED_NO_THRESHOLD` | 12/38 | DEADLINE_SERVICE_BELOW_THRESHOLD | `set_timetable` 12/0 | `set_timetable` → TICK_COMMITTED |
| MAP-17 | 1 | `V10-MAP-17-S1-q2` | `USED_NO_THRESHOLD` | 12/38 | DEADLINE_SERVICE_BELOW_THRESHOLD | `set_timetable` 11/0 | `set_timetable` → TICK_COMMITTED |
| MAP-17 | 2 | `V10-MAP-17-S2-q2` | `USED_NO_THRESHOLD` | 12/38 | DEADLINE_SERVICE_BELOW_THRESHOLD | `set_timetable` 11/0 | `set_timetable` → TICK_COMMITTED |
| MAP-19 | 0 | `V10-MAP-19-S0-i2` | `BUDGET` | 60/60 | decision_budget_exhausted | `forecast_next` 59/0 | `forecast_next` → FORECAST_RECORDED |
| MAP-19 | 1 | `V10-MAP-19-S1-i2` | `BUDGET` | 60/60 | decision_budget_exhausted | `forecast_next` 58/0 | `forecast_next` → FORECAST_RECORDED |
| MAP-19 | 2 | `V10-MAP-19-S2-ext-r2` | `BUDGET` | 60/60 | decision_budget_exhausted | `forecast_next` 59/0 | `forecast_next` → FORECAST_RECORDED |
| MAP-20 | 0 | `V10-MAP-20-S0-j2` | `BUDGET` | 56/56 | decision_budget_exhausted | `open_bypass` 0/0 | `set_flow` → FLOW_SET |
| MAP-20 | 1 | `V10-MAP-20-S1-j2` | `BUDGET` | 56/56 | decision_budget_exhausted | `open_bypass` 0/0 | `set_flow` → FLOW_SET |
| MAP-20 | 2 | `V10-MAP-20-S2-j2` | `BUDGET` | 56/56 | decision_budget_exhausted | `open_bypass` 0/0 | `set_flow` → FLOW_SET |
| MAP-22 | 0 | `V10-MAP-22-S0-ext-r2` | `USED_NO_THRESHOLD` | 59/80 | MOVE_BUDGET_EXHAUSTED | `write_memory` 6/4、`return_to_camp` 5/5 | `move` → MOVE_BUDGET_EXHAUSTED |
| MAP-22 | 1 | `V10-MAP-22-S1-ext` | `ENTRY_REJECTED` | 58/80 | MOVE_BUDGET_EXHAUSTED | `write_memory` 0/0、`return_to_camp` 5/5 | `move` → MOVE_BUDGET_EXHAUSTED |
| MAP-22 | 2 | `V10-MAP-22-S2-ext-r2` | `THRESHOLD` | 28/80 | RETURNED_TO_CAMP_WITH_RUIN_RECORD | `write_memory` 2/0、`return_to_camp` 1/0 | `return_to_camp` → RETURNED_TO_CAMP_WITH_RUIN_RECORD |
| MAP-25 | 0 | `V10-MAP-25-S0-p2` | `BUDGET` | 30/30 | decision_budget_exhausted | `equip` 5/1、`eva_exit` 1/0、`diagnose` 2/1、`repair` 15/15、`return_to_A` 0/0 | `repair` → INVALID_TARGET_ID |
| MAP-25 | 1 | `V10-MAP-25-S1-p2` | `BUDGET` | 30/30 | decision_budget_exhausted | `equip` 4/0、`eva_exit` 1/0、`diagnose` 5/4、`repair` 15/15、`return_to_A` 0/0 | `diagnose` → INVALID_TOOL_ID |
| MAP-25 | 2 | `V10-MAP-25-S2-p2` | `BUDGET` | 30/30 | decision_budget_exhausted | `equip` 5/1、`eva_exit` 1/0、`diagnose` 3/2、`repair` 14/14、`return_to_A` 0/0 | `repair` → INVALID_TARGET_ID |
| MAP-27 | 0 | `V10-MAP-27-S0-n2` | `THRESHOLD` | 20/46 | VEHICLE_STRANDED | `load` 3/0、`repair_relay` 1/0、`rescue` 7/0、`sample` 1/0、`submit` 0/0 | `drive` → VEHICLE_STRANDED |
| MAP-27 | 1 | `V10-MAP-27-S1-n2` | `THRESHOLD` | 27/46 | VEHICLE_STRANDED | `load` 11/0、`repair_relay` 1/0、`rescue` 0/0、`sample` 0/0、`submit` 0/0 | `drive` → VEHICLE_STRANDED |
| MAP-27 | 2 | `V10-MAP-27-S2-n2-r2` | `BUDGET` | 46/46 | decision_budget_exhausted | `load` 3/0、`repair_relay` 1/0、`rescue` 36/0、`sample` 1/0、`submit` 0/0 | `rescue` → ACTION_NOT_ALLOWED |
| MAP-28 | 1 | `V10-MAP-28-S1-i2` | `BUDGET` | 30/30 | decision_budget_exhausted | `record` 5/0、`read_record` 2/1、`submit` 1/1 | `move` → MOVE_SUCCEEDED |
| MAP-28 | 2 | `V10-MAP-28-S2-i2` | `BUDGET` | 30/30 | decision_budget_exhausted | `record` 3/0、`read_record` 1/0、`submit` 0/0 | `move` → MOVE_SUCCEEDED |
| MAP-29 | 0 | `V10-MAP-29-S0-castle` | `BUDGET` | 38/38 | decision_budget_exhausted | `ask` 8/5、`compare_testimony` 1/0、`submit` 0/0 | `move` → MOVE_SUCCEEDED |
| MAP-29 | 1 | `V10-MAP-29-S1-castle` | `BUDGET` | 38/38 | decision_budget_exhausted | `ask` 8/5、`compare_testimony` 1/0、`submit` 0/0 | `investigate` → TARGET_NOT_VISIBLE |
| MAP-29 | 2 | `V10-MAP-29-S2-castle` | `BUDGET` | 38/38 | decision_budget_exhausted | `ask` 8/5、`compare_testimony` 3/0、`submit` 0/0 | `ask` → ANSWER_RECEIVED:B_TIME_BASIS_STOPPED_0005 |

## 4. 结论

- `BUDGET` 的图：预算与 Oracle 动作数的余量足够，模型仍用尽预算 ⇒
  属**策略效率**问题，不是预算过紧。
- `THRESHOLD` 的图：终止码是规则阈值，说明模型确实进入了机制路径但在时序/容量上失败。
- `ENTRY_NOT_ATTEMPTED` 的图：模型从未尝试机制动作 ⇒ 需要检查公开规则是否
  把入口讲清楚（V10 已补 MAP-02/05/27/01 的 `public_rules()`）。
- `USED_NO_THRESHOLD` 的图：最接近“能力边界”，适合作为 V11 的难度与提示设计依据。

## 5. 复算

```powershell
.venv\Scripts\python.exe -m agent_arena.v10.trigger_gap
```
