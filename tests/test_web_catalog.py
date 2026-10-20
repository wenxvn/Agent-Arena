"""V11 30 图公开目录：稳定 ID、展示难度、公开信息边界。"""

from __future__ import annotations

import json

from agent_arena.v10.contract_hints import CONTRACT_HINTS
from agent_arena.web.catalog import (
    DISPLAY_DIFFICULTY,
    DISPLAY_TITLES,
    card,
    cards,
    display_difficulty_rows,
    filter_cards,
    map_detail,
    world_groups,
)

FORBIDDEN_KEYS = {"sealed_truth", "judge_state", "oracle", "answer_key", "truth_seal"}


def _all_keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(str(key))
            found |= _all_keys(item)
    elif isinstance(value, list):
        for item in value:
            found |= _all_keys(item)
    return found


def test_catalog_has_stable_thirty_maps_and_ten_worlds() -> None:
    items = cards()
    assert [item.map_id for item in items] == [f"MAP-{i:02d}" for i in range(1, 31)]
    groups = world_groups()
    assert len(groups) == 10
    assert all(len(group) == 3 for group in groups.values())
    assert all(item.display_difficulty in {"简单", "中等", "困难", "待校准"} for item in items)
    assert set(DISPLAY_TITLES) == {item.map_id for item in items}
    assert set(DISPLAY_DIFFICULTY) == {item.map_id for item in items}


def test_every_map_has_public_goal_rules_contract_and_budget() -> None:
    for item in cards():
        assert item.goal.strip()
        assert item.rule_count > 0
        assert item.tool_count > 0
        assert item.decision_budget > 0
        assert item.seeds
        assert len(item.rule_hash) == 64
        assert len(item.metric_hash) == 64
        assert item.primary_metric


def test_map_detail_never_contains_sealed_truth_or_answer() -> None:
    for item in cards():
        detail = map_detail(item.map_id, item.seeds[0])
        keys = _all_keys(detail)
        assert not (keys & FORBIDDEN_KEYS), (item.map_id, keys & FORBIDDEN_KEYS)
        assert detail["rules"]
        assert detail["contract"]
        assert detail["public_fields"]
        assert detail["scenario_descriptor"]


def test_map_detail_is_seed_dependent_but_public() -> None:
    first = map_detail("MAP-04", 0)
    second = map_detail("MAP-04", 1)
    assert first["scenario_descriptor"] != second["scenario_descriptor"]
    assert "sealed_truth" not in json.dumps(first, ensure_ascii=False)


def test_filter_cards_by_world_difficulty_and_text() -> None:
    assert len(filter_cards(world="castle")) == 3
    assert all(item.world == "castle" for item in filter_cards(world="castle"))
    assert filter_cards(query="温度临界点")[0].map_id == "MAP-19"
    assert filter_cards(difficulty="简单")
    assert filter_cards(query="不存在的关键词") == []


def test_display_difficulty_keeps_design_label() -> None:
    rows = display_difficulty_rows()
    assert len(rows) == 30
    assert all(row["design_difficulty"] for row in rows)
    assert card("MAP-19").design_difficulty == "简单"
    assert card("MAP-19").display_difficulty == "困难"


def test_contract_hints_match_frozen_runner() -> None:
    from scripts.run_v10_mimo import CONTRACT_HINTS as SCRIPT_HINTS

    assert SCRIPT_HINTS == CONTRACT_HINTS
