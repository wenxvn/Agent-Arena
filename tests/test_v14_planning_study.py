"""V14 Batch 4（P0-5）：planning.v2 触发链、成本归因与三组单因子。"""

from __future__ import annotations

from agent_arena.lab.v14.planning_study import (
    PLANNER_INPUT_TOKENS,
    PLANNER_OUTPUT_TOKENS,
    PLANNING_PINNED_BASE,
    PLANNING_STALL_SCRIPT,
    planning_ablation_plan,
    planning_arm_configs,
    planning_markdown,
    planning_offline_probe,
    planning_single_factor_audit,
    planning_study_report,
)


# --------------------------------------------------------------- trigger chain
def test_adaptive_chain_records_trigger_block_and_request() -> None:
    probe = planning_offline_probe({"planner_mode": "adaptive"})
    chain = probe["chain"]
    assert len(chain) == 12
    # 第一步必然初始规划
    assert chain[0]["trigger"] == "initial"
    assert chain[0]["event"] == "plan_created"
    assert chain[0]["planner_request"] == 1
    # TTL 下限会延迟重规划，并留下证据
    deferred = [node for node in chain if node["blocked_by"] == "ttl"]
    assert deferred and deferred[0]["planner_request"] == 0
    assert probe["skipped_ttl"] >= 1
    # 无进度与公开进度都会触发重规划
    triggers = {node["trigger"] for node in chain}
    assert {"no_progress", "public_progress", "repeated_rejection"} <= triggers

def test_planner_requests_are_counted_in_total_requests() -> None:
    probe = planning_offline_probe({"planner_mode": "adaptive"})
    planner_steps = [node for node in probe["chain"] if node["planner_request"]]
    assert probe["planner_requests"] == len(planner_steps)
    # 每个规划步都多花 1 次请求（动作 1 + Planner 1）
    assert all(node["requests"] == 2 for node in planner_steps)
    assert probe["total_requests"] == probe["decisions"] + probe["planner_requests"]
    assert probe["planner_tokens_in"] == PLANNER_INPUT_TOKENS * probe["planner_requests"]
    assert probe["planner_tokens_out"] == PLANNER_OUTPUT_TOKENS * probe["planner_requests"]

def test_initial_only_plans_exactly_once() -> None:
    probe = planning_offline_probe({"planner_mode": "initial_only"})
    assert probe["plan_count"] == 1
    assert probe["planner_requests"] == 1
    assert probe["triggers"] == ["initial"]
    assert probe["skipped_ttl"] == 0

def test_periodic_arms_differ_only_by_frequency() -> None:
    fast = planning_offline_probe(
        {"planner_mode": "periodic", "min_steps_between_plans": 4}
    )
    slow = planning_offline_probe(
        {"planner_mode": "periodic", "min_steps_between_plans": 12}
    )
    assert fast["planner_requests"] > slow["planner_requests"]
    assert fast["total_requests"] > slow["total_requests"]
    assert all(trigger in {"initial", "periodic"} for trigger in fast["triggers"])

def test_disabled_arm_never_requests_planner() -> None:
    probe = planning_offline_probe({"enabled": False})
    assert probe["planner_requests"] == 0
    assert probe["plan_count"] == 0
    assert probe["total_requests"] == probe["decisions"]
    assert probe["triggers"] == []

def test_budget_guard_blocks_planner_when_budget_is_low() -> None:
    probe = planning_offline_probe(
        {"stall_threshold": 2}, script=PLANNING_STALL_SCRIPT, decision_budget=12
    )
    assert probe["skipped_budget"] >= 1
    blocked = [node for node in probe["chain"] if node["blocked_by"] == "budget"]
    assert blocked
    assert all(node["planner_request"] == 0 for node in blocked)

def test_max_plans_cap_stops_new_plans() -> None:
    probe = planning_offline_probe(
        {"stall_threshold": 2, "max_plans": 2},
        script=PLANNING_STALL_SCRIPT,
        decision_budget=24,
    )
    assert probe["plan_count"] == 2
    assert any(node["blocked_by"] == "max_plans" for node in probe["chain"])

def test_probe_is_deterministic() -> None:
    first = planning_offline_probe({"planner_mode": "adaptive"})
    second = planning_offline_probe({"planner_mode": "adaptive"})
    assert first["triggers"] == second["triggers"]
    assert first["total_requests"] == second["total_requests"]
    assert [node["event"] for node in first["chain"]] == [
        node["event"] for node in second["chain"]
    ]

# ------------------------------------------------------------------- arm audit
def test_three_groups_are_each_single_factor() -> None:
    audit = planning_single_factor_audit()
    assert audit["all_single_factor"] is True
    by_group = {item["group"]: item for item in audit["checks"]}
    assert by_group["E2-a"]["manipulated_variable"] == "enabled"
    assert by_group["E2-b"]["manipulated_variable"] == "planner_mode"
    assert by_group["E2-c"]["manipulated_variable"] == "min_steps_between_plans"

def test_frequency_group_pins_periodic_mode() -> None:
    arms = {arm["arm_id"]: arm for arm in planning_arm_configs()}
    assert arms["E2-c-control"]["config"]["planner_mode"] == "periodic"
    assert arms["E2-c-treatment"]["config"]["planner_mode"] == "periodic"
    assert arms["E2-c-control"]["config"]["min_steps_between_plans"] == 4
    assert arms["E2-c-treatment"]["config"]["min_steps_between_plans"] == 12

def test_arms_share_pinned_base() -> None:
    for arm in planning_arm_configs():
        for key, value in PLANNING_PINNED_BASE.items():
            if key in {"enabled", "planner_mode", "min_steps_between_plans"}:
                continue
            assert arm["config"][key] == value
        assert arm["agent_id"] == "planning.v2"

# ---------------------------------------------------------------------- plan
def test_plan_counts_and_negative_control() -> None:
    plan = planning_ablation_plan()
    assert plan["status"] == "PLANNED_ONLY"
    assert plan["live_status"] == "LIVE_PENDING"
    assert plan["main_runs"] == 3 * 2 * 3 * 3
    assert plan["negative_control_runs"] == 18
    assert plan["runs"] == plan["main_runs"] + plan["negative_control_runs"]
    assert plan["negative_control_map"] == "MAP-18"
    assert "MAP-18" in plan["negative_control_note"]

def test_plan_requires_same_total_budget() -> None:
    plan = planning_ablation_plan()
    assert "同一**总预算**" in plan["comparison_rule"]
    assert "cost_per_success_cny" in plan["cost_metrics"]

def test_markdown_reports_pending_not_results() -> None:
    text = planning_markdown(planning_study_report())
    assert "LIVE_PENDING" in text
    assert "PLANNED_ONLY" in text
    assert "planner_deferred_ttl" in text
