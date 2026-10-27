# V14 验证记录

> 只记录**实际运行**的命令与输出摘要。失败保留原样，不事后修饰。
> 平台：Windows 11 + Git Bash（MSYS2）；本地启动器 `python 3.11.9`，项目解释器由 `uv` 固定为 3.13。

## 0. 基线（Batch 0，2026-10-27，HEAD `60c9ba2`）

| 命令 | 结果 |
|---|---|
| `uv lock --check` | 通过 |
| `uv run ruff check .` | 通过 |
| `uv run mypy src` | 323 files，0 issues |
| `uv run pytest -q` | **1639 passed**，122.25s |
| `uv run python -m agent_arena.v10.freeze verify` | 全部 `unchanged` |
| `uv run python -m agent_arena.v10.recompute --check` | 1093/1093 match，30 maps |
| `uv run python -m agent_arena.v10.independent_check --check` | 0 violations，144 seed instances |
| `uv run python scripts/verify_v11.py` | 7/7 |
| `uv run python scripts/verify_v12.py` | 15/15 |
| `uv run python scripts/verify_v13.py` | 18/18 |

远端：`lab-e2e` 连续 7 次 `success`（见 `ci-evidence.md`）。

## 1. Batch 1（P0-2，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run python scripts/audit_v14_data.py --write` | 生成 4 份文档；221 局 / ¥10.97 |
| `uv run pytest -q tests/test_v14_data_validity.py` | **14 passed** |
| `uv run pytest -q tests/test_v13_*.py` | **114 passed** |
| `uv run python scripts/verify_v13.py` | 18/18 |
| `uv run ruff check <改动文件>` | 通过 |
| `uv run mypy src/agent_arena/lab/v13/validity.py src/agent_arena/lab/v14/` | 0 issues |

关键输出：

```text
records: 138
pooled_maps: [MAP-16, MAP-18, MAP-22, MAP-30]
trigger_unknown_maps: [MAP-08, MAP-16, MAP-18, MAP-22, MAP-26, MAP-30]
budget totals: runs=221 upper=103.75 estimate=9.08 recomputed=10.97
declared_total_runs: 229 -> 221（修正后一致）
plans: A 54 / B 186 / C 221
```

## 6. Batch 6–12

> 后续批次在此追加。

## 2. Batch 2（P0-3，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run pytest -q tests/test_v14_conditions.py` | **23 passed** |
| `uv run pytest -q`（批次边界全量） | **1676 passed**，134.89s |
| `uv run ruff check .` | 通过 |
| `uv run mypy src` | 326 files，0 issues |
| `uv run python scripts/audit_v14_data.py --write` | 生成 `pairing-audit.md`，illegal_seeds = [] |

配对复核实测（只读历史）：

```text
memory.v1 消融      pairs=2 comparable=0 descriptive=2 incomparable=0 single_switch=true
planning.v1 消融    pairs=2 comparable=0 descriptive=2 incomparable=0 single_switch=true
reflection.v1 消融  pairs=2 comparable=0 descriptive=2 incomparable=0 single_switch=true
```

## 3. Batch 3（P0-4，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run pytest -q tests/test_v14_agent_studies.py` | **17 passed** |
| `uv run python scripts/audit_v14_agents.py --write` | 生成 `agent-studies.md` / `.json` |
| `uv run ruff check src/agent_arena/lab/v14/` | 通过 |
| `uv run mypy src/agent_arena/lab/v14/` | 0 issues |

SIMULATED 机制结果（零请求）：

```text
context_only_on   decisions=7 requests=7 route=north,east,south,west rejected=1 invalid=1 render=7
context_only_off  decisions=7 requests=7 route=(empty)  bottleneck=NO_RECORD
env_write_on      decisions=8 requests=6 route=north,east,south,west write_accepted=2 route_recall=1.0
disabled          decisions=7 requests=7 render=0 bottleneck=DISABLED
memory_block_leaks = []（全部臂）
all_single_factor = true
plan: 36 局 / PLANNED_ONLY / 实验费用上限 ¥5.00
```

## 4. Batch 4（P0-5，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run pytest -q tests/test_v14_planning_study.py` | **14 passed** |
| `uv run python scripts/audit_v14_agents.py --write` | 生成 Planning 段 |
| `uv run ruff check .` | 通过 |
| `uv run mypy src` | 328 files，0 issues |
| `uv run pytest -q`（批次边界全量） | **1707 passed**，178.23s |

SIMULATED 触发链（12 决策脚本，零请求）：

```text
adaptive     requests=15 planner=3 plans=3 ttl_skip=1 triggers=[initial, no_progress, public_progress]
initial_only requests=13 planner=1 plans=1
periodic_4   requests=15 planner=3
periodic_12  requests=13 planner=1
disabled     requests=12 planner=0
budget_guard ttl_skip=4 budget_skip=2 planner=3
max_plans    plans=2（封顶）
plan: 72 局（MAP-16 主测 54 + MAP-18 对照 18）/ PLANNED_ONLY
```

## 5. Batch 5（P0-6，2026-10-27）

| 命令 | 结果 |
|---|---|
| `uv run pytest -q tests/test_v14_reflection_study.py` | **15 passed** |
| `uv run ruff check .` | 通过 |
| `uv run mypy src` | 329 files，0 issues |
| `uv run pytest -q`（批次边界全量） | **1722 passed**，189.79s |

SIMULATED 六态（12 决策，零请求）：

```text
disabled        requests=12 triggered=0 exposure=DISABLED
trigger_only    requests=12 triggered=9 reflection_requests=0 exposure=TREATMENT_TRIGGERED
reflection_on   requests=15 triggered=3 cooldown_blocked=6 recoveries=2
long_failure_on requests=15 triggered=3 quota_blocked=1 recoveries=3
no_trigger_on   triggered=0 exposure=NO_TREATMENT_EXPOSURE
plan: 27 局（两臂子集 18）/ PLANNED_ONLY
```
