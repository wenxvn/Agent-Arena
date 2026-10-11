"""Run the remaining maps (6 flex pilots + seeded ship) x 5 seeds until complete.

Same winning combo. Stops early when every (config, seed) has a success
trace. Usage: python scripts/run_flex_matrix.py
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIGS = [
    ("lunar-v2", "lunar-escape", "lunar-escape-v2-zh"),
    ("lunar-v2s", "lunar-escape", "lunar-escape-v2-seeded-zh"),
    ("castle-v2", "castle-escape", "castle-escape-v2-zh"),
    ("castle-v2s", "castle-escape", "castle-escape-v2-seeded-zh"),
    ("pyramid-v2", "pyramid-escape", "pyramid-escape-v2-zh"),
    ("pyramid-v2s", "pyramid-escape", "pyramid-escape-v2-seeded-zh"),
    ("ship-seeded", "spaceship-escape", "spaceship-escape-v5-zh-seeded"),
]

MAX_PARALLEL = 21
MAX_ROUNDS = 5


def succeeded() -> set[tuple[str, int]]:
    done: set[tuple[str, int]] = set()
    for path in glob.glob(os.path.join(REPO, "runs", "muse-flex-*", "episode_*.json")):
        cfg = os.path.basename(os.path.dirname(path)).replace("muse-flex-", "")
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if data.get("outcome") == "success":
            done.add((cfg, int(data.get("seed", -1))))
    return done


def launch(tag: str, slug: str, version: str, seed: int, wave: int) -> subprocess.Popen[str]:
    env = dict(os.environ)
    env["AGENT_ARENA_WORLD"] = slug
    env["AGENT_ARENA_WORLD_VERSION"] = version
    env["AGENT_ARENA_STEP_LIMIT"] = "0"
    env["AGENT_ARENA_RESPONSE_FORMAT"] = "json_schema"
    env["OPENAI_SESSION_ID"] = f"muse-flex-w{wave}-{tag}-s{seed}"
    log_path = os.path.join(REPO, "logs", f"flex-{tag}-s{seed}-w{wave}.log")
    fh = open(log_path, "w", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, "scripts/run_episode.py", "run",
         "--provider", "openai", "--agent", "memory",
         "--seed", str(seed),
         "--output-dir", f"runs/muse-flex-{tag}",
         "--autonomous", "--recent-history", "5",
         "--stuck-recovery", "--phase-context"],
        cwd=REPO, env=env, stdout=fh, stderr=subprocess.STDOUT, text=True,
    )


def main() -> None:
    for wave in range(1, MAX_ROUNDS + 1):
        done = succeeded()
        queue = [(t, s, v, seed) for (t, s, v) in CONFIGS for seed in range(5)
                 if (t, seed) not in done]
        print(f"wave {wave}: missing={len(queue)}", flush=True)
        if not queue:
            break
        running: list[tuple[tuple[str, int], subprocess.Popen[str]]] = []
        index = 0
        while index < len(queue) or running:
            while index < len(queue) and len(running) < MAX_PARALLEL:
                tag, slug, version, seed = queue[index]
                index += 1
                running.append(((tag, seed), launch(tag, slug, version, seed, wave)))
                print(f"  started {tag}-s{seed}", flush=True)
            time.sleep(20)
            for job, proc in list(running):
                if proc.poll() is not None:
                    running.remove((job, proc))
                    print(f"  done {job[0]}-s{job[1]} rc={proc.returncode} "
                          f"({len(running)} running)", flush=True)
    missing = [(t, seed) for (t, _s, _v) in CONFIGS for seed in range(5)
               if (t, seed) not in succeeded()]
    print(f"final missing: {missing}", flush=True)


if __name__ == "__main__":
    main()
