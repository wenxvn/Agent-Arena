# V10 Batch 8：有界 MiMo 复测结果

- 由 `python -m agent_arena.v10.mimo_report` 从 `runs/v10/mimo/` 逐字重算，禁止手填。
- 模型：`mimo-v2.6-flash`；temperature=0；reasoning 关闭；每次请求先前预留、按供应商
  usage 结算；未知消费立即封账（保留预留，**不按 0 计**）。
- 全局上限 CNY 10；已结算 **CNY 2.02861492**；未知/未结预留 **CNY 0.13312000**；合计占用 **CNY 2.16173492**。
- 每图 3 个环境 seed、单一 replicate；`n=3` 只作描述，不作显著性断言，也不做跨模型排名。

## 1. 覆盖与账本

| 账本 | 请求 | 结算 CNY | 未结预留 CNY | 关闭原因 | sha256（前 12 位） |
|---|---:|---:|---:|---|---|
| `ledger.jsonl` | 1 | 0.00000000 | 0.01024000 | UNKNOWN_PROVIDER_SPEND | `f18b197e278d` |
| `ledger_supplement_001.jsonl` | 1 | 0.00000000 | 0.01024000 | UNKNOWN_PROVIDER_SPEND | `91baeeaa2d31` |
| `ledger_supplement_002.jsonl` | 1 | 0.00000000 | 0.01024000 | — | `a0688893765f` |
| `ledger_supplement_003.jsonl` | 62 | 0.13262268 | 0.00000000 | — | `101f9217dea8` |
| `ledger_supplement_004.jsonl` | 177 | 0.45549592 | 0.01024000 | PROVIDER_USAGE_OUTSIDE_REGISTERED_CAP | `259c1c435ea2` |
| `ledger_v10_001.jsonl` | 571 | 0.47599728 | 0.00000000 | — | `19ce2c510c94` |
| `ledger_v10_002.jsonl` | 327 | 0.23198268 | 0.01843200 | UNKNOWN_PROVIDER_SPEND | `afdcb39861c5` |
| `ledger_v10_003.jsonl` | 203 | 0.19058348 | 0.01843200 | UNKNOWN_PROVIDER_SPEND | `0939028d7f3f` |
| `ledger_v10_004.jsonl` | 108 | 0.09717440 | 0.00000000 | — | `938a15762bab` |
| `ledger_v10_005.jsonl` | 69 | 0.03609608 | 0.01843200 | UNKNOWN_PROVIDER_SPEND | `e57c67fa2888` |
| `ledger_v10_006.jsonl` | 202 | 0.08406884 | 0.00000000 | — | `bcddacdddd7f` |
| `ledger_v10_007.jsonl` | 164 | 0.03708196 | 0.01843200 | UNKNOWN_PROVIDER_SPEND | `9044e8e2c437` |
| `ledger_v10_008.jsonl` | 168 | 0.03032488 | 0.00000000 | — | `e2060ddf693b` |
| `ledger_v10_009.jsonl` | 31 | 0.01543524 | 0.00000000 | — | `e43f60bb5e92` |
| `ledger_v10_010.jsonl` | 25 | 0.01239556 | 0.00000000 | — | `be2d6c90a9c5` |
| `ledger_v10_011.jsonl` | 18 | 0.00781520 | 0.00000000 | — | `adddbf99fb2a` |
| `ledger_v10_012.jsonl` | 96 | 0.05914944 | 0.00000000 | — | `50bee897baf0` |
| `ledger_v10_013.jsonl` | 69 | 0.04294572 | 0.01843200 | UNKNOWN_PROVIDER_SPEND | `7dbec2ed074c` |
| `ledger_v10_014.jsonl` | 46 | 0.01854100 | 0.00000000 | — | `4ff6517334e4` |
| `ledger_v10_015.jsonl` | 13 | 0.00630880 | 0.00000000 | — | `f4c764deb13c` |
| `ledger_v10_016.jsonl` | 90 | 0.04212948 | 0.00000000 | — | `2719d2b6934f` |
| `ledger_v10_017.jsonl` | 36 | 0.03652772 | 0.00000000 | — | `f312fdf95081` |
| `ledger_v10_018.jsonl` | 30 | 0.01593856 | 0.00000000 | — | `bcd3ccea5a1f` |

