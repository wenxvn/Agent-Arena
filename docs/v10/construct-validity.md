# V10 构念效度

- 由 `python -m agent_arena.v10.construct_validity` 生成；数字来自 `runs/v10/`。
- 两个维度**互不替代**：构念标签说明“机制是否通关必要条件”，效度状态说明“测量是否可信”。
- 全部为 `agent_reviewed`；不声称 `human_approved`。

## 1. 标签定义

| 标签 | 含义 |
|---|---|
| `FORCED` | 核心机制是通关必要条件（移除即失败） |
| `OPTIONAL` | 机制影响质量/成本/风险而非通过与否（须有连续质量指标） |
| `BYPASS` | 存在绕过核心机制的路径（V10 目标为清零） |
| `BLOCKED` | 接口/规则/预算阻止正常测量 |

## 2. 逐图

| 图 | 世界 | 构念 | 效度 | 运行时 | 消融证据 | 消融率区间 | MiMo | 裁定 |
|---|---|---|---|---|---|---|---|---|
| MAP-01 | spaceship | FORCED | VALIDATED | `v10` | `arm_before_pickup` 0/4；`early_confirm` 0/4；`no_support_restore` 0/4；`skip_bus` 0/4 | 0.00–0.00 | 0/3 | Batch 9e：Oracle 4/4、启发式 4/4、四消融 0/4；公开规则含互斥供电与船壳依赖链 |
| MAP-02 | spaceship | FORCED | VALIDATED | `v10` | `crew_only` 0/4；`late_react` 0/4；`nav_only` 0/4；`no_gate` 1/4 | 0.00–0.25 | 0/3 | Batch 9c：Oracle 4/4、启发式 4/4、no_gate 1/4（实例相关）、其余消融 0/4；阶段 6 的 3 局 MiMo 非法动作 0 |
| MAP-03 | spaceship | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `late_read` 0/6；`no_memory` 0/6；`random_guess` 0/6 | 0.00–0.00 | 2/3 | Batch 1：码 seed 化、goal 去泄露、清单封存、write_memory、EVA 对齐；三消融 0/6，启发式 6/6 |
| MAP-04 | lighthouse | OPTIONAL | NEEDS_MORE_EVIDENCE | `v10` | `blind_retry` 1/6；`detour_only` 6/6；`excess_wait` 0/6；`fixed_phase_script` 0/6 | 0.00–1.00 | 0/3 | Batch 4：盲撞计 3 tick 代价；绕行保留但余量恒 ≤ Oracle；blind_retry 1/6（仅开局安全相位的对照实例），excess_wait/fixed_phase_script 0/6 |
| MAP-05 | lighthouse | FORCED | VALIDATED | `v10` | `late_send` 0/4；`no_calibration` 0/4；`no_power_switch` 0/4；`wrong_order` 0/4 | 0.00–0.00 | 0/3 | Batch 9b：4 实例各自可行；Oracle 4/4、启发式 4/4、四消融 0/4；阶段 5b 的 3 局 MiMo 非法动作 0 |
| MAP-06 | lighthouse | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `always_direct` 5/10；`always_reinforce` 9/10；`forecast_always` 8/10 | 0.50–0.90 | 3/3 | Batch 2：10-seed 分层天气 cohort；短风暴计入风险；截止随 seed 公开；always_direct 5/10（长风暴全死），启发式 9/10 且效用均值 0.4228 > 三条固定策略 |
| MAP-07 | abyss | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `fixed_clockwise` 2/4；`late_open` 0/4；`never_open` 0/4；`turn_both` 2/4 | 0.00–0.50 | 1/3 | Batch 5：面板只公开因果不公开开向、拧错进水 +1、水位预测进入成败；fixed_clockwise 2/4（固定脚本假设被证伪）、never_open/late_open 0/4 |
| MAP-08 | abyss | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `blind_repairs` 0/4；`no_hypothesis` 0/4；`over_testing` 4/4；`single_test` 1/4 | 0.00–1.00 | 3/3 | Batch 5：封存诊断成为修复前提、测试必须缩小假设集；no_hypothesis 0/4（V9 旁路）、blind_repairs 0/4、single_test 1/4；over_testing 4/4 但 tests_used 3（合法但更慢） |
| MAP-09 | abyss | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `seal_only` 0/4；`skip_pump` 0/4；`skip_vent` 1/4 | 0.00–0.25 | 3/3 | Batch 5：修复需水位与供氧双门槛、三链同时结算、漏速递增；skip_pump 0/4（FLOODED）、skip_vent 1/4（LOST_POWER）、seal_only 0/4（LOST_OXYGEN） |
| MAP-10 | polar | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `max_load` 1/4；`no_move` 0/4；`underload` 0/4 | 0.00–0.25 | 3/3 | Batch 5：油耗 = burn_base + ceil(cargo/2)、容量与库存双约束；max_load 1/4（烧光油）、underload 0/4（货不够）、no_move 0/4 |
| MAP-11 | polar | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `blind_rescue` 0/4；`single_search_giveup` 2/4；`storm_search` 4/4；`waste_window` 2/4 | 0.00–1.00 | 3/3 | Batch 5：救援需先有信号、风暴窗口公开且漏检 0.5–0.7、生命窗；blind_rescue 0/4（V9 旁路）、storm_search 有风暴搜索但合法、single_search_giveup/waste_window 2/4；启发式风暴搜索 0 次 |
| MAP-12 | polar | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `all_forage` 0/4；`all_research` 0/4；`no_research` 0/4；`waste_slots` 0/4 | 0.00–0.00 | 2/3 | Batch 5：30 天 × 槽位排班、每日双结算、双归零失败；all_research/all_forage/no_research/waste_slots 全 0/4；启发式研究 38/35/40/75 |
| MAP-13 | pyramid | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `blind_guess` 0/4；`no_direction_nail` 4/4；`no_record` 0/4；`record_only_nail` 0/4 | 0.00–1.00 | 0/3 | Batch 5：记录成为出手前提（试排需 ≥1 条、验证需 ≥4 条）；no_record 0/4（V9 为 15 步满分）、blind_guess/record_only_nail 0/4；no_direction_nail 4/4 但 ratio 恒 0.8 |
| MAP-14 | pyramid | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `blind_two_submissions` 0/6；`no_seal` 0/6；`one_question` 2/6；`waste_questions` 6/6 | 0.00–1.00 | 0/3 | Batch 4：公开推理规则；开门需要相容封存假设；6 实例；blind_two_submissions 0/6（V9 为 2/3 开门）、no_seal 0/6、one_question 2/6 |
| MAP-15 | pyramid | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `fixed_route` 1/10；`no_probe` 0/10；`no_transfer` 0/10；`random_rule` 0/10 | 0.00–0.10 | 2/3 | Batch 2：删除 goal 泄露；6 规律家族；训练/测试墙色分离；record_rule 提交假设；消除相位自愈；四消融均 ≤1/10，启发式 10/10 |
| MAP-16 | subway | FORCED | VALIDATED | `v8` | — | — | 未运行 | Batch 5 防回归：V9 Oracle 在当前运行时可复跑；多 seed 覆盖缺口已明确记录 |
| MAP-17 | subway | FORCED | VALIDATED | `v8` | — | — | 未运行 | Batch 5 防回归：V9 Oracle 在当前运行时可复跑；多 seed 覆盖缺口已明确记录 |
| MAP-18 | subway | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `greedy_dispatch` 3/5；`ignore_windows` 0/5；`no_replan` 1/5 | 0.00–0.60 | 0/3 | Batch 1：时钟分离、发车窗口强制、5 个故障变体；抢跑 0/5，no_replan 1/5，greedy 3/5，启发式 5/5 |
| MAP-19 | volcano | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `fixed_vector_no_lag` 0/4；`max_loads_no_cooling` 0/4；`naive_forecast` 1/4；`no_forecast` 0/4 | 0.00–0.25 | 0/3 | Batch 4：预测成为产能的必要条件；精确温度与误差反馈公开；no_forecast 0/4、fixed_vector_no_lag 0/4、naive_forecast 1/4（容差 2 对照实例） |
| MAP-20 | volcano | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `bypass_overuse` 0/4；`no_bypass` 0/4；`static_allocation` 0/4；`zero_flow` 0/4 | 0.00–0.00 | 0/3 | Batch 4：产能与热量解耦、动态热点公开；区阀 C 30→35；static_allocation 0/4、no_bypass 0/4、bypass_overuse 0/4；Oracle bypass_used 10/10 tick |
| MAP-21 | volcano | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `always_collect` 7/10；`always_evac` 10/10；`measure_then_evac` 10/10 | 0.70–1.00 | 3/3 | Batch 2：safety_science 分离；10 seed 覆盖三种喷发时刻；always_evac 0.5（科研 0）、always_collect 3 灾难、risk_aware 0 灾难且均值 0.6886 最高 |
| MAP-22 | jungle | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `fixed_bearings` 0/4；`no_memory_write` 0/4；`no_return` 0/4；`random_walk` 0/4 | 0.00–0.00 | 1/3 | Batch 4：遮蔽（只给当前路标与方位）+ 死胡同分岔 + 跨阶段返程；no_memory_write 0/4（V9 为 12 决策成功）、fixed_bearings/no_return/random_walk 0/4；公开记忆 DFS 3/4（seed 1 因贪心方位顺序超预算，属策略弱点） |
| MAP-23 | jungle | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `ignore_counterevidence` 0/4；`no_scout` 0/4；`scout_everything` 0/4；`single_clue` 2/4 | 0.00–0.50 | 3/3 | Batch 4：出手需要已购线索 + 相容 mark；4 入口 × 3 侦察站使线索价格与信息量错开；no_scout 0/4（V9 为 12 决策成功）、ignore_counterevidence 0/4、scout_everything 0/4、single_clue 2/4 |
| MAP-24 | jungle | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `mountain_only` 4/4；`no_replan` 0/4；`waste_opening` 2/4 | 0.00–1.00 | 3/3 | Batch 4：山路拉长、封路时刻隐藏且不瞬杀、公开 collapse_observed；两条 primary 重定义；no_replan 0/4（replan_success 0）、mountain_only 记为 N/A 合法替代 |
| MAP-25 | lunar | FORCED | VALIDATED | `v10` | `no_diagnosis` 0/4；`no_tether` 0/4；`skip_array_inspection` 0/4；`wrong_tools` 0/4 | 0.00–0.00 | 0/3 | Batch 9f：Oracle 4/4、启发式 4/4、四消融 0/4；公开规则含出舱依赖链与工具组合 |
| MAP-26 | lunar | OPTIONAL | NEEDS_MORE_EVIDENCE | `v10` | `no_diagnosis` 3/4；`test_but_ignore` 0/4 | 0.00–0.75 | 3/3 | Batch 5：换错耗备件并 +1 磨损（达 2 即不可恢复）、rollback 不返还备件；no_diagnosis 3/4 但备件 2/2/1/2 且均有换错、test_but_ignore 0/4；启发式 4/4 且 spares 恒 1、precision 1 |
| MAP-27 | lunar | FORCED | VALIDATED | `v10` | `overload` 1/4；`skip_relay` 0/4；`skip_rescue` 0/4；`skip_sample` 0/4 | 0.00–0.25 | 0/3 | Batch 9d：Oracle 4/4、启发式 4/4、跳过目标消融 0/4、overload 1/4；公开规则含电量/货舱/充电/中继/伤员判据 |
| MAP-28 | castle | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `blind_submit` 0/4；`cite_all` 3/4；`no_record` 0/4；`single_source` 0/4 | 0.00–0.75 | 1/3 | Batch 3：公开 person/path 枚举；4 案卷依赖图不同；引用自洽规则；no_record 0/4、single_source 0/4、blind_submit 0/4、cite_all 3/4 |
| MAP-29 | castle | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `blind_accuse` 0/4；`no_compare` 0/4；`skip_archive` 0/4；`trust_first` 0/4 | 0.00–0.00 | 0/3 | Batch 3：公开 compare 语义；角色分配随 seed 轮换且不公开；部分真实证人；四消融 0/4，启发式 8–9 问 4/4 |
| MAP-30 | castle | FORCED | NEEDS_MORE_EVIDENCE | `v10` | `evidence_shuffle` 0/3；`late_guess` 0/3；`no_casebook` 0/3；`window_delay` 0/3 | 0.00–0.00 | 0/3 | Batch 3：公开条目 ID/成对规则/法庭节点/窗口语义；诱饵事件；两处指标偏置纠正；四消融 0/3，window_delay 触发 window_pressure |

## 3. 汇总

| 维度 | 状态 | 图数 |
|---|---|---:|
| 构念 | FORCED | 28 |
| 构念 | OPTIONAL | 2 |
| 构念 | BYPASS | 0 |
| 构念 | BLOCKED | 0 |
| 效度 | VALIDATED | 7 |
| 效度 | NEEDS_MORE_EVIDENCE | 23 |
| 效度 | NEEDS_REDESIGN | 0 |
| 效度 | BLOCKED | 0 |

## 4. 解释

- `OPTIONAL` 不等于“指标虚设”：MAP-26 的诊断被裁定为 OPTIONAL，但备件/换错次数/精度
  等连续指标仍能区分盲换与真诊断。
- `BYPASS` 标签在 V10 全部清零的依据是逐图消融成功率（见 `baseline-results.md`）与
  `decision-register.md` 的反例测试，而不是通关率变化。
- 7 张 V8 回退图（`runtime=v8`）的构念证据沿用 V9；其环境 seed 未参数化，
  3-seed 缺口见 `validated-regression.md`。
