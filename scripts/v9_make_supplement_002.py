"""生成 V9 MiMo 第二个补充账本：只跑剩余的非 MAP-12 episode。

排除 MAP-12 的 v9_fixed 臂：该图在两次独立请求中都在 ~20 决策遇到 provider
`InternalServerError` 并触发 unknown spend；按“不得无限重跑”的原则不再重试。
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import v9_make_manifest as main_manifest  # noqa: E402

MAIN = ROOT / "docs" / "v9" / "mimo-preregistration.json"
SUPPLEMENT_1 = ROOT / "docs" / "v9" / "mimo-supplement-001.json"
OUTPUT = ROOT / "docs" / "v9" / "mimo-supplement-002.json"
V9 = ROOT / "runs" / "v9"


def _episode_roots() -> list[Path]:
    roots = [V9 / "experiments" / "episodes"]
    for supplement in sorted(V9.glob("supplement_*")):
        candidate = supplement / "experiments" / "episodes"
        if candidate.is_dir():
            roots.append(candidate)
    return roots


def completed_specs() -> set[tuple[str, int, str]]:
    specs: set[tuple[str, int, str]] = set()
    for root in _episode_roots():
        for path in root.glob("*/episode_manifest.json"):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest["status"] in {
                "unknown_provider_spend",
                "provider_error",
                "provider_error_limit",
                "budget_closed",
            }:
                continue
            specs.add(
                (
                    str(manifest["map_id"]),
                    int(manifest["replicate_id"]),
                    str(manifest["arm"]),
                )
            )
    return specs


def main() -> None:
    main_manifest_doc = json.loads(MAIN.read_text(encoding="utf-8"))
    supplement_1 = json.loads(SUPPLEMENT_1.read_text(encoding="utf-8"))
    done = completed_specs()
    remaining = [
        item
        for item in supplement_1["episodes"]
        if (item["map_id"], item["replicate_id"], item["arm"]) not in done
    ]
    remaining = [
        item
        for item in remaining
        if not (item["map_id"] == "MAP-12" and item["arm"] == "v9_fixed")
    ]
    supplement: dict[str, Any] = {
        "experiment_label": "V9-PILOT-001-SUPPLEMENT-002",
        "created_at": datetime.now(UTC).isoformat(),
        "commit": main_manifest_doc["commit"],
        "model": main_manifest_doc["model"],
        "provider": main_manifest_doc["provider"],
        "temperature": main_manifest_doc["temperature"],
        "budget_cny": "10",
        "max_episodes": len(remaining),
        "reason": (
            "supplement_001 在 MAP-12 R0 v9_fixed 第 19 次请求再次遇到 provider "
            "InternalServerError 并按 UNKNOWN_PROVIDER_SPEND 封账。MAP-12 的 v9_fixed 臂"
            "两次独立尝试均在 ~20 决策失败，按“不得无限重跑”不再重试；本补充账本只执行"
            "其余尚未完成的 episode。"
        ),
        "stop_rules": main_manifest_doc["stop_rules"],
        "analysis_plan": main_manifest_doc["analysis_plan"],
        "episodes": remaining,
        "runtime_hashes": main_manifest.runtime_hashes(
            {item["map_id"] for item in remaining}
        ),
        "decision_budgets": {
            item["map_id"]: item["decision_budget"] for item in remaining
        },
    }
    payload = {key: value for key, value in supplement.items() if key != "manifest_hash"}
    supplement["manifest_hash"] = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    OUTPUT.write_text(
        json.dumps(supplement, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)
    print(f"remaining={len(remaining)}")
    for item in remaining:
        print(item["map_id"], item["replicate_id"], item["arm"])


if __name__ == "__main__":
    main()
