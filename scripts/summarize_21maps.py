"""Aggregate the 21-map x 5-seed matrix from persisted traces (offline, no LLM)."""

from __future__ import annotations

import glob
import json
import os
from collections import defaultdict
from statistics import mean, median

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    ok: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    bad: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for path in glob.glob(os.path.join(REPO, "runs", "muse-21maps-*", "episode_*.json")):
        cfg = os.path.basename(os.path.dirname(path)).replace("muse-21maps-", "")
        if cfg in ("smoke", "probe"):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        row = (int(data.get("seed", -1)), int(data.get("executed_action_count", -1)),
               int(data.get("invalid_output_count", 0)))
        (ok if data.get("outcome") == "success" else bad)[cfg].append(row)
    total = 0
    print("config         n/5   mean    med  steps  bad_seeds invalid")
    for cfg in sorted(set(ok) | set(bad)):
        good = sorted(ok[cfg])
        failed = sorted(bad[cfg])
        total += len(good)
        steps = [row[1] for row in good]
        invalid = sum(row[2] for row in good + failed)
        summary = "-"
        if steps:
            summary = f"{mean(steps):.1f} {median(steps)} {steps}"
        print(cfg, f"{len(good)}/5", summary,
              [row[0] for row in failed], invalid)
    print("TOTAL", total, "/ 105")


if __name__ == "__main__":
    main()
