"""V9 abyss 世界（MAP-07/08/09）的公开启发式基线。

三张图的策略彼此独立，不复用同一套路线模板：

- ``Map07Heuristic``：按“先泵后阀、下游优先”的固定次序操作控制台。运行时
  ``target_id`` 必须是 ``control_panel``，而 V8 公开词表写的是 ``console``
  （见 ``agent_arena.v8.prompts._VOCABULARY``）；该常量无法从公开 Observation
  推出，因此本策略是**规则可解性探针**，不是“仅凭公开信息即可复现”的证据。
- ``Map08Heuristic``：只用公开的 ``known_test_semantics``、``test_results``、
  ``published_candidate_set`` 和 ``visible_edges`` 做假设消减。``visible_edges``
  在 V4 适配层里是 ``"A_B:B"`` 形式，策略按 ``:`` 切出真实 ``edge_id``。
- ``Map09Heuristic``：先封舱再依次恢复发电、供氧并发报。首动作必须是封舱或
  最多让一个 1 tick 动作先跑完：漏水每 tick 把 1 单位水从 P 推到 E，E>4 立即
  短路，而初态 E=3。该速率与阈值**不在**公开 prompt/词表中，``isolate_compartment``
  也不在公开词表里，因此本策略同样是规则可解性探针。

所有策略只读公开 Observation 与自己的历史，不访问 Environment、judge_state
或 Oracle。
"""

from __future__ import annotations

import re
from typing import Any

_READING = re.compile(r"([A-Za-z0-9_]+)\s*读数为\s*([A-Za-z0-9_]+)")

#: MAP-07 控制台的运行时合法 target_id。公开词表写的是 ``console``（会被拒绝）。
MAP07_PANEL = "control_panel"


def _wait(ticks: int = 1) -> dict[str, Any]:
    return {"tool": "wait", "ticks": ticks}


class Map07Heuristic:
    """下游优先：先启泵，再按 v3 → v2 → v1 打开，最后等待两个流水 tick。"""

    name = "public_heuristic"
    VALVE_ORDER = ("v3", "v2", "v1")

    def reset(self) -> None:
        return None

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        valves = observation.get("valves") or {}
        if not observation.get("pump_active"):
            return {
                "tool": "interact",
                "target_id": MAP07_PANEL,
                "operation": "start_pump",
                "arguments": {},
            }
        for valve in self.VALVE_ORDER:
            if not valves.get(valve, False):
                return {
                    "tool": "interact",
                    "target_id": MAP07_PANEL,
                    "operation": "set_valve",
                    "arguments": {"valve_id": valve, "open": True},
                }
        # 阀门全部打开后只剩等待，直到连续两个低水位 tick 触发成功。
        return _wait()


