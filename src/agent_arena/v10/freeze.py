"""V8/V9 冻结清单：逐文件 sha256 + 每个根目录的树 hash。

用法：
    python -m agent_arena.v10.freeze write    # 生成 docs/v10/freeze-manifest.json
    python -m agent_arena.v10.freeze verify   # 与清单比对，任何漂移即退出码 1

``runs/`` 不在 Git 中；清单同时记录本机 runs 的 hash，验证时若本机缺失
runs 目录则标记为 ``absent``，不当作通过也不当作漂移。
"""

from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from agent_arena.v10.paths import FROZEN_ROOTS, REPO_ROOT, V10_DOCS

MANIFEST_PATH = V10_DOCS / "freeze-manifest.json"


def _files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def snapshot() -> dict[str, Any]:
    roots: dict[str, Any] = {}
    for relative in FROZEN_ROOTS:
        root = REPO_ROOT / relative
        files = {
            path.relative_to(REPO_ROOT).as_posix(): _sha(path) for path in _files(root)
        }
        tree = sha256()
        for name, digest in sorted(files.items()):
            tree.update(name.encode("utf-8"))
            tree.update(b"\0")
            tree.update(digest.encode("ascii"))
            tree.update(b"\n")
        roots[relative] = {
            "present": root.exists(),
            "git_tracked": not relative.startswith("runs/"),
            "file_count": len(files),
            "tree_sha256": tree.hexdigest(),
            "files": files,
        }
    return {"schema": "v10-freeze-1", "roots": roots}


def write() -> dict[str, Any]:
    payload = snapshot()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )
    return payload


def load() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))


def verify(*, include_runs: bool = True) -> dict[str, Any]:
    """Compare the current tree with the committed manifest."""

    expected = load()["roots"]
    current = snapshot()["roots"]
    report: dict[str, Any] = {}
    for relative, frozen in expected.items():
        if relative.startswith("runs/") and not include_runs:
            continue
        now = current.get(relative, {"present": False, "files": {}})
        if relative.startswith("runs/") and not now["present"]:
            report[relative] = {"state": "absent"}
            continue
        changed = sorted(
            name
            for name, digest in frozen["files"].items()
            if now["files"].get(name) not in (None, digest)
        )
        missing = sorted(set(frozen["files"]) - set(now["files"]))
        added = sorted(set(now["files"]) - set(frozen["files"]))
        state = "unchanged" if not (changed or missing or added) else "drift"
        report[relative] = {
            "state": state,
            "changed": changed,
            "missing": missing,
            "added": added,
        }
    return report


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "verify"
    if command == "write":
        payload = write()
        for relative, root in payload["roots"].items():
            print(f"{relative}: {root['file_count']} files {root['tree_sha256']}")
        return 0
    report = verify()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(item["state"] != "drift" for item in report.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
