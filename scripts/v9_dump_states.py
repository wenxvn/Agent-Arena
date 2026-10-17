"""打印每图一局 judge_state 的字段与类型，供独立指标复算设计使用。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v9.audit import official_rows  # noqa: E402


def main() -> None:
    for row in official_rows():
        if row.replicate_id != 0:
            continue
        judge = json.loads(Path(row.judge_metrics_path).read_text(encoding="utf-8"))
        state = judge.get("judge_state") or {}
        rendered = {
            key: (
                type(value).__name__,
                value
                if isinstance(value, (int, float, bool, str, type(None)))
                else "...",
            )
            for key, value in sorted(state.items())
        }
        print(f"## {row.map_id} metrics={list((judge.get('metrics') or {}).keys())}")
        print(json.dumps(rendered, ensure_ascii=False))


if __name__ == "__main__":
    main()
