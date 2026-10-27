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

## 1. Batch 1–12

> 后续批次在此追加。
