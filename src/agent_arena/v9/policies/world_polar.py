"""V9 polar 世界的公开启发式策略（MAP-10 / MAP-11 / MAP-12）。

约束：策略只读取公开 Observation 与自己的历史记录；不 import 环境、
不访问 ``judge_state``、Oracle 动作或指标内部状态。

每个策略都带一个显式的 ``no_key_mechanism`` 消融：消融只关闭该图的核心机制
（MAP-10 不带随身燃料 / MAP-11 不出发补给 / MAP-12 不维修控制器），
用于检验指标能否区分“机制正确”与“机制缺失”。
"""

from __future__ import annotations

from typing import Any


def _move(edge_id: str) -> dict[str, Any]:
    """只提交 ``tool`` + ``edge_id``；``loaded_return`` 由环境按当前状态裁决。"""

    return {"tool": "move", "edge_id": edge_id}


class Map10Heuristic:
    """MAP-10：在 B 把随身燃料装满，走 B_E → E_T。

    公开依据：``carried_fuel`` 与 ``carry_capacity`` 可见，且动作词表包含
    ``load_fuel``；在 B 装满再出发是无需知道 3 单位门槛也能避免秒失败的安全默认。
    """

    name = "public_heuristic"

    def reset(self) -> None:
        return None

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        location = observation.get("location")
        carried = int(observation.get("carried_fuel") or 0)
        depot = int(observation.get("fuel_depot") or 0)
        capacity = int(observation.get("carry_capacity") or 5)
        generator_online = bool(observation.get("generator_online"))

        if location == "B" and not generator_online:
            if carried < capacity and depot > 0:
                quantity = min(capacity - carried, depot)
                return {"tool": "load_fuel", "quantity": quantity}
            if "B_E" in observation.get("visible_edges", []):
                return {"tool": "walk", "edge_id": "B_E"}
            return {"tool": "wait", "ticks": 1}
        if location == "E":
            if not generator_online:
                return {"tool": "activate_generator"}
            if "E_T" in observation.get("visible_edges", []):
                return {"tool": "walk", "edge_id": "E_T"}
            return {"tool": "wait", "ticks": 1}
        if location == "T":
            return {"tool": "transmit"}
        if location == "W":
            return {"tool": "walk", "edge_id": "W_T"}
        return {"tool": "wait", "ticks": 1}


class Map10NoFuelLoad(Map10Heuristic):
    """消融：不装随身燃料直接出发，复现 2 决策 ``GENERATOR_FUEL_SHORTAGE``。"""

    name = "no_key_mechanism"

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        location = observation.get("location")
        if location == "B":
            return {"tool": "walk", "edge_id": "B_E"}
        if location == "E":
            if not observation.get("generator_online"):
                return {"tool": "activate_generator"}
            return {"tool": "walk", "edge_id": "E_T"}
        if location == "T":
            return {"tool": "transmit"}
        return {"tool": "wait", "ticks": 1}


class Map11Heuristic:
    """MAP-11：先在 B 补满补给，再侦察，按后验在短线与长线之间二选一。

    公开依据：``carried_supply=0``、``supply_depot_B``、``carried_supply_capacity``
    与 ``resupply`` 词表足以支持“先补给出营”的安全默认；``posterior`` 决定路线。
    """

    name = "public_heuristic"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.route: str | None = None

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        location = observation.get("location")
        rescuer_at = observation.get("teammate_rescued", False)
        if not rescuer_at:
            if location == "B":
                carried = int(observation.get("carried_supply") or 0)
                depot = int(observation.get("supply_depot_B") or 0)
                capacity = int(observation.get("carried_supply_capacity") or 8)
                if carried < capacity and depot > 0:
                    quantity = min(capacity - carried, depot)
                    return {"tool": "resupply", "quantity": quantity}
                if observation.get("last_scout_signal") is None:
                    return {"tool": "scout"}
                if self.route is None:
                    posterior = float(
                        observation.get("posterior_unstable_probability_belief") or 0.5
                    )
                    self.route = "short" if posterior <= 0.5 else "long"
                return _move("B_P_SHORT" if self.route == "short" else "B_D_LONG")
            if location == "P":
                return _move("P_S_SHORT")
            if location == "D":
                return _move("D_Q_LONG")
            if location == "Q":
                return _move("Q_S_LONG")
            if location == "S":
                return {"tool": "rescue"}
        if location == "S":
            return _move("P_S_SHORT" if self.route != "long" else "Q_S_LONG")
        if location == "P":
            return _move("B_P_SHORT")
        if location == "Q":
            return _move("D_Q_LONG")
        if location == "D":
            return _move("B_D_LONG")
        return {"tool": "rest"}


