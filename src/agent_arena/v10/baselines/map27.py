"""MAP-27 V10 基线：月球车多目标的 Oracle、公开启发式与消融（DCR-V10-30）。

- Oracle：电量宽裕的实例用 relay-first，电量收紧的实例用 stabilize-first（两条都离线验证过）；
- 启发式：Observation 驱动的 stabilize-first 状态机（只读位置/目标/货舱/电量/补给）；
- 消融：跳过样本/中继/伤员之一，或超载装第三件（触发货舱冲突）。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.worlds.scenario_v8.maps.map27 import _RELAY_FIRST, _STABILIZE_FIRST
from agent_arena.worlds.scenario_v8.models import V8Action

#: 公开拓扑（Observation 的 local_edges 会随位置给出，这里是策略的先验知识）。
EDGE_COST = {"B_S": 1, "S_R": 2, "R_P": 2, "P_E": 4, "S_E": 1}
ADJACENT = {
    "B": {"S": "B_S"},
    "S": {"B": "B_S", "R": "S_R", "E": "S_E"},
    "R": {"S": "S_R", "P": "R_P"},
    "P": {"R": "R_P", "E": "P_E"},
    "E": {"S": "S_E", "P": "P_E"},
}


def _route(start: str, goal: str) -> list[str]:
    """在公开拓扑上做 BFS，返回逐跳的 ``to`` 序列。"""

    if start == goal:
        return []
    frontier: list[tuple[str, list[str]]] = [(start, [])]
    seen = {start}
    while frontier:
        node, path = frontier.pop(0)
        for neighbour in ADJACENT.get(node, {}):
            if neighbour in seen:
                continue
            next_path = [*path, neighbour]
            if neighbour == goal:
                return next_path
            seen.add(neighbour)
            frontier.append((neighbour, next_path))
    return []


class LunarPolicy:
    """stabilize-first 的状态机；``skip`` 可关闭某一目标，``overload`` 会多装一件。"""

    def __init__(
        self,
        *,
        name: str = "public_stabilize_first",
        skip: str | None = None,
        overload: bool = False,
    ) -> None:
        self.name = name
        self.skip = skip
        self.overload = overload
        self._overloaded = False
        self._charging_done = False

    def reset(self) -> None:
        self._overloaded = False
        self._charging_done = False

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _cargo(observation: dict[str, Any]) -> list[str]:
        return [item["item_id"] for item in observation["cargo"]]

    def _drive_to(self, observation: dict[str, Any], goal: str) -> dict[str, Any]:
        route = _route(observation["location"], goal)
        if not route:
            return {"tool": "wait", "turns": 1}
        return {"tool": "drive", "to": route[0]}

    def _needs_charge(self, observation: dict[str, Any], goal: str) -> bool:
        """只在“下一段都付不起”时充电，避免扰动已验证的省电路线。"""

        if self._charging_done or observation["location"] != "S":
            return False
        if observation["charger_cells_remaining"] in (None, 0):
            return False
        if observation["battery"] >= observation["battery_capacity"]:
            return False
        route = _route("S", goal)
        if not route:
            return False
        first_hop = ADJACENT["S"][route[0]]
        return int(observation["battery"]) < EDGE_COST[first_hop]

    # ------------------------------------------------------------------ policy
    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        del history
        cargo = self._cargo(observation)
        objectives = observation["objectives"]
        location = observation["location"]
        supplies = observation["supplies_here"]
        sample_item = "sample_container"
        relay_item = "relay_repair_kit"
        medical_item = "medical_kit"

        if self.overload and not self._overloaded:
            # 多装一件（若本处有第三类物品）→ 触发货舱冲突
            candidates = {
                "B": [sample_item],
                "S": [relay_item, medical_item],
            }.get(location, [])
            if candidates:
                for item in candidates:
                    nearly_full = len(cargo) >= observation["cargo_capacity"] - 1
                    if supplies.get(item, 0) > 0 and nearly_full:
                        self._overloaded = True
                        return {"tool": "load", "item_id": item}

        # 0) 先把样本容器带上（后续采样要用，占一个货舱槽位）
        if sample_item not in cargo and supplies.get(sample_item, 0) > 0:
            return {"tool": "load", "item_id": sample_item}
        if sample_item not in cargo and location != "B":
            return self._drive_to(observation, "B")

        # 1) stabilize-first：医疗包 → E 现场稳定
        if self.skip != "rescue" and observation["survivor_state"] == "UNSUPPORTED":
            if medical_item not in cargo and supplies.get(medical_item, 0) > 0:
                return {"tool": "load", "item_id": medical_item}
            if medical_item not in cargo and location != "S":
                return self._drive_to(observation, "S")
            if location != "E":
                if self._needs_charge(observation, "E"):
                    self._charging_done = True
                    return {"tool": "charge"}
                return self._drive_to(observation, "E")
            return {
                "tool": "rescue",
                "operation": "field_stabilize",
                "item_id": medical_item,
            }

        # 2) 中继包 → R 修复 → 远程撤离
        if self.skip != "relay" and not objectives["relay_online"]:
            if relay_item not in cargo and supplies.get(relay_item, 0) > 0:
                return {"tool": "load", "item_id": relay_item}
            if relay_item not in cargo and location != "S":
                return self._drive_to(observation, "S")
            if location != "R":
                if self._needs_charge(observation, "R"):
                    self._charging_done = True
                    return {"tool": "charge"}
                return self._drive_to(observation, "R")
            return {"tool": "repair_relay"}

        if self.skip != "rescue" and objectives["relay_online"] and (
            observation["survivor_state"] == "STABILIZED"
        ):
            if location != "R":
                return self._drive_to(observation, "R")
            return {"tool": "rescue", "operation": "remote_evacuation"}

        # 3) 采样封存（P）
        if self.skip != "sample" and not objectives["sample_sealed"]:
            if location != "P":
                if self._needs_charge(observation, "P"):
                    self._charging_done = True
                    return {"tool": "charge"}
                return self._drive_to(observation, "P")
            return {"tool": "sample", "item_id": sample_item}

        # 4) 回 B 提交
        if location != "B":
            if self._needs_charge(observation, "B"):
                self._charging_done = True
                return {"tool": "charge"}
            return self._drive_to(observation, "B")
        return {"tool": "submit"}


def HEURISTIC() -> LunarPolicy:
    return LunarPolicy()


def oracle_actions(seed: int) -> list[dict[str, Any]]:
    """电量收紧的实例只有 stabilize-first 可行；逐个回放验证。"""

    environment = create_environment("MAP-27", environment_seed=seed)
    scripts = (_RELAY_FIRST, _STABILIZE_FIRST)
    for script in scripts:
        environment = create_environment("MAP-27", environment_seed=seed)
        for payload in script:
            if environment.is_terminal:
                break
            action = V8Action.model_validate(payload, strict=True)
            if not environment.accepts(action):
                break
            environment.step(action)
        if environment.is_success:
            return [dict(item) for item in script]
    raise AssertionError(f"MAP-27 seed {seed} 没有可行 Oracle 方案")


ABLATIONS = {
    "skip_sample": lambda: LunarPolicy(name="skip_sample", skip="sample"),
    "skip_relay": lambda: LunarPolicy(name="skip_relay", skip="relay"),
    "skip_rescue": lambda: LunarPolicy(name="skip_rescue", skip="rescue"),
    "overload": lambda: LunarPolicy(name="overload", overload=True),
}

__all__ = ["ABLATIONS", "HEURISTIC", "LunarPolicy", "oracle_actions"]
