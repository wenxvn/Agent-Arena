"""T6：seeded 世界版本的确定性、差异性与 oracle 可解性（无模型）。"""
from __future__ import annotations

import pytest

from agent_arena.arena import ToolReason, ToolStatus, action_adapter
from agent_arena.worlds import create_environment
from agent_arena.worlds.spaceship_escape import load_spaceship_escape_definition
from agent_arena.worlds.variants import (
    CANDIDATE_CONTAINERS,
    SeededShipEnvironment,
    build_seeded_definition,
)


def _step(environment: SeededShipEnvironment, payload: dict) -> ToolReason:
    result, _ = environment.step(action_adapter.validate_python(payload))
    assert result.status is ToolStatus.SUCCESS
    return result.reason


def _move(environment: SeededShipEnvironment, destination: str) -> None:
    assert _step(environment, {"tool": "move", "destination": destination}) is ToolReason.MOVED


def _bfs_path(exits: dict[str, tuple[str, ...]], start: str, goal: str) -> list[str]:
    queue: list[tuple[str, list[str]]] = [(start, [])]
    visited = {start}
    while queue:
        room, path = queue.pop(0)
        if room == goal:
            return path
        for nxt in exits[room]:
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, [*path, nxt]))
    raise AssertionError(f"no public path from {start} to {goal}")


def _solve(environment: SeededShipEnvironment) -> None:
    """Oracle 程序化通关：只用公开转移 + 实际工具位置构造动作链。"""
    definition = environment.definition
    exits = {room.id: room.exits for room in definition.rooms}
    objects = {obj.id: obj for obj in definition.objects}
    tool_room = {item.id: objects[item.container_id].room_id for item in definition.items}

    observation = environment.reset(environment._state.seed)
    current = observation.current_room

    def goto(room: str) -> None:
        nonlocal current
        for hop in _bfs_path(exits, current, room):
            _move(environment, hop)
        current = room

    for room in dict.fromkeys(tool_room[item] for item in ("screwdriver", "replacement_fuse")):
        goto(room)
        container = next(
            item_container
            for item_container, room_id in
            ((item.container_id, tool_room[item.id]) for item in definition.items)
            if room_id == room
        )
        assert _step(environment, {"tool": "inspect", "target": container}) is ToolReason.INSPECTED
        for item_id in ("screwdriver", "replacement_fuse"):
            if tool_room[item_id] == room:
                assert (
                    _step(environment, {"tool": "pickup", "item": item_id})
                    is ToolReason.PICKED_UP
                )
    goto("reactor_room")
    assert (
        _step(
            environment,
            {"tool": "use", "item": "screwdriver", "target": "reactor_panel"},
        )
        is ToolReason.PANEL_OPENED
    )
    assert (
        _step(
            environment,
            {"tool": "use", "item": "replacement_fuse", "target": "damaged_fuse"},
        )
        is ToolReason.POWER_RESTORED
    )
    goto("control_room")
    result, _ = environment.step(
        action_adapter.validate_python({"tool": "read_terminal", "target": "control_terminal"})
    )
    assert result.reason is ToolReason.CODE_READ
    goto("escape_pod")
    assert (
        _step(environment, {"tool": "use", "item": "ALPHA-731", "target": "escape_pod"})
        is ToolReason.ESCAPED
    )
    assert environment.is_success()


def test_seeded_definition_is_deterministic_per_seed() -> None:
    assert build_seeded_definition(7).model_dump() == build_seeded_definition(7).model_dump()
    env_a = SeededShipEnvironment(seed=7)
    env_b = SeededShipEnvironment(seed=7)
    assert env_a.identity == env_b.identity


def test_seeded_tool_layout_varies_across_seeds() -> None:
    layouts = set()
    hashes = set()
    for seed in range(20):
        definition = build_seeded_definition(seed)
        layouts.add(tuple((item.id, item.container_id) for item in definition.items))
        hashes.add(
            SeededShipEnvironment(definition=definition, seed=seed).identity[3]
        )
    assert len(layouts) > 1
    assert len(hashes) > 1
    for seed in range(20):
        definition = build_seeded_definition(seed)
        containers = [item.container_id for item in definition.items]
        assert all(c in CANDIDATE_CONTAINERS for c in containers)
        assert len(set(containers)) == 2


def test_seeded_selector_and_gate() -> None:
    environment = create_environment("spaceship-escape", "spaceship-escape-v5-zh-seeded", seed=0)
    assert isinstance(environment, SeededShipEnvironment)
    assert environment.identity[:2] == ("spaceship-escape", "spaceship-escape-v5-zh-seeded")
    assert environment.identity[2] == "spaceship_escape_v1_seeded"
    environment.reset(0)
    for hop in ("corridor", "maintenance_room", "reactor_room"):
        result, _ = environment.step(
            action_adapter.validate_python({"tool": "move", "destination": hop})
        )
        assert result.status is ToolStatus.SUCCESS
    assert "escape_pod" not in environment._available_exits()
    observation = environment.observe()
    assert observation.current_room == "reactor_room"


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_seeded_oracle_solves_every_sample(seed: int) -> None:
    environment = create_environment(
        "spaceship-escape", "spaceship-escape-v5-zh-seeded", seed=seed
    )
    assert isinstance(environment, SeededShipEnvironment)
    _solve(environment)


def test_old_ship_definition_untouched() -> None:
    definition = load_spaceship_escape_definition()
    assert definition.world_id == "spaceship_escape_v1"
    assert {item.container_id for item in definition.items} == {"storage_crate"}
