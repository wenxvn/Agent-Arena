# V10：30 图核心机制重构、难度校准与多 Seed 有效性验证

- 规格：`研究提纲/V10：30图核心机制重构、难度校准与多Seed有效性验证.md`（用户文件，未纳入 Git）
- 起始 HEAD：`2fa4df2726c486d5064a3db9b3965dc27bbd2898`（main）；工作分支 `v10-validity`
- 原则：V8/V9 只读（`docs/v10/freeze-manifest.json` 守卫）；V10 独立 runtime、指标、账本与 run_id；不按通关率改规则；`n=3` 只作描述；全部 `agent_reviewed`

## 进度

| Batch | 内容 | 状态 | commit | 费用 |
|---|---|---|---|---|
| 0 | 基线审计、冻结清单、状态矩阵、决策登记 | 完成 | 见 git log `feat(v10): batch 0` | ¥0 |
| 1 | MAP-03 / MAP-18 | 未开始 | | |
| 2 | MAP-06 / MAP-15 / MAP-21 | 未开始 | | |
| 3 | 古堡 28–30 | 未开始 | | |
| 4 | 其余 NEEDS_REDESIGN | 未开始 | | |
| 5 | NEEDS_MORE_EVIDENCE 与 VALIDATED 复核 | 未开始 | | |
| 6 | 指标治理 | 未开始 | | |
| 7 | 多 seed 定标 | 未开始 | | |
| 8 | 有界 MiMo | 未开始 | | |
| 9 | 最终报告 | 未开始 | | |

## 文件

| 文件 | 内容 |
|---|---|
| `baseline-audit.md` | Batch 0：HEAD、质量基线、冻结、V8/V9 证据可达性、seed 现状 |
| `decision-register.md` | 规则变更 vs 接口/指标修复的逐图登记 |
| `freeze-manifest.json` | V8/V9 逐文件 sha256 与树 hash |
| `map-status-matrix.csv/.md/.json` | 30 图状态矩阵（字段见提纲 §2.4） |

## 复现

```powershell
.\.venv\Scripts\python.exe -m agent_arena.v10.freeze verify      # 冻结校验
.\.venv\Scripts\python.exe -m agent_arena.v10.baseline_audit     # V8/V9 只读复算
.\.venv\Scripts\python.exe -m agent_arena.v10.status             # 生成状态矩阵
.\.venv\Scripts\python.exe -m pytest tests/test_v10_*.py -q
```

`runs/v10/` 与 `runs/v8`、`runs/v9` 一样不纳入 Git；文档中引用的数字都可由上述命令在本机复算。