## 2. 分组结果（仅统计有效局）

| 分组 | 有效局 | 成功 | 成功率 | 中断保留 | 结算 CNY |
|---|---:|---:|---:|---:|---:|
| P0 五图 | 15 | 10 | 0.667 | 1 | 0.66853700 |
| 古堡三图 | 9 | 0 | 0.000 | 0 | 0.33327568 |
| 接口七图 | 21 | 18 | 0.857 | 0 | 0.06230320 |
| 扩展八图 | 24 | 7 | 0.292 | 3 | 0.54273108 |
| 接口修复重跑（MAP-18/19/20/28） | 8 | 1 | 0.125 | 1 | 0.13425636 |
| 接口补全重跑（MAP-20 公开规则） | 3 | 0 | 0.000 | 0 | 0.03032488 |
| MAP-05 原生首测 | 3 | 0 | 0.000 | 0 | 0.01543524 |
| MAP-05 契约补区间重跑 | 3 | 0 | 0.000 | 0 | 0.01239556 |
| MAP-02 原生首测 | 3 | 0 | 0.000 | 0 | 0.00781520 |
| 补公开规则后重跑（MAP-02/05） | 6 | 0 | 0.000 | 0 | 0.05914944 |
| MAP-27 原生首测 | 3 | 0 | 0.000 | 1 | 0.06148672 |
| MAP-01 原生首测 | 3 | 0 | 0.000 | 0 | 0.00630880 |

## 3. 逐图逐 seed

