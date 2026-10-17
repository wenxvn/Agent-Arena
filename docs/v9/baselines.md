# V9 基线与消融结果（自动生成）

来源：`runs/v9/baselines/MAP-XX.json`。每图包含 Oracle 回放、20 个策略种子的
`legal_random`、一个 `public_heuristic` 与（若有）显式消融。
Oracle 只证明存在合法路径，不代表模型能力；`legal_random` 语义非法由环境裁决。

> 环境 seed 固定为注册实例（默认 0）；`legal_random` 只改变策略 RNG 种子。

## 1. 总览

| map | world | 难度 | Oracle | random 成功 | heuristic | 决策 | 终局 | 消融（成功=旁路证据） |
|---|---|---|---:|---:|---|---:|---|---|
| MAP-01 | spaceship | 简单 | 1/1 | 0/20 | ✓ | 15 | REPAIR_CONFIRMED | no_support_handoff=✗ |
| MAP-02 | spaceship | 中等 | 2/2 | 0/20 | ✓ | 10 | DUAL_OBJECTIVE_COMPLETE | no_leak_response=✗ |
| MAP-03 | spaceship | 困难 | 2/2 | 0/20 | ✓ | 30 | ROUTE_CALIBRATED | no_key_memory=✗ |
| MAP-04 | lighthouse | 简单 | 2/2 | 0/20 | ✓ | 9 | SIGNAL_LIT | detour_shortcut=✓, no_phase_wait=✓ |
| MAP-05 | lighthouse | 中等 | 2/2 | 0/20 | ✓ | 19 | THREE_SIGNALS_SENT | no_power_switch=✗, no_window_wait=✗ |
| MAP-06 | lighthouse | 困难 | 4/4 | 0/20 | ✓ | 5 | LAMP_RESTORED | forecast_trusting=✓, shortcut=✓ |
| MAP-07 | abyss | 简单 | 2/2 | 0/20 | ✓ | 6 | LOW_WATER_STABLE | - |
| MAP-08 | abyss | 中等 | 1/1 | 0/20 | ✓ | 5 | LEAK_SEALED | no_hypothesis=✓ |
| MAP-09 | abyss | 困难 | 2/2 | 0/20 | ✓ | 10 | DISTRESS_PACKET_SENT | skip_pump=✓ |
| MAP-10 | polar | 简单 | 2/2 | 0/20 | ✓ | 5 | TRANSMISSION_COMPLETE | no_key_mechanism=✗ |
| MAP-11 | polar | 中等 | 3/3 | 0/20 | ✓ | 7 | FULL_SAFE_RETURN | no_key_mechanism=✗ |
| MAP-12 | polar | 困难 | 2/2 | 0/20 | ✓ | 60 | SURVIVED_AND_RESEARCHED | no_key_mechanism=✗ |
| MAP-13 | pyramid | 简单 | 2/2 | 0/20 | ✓ | 20 | GATE_OPENED | no_direction_nail=✓ |
| MAP-14 | pyramid | 中等 | 2/2 | 0/20 | ✓ | 10 | GATE_OPENED | blind_two_submissions=✓, no_compare=✓ |
| MAP-15 | pyramid | 困难 | 2/2 | 5/20 | ✓ | 10 | GATE_OPENED | no_probe=✓, no_rule_transfer=✓ |
| MAP-16 | subway | 简单 | 1/1 | 0/20 | ✓ | 16 | GATE_OPENED | no_siding=✗ |
| MAP-17 | subway | 中等 | 2/2 | 0/20 | ✓ | 12 | DEMAND_THRESHOLD_MET | no_branch_switch=✗ |
| MAP-18 | subway | 困难 | 1/1 | 0/20 | ✓ | 12 | SERVICE_COMPLETE | ignore_windows=✓ |
| MAP-19 | volcano | 简单 | 2/2 | 0/20 | ✓ | 15 | PRODUCTION_TARGET_MET | no_lag_load_curtailment=✓ |
| MAP-20 | volcano | 中等 | 1/1 | 0/20 | ✓ | 13 | PRODUCTION_TARGET_MET | no_load_management=✗ |
| MAP-21 | volcano | 困难 | 3/3 | 6/20 | ✓ | 2 | EVACUATED_BEFORE_ERUPTION | shortcut_direct_evac=✓ |
| MAP-22 | jungle | 简单 | 1/1 | 0/20 | ✓ | 24 | RETURNED_TO_CAMP_WITH_RUIN_RECORD | no_memory_write=✓ |
| MAP-23 | jungle | 中等 | 2/2 | 0/20 | ✓ | 9 | TRUE_ENTRANCE_FOUND | no_scout=✓ |
| MAP-24 | jungle | 困难 | 2/2 | 0/20 | ✓ | 14 | ALL_ITEMS_DELIVERED | no_replan=✗ |
| MAP-25 | lunar | 简单 | 2/2 | 0/20 | ✓ | 16 | ALL_OBJECTIVES_COMPLETE | no_tool_collection=✗ |
| MAP-26 | lunar | 中等 | 1/1 | 0/20 | ✓ | 11 | ALL_OBJECTIVES_COMPLETE | no_diagnosis=✓ |
| MAP-27 | lunar | 困难 | 2/2 | 0/20 | ✓ | 19 | ALL_OBJECTIVES_COMPLETE | - |
| MAP-28 | castle | 简单 | 1/1 | 0/20 | ✓ | 18 | ALL_CLAIMS_SUPPORTED_AND_CORRECT | no_record=✗ |
| MAP-29 | castle | 中等 | 2/2 | 0/20 | ✓ | 17 | ALL_OBJECTIVES_COMPLETE | no_compare=✗ |
| MAP-30 | castle | 困难 | 1/1 | 0/20 | ✓ | 24 | ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN | no_casebook=✗ |

- Oracle：55/55 个用例真实回放成功。
- `legal_random`：11/600 次运行成功（30 图 × 20 seed）。
- `public_heuristic`：30/30 图成功。

## 2. 关键读法

- **random 成功率高**（MAP-15、MAP-21）说明地图的通过条件可被低成本猜中，是 `LOW_DISCRIMINATION` / `CONSTRUCT_BYPASS` 的直接证据。
- **消融成功**表示“被移除的机制不是通关必需”，但这不等于地图无效：有些机制是效率/安全护栏，不是成功前置。逐图审计 §2/§9 区分了这两种情况。
- **heuristic 成功不等于模型可发现**：策略作者可以使用设计稿常量；审计 §3 标注了哪些常量未公开。早期 MAP-22/26 的策略失败已分别修正为 24/11 决策成功，原因记录在对应审计 §4。

## 3. 复现

```powershell
.\.venv\Scripts\python.exe -m agent_arena.v9.baseline_run
```

单图：`. \.venv\Scripts\python.exe -m agent_arena.v9.baseline_run MAP-09`；
调试策略：`. \.venv\Scripts\python.exe scripts/v9_try_policy.py MAP-09`。