class Map08Heuristic:
    """先 X 后 Y 的压力测试消减候选集，只剩一个候选时再动密封剂。

    只用公开信息：候选集、签名表、测试结果、可见边。``visible_edges`` 的
    ``"edge_id:other"`` 形式由适配层产生，策略只做字符串切分，不假设隐藏图。
    """

    name = "public_heuristic"
    STATION_ORDER = ("X", "Y")

    def reset(self) -> None:
        self._graph: dict[str, dict[str, str]] = {}

    # ------------------------------------------------------------------ public
    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        self._remember(observation)
        location = str(observation.get("location") or "")
        if int(observation.get("sealant_count") or 0) <= 0:
            return {"tool": "wait", "turns": 1}
        candidates = self._consistent(observation)
        if not candidates:
            return {"tool": "wait", "turns": 1}
        if len(candidates) == 1:
            return self._repair_or_move(location, candidates[0])
        station = self._next_station(observation, candidates)
        if station is None:
            return self._repair_or_move(location, candidates[0])
        if location == station:
            return {
                "tool": "interact",
                "target_id": station,
                "operation": f"pressure_test_{station}",
            }
        return self._move_towards(location, station)

    # --------------------------------------------------------------- diagnosis
    @staticmethod
    def _signatures(observation: dict[str, Any]) -> dict[str, dict[str, str]]:
        raw = observation.get("known_test_semantics")
        table: dict[str, dict[str, str]] = {}
        if not isinstance(raw, dict):
            return table
        for station, text in raw.items():
            if not isinstance(station, str) or not isinstance(text, str):
                continue
            for site, reading in _READING.findall(text):
                table.setdefault(site, {})[station] = reading
        return table

    def _consistent(self, observation: dict[str, Any]) -> list[str]:
        table = self._signatures(observation)
        raw = observation.get("published_candidate_set")
        candidates = [str(item) for item in raw] if isinstance(raw, (list, tuple)) else []
        if not candidates:
            candidates = sorted(table)
        results = observation.get("test_results") or {}
        remaining = list(candidates)
        for station, reading in results.items():
            if not isinstance(station, str) or not isinstance(reading, str):
                continue
            narrowed = [
                site
                for site in remaining
                if table.get(site, {}).get(station) == reading
            ]
            if narrowed:
                remaining = narrowed
        return remaining

    def _next_station(
        self, observation: dict[str, Any], candidates: list[str]
    ) -> str | None:
        table = self._signatures(observation)
        results = observation.get("test_results") or {}
        for station in self.STATION_ORDER:
            if station in results:
                continue
            readings = {
                table.get(site, {}).get(station) for site in candidates
            }
            readings.discard(None)
            if len(readings) > 1:
                return station
        return None

    # -------------------------------------------------------------- navigation
    def _remember(self, observation: dict[str, Any]) -> None:
        location = str(observation.get("location") or "")
        if not location:
            return
        edges = observation.get("visible_edges") or []
        row: dict[str, str] = {}
        for token in edges:
            if not isinstance(token, str) or ":" not in token:
                continue
            edge_id, other = token.split(":", 1)
            if edge_id and other:
                row[edge_id] = other
        if row:
            self._graph[location] = row

    def _nodes(self) -> set[str]:
        nodes = set(self._graph)
        for row in self._graph.values():
            nodes.update(row.values())
        return nodes

    def _repair_or_move(self, location: str, target: str) -> dict[str, Any]:
        if location == target:
            return {
                "tool": "interact",
                "target_id": target,
                "operation": "repair_leak",
            }
        return self._move_towards(location, target)

    def _move_towards(self, location: str, target: str) -> dict[str, Any]:
        edge: str | None = None
        if target in self._nodes():
            edge = self._bfs_edge(location, target)
        if edge is None:
            edge = self._frontier_edge(location)
        if edge is None:
            hub = self._nearest_unvisited(location)
            if hub is not None and hub != location:
                edge = self._bfs_edge(location, hub)
        if edge is None:
            return {"tool": "wait", "turns": 1}
        return {"tool": "move", "edge_id": edge}

    def _adjacency(self) -> dict[str, list[tuple[str, str]]]:
        adjacency: dict[str, list[tuple[str, str]]] = {}
        for node, row in self._graph.items():
            for edge_id, other in row.items():
                adjacency.setdefault(node, []).append((edge_id, other))
                adjacency.setdefault(other, []).append((edge_id, node))
        return adjacency

    def _bfs_edge(self, start: str, target: str) -> str | None:
        if start == target:
            return None
        adjacency = self._adjacency()
        queue: list[tuple[str, str | None]] = [(start, None)]
        seen = {start}
        while queue:
            node, first_edge = queue.pop(0)
            for edge_id, other in sorted(adjacency.get(node, [])):
                if other in seen:
                    continue
                seen.add(other)
                edge = first_edge or edge_id
                if other == target:
                    return edge
                queue.append((other, edge))
        return None

    def _frontier_edge(self, location: str) -> str | None:
        visited = set(self._graph)
        unknown = [
            (edge_id, other)
            for edge_id, other in sorted(
                self._graph.get(location, {}).items(), reverse=True
            )
            if other not in visited
        ]
        return unknown[0][0] if unknown else None

    def _nearest_unvisited(self, location: str) -> str | None:
        visited = set(self._graph)
        adjacency = self._adjacency()
        queue = [location]
        seen = {location}
        while queue:
            node = queue.pop(0)
            for _, other in sorted(adjacency.get(node, [])):
                if other in seen:
                    continue
                if other not in visited:
                    return other
                seen.add(other)
                queue.append(other)
        return None


class Map08NoHypothesis:
    """消融：不做任何测试，直接把密封剂用在公开候选集的第一个候选上。

    seed=0 的真实漏点恰好是 B，所以该消融会“盲中”成功；它存在的目的正是
    暴露 MAP-08 在单 seed 下的 1/3 构造旁路，而不是当作能力证据。
    """

    name = "no_hypothesis"

    def reset(self) -> None:
        return None

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        if int(observation.get("sealant_count") or 0) <= 0:
            return {"tool": "wait", "turns": 1}
        if str(observation.get("location") or "") == "A":
            return {"tool": "move", "edge_id": "A_B"}
        return {"tool": "interact", "target_id": "B", "operation": "repair_leak"}


