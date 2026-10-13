from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_seeded_lunar_world_hash_is_stable_across_process_hash_seeds() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source_root = project_root / "src"
    code = (
        f"import sys; sys.path.insert(0, {str(source_root)!r}); "
        "import json; "
        "from agent_arena.worlds.flex import LunarV2SeededEnvironment; "
        "print(json.dumps([LunarV2SeededEnvironment(seed=seed).identity[3] "
        "for seed in (1, 2)]))"
    )
    hashes: list[str] = []

    for hash_seed in ("1", "2"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = hash_seed
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            cwd=project_root,
            env=environment,
            capture_output=True,
            encoding="utf-8",
            text=True,
        )
        hashes.append(result.stdout.strip())

    assert hashes[0] == hashes[1]
    assert json.loads(hashes[0])[0] == json.loads(hashes[0])[1]