| 图 | 世界 | 难度 | seed | run_id | 结局 | 决策数 | 主指标 | 机制触发 | CNY | 有效 |
|---|---|---|---:|---|---|---:|---|---|---:|---|
| MAP-01 | spaceship | 简单 | 0 | `V10-MAP-01-S0-o2` | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 4 | 0 | False | 0.00258500 | 是 |
| MAP-01 | spaceship | 简单 | 1 | `V10-MAP-01-S1-o2` | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 4 | 0 | False | 0.00258200 | 是 |
| MAP-01 | spaceship | 简单 | 2 | `V10-MAP-01-S2-o2` | OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 5 | 0 | False | 0.00114180 | 是 |
| MAP-02 | spaceship | 中等 | 0 | `V10-MAP-02-S0-l2` | NAV_CORE_FLOODED | 6 | 0 | True | 0.00291800 | 是 |
| MAP-02 | spaceship | 中等 | 0 | `V10-MAP-02-S0-m2` | CREW_PRESSURE_LOST | 12 | 0 | True | 0.00912600 | 是 |
| MAP-02 | spaceship | 中等 | 1 | `V10-MAP-02-S1-l2` | NAV_CORE_FLOODED | 6 | 0 | True | 0.00223008 | 是 |
| MAP-02 | spaceship | 中等 | 1 | `V10-MAP-02-S1-m2` | CREW_PRESSURE_LOST | 10 | 0 | True | 0.00381052 | 是 |
| MAP-02 | spaceship | 中等 | 2 | `V10-MAP-02-S2-l2` | NAV_CORE_FLOODED | 6 | 0 | False | 0.00266712 | 是 |
| MAP-02 | spaceship | 中等 | 2 | `V10-MAP-02-S2-m2` | CREW_PRESSURE_LOST | 10 | 0 | True | 0.00305016 | 是 |
| MAP-03 | spaceship | 困难 | 0 | `V10-MAP-03-S0-p0` | RETURN_WINDOW_EXPIRED | 39 | None | False | 0.16710588 | 是 |
| MAP-03 | spaceship | 困难 | 1 | `V10-MAP-03-S1-p0` | ROUTE_CALIBRATED | 25 | 1 | True | 0.10062108 | 是 |
| MAP-03 | spaceship | 困难 | 2 | `V10-MAP-03-S2-p0` | ROUTE_CALIBRATED | 34 | 1 | True | 0.07361828 | 是 |
| MAP-04 | lighthouse | 简单 | 0 | `V10-MAP-04-S0-ext` | RESCUE_SIGNAL_WINDOW_EXPIRED | 12 | 0 | True | 0.00652640 | 是 |
| MAP-04 | lighthouse | 简单 | 1 | `V10-MAP-04-S1-ext` | RESCUE_SIGNAL_WINDOW_EXPIRED | 10 | 0 | True | 0.00404544 | 是 |
| MAP-04 | lighthouse | 简单 | 2 | `V10-MAP-04-S2-ext` | RESCUE_SIGNAL_WINDOW_EXPIRED | 10 | 0 | True | 0.00493452 | 是 |
| MAP-05 | lighthouse | 中等 | 0 | `V10-MAP-05-S0-k2` | SIGNAL_WINDOW_MISSED | 12 | 0 | False | 0.00606956 | 是 |
| MAP-05 | lighthouse | 中等 | 0 | `V10-MAP-05-S0-k2b` | SIGNAL_WINDOW_MISSED | 12 | 0 | False | 0.00619600 | 是 |
| MAP-05 | lighthouse | 中等 | 0 | `V10-MAP-05-S0-m2` | SIGNAL_WINDOW_MISSED | 25 | 0 | True | 0.01723336 | 是 |
| MAP-05 | lighthouse | 中等 | 1 | `V10-MAP-05-S1-k2` | SIGNAL_WINDOW_MISSED | 6 | 0 | False | 0.00283300 | 是 |
| MAP-05 | lighthouse | 中等 | 1 | `V10-MAP-05-S1-k2b` | SIGNAL_WINDOW_MISSED | 6 | 0 | False | 0.00273556 | 是 |
| MAP-05 | lighthouse | 中等 | 1 | `V10-MAP-05-S1-m2` | SIGNAL_WINDOW_MISSED | 20 | 0 | True | 0.01351336 | 是 |
| MAP-05 | lighthouse | 中等 | 2 | `V10-MAP-05-S2-k2` | SIGNAL_WINDOW_MISSED | 13 | 0 | False | 0.00653268 | 是 |
| MAP-05 | lighthouse | 中等 | 2 | `V10-MAP-05-S2-k2b` | SIGNAL_WINDOW_MISSED | 7 | 0 | False | 0.00346400 | 是 |
| MAP-05 | lighthouse | 中等 | 2 | `V10-MAP-05-S2-m2` | SIGNAL_WINDOW_MISSED | 19 | 0 | False | 0.01241604 | 是 |
| MAP-06 | lighthouse | 困难 | 0 | `V10-MAP-06-S0-p0` | LAMP_RESTORED | 3 | 0.821429 | False | 0.00263400 | 是 |
| MAP-06 | lighthouse | 困难 | 1 | `V10-MAP-06-S1-p0` | LAMP_RESTORED | 3 | 0.521429 | True | 0.00130288 | 是 |
| MAP-06 | lighthouse | 困难 | 2 | `V10-MAP-06-S2-p0` | LAMP_RESTORED | 6 | 0.371429 | True | 0.00638620 | 是 |
| MAP-07 | abyss | 简单 | 0 | `V10-MAP-07-S0-interface` | DRAINED_IN_TIME | 4 | 1 | True | 0.00199200 | 是 |
| MAP-07 | abyss | 简单 | 1 | `V10-MAP-07-S1-interface` | FLOODED | 4 | 0 | False | 0.00196900 | 是 |
| MAP-07 | abyss | 简单 | 2 | `V10-MAP-07-S2-interface` | FLOODED | 2 | 0 | False | 0.00094000 | 是 |
| MAP-08 | abyss | 中等 | 0 | `V10-MAP-08-S0-interface` | LEAK_REPAIRED | 3 | 1 | True | 0.00174700 | 是 |
| MAP-08 | abyss | 中等 | 1 | `V10-MAP-08-S1-interface` | LEAK_REPAIRED | 3 | 1 | True | 0.00174500 | 是 |
| MAP-08 | abyss | 中等 | 2 | `V10-MAP-08-S2-interface` | LEAK_REPAIRED | 4 | 1 | True | 0.00239200 | 是 |
| MAP-09 | abyss | 困难 | 0 | `V10-MAP-09-S0-interface` | HULL_SEALED | 4 | 1 | True | 0.00185000 | 是 |
| MAP-09 | abyss | 困难 | 1 | `V10-MAP-09-S1-interface` | HULL_SEALED | 2 | 1 | True | 0.00088900 | 是 |
| MAP-09 | abyss | 困难 | 2 | `V10-MAP-09-S2-interface` | HULL_SEALED | 5 | 1 | True | 0.00210512 | 是 |
| MAP-10 | polar | 简单 | 0 | `V10-MAP-10-S0-interface` | DELIVERED_IN_FULL | 2 | 1 | True | 0.00079100 | 是 |
| MAP-10 | polar | 简单 | 1 | `V10-MAP-10-S1-interface` | DELIVERED_IN_FULL | 2 | 1 | True | 0.00078700 | 是 |
| MAP-10 | polar | 简单 | 2 | `V10-MAP-10-S2-interface` | DELIVERED_IN_FULL | 2 | 1 | True | 0.00054012 | 是 |
| MAP-11 | polar | 中等 | 0 | `V10-MAP-11-S0-interface` | SURVIVOR_RESCUED | 3 | 1 | False | 0.00110912 | 是 |
| MAP-11 | polar | 中等 | 1 | `V10-MAP-11-S1-interface` | SURVIVOR_RESCUED | 2 | 1 | True | 0.00087100 | 是 |
| MAP-11 | polar | 中等 | 2 | `V10-MAP-11-S2-interface` | SURVIVOR_RESCUED | 5 | 1 | True | 0.00198024 | 是 |
| MAP-12 | polar | 困难 | 0 | `V10-MAP-12-S0-interface` | RESEARCH_COMPLETED | 30 | 1 | True | 0.01534724 | 是 |
| MAP-12 | polar | 困难 | 1 | `V10-MAP-12-S1-interface` | RESEARCH_COMPLETED | 30 | 1 | True | 0.01490592 | 是 |
| MAP-12 | polar | 困难 | 2 | `V10-MAP-12-S2-interface` | STATION_LOST | 12 | 0 | True | 0.00577524 | 是 |
| MAP-13 | pyramid | 简单 | 0 | `V10-MAP-13-S0-ext` | INCORRECT_ATTEMPT_LIMIT | 24 | 0.2 | True | 0.01732500 | 是 |
| MAP-13 | pyramid | 简单 | 1 | `V10-MAP-13-S1-ext` | decision_budget_exhausted | 30 | None | True | 0.01856380 | 是 |
| MAP-13 | pyramid | 简单 | 2 | `V10-MAP-13-S2-ext` | INCORRECT_ATTEMPT_LIMIT | 24 | 0.2 | True | 0.01605760 | 是 |
| MAP-14 | pyramid | 中等 | 0 | `V10-MAP-14-S0-ext` | WRONG_SUBMISSION_LIMIT | 35 | 0 | False | 0.02588176 | 是 |
| MAP-14 | pyramid | 中等 | 1 | `V10-MAP-14-S1-ext` | WRONG_SUBMISSION_LIMIT | 35 | 0 | False | 0.02650352 | 是 |
| MAP-14 | pyramid | 中等 | 2 | `V10-MAP-14-S2-ext` | WRONG_SUBMISSION_LIMIT | 24 | 0 | False | 0.01961204 | 是 |
| MAP-15 | pyramid | 困难 | 0 | `V10-MAP-15-S0-p0` | TEST_WRONG_LIMIT | 21 | 0.0 | True | 0.07052416 | 是 |
| MAP-15 | pyramid | 困难 | 1 | `V10-MAP-15-S1-p0` | GATE_OPENED | 13 | 0.5 | True | 0.02945696 | 是 |
| MAP-15 | pyramid | 困难 | 2 | `V10-MAP-15-S2-p0` | settle_closed:供应商 usage 超出登记上限。 | 32 | None | False | 0.13646916 | 否 |
| MAP-15 | pyramid | 困难 | 2 | `V10-MAP-15-S2-p0-r2` | GATE_OPENED | 22 | 0.5 | True | 0.01823088 | 是 |
| MAP-16 | subway | 简单 | 0 | `V10-MAP-16-S0-r2` | NODE_CAPACITY_CONFLICT | 7 | 0 | False | 0.00407120 | 是 |
| MAP-16 | subway | 简单 | 1 | `V10-MAP-16-S1-r2` | GATE_OPENED | 19 | 1 | True | 0.00975064 | 是 |
| MAP-16 | subway | 简单 | 2 | `V10-MAP-16-S2-r2` | NODE_CAPACITY_CONFLICT | 4 | 0 | False | 0.00211672 | 是 |
| MAP-17 | subway | 中等 | 0 | `V10-MAP-17-S0-q2` | DEADLINE_SERVICE_BELOW_THRESHOLD | 12 | 0 | False | 0.01474412 | 是 |
| MAP-17 | subway | 中等 | 1 | `V10-MAP-17-S1-q2` | DEADLINE_SERVICE_BELOW_THRESHOLD | 12 | 0 | False | 0.01088680 | 是 |
| MAP-17 | subway | 中等 | 2 | `V10-MAP-17-S2-q2` | DEADLINE_SERVICE_BELOW_THRESHOLD | 12 | 0 | False | 0.01089680 | 是 |
| MAP-18 | subway | 困难 | 0 | `V10-MAP-18-S0-i2` | HEAD_ON_COLLISION | 13 | 0.5 | True | 0.01704928 | 是 |
| MAP-18 | subway | 困难 | 0 | `V10-MAP-18-S0-p0` | ACTION_LIMIT_REACHED | 20 | 0.0 | False | 0.02415288 | 是 |
| MAP-18 | subway | 困难 | 1 | `V10-MAP-18-S1-i2` | STATION_CAPACITY_EXCEEDED | 8 | 0.5 | True | 0.00803436 | 是 |
| MAP-18 | subway | 困难 | 1 | `V10-MAP-18-S1-p0` | ACTION_LIMIT_REACHED | 20 | 0.0 | False | 0.00577792 | 是 |
| MAP-18 | subway | 困难 | 2 | `V10-MAP-18-S2-i2` | SEGMENT_CAPACITY | 7 | 0.333333 | True | 0.00764352 | 是 |
| MAP-18 | subway | 困难 | 2 | `V10-MAP-18-S2-p0` | ACTION_LIMIT_REACHED | 20 | 0.0 | False | 0.01964128 | 是 |
| MAP-19 | volcano | 简单 | 0 | `V10-MAP-19-S0-ext` | decision_budget_exhausted | 60 | None | False | 0.04519940 | 是 |
| MAP-19 | volcano | 简单 | 0 | `V10-MAP-19-S0-i2` | decision_budget_exhausted | 60 | None | False | 0.01315280 | 是 |
| MAP-19 | volcano | 简单 | 1 | `V10-MAP-19-S1-ext` | decision_budget_exhausted | 60 | None | False | 0.04610320 | 是 |
| MAP-19 | volcano | 简单 | 1 | `V10-MAP-19-S1-i2` | decision_budget_exhausted | 60 | None | False | 0.01435920 | 是 |
| MAP-19 | volcano | 简单 | 2 | `V10-MAP-19-S2-ext` | unknown_provider_spend | 2 | None | False | 0.00123000 | 否 |
| MAP-19 | volcano | 简单 | 2 | `V10-MAP-19-S2-ext-r2` | decision_budget_exhausted | 60 | None | False | 0.00738220 | 是 |
| MAP-19 | volcano | 简单 | 2 | `V10-MAP-19-S2-i2` | unknown_provider_spend | 43 | None | False | 0.00956996 | 否 |
| MAP-20 | volcano | 中等 | 0 | `V10-MAP-20-S0-ext` | decision_budget_exhausted | 56 | 0.0 | False | 0.05722948 | 是 |
| MAP-20 | volcano | 中等 | 0 | `V10-MAP-20-S0-j2` | decision_budget_exhausted | 56 | 0.0 | False | 0.01219616 | 是 |
| MAP-20 | volcano | 中等 | 1 | `V10-MAP-20-S1-ext` | decision_budget_exhausted | 56 | 0.0 | False | 0.05725844 | 是 |
| MAP-20 | volcano | 中等 | 1 | `V10-MAP-20-S1-j2` | decision_budget_exhausted | 56 | 0.0 | False | 0.00812904 | 是 |
| MAP-20 | volcano | 中等 | 2 | `V10-MAP-20-S2-ext` | decision_budget_exhausted | 56 | 0.0 | False | 0.05757780 | 是 |
| MAP-20 | volcano | 中等 | 2 | `V10-MAP-20-S2-j2` | decision_budget_exhausted | 56 | 0.0 | False | 0.00999968 | 是 |
| MAP-21 | volcano | 困难 | 0 | `V10-MAP-21-S0-p0` | EVACUATED_BEFORE_ERUPTION | 7 | 0.654546 | True | 0.00589824 | 是 |
| MAP-21 | volcano | 困难 | 1 | `V10-MAP-21-S1-p0` | EVACUATED_BEFORE_ERUPTION | 6 | 0.916667 | True | 0.00438948 | 是 |
| MAP-21 | volcano | 困难 | 2 | `V10-MAP-21-S2-p0` | EVACUATED_BEFORE_ERUPTION | 6 | 0.590909 | True | 0.00232772 | 是 |
| MAP-22 | jungle | 简单 | 0 | `V10-MAP-22-S0-ext` | unknown_provider_spend | 34 | 0 | False | 0.01851776 | 否 |
| MAP-22 | jungle | 简单 | 0 | `V10-MAP-22-S0-ext-r2` | MOVE_BUDGET_EXHAUSTED | 59 | 0 | False | 0.03265288 | 是 |
| MAP-22 | jungle | 简单 | 1 | `V10-MAP-22-S1-ext` | MOVE_BUDGET_EXHAUSTED | 58 | 0 | False | 0.03065940 | 是 |
| MAP-22 | jungle | 简单 | 2 | `V10-MAP-22-S2-ext` | unknown_provider_spend | 10 | 0 | False | 0.00543668 | 否 |
| MAP-22 | jungle | 简单 | 2 | `V10-MAP-22-S2-ext-r2` | RETURNED_TO_CAMP_WITH_RUIN_RECORD | 28 | 1 | False | 0.01779472 | 是 |
| MAP-23 | jungle | 中等 | 0 | `V10-MAP-23-S0-ext` | TRUE_ENTRANCE_FOUND | 9 | 0.666667 | True | 0.00614600 | 是 |
| MAP-23 | jungle | 中等 | 1 | `V10-MAP-23-S1-ext` | TRUE_ENTRANCE_FOUND | 13 | 0.666667 | True | 0.00530980 | 是 |
| MAP-23 | jungle | 中等 | 2 | `V10-MAP-23-S2-ext` | TRUE_ENTRANCE_FOUND | 6 | 0.666667 | True | 0.00272260 | 是 |
| MAP-24 | jungle | 困难 | 0 | `V10-MAP-24-S0-ext` | ALL_ITEMS_DELIVERED | 9 | 1 | True | 0.00637100 | 是 |
| MAP-24 | jungle | 困难 | 1 | `V10-MAP-24-S1-ext` | ALL_ITEMS_DELIVERED | 9 | 1 | True | 0.00286568 | 是 |
| MAP-24 | jungle | 困难 | 2 | `V10-MAP-24-S2-ext` | ALL_ITEMS_DELIVERED | 9 | 1 | True | 0.00282396 | 是 |
| MAP-25 | lunar | 简单 | 0 | `V10-MAP-25-S0-p2` | decision_budget_exhausted | 30 | None | False | 0.01587828 | 是 |
| MAP-25 | lunar | 简单 | 1 | `V10-MAP-25-S1-p2` | decision_budget_exhausted | 30 | None | False | 0.01240108 | 是 |
| MAP-25 | lunar | 简单 | 2 | `V10-MAP-25-S2-p2` | decision_budget_exhausted | 30 | None | False | 0.01385012 | 是 |
| MAP-26 | lunar | 中等 | 0 | `V10-MAP-26-S0-interface` | UNIT_RESTORED | 3 | 1 | True | 0.00183600 | 是 |
| MAP-26 | lunar | 中等 | 1 | `V10-MAP-26-S1-interface` | UNIT_RESTORED | 3 | 1 | True | 0.00121080 | 是 |
| MAP-26 | lunar | 中等 | 2 | `V10-MAP-26-S2-interface` | UNIT_RESTORED | 3 | 1 | True | 0.00152040 | 是 |
| MAP-27 | lunar | 困难 | 0 | `V10-MAP-27-S0-n2` | VEHICLE_STRANDED | 20 | 0 | False | 0.01471032 | 是 |
| MAP-27 | lunar | 困难 | 1 | `V10-MAP-27-S1-n2` | VEHICLE_STRANDED | 27 | 0 | False | 0.01751156 | 是 |
| MAP-27 | lunar | 困难 | 2 | `V10-MAP-27-S2-n2` | unknown_provider_spend | 21 | None | False | 0.01072384 | 否 |
| MAP-27 | lunar | 困难 | 2 | `V10-MAP-27-S2-n2-r2` | decision_budget_exhausted | 46 | None | False | 0.01854100 | 是 |
| MAP-28 | castle | 简单 | 0 | `V10-MAP-28-S0-castle` | decision_budget_exhausted | 30 | None | False | 0.03482488 | 是 |
| MAP-28 | castle | 简单 | 0 | `V10-MAP-28-S0-i2` | ALL_CLAIMS_SUPPORTED_AND_CORRECT | 20 | 1.0 | True | 0.01538112 | 是 |
| MAP-28 | castle | 简单 | 1 | `V10-MAP-28-S1-castle` | decision_budget_exhausted | 30 | None | False | 0.02478312 | 是 |
| MAP-28 | castle | 简单 | 1 | `V10-MAP-28-S1-i2` | decision_budget_exhausted | 30 | None | False | 0.02548280 | 是 |
| MAP-28 | castle | 简单 | 2 | `V10-MAP-28-S2-castle` | decision_budget_exhausted | 30 | None | False | 0.01862644 | 是 |
| MAP-28 | castle | 简单 | 2 | `V10-MAP-28-S2-i2` | decision_budget_exhausted | 30 | None | False | 0.02358332 | 是 |
| MAP-29 | castle | 中等 | 0 | `V10-MAP-29-S0-castle` | decision_budget_exhausted | 38 | 0.0 | False | 0.03657720 | 是 |
| MAP-29 | castle | 中等 | 1 | `V10-MAP-29-S1-castle` | decision_budget_exhausted | 38 | 0.0 | False | 0.03658588 | 是 |
| MAP-29 | castle | 中等 | 2 | `V10-MAP-29-S2-castle` | decision_budget_exhausted | 38 | 0.0 | False | 0.03359748 | 是 |
| MAP-30 | castle | 困难 | 0 | `V10-MAP-30-S0-castle` | decision_budget_exhausted | 46 | 0.75 | True | 0.05126152 | 是 |
| MAP-30 | castle | 困难 | 1 | `V10-MAP-30-S1-castle` | decision_budget_exhausted | 46 | 0.5 | True | 0.04725760 | 是 |
| MAP-30 | castle | 困难 | 2 | `V10-MAP-30-S2-castle` | decision_budget_exhausted | 46 | 0.5 | True | 0.04976156 | 是 |

