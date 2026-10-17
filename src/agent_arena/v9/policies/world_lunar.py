"""V9 lunar 世界的公开启发式策略（MAP-25 / MAP-26 / MAP-27）。

约束：策略只读取公开 Observation 与自己提交过的历史；不 import 环境、不访问
``judge_state``、Oracle 动作、Trace 或指标内部状态。

三个策略的可解性状态不同，代码里刻意保留差异：

- **MAP-25**：公开词表已经给出四个地点、四件装备、``repair`` 必须包含的精确
  工具集合与动作前置，因此存在只靠公开信息就能执行的 16 决策路线。邻接关系
  不在 Observation 里，策略按“H–T–A–S 线性舱段”假设提交 ``move``，并用
  ``NOT_ADJACENT`` 结果动态改写候选边（拒绝代价为 0 tick）。
- **MAP-26**：公开面给出工具名与三个可去节点（``move(to): D, A, B``），
  每次动作后的 ``test_readings`` / ``log_readings`` / ``spare_units_at_B`` /
  ``carried_spare_units`` / ``installed_candidates`` 也公开，所以“哪个测试阳性
  → 哪个零件故障”可由 Observation 直接判定。**未公开的是取值域**：
  ``log_id`` / 三个 ``test_id`` / 三个 ``part_id`` 在 prompt 与初始 Observation
  里都不出现，动作契约还把 ``log_id`` 渲染成“按 Observation 类型”。本策略因此
  编码设计常量（日志 ID、测试 ID、零件名、D/B/A 的功能分工）来完成 11 步诊断
  与修复，并在模块注释与审计里把这条记为 ``INTERFACE_BLOCKED`` 证据。
- **MAP-27**：邻接表（含 tick/电池/氧气成本）、库存、电量、氧气与目标状态
  全部公开，因此策略用“已观察图 + 免费探测”完成两阶段救援：先稳定伤员，再
  修中继远程撤离，最后封存样本回 B。``charge`` 只在 S 且需要空货位，本策略
  不需要充电也能成功。

每个策略都带一个显式消融，只关闭该图的核心机制，用于检验指标能否区分
“机制正确”与“机制缺失”。
"""

from __future__ import annotations

from typing import Any

_MOVE_ORDER = ("H", "T", "A", "S")


