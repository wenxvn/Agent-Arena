"""Batch 8：公开动作契约类型渲染的单元测试（DCR-V10-24）。"""

from __future__ import annotations

from agent_arena.v10.contract import action_contract, field_shape, unknown_fields
from agent_arena.v10.runtime.catalog import MAP_IDS, create_environment


def test_unknown_fields_absent_for_all_maps() -> None:
    """``SHAPES`` 里不得出现 ``V8Action`` 不认识的字段名。"""

    for map_id in MAP_IDS:
        shapes = create_environment(map_id).SHAPES
        assert unknown_fields(shapes) == [], map_id


def test_scalar_types_are_rendered() -> None:
    assert field_shape("tick") == "<int>"
    assert field_shape("to") == "<str>"
    assert field_shape("turns") == "<int>"


def test_nested_types_are_rendered() -> None:
    assert field_shape("operations") == '{"<key>": {"<key>": <value>}}'
    assert field_shape("claims") == '[{"<key>": <value>}]'
    assert field_shape("cited_entry_ids") == "[<str>]"
    assert field_shape("event_claims") == (
        '[{"event_id": <str>, "time": <str>, "location": <str>, "duty_code": <str>}]'
    )


def test_contract_documents_shapes_for_map18_and_map28() -> None:
    contract18 = action_contract(create_environment("MAP-18").SHAPES)
    assert '"operations": {"<key>": {"<key>": <value>}}' in contract18
    assert "tick" in contract18
    contract28 = action_contract(create_environment("MAP-28").SHAPES)
    assert '"claims": [{"<key>": <value>}]' in contract28


def test_contract_has_no_hidden_truth_sections() -> None:
    for map_id in ("MAP-15", "MAP-18", "MAP-28"):
        contract = action_contract(create_environment(map_id).SHAPES)
        assert "sealed" not in contract.lower()
        assert "truth" not in contract.lower()
