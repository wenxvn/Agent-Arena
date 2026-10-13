"""Offline audit: structural uniqueness of all 30 maps + real-model coverage.

No LLM calls. Reads JSON definitions and existing traces only.
"""

from __future__ import annotations

import glob
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "src", "agent_arena", "worlds", "data")

MAPS = [
    ("spaceship", "spaceship-escape", "spaceship_escape_v1", "spaceship-escape-v2-zh", "easy"),
    ("spaceship", "spaceship-escape", "spaceship_escape_v2", "spaceship-escape-v3-zh", "med"),
    ("spaceship", "spaceship-escape", "spaceship_escape_v3", "spaceship-escape-v4-zh", "hard"),
    ("lighthouse", "lighthouse-escape", "lighthouse_escape_v1", "lighthouse-escape-v1-zh", "easy"),
    ("lighthouse", "lighthouse-escape", "lighthouse_escape_v2", "lighthouse-escape-v2-zh", "med"),
    ("lighthouse", "lighthouse-escape", "lighthouse_escape_v3", "lighthouse-escape-v3-zh", "hard"),
    ("abyss", "abyss-escape", "abyss_escape_easy", "abyss-escape-easy-zh", "easy"),
    ("abyss", "abyss-escape", "abyss_escape_v1", "abyss-escape-v1-zh", "med"),
    ("abyss", "abyss-escape", "abyss_escape_hard", "abyss-escape-hard-zh", "hard"),
]
for key in ["polar", "pyramid", "subway", "volcano", "jungle", "lunar", "castle"]:
    slug = f"{key}-escape"
    file = f"{key}_escape"
    MAPS += [(key, slug, f"{file}_easy", f"{slug}-easy-zh", "easy"),
             (key, slug, f"{file}_v1", f"{slug}-v1-zh", "med"),
             (key, slug, f"{file}_hard", f"{slug}-hard-zh", "hard")]


def main() -> None:
    print("=== structural signatures ===")
    for _key, _slug, file, _ver, _diff in MAPS:
        with open(os.path.join(DATA, f"{file}.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        rooms = {r["id"]: r for r in doc["rooms"]}
        edges = sorted(f"{a}->{b}" for a, r in rooms.items() for b in r["exits"] if a < b)
        terms = [(o["id"], o["room_id"]) for o in doc["objects"] if o["kind"] == "terminal"]
        cont = [(o["id"], o["room_id"]) for o in doc["objects"] if o["kind"] == "container"]
        items = sorted((i["id"], i["container_id"]) for i in doc["items"])
        print(f"{file}: rooms={len(rooms)} code={doc['authorization_code']} "
              f"start={doc['start_room']}")
        print(f"  edges={edges}")
        print(f"  terminals={terms} containers={cont} items={len(items)}")

    print("=== real-model coverage (winning combo) ===")
    for _key, slug, _file, ver, _diff in MAPS:
        ok: set[int] = set()
        combos: set[str] = set()
        n = 0
        for run_dir in ("runs/muse-9maps-*", "runs/muse-21maps-*"):
            for path in glob.glob(os.path.join(REPO, run_dir, "episode_*.json")):
                try:
                    with open(path, encoding="utf-8") as fh:
                        data = json.load(fh)
                except (OSError, ValueError):
                    continue
                prov = data.get("provenance", {})
                ident = (prov.get("world"), data.get("world_version"), data.get("agent"),
                         prov.get("recent_history_window"),
                         prov.get("stuck_recovery_enabled"),
                         prov.get("public_phase_context_enabled"),
                         prov.get("step_limit"), prov.get("model_name"))
                if (ident[0], ident[1]) != (slug, ver):
                    continue
                n += 1
                combos.add(str((ident[2], ident[3], ident[4], ident[5], ident[6], ident[7])))
                if data.get("outcome") == "success":
                    ok.add(int(data.get("seed", -1)))
        print(f"{slug}/{ver}: success_seeds={sorted(ok)} traces={n} combos={combos}")


if __name__ == "__main__":
    main()
