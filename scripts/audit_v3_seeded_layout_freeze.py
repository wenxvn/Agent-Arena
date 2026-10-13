"""Enumerate proposed V3 seeded layouts and freeze offline difficulty/split."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from itertools import combinations
from math import gcd
from pathlib import Path
from typing import Any, cast

from audit_v2_seeded_overhead import _minimum_route

from agent_arena.worlds import create_environment
from agent_arena.worlds.flex import (
    FlexEnvironment,
    load_lunar_v2_seeded_definition,
    load_pyramid_v2_seeded_definition,
)
from agent_arena.worlds.spaceship_escape import ItemDefinition, ObjectDefinition

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs/research/v2/assets/seeded-v3-layout-freeze.csv"
SPLIT_RATIO_DENOMINATOR = 3
FROZEN_MANIFEST_SHA256 = "85967e180a535cc186e8c20e66de223eb74ca2a88ac7a697067c4fda8bb5be98"

SLOT_POOLS: dict[str, tuple[tuple[str, str], ...]] = {
    "lunar": (
        ("depot_crate", "depot_store"),
        ("spare_crate", "cupola"),
        ("tunnel_cache", "regolith_tunnel"),
        ("telemetry_case", "telemetry_nook"),
        ("reactor_cache", "reactor_bay"),
        ("auxiliary_crate", "aux_bay"),
    ),
    "pyramid": (
        ("relic_chest", "relic_store"),
        ("sand_crate", "mural_hall"),
        ("tunnel_cache", "sand_tunnel"),
        ("survey_case", "survey_nook"),
        ("crypt_crate", "engine_crypt"),
        ("priest_coffer", "priest_cell"),
    ),
}

WORLD_CONFIG: dict[str, dict[str, Any]] = {
    "lunar": {
        "loader": load_lunar_v2_seeded_definition,
        "world_version": "lunar-escape-v3-seeded-zh",
        "world_id": "lunar_escape_v3_seeded",
        "simple_max_actions": 18,
    },
    "pyramid": {
        "loader": load_pyramid_v2_seeded_definition,
        "world_version": "pyramid-escape-v3-seeded-zh",
        "world_id": "pyramid_escape_v3_seeded",
        "simple_max_actions": 14,
    },
}

FIELDS = (
    "world_version",
    "instance_hash",
    "seed",
    "difficulty_label",
    "minimum_actions",
    "minimum_moves",
    "split",
    "active_containers_json",
    "tool_placements_json",
)


def _tool_distributions(
    family: str, tools: tuple[str, ...], container_a: str, container_b: str
) -> list[dict[str, str]]:
    if family == "lunar":
        return [
            {
                **{tool: container_a for tool in left},
                **{tool: container_b for tool in tools if tool not in left},
            }
            for left in combinations(tools, 2)
        ]
    return [
        {tools[0]: container_a, tools[1]: container_b},
        {tools[0]: container_b, tools[1]: container_a},
    ]


def _layout_definition(
    family: str, distribution: dict[str, str]
) -> tuple[Any, tuple[str, ...]]:
    config = WORLD_CONFIG[family]
    definition = config["loader"]()
    slots = SLOT_POOLS[family]
    candidate_ids = {container_id for container_id, _ in slots}
    slot_rooms = dict(slots)
    active_ids = tuple(sorted(set(distribution.values())))

    objects = list(definition.objects)
    known_ids = {item.id for item in objects}
    for container_id, room_id in slots:
        if container_id not in known_ids:
            objects.append(
                ObjectDefinition(
                    id=container_id,
                    room_id=room_id,
                    kind="container",
                    inspect_result="里面装着收纳的维修工具。",
                )
            )

    rooms = []
    for room in definition.rooms:
        object_ids = [
            object_id
            for object_id in room.object_ids
            if object_id not in candidate_ids
        ]
        object_ids.extend(
            container_id
            for container_id in active_ids
            if slot_rooms[container_id] == room.id
        )
        rooms.append(room.model_copy(update={"object_ids": tuple(object_ids)}))

    updated = definition.model_copy(
        update={
            "world_id": config["world_id"],
            "version": "v3-seeded-zh",
            "rooms": tuple(rooms),
            "objects": tuple(objects),
            "containers": tuple(container_id for container_id, _ in slots),
            "seed_containers": tuple(container_id for container_id, _ in slots),
            "items": tuple(
                ItemDefinition(id=tool, container_id=container_id)
                for tool, container_id in sorted(distribution.items())
            ),
        }
    )
    return updated, active_ids


def _enumerate_world(family: str) -> list[dict[str, Any]]:
    definition = WORLD_CONFIG[family]["loader"]()
    tools = tuple(sorted(item.id for item in definition.items))
    containers = tuple(container_id for container_id, _ in SLOT_POOLS[family])
    rows: list[dict[str, Any]] = []
    for container_a, container_b in combinations(containers, 2):
        for distribution in _tool_distributions(
            family, tools, container_a, container_b
        ):
            layout, active_ids = _layout_definition(family, distribution)
            environment = FlexEnvironment(definition=layout)
            minimum_actions, minimum_moves, states_expanded = _minimum_route(
                environment
            )
            config = WORLD_CONFIG[family]
            rows.append(
                {
                    "world_version": config["world_version"],
                    "instance_hash": environment.identity[3],
                    "difficulty_label": (
                        "simple"
                        if minimum_actions <= config["simple_max_actions"]
                        else "complex"
                    ),
                    "minimum_actions": minimum_actions,
                    "minimum_moves": minimum_moves,
                    "states_expanded": states_expanded,
                    "active_containers_json": json.dumps(
                        active_ids, ensure_ascii=False, separators=(",", ":")
                    ),
                    "tool_placements_json": json.dumps(
                        dict(sorted(distribution.items())),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )
            if len(rows) % 15 == 0:
                print(f"{family}: 已穷举 {len(rows)} 个布局", flush=True)
    if len({row["instance_hash"] for row in rows}) != len(rows):
        raise ValueError(f"{family} 存在重复的 stable instance_hash。")
    return rows


def _assign_seed_indices(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(rows, key=lambda row: row["instance_hash"])
    count = len(ordered)
    world_version = ordered[0]["world_version"]
    digest = hashlib.sha256(
        f"agent-arena-v3-seed-map-v1\0{world_version}".encode()
    ).digest()
    stride = int.from_bytes(digest[:8], "big") % count or 1
    while gcd(stride, count) != 1:
        stride = (stride + 1) % count or 1
    offset = int.from_bytes(digest[8:16], "big") % count
    for seed in range(count):
        ordered[(offset + stride * seed) % count]["seed"] = seed


def _freeze_split(rows: list[dict[str, Any]]) -> None:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[(row["world_version"], row["difficulty_label"])].append(row)
    for (world_version, difficulty), bucket in buckets.items():
        ordered = sorted(
            bucket,
            key=lambda row: hashlib.sha256(
                f"agent-arena-v3-heldout-v1\0{world_version}\0{difficulty}\0{row['instance_hash']}".encode()
            ).hexdigest(),
        )
        test_size = max(1, (len(ordered) + SPLIT_RATIO_DENOMINATOR - 1) // SPLIT_RATIO_DENOMINATOR)
        for index, row in enumerate(ordered):
            row["split"] = "test" if index < test_size else "dev"


def _verify_runtime(manifest_path: Path) -> int:
    manifest_sha256 = hashlib.sha256(
        manifest_path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    if manifest_sha256 != FROZEN_MANIFEST_SHA256:
        raise ValueError(
            "冻结清单 SHA-256 differs from the pre-registered manifest. "
            f"Expected {FROZEN_MANIFEST_SHA256}, got {manifest_sha256}."
        )

    with manifest_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["world_version"]].append(row)

    for world_version, version_rows in grouped.items():
        world = world_version.removesuffix("-v3-seeded-zh")
        population_size = len(version_rows)
        seen_hashes: set[str] = set()
        for row in version_rows:
            seed = int(row["seed"])
            environment = cast(
                FlexEnvironment,
                create_environment(world, world_version, seed=seed),
            )
            expected_hash = row["instance_hash"]
            if environment.identity[3] != expected_hash:
                raise ValueError(
                    f"{world_version} seed {seed}: runtime hash differs from frozen manifest."
                )
            if expected_hash in seen_hashes:
                raise ValueError(f"{world_version} repeats an instance hash.")
            seen_hashes.add(expected_hash)

            expected_items = json.loads(row["tool_placements_json"])
            actual_items = {
                item.id: item.container_id
                for item in environment.definition.items
            }
            if actual_items != expected_items:
                raise ValueError(
                    f"{world_version} seed {seed}: runtime tool placement differs."
                )
            expected_active = tuple(json.loads(row["active_containers_json"]))
            actual_active = tuple(sorted(set(actual_items.values())))
            if actual_active != expected_active:
                raise ValueError(
                    f"{world_version} seed {seed}: runtime active containers differ."
                )
            visible_candidates = {
                object_id
                for room in environment.definition.rooms
                for object_id in room.object_ids
                if object_id in environment.definition.seed_containers
            }
            if visible_candidates != set(expected_active):
                raise ValueError(
                    f"{world_version} seed {seed}: inactive containers enter room observations."
                )

            wrapped = cast(
                FlexEnvironment,
                create_environment(
                    world, world_version, seed=seed + population_size
                ),
            )
            if wrapped.identity[3] != expected_hash:
                raise ValueError(
                    f"{world_version} seed cycle differs after {population_size}."
                )

        if len(seen_hashes) != population_size:
            raise ValueError(f"{world_version} did not cover its frozen population.")
        print(f"{world_version}: runtime 与冻结清单 {population_size}/{population_size} 一致")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        help="新候选清单的输出路径；生成模式必须显式指定且不能覆盖冻结清单。",
    )
    parser.add_argument(
        "--verify-runtime",
        action="store_true",
        help="将已生成的 manifest 与运行时 selector、identity、placements 对照。",
    )
    args = parser.parse_args()

    if args.verify_runtime:
        output = args.output or DEFAULT_OUTPUT
        output = output if output.is_absolute() else ROOT / output
        return _verify_runtime(output)

    if args.output is None:
        parser.error("生成候选清单时必须显式指定 --output；冻结清单不能覆盖。")
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.resolve() == DEFAULT_OUTPUT.resolve():
        parser.error("拒绝覆盖冻结清单；请写入新的候选路径。")

    rows: list[dict[str, Any]] = []
    for family in WORLD_CONFIG:
        family_rows = _enumerate_world(family)
        _assign_seed_indices(family_rows)
        rows.extend(family_rows)
    _freeze_split(rows)
    rows.sort(key=lambda row: (row["world_version"], row["seed"]))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    for version in WORLD_CONFIG.values():
        world_rows = [row for row in rows if row["world_version"] == version["world_version"]]
        print(
            version["world_version"],
            f"layouts={len(world_rows)}",
            "actions="
            + str(dict(sorted(Counter(row["minimum_actions"] for row in world_rows).items()))),
            f"difficulty={dict(Counter(row['difficulty_label'] for row in world_rows))}",
            f"split={dict(Counter(row['split'] for row in world_rows))}",
        )
    print(f"冻结清单：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
