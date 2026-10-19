# V10 基线对照表（Oracle / 启发式 / 随机 / 消融）

- 由 `python -m agent_arena.v10.difficulty` 从 `runs/v10/baselines/MAP-XX.json` 重算。
- `legal_random` = 每环境 seed × 20 个 policy seed；`机制触发` 只对 Oracle 有定义。
- 消融率越高说明核心机制越容易被绕过；但“合法替代策略”也会表现为消融成功
  （见 final-report §2）。

| 图 | seed 数 | Oracle | 机制触发 | 启发式 | 随机 | 消融（成功率） | 最易绕过 |
|---|---:|---|---|---|---:|---|---:|
| MAP-01 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `arm_before_pickup` 0/4；`early_confirm` 0/4；`no_support_restore` 0/4；`skip_bus` 0/4 | 0.0 |
| MAP-02 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `crew_only` 0/4；`late_react` 0/4；`nav_only` 0/4；`no_gate` 1/4 | 0.25 |
| MAP-03 | 6 | 6/6 | 6/6 | 6/6 | 0/120 | `late_read` 0/6；`no_memory` 0/6；`random_guess` 0/6 | 0.0 |
| MAP-04 | 6 | 6/6 | 6/6 | 6/6 | 0/120 | `blind_retry` 1/6；`detour_only` 6/6；`excess_wait` 0/6；`fixed_phase_script` 0/6 | 1.0 |
| MAP-05 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `late_send` 0/4；`no_calibration` 0/4；`no_power_switch` 0/4；`wrong_order` 0/4 | 0.0 |
| MAP-06 | 10 | 10/10 | 9/10 | 9/10 | 0/200 | `always_direct` 5/10；`always_reinforce` 9/10；`forecast_always` 8/10 | 0.9 |
| MAP-07 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `fixed_clockwise` 2/4；`late_open` 0/4；`never_open` 0/4；`turn_both` 2/4 | 0.5 |
| MAP-08 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `blind_repairs` 0/4；`no_hypothesis` 0/4；`over_testing` 4/4；`single_test` 1/4 | 1.0 |
| MAP-09 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `seal_only` 0/4；`skip_pump` 0/4；`skip_vent` 1/4 | 0.25 |
| MAP-10 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `max_load` 1/4；`no_move` 0/4；`underload` 0/4 | 0.25 |
| MAP-11 | 4 | 4/4 | 3/4 | 4/4 | 0/80 | `blind_rescue` 0/4；`single_search_giveup` 2/4；`storm_search` 4/4；`waste_window` 2/4 | 1.0 |
| MAP-12 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `all_forage` 0/4；`all_research` 0/4；`no_research` 0/4；`waste_slots` 0/4 | 0.0 |
| MAP-13 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `blind_guess` 0/4；`no_direction_nail` 4/4；`no_record` 0/4；`record_only_nail` 0/4 | 1.0 |
| MAP-14 | 6 | 6/6 | 6/6 | 6/6 | 0/120 | `blind_two_submissions` 0/6；`no_seal` 0/6；`one_question` 2/6；`waste_questions` 6/6 | 1.0 |
| MAP-15 | 10 | 10/10 | 10/10 | 10/10 | 0/200 | `fixed_route` 1/10；`no_probe` 0/10；`no_transfer` 0/10；`random_rule` 0/10 | 0.1 |
| MAP-18 | 5 | 5/5 | 5/5 | 5/5 | 0/100 | `greedy_dispatch` 3/5；`ignore_windows` 0/5；`no_replan` 1/5 | 0.6 |
| MAP-19 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `fixed_vector_no_lag` 0/4；`max_loads_no_cooling` 0/4；`naive_forecast` 1/4；`no_forecast` 0/4 | 0.25 |
| MAP-20 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `bypass_overuse` 0/4；`no_bypass` 0/4；`static_allocation` 0/4；`zero_flow` 0/4 | 0.0 |
| MAP-21 | 10 | 10/10 | 10/10 | 10/10 | 0/200 | `always_collect` 7/10；`always_evac` 10/10；`measure_then_evac` 10/10 | 1.0 |
| MAP-22 | 4 | 4/4 | 4/4 | 3/4 | 0/80 | `fixed_bearings` 0/4；`no_memory_write` 0/4；`no_return` 0/4；`random_walk` 0/4 | 0.0 |
| MAP-23 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `ignore_counterevidence` 0/4；`no_scout` 0/4；`scout_everything` 0/4；`single_clue` 2/4 | 0.5 |
| MAP-24 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `mountain_only` 4/4；`no_replan` 0/4；`waste_opening` 2/4 | 1.0 |
| MAP-25 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `no_diagnosis` 0/4；`no_tether` 0/4；`skip_array_inspection` 0/4；`wrong_tools` 0/4 | 0.0 |
| MAP-26 | 4 | 4/4 | 4/4 | 4/4 | 1/80 | `no_diagnosis` 3/4；`test_but_ignore` 0/4 | 0.75 |
| MAP-27 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `overload` 1/4；`skip_relay` 0/4；`skip_rescue` 0/4；`skip_sample` 0/4 | 0.25 |
| MAP-28 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `blind_submit` 0/4；`cite_all` 3/4；`no_record` 0/4；`single_source` 0/4 | 0.75 |
| MAP-29 | 4 | 4/4 | 4/4 | 4/4 | 0/80 | `blind_accuse` 0/4；`no_compare` 0/4；`skip_archive` 0/4；`trust_first` 0/4 | 0.0 |
| MAP-30 | 3 | 3/3 | 3/3 | 3/3 | 0/60 | `evidence_shuffle` 0/3；`late_guess` 0/3；`no_casebook` 0/3；`window_delay` 0/3 | 0.0 |

## 复算

```powershell
.venv\Scripts\python.exe -m agent_arena.v10.baselines.suite
.venv\Scripts\python.exe -m agent_arena.v10.difficulty
```
