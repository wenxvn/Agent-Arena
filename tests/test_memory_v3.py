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
from agent_arena.evaluation.trace import read_episode_trace, write_episode_trace
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
        prior_room_count = len(state.visited_rooms)
        prior_insertions = state.statistics.insertions
        prior_updates = state.statistics.updates
        prior_current_room = state.current_room
        state = reducer.apply(
            state,
            MoveAction(tool="move", destination=destination),
            ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
            make_observation(destination),
        )
        if prior_room_count == 12:
            assert len(state.visited_locations) == 12
            assert state.statistics.insertions - prior_insertions == 4
        if state.current_room != prior_current_room:
            assert state.statistics.updates - prior_updates == 1

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


def test_memory_v3_statistics_count_base_memory_insertions_and_updates() -> None:
    reducer = MemoryV3Reducer()
    initial = make_observation(
        "room_a", exits=("room_b",), inventory=("key",)
    ).model_copy(update={"visible_objects": ("screwdriver",)})
    state = reducer.initialize(initial)

    assert state.statistics.insertions == 5

    observation = make_observation(
        "room_a", inventory=("key", "replacement_fuse")
    ).model_copy(update={"visible_objects": ("screwdriver", "replacement_fuse")})
    state = reducer.apply(
        state,
        LookAction(tool="look"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.LOOKED, summary="发现新物品。"),
        observation,
    )
    assert state.statistics.insertions == 7
    assert state.statistics.updates == 1

    action = UseAction(tool="use", item="screwdriver", target="reactor_panel")
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
    assert state.statistics.insertions == 9
    assert state.statistics.updates == 1

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
    assert state.statistics.insertions == 10
    assert state.statistics.updates == 3
    assert state.statistics.invalidations == 0

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
    assert state.statistics.updates == 4


def test_memory_v3_replays_only_executed_actions_after_invalid_candidate_and_correction() -> None:
    settings = RuntimeSettings.load(
        {
            "provider": "fake",
            "world": "spaceship-escape",
            "world_version": "spaceship-escape-v2-zh",
            "agent": "memory",
            "memory_version": "v3_spatial_event",
            "step_limit": 1,
        },
        env_file=None,
    )
    provider = FakeDecisionProvider(
        [
            {"not": "a decision"},
            {
                "decision_reason": "尝试移动",
                "action": {"tool": "move", "destination": "reactor_room"},
            },
        ]
    )
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        MemoryAgent(provider, memory_version="v3_spatial_event"),
        settings,
    ).run()

    assert [step.event.value for step in trace.steps] == [
        "action_invalid",
        "correction_requested",
        "action_rejected",
    ]
    assert trace.steps[0].action is None
    assert trace.steps[1].action is None
    assert trace.steps[1].result is None

    replay_agent = MemoryAgent(
        FakeDecisionProvider([]), memory_version="v3_spatial_event"
    )
    replay_agent.reset(trace.steps[0].observation)
    for step in trace.steps:
        if (
            step.action is not None
            and step.result is not None
            and step.next_observation is not None
        ):
            replay_agent.observe(step.action, step.result, step.next_observation)

    assert isinstance(replay_agent._memory, MemoryV3State)
    assert replay_agent._memory.traversed_edges == ()
    assert replay_agent._memory.public_events == ()


