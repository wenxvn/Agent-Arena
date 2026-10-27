"""V14 Batch 6：LIVE 方案 A 预注册（零请求）。"""

from __future__ import annotations

import pytest

from agent_arena.lab.paths import REPO_ROOT
from agent_arena.lab.v13.history import load_v12_history
from agent_arena.lab.v14.data_audit import map_unit_costs
from agent_arena.lab.v14.live_plan import (
    LIVE_PENDING,
    PLAN_A_GROUPS,
    RECOMMENDED_CAP_CNY,
    STATUS_PLANNED,
    plan_a_arms,
    plan_a_cost_estimate,
    plan_a_markdown,
    plan_a_preflight,
    plan_a_seed_audit,
    plan_a_single_factor_checks,
    plan_a_specs,
)

REAL_RUNS = REPO_ROOT / "docs" / "v12" / "real-runs"

@pytest.fixture(scope="module")
def unit_costs():
    if not REAL_RUNS.is_dir():
        pytest.skip("需要 docs/v12/real-runs 只读历史")
    return map_unit_costs(load_v12_history())

# ------------------------------------------------------------------- structure
def test_plan_a_has_three_groups_and_two_arms_each() -> None:
    arms = plan_a_arms()
    assert list(arms) == list(PLAN_A_GROUPS)
    for group, items in arms.items():
        assert len(items) == 2, group
        assert {item["arm_id"] for item in items} == {
            f"{group}-control",
            f"{group}-treatment",
        } if group != "E3" else {
            "E3-control",
            "E3-treatment",
        }

def test_every_group_is_single_factor() -> None:
    checks = plan_a_single_factor_checks()
    assert len(checks) == 3
    assert all(item["ok"] for item in checks)
    by_group = {item["group"]: item for item in checks}
    assert by_group["E1-a"]["manipulated_variable"] == "route_log"
    assert by_group["E2-a"]["manipulated_variable"] == "enabled"

def test_route_log_group_pins_context_only() -> None:
    arms = {arm["arm_id"]: arm for arm in plan_a_arms()["E1-a"]}
    assert arms["E1-a-control"]["config"]["route_mode"] == "context_only"
    assert arms["E1-a-treatment"]["config"]["route_mode"] == "context_only"

def test_specs_are_simulated_by_default() -> None:
    specs = plan_a_specs()
    assert len(specs) == 6
    for item in specs:
        assert item["spec"].mode.value == "simulated"
        assert item["spec"].provider_id == "simulated_scripted"
        assert item["runs"] == 9
        assert item["spec"].replicates == 3

# ------------------------------------------------------------------------ cost
def test_cost_totals_match_v13_corrected_plan_a(unit_costs) -> None:
    cost = plan_a_cost_estimate(unit_costs)
    assert cost["runs"] == 54
    assert cost["estimate_cny"] == pytest.approx(2.11, abs=0.02)
    assert cost["upper_cny"] == pytest.approx(27.0, abs=0.01)
    assert cost["recommended_cap_cny"] == float(RECOMMENDED_CAP_CNY)

def test_cost_marks_unknown_unit_cost_instead_of_zero() -> None:
    cost = plan_a_cost_estimate({})
    assert all(row["estimate_cny"] is None for row in cost["groups"])
    assert cost["estimate_cny"] == 0.0
    # 上界仍然可算（按单局硬上限），但预估不能凭空填 0
    assert cost["upper_cny"] == pytest.approx(27.0, abs=0.01)

# ----------------------------------------------------------------------- seeds
def test_all_seeds_are_whitelisted() -> None:
    rows = plan_a_seed_audit()
    assert rows
    assert all(row["valid"] for row in rows)
    assert {row["seed"] for row in rows} == {0, 1, 2}

# ------------------------------------------------------------------ preflight
def test_preflight_is_planned_only(unit_costs) -> None:
    plan = plan_a_preflight(unit_costs)
    assert plan["status"] == STATUS_PLANNED
    assert plan["live_status"] == LIVE_PENDING
    assert plan["all_single_factor"] is True
    assert plan["all_seeds_valid"] is True
    assert plan["cost"]["runs"] == 54
    assert any("unknown_spend" in rule for rule in plan["stop_rules"])
    assert "不构成执行授权" in plan_a_markdown(plan) or "不构成执行授权" in (
        plan["approval_required"] + plan["no_go_note"]
    )

def test_e3_is_flagged_as_combination_contrast(unit_costs) -> None:
    plan = plan_a_preflight(unit_costs)
    combos = plan["combination_contrasts"]
    assert any(item["group"] == "E3" for item in combos)
    text = plan_a_markdown(plan)
    assert "组合对照" in text
    assert "trigger_only → reflection_on" in text

def test_markdown_states_zero_requests_and_no_authorisation(unit_costs) -> None:
    text = plan_a_markdown(plan_a_preflight(unit_costs))
    assert "PLANNED_ONLY" in text
    assert "LIVE_PENDING" in text
    assert "**0**" in text
    assert "不构成执行授权" in text
    assert "54" in text
