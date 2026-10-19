"""MAP-01 V10 基线：生命支持依赖链的 Oracle、公开启发式与消融（DCR-V10-31）。

- Oracle：15 动作固定方案（供氧 → 取件 → 切臂 → 修壳 → 复供 → 母线 → 气闸 → 确认）；
- 启发式：只读 Observation 的状态机（含公开拓扑的 BFS 寻路）；
- 消融：不复供、不重置母线、修壳前先切臂、未测气闸就确认。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.worlds.scenario_v8.models import V8Action

PLAN: tuple[dict[str, Any], ...] = (
    {"tool": "interact", "target": "oxygen_relay", "choice": "start_support"},
    {"tool": "move", "edge_id": "B_H"},
    {"tool": "move", "edge_id": "H_W"},
    {"tool": "pickup", "item_id": "patch_kit"},
    {"tool": "interact", "target": "local_breaker", "choice": "route_arm"},
    {"tool": "interact", "target": "hull_panel", "choice": "apply_patch"},
    {"tool": "interact", "target": "local_breaker", "choice": "route_support"},
    {"tool": "move", "edge_id": "W_P_SERVICE"},
    {"tool": "interact", "target": "main_reactor", "choice": "reset_bus"},
    {"tool": "move", "edge_id": "H_P"},
    {"tool": "move", "edge_id": "H_A"},
    {"tool": "interact", "target": "airlock_console", "choice": "pressure_test"},
    {"tool": "move", "edge_id": "H_A"},
    {"tool": "move", "edge_id": "B_H"},
    {"tool": "interact", "target": "bridge_console", "choice": "confirm_repair"},
)

#: 公开拓扑（edge_id, 另一端）。
ADJACENCY = {
    "B": [("B_H", "H")],
    "H": [("B_H", "B"), ("H_W", "W"), ("H_P", "P"), ("H_A", "A")],
    "W": [("H_W", "H"), ("W_P_SERVICE", "P")],
    "P": [("H_P", "H"), ("W_P_SERVICE", "W")],
    "A": [("H_A", "H")],
}


def _route(start: str, goal: str, *, service_open: bool) -> list[tuple[str, str]]:
    if start == goal:
        return []
    frontier: list[tuple[str, list[tuple[str, str]]]] = [(start, [])]
    seen = {start}
    while frontier:
        node, path = frontier.pop(0)
        for edge_id, neighbour in ADJACENCY.get(node, []):
            if edge_id == "W_P_SERVICE" and not service_open:
                continue
            if neighbour in seen:
                continue
            next_path = [*path, (edge_id, neighbour)]
            if neighbour == goal:
                return next_path
            seen.add(neighbour)
            frontier.append((neighbour, next_path))
    return []


class LifeSupportPolicy:
    def __init__(
        self,
        *,
        name: str = "public_dependency_chain",
        restore_support: bool = True,
        reset_bus: bool = True,
        arm_first: bool = False,
        early_confirm: bool = False,
    ) -> None:
        self.name = name
        self.restore_support = restore_support
        self.reset_bus = reset_bus
        self.arm_first = arm_first
        self.early_confirm = early_confirm

    def reset(self) -> None:
        return None

    def _goto(self, observation: dict[str, Any], goal: str) -> dict[str, Any]:
        route = _route(
            observation["location"],
            goal,
            service_open=bool(observation["hull_intact"]),
        )
        if not route:
            return {"tool": "wait", "turns": 1}
        return {"tool": "move", "edge_id": route[0][0]}

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        del history
        location = observation["location"]
        branch = observation["routed_branch"]
        if self.early_confirm and not observation["pressure_test"] == "pass":
            return self._goto(observation, "B") if location != "B" else {
                "tool": "interact",
                "target": "bridge_console",
                "choice": "confirm_repair",
            }
        # 1) 供氧（B/H 才能启动）
        if not observation["oxygen_output"] and branch != "arm":
            if location in {"B", "H"}:
                return {
                    "tool": "interact",
                    "target": "oxygen_relay",
                    "choice": "start_support",
                }
            return self._goto(observation, "H")
        # 2) 取件
        if self.arm_first and "patch_kit" not in observation["inventory"]:
            if location == "W":
                return {"tool": "interact", "target": "local_breaker", "choice": "route_arm"}
            return self._goto(observation, "W")
        if "patch_kit" not in observation["inventory"] and not observation["hull_intact"]:
            if location == "W":
                return {"tool": "pickup", "item_id": "patch_kit"}
            return self._goto(observation, "W")
        # 3) 切维修臂
        if not observation["hull_intact"] and branch != "arm":
            if location == "W":
                return {"tool": "interact", "target": "local_breaker", "choice": "route_arm"}
            return self._goto(observation, "W")
        # 4) 修壳
        if not observation["hull_intact"]:
            return {"tool": "interact", "target": "hull_panel", "choice": "apply_patch"}
        # 5) 复供氧
        if self.restore_support and not observation["oxygen_output"]:
            if location == "W":
                return {"tool": "interact", "target": "local_breaker", "choice": "route_support"}
            return self._goto(observation, "W")
        # 6) 母线
        if self.reset_bus and not observation["main_bus"]:
            if location == "P":
                return {"tool": "interact", "target": "main_reactor", "choice": "reset_bus"}
            return self._goto(observation, "P")
        # 7) 气闸
        if observation["pressure_test"] != "pass":
            if location == "A":
                return {
                    "tool": "interact",
                    "target": "airlock_console",
                    "choice": "pressure_test",
                }
            return self._goto(observation, "A")
        # 8) 舰桥确认
        if location != "B":
            return self._goto(observation, "B")
        return {"tool": "interact", "target": "bridge_console", "choice": "confirm_repair"}


def HEURISTIC() -> LifeSupportPolicy:
    return LifeSupportPolicy()


def oracle_actions(seed: int) -> list[dict[str, Any]]:
    environment = create_environment("MAP-01", environment_seed=seed)
    for payload in PLAN:
        if environment.is_terminal:
            break
        action = V8Action.model_validate(payload, strict=True)
        if not environment.accepts(action):
            raise AssertionError(f"MAP-01 方案含非法动作：{payload}")
        environment.step(action)
    if not environment.is_success:
        raise AssertionError(
            f"MAP-01 seed {seed} 方案不可行（{environment.status.value}）"
        )
    return [dict(item) for item in PLAN]


ABLATIONS = {
    "no_support_restore": lambda: LifeSupportPolicy(
        name="no_support_restore", restore_support=False
    ),
    "skip_bus": lambda: LifeSupportPolicy(name="skip_bus", reset_bus=False),
    "arm_before_pickup": lambda: LifeSupportPolicy(name="arm_before_pickup", arm_first=True),
    "early_confirm": lambda: LifeSupportPolicy(name="early_confirm", early_confirm=True),
}

__all__ = ["ABLATIONS", "HEURISTIC", "LifeSupportPolicy", "PLAN", "oracle_actions"]