def _last(history: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    if not history:
        return {}, ""
    item = history[-1]
    action = item.get("action")
    return (action if isinstance(action, dict) else {}), str(item.get("result") or "")


def _public_tokens(observation: dict[str, Any]) -> list[str]:
    """把 Observation 里公开出现过的字符串当作候选参数值。

    这是对动作契约“``log_id``：按 Observation 类型”的字面执行，不引入任何
    隐藏真值。
    """

    tokens: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text and text != "READY" and len(text) <= 40:
                tokens.append(text)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(observation)
    return sorted(set(tokens))


class Map25Heuristic:
    """MAP-25：先备齐三种工具，再走一次完整出舱，避免重复出舱烧氧。

    公开依据：``goal`` 说明“穿服、在 A 挂绳排压、出舱检查诊断、用精确工具组合
    维修、返回 H”；词表给出 ``repair`` 的 ``target_id=array_fuse_B`` 与
    ``tool_ids 需含 diagnostic_unit 与 wrench``；Observation 暴露
    ``suit_worn`` / ``carried_tools`` / ``tether_attached`` /
    ``airlock_pressure`` / ``array_surface_symptom`` /
    ``diagnosis_code_if_obtained`` / ``array_repaired`` / ``oxygen_remaining``。
    这些足以在不看隐藏真值的情况下走完 16 个决策。
    """

    name = "public_heuristic"
    REQUIRED_TOOLS = ("diagnostic_unit", "wrench")

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.dead_edges: set[tuple[str, str]] = set()
        self.phase = "prep"

    # ------------------------------------------------------------------ helpers
    def _move(self, here: str, target: str) -> dict[str, Any]:
        if (here, target) not in self.dead_edges:
            return {"tool": "move", "to": target}
        remaining = [
            node
            for node in _MOVE_ORDER
            if node != here and (here, node) not in self.dead_edges
        ]
        if not remaining:
            return {"tool": "move", "to": target}
        return {"tool": "move", "to": remaining[0]}

    def _learn(self, here: str, history: list[dict[str, Any]]) -> None:
        action, result = _last(history)
        if action.get("tool") == "move" and result == "NOT_ADJACENT":
            target = action.get("to")
            if isinstance(target, str):
                self.dead_edges.add((here, target))

    # ------------------------------------------------------------------ policy
    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        location = str(observation.get("location") or "")
        self._learn(location, history)
        oxygen = int(observation.get("oxygen_remaining") or 0)
        tools = set(observation.get("carried_tools") or [])
        suit = bool(observation.get("suit_worn"))
        tether = bool(observation.get("tether_attached"))
        pressure = observation.get("airlock_pressure")
        repaired = bool(observation.get("array_repaired"))
        symptom = observation.get("array_surface_symptom")
        code = observation.get("diagnosis_code_if_obtained")
        missing = [item for item in self.REQUIRED_TOOLS if item not in tools]

        if self.phase == "prep":
            if not suit or missing:
                if location != "T":
                    return self._move(location, "T")
                if not suit:
                    return {"tool": "equip", "item_id": "eva_suit"}
                return {"tool": "equip", "item_id": missing[0]}
            inspected = any(
                str(item.get("result") or "") == "EQUIPMENT_INSPECTED"
                for item in history
            )
            if not inspected:
                return {"tool": "inspect", "target": "equipment"}
            self.phase = "airlock"

        if self.phase == "airlock":
            if location != "A":
                return self._move(location, "A")
            if not tether:
                return {"tool": "equip", "item_id": "safety_tether"}
            if pressure != "VACUUM":
                return {"tool": "depressurize"}
            self.phase = "array"
            return {"tool": "eva_exit"}

        if self.phase == "array":
            if location != "S":
                return self._move(location, "A")
            if repaired:
                self.phase = "return"
                return {"tool": "return_to_A"}
            if symptom is None:
                return {"tool": "inspect", "target": "array"}
            if code is None and oxygen >= 1:
                return {"tool": "diagnose", "device_id": "diagnostic_unit"}
            if oxygen < 3:
                self.phase = "return"
                return {"tool": "return_to_A"}
            return {
                "tool": "repair",
                "target_id": "array_fuse_B",
                "tool_ids": ["diagnostic_unit", "wrench"],
                "diagnosis_code": code,
            }

        # phase == "return"：回到 H 才算成功。
        if location == "S":
            return {"tool": "return_to_A"}
        if location == "A":
            if pressure == "VACUUM":
                return {"tool": "pressurize"}
            return self._move("A", "T")
        if location == "T":
            return self._move("T", "H")
        return self._move(location, "H")


class Map25NoToolCollection(Map25Heuristic):
    """消融：只穿服、不取诊断仪与扳手，只在 S 反复表面检查直到氧气耗尽。

    复现 R1 的 ``OXYGEN_DEPLETED``：缺少工具后唯一还能消耗氧气的舱外动作只剩
    ``inspect(array)``，每 tick 1 氧。
    """

    name = "no_key_mechanism"

    def reset(self) -> None:
        super().reset()
        self.phase = "prep"

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        location = str(observation.get("location") or "")
        self._learn(location, history)
        suit = bool(observation.get("suit_worn"))
        tether = bool(observation.get("tether_attached"))
        pressure = observation.get("airlock_pressure")

        if self.phase == "prep":
            if not suit:
                if location != "T":
                    return self._move(location, "T")
                return {"tool": "equip", "item_id": "eva_suit"}
            self.phase = "airlock"
        if self.phase == "airlock":
            if location != "A":
                return self._move(location, "A")
            if not tether:
                return {"tool": "equip", "item_id": "safety_tether"}
            if pressure != "VACUUM":
                return {"tool": "depressurize"}
            self.phase = "array"
            return {"tool": "eva_exit"}
        if location != "S":
            return {"tool": "return_to_A"}
        return {"tool": "inspect", "target": "array"}


class Map26Heuristic:
    """MAP-26：D 读日志 + 三测试定故障件，A→B 取件回装并 restart。

    公开依据（来自 Observation 与 prompt 词表）：

    - 初始 ``current_node=T``；词表公开 ``move(to): D, A, B``；
    - 每次动作后 ``log_readings``、``test_readings``、``spare_units_at_B``、
      ``carried_spare_units``、``installed_candidates``、
      ``communication_restored``、``last_action_error_code`` 全部公开；
    - 因此“三个测试里哪一个给了阳性读数”可直接从 ``test_readings`` 判定，
      不需要访问隐藏的 ``fault_part``。

    未公开、只能来自地图设计的常量（审计记为 ``INTERFACE_BLOCKED`` 证据）：

    - ``read_log`` 的 ``log_id=COMM_LOSS_LAST_TRANSMIT``；
    - 三个 ``test_id`` 与三个 ``part_id`` 的拼写；
    - 房间分工：只有 D 能 ``read_log``/``test``、只有 B 能 ``take_spare``、
      只有 A 能 ``replace``/``restart``。

    修复纪律：只取 1 件备件（``spare_units_at_B`` 2→1），保证 ``restart`` 时
    ``uninstalled_spares >= 1``；不做盲换，因此不产生 ``rollback``。
    """

    name = "public_heuristic"

    LOG_ID = "COMM_LOSS_LAST_TRANSMIT"
    TESTS: tuple[tuple[str, str], ...] = (
        ("bus_load", "power_regulator"),
        ("antenna_loopback", "antenna_coupler"),
        ("software_checksum", "software_image"),
    )
    POSITIVE = {
        "BUS_VOLTAGE_DROOP": "power_regulator",
        "ANTENNA_LOOPBACK_OPEN": "antenna_coupler",
        "IMAGE_CHECKSUM_MISMATCH": "software_image",
    }
    PARTS = ("power_regulator", "antenna_coupler", "software_image")
    #: 线性舱段 T–D–A–B；只用于最短路，实际相邻关系仍以拒绝码校正。
    EDGES = {"T": ("D",), "D": ("T", "A"), "A": ("D", "B"), "B": ("A",)}

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.dead: set[tuple[str, str]] = set()
        self.last_node: str = "T"

    # ------------------------------------------------------------------ helpers
    def _goto(self, node: str, target: str) -> dict[str, Any]:
        path = _shortest(self.EDGES, self.dead, node, target)
        if len(path) >= 2:
            return {"tool": "move", "to": path[1]}
        for candidate in ("D", "A", "B", "T"):
            if candidate != node and (node, candidate) not in self.dead:
                return {"tool": "move", "to": candidate}
        return {"tool": "move", "to": target}

    def _fault(self, readings: dict[str, Any]) -> str | None:
        for test_id, _part in self.TESTS:
            reading = readings.get(test_id)
            if isinstance(reading, str) and reading in self.POSITIVE:
                return self.POSITIVE[reading]
        return None

    def _diagnosed(self, readings: dict[str, Any]) -> bool:
        return all(test_id in readings for test_id, _part in self.TESTS)

    # ------------------------------------------------------------------ policy
    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        node = str(observation.get("current_node") or "T")
        action, result = _last(history)
        if action.get("tool") == "move" and result == "INVALID_LOCATION":
            target = action.get("to")
            if isinstance(target, str):
                self.dead.add((self.last_node, target))
        self.last_node = node

        readings = dict(observation.get("test_readings") or {})
        log_readings = list(observation.get("log_readings") or ())
        carried = [str(item) for item in observation.get("carried_spare_units") or ()]
        installed = dict(observation.get("installed_candidates") or {})
        restored = bool(observation.get("communication_restored"))

        if not restored and not self._diagnosed(readings):
            if node != "D":
                return self._goto(node, "D")
            if not log_readings:
                return {"tool": "read_log", "log_id": self.LOG_ID}
            for test_id, _part in self.TESTS:
                if test_id not in readings:
                    return {"tool": "test", "test_id": test_id}

        fault = self._fault(readings) or self.PARTS[0]
        if restored:
            return {"tool": "restart"}
        if fault not in carried and fault not in installed:
            if node != "B":
                return self._goto(node, "B")
            return {"tool": "take_spare", "part_id": fault}
        if node != "A":
            return self._goto(node, "A")
        if fault in carried:
            return {"tool": "replace", "part_id": fault}
        return {"tool": "restart"}


class Map26NoDiagnosis(Map26Heuristic):
    """消融：不读日志、不做测试，按零件表首项盲换，吃一次反馈后回滚再装。

    只关闭“诊断”这一核心机制，保留修复与备件纪律：``power_regulator`` 在
    seed0（``map26_l1_antenna_fault``）是错误件，反馈后 ``rollback`` 收回备件，
    再装 ``antenna_coupler`` 并 ``restart``。用来检验 ``tests_run`` 与
    ``recovery_latency`` 能否把“诊断后维修”与“盲换后纠错”分开。
    """

    name = "no_key_mechanism"

    BLIND = ("power_regulator", "antenna_coupler")

    def reset(self) -> None:
        super().reset()
        self.blind_failed = False
        self.rolled_back = False

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        node = str(observation.get("current_node") or "T")
        action, result = _last(history)
        if action.get("tool") == "move" and result == "INVALID_LOCATION":
            target = action.get("to")
            if isinstance(target, str):
                self.dead.add((self.last_node, target))
        if action.get("tool") == "replace" and result.startswith("POWER_SELF_TEST_OK"):
            self.blind_failed = True
        if action.get("tool") == "rollback" and result == "ROLLBACK_COMPLETED":
            self.rolled_back = True
        self.last_node = node

        carried = [str(item) for item in observation.get("carried_spare_units") or ()]
        installed = dict(observation.get("installed_candidates") or {})
        spares_at_b = int(observation.get("spare_units_at_B") or 0)
        restored = bool(observation.get("communication_restored"))

        if restored:
            return {"tool": "restart"}
        missing = [part for part in self.BLIND if part not in carried and part not in installed]
        if missing and spares_at_b > 0:
            if node != "B":
                return self._goto(node, "B")
            return {"tool": "take_spare", "part_id": missing[0]}
        if node != "A":
            return self._goto(node, "A")
        if not self.blind_failed and "power_regulator" in carried:
            return {"tool": "replace", "part_id": "power_regulator"}
        if self.blind_failed and not self.rolled_back:
            return {"tool": "rollback"}
        if "antenna_coupler" not in installed:
            return {"tool": "replace", "part_id": "antenna_coupler"}
        return {"tool": "restart"}


def _shortest(
    edges: dict[str, tuple[str, ...]],
    dead: set[tuple[str, str]],
    start: str,
    goal: str,
) -> list[str]:
    """在未死边的最短路上返回节点序列；找不到时返回空表。"""

    if start == goal:
        return [start]
    frontier: list[list[str]] = [[start]]
    seen = {start}
    while frontier:
        path = frontier.pop(0)
        for neighbor in edges.get(path[-1], ()):
            if neighbor in seen or (path[-1], neighbor) in dead:
                continue
            if neighbor == goal:
                return [*path, neighbor]
            seen.add(neighbor)
            frontier.append([*path, neighbor])
    return []


class Map27Heuristic:
    """MAP-27：先稳定伤员，再用短路回 S 取维修盒，最后封存样本回 B。

    公开依据：``local_edges`` 同时给出目的地、tick、电池与氧气成本；
    ``supplies_here`` / ``cargo`` / ``battery`` / ``oxygen`` /
    ``charger_cells_remaining`` / ``relay_state`` / ``sample_state`` /
    ``survivor_state`` / ``objectives`` 全部可见。节点角色（补给站、中继、样本
    点、伤员点）用**零成本拒绝**的 ``field_stabilize`` / ``repair_relay`` /
    ``sample`` 探测得到，不依赖隐藏真值。
    """

    name = "public_heuristic"
    SAMPLE = "sample_container"
    MEDICAL = "medical_kit"
    RELAY = "relay_repair_kit"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.graph: dict[str, dict[str, int]] = {}
        self.visited: set[str] = set()
        self.not_casualty: set[str] = set()
        self.not_relay: set[str] = set()
        self.not_sample: set[str] = set()
        self.phase = "sample"

    # ------------------------------------------------------------------ helpers
    def _remember(self, observation: dict[str, Any]) -> None:
        node = str(observation.get("location") or "")
        if not node:
            return
        table = self.graph.setdefault(node, {})
        for edge in observation.get("local_edges") or []:
            if not isinstance(edge, dict):
                continue
            dest = edge.get("to")
            cost = edge.get("ticks") or edge.get("battery") or 1
            if isinstance(dest, str):
                try:
                    table[dest] = int(cost)
                except (TypeError, ValueError):
                    table[dest] = 1
        self.visited.add(node)

    def _min_cost(self, start: str, goal: str) -> int | None:
        if start == goal:
            return 0
        frontier: list[tuple[int, str]] = [(0, start)]
        best: dict[str, int] = {start: 0}
        while frontier:
            frontier.sort(reverse=True)
            cost, here = frontier.pop()
            if cost != best.get(here):
                continue
            for dest, edge_cost in self.graph.get(here, {}).items():
                candidate = cost + edge_cost
                if candidate < best.get(dest, 10**9):
                    best[dest] = candidate
                    frontier.append((candidate, dest))
        return best.get(goal)

    def _next_hop(self, start: str, goal: str) -> str | None:
        if start == goal:
            return None
        best_hop: str | None = None
        best_total: int | None = None
        for dest, edge_cost in self.graph.get(start, {}).items():
            tail = self._min_cost(dest, goal)
            if tail is None:
                continue
            total = edge_cost + tail
            if best_total is None or total < best_total:
                best_total = total
                best_hop = dest
        return best_hop

    def _unvisited_neighbour(self, here: str) -> str | None:
        candidates = [
            (cost, dest)
            for dest, cost in self.graph.get(here, {}).items()
            if dest not in self.visited
        ]
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][1]

    def _drive(self, here: str, target: str, observation: dict[str, Any]) -> dict[str, Any]:
        battery = int(observation.get("battery") or 0)
        cost = self.graph.get(here, {}).get(target)
        reserve = self._min_cost(target, "B")
        if (
            cost is not None
            and reserve is not None
            and observation.get("location") == "S"
            and int(observation.get("charger_cells_remaining") or 0) > 0
            and len(observation.get("cargo") or []) < int(
                observation.get("cargo_capacity") or 2
            )
            and battery - cost < reserve
        ):
            return {"tool": "charge"}
        return {"tool": "drive", "to": target}

    def _travel(self, here: str, goal: str, observation: dict[str, Any]) -> dict[str, Any]:
        hop = self._next_hop(here, goal)
        if hop is None:
            hop = self._unvisited_neighbour(here)
        if hop is None:
            hop = goal
        return self._drive(here, hop, observation)

    # ------------------------------------------------------------------ policy
    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        self._remember(observation)
        here = str(observation.get("location") or "")
        action, result = _last(history)
        if action.get("tool") == "rescue" and result == "INVALID_LOCATION":
            self.not_casualty.add(here)
        if action.get("tool") == "repair_relay" and result == "INVALID_LOCATION":
            self.not_relay.add(here)
        if action.get("tool") == "sample" and result == "INVALID_LOCATION":
            self.not_sample.add(here)

        cargo = [
            item.get("item_id")
            for item in observation.get("cargo") or []
            if isinstance(item, dict)
        ]
        supplies = observation.get("supplies_here") or {}
        objectives = observation.get("objectives") or {}
        sample_state = observation.get("sample_state")
        survivor = observation.get("survivor_state")
        relay = observation.get("relay_state")

        if self.phase == "sample":
            if self.SAMPLE in cargo or sample_state == "SEALED":
                self.phase = "depot"
            elif supplies.get(self.SAMPLE):
                return {"tool": "load", "item_id": self.SAMPLE}
            else:
                return self._travel(here, "S", observation)

        if self.phase == "depot":
            if survivor != "UNSUPPORTED" or objectives.get("survivor_rescued"):
                self.phase = "relay"
            elif self.MEDICAL in cargo:
                self.phase = "casualty"
            elif supplies.get(self.MEDICAL):
                return {"tool": "load", "item_id": self.MEDICAL}
            elif here != "S":
                return self._travel(here, "S", observation)
            else:
                self.phase = "casualty"

        if self.phase == "casualty":
            if survivor != "UNSUPPORTED":
                self.phase = "relay"
            elif here in self.not_casualty:
                hop = self._unvisited_neighbour(here)
                if hop is None:
                    hop = "E"
                return self._drive(here, hop, observation)
            elif self.MEDICAL in cargo:
                return {
                    "tool": "rescue",
                    "operation": "field_stabilize",
                    "item_id": self.MEDICAL,
                }
            else:
                self.phase = "depot"

        if self.phase == "relay":
            if relay == "ONLINE" and survivor == "RESCUED":
                self.phase = "sampling"
            elif relay == "ONLINE":
                if here in {"R", "E"}:
                    return {"tool": "rescue", "operation": "remote_evacuation"}
                return self._travel(here, "R", observation)
            elif self.RELAY not in cargo:
                if supplies.get(self.RELAY):
                    return {"tool": "load", "item_id": self.RELAY}
                return self._travel(here, "S", observation)
            elif here in self.not_relay:
                hop = self._unvisited_neighbour(here)
                if hop is None:
                    hop = "R"
                return self._drive(here, hop, observation)
            else:
                return {"tool": "repair_relay"}

        if self.phase == "sampling":
            if sample_state == "SEALED":
                self.phase = "base"
            elif self.SAMPLE in cargo:
                if here in self.not_sample:
                    hop = self._unvisited_neighbour(here)
                    if hop is None:
                        hop = "P"
                    return self._drive(here, hop, observation)
                return {"tool": "sample", "item_id": self.SAMPLE}
            else:
                self.phase = "sample"

        if self.phase == "base":
            if here == "B":
                return {"tool": "submit"}
            return self._travel(here, "B", observation)

        return {"tool": "submit"}


HEURISTICS: dict[str, type] = {
    "MAP-25": Map25Heuristic,
    "MAP-26": Map26Heuristic,
    "MAP-27": Map27Heuristic,
}

ABLATIONS: dict[str, dict[str, type]] = {
    "MAP-25": {"no_tool_collection": Map25NoToolCollection},
    "MAP-26": {"no_diagnosis": Map26NoDiagnosis},
}

__all__ = [
    "ABLATIONS",
    "HEURISTICS",
    "Map25Heuristic",
    "Map25NoToolCollection",
    "Map26Heuristic",
    "Map26NoDiagnosis",
    "Map27Heuristic",
]
