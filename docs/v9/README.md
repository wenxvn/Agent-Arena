# V9：30 图难度定标、失败归因与能力区分度优化

- 执行对象：DeepSeek V4.1 Flash
- 起始 HEAD：`35e37117e890c8e165a708d89204a01cf1801466`
- V8 冻结：`b174a6f734fbc6b2f1d25c0b6beba40f62431ce0572b281a40c0c3049c32dbb0`
- 原则：V8 只读；V9 独立 hash、账本与实验 ID；不按通关率改规则；`n=3` 只作描述

## 目录

| 文件 | 内容 |
|---|---|
| `README.md` | 本文件：范围、文件索引、复现命令 |
| `baseline-audit.md` | Batch 0：90 局复算、版本/费用/分层 |
| `run-index.csv` | 90 局逐局索引（run_id、hash、费用、失败码、指标五态） |
| `data-integrity.md` | 可验证性、hash 一致性、五态与口径问题 |
| `audit-template.md` | 逐图审计 12 节规范 |
| `maps/MAP-XX-audit.md` | 30 份逐图审计（机制、公开/隐藏信息、Triple Trace 归因、DCR 候选） |
| `failure-taxonomy.md` | A–I 首因统计与 22 张 0/3 分组 |
| `construct-validity.md` | 30 图构念是否被真正测量（FORCED/OPTIONAL/BYPASS/BLOCKED） |
| `difficulty-calibration.md` | 10 世界三难度递进审计 |
| `baseline-protocol.md` | Oracle/随机/启发式/消融协议与独立性 |
| `baselines.md` | 55 Oracle、600 次随机、30 个启发式、消融总表 |
| `metric-independent-check.md` | 120 条独立复算与指标缺陷 |
| `map-status-matrix.md` | VALIDATED/NEEDS_MORE_EVIDENCE/NEEDS_REDESIGN/BLOCKED |
| `intervention-register.md` | DCR 索引、已实施/待裁定/未实施缺陷 |
| `dcr/DCR-*.md` | 14 份全局与地图级 DCR（另有 25/26/27 专项候选） |
| `mimo-preregistration.json` | 29 局预登记（manifest hash、runtime hash、停止规则） |
| `mimo-supplement-001.json` | 主账本 unknown spend 后剩余 16 局的隔离补充预登记 |
| `mimo-supplement-002.json` | 排除 MAP-12 `v9_fixed` 后剩余 13 局的第二个补充预登记 |
| `mimo-results.md` | 有界 MiMo V9 复测结果与前后对照 |
| `final-report.md` | 最终报告：结论、限制、V10 方向 |

## 代码与产物

| 路径 | 内容 |
|---|---|
| `src/agent_arena/v9/audit.py` | Batch 0 复算 |
| `src/agent_arena/v9/evidence.py` | 30 图证据包（`runs/v9/evidence/`） |
| `src/agent_arena/v9/prompts.py` | V9 公开信息补充（`v8_compat` / `v9_fixed` 两臂） |
| `src/agent_arena/v9/metrics.py` | 截尾投影修正 + V8 只读重算 |
| `src/agent_arena/v9/metric_overlay.py` | 6 图指标叠加（不覆盖旧值） |
| `src/agent_arena/v9/metric_checks/` | 120 条独立复算 |
| `src/agent_arena/v9/baselines.py` | Oracle/随机/启发式/消融执行器 |
| `src/agent_arena/v9/policies/world_*.py` | 30 个公开启发式 + 消融 |
| `src/agent_arena/v9/budget.py` | 独立 ¥10 append-only 账本 |
| `src/agent_arena/v9/runner.py` | 有界 MiMo runner（`arm` 区分两臂） |
| `runs/v9/` | 基线、证据、重算、MiMo 结果与账本 |
| `tests/test_v9_*.py` | 审计、基线、runner、叠加、独立复算测试 |

## 复现命令

```powershell
# Batch 0：90 局复算与证据包
.\.venv\Scripts\python.exe -m agent_arena.v9.audit
.\.venv\Scripts\python.exe -m agent_arena.v9.evidence
.\.venv\Scripts\python.exe -m agent_arena.v9.report

# 指标：截尾重算 + 叠加
.\.venv\Scripts\python.exe -m agent_arena.v9.metrics
.\.venv\Scripts\python.exe -c "from agent_arena.v9.metric_checks.base import run_all; print(run_all())"

# 30 图基线
.\.venv\Scripts\python.exe -m agent_arena.v9.baseline_run
.\.venv\Scripts\python.exe scripts/v9_report_baselines.py

# 单图调试
.\.venv\Scripts\python.exe scripts/v9_try_policy.py MAP-09
.\.venv\Scripts\python.exe scripts/v9_show_map.py MAP-09

# 有界 MiMo（预登记）
.\.venv\Scripts\python.exe scripts/run_v9_mimo.py --dry-run
.\.venv\Scripts\python.exe scripts/run_v9_mimo.py

# 测试
.\.venv\Scripts\python.exe -m pytest tests/test_v9_*.py -q
```

## 边界

- 30 份逐图审计是 `agent_reviewed`；**没有** `human_approved`，也没有把用户写成审核人。
- V9 的公开信息补充只影响 `v9_fixed` 臂；`v8_compat` 臂保持 V8 原文，用于同期对照。
- 指标叠加不覆盖 V8 的 `v8_metrics.json`；旧值与新值并列报告。
- 真实 MiMo 只用于预登记的 29 局诊断/对照，不构成 V9 主实验，也不用于“试到成功”。
