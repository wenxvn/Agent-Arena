from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v6.offline_gate import (  # noqa: E402
    frozen_file_hashes,
    gate_digest,
    git_head,
    runtime_tree_digest,
)


def run_check(label: str, command: list[str], *, timeout: int = 900) -> dict[str, Any]:
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
    )
    output = (completed.stdout + completed.stderr).strip()
    return {
        "name": label,
        "command": command,
        "exit_code": completed.returncode,
        "output_tail": output[-3_000:],
    }


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(serialized)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def main() -> int:
    python = sys.executable
    checks = [
        run_check("scoped_ruff", [python, "-m", "ruff", "check", "src", "scripts", "tests"]),
        run_check("mypy", [python, "-m", "mypy", "src"]),
        run_check("pytest", [python, "-m", "pytest", "-q"]),
        run_check("v4_oracle_replay", [python, "scripts/validate_v4_runtime.py"]),
        run_check("v5_solvers", [python, "scripts/validate_v5_solvers.py"]),
        run_check("v6_instances", [python, "scripts/validate_v6_instances.py"]),
        run_check("v6_leakage", [python, "scripts/validate_v6_leakage.py"]),
        run_check("v6_fake_dry_run", [python, "scripts/run_v6_pilot.py", "--dry-run"]),
        run_check("git_diff_check", ["git", "diff", "--check", "HEAD~1", "HEAD"]),
    ]
    lock_diff = subprocess.run(
        ["git", "diff", "HEAD", "--quiet", "--", "pyproject.toml", "uv.lock"],
        cwd=ROOT,
        check=False,
    )
    success = all(item["exit_code"] == 0 for item in checks) and lock_diff.returncode == 0
    gate: dict[str, Any] = {
        "schema_version": "v6_offline_gate_v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "passed" if success else "failed",
        "runtime_commit": git_head(),
        "runtime_tree_hash": "",
        "source_file_sha256": frozen_file_hashes(),
        "dependency_lock_unchanged_from_head": lock_diff.returncode == 0,
        "checks": checks,
    }
    gate["runtime_tree_hash"] = runtime_tree_digest(gate["source_file_sha256"])
    gate["frozen_gate_hash"] = gate_digest(gate)
    _atomic_write(ROOT / "runs" / "v6" / "frozen_offline_gate.json", gate)
    for item in checks:
        print(f"{item['name']}: exit={item['exit_code']}")
    print(f"offline_gate: {gate['status']} {gate['frozen_gate_hash']}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
