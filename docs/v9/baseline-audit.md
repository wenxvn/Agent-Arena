# V9 Batch 0：V8 基线冻结与复算

- 复算时间（本地）：2026-10-17 20:25 +08:00
- 仓库 HEAD：`35e37117e890c8e165a708d89204a01cf1801466`（`main...origin/main`，工作树仅有未跟踪的 `研究提纲/`）
- V8 冻结：`b174a6f734fbc6b2f1d25c0b6beba40f62431ce0572b281a40c0c3049c32dbb0`，冻结 commit `039e25ce6503871ceb31184e85c9265451ee7486`
- 复算入口：`python -m agent_arena.v9.audit`、`python -m agent_arena.v9.evidence`、`python -m agent_arena.v9.report`
- 机器可读结果：`runs/v9/baseline/baseline.json`、`runs/v9/baseline/run-index.csv`、`runs/v9/evidence/MAP-XX.json`、`runs/v9/reports/data-digest.md`
- 逐局索引（提交副本）：`docs/v9/run-index.csv`

> 本文件的所有数字都由上述脚本从 `runs/v8/results_90.csv`、90 个 episode 目录、12 个 V8 账本与 30 个冻结 hash 重新计算，不复制 `docs/v8` 摘要。

## 1. Gate 0 判定

**Gate 0 通过（有 1 项口径差异需记录）。**

| 检查 | 结果 |
|---|---|
| 正式行数 90 = 30 图 × 3 重复 | 通过 |
| 缺失 (map, replicate) | 0 |
| 重复 (map, replicate) | 0 |
| 重复 run_id | 0 |
| Trace / judge / V8 metrics 三件套齐全 | 90/90 |
| judge `decision_count` = Trace 决策行数 | 90/90 |
| judge success/终止原因 = registry 行 | 90/90 |
| Trace header 与冻结 manifest 的 scenario/rule/source/prompt/metric hash | 90/90 一致 |
| 当前运行时重算 30 图 5 类 hash | 30/30 一致（MAP-12 预算例外已纳入） |
| 90 局费用复算 | ¥1.27464628 = registry = CSV |
| 不可验证 Trace | 0 |

**口径差异**：`docs/v8/mimo-90-results.md` 的“账本 settled ¥1.39004496”不包含 5 个 *aborted* 预跑账本；把 `runs/v8/aborted/*/ledger.jsonl` 一并计入后，全账本 settled 为 **¥1.45502656**。两者都不等于正式 90 局费用 ¥1.27464628。V9 采用三分口径：

1. 正式 90 局：**¥1.27464628**；
2. 正式运行补充账本（main + supplement_001–006，含 superseded 旧局）：**¥1.39004496**；
3. 含 5 次作废预跑的全部 V8 账本：**¥1.45502656**。

## 2. 复算的正式结果

- 成功 **17/90**（18.9%）；`failure` 39、`decision_budget_reached` 32、`censored` 2。
- 简单 3/30、中等 3/30、困难 11/30（原始计数，不作显著性断言）。
- 0/3：22 图；3/3：MAP-06、MAP-15、MAP-21。
- 1/3：MAP-04、MAP-23；2/3：MAP-13、MAP-20、MAP-24。
- 平均决策 21.6、请求 1944（90 局）；正式局平均费用 ¥0.014163。

| map | world | 难度 | 成功 | statuses | 终止原因 | 平均决策 | 非法动作 |
|---|---|---|---|---|---|---|---|
| MAP-01 | spaceship | 简单 | 0/3 | failure×3 | OXYGEN_SUPPLY_INTERRUPTION_LIMIT; BUS_RESET_WITH_HULL_OPEN; OXYGEN_SUPPLY_INTERRUPTION_LIMIT | 12.3 | 0 |
| MAP-02 | spaceship | 中等 | 0/3 | failure×3 | NAV_CORE_FLOODED ×3 | 6.0 | 0 |
| MAP-03 | spaceship | 困难 | 0/3 | failure×3 | EVA_OXYGEN_EXHAUSTED ×2; SAMPLE_COLD_WINDOW_EXPIRED | 25.3 | 0 |
| MAP-04 | lighthouse | 简单 | 1/3 | failure×2, success×1 | SIGNAL_LIT; RESCUE_SIGNAL_WINDOW_EXPIRED ×2 | 15.3 | 0 |
| MAP-05 | lighthouse | 中等 | 0/3 | failure×3 | SIGNAL_WINDOW_MISSED ×3 | 19.3 | 0 |
| MAP-06 | lighthouse | 困难 | 3/3 | success×3 | LAMP_RESTORED ×3 | 2.7 | 0 |
| MAP-07 | abyss | 简单 | 0/3 | decision_budget×3 | — | 30.0 | 0 |
| MAP-08 | abyss | 中等 | 0/3 | decision_budget×3 | — | 38.0 | 0 |
| MAP-09 | abyss | 困难 | 0/3 | failure×3 | SHORT_CIRCUIT ×3 | 2.0 | 0 |
| MAP-10 | polar | 简单 | 0/3 | failure×3 | GENERATOR_FUEL_SHORTAGE ×3 | 3.0 | 0 |
| MAP-11 | polar | 中等 | 0/3 | failure×3 | SUPPLY_SHORTAGE ×3 | 2.0 | 0 |
| MAP-12 | polar | 困难 | 0/3 | failure×3 | RESEARCH_TARGET_MISSED ×3 | 60.0 | 0 |
| MAP-13 | pyramid | 简单 | 2/3 | decision_budget×1, success×2 | GATE_OPENED ×2 | 25.3 | 0 |
| MAP-14 | pyramid | 中等 | 0/3 | decision_budget×3 | — | 38.0 | 0 |
| MAP-15 | pyramid | 困难 | 3/3 | success×3 | GATE_OPENED ×3 | 12.3 | 0 |
| MAP-16 | subway | 简单 | 0/3 | failure×3 | DEADLOCK; NODE_CAPACITY_CONFLICT ×2 | 15.0 | 0 |
| MAP-17 | subway | 中等 | 0/3 | decision_budget×3 | — | 38.0 | 1 |
| MAP-18 | subway | 困难 | 0/3 | censored×2, failure×1 | ACTION_LIMIT_REACHED ×2; STATION_CAPACITY_EXCEEDED | 9.0 | 0 |
| MAP-19 | volcano | 简单 | 0/3 | decision_budget×2, failure×1 | THERMAL_RUNAWAY | 27.7 | 0 |
| MAP-20 | volcano | 中等 | 2/3 | failure×1, success×2 | THERMAL_OVERHEAT; PRODUCTION_TARGET_MET ×2 | 19.3 | 0 |
| MAP-21 | volcano | 困难 | 3/3 | success×3 | EVACUATED_BEFORE_ERUPTION ×3 | 1.7 | 0 |
| MAP-22 | jungle | 简单 | 0/3 | decision_budget×3 | — | 30.0 | 0 |
| MAP-23 | jungle | 中等 | 1/3 | failure×2, success×1 | SUPPLY_DEPLETED ×2; TRUE_ENTRANCE_FOUND | 16.0 | 0 |
| MAP-24 | jungle | 困难 | 2/3 | failure×1, success×2 | STRANDED_ON_BRIDGE; ALL_ITEMS_DELIVERED ×2 | 10.0 | 0 |
| MAP-25 | lunar | 简单 | 0/3 | decision_budget×2, failure×1 | OXYGEN_DEPLETED | 29.7 | 0 |
| MAP-26 | lunar | 中等 | 0/3 | decision_budget×3 | — | 38.0 | 0 |
| MAP-27 | lunar | 困难 | 0/3 | failure×3 | VEHICLE_STRANDED ×3 | 8.0 | 0 |
| MAP-28 | castle | 简单 | 0/3 | decision_budget×3 | — | 30.0 | 0 |
| MAP-29 | castle | 中等 | 0/3 | decision_budget×3 | — | 38.0 | 0 |
| MAP-30 | castle | 困难 | 0/3 | decision_budget×3 | — | 46.0 | 0 |

