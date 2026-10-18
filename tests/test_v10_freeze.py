"""V10 冻结守卫：V8/V9 的已跟踪文件在 V10 期间不得变化。"""

from __future__ import annotations

from agent_arena.v10 import freeze
from agent_arena.v10.paths import FROZEN_ROOTS


def test_manifest_covers_all_frozen_roots() -> None:
    manifest = freeze.load()
    assert set(manifest["roots"]) == set(FROZEN_ROOTS)
    for root in manifest["roots"].values():
        assert root["file_count"] == len(root["files"])


def test_tracked_v8_v9_files_are_unchanged() -> None:
    report = freeze.verify(include_runs=False)
    drift = {name: item for name, item in report.items() if item["state"] == "drift"}
    assert drift == {}


def test_local_runs_are_unchanged_or_absent() -> None:
    report = freeze.verify(include_runs=True)
    for name in ("runs/v8", "runs/v9"):
        assert report[name]["state"] in {"unchanged", "absent"}, report[name]
