"""V6 leakage counter-example tests."""

from __future__ import annotations

from agent_arena.v6.catalog import build_environment, get_scene
from agent_arena.v6.leakage import audit_all
from agent_arena.v6.prompts import v6_action_contract, v6_system_prompt


def test_no_leakage_findings_across_all_instances() -> None:
    assert audit_all() == {}


def test_map22_conditions_exclude_unavailable_memory_action() -> None:
    assert "write_memory{" not in v6_action_contract("MAP-22", "history5")
    assert "write_memory{" in v6_action_contract("MAP-22", "history5_graph_memory")
    assert "不会自动移动" in v6_system_prompt("MAP-22", "history5")


def test_map30_initial_observation_hides_unlocked_evidence() -> None:
    scene = get_scene("map30_l2_three_event_alt")
    environment = build_environment(scene, "history5_casebook", seed=0)
    dump = environment.observe().model_dump(mode="json")
    assert dump["casebook"] == []
    assert "NELL_ORAV" not in str(dump)


def test_prompt_does_not_contain_oracle_actions() -> None:
    prompt = v6_system_prompt("MAP-16", "react")
    assert "inspect_network" in prompt  # the action vocabulary is public
    # But no concrete routed action payload is embedded.
    assert '"next_node"' not in prompt
