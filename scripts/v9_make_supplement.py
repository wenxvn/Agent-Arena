"""生成 V9 MiMo 补充账本的预登记（只包含主实验未完成的 episode）。"""

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
RESULTS = ROOT / "runs" / "v9" / "mimo_results.json"
OUTPUT = ROOT / "docs" / "v9" / "mimo-supplement-001.json"


def main() -> None:
    manifest = json.loads(MAIN.read_text(encoding="utf-8"))
    results = json.loads(RESULTS.read_text(encoding="utf-8"))["results"]
    completed = {
        (item["map_id"], item["replicate_id"], item["arm"])
        for item in results
        if item["status"] not in {"unknown_provider_spend", "provider_error", "budget_closed"}
    }
    remaining = [
        item
        for item in manifest["episodes"]
        if (item["map_id"], item["replicate_id"], item["arm"]) not in completed
    ]
    supplement: dict[str, Any] = {
        "experiment_label": "V9-PILOT-001-SUPPLEMENT-001",
        "created_at": datetime.now(UTC).isoformat(),
        "commit": manifest["commit"],
        "model": manifest["model"],
        "provider": manifest["provider"],
        "temperature": manifest["temperature"],
        "budget_cny": "10",
        "max_episodes": len(remaining),
        "reason": (
            "主账本在 MAP-12 R1 v8_compat 第 29 次请求遇到 provider InternalServerError，"
            "按规则以 UNKNOWN_PROVIDER_SPEND 关闭；不重开旧账本，补充账本只执行预登记中"
            "尚未完成的 episode。"
        ),
        "stop_rules": manifest["stop_rules"],
        "analysis_plan": manifest["analysis_plan"],
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
