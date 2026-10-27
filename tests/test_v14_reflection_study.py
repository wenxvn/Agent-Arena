"""V14 Batch 5（P0-6）：reflection.v2 六态、三臂与选择偏倚防护。"""

from __future__ import annotations

from agent_arena.lab.policies.reflection_v2 import EXPOSURE_NONE, EXPOSURE_TRIGGERED
from agent_arena.lab.v14.reflection_study import (
    REFLECTION_PINNED_BASE,
    REFLECTION_SCRIPT,
    evaluate_without_selection_bias,
    exposure_gate,
    reflection_ablation_plan,
    reflection_arm_configs,
    reflection_markdown,
    reflection_offline_probe,
    reflection_single_factor_audit,
    reflection_study_report,
)


# ------------------------------------------------------------------ six states
def test_reflection_on_really_triggers_and_pays_requests() -> None:
    probe = reflection_offline_probe({"trigger_only": False})
    assert probe["triggered"] >= 1
    assert probe["reflection_requests"] == probe["triggered"]
    assert probe["exposure"] == EXPOSURE_TRIGGERED
    # 每次反思都是额外一次请求
    assert probe["total_requests"] == probe["decisions"] + probe["reflection_requests"]
    assert probe["reflection_tokens_in"] > 0

def test_trigger_only_counts_exposure_without_requests() -> None:
    probe = reflection_offline_probe({"trigger_only": True})
    assert probe["triggered"] >= 1
    assert probe["reflection_requests"] == 0
    assert probe["total_requests"] == probe["decisions"]
    assert probe["exposure"] == EXPOSURE_TRIGGERED

def test_disabled_arm_never_triggers() -> None:
    probe = reflection_offline_probe({"enabled": False})
    assert probe["triggered"] == 0
    assert probe["eligible"] == 0
    assert probe["exposure"] == "DISABLED"
    assert probe["total_requests"] == probe["decisions"]

def test_cooldown_and_quota_are_separately_counted() -> None:
    probe = reflection_offline_probe({"trigger_only": False})
    assert probe["blocked_cooldown"] >= 1
    # 触发判定总次数 = 真触发 + 冷却挡 + 额度挡
    detections = len(probe["triggers"])
    assert probe["triggered"] + probe["blocked_cooldown"] + probe["blocked_quota"] == detections
    assert probe["triggered"] <= probe["eligible"]

def test_quota_blocks_after_max_reflections() -> None:
    probe = reflection_offline_probe(
        {"trigger_only": False, "max_reflections": 2},
    )
    assert probe["triggered"] == 2
    assert probe["blocked_quota"] >= 1

def test_advice_is_injected_after_reflection() -> None:
    probe = reflection_offline_probe({"trigger_only": False})
    assert probe["advice_injected_steps"] >= 1

def test_no_trigger_case_is_no_treatment_exposure() -> None:
    probe = reflection_offline_probe(
        {"trigger_only": False},
        script=tuple(
            {"moves_used": index + 1, "result": "MOVED", "rejected": False}
            for index in range(6)
        ),
        cycle_actions=True,
        include_tick=False,
    )
    assert probe["triggered"] == 0
    gate = exposure_gate(probe)
    assert gate["status"] == EXPOSURE_NONE
    assert "NO_TREATMENT_EXPOSURE" in gate["allowed_conclusion"]
    assert "无效" in gate["allowed_conclusion"]

def test_long_failure_prefix_keeps_triggering() -> None:
    long_script = tuple(
        {"moves_used": 1, "result": "BEARING_NOT_AVAILABLE", "rejected": True}
        for _ in range(12)
    )
    probe = reflection_offline_probe({"trigger_only": False}, script=long_script)
    assert probe["triggered"] == 3  # max_reflections 封顶
    assert probe["blocked_quota"] >= 1
    assert probe["recoveries"] >= 1

def test_probe_is_deterministic() -> None:
    first = reflection_offline_probe({"trigger_only": False})
    second = reflection_offline_probe({"trigger_only": False})
    assert first["triggered"] == second["triggered"]
    assert first["total_requests"] == second["total_requests"]
    assert first["triggers"] == second["triggers"]
    assert len(REFLECTION_SCRIPT) == 12

# ------------------------------------------------------------------- arm audit
def test_two_single_factor_pairs_and_one_combination() -> None:
    audit = reflection_single_factor_audit()
    assert audit["all_single_factor"] is True
    assert len(audit["single_factor_pairs"]) == 2
    assert len(audit["combination_pairs"]) == 1
    by_pair = {(item["left"], item["right"]): item for item in audit["checks"]}
    assert by_pair[("E3-trigger-only", "E3-treatment")]["manipulated_variable"] == "trigger_only"
    assert by_pair[("E3-control", "E3-treatment")]["manipulated_variable"] == "enabled"
    combo = by_pair[("E3-control", "E3-trigger-only")]
    assert combo["ok"] is False
    assert set(combo["changed_keys"]) == {"enabled", "trigger_only"}

def test_arms_share_pinned_base() -> None:
    for arm in reflection_arm_configs():
        for key, value in REFLECTION_PINNED_BASE.items():
            if key in {"enabled", "trigger_only"}:
                continue
            assert arm["config"][key] == value
        assert arm["agent_id"] == "reflection.v2"

# ------------------------------------------------------------- selection bias
def test_selection_bias_is_flagged_when_subset_is_smaller() -> None:
    all_assigned = [
        {"category": "mechanism_failure"},
        {"category": "mechanism_failure"},
        {"category": "completed_success"},
        {"category": "completed_success"},
    ]
    subset = [{"category": "completed_success"}, {"category": "completed_success"}]
    result = evaluate_without_selection_bias(
        all_assigned=all_assigned, triggered_subset=subset
    )
    assert result["all_assigned"]["success_rate"] == 0.5
    assert result["triggered_subset"]["success_rate"] == 1.0
    assert result["selection_bias"]["present"] is True
    assert result["selection_bias"]["dropped_runs"] == 2
    assert "高估" in result["selection_bias"]["note"]

def test_no_bias_when_all_runs_triggered() -> None:
    rows = [{"category": "completed_success"}, {"category": "mechanism_failure"}]
    result = evaluate_without_selection_bias(all_assigned=rows, triggered_subset=rows)
    assert result["selection_bias"]["present"] is False

# ----------------------------------------------------------------------- plan
def test_plan_counts_three_arms_and_two_arm_subset() -> None:
    plan = reflection_ablation_plan()
    assert plan["status"] == "PLANNED_ONLY"
    assert plan["live_status"] == "LIVE_PENDING"
    assert plan["runs"] == 3 * 3 * 3
    assert plan["two_arm_subset_runs"] == 18
    assert "NO_TREATMENT_EXPOSURE" in plan["activation_gate"]
    assert any(item["map_id"] == "MAP-19" for item in plan["candidate_maps"])

def test_markdown_mentions_gate_and_bias() -> None:
    text = reflection_markdown(reflection_study_report())
    assert "NO_TREATMENT_EXPOSURE" in text
    assert "选择偏倚" in text
    assert "LIVE_PENDING" in text
    assert "trigger_only" in text
