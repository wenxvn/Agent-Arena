"""V13 运行时测试：分页索引、SDK 自检、压力数据隔离与一键验收。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent_arena.lab.v13.perf import (
    performance_markdown,
    stress_index,
    synthesize_history,
)
from agent_arena.lab.v13.sdkcheck import check_plugin_factory, error_hint, run_sdk_checks
from agent_arena.lab.v13.selfcheck import run_checks
from agent_arena.web.index import RunIndex, page_rows


# ------------------------------------------------------------------- pagination
def _history(tmp_path: Path, count: int = 40) -> Path:
    base = tmp_path / "web"
    synthesize_history(base, count)
    return base


def test_index_paginates_without_loading_everything(tmp_path: Path) -> None:
    base = _history(tmp_path, 40)
    index = RunIndex(base)
    first = index.page(offset=0, limit=10)
    assert first["total"] == 40
    assert len(first["rows"]) == 10
    assert first["has_more"] is True
    last = index.page(offset=30, limit=10)
    assert len(last["rows"]) == 10
    assert last["has_more"] is False


def test_index_filters_and_aggregates(tmp_path: Path) -> None:
    base = _history(tmp_path, 60)
    index = RunIndex(base)
    page = index.page(map_id="MAP-16", state="FAILED", limit=5)
    assert all(row["map_id"] == "MAP-16" and row["state"] == "FAILED" for row in page["rows"])
    aggregate = index.aggregate()
    assert aggregate["runs"] == 60
    assert sum(aggregate["by_map"].values()) == 60
    assert aggregate["cost_unknown_runs"] >= 0


def test_index_caches_until_directory_changes(tmp_path: Path) -> None:
    base = _history(tmp_path, 20)
    index = RunIndex(base)
    index.refresh()
    rebuilds = index.stats.rebuilds
    index.page(limit=5)
    index.page(limit=5)
    assert index.stats.rebuilds == rebuilds
    synthesize_history(base, 1, seed=99)
    index.invalidate()
    index.refresh()
    assert index.stats.runs == 21


def test_index_lazy_page_matches_full_page(tmp_path: Path) -> None:
    """懒加载第一页与全量排序必须逐行一致（否则翻页会跳记录）。"""

    base = _history(tmp_path, 30)
    index = RunIndex(base)
    lazy = index.page(offset=0, limit=10)
    full = index.page(offset=0, limit=10, lazy=False)
    assert lazy.get("lazy") is True
    assert [row["run_id"] for row in lazy["rows"]] == [
        row["run_id"] for row in full["rows"]
    ]
    assert lazy["total"] == full["total"]
    # 中间页也要一致（同 created_at 的并列项按 run_id 降序打破）。
    lazy_mid = index.page(offset=20, limit=10)
    full_mid = index.page(offset=20, limit=10, lazy=False)
    assert [row["run_id"] for row in lazy_mid["rows"]] == [
        row["run_id"] for row in full_mid["rows"]
    ]


def test_page_rows_pure_function() -> None:
    rows = [{"run_id": str(index)} for index in range(7)]
    page = page_rows(rows, offset=5, limit=10)
    assert page["total"] == 7
    assert len(page["rows"]) == 2
    assert page["has_more"] is False


def test_stress_refuses_repo_runs_dir() -> None:
    from agent_arena.lab.paths import WEB_RUNS

    with pytest.raises(ValueError):
        synthesize_history(WEB_RUNS / "v13-should-not-exist", 1)


def test_stress_report_has_real_numbers(tmp_path: Path) -> None:
    base = _history(tmp_path, 80)
    result = stress_index(base, label="STRESS_DATA:80")
    payload = result.as_dict()
    assert payload["runs"] == 80
    assert payload["timings"]
    assert payload["peak_memory_kib"] > 0
    markdown = performance_markdown(
        {"counts": [80], "events_per_run": 0, "results": [payload], "note": "合成数据"}
    )
    assert "峰值内存" in markdown
    assert "冷启动" in markdown


def test_stress_history_marks_manifests_as_synthetic(tmp_path: Path) -> None:
    base = _history(tmp_path, 3)
    for directory in base.iterdir():
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["stress_data"] is True


# ------------------------------------------------------------------------ sdk
def test_sdk_selfcheck_passes() -> None:
    report = run_sdk_checks()
    assert report["ok"], [item for item in report["checks"] if not item["ok"]]
    names = {item["name"] for item in report["checks"]}
    assert names == {
        "contract_version",
        "public_observation_only",
        "lifecycle_hooks",
        "version_identity",
        "invalid_action_isolated",
        "budget_and_simulated",
        "exception_isolated",
        "legacy_act_signature",
    }


def test_sdk_error_hints_are_actionable() -> None:
    assert "allowlist" in error_hint("PluginLoadError: nope")
    assert "平铺" in error_hint("invalid_action")
    assert error_hint("unknown failure") == ""


def test_plugin_factory_check_reports_missing_methods() -> None:
    class Empty:
        pass

    problems = check_plugin_factory(lambda: Empty())
    assert problems and "decide" in problems[0]
    assert check_plugin_factory(lambda: type("P", (), {"decide": lambda self, o, c: None})()) == []


def test_plugin_factory_failure_is_reported_not_raised() -> None:
    def boom() -> Any:
        raise RuntimeError("nope")

    problems = check_plugin_factory(boom)
    assert problems and "工厂调用失败" in problems[0]


# ------------------------------------------------------------------- selfcheck
def test_v13_selfcheck_all_green() -> None:
    report = run_checks()
    failed = [item for item in report["checks"] if not item["ok"]]
    assert report["ok"], failed
    assert report["failed"] == 0
    names = {item["name"] for item in report["checks"]}
    for required in (
        "contract_v13",
        "history_reproduction",
        "ledger_reproduction",
        "map30_ladder",
        "six_map_validity",
        "policies_v13",
        "ablation_templates",
        "comparability",
        "taxonomy_capability",
        "report",
        "ledger_tooling",
        "sdk",
        "pagination",
        "replicate_flow",
        "simulated_isolation",
        "exports_recompute",
    ):
        assert required in names, required
