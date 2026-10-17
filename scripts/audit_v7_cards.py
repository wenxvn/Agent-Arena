"""Reproducible self-review audit for the 30 V7 design cards.

This is not a human sign-off. It checks the structural claims that can be
verified offline: required sections, metric coverage, numeric hand-example
sections, front-matter status, and cross-card construct similarity.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any

from agent_arena.v7.metrics import registry

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "docs" / "v7" / "maps"
REQUIRED_SECTIONS = tuple(f"## {index}." for index in range(1, 14))
METRIC_REF = re.compile(r"`(map\d{2}\.(?!py\b)[a-z0-9_]+)`")


def _section(text: str, number: int) -> str:
    match = re.search(rf"^## {number}\..*?$(.*?)(?=^## \d+\.|\Z)", text, re.M | re.S)
    return match.group(1) if match else ""


def _is_generic(metric_id: str) -> bool:
    return metric_id.endswith(
        (
            ".completion_ticks",
            ".legal_action_rate",
            ".fuel_consumed",
            ".query_budget_overruns",
        )
    )


def audit() -> dict[str, Any]:
    cards: dict[str, str] = {}
    findings: list[str] = []
    constructs: list[tuple[str, str]] = []
    specific_constructs: list[tuple[str, str]] = []
    for map_id in (f"MAP-{index:02d}" for index in range(1, 31)):
        path = CARDS / f"{map_id}.md"
        if not path.exists():
            findings.append(f"{map_id}: missing card")
            continue
        text = path.read_text(encoding="utf-8")
        cards[map_id] = text
        headings = tuple(line[:6] for line in text.splitlines() if line.startswith("## "))
        for required in REQUIRED_SECTIONS:
            if not any(heading.startswith(required) for heading in headings):
                findings.append(f"{map_id}: missing section {required}")
        declared = {spec.metric_id for spec in registry.specs_for(map_id)}
        referenced = set(METRIC_REF.findall(text))
        if declared - referenced:
            findings.append(f"{map_id}: card misses metrics {sorted(declared - referenced)}")
        if referenced - declared:
            findings.append(
                f"{map_id}: card has unregistered metrics {sorted(referenced - declared)}"
            )
        for number in (5, 6, 7):
            if not re.search(r"\d", _section(text, number)):
                findings.append(f"{map_id}: section {number} has no concrete number")
        for spec in registry.specs_for(map_id):
            constructs.append((spec.metric_id, spec.construct_name))
            if not _is_generic(spec.metric_id):
                specific_constructs.append((spec.metric_id, spec.construct_name))

    max_similarity = 0.0
    max_pair = ("", "")
    for index, (left_id, left) in enumerate(specific_constructs):
        for right_id, right in specific_constructs[index + 1 :]:
            ratio = difflib.SequenceMatcher(None, left, right).ratio()
            if ratio > max_similarity:
                max_similarity = ratio
                max_pair = (left_id, right_id)

    return {
        "cards": len(cards),
        "metrics": len(constructs),
        "generic_metric_families": [
            "completion_ticks",
            "legal_action_rate",
            "fuel_consumed",
            "query_budget_overruns",
        ],
        "max_specific_construct_similarity": round(max_similarity, 6),
        "max_specific_construct_pair": list(max_pair),
        "findings": findings,
    }


def main() -> int:
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
