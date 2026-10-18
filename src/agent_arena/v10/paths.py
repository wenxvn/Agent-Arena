"""V10 路径常量：V8/V9 只读，V10 只写自己的目录。"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
V8_RUNS = REPO_ROOT / "runs" / "v8"
V9_RUNS = REPO_ROOT / "runs" / "v9"
V10_RUNS = REPO_ROOT / "runs" / "v10"
V10_DOCS = REPO_ROOT / "docs" / "v10"

#: 冻结范围：V10 期间这些路径下的任何文件都不得变化。
FROZEN_ROOTS: tuple[str, ...] = (
    "runs/v8",
    "runs/v9",
    "docs/v8",
    "docs/v9",
    "src/agent_arena/v8",
    "src/agent_arena/v9",
    "src/agent_arena/worlds/scenario_v8",
    "src/agent_arena/worlds/scenario_v4",
    "worlds/v4",
)

__all__ = [
    "FROZEN_ROOTS",
    "REPO_ROOT",
    "V8_RUNS",
    "V9_RUNS",
    "V10_DOCS",
    "V10_RUNS",
]
