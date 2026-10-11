"""Run the 9 redesign maps x 5 seeds until complete (bounded rounds).

Same winning combo as the 21-map matrix. Stops early when every
(config, seed) has a success trace. Usage: python scripts/run_redesign_matrix.py
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
    ("ship-easy", "spaceship-escape", "spaceship-escape-easy-zh"),
    ("ship-med", "spaceship-escape", "spaceship-escape-v1-zh"),
    ("ship-hard", "spaceship-escape", "spaceship-escape-hard-zh"),
    ("light-easy", "lighthouse-escape", "lighthouse-escape-v4-zh"),
    ("light-med", "lighthouse-escape", "lighthouse-escape-v5-zh"),
    ("light-hard", "lighthouse-escape", "lighthouse-escape-v6-zh"),
    ("abyss-easy", "abyss-escape", "abyss-escape-v2-zh"),
    ("abyss-med", "abyss-escape", "abyss-escape-v3-zh"),
    ("abyss-hard", "abyss-escape", "abyss-escape-v4-zh"),
]

MAX_PARALLEL = 21
MAX_ROUNDS = 4


def succeeded() -> set[tuple[str, int]]:
    done: set[tuple[str, int]] = set()
    for path in glob.glob(os.path.join(REPO, "runs", "muse-redesign-*", "episode_*.json")):
        cfg = os.path.basename(os.path.dirname(path)).replace("muse-redesign-", "")
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
    env["OPENAI_SESSION_ID"] = f"muse-redesign-w{wave}-{tag}-s{seed}"
    log_path = os.path.join(REPO, "logs", f"redesign-{tag}-s{seed}-w{wave}.log")
    fh = open(log_path, "w", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, "scripts/run_episode.py", "run",
         "--provider", "openai", "--agent", "memory",
         "--seed", str(seed),
         "--output-dir", f"runs/muse-redesign-{tag}",
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
