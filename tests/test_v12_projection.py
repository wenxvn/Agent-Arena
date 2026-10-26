"""DCR-V12-02 回归测试：V12 投影指标 + 地图补丁。"""

from __future__ import annotations

from agent_arena.lab.contract_v12 import MAP_HINTS, augmentation_for
from agent_arena.lab.metrics_v12 import (
    PROJECTION_VERSION,
    ROUTE_RECALL_ID,
    project_metrics,
    project_route_recall,
)
from agent_arena.v10.runtime.catalog import create_environment

ROUTE = ["west", "south", "north"]


def test_bearing_keys_are_read_like_v10() -> None:
    notes = [
        {"key": "bearing", "value": "west"},
        {"key": "bearing", "value": "south"},
        {"key": "bearing", "value": "north"},
    ]
    result = project_route_recall(notes=notes, route=ROUTE)
    assert result["state"] == "VALID"
    assert result["value"] == 1.0
    assert result["numerator"] == 3
    assert result["denominator"] == 3
    assert result["rule_version"] == PROJECTION_VERSION


def test_path_state_is_parsed() -> None:
    notes = [{"key": "path_state", "value": "west,south,north"}]
    result = project_route_recall(notes=notes, route=ROUTE)
    assert result["value"] == 1.0


def test_free_form_keys_are_accepted_with_partial_match() -> None:
    """真实 MiMo 的写法：键名自由，但值是方位序列。

    ``camp->west->split_1->south`` 的前两位正好命中真实路线 ``west,south``，
    所以匹配 2/3——比"只认 bearing/path_state"时直接判 N/A 更有信息量。
    """

    notes = [
        {"key": "path_to_here", "value": "pale_7->south->leaning_3"},
        {"key": "route_from_camp", "value": "camp->west->split_1->south"},
    ]
    result = project_route_recall(notes=notes, route=ROUTE)
    assert result["state"] == "VALID"
    assert result["numerator"] == 2
    assert result["value"] == round(2 / 3, 6)
    assert "route_from_camp" in result["source_keys"]


def test_unrelated_notes_are_ignored() -> None:
    notes = [{"key": "next_plan", "value": "explore south from split_1"}]
    result = project_route_recall(notes=notes, route=ROUTE)
    # 键名不含路线提示 → 不把"计划"当成走过的路线。
    assert result["state"] == "NOT_APPLICABLE"


def test_no_notes_is_not_applicable() -> None:
    result = project_route_recall(notes=[], route=ROUTE)
    assert result["state"] == "NOT_APPLICABLE"
    assert result["denominator"] == 3
    assert "没有可解析" in result["note"]


def test_no_route_is_not_applicable() -> None:
    result = project_route_recall(notes=[{"key": "bearing", "value": "west"}], route=[])
    assert result["state"] == "NOT_APPLICABLE"
    assert result["denominator"] == 0


def test_partial_sequences_are_not_padded() -> None:
    notes = [{"key": "bearing", "value": "west"}]
    result = project_route_recall(notes=notes, route=ROUTE)
    assert result["numerator"] == 1
    assert result["denominator"] == 3
    assert result["value"] == round(1 / 3, 6)


def test_chinese_and_abbreviations_are_understood() -> None:
    notes = [{"key": "路线", "value": "北, 东"}]
    result = project_route_recall(notes=notes, route=["north", "east"])
    assert result["value"] == 1.0


def test_projection_only_applies_to_map22() -> None:
    assert project_metrics("MAP-22", notes=[], route=[]) != {}
    assert project_metrics("MAP-18", notes=[], route=[]) == {}


def test_projection_id_is_namespaced() -> None:
    assert ROUTE_RECALL_ID == "v12.projection.route_recall"
    assert not ROUTE_RECALL_ID.startswith("map22.")


def test_map22_hint_is_public_information_only() -> None:
    text = " ".join(MAP_HINTS["MAP-22"]).lower()
    for forbidden in ("sealed_truth", "judge_state", "oracle", "answer", "最优"):
        assert forbidden not in text
    assert "bearing" in text and "path_state" in text


def test_map22_augmentation_contains_both_hints() -> None:
    hints = augmentation_for(create_environment("MAP-22"))
    assert len(hints) == 2
    assert any("facts" in item for item in hints)
    assert any("path_state" in item for item in hints)


def test_map03_gets_only_facts_hint() -> None:
    hints = augmentation_for(create_environment("MAP-03"))
    assert len(hints) == 1
    assert "facts" in hints[0]


def test_other_maps_get_no_map_hint() -> None:
    hints = augmentation_for(create_environment("MAP-18"))
    assert hints == ()
