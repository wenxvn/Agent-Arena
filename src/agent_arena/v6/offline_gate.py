"""Content-addressed offline validation gate for the separately registered V6 pilot."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from agent_arena.worlds.scenario_v4.catalog import MAP_IDS

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GATE_PATH = Path("runs/v6/frozen_offline_gate.json")


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
        REPOSITORY_ROOT / "docs" / "specs" / "0019-v6-measurement-validity.md",
    }
    for package_root in (
        REPOSITORY_ROOT / "src" / "agent_arena" / "v6",
        REPOSITORY_ROOT / "src" / "agent_arena" / "worlds" / "scenario_v4",
    ):
        paths.update(path for path in package_root.rglob("*.py") if path.is_file())
    paths.add(REPOSITORY_ROOT / "src" / "agent_arena" / "v5" / "runner.py")
    paths.add(REPOSITORY_ROOT / "src" / "agent_arena" / "llm" / "protocol.py")
    paths.update(
        REPOSITORY_ROOT / "scripts" / name
        for name in (
            "freeze_v6_offline_gate.py",
            "run_v6_pilot.py",
            "validate_v4_runtime.py",
            "validate_v6_instances.py",
            "validate_v6_leakage.py",
        )
    )
    paths.update(
        REPOSITORY_ROOT / "tests" / name
        for name in (
            "test_scenario_v4_runtime.py",
            "test_v5_pilot_controls.py",
            "test_v6_instances.py",
            "test_v6_leakage.py",
        )
    )
    docs_root = REPOSITORY_ROOT / "docs" / "v6"
    if docs_root.is_dir():
        paths.update(path for path in docs_root.rglob("*.md") if path.is_file())
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
        raise FileNotFoundError(f"Frozen V6 gate input is missing: {missing[0]}")
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
        raise RuntimeError("Frozen V6 offline gate is missing or malformed.") from exc
    if not isinstance(gate, dict) or gate.get("status") != "passed":
        raise RuntimeError("Frozen V6 offline gate did not pass.")
    if gate.get("frozen_gate_hash") != gate_digest(gate):
        raise RuntimeError("Frozen V6 offline gate content hash does not match.")
    if gate.get("runtime_commit") != git_head():
        raise RuntimeError("Git HEAD changed after the V6 offline gate was frozen.")
    expected_files = gate.get("source_file_sha256")
    if not isinstance(expected_files, dict) or expected_files != frozen_file_hashes():
        raise RuntimeError("A frozen V6 source, prompt, map, test, or protocol file changed.")
    if gate.get("runtime_tree_hash") != runtime_tree_digest(expected_files):
        raise RuntimeError("Frozen V6 runtime tree hash does not match the source manifest.")
    checks = gate.get("checks")
    required_checks = {
        "scoped_ruff",
        "mypy",
        "pytest",
        "v4_oracle_replay",
        "v5_solvers",
        "v6_instances",
        "v6_leakage",
        "v6_fake_dry_run",
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
        raise RuntimeError("V6 offline gate validation checks are incomplete or failed.")
    return gate
