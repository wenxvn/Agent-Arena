"""Discrete, player-dispatched trains and mutually exclusive track segments."""

from __future__ import annotations

from typing import Literal, cast

from agent_arena.arena import InteractAction, PublicStatusFact, ScenarioAction
from agent_arena.arena.scenario_models import ScenarioStatus
from agent_arena.worlds.scenario.base import (
    ScenarioActionResult,
    ScenarioEnvironment,
    ScenarioState,
    applied,
    rejected,
)

Difficulty = Literal["easy", "medium", "hard"]


class SubwayState(ScenarioState):
    positions: dict[str, int]
    routes: dict[str, str] = {}
    green_signals: set[str] = set()
    maintenance_lock: bool = False
    arrival_order: list[str] = []


class SubwayScenario(ScenarioEnvironment):
    def __init__(self, difficulty: Difficulty, seed: int = 0) -> None:
        self._difficulty = difficulty
        rooms = {
            "control": "地铁调度室。列车不会自动行驶；所有位置、信号和占用区段均公开。",
        }
        if difficulty == "easy":
            objects = {
                "switch": ("control", "道岔设为 NORTH。"),
                "signal_panel": ("control", "绿灯后可授权列车 1 前进。"),
                "train_1": ("control", "列车 1 每次 advance 仅前进一个区段。"),
            }
            interactions = {
                "switch": ("north", "south"),
                "signal_panel": ("green_train_1", "red_train_1"),
                "train_1": ("advance",),
            }
            trains = {"train_1": ["yard", "segment_1", "north_platform"]}
            positions = {"train_1": 0}
            deadline = None
        elif difficulty == "medium":
            objects = {
                "switch_a": ("control", "设定 A 车到 platform_a。"),
                "switch_b": ("control", "设定 B 车到 platform_b。"),
                "signal_panel": ("control", "分别为列车授权绿灯。"),
                "train_a": ("control", "A 车从西侧进入 single_track。"),
                "train_b": ("control", "B 车从东侧进入 single_track。"),
            }
            interactions = {
                "switch_a": ("platform_a",),
                "switch_b": ("platform_b",),
                "signal_panel": ("green_a", "green_b", "red_a", "red_b"),
                "train_a": ("advance",),
                "train_b": ("advance",),
            }
            trains = {
                "train_a": ["west_approach", "single_track", "platform_a"],
                "train_b": ["east_approach", "single_track", "platform_b"],
            }
            positions = {"train_a": 0, "train_b": 0}
            deadline = None
        else:
            objects = {
                "maintenance_console": (
                    "control",
                    "B 车维护锁会阻止其放行，解除操作消耗一个 tick。",
                ),
                "switch_panel": ("control", "分别为 A、B、C 设定各自终点。"),
                "signal_panel": ("control", "分别为三列车授权绿灯。"),
                "train_a": ("control", "A 车必须早于 C 车抵达终点。"),
                "train_b": ("control", "B 车受维护锁影响。"),
                "train_c": ("control", "C 车。"),
                "dispatch_clock": ("control", "18 tick 公開調度预算。"),
            }
            interactions = {
                "maintenance_console": ("release_b",),
                "switch_panel": ("route_a", "route_b", "route_c"),
                "signal_panel": ("green_a", "green_b", "green_c"),
                "train_a": ("advance",),
                "train_b": ("advance",),
                "train_c": ("advance",),
            }
            trains = {
                "train_a": ["a_entry", "shared_track", "platform_a"],
                "train_b": ["b_entry", "shared_track", "platform_b"],
                "train_c": ["c_entry", "shared_track", "platform_c"],
            }
            positions = {name: 0 for name in trains}
            deadline = 18
        exits: dict[str, tuple[str, ...]] = {"control": ()}
        definition = {
            "scenario_id": f"SU-{difficulty[0].upper()}",
            "source_design_id": f"SU-{difficulty[0].upper()}",
            "family": "subway",
            "difficulty": difficulty,
            "mechanic_version": "manual-dispatch-locking-v1",
            "rooms": rooms,
            "exits": exits,
            "objects": objects,
            "items": {},
            "trains": trains,
            "initial_positions": positions,
            "deadline": deadline,
        }
        self._train_routes = trains
        super().__init__(
            family="subway",
            difficulty=difficulty,
            scenario_id=f"SU-{difficulty[0].upper()}",
            public_goal="逐列配置道岔与信号，在共享区段安全互斥的前提下完成调度。",
            world="subway-escape",
            world_version=f"subway-escape-world-v3-{difficulty}-zh",
            mechanic_version="manual-dispatch-locking-v1",
            start_room="control",
            rooms=rooms,
            exits=exits,
            objects=objects,
            interactions=interactions,
            items={},
            definition=definition,
            seed=seed,
        )

    def _subway(self) -> SubwayState:
        return cast(SubwayState, self._require_state())

    def _initial_state(self, seed: int) -> SubwayState:
        positions = {name: 0 for name in self._train_routes}
        return SubwayState(
            seed=seed,
            current_room=self.start_room,
            positions=positions,
            maintenance_lock=False,
        )

    def _apply_family_action(self, action: ScenarioAction) -> ScenarioActionResult:
        if not isinstance(action, InteractAction):
            return rejected("该动作不适用于地铁调度。", "dispatch_action_rejected")
        state = self._subway()
        if self._difficulty == "easy":
            if action.target == "switch" and action.choice in {"north", "south"}:
                if state.positions["train_1"] > 0:
                    return rejected("列车驶入线路后道岔锁定，不能追溯改线。", "route_locked")
                state.routes["train_1"] = action.choice
                return applied(f"道岔已设为 {action.choice.upper()}。", "route_set")
            if action.target == "signal_panel" and action.choice in {
                "green_train_1",
                "red_train_1",
            }:
                state.green_signals = {"train_1"} if action.choice.startswith("green") else set()
                return applied("列车 1 信号已更新。", "signal_updated")
        if (
            self._difficulty == "hard"
            and action.target == "maintenance_console"
            and action.choice == "release_b"
        ):
            if not state.maintenance_lock:
                return rejected("B 车尚未触发维护锁。", "maintenance_not_active")
            if state.positions["train_b"] != len(self._train_routes["train_b"]) - 1:
                return rejected("B 车到站后才能解除维护锁。", "maintenance_train_not_arrived")
            state.maintenance_lock = False
            return applied("B 车维护锁已解除。", "maintenance_released")
        if action.target in {"switch_a", "switch_b"} and action.choice in {
            "platform_a",
            "platform_b",
        }:
            train = "train_a" if action.target == "switch_a" else "train_b"
            if state.positions[train] > 0:
                return rejected("列车驶入线路后路由锁定，不能追溯改线。", "route_locked")
            state.routes[train] = action.choice
            return applied(f"{train} 路由已锁定。", "route_set")
        if (
            self._difficulty == "hard"
            and action.target == "switch_panel"
            and action.choice in {"route_a", "route_b", "route_c"}
        ):
            train = f"train_{action.choice[-1]}"
            if state.maintenance_lock:
                return rejected("B 车维护锁定期间不能切换总道岔。", "maintenance_locked")
            if state.positions[train] > 0:
                return rejected("列车驶入线路后路由锁定，不能追溯改线。", "route_locked")
            state.routes[train] = f"platform_{action.choice[-1]}"
            return applied(f"{train} 路由已锁定。", "route_set")
        if action.target == "signal_panel" and action.choice.startswith("green_"):
            train = (
                f"train_{action.choice[-1]}"
                if self._difficulty == "hard"
                else f"train_{action.choice[-1]}"
            )
            state.green_signals.add(train)
            return applied(f"{train} 已获绿灯授权。", "signal_green")
        if action.target == "signal_panel" and action.choice.startswith("red_"):
            train = f"train_{action.choice[-1]}"
            state.green_signals.discard(train)
            return applied(f"{train} 信号已转红。", "signal_red")
        if action.target.startswith("train_") and action.choice == "advance":
            return self._advance_train(action.target, state)
        return rejected("该调度设备当前不接受此操作。", "dispatch_action_rejected")

    def _advance_train(self, train: str, state: SubwayState) -> ScenarioActionResult:
        if train not in self._train_routes:
            return rejected("未知列车。", "unknown_train")
        if train not in state.green_signals:
            return rejected("列车当前没有绿灯授权。", "signal_red")
        if train not in state.routes:
            return rejected("尚未为列车锁定目的路由。", "route_unset")
        positions = state.positions
        route = self._train_routes[train]
        expected_destination = "north" if self._difficulty == "easy" else f"platform_{train[-1]}"
        if state.routes[train] != expected_destination:
            return rejected("当前道岔路由与列车目标站台不一致。", "route_mismatch")
        next_index = positions[train] + 1
        if next_index >= len(route):
            return rejected("列车已抵达终点站台。", "already_arrived")
        next_segment = route[next_index]
        if next_segment in {"single_track", "shared_track"}:
            for other, index in positions.items():
                if other != train and self._train_routes[other][index] == next_segment:
                    return rejected("共享区段正在被另一列车占用。", "track_occupied")
        positions[train] = next_index
        if self._difficulty == "hard" and train == "train_b" and next_index == 1:
            state.maintenance_lock = True
        if next_index == len(route) - 1:
            state.arrival_order.append(train)
            if (
                self._difficulty == "hard"
                and train == "train_c"
                and "train_a" not in state.arrival_order
            ):
                state.terminal_status = ScenarioStatus.FAILURE
                state.failure_reason = "C 车早于 A 车抵达，违反公开优先顺序。"
                return applied("C 车已到站，但公开的 A 车优先条件被违反。", "priority_violated")
            expected = set(self._train_routes)
            if set(state.arrival_order) == expected:
                state.terminal_status = ScenarioStatus.SUCCESS
                state.score_components = {
                    "ticks_used": state.tick + 1,
                    "arrival_order": ",".join(state.arrival_order),
                }
        return applied(f"{train} 前进一个区段至 {next_segment}。", "train_advanced")

    def _public_status(self) -> tuple[PublicStatusFact, ...]:
        state = self._subway()
        facts = [
            PublicStatusFact(
                id="tick_budget",
                value=f"{state.tick}/18" if self._difficulty == "hard" else str(state.tick),
            ),
            PublicStatusFact(id="maintenance_lock", value=str(state.maintenance_lock).lower()),
            PublicStatusFact(id="arrivals", value=",".join(state.arrival_order) or "none"),
        ]
        for train, index in sorted(state.positions.items()):
            facts.append(
                PublicStatusFact(id=f"{train}_segment", value=self._train_routes[train][index])
            )
            facts.append(
                PublicStatusFact(id=f"{train}_route", value=state.routes.get(train, "unset"))
            )
            facts.append(
                PublicStatusFact(
                    id=f"{train}_signal",
                    value="green" if train in state.green_signals else "red",
                )
            )
        return tuple(facts)

    def _advance_tick(self) -> None:
        state = self._subway()
        if (
            self._difficulty == "hard"
            and state.tick >= 18
            and state.terminal_status is ScenarioStatus.RUNNING
        ):
            state.terminal_status = ScenarioStatus.FAILURE
            state.failure_reason = "公开的 18 tick 调度预算耗尽。"


__all__ = ["SubwayScenario"]
