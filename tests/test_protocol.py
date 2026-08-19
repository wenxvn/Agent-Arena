from agent_arena.llm.protocol import decision_response_schema


def test_decision_response_schema_requires_the_shared_action_shape() -> None:
    schema = decision_response_schema()

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["decision_reason", "action"]
    action_schema = schema["properties"]["action"]
    assert isinstance(action_schema, dict)
    assert action_schema["discriminator"]["propertyName"] == "tool"
