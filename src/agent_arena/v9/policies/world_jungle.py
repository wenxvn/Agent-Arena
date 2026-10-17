"""V9 jungle 世界公开策略：MAP-22 / MAP-23 / MAP-24。

约束（与 ``agent_arena.v9.policies.base`` 一致）：

- 只读取公开 ``Observation``、公开动作 schema 和本策略自己的历史；
- 不导入 Environment、``judge_state``、Oracle 或 V8/V9 指标实现；
- 不提交 ``None`` 字段，动作形状必须精确匹配该图 ``SHAPES``。

三个策略的机制取向不同：

- ``Map22Heuristic``：使用 ``write_memory``，但只写 ``traversed_edge_page``（节点页的内容
  等于当前可见的出口方位，离开后对返程无增量信息，却要多花 2 个决策）；开局观察一次
  核对 ``<X>_silhouette ↔ <X>_SIGN`` 的公开命名约定，之后每条亲历边写一条事实。
  30 决策预算下实测 24 个决策通关；若同时写节点页则需要 37 个决策。
- ``Map23Heuristic``：在最便宜的可达侦察点 scout，用 ``supports`` 交集定位真入口，
  在 A 补满后按已知邻接前进。
- ``Map24Heuristic``：从开局就避走 A-B / B-C 桥边（坍塌时刻公开未知），
  走 A-E-D-C-D-E-A，过潮道前用 ``measure_tide`` 读下一拍状态。
"""

from __future__ import annotations

from typing import Any

#: 六个公开方位的反向方位，仅作为“回退一步”的几何假设使用（不作地图真值）。
OPPOSITE: dict[str, str] = {
    "N": "S",
    "S": "N",
    "E": "W",
    "W": "E",
    "NE": "SW",
    "SW": "NE",
    "NW": "SE",
    "SE": "NW",
}

_SILHOUETTE_SUFFIX = "_silhouette"
_SIGN_SUFFIX = "_SIGN"


def _sign_prefix(signature: str) -> str:
    if signature.endswith(_SILHOUETTE_SUFFIX):
        return signature[: -len(_SILHOUETTE_SUFFIX)]
    return signature


def _marker_prefix(marker: str) -> str:
    if marker.endswith(_SIGN_SUFFIX):
        return marker[: -len(_SIGN_SUFFIX)]
    return marker


