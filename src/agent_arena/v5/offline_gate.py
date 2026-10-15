"""Content-addressed offline validation gate for paid V5 execution."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from agent_arena.worlds.scenario_v4.catalog import MAP_IDS, map_source_hashes

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GATE_PATH = Path("runs/v5/frozen_offline_gate.json")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _frozen_paths() -> list[Path]:
    paths = {
        REPOSITORY_ROOT / "AGENTS.md",
        REPOSITORY_ROOT / "pyproject.toml",
        REPOSITORY_ROOT / "uv.lock",
        REPOSITORY_ROOT / "worlds" / "v4" / "README.md",
        REPOSITORY_ROOT / "worlds" / "v4" / "AGENTS.md",
        REPOSITORY_ROOT / "src" / "agent_arena" / "AGENTS.md",
        REPOSITORY_ROOT / "docs" / "workflow.md",
        REPOSITORY_ROOT / "docs" / "specs" / "0018-v5-six-map-measurement.md",
        REPOSITORY_ROOT / "docs" / "v5" / "00-repo-audit.md",
        REPOSITORY_ROOT / "docs" / "v5" / "design-discrepancies.md",
        REPOSITORY_ROOT / "docs" / "v5" / "README.md",
        REPOSITORY_ROOT / "docs" / "v5" / "runtime-contract.md",
        REPOSITORY_ROOT / "docs" / "v5" / "capability-validity.md",
        REPOSITORY_ROOT / "docs" / "v5" / "next-24-maps.md",
        REPOSITORY_ROOT / "研究提纲" / "V5能力测量体系测试.md",
    }
    for package_root in (
        REPOSITORY_ROOT / "src" / "agent_arena",
        REPOSITORY_ROOT / "tests",
    ):
        paths.update(path for path in package_root.rglob("*.py") if path.is_file())
    paths.update(
        REPOSITORY_ROOT / "scripts" / name
        for name in (
            "freeze_v5_offline_gate.py",
            "run_v5_pilot.py",
            "validate_v4_runtime.py",
            "validate_v5_solvers.py",
        )
    )
    accepted_map_suffixes = {".md", ".yaml", ".yml", ".json", ".jsonl", ".py"}
    for map_id in MAP_IDS:
        map_root = REPOSITORY_ROOT / "worlds" / "v4" / map_id
        paths.update(
            path
            for path in map_root.rglob("*")
            if path.is_file() and path.suffix.lower() in accepted_map_suffixes
        )
    missing = sorted(path for path in paths if not path.is_file())
    if missing:
        raise FileNotFoundError(f"Frozen offline gate input is missing: {missing[0]}")
    return sorted(paths)


def frozen_file_hashes() -> dict[str, str]:
    return {
        path.relative_to(REPOSITORY_ROOT).as_posix(): _sha256(path.read_bytes())
        for path in _frozen_paths()
    }


def gate_digest(gate: dict[str, Any]) -> str:
    payload = {key: value for key, value in gate.items() if key != "frozen_gate_hash"}
    return _sha256(_canonical_bytes(payload))


def runtime_tree_digest(file_hashes: dict[str, str]) -> str:
    return _sha256(_canonical_bytes(file_hashes))


def load_and_validate_gate(path: Path | None = None) -> dict[str, Any]:
    gate_path = path or REPOSITORY_ROOT / GATE_PATH
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Frozen offline gate is missing or malformed.") from exc
    if not isinstance(gate, dict) or gate.get("status") != "passed":
        raise RuntimeError("Frozen offline gate did not pass.")
    if gate.get("frozen_gate_hash") != gate_digest(gate):
        raise RuntimeError("Frozen offline gate content hash does not match.")
    if gate.get("runtime_commit") != git_head():
        raise RuntimeError("Git HEAD changed after the offline gate was frozen.")
    expected_files = gate.get("source_file_sha256")
    if not isinstance(expected_files, dict) or expected_files != frozen_file_hashes():
        raise RuntimeError("A frozen V5 source, prompt, map, test, or protocol file changed.")
    if gate.get("runtime_tree_hash") != runtime_tree_digest(expected_files):
        raise RuntimeError("Frozen runtime tree hash does not match the source manifest.")
    if gate.get("map_source_sha256") != map_source_hashes():
        raise RuntimeError("A registered V4 map source hash changed.")
    checks = gate.get("checks")
    required_checks = {
        "scoped_ruff",
        "mypy",
        "pytest",
        "v4_oracle_replay",
        "independent_solvers",
        "fake_api_dry_run",
        "git_diff_check",
    }
    check_names = (
        {item.get("name") for item in checks if isinstance(item, dict)}
        if isinstance(checks, list)
        else set()
    )
    if (
        not isinstance(checks, list)
        or not required_checks.issubset(check_names)
        or any(not isinstance(item, dict) or item.get("exit_code") != 0 for item in checks)
    ):
        raise RuntimeError("Offline gate validation checks are incomplete or failed.")
    if not gate.get("dependency_lock_unchanged_from_head"):
        raise RuntimeError("Dependency manifests changed after the project lock was validated.")
    return gate