## 4. 结局分类（V10 首次真实归因）

| outcome | 局数 |
|---|---:|
| `decision_budget_exhausted` | 35 |
| `failure` | 44 |
| `settle_closed:供应商 usage 超出登记上限。` | 1 |
| `success` | 31 |
| `unknown_provider_spend` | 5 |

- 有效局成功 **37/110**；其余为机制失败/决策预算耗尽。
- 结论范围：本矩阵覆盖全部 30 张 V10 原生图；V8 回退图为 0。
  不得据此声称 30/30 的 MiMo 多 seed 覆盖。

## 5. 中断与补跑（全部保留，不覆盖）

| run_id | 图 | seed | 结局 | 决策数 | 处置 |
|---|---|---:|---|---:|---|
| `V10-MAP-15-S2-p0` | MAP-15 | 2 | settle_closed:供应商 usage 超出登记上限。 | 32 | 保留记录，不计入该 seed 有效证据；按预登记规则另开账本、以新 run_id 补跑 |
| `V10-MAP-19-S2-ext` | MAP-19 | 2 | unknown_provider_spend | 2 | 保留记录，不计入该 seed 有效证据；按预登记规则另开账本、以新 run_id 补跑 |
| `V10-MAP-19-S2-i2` | MAP-19 | 2 | unknown_provider_spend | 43 | 保留记录，不计入该 seed 有效证据；按预登记规则另开账本、以新 run_id 补跑 |
| `V10-MAP-22-S0-ext` | MAP-22 | 0 | unknown_provider_spend | 34 | 保留记录，不计入该 seed 有效证据；按预登记规则另开账本、以新 run_id 补跑 |
| `V10-MAP-22-S2-ext` | MAP-22 | 2 | unknown_provider_spend | 10 | 保留记录，不计入该 seed 有效证据；按预登记规则另开账本、以新 run_id 补跑 |
| `V10-MAP-27-S2-n2` | MAP-27 | 2 | unknown_provider_spend | 21 | 保留记录，不计入该 seed 有效证据；按预登记规则另开账本、以新 run_id 补跑 |

