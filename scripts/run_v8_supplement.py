"""V8 补跑：在独立补充账本中完成被 provider 中断的正式局。

原账本 `runs/v8/ledger.jsonl` 已因 `InternalServerError`（unknown spend）封账。
本脚本不重开该账本，而是新建 `runs/v8/supplement_001/ledger.jsonl`，只运行
尚无正式结果的 `(map, replicate)`；每局使用新的 run_id 与目录，原失败记录保留。

实现方式：复用冻结的 `scripts/run_v8_90.py`，只替换输出根与尝试扫描函数；
不修改冻结的运行时代码或 prompt。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT / "runs" / "v8"
SUPPLEMENT = V8 / "supplement_001"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_v8_90 as base  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def merged_attempts() -> dict[tuple[str, int], list[dict[str, Any]]]:
    attempts: dict[tuple[str, int], list[dict[str, Any]]] = {}
    roots = [
        V8 / "experiments" / "episodes",
        SUPPLEMENT / "experiments" / "episodes",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/episode_manifest.json")):
            manifest = read_json(path)
            key = (str(manifest.get("map_id")), int(manifest.get("replicate_id", 0)))
            attempts.setdefault(key, []).append(manifest)
    return attempts


def main() -> int:
    SUPPLEMENT.mkdir(parents=True, exist_ok=True)
    base.EXPERIMENT_ROOT = SUPPLEMENT / "experiments"
    base.EPISODE_ROOT = base.EXPERIMENT_ROOT / "episodes"
    base.LEDGER_PATH = SUPPLEMENT / "ledger.jsonl"
    base.RUN_MANIFEST_PATH = base.EXPERIMENT_ROOT / "run_manifest.json"
    base.CHECKPOINT_DIR = base.EXPERIMENT_ROOT / "checkpoints"
    base.scan_attempts = merged_attempts
    sys.argv = ["run_v8_supplement.py"]
    print(
        json.dumps(
            {
                "supplement_ledger": str(base.LEDGER_PATH),
                "experiment_root": str(base.EXPERIMENT_ROOT),
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
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
