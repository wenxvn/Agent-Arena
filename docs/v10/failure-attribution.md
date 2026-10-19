# V10 MiMo trace 级失败归因

- 由 `python -m agent_arena.v10.attribution` 生成；逐局回放 `runs/v10/mimo/`
  `episodes/` 的动作序列。
- 覆盖 **116** 局（其中有效局 90）；机制动作集见模块
  `MECHANISM_TOOLS`。
- 标签含义：`CONTRACT_ARTIFACT`（接口假象）｜`KEY_ACTION_NEVER_ATTEMPTED`｜`KEY_ACTION_ATTEMPTED_REJECTED`｜`KEY_ACTION_USED_NO_TRIGGER`｜`TRIGGERED`。

## 1. 标签分布

| 标签 | 局数 |
|---|---:|
| `CONTRACT_ARTIFACT` | 10 |
| `KEY_ACTION_ATTEMPTED_REJECTED` | 2 |
| `KEY_ACTION_NEVER_ATTEMPTED` | 8 |
| `KEY_ACTION_USED_NO_TRIGGER` | 41 |
| `TRIGGERED` | 55 |

## 2. 逐局归因（有效局）

| 图 | seed | run_id | 标签 | 决策数 | 非法率 | 机制动作（尝试/被拒） | 终止 | 主指标 |
|---|---:|---|---|---:|---:|---|---|---|
| MAP-01 | 0 | `V10-MAP-01-S0-o2` | `KEY_ACTION_USED_NO_TRIGGER` | 4 | 0.0 | `interact` 0/0、`pickup` 0/0、`move` 1/0 | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 0 |
| MAP-01 | 1 | `V10-MAP-01-S1-o2` | `KEY_ACTION_USED_NO_TRIGGER` | 4 | 0.0 | `interact` 0/0、`pickup` 0/0、`move` 1/0 | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 0 |
| MAP-01 | 2 | `V10-MAP-01-S2-o2` | `KEY_ACTION_USED_NO_TRIGGER` | 5 | 0.0 | `interact` 0/0、`pickup` 0/0、`move` 2/0 | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 0 |
| MAP-02 | 0 | `V10-MAP-02-S0-m2` | `TRIGGERED` | 12 | 0.0 | `pickup` 1/0、`interact` 3/1 | CREW_PRESSURE_LOST | 0 |
| MAP-02 | 1 | `V10-MAP-02-S1-m2` | `TRIGGERED` | 10 | 0.0 | `pickup` 1/0、`interact` 1/0 | CREW_PRESSURE_LOST | 0 |
| MAP-02 | 2 | `V10-MAP-02-S2-m2` | `TRIGGERED` | 10 | 0.0 | `pickup` 1/0、`interact` 3/1 | CREW_PRESSURE_LOST | 0 |
| MAP-03 | 0 | `V10-MAP-03-S0-p0` | `KEY_ACTION_USED_NO_TRIGGER` | 39 | 0.0 | `write_memory` 1/0、`submit` 0/0 | RETURN_WINDOW_EXPIRED | None |
| MAP-03 | 1 | `V10-MAP-03-S1-p0` | `TRIGGERED` | 25 | 0.0 | `write_memory` 1/0、`submit` 1/0 | ROUTE_CALIBRATED | 1 |
| MAP-03 | 2 | `V10-MAP-03-S2-p0` | `TRIGGERED` | 34 | 0.029 | `write_memory` 1/0、`submit` 1/0 | ROUTE_CALIBRATED | 1 |
| MAP-04 | 0 | `V10-MAP-04-S0-ext` | `TRIGGERED` | 12 | 0.083 | `wait` 1/0 | RESCUE_SIGNAL_WINDOW_EXPIRED | 0 |
| MAP-04 | 1 | `V10-MAP-04-S1-ext` | `TRIGGERED` | 10 | 0.0 | `wait` 2/0 | RESCUE_SIGNAL_WINDOW_EXPIRED | 0 |
| MAP-04 | 2 | `V10-MAP-04-S2-ext` | `TRIGGERED` | 10 | 0.0 | `wait` 3/0 | RESCUE_SIGNAL_WINDOW_EXPIRED | 0 |
| MAP-05 | 0 | `V10-MAP-05-S0-m2` | `TRIGGERED` | 25 | 0.16 | `switch_power` 7/5、`interact` 6/0 | SIGNAL_WINDOW_MISSED | 0 |
| MAP-05 | 1 | `V10-MAP-05-S1-m2` | `TRIGGERED` | 20 | 0.15 | `switch_power` 5/3、`interact` 6/0 | SIGNAL_WINDOW_MISSED | 0 |
| MAP-05 | 2 | `V10-MAP-05-S2-m2` | `KEY_ACTION_USED_NO_TRIGGER` | 19 | 0.105 | `switch_power` 3/2、`interact` 4/0 | SIGNAL_WINDOW_MISSED | 0 |
| MAP-06 | 0 | `V10-MAP-06-S0-p0` | `KEY_ACTION_USED_NO_TRIGGER` | 3 | 0.0 | `interact` 1/0 | LAMP_RESTORED | 0.821429 |
| MAP-06 | 1 | `V10-MAP-06-S1-p0` | `TRIGGERED` | 3 | 0.0 | `interact` 1/0 | LAMP_RESTORED | 0.521429 |
| MAP-06 | 2 | `V10-MAP-06-S2-p0` | `TRIGGERED` | 6 | 0.0 | `interact` 2/0 | LAMP_RESTORED | 0.371429 |
| MAP-07 | 0 | `V10-MAP-07-S0-interface` | `TRIGGERED` | 4 | 0.0 | `turn_valve` 1/0 | DRAINED_IN_TIME | 1 |
| MAP-07 | 1 | `V10-MAP-07-S1-interface` | `KEY_ACTION_USED_NO_TRIGGER` | 4 | 0.0 | `turn_valve` 1/0 | FLOODED | 0 |
| MAP-07 | 2 | `V10-MAP-07-S2-interface` | `KEY_ACTION_NEVER_ATTEMPTED` | 2 | 0.0 | `turn_valve` 0/0 | FLOODED | 0 |
| MAP-08 | 0 | `V10-MAP-08-S0-interface` | `TRIGGERED` | 3 | 0.0 | `run_test` 1/0、`seal_diagnosis` 1/0 | LEAK_REPAIRED | 1 |
| MAP-08 | 1 | `V10-MAP-08-S1-interface` | `TRIGGERED` | 3 | 0.0 | `run_test` 1/0、`seal_diagnosis` 1/0 | LEAK_REPAIRED | 1 |
| MAP-08 | 2 | `V10-MAP-08-S2-interface` | `TRIGGERED` | 4 | 0.0 | `run_test` 2/0、`seal_diagnosis` 1/0 | LEAK_REPAIRED | 1 |
| MAP-09 | 0 | `V10-MAP-09-S0-interface` | `TRIGGERED` | 4 | 0.0 | `pump` 2/0、`seal` 0/0、`vent` 1/0 | HULL_SEALED | 1 |
| MAP-09 | 1 | `V10-MAP-09-S1-interface` | `TRIGGERED` | 2 | 0.0 | `pump` 1/0、`seal` 0/0、`vent` 0/0 | HULL_SEALED | 1 |
| MAP-09 | 2 | `V10-MAP-09-S2-interface` | `TRIGGERED` | 5 | 0.0 | `pump` 2/0、`seal` 0/0、`vent` 2/0 | HULL_SEALED | 1 |
| MAP-10 | 0 | `V10-MAP-10-S0-interface` | `TRIGGERED` | 2 | 0.0 | `load` 1/0、`unload` 0/0 | DELIVERED_IN_FULL | 1 |
| MAP-10 | 1 | `V10-MAP-10-S1-interface` | `TRIGGERED` | 2 | 0.0 | `load` 1/0、`unload` 0/0 | DELIVERED_IN_FULL | 1 |
| MAP-10 | 2 | `V10-MAP-10-S2-interface` | `TRIGGERED` | 2 | 0.0 | `load` 1/0、`unload` 0/0 | DELIVERED_IN_FULL | 1 |
| MAP-11 | 0 | `V10-MAP-11-S0-interface` | `KEY_ACTION_USED_NO_TRIGGER` | 3 | 0.0 | `search` 2/1、`rescue` 1/0 | SURVIVOR_RESCUED | 1 |
| MAP-11 | 1 | `V10-MAP-11-S1-interface` | `TRIGGERED` | 2 | 0.0 | `search` 1/0、`rescue` 1/0 | SURVIVOR_RESCUED | 1 |
| MAP-11 | 2 | `V10-MAP-11-S2-interface` | `TRIGGERED` | 5 | 0.0 | `search` 3/2、`rescue` 1/0 | SURVIVOR_RESCUED | 1 |
| MAP-12 | 0 | `V10-MAP-12-S0-interface` | `TRIGGERED` | 30 | 0.0 | `assign` 30/0 | RESEARCH_COMPLETED | 1 |
| MAP-12 | 1 | `V10-MAP-12-S1-interface` | `TRIGGERED` | 30 | 0.0 | `assign` 30/0 | RESEARCH_COMPLETED | 1 |
| MAP-12 | 2 | `V10-MAP-12-S2-interface` | `TRIGGERED` | 12 | 0.0 | `assign` 12/0 | STATION_LOST | 0 |
| MAP-13 | 0 | `V10-MAP-13-S0-ext` | `TRIGGERED` | 24 | 0.042 | `record_constraint` 5/1、`set_trial_layout` 3/0、`verify_layout` 3/0 | INCORRECT_ATTEMPT_LIMIT | 0.2 |
| MAP-13 | 1 | `V10-MAP-13-S1-ext` | `TRIGGERED` | 30 | 0.033 | `record_constraint` 7/5、`set_trial_layout` 0/0、`verify_layout` 0/0 | decision_budget_exhausted | None |
| MAP-13 | 2 | `V10-MAP-13-S2-ext` | `TRIGGERED` | 24 | 0.0 | `record_constraint` 5/1、`set_trial_layout` 3/0、`verify_layout` 4/0 | INCORRECT_ATTEMPT_LIMIT | 0.2 |
| MAP-14 | 0 | `V10-MAP-14-S0-ext` | `KEY_ACTION_USED_NO_TRIGGER` | 35 | 0.0 | `compare_evidence` 4/4、`submit_configuration` 5/4 | WRONG_SUBMISSION_LIMIT | 0 |
| MAP-14 | 1 | `V10-MAP-14-S1-ext` | `KEY_ACTION_USED_NO_TRIGGER` | 35 | 0.0 | `compare_evidence` 4/4、`submit_configuration` 5/4 | WRONG_SUBMISSION_LIMIT | 0 |
| MAP-14 | 2 | `V10-MAP-14-S2-ext` | `KEY_ACTION_USED_NO_TRIGGER` | 24 | 0.042 | `compare_evidence` 2/2、`submit_configuration` 5/4 | WRONG_SUBMISSION_LIMIT | 0 |
| MAP-15 | 0 | `V10-MAP-15-S0-p0` | `TRIGGERED` | 21 | 0.0 | `record_rule` 1/1、`predict_transition` 0/0 | TEST_WRONG_LIMIT | 0.0 |
| MAP-15 | 1 | `V10-MAP-15-S1-p0` | `TRIGGERED` | 13 | 0.0 | `record_rule` 1/1、`predict_transition` 0/0 | GATE_OPENED | 0.5 |
| MAP-15 | 2 | `V10-MAP-15-S2-p0-r2` | `TRIGGERED` | 22 | 0.0 | `record_rule` 1/1、`predict_transition` 1/1 | GATE_OPENED | 0.5 |
| MAP-16 | 0 | `V10-MAP-16-S0-r2` | `KEY_ACTION_USED_NO_TRIGGER` | 7 | 0.0 | `set_route` 4/0、`move_train` 3/1、`occupy_siding` 0/0 | NODE_CAPACITY_CONFLICT | 0 |
| MAP-16 | 1 | `V10-MAP-16-S1-r2` | `TRIGGERED` | 19 | 0.0 | `set_route` 10/1、`move_train` 9/0、`occupy_siding` 0/0 | GATE_OPENED | 1 |
| MAP-16 | 2 | `V10-MAP-16-S2-r2` | `KEY_ACTION_USED_NO_TRIGGER` | 4 | 0.0 | `set_route` 2/0、`move_train` 1/0、`occupy_siding` 0/0 | NODE_CAPACITY_CONFLICT | 0 |
| MAP-17 | 0 | `V10-MAP-17-S0-q2` | `KEY_ACTION_USED_NO_TRIGGER` | 12 | 0.0 | `set_timetable` 12/0 | DEADLINE_SERVICE_BELOW_THRESHOLD | 0 |
| MAP-17 | 1 | `V10-MAP-17-S1-q2` | `KEY_ACTION_USED_NO_TRIGGER` | 12 | 0.083 | `set_timetable` 11/0 | DEADLINE_SERVICE_BELOW_THRESHOLD | 0 |
| MAP-17 | 2 | `V10-MAP-17-S2-q2` | `KEY_ACTION_USED_NO_TRIGGER` | 12 | 0.083 | `set_timetable` 11/0 | DEADLINE_SERVICE_BELOW_THRESHOLD | 0 |
| MAP-18 | 0 | `V10-MAP-18-S0-i2` | `TRIGGERED` | 13 | 0.0 | `set_timetable` 13/2 | HEAD_ON_COLLISION | 0.5 |
| MAP-18 | 1 | `V10-MAP-18-S1-i2` | `TRIGGERED` | 8 | 0.0 | `set_timetable` 8/1 | STATION_CAPACITY_EXCEEDED | 0.5 |
| MAP-18 | 2 | `V10-MAP-18-S2-i2` | `TRIGGERED` | 7 | 0.0 | `set_timetable` 7/0 | SEGMENT_CAPACITY | 0.333333 |
| MAP-19 | 0 | `V10-MAP-19-S0-i2` | `KEY_ACTION_USED_NO_TRIGGER` | 60 | 0.0 | `forecast_next` 59/0 | decision_budget_exhausted | None |
| MAP-19 | 1 | `V10-MAP-19-S1-i2` | `KEY_ACTION_USED_NO_TRIGGER` | 60 | 0.0 | `forecast_next` 58/0 | decision_budget_exhausted | None |
| MAP-19 | 2 | `V10-MAP-19-S2-ext-r2` | `KEY_ACTION_USED_NO_TRIGGER` | 60 | 0.0 | `forecast_next` 59/0 | decision_budget_exhausted | None |
| MAP-20 | 0 | `V10-MAP-20-S0-j2` | `KEY_ACTION_NEVER_ATTEMPTED` | 56 | 0.0 | `open_bypass` 0/0 | decision_budget_exhausted | 0.0 |
| MAP-20 | 1 | `V10-MAP-20-S1-j2` | `KEY_ACTION_NEVER_ATTEMPTED` | 56 | 0.0 | `open_bypass` 0/0 | decision_budget_exhausted | 0.0 |
| MAP-20 | 2 | `V10-MAP-20-S2-j2` | `KEY_ACTION_NEVER_ATTEMPTED` | 56 | 0.0 | `open_bypass` 0/0 | decision_budget_exhausted | 0.0 |
| MAP-21 | 0 | `V10-MAP-21-S0-p0` | `TRIGGERED` | 7 | 0.0 | `collect_and_carry_sample` 1/0、`reinforce_sample_case` 1/0 | EVACUATED_BEFORE_ERUPTION | 0.654546 |
| MAP-21 | 1 | `V10-MAP-21-S1-p0` | `TRIGGERED` | 6 | 0.0 | `collect_and_carry_sample` 1/0、`reinforce_sample_case` 0/0 | EVACUATED_BEFORE_ERUPTION | 0.916667 |
| MAP-21 | 2 | `V10-MAP-21-S2-p0` | `TRIGGERED` | 6 | 0.0 | `collect_and_carry_sample` 1/0、`reinforce_sample_case` 0/0 | EVACUATED_BEFORE_ERUPTION | 0.590909 |
| MAP-22 | 0 | `V10-MAP-22-S0-ext-r2` | `KEY_ACTION_USED_NO_TRIGGER` | 59 | 0.0 | `write_memory` 6/4、`return_to_camp` 5/5 | MOVE_BUDGET_EXHAUSTED | 0 |
| MAP-22 | 1 | `V10-MAP-22-S1-ext` | `KEY_ACTION_ATTEMPTED_REJECTED` | 58 | 0.017 | `write_memory` 0/0、`return_to_camp` 5/5 | MOVE_BUDGET_EXHAUSTED | 0 |
| MAP-22 | 2 | `V10-MAP-22-S2-ext-r2` | `KEY_ACTION_USED_NO_TRIGGER` | 28 | 0.0 | `write_memory` 2/0、`return_to_camp` 1/0 | RETURNED_TO_CAMP_WITH_RUIN_RECORD | 1 |
| MAP-23 | 0 | `V10-MAP-23-S0-ext` | `TRIGGERED` | 9 | 0.0 | `scout` 1/0、`mark` 1/0 | TRUE_ENTRANCE_FOUND | 0.666667 |
| MAP-23 | 1 | `V10-MAP-23-S1-ext` | `TRIGGERED` | 13 | 0.0 | `scout` 1/0、`mark` 2/0 | TRUE_ENTRANCE_FOUND | 0.666667 |
| MAP-23 | 2 | `V10-MAP-23-S2-ext` | `TRIGGERED` | 6 | 0.0 | `scout` 1/0、`mark` 1/0 | TRUE_ENTRANCE_FOUND | 0.666667 |
| MAP-24 | 0 | `V10-MAP-24-S0-ext` | `TRIGGERED` | 9 | 0.0 | `probe_bridge` 1/0、`record_route` 0/0、`measure_tide` 0/0 | ALL_ITEMS_DELIVERED | 1 |
| MAP-24 | 1 | `V10-MAP-24-S1-ext` | `TRIGGERED` | 9 | 0.0 | `probe_bridge` 1/0、`record_route` 0/0、`measure_tide` 0/0 | ALL_ITEMS_DELIVERED | 1 |
| MAP-24 | 2 | `V10-MAP-24-S2-ext` | `TRIGGERED` | 9 | 0.0 | `probe_bridge` 1/0、`record_route` 0/0、`measure_tide` 0/0 | ALL_ITEMS_DELIVERED | 1 |
| MAP-25 | 0 | `V10-MAP-25-S0-p2` | `KEY_ACTION_USED_NO_TRIGGER` | 30 | 0.0 | `equip` 5/1、`eva_exit` 1/0、`diagnose` 2/1、`repair` 15/15、`return_to_A` 0/0 | decision_budget_exhausted | None |
| MAP-25 | 1 | `V10-MAP-25-S1-p2` | `KEY_ACTION_USED_NO_TRIGGER` | 30 | 0.0 | `equip` 4/0、`eva_exit` 1/0、`diagnose` 5/4、`repair` 15/15、`return_to_A` 0/0 | decision_budget_exhausted | None |
| MAP-25 | 2 | `V10-MAP-25-S2-p2` | `KEY_ACTION_USED_NO_TRIGGER` | 30 | 0.0 | `equip` 5/1、`eva_exit` 1/0、`diagnose` 3/2、`repair` 14/14、`return_to_A` 0/0 | decision_budget_exhausted | None |
| MAP-26 | 0 | `V10-MAP-26-S0-interface` | `TRIGGERED` | 3 | 0.0 | `run_test` 1/0、`replace` 1/0、`rollback` 0/0 | UNIT_RESTORED | 1 |
| MAP-26 | 1 | `V10-MAP-26-S1-interface` | `TRIGGERED` | 3 | 0.0 | `run_test` 1/0、`replace` 1/0、`rollback` 0/0 | UNIT_RESTORED | 1 |
| MAP-26 | 2 | `V10-MAP-26-S2-interface` | `TRIGGERED` | 3 | 0.0 | `run_test` 1/0、`replace` 1/0、`rollback` 0/0 | UNIT_RESTORED | 1 |
| MAP-27 | 0 | `V10-MAP-27-S0-n2` | `KEY_ACTION_USED_NO_TRIGGER` | 20 | 0.0 | `load` 3/3、`repair_relay` 1/0、`rescue` 7/0、`sample` 1/0、`submit` 0/0 | VEHICLE_STRANDED | 0 |
| MAP-27 | 1 | `V10-MAP-27-S1-n2` | `KEY_ACTION_USED_NO_TRIGGER` | 27 | 0.0 | `load` 11/2、`repair_relay` 1/0、`rescue` 0/0、`sample` 0/0、`submit` 0/0 | VEHICLE_STRANDED | 0 |
| MAP-27 | 2 | `V10-MAP-27-S2-n2-r2` | `KEY_ACTION_USED_NO_TRIGGER` | 46 | 0.022 | `load` 3/3、`repair_relay` 1/0、`rescue` 36/0、`sample` 1/0、`submit` 0/0 | decision_budget_exhausted | None |
| MAP-28 | 0 | `V10-MAP-28-S0-i2` | `TRIGGERED` | 20 | 0.0 | `record` 5/0、`read_record` 1/0、`submit` 1/0 | ALL_CLAIMS_SUPPORTED_AND_CORRECT | 1.0 |
| MAP-28 | 1 | `V10-MAP-28-S1-i2` | `KEY_ACTION_USED_NO_TRIGGER` | 30 | 0.0 | `record` 5/0、`read_record` 2/1、`submit` 1/1 | decision_budget_exhausted | None |
| MAP-28 | 2 | `V10-MAP-28-S2-i2` | `KEY_ACTION_USED_NO_TRIGGER` | 30 | 0.0 | `record` 3/0、`read_record` 1/0、`submit` 0/0 | decision_budget_exhausted | None |
| MAP-29 | 0 | `V10-MAP-29-S0-castle` | `KEY_ACTION_USED_NO_TRIGGER` | 38 | 0.0 | `ask` 8/5、`compare_testimony` 1/0、`submit` 0/0 | decision_budget_exhausted | 0.0 |
| MAP-29 | 1 | `V10-MAP-29-S1-castle` | `KEY_ACTION_USED_NO_TRIGGER` | 38 | 0.0 | `ask` 8/5、`compare_testimony` 1/0、`submit` 0/0 | decision_budget_exhausted | 0.0 |
| MAP-29 | 2 | `V10-MAP-29-S2-castle` | `KEY_ACTION_USED_NO_TRIGGER` | 38 | 0.0 | `ask` 8/5、`compare_testimony` 3/0、`submit` 0/0 | decision_budget_exhausted | 0.0 |
| MAP-30 | 0 | `V10-MAP-30-S0-castle` | `TRIGGERED` | 46 | 0.0 | `record` 14/0、`compare_records` 5/0、`formal_accuse` 0/0 | decision_budget_exhausted | 0.75 |
| MAP-30 | 1 | `V10-MAP-30-S1-castle` | `TRIGGERED` | 46 | 0.0 | `record` 11/0、`compare_records` 0/0、`formal_accuse` 0/0 | decision_budget_exhausted | 0.5 |
| MAP-30 | 2 | `V10-MAP-30-S2-castle` | `TRIGGERED` | 46 | 0.0 | `record` 13/0、`compare_records` 1/0、`formal_accuse` 0/0 | decision_budget_exhausted | 0.5 |