def test_memory_v3_tracks_code_read_through_move_and_backtracking() -> None:
    reducer = MemoryV3Reducer()
    state = reducer.initialize(
        make_observation("room_a", exits=("room_b", "room_dead_end"))
    )
    state = reducer.apply(
        state,
        LookAction(tool="look"),
        ToolResult(
            status=ToolStatus.SUCCESS,
            reason=ToolReason.CODE_READ,
            summary="公开终端返回授权码。",
        ),
        make_observation("room_a", exits=("room_b", "room_dead_end")),
    )
    state = reducer.apply(
        state,
        MoveAction(tool="move", destination="room_b"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
        make_observation("room_b", exits=("room_a", "room_c")),
    )
    state = reducer.apply(
        state,
        MoveAction(tool="move", destination="room_a"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已返回。"),
        make_observation("room_a", exits=("room_b", "room_dead_end")),
    )

    assert state.current_room == "room_a"
    assert state.visited_rooms == ("room_a", "room_b")
    assert {(edge.source, edge.destination) for edge in state.traversed_edges} == {
        ("room_a", "room_b"),
        ("room_b", "room_a"),
    }
    assert {(link.source, link.destination) for link in state.frontier} == {
        ("room_a", "room_dead_end"),
        ("room_b", "room_c"),
    }
    assert [(event.reason, event.first_seen_step) for event in state.public_events] == [
        ("code_read", 1)
    ]


def test_memory_v3_does_not_infer_a_reverse_one_way_exit() -> None:
    reducer = MemoryV3Reducer()
    state = reducer.initialize(make_observation("room_a", exits=("room_b",)))
    state = reducer.apply(
        state,
        MoveAction(tool="move", destination="room_b"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.MOVED, summary="已移动。"),
        make_observation("room_b"),
    )

    assert [(link.source, link.destination) for link in state.known_exits] == [
        ("room_a", "room_b")
    ]
    assert state.frontier == ()


def test_memory_v3_replaces_stale_summary_for_the_same_public_event() -> None:
    agent = MemoryAgent(FakeDecisionProvider([]), memory_version="v3_spatial_event")
    observation = make_observation("reactor_room")
    stale_summary = "旧公开摘要：供电状态尚未稳定。"
    corrected_summary = "更正后的公开摘要：主电源稳定恢复。"
    agent.reset(observation)
    agent.observe(
        LookAction(tool="look"),
        ToolResult(
            status=ToolStatus.SUCCESS,
            reason=ToolReason.POWER_RESTORED,
            summary=stale_summary,
        ),
        observation,
    )
    agent.observe(
        LookAction(tool="look"),
        ToolResult(
            status=ToolStatus.SUCCESS,
            reason=ToolReason.POWER_RESTORED,
            summary=corrected_summary,
        ),
        observation,
    )

    payload = json.loads(agent._render_memory_data().split("\n", 2)[2])

    assert len(payload["public_events"]) == 1
    assert payload["public_events"][0]["summary"] == corrected_summary
    assert stale_summary not in json.dumps(payload, ensure_ascii=False)
    assert corrected_summary not in payload["facts"]


def test_memory_v3_replaces_a_stale_public_room_description() -> None:
    agent = MemoryAgent(FakeDecisionProvider([]), memory_version="v3_spatial_event")
    stale_description = "旧公开状态：反应堆仍然断电。"
    corrected_description = "更正后的公开状态：反应堆供电已恢复。"
    observation = make_observation("reactor_room").model_copy(
        update={"description": stale_description}
    )
    agent.reset(observation)
    agent.observe(
        LookAction(tool="look"),
        ToolResult(status=ToolStatus.SUCCESS, reason=ToolReason.LOOKED, summary="观察完成。"),
        observation.model_copy(update={"description": corrected_description}),
    )

    assert isinstance(agent._memory, MemoryV3State)
    payload = json.loads(agent._render_memory_data().split("\n", 2)[2])

    assert payload["room_facts"] == [
        {"room": "reactor_room", "description": corrected_description}
    ]
    assert stale_description not in json.dumps(payload, ensure_ascii=False)
    assert agent._memory.statistics.updates == 1
    assert agent._memory.statistics.invalidations == 0


def test_memory_v3_complete_trace_replay_has_a_stable_digest_frontier_and_event_order(
    tmp_path,
) -> None:
    def decision(reason: str, action: dict[str, str]) -> dict[str, object]:
        return {"decision_reason": reason, "action": action}

    decisions = [
        decision("前往走廊", {"tool": "move", "destination": "corridor"}),
        decision("前往储物室", {"tool": "move", "destination": "storage_room"}),
        decision("检查储物箱", {"tool": "inspect", "target": "storage_crate"}),
        decision("拿起螺丝刀", {"tool": "pickup", "item": "screwdriver"}),
        decision("拿起备用保险丝", {"tool": "pickup", "item": "replacement_fuse"}),
        decision("返回走廊", {"tool": "move", "destination": "corridor"}),
        decision("前往维修室", {"tool": "move", "destination": "maintenance_room"}),
        decision("前往反应堆室", {"tool": "move", "destination": "reactor_room"}),
        decision(
            "打开反应堆面板",
            {"tool": "use", "item": "screwdriver", "target": "reactor_panel"},
        ),
        decision(
            "更换损坏的保险丝",
            {"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"},
        ),
    ]
    settings = RuntimeSettings.load(
        {
            "provider": "fake",
            "world": "spaceship-escape",
            "world_version": "spaceship-escape-v2-zh",
            "agent": "memory",
            "memory_version": "v3_spatial_event",
            "step_limit": len(decisions),
        },
        env_file=None,
    )
    trace = EpisodeRunner(
        SpaceshipEscapeEnvironment(),
        MemoryAgent(
            FakeDecisionProvider(decisions), memory_version="v3_spatial_event"
        ),
        settings,
    ).run()
    public_trace = read_episode_trace(write_episode_trace(trace, tmp_path))

    def replay():
        agent = MemoryAgent(
            FakeDecisionProvider([]), memory_version="v3_spatial_event"
        )
        agent.reset(public_trace.steps[0].observation)
        for step in public_trace.steps:
            if (
                step.action is not None
                and step.result is not None
                and step.next_observation is not None
            ):
                agent.observe(step.action, step.result, step.next_observation)
        assert isinstance(agent._memory, MemoryV3State)
        return agent._memory

    first = replay()
    second = replay()
    event_order = tuple(
        (event.reason, event.first_seen_step) for event in first.public_events
    )

    assert public_trace.executed_action_count == len(decisions)
    assert first.step_index == public_trace.executed_action_count
    assert len(first.memory_digest) == 64
    assert first.memory_digest == second.memory_digest
    assert first.frontier == second.frontier
    assert event_order == tuple(
        (event.reason, event.first_seen_step) for event in second.public_events
    )
    assert event_order == (("panel_opened", 9), ("power_restored", 10))


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
