"""Batch entry point: `python scripts/run_episode.py run ...`.

Exists so parallel launchers don't need nested quoting
(`python -c "from agent_arena.cli import app; app()"` breaks under
Start-Process -Command). Run from the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_arena.cli import app

if __name__ == "__main__":
    app()
