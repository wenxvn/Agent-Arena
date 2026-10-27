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

## 2. Batch 2–12

> 后续批次在此追加。
