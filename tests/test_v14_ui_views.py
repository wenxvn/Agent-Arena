"""V14 Batch 9（P1-5 / P2-3）：Lab 视图纯函数。"""

from __future__ import annotations

from agent_arena.lab.v14.ui_views import (
    comparison_gate,
    first_divergence_view,
    map22_exploration_view,
    map30_ladder_view,
    seed_grouped_repeats,
)


def _step(index, action, result):
    return {"decision_index": index, "action": action, "result": result}

# ------------------------------------------------------------ first divergence
def test_first_divergence_marks_the_first_differing_step() -> None:
    left = [
        _step(0, {"tool": "move", "bearing": "north"}, "MOVED"),
        _step(1, {"tool": "move", "bearing": "east"}, "MOVED"),
    ]
    right = [
        _step(0, {"tool": "move", "bearing": "north"}, "MOVED"),
        _step(1, {"tool": "read_map"}, "MAP_READ"),
    ]
    view = first_divergence_view(left, right)
    assert view["first_divergence"]["step"] == 1
    assert view["first_divergence"]["kind"] == "ACTION"
    assert view["rows"][0]["first_divergence"] is False
    assert view["rows"][1]["first_divergence"] is True
    assert view["identical_prefix"] == 1

def test_first_divergence_detects_result_only_difference() -> None:
    left = [_step(0, {"tool": "move", "bearing": "north"}, "MOVED")]
    right = [_step(0, {"tool": "move", "bearing": "north"}, "BEARING_NOT_AVAILABLE")]
    view = first_divergence_view(left, right)
    assert view["first_divergence"]["kind"] == "PUBLIC_RESULT"
    assert view["first_divergence"]["right_rejected"] is True
    assert view["first_divergence"]["left_rejected"] is False

def test_identical_traces_have_no_divergence() -> None:
    steps = [_step(0, {"tool": "wait"}, "TICK")]
    view = first_divergence_view(steps, steps)
    assert view["first_divergence"] is None
    assert all(row["differs"] is False for row in view["rows"])

def test_version_mismatch_is_flagged() -> None:
    view = first_divergence_view(
        [_step(0, {"tool": "wait"}, "TICK")],
        [_step(0, {"tool": "wait"}, "TICK")],
        left_version="1.0.0",
        right_version="2.0.0",
    )
    assert "版本比较" in view["version_note"]

def test_missing_steps_do_not_crash() -> None:
    view = first_divergence_view([], [])
    assert view["compared_steps"] == 0
    assert view["first_divergence"] is None

# ------------------------------------------------------------- seed grouping
def test_seed_grouping_keeps_seed_as_sample_unit() -> None:
    rows = [
        {"map_id": "MAP-22", "environment_seed": 0, "n": 2, "categories": ["completed_success"]},
        {"map_id": "MAP-22", "environment_seed": 0, "n": 1, "categories": ["mechanism_failure"]},
        {"map_id": "MAP-22", "environment_seed": 1, "n": 3, "categories": ["completed_success"]},
    ]
    grouped = seed_grouped_repeats(rows)
    assert grouped["seed_count"] == 2
    by_seed = {(row["map_id"], row["environment_seed"]): row for row in grouped["rows"]}
    assert by_seed[("MAP-22", 0)]["observations"] == 3
    assert by_seed[("MAP-22", 0)]["flipped"] is True
    assert by_seed[("MAP-22", 1)]["flipped"] is False
    assert grouped["flipped_seeds"] == ["MAP-22#0"]
    assert "不构成新的环境样本" in grouped["note"]

# --------------------------------------------------------------- MAP-22 view
def test_map22_view_never_draws_rejected_moves() -> None:
    model = {
        "available": True,
        "nodes": [{"sign": "A"}, {"sign": "B"}],
        "edges": [{"from": "A", "to": "B", "bearing": "north", "step": 0, "accepted": True}],
        "rejected_moves": [
            {"step": 1, "bearing": "north", "result": "BEARING_NOT_AVAILABLE", "sign": "B"}
        ],
        "moves_used": 1,
        "move_budget": 40,
    }
    view = map22_exploration_view(model)
    assert view["accepted_edges"] == 1
    assert view["walked_path"] == ["A", "B"]
    assert view["rejected_moves"] == 1
    assert all(row["position_unchanged"] for row in view["rejected_rows"])
    assert "没有改变位置" in view["statement"]
    # 被拒的方位不得出现在走过的路径里（这里 north 已走过，因此用不同断言）
    assert len(view["walked_path"]) == 2

def test_map22_view_empty_state() -> None:
    view = map22_exploration_view({"available": False, "empty_reason": "没有动作"})
    assert view["available"] is False
    assert view["reason"] == "没有动作"

# --------------------------------------------------------------- MAP-30 view
def test_map30_ladder_view_separates_censored_from_mechanism() -> None:
    tiers = [
        {
            "tier": "req=90|tok=200000",
            "request_cap": 90,
            "input_token_cap": 200_000,
            "runs": 9,
            "successes": 0,
            "censored": 8,
            "mechanism_failures": 1,
            "bottleneck_axis": "REQUESTS",
            "bottleneck_evidence": "8/8 局撞满请求上限。",
            "capacity": {"estimated_supported_decisions": [113, 155]},
        }
    ]
    view = map30_ladder_view(tiers)
    assert view["tiers"] == 1
    assert view["total_censored"] == 8
    assert view["total_successes"] == 0
    assert view["rows"][0]["supported_decisions"] == [113, 155]
    assert "不能读作能力不足" in view["reading"]

# ------------------------------------------------------------ comparison gate
def test_incomparable_blocks_ranking() -> None:
    gate = comparison_gate("INCOMPARABLE", ["request_cap 不一致（90 vs 180）"])
    assert gate["allowed"] is False
    assert gate["show_ranking"] is False
    assert "不可做因果比较" in gate["headline"]
    assert "request_cap" in gate["reason"]

def test_descriptive_allows_numbers_but_no_ranking() -> None:
    gate = comparison_gate("DESCRIPTIVE_ONLY", ["prompt_hash 未登记"])
    assert gate["allowed"] is True
    assert gate["show_ranking"] is False
    assert "不能宣称显著改善" in gate["note"]

def test_comparable_still_forbids_causal_claims() -> None:
    gate = comparison_gate("COMPARABLE")
    assert gate["show_ranking"] is True
    assert "不等于显著改善" in gate["note"]