class Map09Heuristic:
    """先封舱，再恢复发电与供氧，最后在 C 发报。

    首动作封舱让 E 停在 3；任何单个 1 tick 动作后再封舱也能活（E=4），
    但第二个未封舱的 tick 必然短路。策略选“立即封舱”以保留 P 的水与
    更低的 E 水位。
    """

    name = "public_heuristic"
    #: 消融子类把该开关关掉，用来验证“抽水是否真是成功必要条件”。
    PUMP = True

    def reset(self) -> None:
        return None

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        location = str(observation.get("location") or "")
        if observation.get("bulkhead_state") == "open":
            if location == "E":
                return {
                    "tool": "interact",
                    "target_id": "bulkhead_E_P",
                    "operation": "isolate_compartment",
                    "arguments": {"mode": "preserve"},
                }
            return self._move_towards(location, "E")
        if not observation.get("generator_online"):
            if location == "E":
                return {
                    "tool": "interact",
                    "target_id": "power_line",
                    "operation": "restore_power_line",
                }
            return self._move_towards(location, "E")
        if (
            self.PUMP
            and not observation.get("p_sacrificed")
            and int(observation.get("water_P") or 0) > 1
        ):
            if location == "P":
                return {
                    "tool": "interact",
                    "target_id": "pump",
                    "operation": "pump_once",
                }
            return self._move_towards(location, "P")
        if not observation.get("oxygen_support_on"):
            if location == "O":
                return {
                    "tool": "interact",
                    "target_id": "oxygen_system",
                    "operation": "restart_oxygen",
                }
            return self._move_towards(location, "O")
        if (
            int(observation.get("oxygen_reserve") or 0) < 12
            and location == "O"
        ):
            return {
                "tool": "interact",
                "target_id": "oxygen_system",
                "operation": "replenish_oxygen",
            }
        if location == "C":
            return {
                "tool": "interact",
                "target_id": "radio",
                "operation": "send_distress_packet",
            }
        return self._move_towards(location, "C")

    # -------------------------------------------------------------- navigation
    def _move_towards(self, location: str, target: str) -> dict[str, Any]:
        graph = self._graph()
        if location == target:
            return _wait()
        edge = _bfs_first_edge(graph, location, target)
        if edge is None:
            return _wait()
        return {"tool": "move", "edge_id": edge}

    def _graph(self) -> dict[str, dict[str, str]]:
        # 按边名的主干部分（E_P/E_C_EMERGENCY/C_E/O_C/P_O）展开邻接，这是
        # 公开命名约定，不读取 judge_state；本字典不含水位、阈值或故障真值。
        return {
            "E": {"E_P": "P", "E_C_EMERGENCY": "C", "C_E": "C"},
            "P": {"E_P": "E", "P_O": "O"},
            "O": {"P_O": "P", "O_C": "C"},
            "C": {"O_C": "O", "C_E": "E", "E_C_EMERGENCY": "E"},
        }


def _bfs_first_edge(
    graph: dict[str, dict[str, str]], start: str, target: str
) -> str | None:
    if start == target:
        return None
    queue: list[tuple[str, str | None]] = [(start, None)]
    seen = {start}
    while queue:
        node, first_edge = queue.pop(0)
        for edge_id, other in sorted(graph.get(node, {}).items()):
            if other in seen:
                continue
            seen.add(other)
            edge = first_edge or edge_id
            if other == target:
                return edge
            queue.append((other, edge))
    return None


HEURISTICS: dict[str, type[Any]] = {
    "MAP-07": Map07Heuristic,
    "MAP-08": Map08Heuristic,
    "MAP-09": Map09Heuristic,
}


class Map09SkipPump(Map09Heuristic):
    """消融：封舱后完全跳过抽水，直接恢复发电/供氧/发报。

    若该消融同样成功，说明“泵耗电与发报电量刚好相等”这一核心资源张力
    不是通关必要条件；它只影响水_P 与 repair_actions，不影响终局。
    """

    name = "skip_pump"
    PUMP = False


ABLATIONS: dict[str, dict[str, type[Any]]] = {
    "MAP-08": {"no_hypothesis": Map08NoHypothesis},
    "MAP-09": {"skip_pump": Map09SkipPump},
}

__all__ = [
    "ABLATIONS",
    "HEURISTICS",
    "Map07Heuristic",
    "Map08Heuristic",
    "Map08NoHypothesis",
    "Map09Heuristic",
    "Map09SkipPump",
]