class Map11NoResupply(Map11Heuristic):
    """消融：不补给直接出营，复现首段移动即 ``SUPPLY_SHORTAGE``。"""

    name = "no_key_mechanism"

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        location = observation.get("location")
        if not observation.get("teammate_rescued"):
            if location == "B":
                return _move("B_P_SHORT")
            if location == "P":
                return _move("P_S_SHORT")
            if location == "S":
                return {"tool": "rescue"}
        if location == "S":
            return _move("P_S_SHORT")
        if location == "P":
            return _move("B_P_SHORT")
        return {"tool": "rest"}


class Map12Heuristic:
    """MAP-12：把研究放在每天第一槽，第二槽用于零件两段转运；磨损日先维修。

    公开依据：``controller_online`` / ``maintenance_today`` / ``node_inventories``
    与 ``research_points`` / ``research_streak`` 反馈。研究需要连续三日才计分这一
    规则不在 Observation 里，所以策略保持“在线就每天研究”，用公开的
    ``research_points`` 变化确认周期，而不是假设周期长度。
    """

    name = "public_heuristic"

    REQUIRED_POINTS = 12
    PARTS_PER_REPAIR = 2

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._researched_day: int | None = None
        self._last_parts_target: str | None = None

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        day = int(observation.get("day") or 1)
        inventories = observation.get("node_inventories") or {}
        parts = inventories.get("parts") or {}
        parts_e = int(parts.get("E") or 0)
        parts_g = int(parts.get("G") or 0)
        parts_s = int(parts.get("S") or 0)
        online = bool(observation.get("controller_online"))

        if not online:
            if parts_e >= self.PARTS_PER_REPAIR:
                return {"tool": "repair_controller"}
            return self._haul_parts(parts_s, parts_g)

        points = int(observation.get("research_points") or 0)
        if self._researched_day != day and points < self.REQUIRED_POINTS:
            self._researched_day = day
            return {"tool": "research"}

        # 第二槽：为下一个磨损日预先囤 2 个零件到 E。
        if parts_e < 4:
            return self._haul_parts(parts_s, parts_g)
        return {"tool": "wait"}

    def _haul_parts(self, parts_s: int, parts_g: int) -> dict[str, Any]:
        if parts_g >= self.PARTS_PER_REPAIR:
            return {
                "tool": "transfer",
                "commodity": "parts",
                "from_node": "G",
                "to_node": "E",
                "edge_id": "E_G",
                "quantity": self.PARTS_PER_REPAIR,
            }
        if parts_s >= self.PARTS_PER_REPAIR:
            return {
                "tool": "transfer",
                "commodity": "parts",
                "from_node": "S",
                "to_node": "G",
                "edge_id": "G_S",
                "quantity": self.PARTS_PER_REPAIR,
            }
        return {"tool": "wait"}


class Map12NoMaintenance(Map12Heuristic):
    """消融：只研究、不维修也不转运；第 7 天起控制器永久离线，积分停在 6。"""

    name = "no_key_mechanism"

    def reset(self) -> None:
        self._researched_day = None

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        day = int(observation.get("day") or 1)
        if (
            observation.get("controller_online")
            and self._researched_day != day
            and int(observation.get("research_points") or 0) < 12
        ):
            self._researched_day = day
            return {"tool": "research"}
        return {"tool": "wait"}


HEURISTICS: dict[str, type] = {
    "MAP-10": Map10Heuristic,
    "MAP-11": Map11Heuristic,
    "MAP-12": Map12Heuristic,
}

ABLATIONS: dict[str, dict[str, type]] = {
    "MAP-10": {"no_key_mechanism": Map10NoFuelLoad},
    "MAP-11": {"no_key_mechanism": Map11NoResupply},
    "MAP-12": {"no_key_mechanism": Map12NoMaintenance},
}

__all__ = [
    "ABLATIONS",
    "HEURISTICS",
    "Map10Heuristic",
    "Map11Heuristic",
    "Map12Heuristic",
]
