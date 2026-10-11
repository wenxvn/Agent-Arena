"""Rerun failed 21-map episodes with a bounded parallel pool.

Queue = every (config, seed) without a success trace. At most MAX_PARALLEL
episodes run concurrently (default 21, proven scale). Each job gets its own
gateway session id. Usage: python scripts/rerun_21maps_pool.py [max_parallel]
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
    ("polar", "polar-escape"),
    ("pyramid", "pyramid-escape"),
    ("subway", "subway-escape"),
    ("volcano", "volcano-escape"),
    ("jungle", "jungle-escape"),
    ("lunar", "lunar-escape"),
    ("castle", "castle-escape"),
]
DIFFS = ["easy", "med", "hard"]
VERSION_OF = {"easy": "easy-zh", "med": "v1-zh", "hard": "hard-zh"}


def succeeded() -> set[tuple[str, int]]:
    done: set[tuple[str, int]] = set()
    for path in glob.glob(os.path.join(REPO, "runs", "muse-21maps-*", "episode_*.json")):
        cfg = os.path.basename(os.path.dirname(path)).replace("muse-21maps-", "")
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if data.get("outcome") == "success":
            done.add((cfg, int(data.get("seed", -1))))
    return done


def main() -> None:
    max_parallel = int(sys.argv[1]) if len(sys.argv) > 1 else 21
    done = succeeded()
    queue: list[tuple[str, str, str, str, int]] = []
    for key, slug in CONFIGS:
        for diff in DIFFS:
            tag = f"{key}-{diff}"
            version = f"{slug}-{VERSION_OF[diff]}"
            for seed in range(5):
                if (tag, seed) not in done:
                    queue.append((tag, slug, version, diff, seed))
    print(f"queue={len(queue)} max_parallel={max_parallel} already_ok={len(done)}", flush=True)

    running: dict[tuple[str, int], subprocess.Popen[str]] = {}
    logs: dict[tuple[str, int], object] = {}
    finished = 0
    attempt = 0
    while queue or running:
        while queue and len(running) < max_parallel:
            tag, slug, version, _diff, seed = queue.pop(0)
            attempt += 1
            env = dict(os.environ)
            env["AGENT_ARENA_WORLD"] = slug
            env["AGENT_ARENA_WORLD_VERSION"] = version
            env["AGENT_ARENA_STEP_LIMIT"] = "0"
            env["AGENT_ARENA_RESPONSE_FORMAT"] = "json_schema"
            env["OPENAI_SESSION_ID"] = f"muse-21maps-r2-{tag}-s{seed}"
            log_path = os.path.join(REPO, "logs", f"21-{tag}-s{seed}-r2.log")
            fh = open(log_path, "w", encoding="utf-8")
            logs[(tag, seed)] = fh
            proc = subprocess.Popen(
                [sys.executable, "scripts/run_episode.py", "run",
                 "--provider", "openai", "--agent", "memory",
                 "--seed", str(seed),
                 "--output-dir", f"runs/muse-21maps-{tag}",
                 "--autonomous", "--recent-history", "5",
                 "--stuck-recovery", "--phase-context"],
                cwd=REPO, env=env, stdout=fh, stderr=subprocess.STDOUT,
                text=True,
            )
            running[(tag, seed)] = proc
            print(f"started {tag}-s{seed} (queue_left={len(queue)})", flush=True)
        time.sleep(20)
        for job, proc in list(running.items()):
            if proc.poll() is not None:
                fh = logs.pop(job)
                assert not isinstance(fh, str)
                fh.close()
                del running[job]
                finished += 1
                print(f"done {job[0]}-s{job[1]} rc={proc.returncode} "
                      f"({finished} finished, {len(queue)} queued)", flush=True)
    print(f"all reruns launched and finished: {finished}", flush=True)


if __name__ == "__main__":
    main()