## 3. 非触发局的归类

| 图 | 局数 | 主因 | 说明 |
|---|---:|---|---|
| MAP-01 | 3/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×3 |
| MAP-03 | 1/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×1 |
| MAP-05 | 1/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×1 |
| MAP-06 | 1/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×1 |
| MAP-07 | 2/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×1；KEY_ACTION_NEVER_ATTEMPTED×1 |
| MAP-11 | 1/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×1 |
| MAP-14 | 3/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×3 |
| MAP-16 | 2/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×2 |
| MAP-17 | 3/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×3 |
| MAP-19 | 3/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×3 |
| MAP-20 | 3/3 | `KEY_ACTION_NEVER_ATTEMPTED` | KEY_ACTION_NEVER_ATTEMPTED×3 |
| MAP-22 | 3/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×2；KEY_ACTION_ATTEMPTED_REJECTED×1 |
| MAP-25 | 3/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×3 |
| MAP-27 | 3/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×3 |
| MAP-28 | 2/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×2 |
| MAP-29 | 3/3 | `KEY_ACTION_USED_NO_TRIGGER` | KEY_ACTION_USED_NO_TRIGGER×3 |

## 4. 结论要点

- `CONTRACT_ARTIFACT` 的局**不能**用于判断能力：必须在接口修复后重跑
  （见 DCR-V10-24/25）。
- `KEY_ACTION_NEVER_ATTEMPTED` 说明模型没有走到机制入口（多为策略/预算问题，
  需结合动作直方图）；对应局的失败应记在“策略”而不是“环境”。
- `KEY_ACTION_USED_NO_TRIGGER` 说明模型按机制动作操作，但阈值/时序没满足——这是
  最有价值的“接近但未达成”信号，适合作为 V11 的难度与提示设计依据。

## 5. 复算

```powershell
.venv\Scripts\python.exe -m agent_arena.v10.attribution
```

仓库根：`D:\wenxvn(2)\Agent-Arena`。
