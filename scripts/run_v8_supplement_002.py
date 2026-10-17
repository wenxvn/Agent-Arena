"""V8 第三次、也是最后一次补跑：独立账本 supplement_002。

授权边界（用户 2026-10-17 确认）：
- 只补跑剩余 48 局（MAP-15 R0–R2 与 MAP-16–30）；
- 每局新 run_id，保留原失败记录；
- 若再出现 1 次 unknown spend，或费用接近 ¥10，永久停止，不创建 supplement_003。

复用冻结的 `scripts/run_v8_90.py`，只替换输出根与尝试扫描函数。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT / "runs" / "v8"
SUPPLEMENT = V8 / "supplement_002"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_v8_90 as base  # noqa: E402

ROOTS = [
    V8 / "experiments" / "episodes",
    V8 / "supplement_001" / "experiments" / "episodes",
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
            manifest = read_json(path)
            key = (str(manifest.get("map_id")), int(manifest.get("replicate_id", 0)))
            attempts.setdefault(key, []).append(manifest)
    return attempts


def main() -> int:
    if (SUPPLEMENT / "ledger.jsonl").exists():
        raise SystemExit("supplement_002 ledger already exists; refusing to reuse.")
    SUPPLEMENT.mkdir(parents=True, exist_ok=True)
    base.EXPERIMENT_ROOT = SUPPLEMENT / "experiments"
    base.EPISODE_ROOT = base.EXPERIMENT_ROOT / "episodes"
    base.LEDGER_PATH = SUPPLEMENT / "ledger.jsonl"
    base.RUN_MANIFEST_PATH = base.EXPERIMENT_ROOT / "run_manifest.json"
    base.CHECKPOINT_DIR = base.EXPERIMENT_ROOT / "checkpoints"
    base.scan_attempts = merged_attempts
    sys.argv = ["run_v8_supplement_002.py"]
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
