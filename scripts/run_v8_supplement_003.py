"""V8 第四次补跑：MAP-22 接口修复后的重跑 + MAP-23–30。

背景：MAP-22 的三次正式局全部因 `write_memory` 事实 schema 未公开而
`schema_fault_limit`。按 V8 提纲“三局都因接口误导或无效 schema 失败则修复后
重新冻结重跑”，旧三局标记为 superseded，不计入正式结果。

本账本只跑：
- MAP-22 R0–R2（新 prompt，含 fact schema）；
- MAP-23–30 的 24 局。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT / "runs" / "v8"
SUPPLEMENT = V8 / "supplement_003"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_v8_90 as base  # noqa: E402

ROOTS = [
    V8 / "experiments" / "episodes",
    V8 / "supplement_001" / "experiments" / "episodes",
    V8 / "supplement_002" / "experiments" / "episodes",
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
        raise SystemExit("supplement_003 ledger already exists; refusing to reuse.")
    SUPPLEMENT.mkdir(parents=True, exist_ok=True)
    base.EXPERIMENT_ROOT = SUPPLEMENT / "experiments"
    base.EPISODE_ROOT = base.EXPERIMENT_ROOT / "episodes"
    base.LEDGER_PATH = SUPPLEMENT / "ledger.jsonl"
    base.RUN_MANIFEST_PATH = base.EXPERIMENT_ROOT / "run_manifest.json"
    base.CHECKPOINT_DIR = base.EXPERIMENT_ROOT / "checkpoints"
    base.scan_attempts = merged_attempts
    sys.argv = ["run_v8_supplement_003.py"]
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