补跑局（`-r2`，新 run_id + 原因已在 `mimo-preregistration.json` 登记）：

| run_id | 图 | seed | 结局 | 决策数 |
|---|---|---:|---|---:|
| `V10-MAP-15-S2-p0-r2` | MAP-15 | 2 | GATE_OPENED | 22 |
| `V10-MAP-16-S0-r2` | MAP-16 | 0 | NODE_CAPACITY_CONFLICT | 7 |
| `V10-MAP-16-S1-r2` | MAP-16 | 1 | GATE_OPENED | 19 |
| `V10-MAP-16-S2-r2` | MAP-16 | 2 | NODE_CAPACITY_CONFLICT | 4 |
| `V10-MAP-19-S2-ext-r2` | MAP-19 | 2 | decision_budget_exhausted | 60 |
| `V10-MAP-22-S0-ext-r2` | MAP-22 | 0 | MOVE_BUDGET_EXHAUSTED | 59 |
| `V10-MAP-22-S2-ext-r2` | MAP-22 | 2 | RETURNED_TO_CAMP_WITH_RUIN_RECORD | 28 |
| `V10-MAP-27-S2-n2-r2` | MAP-27 | 2 | decision_budget_exhausted | 46 |

另有阶段 3（`-i2`）接口修复后的同图全 seed 重跑：见 DCR-V10-24 与 `mimo-preregistration.json` 的 `phase_3_interface_fix`。
阶段 3 与阶段 1/2 的同图同 seed 只作“接口修复前后”的配对描述，不称严格同条件 A/B。

