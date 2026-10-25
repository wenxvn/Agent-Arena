"""V12 Lab 路径常量：父实验写 ``runs/lab/``，子局仍写 ``runs/web/``。"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LAB_RUNS = REPO_ROOT / "runs" / "lab"
WEB_RUNS = REPO_ROOT / "runs" / "web"
LAB_DOCS = REPO_ROOT / "docs" / "v12"
LAB_DEMO = LAB_DOCS / "demo"

EXPERIMENT_ID_PATTERN = r"^lab-\d{8}T\d{6}Z-[0-9a-f]{8}$"

__all__ = [
    "EXPERIMENT_ID_PATTERN",
    "LAB_DEMO",
    "LAB_DOCS",
    "LAB_RUNS",
    "REPO_ROOT",
    "WEB_RUNS",
]
