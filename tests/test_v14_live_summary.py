"""V14.1：LIVE 聚合口径（中断 vs 机制失败）与逐局证据索引。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.summarize_v14_live import LIVE_DIR, VALID, build_manifest, classify_state

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "docs" / "v14" / "live-manifest.json"


def test_classify_state_success_and_censored() -> None:
    assert classify_state(success=True, state="SUCCEEDED") == "completed_success"
    assert classify_state(success=False, state="BUDGET_REACHED") == "budget_censored"
    assert classify_state(success=False, state="FAILED") == "mechanism_failure"


def test_classify_state_separates_infrastructure_interruptions() -> None:
    """Provider 5xx / 取消不是"场景机制失败"，也不进效果分母（DCR-V14-11）。"""

    assert classify_state(success=False, state="PROVIDER_ERROR") == "provider_error"
    assert classify_state(success=False, state="CANCELLED") == "cancelled"
    assert "provider_error" not in VALID
    assert "cancelled" not in VALID


def test_classify_state_never_upgrades_unknown_state() -> None:
    assert classify_state(success=False, state=None) == "mechanism_failure"
    assert classify_state(success=False, state="") == "mechanism_failure"
    # 成功标志优先于 state 文本
    assert classify_state(success=True, state="BUDGET_REACHED") == "completed_success"


def test_manifest_matches_committed_index() -> None:
    if not LIVE_DIR.is_dir():
        pytest.skip("本机没有 runs/v14/live（原始 trace 不入库）")
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    actual = build_manifest()
    assert actual["totals"]["runs"] == 308
    assert actual["totals"]["experiments"] == 43
    assert actual["totals"]["provider_errors"] == 4
    assert actual["ledger"]["settled"] == actual["ledger"]["started"] == 308
    assert actual == expected


def test_manifest_has_no_absolute_paths_or_secrets() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    for needle in ("C:", "D:", "sk-", "Bearer ", "OPENAI_API_KEY"):
        assert needle not in text, f"manifest 含可疑内容：{needle}"
