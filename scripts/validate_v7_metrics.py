"""Offline validation for the V7 metric layer.

Checks, in order:

1. Registry invariants: 30 maps, 154 specs, 44 implemented + 110 design-only,
   unique ids, per-map kind coverage, frozen doc refs.
2. Every design card's front-matter hashes match the frozen V4 sources, and
   every metric id printed in a card exists in that map's registry entry.
3. The 24 maps without a runtime each have a per-map pending-runtime note and a
   row in ``pending-runtime/README.md``.
4. Offline replay: the V6 solvers' actions are re-executed against the real V4
   environments for the six runtime-backed maps, then every metric is recomputed
   from the resulting public trace. No provider, no network, no paid API.

The script only reads files and runs deterministic local code. It never writes
``runs/`` or ``results/``.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v6.catalog import build_environment, get_scene  # noqa: E402
from agent_arena.v6.scenes import all_scenes  # noqa: E402
from agent_arena.v6.solvers import solve  # noqa: E402
from agent_arena.v7.metrics import registry  # noqa: E402
from agent_arena.v7.metrics.schema import (  # noqa: E402
    MetricKind,
    MetricStatus,
    parse_trace_rows,
)
from agent_arena.worlds.scenario_v4 import ScenarioV4Action  # noqa: E402

MAP_IDS = tuple(f"MAP-{index:02d}" for index in range(1, 31))
EXPECTED_RUNTIME_COUNTS = {
    "MAP-08": 7,
    "MAP-16": 8,
    "MAP-18": 8,
    "MAP-22": 7,
    "MAP-26": 7,
    "MAP-30": 7,
}
# Cards MAP-01..07 and MAP-09..15 document a fifth, map-specific cost metric.
EXPECTED_DESIGN_COUNTS = {
    **{f"MAP-{index:02d}": 5 for index in (*range(1, 8), *range(9, 16))},
    **{f"MAP-{index:02d}": 4 for index in (17, 19, 20, 21, 23, 24, 25, 27, 28, 29)},
}
EXPECTED_TOTAL = 154
EXPECTED_IMPLEMENTED = 44
EXPECTED_DESIGN = 110
CONDITIONS = {
    "MAP-08": "hypothesis_table",
    "MAP-16": "constraint_table",
    "MAP-18": "alert_on",
    "MAP-22": "history5_graph_memory",
    "MAP-26": "free_diagnosis",
    "MAP-30": "history5_casebook",
}
EXPECTED_RUNTIME_VALUES: dict[str, dict[str, Any]] = {
    "MAP-08": {"map08.diagnosis_accuracy": 1, "map08.wrong_repair": 0},
    "MAP-16": {"map16.makespan_gap": 0, "map16.deadlock": 0},
    "MAP-18": {"map18.service_rate": 1.0},
    "MAP-22": {"map22.return_success": 1, "map22.path_gap": 0},
    "MAP-26": {
        "map26.repair_success": 1,
        "map26.diagnosis_accuracy": 1,
        "map26.spares_remaining": 1,
    },
    "MAP-30": {
        "map30.q4_recall_accuracy": 1,
        "map30.evidence_chain_coverage": 1.0,
        "map30.investigation_progress": 1.0,
        "map30.unsupported_accusations": 0,
    },
}
# Instances whose spare inventory differs from the map default of one spare.
EXPECTED_INSTANCE_VALUES: dict[str, dict[str, Any]] = {
    "map26_l2_spare_rich": {"map26.spares_remaining": 2},
}
_FRONT_MATTER = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)
_METRIC_REF = re.compile(r"`(map\d{2}\.(?!py\b)[a-z0-9_]+)`")


def _check_registry(failures: list[str]) -> None:
    specs = registry.all_specs()
    by_map: dict[str, list[Any]] = {}
    for spec in specs:
        by_map.setdefault(spec.map_id, []).append(spec)

    if sorted(by_map) != list(MAP_IDS):
        failures.append(f"registry maps are {sorted(by_map)}, expected MAP-01..MAP-30")
        return
    if len(specs) != EXPECTED_TOTAL:
        failures.append(f"registry has {len(specs)} specs, expected {EXPECTED_TOTAL}")
    ids = [spec.metric_id for spec in specs]
    if len(ids) != len(set(ids)):
        failures.append("registry contains duplicate metric ids")

    implemented = [spec for spec in specs if spec.implemented]
    design = [spec for spec in specs if not spec.implemented]
    if len(implemented) != EXPECTED_IMPLEMENTED:
        failures.append(f"implemented specs = {len(implemented)}, expected {EXPECTED_IMPLEMENTED}")
    if len(design) != EXPECTED_DESIGN:
        failures.append(f"design-only specs = {len(design)}, expected {EXPECTED_DESIGN}")
    if registry.implemented_map_ids() != tuple(sorted(EXPECTED_RUNTIME_COUNTS)):
        failures.append(f"implemented maps = {registry.implemented_map_ids()}")

    for map_id in MAP_IDS:
        map_specs = by_map[map_id]
        expected_count = (
            EXPECTED_RUNTIME_COUNTS[map_id]
            if map_id in EXPECTED_RUNTIME_COUNTS
            else EXPECTED_DESIGN_COUNTS[map_id]
        )
        if len(map_specs) != expected_count:
            failures.append(f"{map_id}: {len(map_specs)} specs, expected {expected_count}")
        kinds = {spec.kind for spec in map_specs}
        for kind in (MetricKind.PRIMARY, MetricKind.GUARDRAIL, MetricKind.DIAGNOSTIC):
            if kind not in kinds:
                failures.append(f"{map_id}: missing {kind.value} metric")
        for spec in map_specs:
            prefix = map_id.replace("-", "").lower() + "."
            if not spec.metric_id.startswith(prefix):
                failures.append(f"{spec.metric_id}: id does not start with {prefix}")
            if spec.map_id != map_id:
                failures.append(f"{spec.metric_id}: map_id {spec.map_id} != {map_id}")
            if spec.doc_ref != f"docs/v7/maps/{map_id}.md":
                failures.append(f"{spec.metric_id}: unexpected doc_ref {spec.doc_ref}")
            should_be_implemented = map_id in EXPECTED_RUNTIME_COUNTS
            if spec.implemented != should_be_implemented:
                failures.append(
                    f"{spec.metric_id}: implemented={spec.implemented}, "
                    f"expected {should_be_implemented}"
                )
            if not spec.construct_name or not spec.formula or not spec.source_events:
                failures.append(f"{spec.metric_id}: incomplete metric contract")
        if len({spec.kind for spec in map_specs}) < 3:
            failures.append(f"{map_id}: metric kinds are not differentiated")


def _card_front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.search(text)
    fields: dict[str, str] = {}
    if not match:
        return fields
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields, text


def _check_cards(failures: list[str]) -> None:
    for map_id in MAP_IDS:
        path = ROOT / "docs" / "v7" / "maps" / f"{map_id}.md"
        if not path.exists():
            failures.append(f"{map_id}: design card is missing")
            continue
        fields, text = _card_front_matter(path)
        for key in (
            "map_id",
            "world",
            "nominal_level",
            "capability_primary",
            "source_map_spec_hash",
            "source_design_hash",
            "design_status",
            "review_status",
            "runtime_status",
            "metric_status",
        ):
            if key not in fields:
                failures.append(f"{map_id}: front matter missing {key}")
        if fields.get("map_id") != map_id:
            failures.append(f"{map_id}: front matter map_id mismatch")
        if fields.get("review_status") not in {"pending_human_review", "human_approved"}:
            failures.append(
                f"{map_id}: review_status must be pending_human_review or human_approved"
            )
        has_runtime = map_id in EXPECTED_RUNTIME_COUNTS
        expected_runtime = "runtime" if has_runtime else "design_only"
        if fields.get("runtime_status") != expected_runtime:
            failures.append(
                f"{map_id}: runtime_status={fields.get('runtime_status')}, "
                f"expected {expected_runtime}"
            )
        expected_metric_status = (
            "implemented_offline_validated" if has_runtime else "registered_design"
        )
        if fields.get("metric_status") != expected_metric_status:
            failures.append(
                f"{map_id}: metric_status={fields.get('metric_status')}, "
                f"expected {expected_metric_status}"
            )
        spec_path = ROOT / "worlds" / "v4" / map_id / "map_spec.yaml"
        design_path = ROOT / "worlds" / "v4" / map_id / "DESIGN.md"
        if not spec_path.exists() or not design_path.exists():
            failures.append(f"{map_id}: frozen V4 source files are missing")
            continue
        spec_hash = hashlib.sha256(spec_path.read_bytes()).hexdigest()
        design_hash = hashlib.sha256(design_path.read_bytes()).hexdigest()
        if fields.get("source_map_spec_hash") != spec_hash:
            failures.append(f"{map_id}: source_map_spec_hash does not match map_spec.yaml")
        if fields.get("source_design_hash") != design_hash:
            failures.append(f"{map_id}: source_design_hash does not match DESIGN.md")

        declared = {spec.metric_id for spec in registry.specs_for(map_id)}
        referenced = set(_METRIC_REF.findall(text))
        unknown = sorted(referenced - declared)
        if unknown:
            failures.append(f"{map_id}: card references unregistered metrics {unknown}")
        missing = sorted(declared - referenced)
        if missing:
            failures.append(f"{map_id}: card does not document metrics {missing}")


def _check_pending_runtime(failures: list[str]) -> None:
    path = ROOT / "docs" / "v7" / "pending-runtime" / "README.md"
    if not path.exists():
        failures.append("pending-runtime/README.md is missing")
        return
    text = path.read_text(encoding="utf-8")
    for map_id in MAP_IDS:
        if map_id in EXPECTED_RUNTIME_COUNTS:
            continue
        if f"| {map_id} |" not in text:
            failures.append(f"{map_id}: missing from pending-runtime table")
        note = ROOT / "docs" / "v7" / "pending-runtime" / f"{map_id}.md"
        if not note.exists():
            failures.append(f"{map_id}: pending-runtime note is missing")
            continue
        note_text = note.read_text(encoding="utf-8")
        if map_id not in note_text or "design_only" not in note_text:
            failures.append(f"{map_id}: pending-runtime note lacks map id or design_only status")


def _replay(instance_id: str, condition_id: str) -> tuple[Any, Any]:
    scene = get_scene(instance_id)
    environment = build_environment(scene, condition_id, seed=0)
    solution = solve(instance_id, seed=0)
    rows: list[dict[str, Any]] = [
        {
            "event": "trace_header",
            "map_id": scene.map_id,
            "instance_id": instance_id,
            "condition_id": condition_id,
            "seed": 0,
            "scenario_hash": environment.source_hash,
            "provider": "offline",
            "model": "v6-solver",
        }
    ]
    observation = environment.observe().model_dump(mode="json")
    for index, payload in enumerate(solution.actions):
        step = environment.step(ScenarioV4Action.model_validate(payload, strict=True))
        after = step.observation.model_dump(mode="json")
        rows.append(
            {
                "event": "decision",
                "decision_index": index,
                "action": payload,
                "result": step.result,
                "observation_before": observation,
                "observation_after": after,
                "invalid_output_reason": None,
            }
        )
        observation = after
    judge = {
        "status": "success" if environment.is_success else "failure",
        "judge_state": {
            "true_leak": getattr(environment, "true_leak", None),
            "casebook_visible": getattr(environment, "casebook_visible", None),
        },
    }
    record = parse_trace_rows(rows, judge=judge, source=f"offline:{instance_id}")
    return environment, record


def _check_runtime_replays(failures: list[str]) -> int:
    checked = 0
    runtime_maps = set(EXPECTED_RUNTIME_COUNTS)
    for instance_id, scene in sorted(all_scenes().items()):
        if scene.map_id not in runtime_maps:
            continue
        condition = CONDITIONS[scene.map_id]
        if condition not in scene.paired_conditions:
            condition = scene.paired_conditions[0]
        environment, record = _replay(instance_id, condition)
        checked += 1
        if not environment.is_success:
            failures.append(
                f"{instance_id}: solver replay ended {environment.status.value} "
                f"({environment.terminal_reason})"
            )
            continue
        values = registry.compute_metrics(record)
        expected = {spec.metric_id for spec in registry.specs_for(scene.map_id)}
        if set(values) != expected:
            failures.append(f"{instance_id}: computed ids do not match registry")
        for metric_id, value in values.items():
            if value.status in {MetricStatus.INVALID_TRACE, MetricStatus.UNAVAILABLE}:
                failures.append(f"{instance_id}: {metric_id} is {value.status.value}")
        for metric_id, wanted in {
            **EXPECTED_RUNTIME_VALUES[scene.map_id],
            **EXPECTED_INSTANCE_VALUES.get(instance_id, {}),
        }.items():
            value = values[metric_id]
            if value.status is not MetricStatus.VALID or value.value != wanted:
                failures.append(
                    f"{instance_id}: {metric_id}={value.value!r} "
                    f"({value.status.value}), expected {wanted!r}"
                )
    return checked


def main() -> None:
    failures: list[str] = []
    _check_registry(failures)
    _check_cards(failures)
    _check_pending_runtime(failures)
    replayed = _check_runtime_replays(failures)
    if failures:
        print("V7 metric validation FAILED:")
        for failure in failures:
            print(" -", failure)
        raise SystemExit(1)
    print(
        "V7 metric validation passed: "
        f"{len(registry.all_specs())} specs across {len(MAP_IDS)} maps "
        f"({len(EXPECTED_RUNTIME_COUNTS)} runtime-backed, 24 design-only); "
        f"{replayed} solver episodes replayed offline."
    )


if __name__ == "__main__":
    main()
