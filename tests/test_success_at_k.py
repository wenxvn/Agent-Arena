"""T2：Success@K 离线裁剪规则的边界单测（纯函数，不调用模型）。"""
from __future__ import annotations


def success_at_k(action_count: int | None, outcome: str, k: int) -> str:
    """返回 'success' | 'fail' | 'censored' | 'N/A'。

    - success 且步数<=K → success；success 但步数>K → fail（预算内未完成）。
    - provider_error/截断且无足够后续证据 → censored。
    - 缺 outcome/步数 → N/A（不填零）。
    """
    if outcome is None or action_count is None:
        return "N/A"
    if outcome == "provider_error":
        return "censored"
    if outcome in ("step_limit", "invalid_action_limit"):
        return "censored"
    if outcome != "success":
        return "N/A"
    return "success" if action_count <= k else "fail"


def test_k_boundary_inclusive() -> None:
    assert success_at_k(30, "success", 30) == "success"
    assert success_at_k(31, "success", 30) == "fail"


def test_provider_error_is_censored_not_fail() -> None:
    assert success_at_k(12, "provider_error", 200) == "censored"
    assert success_at_k(0, "provider_error", 30) == "censored"


def test_truncation_is_censored() -> None:
    assert success_at_k(30, "step_limit", 30) == "censored"
    assert success_at_k(5, "invalid_action_limit", 200) == "censored"


def test_missing_fields_yield_na() -> None:
    assert success_at_k(None, "success", 60) == "N/A"
    assert success_at_k(20, None, 60) == "N/A"  # type: ignore[arg-type]


def test_duplicate_episodes_dedup_rule() -> None:
    """同 (world, seed) 双文件：provider_error 丢、success 留；双 success 取先到。"""
    files = [
        {"seed": 0, "outcome": "provider_error", "action_count": 12},
        {"seed": 0, "outcome": "success", "action_count": 26},
    ]
    kept = [f for f in files if success_at_k(f["action_count"], f["outcome"], 10**9) != "censored"]
    assert [f["action_count"] for f in kept] == [26]
