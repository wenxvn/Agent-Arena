from agent_arena.llm.protocol import (
    decision_response_schema,
    decision_response_schema_strict,
    planner_response_schema,
    planner_response_schema_strict,
)


def test_decision_response_schema_requires_the_shared_action_shape() -> None:
    schema = decision_response_schema()

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["decision_reason", "action"]
    action_schema = schema["properties"]["action"]
    assert isinstance(action_schema, dict)
    assert action_schema["discriminator"]["propertyName"] == "tool"


def test_decision_response_schema_strict_has_no_refs() -> None:
    schema = decision_response_schema_strict()

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["decision_reason", "action"]
    dumped = repr(schema)
    assert "$ref" not in dumped
    assert "$defs" not in dumped
    variants = schema["properties"]["action"]["anyOf"]
    assert isinstance(variants, list)
    assert len(variants) == 5
    tools: list[str] = []
    for variant in variants:
        assert variant["additionalProperties"] is False
        tool_schema = variant["properties"]["tool"]
        tools.extend(
            [tool_schema["const"]]
            if "const" in tool_schema
            else list(tool_schema["enum"])
        )
    assert sorted(tools) == [
        "inspect",
        "look",
        "move",
        "pickup",
        "read_terminal",
        "use",
    ]


def test_planner_response_schema_strict_requires_every_property() -> None:
    schema = planner_response_schema_strict()

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    criterion = schema["properties"]["success_criteria"]["items"]["anyOf"][1]
    assert set(criterion["required"]) == set(criterion["properties"])
    dumped = repr(schema)
    assert "$ref" not in dumped
    assert "$defs" not in dumped


def test_planner_response_schema_has_no_executable_action_field() -> None:
    schema = planner_response_schema()

    assert schema["additionalProperties"] is False
    assert "action" not in schema["properties"]
    assert "current_subgoal" in schema["required"]
    assert "success_criteria" in schema["required"]
