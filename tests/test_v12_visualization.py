"""V12 可视化 view-model 测试：六图专属视图、通用回退、空态与公开边界。"""

from __future__ import annotations

import json
from typing import Any

from v12_support import simulated_config

from agent_arena.lab.runner import run_lab_episode
from agent_arena.lab.simulated import SimulatedDecisionProvider
from agent_arena.lab.visualization import (
    FOCUS_MAPS,
    KIND_BY_MAP,
    build_view_model,
)
from agent_arena.v10.runtime.catalog import create_environment


def _real_run(map_id: str, *, decisions: int = 8) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    environment = create_environment(map_id, environment_seed=0)
    provider = SimulatedDecisionProvider(map_id=map_id, shapes=environment.SHAPES)
    outcome = run_lab_episode(
        simulated_config(map_id, max_decisions=decisions, max_requests=40),
        provider=provider,
        on_event=None,
    )
    events: list[dict[str, Any]] = []
    provider2 = SimulatedDecisionProvider(map_id=map_id, shapes=environment.SHAPES)
    run_lab_episode(
        simulated_config(map_id, max_decisions=decisions, max_requests=40),
        provider=provider2,
        on_event=events.append,
    )
    steps = [event for event in events if event.get("event") == "decision"]
    return steps, outcome.result


def test_focus_maps_cover_six_kinds() -> None:
    assert set(FOCUS_MAPS) == {"MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30"}
    assert set(KIND_BY_MAP.values()) == {
        "diagnosis_funnel",
        "occupancy_timeline",
        "recovery_gantt",
        "exploration_graph",
        "maintenance_chain",
        "evidence_chain",
    }


def test_each_focus_map_builds_available_view_model() -> None:
    for map_id in FOCUS_MAPS:
        steps, result = _real_run(map_id)
        model = build_view_model(map_id, steps, result)
        assert model["available"] is True, map_id
        assert model["kind"] == KIND_BY_MAP[map_id], map_id
        assert model["source"] == "public_trace"
        assert json.dumps(model, ensure_ascii=False)


def test_empty_steps_give_explainable_empty_state() -> None:
    for map_id in (*FOCUS_MAPS, "MAP-01"):
        model = build_view_model(map_id, [], {"map_id": map_id, "state": "CREATED"})
        assert model["available"] is False
        assert model["empty_reason"]


def test_generic_fallback_for_other_maps() -> None:
    steps, result = _real_run("MAP-01")
    model = build_view_model("MAP-01", steps, result)
    assert model["kind"] == "generic_progress"
    assert "tool_histogram" in model
    assert "series" in model


def test_map08_funnel_shrinks_candidates() -> None:
    steps, result = _real_run("MAP-08", decisions=10)
    model = build_view_model("MAP-08", steps, result)
    funnel = model["funnel"]
    assert funnel[0]["event"] == "initial"
    assert funnel[0]["candidate_count"] >= funnel[-1]["candidate_count"]
    assert all("candidate_sites" in row for row in funnel)


def test_map16_timeline_has_public_positions() -> None:
    steps, result = _real_run("MAP-16", decisions=6)
    model = build_view_model("MAP-16", steps, result)
    assert model["timeline"]
    assert all("train_positions" in row for row in model["timeline"])
    assert model["topology"]


def test_map18_timeline_tracks_delivery_and_windows() -> None:
    steps, result = _real_run("MAP-18", decisions=6)
    model = build_view_model("MAP-18", steps, result)
    assert model["timeline"]
    assert "dispatch_windows" in model
    assert all("task_status" in row for row in model["timeline"])


def test_map22_only_draws_discovered_nodes() -> None:
    steps, result = _real_run("MAP-22", decisions=10)
    model = build_view_model("MAP-22", steps, result)
    assert model["nodes"], "至少应有起点或到达过的路标"
    assert model["discovered_node_count"] == len(model["nodes"])
    # 只可能出现在实际到达过的路标；不能等于隐藏地图节点数（该 seed 节点数更大）。
    assert len(model["nodes"]) <= len(steps) + 1
    assert all(edge["to"] in {node["sign"] for node in model["nodes"]} for edge in model["edges"])
    text = json.dumps(model, ensure_ascii=False).lower()
    for forbidden in ("sealed_truth", "judge_state", "truth_seal"):
        assert forbidden not in text


def test_map26_chain_is_ordered_by_step() -> None:
    steps, result = _real_run("MAP-26", decisions=8)
    model = build_view_model("MAP-26", steps, result)
    chain = model["chain"]
    assert chain
    assert [row["step"] for row in chain] == sorted(row["step"] for row in chain)
    assert all("node_type" in row for row in chain)


def test_map30_evidence_cards_only_include_recorded_entries() -> None:
    steps: list[dict[str, Any]] = [
        {
            "event": "decision",
            "decision_index": 1,
            "action": {
                "tool": "record",
                "entry_id": "EVENT_1_HANDOFF",
                "evidence_ids": ["B_KEY_STUB_2310"],
            },
            "result": "ENTRY_RECORDED",
            "observation_after": {
                "map_id": "MAP-30",
                "casebook": {"EVENT_1_HANDOFF": {}},
                "recent_action_window": [{"event": "record"}],
                "chain_reconciled": False,
                "location": "B",
            },
        }
    ]
    result = {
        "map_id": "MAP-30",
        "starting_observation": {
            "entry_requirements": {
                "EVENT_1_HANDOFF": ["B_KEY_STUB_2310", "B_WITNESS_HANDOFF"],
                "EVENT_2_WAX": ["K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE"],
            },
            "courtroom_node": "J",
        },
        "metrics": {},
    }
    model = build_view_model("MAP-30", steps, result)
    assert model["recorded_count"] == 1
    assert model["required_count"] == 2
    cards = {card["entry_id"]: card for card in model["evidence_cards"]}
    assert cards["EVENT_1_HANDOFF"]["recorded"] is True
    assert cards["EVENT_2_WAX"]["recorded"] is False
    assert cards["EVENT_2_WAX"]["recorded_evidence"] == []


def test_map22_edges_reconstruct_from_public_signs() -> None:
    steps: list[dict[str, Any]] = [
        {
            "event": "decision",
            "decision_index": 1,
            "action": {"tool": "move", "bearing": "west"},
            "result": "MOVED_TO:split_1",
            "observation_after": {"current_sign": "split_1", "moves_used": 1},
        },
        {
            "event": "decision",
            "decision_index": 2,
            "action": {"tool": "move", "bearing": "east"},
            "result": "MOVED_TO:camp",
            "observation_after": {"current_sign": "camp", "moves_used": 2},
        },
    ]
    result = {
        "map_id": "MAP-22",
        "starting_observation": {"current_sign": "camp", "move_budget": 44},
        "agent_notes": [],
        "metrics": {},
    }
    model = build_view_model("MAP-22", steps, result)
    assert [node["sign"] for node in model["nodes"]] == ["camp", "split_1"]
    assert model["edges"][0] == {
        "from": "camp",
        "bearing": "west",
        "to": "split_1",
        "step": 1,
        "accepted": True,
    }
    assert model["edges"][1]["from"] == "split_1"
    assert model["edges"][1]["to"] == "camp"


def test_metric_states_are_passed_through_unchanged() -> None:
    result = {
        "map_id": "MAP-08",
        "metrics": {"map08.v10.mission_success": {"state": "CENSORED", "value": None}},
        "metric_specs": [],
    }
    model = build_view_model("MAP-08", [], result)
    assert model["metrics"]["map08.v10.mission_success"]["state"] == "CENSORED"
