from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from agent_arena.worlds import create_environment

MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "docs/research/v2/assets/seeded-v3-layout-freeze.csv"
)
AUDIT_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/audit_v3_seeded_layout_freeze.py"
)
FROZEN_MANIFEST_SHA256 = "85967e180a535cc186e8c20e66de223eb74ca2a88ac7a697067c4fda8bb5be98"
EXPECTED_ACTION_COUNTS = {
    "lunar-escape-v3-seeded-zh": {17: 24, 18: 12, 19: 6, 20: 36, 22: 12},
    "pyramid-escape-v3-seeded-zh": {12: 6, 14: 12, 16: 10, 18: 2},
}
EXPECTED_SPLIT_COUNTS = {
    "lunar-escape-v3-seeded-zh": {
        ("simple", "dev"): 24,
        ("simple", "test"): 12,
        ("complex", "dev"): 36,
        ("complex", "test"): 18,
    },
    "pyramid-escape-v3-seeded-zh": {
        ("simple", "dev"): 12,
        ("simple", "test"): 6,
        ("complex", "dev"): 8,
        ("complex", "test"): 4,
    },
}
POPULATIONS = {
    "lunar-escape-v3-seeded-zh": {
        "world": "lunar-escape",
        "size": 90,
        "tools": {"core_cell_a", "core_cell_b", "hex_driver", "torque_driver"},
        "simple_max_actions": 18,
    },
    "pyramid-escape-v3-seeded-zh": {
        "world": "pyramid-escape",
        "size": 30,
        "tools": {"chisel", "sun_cell"},
        "simple_max_actions": 14,
    },
}


def test_v3_seeded_instances_match_frozen_manifest() -> None:
    manifest_bytes = MANIFEST.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(manifest_bytes).hexdigest() == FROZEN_MANIFEST_SHA256

    with MANIFEST.open(encoding="utf-8-sig", newline="") as stream:
        manifest_rows = list(csv.DictReader(stream))

    assert len(manifest_rows) == sum(
        config["size"] for config in POPULATIONS.values()
    )
    rows_by_version: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in manifest_rows:
        rows_by_version[row["world_version"]].append(row)

    all_hashes: set[str] = set()
    for world_version, config in POPULATIONS.items():
        rows = rows_by_version[world_version]
        population_size = config["size"]
        assert len(rows) == population_size
        assert {int(row["seed"]) for row in rows} == set(range(population_size))
        assert len({row["instance_hash"] for row in rows}) == population_size

        bucket_splits: dict[str, set[str]] = defaultdict(set)
        action_counts = Counter(int(row["minimum_actions"]) for row in rows)
        split_counts = Counter(
            (row["difficulty_label"], row["split"]) for row in rows
        )
        assert dict(action_counts) == EXPECTED_ACTION_COUNTS[world_version]
        assert dict(split_counts) == EXPECTED_SPLIT_COUNTS[world_version]
        for row in rows:
            seed = int(row["seed"])
            environment = create_environment(
                config["world"], world_version, seed=seed
            )
            expected_hash = row["instance_hash"]
            assert environment.identity[3] == expected_hash
            assert expected_hash not in all_hashes
            all_hashes.add(expected_hash)

            placements = {
                item.id: item.container_id
                for item in environment.definition.items
            }
            assert placements == json.loads(row["tool_placements_json"])
            assert set(placements) == config["tools"]

            active = set(placements.values())
            expected_active = set(json.loads(row["active_containers_json"]))
            assert len(active) == 2
            assert active == expected_active
            assert active <= set(environment.definition.seed_containers)
            room_ids = {
                object_id
                for room in environment.definition.rooms
                for object_id in room.object_ids
                if object_id in environment.definition.seed_containers
            }
            assert room_ids == active

            counts = Counter(placements.values())
            if len(config["tools"]) == 4:
                assert set(counts.values()) == {2}
            else:
                assert set(counts.values()) == {1}

            minimum_actions = int(row["minimum_actions"])
            expected_difficulty = (
                "simple"
                if minimum_actions <= config["simple_max_actions"]
                else "complex"
            )
            assert row["difficulty_label"] == expected_difficulty
            assert row["split"] in {"dev", "test"}
            bucket_splits[expected_difficulty].add(row["split"])

            cycled = create_environment(
                config["world"], world_version, seed=seed + population_size
            )
            assert cycled.identity[3] == expected_hash

        assert set(bucket_splits) == {"simple", "complex"}
        assert all(splits == {"dev", "test"} for splits in bucket_splits.values())

    assert len(all_hashes) == 120


@pytest.mark.parametrize(
    "arguments",
    [(), ("--output", str(MANIFEST))],
)
def test_freeze_generator_refuses_to_overwrite_frozen_manifest(
    arguments: tuple[str, ...],
) -> None:
    before = hashlib.sha256(
        MANIFEST.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    completed = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), *arguments],
        check=False,
        capture_output=True,
        cwd=MANIFEST.parents[4],
        text=True,
    )
    after = hashlib.sha256(
        MANIFEST.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()

    assert completed.returncode == 2
    assert "冻结清单不能覆盖" in completed.stderr or "拒绝覆盖冻结清单" in completed.stderr
    assert after == before


def test_freeze_verifier_rejects_modified_manifest(tmp_path: Path) -> None:
    modified_manifest = tmp_path / "modified-layout-freeze.csv"
    modified_manifest.write_bytes(MANIFEST.read_bytes().replace(b"lunar", b"Lunar", 1))

    completed = subprocess.run(
        [
            sys.executable,
            str(AUDIT_SCRIPT),
            "--verify-runtime",
            "--output",
            str(modified_manifest),
        ],
        check=False,
        capture_output=True,
        cwd=MANIFEST.parents[4],
        text=True,
    )

    assert completed.returncode == 1
    assert "SHA-256 differs from the pre-registered manifest" in completed.stderr


@pytest.mark.parametrize(
    ("world", "world_version"),
    [
        ("lunar-escape", "lunar-escape-v3-seeded-zh"),
        ("pyramid-escape", "pyramid-escape-v3-seeded-zh"),
    ],
)
def test_v3_seeded_rejects_negative_seed(world: str, world_version: str) -> None:
    with pytest.raises(ValueError, match="non-negative seed"):
        create_environment(world, world_version, seed=-1)
