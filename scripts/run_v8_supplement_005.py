"""V8 第六个账本：完成 MAP-28–30 的剩余 9 局。

用户已明确授权充足预算、无总额限制，并要求全部跑完后统一汇报。
本账本只补跑尚无正式结果的 `(map, replicate)`；每局新 run_id，旧记录保留。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT / "runs" / "v8"
SUPPLEMENT = V8 / "supplement_005"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_v8_90 as base  # noqa: E402

ROOTS = [
    V8 / "experiments" / "episodes",
    V8 / "supplement_001" / "experiments" / "episodes",
    V8 / "supplement_002" / "experiments" / "episodes",
    V8 / "supplement_003" / "experiments" / "episodes",
    V8 / "supplement_004" / "experiments" / "episodes",
    SUPPLEMENT / "experiments" / "episodes",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def merged_attempts() -> dict[tuple[str, int], list[dict[str, Any]]]:
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


def main() -> int:
    if (SUPPLEMENT / "ledger.jsonl").exists():
        raise SystemExit("supplement_005 ledger already exists; refusing to reuse.")
    SUPPLEMENT.mkdir(parents=True, exist_ok=True)
    base.EXPERIMENT_ROOT = SUPPLEMENT / "experiments"
    base.EPISODE_ROOT = base.EXPERIMENT_ROOT / "episodes"
    base.LEDGER_PATH = SUPPLEMENT / "ledger.jsonl"
    base.RUN_MANIFEST_PATH = base.EXPERIMENT_ROOT / "run_manifest.json"
    base.CHECKPOINT_DIR = base.EXPERIMENT_ROOT / "checkpoints"
    base.scan_attempts = merged_attempts
    sys.argv = ["run_v8_supplement_005.py"]
    print(
        json.dumps(
            {
                "supplement_ledger": str(base.LEDGER_PATH),
                "already_formal": sum(
                    1
                    for items in merged_attempts().values()
                    if base.formal_outcome(items) is not None
                ),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    time.sleep(60)
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())


