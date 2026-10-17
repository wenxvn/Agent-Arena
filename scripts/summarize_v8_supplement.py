"""合并原账本与补充账本，重建 V8 的 90 行注册表。

原账本因 unknown spend 封账；补充账本只包含缺失局。本脚本只读两份 ledger 与
两个 episode 根，不调用 Provider、不改写任何 episode。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT / "runs" / "v8"
ORIGINAL = V8 / "experiments" / "episodes"
SUPPLEMENT = V8 / "supplement_001"
SUPPLEMENT_2 = V8 / "supplement_002"
SUPPLEMENT_3 = V8 / "supplement_003"
SUPPLEMENT_4 = V8 / "supplement_004"
ROOTS = [ORIGINAL, *sorted(V8.glob("supplement_*/experiments/episodes"))]
LEDGERS = [V8 / "ledger.jsonl", *sorted(V8.glob("supplement_*/ledger.jsonl"))]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import summarize_v8 as base  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def merged_manifests() -> dict[tuple[str, int], list[dict[str, Any]]]:
    attempts: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for root in ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/episode_manifest.json")):
            if (path.parent / "SUPERSEDED.json").exists():
                continue
            manifest = read_json(path)
            key = (str(manifest.get("map_id")), int(manifest.get("replicate_id", 0)))
            attempts.setdefault(key, []).append(manifest)
    return attempts


def merged_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in LEDGERS:
        if path.is_file():
            events.extend(
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
    return events


def main() -> int:
    base.scan_manifests = merged_manifests
    base.ledger_events = merged_events
    code = base.main()
    registry = read_json(V8 / "registry.json")
    experiment_ids = []
    for event in merged_events():
        experiment_id = event.get("experiment_id")
        if (
            event.get("event") == "experiment_created"
            and experiment_id not in experiment_ids
        ):
            experiment_ids.append(experiment_id)
    registry["experiment_ids"] = experiment_ids
    ledgers: dict[str, Any] = {}
    for path in LEDGERS:
        if not path.is_file():
            continue
        events = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        key = "original" if path.parent == V8 else path.parent.name
        ledgers[key] = {
            "path": path.relative_to(ROOT).as_posix(),
            **base.ledger_snapshot(events),
            "event_count": len(events),
        }
    registry["ledgers"] = ledgers
    (V8 / "registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "experiment_ids": experiment_ids,
                "formal_episodes": registry["formal_episodes_completed"],
                "gaps": len(registry["gaps"]),
                "settled_cost": registry["ledger"]["settled_cost"],
                "requests": registry["ledger"]["request_attempts"],
            },
            ensure_ascii=False,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