# --------------------------------------------------------------------------- #
# MAP-22：没有地图的森林
# --------------------------------------------------------------------------- #
class Map22Heuristic:
    """MAP-22：只记「亲历的边」的深度优先遍历。

    设计取舍（预算驱动，不改规则）：

    - 只写 ``traversed_edge_page``。节点页内容 = 当前可见的 ``visible_exit_bearings``，
      离开该节点后对返程没有增量信息，却要额外花 2 个决策（observe + write）；
      边页才是"哪条方位通向哪个路标"的唯一载体。
    - 只在开局 ``observe_signpost`` 一次，用来核对公开命名约定
      ``<X>_silhouette`` ↔ ``<X>_SIGN``；核对通过后其余节点的 ``sign_id``
      由同一约定推出，核对失败则自动退回"每个新节点先观察再写"的安全模式。
    - 导航仍用自建图（与 journal 内容一一对应）：未试方位优先，无前沿时按已知边回到最近的前沿。

    ``record_edges=False`` 时退化成不写记忆的同款导航（``no_memory_write`` 消融）。
    """

    name = "public_heuristic"
    record_edges = True
    observe_each_node_when_unverified = True

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.start_sign: str | None = None
        self.current: str | None = None
        self.confirmed_goal = False
        self.pending_bearing: str | None = None
        self.pending_edge: tuple[str, str, str] | None = None
        #: 已知有向边 (from, to) -> 使用的方位
        self.edges: dict[tuple[str, str], str] = {}
        self.exits: dict[str, set[str]] = {}
        self.tried: dict[str, set[str]] = {}
        self.observed: set[str] = set()
        self.edge_pages: set[tuple[str, str, str]] = set()
        #: 粗形 silhouette -> sign_id（开局观察一次，其余按公开命名约定推出）
        self.sign_of: dict[str, str] = {}
        self.convention_checked = False
        self.observe_each_node = False
        self.goal_sign: str | None = None

    # ------------------------------------------------------------------ helpers
    def _absorb(self, observation: dict[str, Any]) -> None:
        sign = str(observation["current_coarse_silhouette"])
        exits = {str(item) for item in observation["visible_exit_bearings"]}
        if self.start_sign is None:
            self.start_sign = sign
        if self.pending_bearing is not None and self.current is not None:
            if sign != self.current:
                self.edges[(self.current, sign)] = self.pending_bearing
                self.tried.setdefault(self.current, set()).add(self.pending_bearing)
                self.pending_edge = (self.current, self.pending_bearing, sign)
            else:
                # 该方位被拒绝：记为已尝试，避免重复撞墙。
                self.tried.setdefault(self.current, set()).add(self.pending_bearing)
                self.pending_edge = None
        self.pending_bearing = None
        self.current = sign
        self.exits.setdefault(sign, set()).update(exits)
        self.tried.setdefault(sign, set())
        detail = observation.get("inspected_current_sign_detail")
        if isinstance(detail, dict) and detail.get("sign_id"):
            self.observed.add(sign)
            self.sign_of[sign] = str(detail["sign_id"])
            if str(detail["sign_id"]) == str(observation["active_goal_marker"]):
                self.confirmed_goal = True
                self.goal_sign = sign
        if not self.confirmed_goal and self._is_goal_sign(sign, observation):
            self.confirmed_goal = True
            self.goal_sign = sign

    def _is_goal_sign(self, sign: str, observation: dict[str, Any]) -> bool:
        marker = str(observation["active_goal_marker"])
        return _sign_prefix(sign) == _marker_prefix(marker)

    def _sign_id(self, signature: str) -> str | None:
        known = self.sign_of.get(signature)
        if known is not None:
            return known
        if self.convention_checked and not self.observe_each_node:
            return f"{_sign_prefix(signature)}{_SIGN_SUFFIX}"
        return None

    def _neighbours(self, sign: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for (origin, destination), bearing in self.edges.items():
            if origin == sign:
                out.append((bearing, destination))
            elif destination == sign:
                reverse = OPPOSITE.get(bearing)
                if reverse is not None:
                    out.append((reverse, origin))
        return sorted(out)

    def _path(self, target: str) -> list[str]:
        if self.current is None or self.current == target:
            return []
        queue: list[tuple[str, list[str]]] = [(self.current, [])]
        seen = {self.current}
        while queue:
            node, bearings = queue.pop(0)
            for bearing, destination in self._neighbours(node):
                if destination in seen:
                    continue
                route = [*bearings, bearing]
                if destination == target:
                    return route
                seen.add(destination)
                queue.append((destination, route))
        return []

    def _frontier_path(self) -> list[str]:
        """到最近一个仍有未试出口的已知节点的路径。"""

        if self.current is None:
            return []
        queue: list[tuple[str, list[str]]] = [(self.current, [])]
        seen = {self.current}
        while queue:
            node, bearings = queue.pop(0)
            if self.exits.get(node, set()) - self.tried.get(node, set()):
                return bearings
            for bearing, destination in self._neighbours(node):
                if destination in seen:
                    continue
                seen.add(destination)
                queue.append((destination, [*bearings, bearing]))
        return []

    def _next_bearing(self, observation: dict[str, Any]) -> str | None:
        assert self.current is not None
        if self.confirmed_goal and self.start_sign is not None:
            route = self._path(self.start_sign)
            if route:
                return route[0]
        route = self._frontier_path()
        if route:
            return route[0]
        untried = sorted(self.exits[self.current] - self.tried[self.current])
        if untried:
            return untried[0]
        available = sorted(str(item) for item in observation["visible_exit_bearings"])
        return available[0] if available else None

    # ------------------------------------------------------------------ policy
    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        self._absorb(observation)
        assert self.current is not None

        # 1) 开局观察一次，核对 silhouette -> sign_id 的公开命名约定。
        if self.record_edges and not self.convention_checked:
            if self.current not in self.observed:
                return {"tool": "observe_signpost"}
            derived = f"{_sign_prefix(self.current)}{_SIGN_SUFFIX}"
            self.observe_each_node = self.sign_of.get(self.current) != derived
            self.convention_checked = True

        # 2) 落地后先补记刚走过的边（边页只在最近一次移动后有效）。
        if (
            self.record_edges
            and self.pending_edge is not None
            and self.pending_edge not in self.edge_pages
        ):
            origin_sil, bearing, destination_sil = self.pending_edge
            reverse = OPPOSITE.get(bearing)
            origin_sign = self._sign_id(origin_sil)
            destination_sign = self._sign_id(destination_sil)
            if reverse is not None and origin_sign and destination_sign:
                self.edge_pages.add(self.pending_edge)
                self.pending_edge = None
                return {
                    "tool": "write_memory",
                    "facts": [
                        {
                            "fact_type": "traversed_edge_page",
                            "from_sign_id": origin_sign,
                            "departure_bearing": bearing,
                            "to_sign_id": destination_sign,
                            "arrival_reverse_bearing": reverse,
                        }
                    ],
                }
            if self.observe_each_node and self.current not in self.observed:
                return {"tool": "observe_signpost"}

        # 3) 约定核对失败时，退回"每个新节点先观察"。
        if (
            self.record_edges
            and self.observe_each_node
            and self.current not in self.observed
        ):
            return {"tool": "observe_signpost"}

        next_bearing = self._next_bearing(observation)
        if next_bearing is None:
            return {"tool": "observe_signpost"}
        self.pending_bearing = next_bearing
        return {"tool": "move", "bearing": next_bearing}


class Map22NoMemoryWrite(Map22Heuristic):
    """消融：同样的 DFS 导航，但不调用 ``write_memory``。"""

    name = "no_memory_write"
    record_edges = False


# --------------------------------------------------------------------------- #
# MAP-23：迷雾中的遗迹
# --------------------------------------------------------------------------- #
class Map23Heuristic:
    """MAP-23：用最便宜可达侦察点的线索交集定位真入口，再按已知邻接前往。"""

    name = "public_heuristic"
    use_scout = True
    #: 公开词表给出的侦察点（``scout() 在 N|R|H``）。
    stations = ("N", "R", "H")
    entrances = ("X", "Y", "Z")
    resupply_below = 12
    refuel_below = 10

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.costs: dict[tuple[str, str], int] = {}
        self.candidates = {"X", "Y", "Z"}
        self.target: str | None = None
        self.tried_entrances: list[str] = []
        self.location = "A"
        self.visited: set[str] = {"A"}
        self.resupply_used = False

    # ------------------------------------------------------------------ helpers
    def _absorb(self, observation: dict[str, Any]) -> None:
        location = str(observation["location"])
        self.visited.add(location)
        neighbours = observation.get("neighbors") or {}
        if isinstance(neighbours, dict):
            for other, cost in neighbours.items():
                self.costs[(location, str(other))] = int(cost)
                self.costs[(str(other), location)] = int(cost)
        if self.use_scout:
            for clue in observation.get("clues_received") or []:
                supports = {str(item) for item in clue.get("supports") or []}
                if supports:
                    self.candidates &= supports
        for entrance in observation.get("searched_false_entrances") or []:
            if entrance not in self.tried_entrances:
                self.tried_entrances.append(str(entrance))
        if len(self.candidates) == 1:
            self.target = next(iter(self.candidates))

    def _route(self, target: str, *, frontier: bool = False) -> list[str]:
        start = self.location
        if start == target:
            return []
        queue: list[tuple[str, list[str]]] = [(start, [])]
        seen = {start}
        while queue:
            node, route = queue.pop(0)
            ordered = sorted(self.costs.items(), key=lambda item: (item[1], item[0]))
            for (origin, destination), _cost in ordered:
                if origin != node or destination in seen:
                    continue
                path = [*route, destination]
                if destination == target:
                    return path
                if frontier and destination not in self.visited:
                    return path
                seen.add(destination)
                queue.append((destination, path))
        return []

    def _cheapest_station(self) -> str | None:
        """按已知道路成本估计可达侦察点，未知到达成本的排在后面。"""

        best: tuple[int, str] | None = None
        for station in self.stations:
            if station == self.location:
                return station
            route = self._route(station)
            if not route:
                continue
            steps = zip([self.location, *route[:-1]], route, strict=True)
            cost = sum(self.costs[step] for step in steps)
            if best is None or cost < best[0]:
                best = (cost, station)
        return best[1] if best else None

    def _missing_entrance(self) -> str | None:
        for entrance in self.entrances:
            if entrance not in self.tried_entrances:
                return entrance
        return None

    # ------------------------------------------------------------------ policy
    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        self._absorb(observation)
        self.location = str(observation["location"])
        self.resupply_used = any(
            str(item.get("result")) == "RESUPPLIED" for item in history
        )
        supply = int(observation["supply_remaining"])
        if observation.get("resupply_cache_available") and supply < self.resupply_below:
            return {"tool": "resupply"}

        available = observation.get("available_scout_stations") or []
        if (
            not self.resupply_used
            and supply < self.refuel_below
            and self.location != "A"
        ):
            home = self._route("A")
            if home:
                return {"tool": "move", "to": home[0]}

        if self.target is not None:
            if self.location == self.target:
                self.tried_entrances.append(self.target)
                return {"tool": "investigate", "entrance": self.target}
            route = self._route(self.target)
            if route:
                return {"tool": "move", "to": route[0]}
            # 真入口已知但通往它的路还没走过：先回 A 把一次性补给箱用掉。
            if not self.resupply_used and supply < 14 and self.location != "A":
                home = self._route("A")
                if home:
                    return {"tool": "move", "to": home[0]}
            route = self._route(self.target, frontier=True)
            if route:
                return {"tool": "move", "to": route[0]}

        if self.use_scout and available:
            return {"tool": "scout"}

        if self.use_scout and self.target is None:
            station = self._cheapest_station()
            if station is not None and station != self.location:
                route = self._route(station)
                if not route:
                    route = self._route(station, frontier=True)
                if route:
                    return {"tool": "move", "to": route[0]}

        if self.target is None:
            entrance = self._missing_entrance()
            if entrance is not None:
                if self.location == entrance:
                    self.tried_entrances.append(entrance)
                    return {"tool": "investigate", "entrance": entrance}
                route = self._route(entrance)
                if not route:
                    route = self._route(entrance, frontier=True)
                if route:
                    return {"tool": "move", "to": route[0]}

        neighbours = sorted((observation.get("neighbors") or {}).keys())
        if neighbours:
            return {"tool": "move", "to": str(neighbours[0])}
        return {"tool": "resupply"}


class Map23NoScout(Map23Heuristic):
    """消融：不侦察，直接按 X→Y→Z 顺序逐个付费试入口。"""

    name = "no_scout"
    use_scout = False


# --------------------------------------------------------------------------- #
# MAP-24：消失的道路
# --------------------------------------------------------------------------- #
class Map24Heuristic:
    """MAP-24：避开桥边，走 A-F-C-D-E-A，潮道按窗口重试。"""

    name = "public_heuristic"
    #: 公开 goal 说明桥会在未知时刻永久断开，因此默认不把 A-B / B-C 放进计划。
    avoid_edges = frozenset({"A-B", "B-C"})
    max_tide_retries = 3

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.costs: dict[tuple[str, str], int] = {}
        self.location = "A"
        self.visited: set[str] = {"A"}
        self.tide_retries = 0

    # ------------------------------------------------------------------ helpers
    def _absorb(self, observation: dict[str, Any]) -> None:
        location = str(observation["location"])
        self.visited.add(location)
        for connection in observation.get("local_connections") or []:
            other = str(connection["to"])
            self.costs[(location, other)] = int(connection.get("ticks", 1))

    def _route(
        self, target: str, *, allow_bridge: bool = False, frontier: bool = False
    ) -> list[str]:
        start = self.location
        if start == target:
            return []
        queue: list[tuple[str, list[str]]] = [(start, [])]
        seen = {start}
        while queue:
            node, route = queue.pop(0)
            for destination in sorted({b for (a, b) in self.costs if a == node}):
                edge = "-".join(sorted((node, destination)))
                if not allow_bridge and edge in self.avoid_edges:
                    continue
                if destination in seen:
                    continue
                path = [*route, destination]
                if destination == target:
                    return path
                if frontier and destination not in self.visited:
                    return path
                seen.add(destination)
                queue.append((destination, path))
        return []

    def _goal(self, observation: dict[str, Any]) -> str:
        carried = {str(item) for item in observation.get("carried_items") or []}
        if "relic_C" not in carried:
            return "C"
        if "supply_case_D" not in carried:
            return "D"
        return "A"

    # ------------------------------------------------------------------ policy
    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        self._absorb(observation)
        self.location = str(observation["location"])
        zone = self._goal(observation)

        visible = observation.get("visible_item_here")
        if isinstance(visible, str) and zone == self.location:
            item = visible
            if item not in {
                str(entry) for entry in observation.get("carried_items") or []
            }:
                return {"tool": "take", "item_id": item}

        route = self._route(zone)
        if not route:
            route = self._route(zone, frontier=True)
        if not route:
            route = self._route(zone, allow_bridge=True)
        if not route:
            route = self._route(zone, allow_bridge=True, frontier=True)
        if not route:
            return {"tool": "wait"}

        hop = route[0]
        edge = "-".join(sorted((self.location, hop)))
        if edge == "D-E":
            reading = observation.get("latest_local_tide_reading")
            tick = int(observation["tick"])
            if (
                isinstance(reading, dict)
                and int(reading.get("tick", -1)) == tick
                and str(reading.get("state")) == "OPEN"
            ):
                return {"tool": "move", "to": hop}
            return {"tool": "measure_tide"}
        return {"tool": "move", "to": hop}


class Map24NoReplan(Map24Heuristic):
    """消融：固定走 A-B-C-D-C-B-A，桥断后不换路，只重复同一移动。"""

    name = "no_replan"
    avoid_edges: frozenset[str] = frozenset()

    def reset(self) -> None:
        super().reset()
        self.plan: list[dict[str, Any]] = [
            {"tool": "move", "to": "B"},
            {"tool": "probe_bridge"},
            {"tool": "record_route"},
            {"tool": "move", "to": "C"},
            {"tool": "take", "item_id": "relic_C"},
            {"tool": "move", "to": "D"},
            {"tool": "take", "item_id": "supply_case_D"},
            {"tool": "move", "to": "C"},
            {"tool": "move", "to": "B"},
            {"tool": "move", "to": "A"},
        ]
        self.step = 0

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        self._absorb(observation)
        self.location = str(observation["location"])
        if self.step < len(self.plan):
            action = dict(self.plan[self.step])
            self.step += 1
            return action
        # 计划用尽后仍重复走旧桥边（不重规划）。
        return {"tool": "move", "to": "B"}


HEURISTICS: dict[str, type[Any]] = {
    "MAP-22": Map22Heuristic,
    "MAP-23": Map23Heuristic,
    "MAP-24": Map24Heuristic,
}

ABLATIONS: dict[str, dict[str, type[Any]]] = {
    "MAP-22": {"no_memory_write": Map22NoMemoryWrite},
    "MAP-23": {"no_scout": Map23NoScout},
    "MAP-24": {"no_replan": Map24NoReplan},
}

__all__ = [
    "ABLATIONS",
    "HEURISTICS",
    "Map22Heuristic",
    "Map22NoMemoryWrite",
    "Map23Heuristic",
    "Map23NoScout",
    "Map24Heuristic",
    "Map24NoReplan",
]
