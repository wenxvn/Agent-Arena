"""V14 Batch 3（P0-4）：memory.v2 机制验证、单因子臂与预检登记。"""

from __future__ import annotations

from agent_arena.lab.adapters import FORBIDDEN_PUBLIC_KEYS
from agent_arena.lab.v14.agent_studies import (
    DEFAULT_SCRIPT,
    MEMORY_PINNED_BASE,
    memory_ablation_plan,
    memory_arm_configs,
    memory_markdown,
    memory_offline_probe,
    memory_single_factor_audit,
    memory_study_report,
)


# --------------------------------------------------------------- mechanism fixtures
def test_rejected_and_invalid_moves_never_enter_route() -> None:
    probe = memory_offline_probe({"route_mode": "context_only", "route_log": True})
    assert probe["rejected_moves"] == 1
    assert probe["invalid_moves"] == 1
    assert probe["route_preview"] == "north,east,south,west"
    assert probe["route_matches_expected"] is True

def test_route_off_records_nothing_but_still_reports_no_route() -> None:
    probe = memory_offline_probe({"route_mode": "context_only", "route_log": False})
    assert probe["route_length"] == 0
    assert probe["route_preview"] == ""
    assert probe["bottleneck"]["label"] == "NO_RECORD"
    assert probe["bottleneck_v13"] == "NO_RECORD"
    # 关掉路线日志后，"路线 == 接受序列"必然不成立，这正是被测差异。
    assert probe["route_matches_expected"] is False

def test_return_to_start_can_reference_full_bearing_sequence() -> None:
    probe = memory_offline_probe({"route_mode": "context_only", "route_log": True})
    assert probe["route_preview"] == "north,east,south,west"
    assert probe["final_block_has_all_bearings"] is True
    block = probe["last_memory_block"] or ""
    for bearing in ("north", "east", "south", "west"):
        assert bearing in block

def test_memory_block_never_contains_hidden_truth() -> None:
    for config in (
        {"route_mode": "context_only", "route_log": True},
        {"route_mode": "env_write", "route_log": True},
    ):
        probe = memory_offline_probe(config)
        assert probe["memory_block_leaks"] == []
        block = (probe["last_memory_block"] or "").lower()
        for word in FORBIDDEN_PUBLIC_KEYS:
            assert word not in block

def test_env_write_costs_a_decision_but_no_request() -> None:
    context_only = memory_offline_probe({"route_mode": "context_only", "route_log": True})
    env_write = memory_offline_probe({"route_mode": "env_write", "route_log": True})
    assert env_write["write_accepted"] >= 1
    assert context_only["write_attempts"] == 0
    # env_write 多花决策、不少花请求：这是"记忆的代价"必须可见的部分
    assert env_write["decisions"] > context_only["decisions"]
    assert env_write["requests"] < env_write["decisions"]

def test_env_write_projection_recall_is_valid_and_full_route_written() -> None:
    probe = memory_offline_probe({"route_mode": "env_write", "route_log": True})
    assert probe["final_write_route"] == "north,east,south,west"
    assert probe["route_recall_v14"]["state"] == "VALID"
    assert probe["route_recall_v14"]["value"] == 1.0

def test_context_only_route_recall_is_not_applicable_for_v10_metric() -> None:
    probe = memory_offline_probe({"route_mode": "context_only", "route_log": True})
    # 不写环境 → V10 官方口径 N/A；不能把 N/A 当成 0 分
    assert probe["route_recall_v14"]["state"] == "NOT_APPLICABLE"
    assert probe["route_recall_v14"]["value"] is None
    assert "NOT_APPLICABLE" in probe["route_recall_v10_note"]

def test_disabled_memory_renders_nothing() -> None:
    probe = memory_offline_probe({"enabled": False})
    assert probe["render_count"] == 0
    assert probe["bottleneck"]["label"] == "DISABLED"
    assert probe["route_length"] == 0

def test_bottleneck_projection_fixes_write_count_comparison() -> None:
    """DCR-V14-03：原口径按写入次数判定，V14 按已写入方位数判定。"""

    probe = memory_offline_probe({"route_mode": "env_write", "route_log": True})
    assert probe["bottleneck_v13"] == "RECORDED_TOO_SHORT"
    assert probe["bottleneck"]["label"] == "RECORDED_AND_RENDERED"
    assert "方位" in probe["bottleneck"]["reason"] or "渲染" in probe["bottleneck"]["reason"]

def test_script_is_deterministic_across_runs() -> None:
    first = memory_offline_probe({"route_mode": "env_write", "route_log": True})
    second = memory_offline_probe({"route_mode": "env_write", "route_log": True})
    for key in ("decisions", "requests", "route_preview", "write_accepted", "route_length"):
        assert first[key] == second[key]
    assert len(DEFAULT_SCRIPT) == 6

# ---------------------------------------------------------------- arm registry
def test_each_group_changes_exactly_one_key() -> None:
    audit = memory_single_factor_audit()
    assert audit["all_single_factor"] is True
    by_group = {item["group"]: item for item in audit["checks"]}
    assert by_group["E1-a"]["manipulated_variable"] == "route_log"
    assert by_group["E1-b"]["manipulated_variable"] == "route_mode"

def test_route_log_group_pins_route_mode() -> None:
    arms = {arm["arm_id"]: arm for arm in memory_arm_configs()}
    assert (
        arms["E1-a-control"]["config"]["route_mode"]
        == arms["E1-a-treatment"]["config"]["route_mode"]
        == "context_only"
    )
    assert arms["E1-a-control"]["config"]["route_log"] is False
    assert arms["E1-a-treatment"]["config"]["route_log"] is True

def test_env_write_group_pins_route_log() -> None:
    arms = {arm["arm_id"]: arm for arm in memory_arm_configs()}
    assert (
        arms["E1-b-control"]["config"]["route_log"]
        == arms["E1-b-treatment"]["config"]["route_log"]
        is True
    )
    assert arms["E1-b-control"]["config"]["route_mode"] == "context_only"
    assert arms["E1-b-treatment"]["config"]["route_mode"] == "env_write"

def test_all_arms_share_pinned_base_except_the_switch() -> None:
    for arm in memory_arm_configs():
        for key, value in MEMORY_PINNED_BASE.items():
            if key in {"route_log", "route_mode"}:
                continue
            assert arm["config"][key] == value
        assert arm["agent_id"] == "memory.v2"

# ------------------------------------------------------------------ plan/gating
def test_plan_is_planned_only_and_costs_match_group_count() -> None:
    plan = memory_ablation_plan()
    assert plan["status"] == "PLANNED_ONLY"
    assert plan["live_status"] == "LIVE_PENDING"
    assert plan["runs"] == len(plan["groups"]) * 2 * len(plan["seeds"]) * plan["replicates"]
    assert plan["runs"] == 36
    assert plan["budget"]["experiment_cost_cap_cny"] == 5.00
    assert any("unknown_spend" in rule for rule in plan["stop_rules"])

def test_plan_declares_both_metric_namespaces() -> None:
    plan = memory_ablation_plan()
    assert "v14.projection.route_recall" in plan["primary_metrics"]
    assert "map22.v10.route_recall" in plan["primary_metrics"]

def test_report_and_markdown_are_self_consistent() -> None:
    report = memory_study_report()
    text = memory_markdown(report)
    assert "PLANNED_ONLY" in text
    assert "LIVE_PENDING" in text
    assert "route_recall" in text
    # 不允许把模拟结果写成真实收益
    assert "SIMULATED" in text
    assert "env_write" in text