（完整费用列、trace sha256 与失败码见 `docs/v9/run-index.csv`。）

## 3. 版本一致性

| commit | 正式行 | 地图 |
|---|---|---|
| `223e532ed9b9613ba96e06d129b41fb1f52b37bc` | 60 | MAP-01 – MAP-11、MAP-13 – MAP-21 |
| `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` | 27 | MAP-22 – MAP-30 |
| `039e25ce6503871ceb31184e85c9265451ee7486` | 3 | MAP-12（预算修为 60 的补跑） |

三个 commit 不同，但 **90 条 Trace header 的 scenario/rule/source/prompt/metric_schema hash 与冻结清单逐条一致**；说明差异只在文档/脚本/账本编排，不在场景规则、动作契约、prompt 或指标定义。因此 90 行在测量条件上可比；MAP-12 的 `decision_budget=60` 是唯一登记过的预算例外，已在冻结 manifest 的 map 条目中体现，V9 不得把它与 46 混淆。

## 4. 账本与费用

| ledger | settled ¥ | 正式局 | 正式 ¥ | superseded 局 | superseded ¥ | closed |
|---|---|---|---|---|---|---|
| main | 0.39018164 | 35 | 0.28607888 | 4 | 0.10410276 | True |
| supplement_001 | 0.07356604 | 4 | 0.07356604 | 0 | 0 | True |
| supplement_002 | 0.29372260 | 21 | 0.28697024 | 3 | 0.00675236 | True |
| supplement_003 | 0.18176880 | 14 | 0.17879392 | 1 | 0.00297488 | True |
| supplement_004 | 0.03338392 | 4 | 0.03181524 | 1 | 0.00156868 | True |
| supplement_005 | 0.30242300 | 9 | 0.30242300 | 0 | 0 | False（无 close 事件） |
| supplement_006 | 0.11499896 | 3 | 0.11499896 | 0 | 0 | False（无 close 事件） |
| aborted/pre_*（5 个） | 0.06498160 | 0 | 0 | 26 | 0.06498160 | False |

- 90 个正式 run_id 在**恰好一个**账本中出现（覆盖 90/90），费用逐局与 CSV 一致。
- `failed_requests` 4，全部 `unknown_spend=True`：MAP-13 R2、MAP-15 R0、MAP-26 R2、MAP-28 R0；均已用新 run_id 补跑并保留原记录。
- `supplement_005/006` 没有 `experiment_closed`：只表示脚本正常跑完未主动 close，不代表有未结算请求；其 request_reserved 与 settled 一一配对（本审计重算未发现悬挂预留）。
- V8 的 `closed=True` 账本一律只读；V9 不复用、不续跑、不改写。

## 5. 本批结论与后续入口

1. V8 的 90 局、17 成功、分层计数、费用与冻结 hash **可以完整复算**；没有 `UNVERIFIABLE` 项。
2. 唯一需要更正的仓库摘要口径是“账本 settled”应注明是否包含 aborted 预跑；V9 报告采用三口径。
3. 90 局的 prompt/规则/指标 hash 一致，可按同一测量条件做逐图归因；但 **n=3 只是同实例重复**，不是独立场景 seed。
4. 逐局证据包（初始 Observation、每步动作/结果/观察差分、judge 指标）已生成在 `runs/v9/evidence/`，Batch 1–4 的每图审计必须引用其中的具体决策序号。
