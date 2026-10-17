# V8：30 图定稿与 MiMo 三重复验收

V8 的目标是让 30 张地图**规则冻结、运行时可玩、指标可计算**，并对每图完成 3 次真实 MiMo
重复运行（30×3=90）。本目录只记录 V8 的事实与产物，不改写 V2/V4/V5/V6/V7 的历史。

## 1. 交付物索引

| 文件 | 内容 |
|---|---|
| `runtime-contract.md` | 24 张新运行时的实现契约与反换皮要求 |
| `baseline-audit.md` | 开始前 HEAD、V7 声明核查、发现并修复的基线差异 |
| `dcr-resolution.md` | V7 的 12 项 DCR + V8 新增裁决 |
| `runtime-matrix.md` | 30 行运行时状态矩阵（世界/难度/构念/规则 hash/审阅） |
| `metric-matrix.md` | 154 条指标的类型、方向、公式、分母、缺失/截尾规则 |
| `offline-validation.md` | 30 图离线统一门禁、pytest/Ruff/mypy、费用 dry-run |
| `mimo-preregistration.md` | 90 局的模型、预算、条件、补跑与停机预登记 |
| `mimo-90-results.md` | 90 行真实 MiMo 结果、逐图汇总、缺口 |
| `failure-analysis.md` | 失败类型分布、地板/天花板、Token/费用与异常 |
| `final-acceptance.md` | 30 图定稿表、逐图验收结论、未解决风险 |
| `maps/MAP-XX-final.md` | 每图定稿：机制、公开/私有、动作、结算、失败码、指标、Oracle、MiMo 3 局 |
| `extra-fixtures.json` | 冻结后补充的 12 条失败/边界手算用例（不改变运行时 hash） |

机器可读产物（`runs/` 默认不入 Git）：

- `runs/v8/freeze_manifest.json`：30 图 `scenario_hash, rule_hash, prompt_hash, metric_schema_hash, oracle_hash, commit`、`runtime_tree_hash` 与 `freeze_hash`。
- `runs/v8/offline_gate.json`：离线门禁逐图结果。
- `runs/v8/ledger.jsonl`：独立 append-only 账本，¥10 硬上限。
- `runs/v8/experiments/episodes/<run_id>/`：每局不可覆盖的 trace、judge metrics、V8 metrics、manifest。
- `runs/v8/registry.json`：90 行正式结果、所有尝试、缺口、账本快照。
- `runs/v8/results_90.csv` / `results_90.md`：90 行结果表。

## 2. 复现顺序

```powershell
# 1. 单图自检（30 次）
.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-01

# 2. 全量测试与离线门禁
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/validate_v8_offline.py
.\.venv\Scripts\python.exe scripts/check_v8_extra_cases.py

# 3. 冻结（离线门禁必须 30/30）
.\.venv\Scripts\python.exe scripts/freeze_v8.py

# 4. 正式 90 局（可恢复；先 dry-run 校验冻结）
.\.venv\Scripts\python.exe scripts/run_v8_90.py --dry-run
.\.venv\Scripts\python.exe scripts/run_v8_90.py

# 5. 重建注册表、结果表与逐图文档
.\.venv\Scripts\python.exe scripts/summarize_v8.py
.\.venv\Scripts\python.exe scripts/report_v8_maps.py
```

## 3. 关键口径

- **一次正式条件/图**：MAP-08/16/18/22/26/30 使用各自能力承载条件，其余图 `default`；不混入 V5–V7 消融。
- **重复而非 Seed**：`seed=0` 固定，`replicate_id=0/1/2`；三次是同图重复运行，不是三个独立场景实例。
- **失败合法**：MiMo 失败、截尾、机制失败都保留；只有不可解、泄漏或无效 Trace 才不得作为正式结果。
- **不比较不同地图的原始指标**：10 世界×3 难度不是同一量表；每图独立主指标。
- **n=3**：只描述重复运行，不做显著性断言；Oracle 成功率不是 MiMo 能力。
- **预算**：独立账本、请求前预留、结算后释放、未知消费立即封账；不突破 ¥10。
- **补跑**：仅确认未计费的传输/供应商中断，最多 15 局；模型正常失败不补跑。

## 4. 当前状态

状态由 `final-acceptance.md` 与 `runs/v8/registry.json` 给出；本文件不预先宣称 90/90。
