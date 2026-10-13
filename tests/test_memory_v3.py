from __future__ import annotations

import json

import pytest

from agent_arena.agents.memory import (
    FailedAction,
    MemoryAgent,
    MemoryLimits,
    MemoryV3Limits,
    MemoryV3Reducer,
    MemoryV3State,
)
from agent_arena.arena import Observation, ToolReason, ToolResult, ToolStatus
from agent_arena.arena.models import LookAction, MoveAction, UseAction
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation.runner import EpisodeRunner
from agent_arena.llm import FakeDecisionProvider
from agent_arena.worlds import SpaceshipEscapeEnvironment


def make_observation(
    room: str,
    *,
    exits: tuple[str, ...] = (),
    inventory: tuple[str, ...] = (),
) -> Observation:
    return Observation(
        current_room=room,
        description=f"当前地点：{room}",
        visible_objects=(),
        available_exits=exits,
        inventory=inventory,
        last_action_result=None,
    )


def test_memory_v3_records_observed_frontier_and_only_successful_move_edges() -> None:
    reducer = MemoryV3Reducer()
    state = reducer.initialize(make_observation("room_a", exits=("room_b", "room_c")))

    assert {(item.source, item.destination) for item in state.frontier} == {
        ("room_a", "room_b"),
        ("room_a", "room_c"),
    }

    state = reducer.apply(
        state,
        MoveAction(tool="move", destination="room_b"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
        make_observation("room_b", exits=("room_a", "room_d")),
    )
    assert {(item.source, item.destination) for item in state.traversed_edges} == {
        ("room_a", "room_b")
    }
    assert {(item.source, item.destination) for item in state.frontier} == {
        ("room_a", "room_c"),
        ("room_b", "room_d"),
    }

    state = reducer.apply(
        state,
        MoveAction(tool="move", destination="room_c"),
        ToolResult(
            status=ToolStatus.REJECTED,
            reason=ToolReason.NOT_ADJACENT,
            summary="该出口尚不可达。",
        ),
        make_observation("room_b", exits=("room_a", "room_d")),
    )
    assert ("room_b", "room_c") not in {
        (item.source, item.destination) for item in state.traversed_edges
    }


def test_memory_v3_frontier_uses_visited_rooms_beyond_the_v2_location_limit() -> None:
    reducer = MemoryV3Reducer(limits=MemoryLimits(max_locations=12))
    route = ["room_a", *(f"room_{index}" for index in range(1, 14))]
    state = reducer.initialize(make_observation(route[0], exits=(route[1],)))

    for _source, destination in zip(route, route[1:], strict=False):
        state = reducer.apply(
            state,
            MoveAction(tool="move", destination=destination),
            ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
            make_observation(destination),
        )

    state = reducer.apply(
        state,
        LookAction(tool="look"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.LOOKED, summary="看到两个出口。"),
        make_observation(route[-1], exits=(route[-2], "room_14")),
    )

    assert state.visited_locations == tuple(route[:12])
    assert state.visited_rooms == tuple(route)
    assert {(link.source, link.destination) for link in state.frontier} == {
        (route[-1], "room_14")
    }


def test_memory_v3_events_are_public_successes_and_reset_between_episodes() -> None:
    provider = FakeDecisionProvider([{}])
    agent = MemoryAgent(provider, memory_version="v3_spatial_event")
    start = make_observation("room_a", exits=("room_b",))
    destination = make_observation("room_b", exits=("room_a",), inventory=("key",))

    agent.reset(start)
    agent.observe(
        MoveAction(tool="move", destination="room_b"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
        destination,
    )
    agent.observe(
        LookAction(tool="look"),
        ToolResult(
            status=ToolStatus.SUCCESS,
            reason=ToolReason.POWER_RESTORED,
            summary="公开结果：供电已恢复。",
        ),
        destination,
    )
    first = agent._render_memory_data()
    assert '"reason":"power_restored"' in first
    assert '"source":"room_a","destination":"room_b"' in first

    second_agent = MemoryAgent(FakeDecisionProvider([{}]), memory_version="v3_spatial_event")
    second_agent.reset(start)
    second_agent.observe(
        MoveAction(tool="move", destination="room_b"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
        destination,
    )
    second_agent.observe(
        LookAction(tool="look"),
        ToolResult(
            status=ToolStatus.SUCCESS,
            reason=ToolReason.POWER_RESTORED,
            summary="公开结果：供电已恢复。",
        ),
        destination,
    )
    assert second_agent._render_memory_data() == first

    agent.finish("success")
    agent.reset(start)
    reset_data = agent._render_memory_data()
    assert "power_restored" not in reset_data
    assert agent.memory_statistics is not None
    assert agent.memory_statistics["invalidations"] == 0


def test_memory_v3_tracks_event_order_without_assuming_a_fixed_phase_sequence() -> None:
    reducer = MemoryV3Reducer()
    observation = make_observation("control_room")
    state = reducer.initialize(observation)
    state = reducer.apply(
        state,
        LookAction(tool="look"),
        ToolResult(
            status=ToolStatus.SUCCESS,
            reason=ToolReason.CODE_READ,
            summary="公开终端返回授权码。",
        ),
        observation,
    )
    state = reducer.apply(
        state,
        LookAction(tool="look"),
        ToolResult(
            status=ToolStatus.SUCCESS,
            reason=ToolReason.POWER_RESTORED,
            summary="公开结果显示供电恢复。",
        ),
        observation,
    )

    assert [(event.reason, event.first_seen_step) for event in state.public_events] == [
        ("code_read", 1),
        ("power_restored", 2),
    ]


def test_memory_v3_clears_a_public_precondition_question_after_repair() -> None:
    reducer = MemoryV3Reducer()
    observation = make_observation("reactor_room")
    state = reducer.initialize(observation)
    action = UseAction(tool="use", item="wrench", target="panel")
    state = reducer.apply(
        state,
        action,
        ToolResult(
            status=ToolStatus.REJECTED,
            reason=ToolReason.PANEL_CLOSED,
            summary="需要先打开面板。",
        ),
        observation,
    )
    assert [question.key for question in state.open_questions] == ["reactor_panel"]

    state = reducer.apply(
        state,
        action,
        ToolResult(
            status=ToolStatus.SUCCESS,
            reason=ToolReason.PANEL_OPENED,
            summary="面板已打开。",
        ),
        observation,
    )
    assert state.open_questions == ()
    assert len(state.failed_actions) == 1
    assert [event.reason for event in state.public_events] == ["panel_opened"]


def test_memory_v3_renderer_compacts_with_visible_omission_counts() -> None:
    agent = MemoryAgent(FakeDecisionProvider([{}]), memory_version="v3_spatial_event")
    agent.reset(make_observation("room_a"))
    assert isinstance(agent._memory, MemoryV3State)
    state = agent._memory
    agent._memory = state.model_copy(
        update={
            "facts": tuple(f"fact-{index}-" + "x" * 270 for index in range(24)),
            "failed_actions": tuple(
                FailedAction(
                    identity=f"failed-{index}",
                    action=LookAction(tool="look"),
                    result_summary="y" * 280,
                )
                for index in range(20)
            ),
        }
    )

    agent._refresh_v3_render_statistics()
    rendered = agent._render_memory_data()
    payload = json.loads(rendered.split("\n", 2)[2])

    assert len(rendered) <= MemoryV3Limits().max_rendered_chars
    assert payload["memory_omissions"]
    assert agent.memory_statistics is not None
    assert agent.memory_statistics["compactions"] == 1
    assert agent.memory_statistics["rendered_chars"] == len(rendered)
    assert agent.memory_statistics["estimated_tokens"] == (len(rendered) + 3) // 4


def test_memory_v3_fails_loudly_when_required_frontier_exceeds_payload_limit() -> None:
    agent = MemoryAgent(FakeDecisionProvider([{}]), memory_version="v3_spatial_event")
    exits = tuple(f"exit-{index}-" + "x" * 280 for index in range(64))

    with pytest.raises(ValueError, match="required public memory"):
        agent.reset(make_observation("room_a", exits=exits))


def test_memory_v3_fails_loudly_when_required_spatial_or_event_capacity_is_exceeded() -> None:
    with pytest.raises(ValueError, match="spatial memory"):
        MemoryV3Reducer(v3_limits=MemoryV3Limits(max_known_exits=1)).initialize(
            make_observation("room_a", exits=("room_b", "room_c"))
        )

    reducer = MemoryV3Reducer(v3_limits=MemoryV3Limits(max_visited_rooms=2))
    state = reducer.initialize(make_observation("room_a"))
    state = reducer.apply(
        state,
        MoveAction(tool="move", destination="room_b"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
        make_observation("room_b"),
    )
    with pytest.raises(ValueError, match="visited-room memory"):
        reducer.apply(
            state,
            MoveAction(tool="move", destination="room_c"),
            ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
            make_observation("room_c"),
        )

    reducer = MemoryV3Reducer(v3_limits=MemoryV3Limits(max_traversed_edges=1))
    state = reducer.initialize(make_observation("room_a"))
    state = reducer.apply(
        state,
        MoveAction(tool="move", destination="room_b"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
        make_observation("room_b"),
    )
    with pytest.raises(ValueError, match="spatial memory"):
        reducer.apply(
            state,
            MoveAction(tool="move", destination="room_c"),
            ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
            make_observation("room_c"),
        )

    reducer = MemoryV3Reducer(v3_limits=MemoryV3Limits(max_public_events=1))
    state = reducer.initialize(make_observation("room_a"))
    state = reducer.apply(
        state,
        LookAction(tool="look"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.PANEL_OPENED, summary="面板已开。"),
        make_observation("room_a"),
    )
    with pytest.raises(ValueError, match="causal-event memory"):
        reducer.apply(
            state,
            LookAction(tool="look"),
            ToolResult(
                status=ToolStatus.SUCCESS,
                reason=ToolReason.POWER_RESTORED,
                summary="供电已恢复。",
            ),
            make_observation("room_a"),
        )


def test_runner_records_v3_provenance_and_per_step_memory_statistics() -> None:
    settings = RuntimeSettings.load(
        {
            "provider": "fake",
            "agent": "memory",
            "memory_version": "v3_spatial_event",
            "step_limit": 1,
        },
        env_file=None,
    )
    provider = FakeDecisionProvider(
        [{"decision_reason": "查看当前地点", "action": {"tool": "look"}}]
    )
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        MemoryAgent(provider, memory_version="v3_spatial_event"),
        settings,
    ).run()

    assert trace.provenance.memory_schema_version == "v3"
    assert trace.provenance.memory_renderer_version == "v3_spatial_event"
    assert len(trace.steps) == 1
    assert trace.steps[0].memory_statistics is not None
    assert trace.steps[0].memory_statistics.insertions > 0
