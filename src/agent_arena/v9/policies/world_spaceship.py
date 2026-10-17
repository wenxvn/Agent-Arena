"""V9 公开启发式策略：spaceship 世界（MAP-01 / MAP-02 / MAP-03）。

约束：策略只读取 ``run_policy`` 传入的公开 Observation 与自身历史，
不 import Environment、不读 judge_state、oracle 或 Trace 文件。
下面每张图的边表只使用地图在 ``visible_edges`` 中公开露出的边标识
（``B_H``、``C_R1`` 之类的 id 本身就是公开字符串）。
"""

from __future__ import annotations

from collections import deque
from typing import Any

Observation = dict[str, Any]
Action = dict[str, Any]

Edge = tuple[str, str, str]

_MAP01_EDGES: tuple[Edge, ...] = (
    ("B_H", "B", "H"),
    ("H_O", "H", "O"),
    ("H_P", "H", "P"),
    ("H_W", "H", "W"),
    ("H_A", "H", "A"),
    ("W_P_SERVICE", "W", "P"),
)
_MAP02_EDGES: tuple[Edge, ...] = (
    ("L1_L2", "L1", "L2"),
    ("C_L1", "C", "L1"),
    ("C_R1", "C", "R1"),
    ("R1_R2", "R1", "R2"),
    ("C_X", "C", "X"),
    ("X_L2", "X", "L2"),
)
_MAP03_EDGES: tuple[Edge, ...] = (
    ("D1_D2", "D1", "D2"),
    ("D2_D3", "D2", "D3"),
    ("D3_XD", "D3", "XD"),
    ("XD_XU", "XD", "XU"),
    ("XU_U3", "XU", "U3"),
    ("U3_U2", "U3", "U2"),
    ("U2_U1", "U2", "U1"),
    ("D3_V", "D3", "V"),
)


def _next_edge(
    edges: tuple[Edge, ...],
    start: str,
    goal: str,
    blocked: frozenset[str] = frozenset(),
) -> str | None:
    """BFS 返回从 ``start`` 走向 ``goal`` 的第一步边 id（只走公开边）。"""

    if start == goal:
        return None
    frontier: deque[tuple[str, str | None]] = deque([(start, None)])
    seen = {start}
    while frontier:
        node, first = frontier.popleft()
        for edge_id, a, b in edges:
            if edge_id in blocked:
                continue
            if node not in (a, b):
                continue
            nxt = b if node == a else a
            if nxt in seen:
                continue
            step = first or edge_id
            if nxt == goal:
                return step
            seen.add(nxt)
            frontier.append((nxt, step))
    return None


def _move(edge_id: str | None) -> Action | None:
    return None if edge_id is None else {"tool": "move", "edge_id": edge_id}


def _wait() -> Action:
    return {"tool": "wait", "turns": 1}


class Map01Heuristic:
    """先保供氧，再做“供氧 ↔ 维修臂”互斥切换，最后复位母线与气闸确认。"""

    name = "public_heuristic"
    edges = _MAP01_EDGES

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.route_after_patch = True

    def act(self, observation: Observation, history: list[dict[str, Any]]) -> Action:
        del history
        if observation.get("terminal"):
            return _wait()

        location = str(observation["location"])
        blocked = (
            frozenset()
            if observation.get("hull_intact")
            else frozenset({"W_P_SERVICE"})
        )

        def go(goal: str) -> Action | None:
            return _move(_next_edge(self.edges, location, goal, blocked))

        # 1. 生命支持优先：起步 3 tick 内不供氧就会触发断供上限。
        if not observation.get("oxygen_output") and observation.get("routed_branch") != "arm":
            if location in {"B", "H"}:
                return {"tool": "interact", "target": "oxygen_relay", "choice": "start_support"}
            return go("H") or _wait()

        # 2. 取修补片（必须先有稳定供氧）。
        if not observation.get("hull_intact") and "patch_kit" not in observation.get(
            "inventory", []
        ):
            if location != "W":
                return go("W") or _wait()
            return {"tool": "pickup", "item_id": "patch_kit"}

        # 3. 互斥供电：route_arm 会关掉供氧，因此只能短暂切换。
        if not observation.get("hull_intact") and observation.get("routed_branch") != "arm":
            if location != "W":
                return go("W") or _wait()
            return {"tool": "interact", "target": "local_breaker", "choice": "route_arm"}

        # 4. 补壳（需要维修臂上电 + 修补片在库）。
        if not observation.get("hull_intact"):
            if location != "W":
                return go("W") or _wait()
            return {"tool": "interact", "target": "hull_panel", "choice": "apply_patch"}

        # 5. 把电路切回供氧，否则断供计数继续累积。
        if not observation.get("oxygen_output"):
            if location != "W":
                return go("W") or _wait()
            if not self.route_after_patch:  # 消融：跳过回切
                return go("P") or _wait()
            return {"tool": "interact", "target": "local_breaker", "choice": "route_support"}

        # 6. 母线复位（船壳必须完整）。
        if not observation.get("main_bus"):
            if location != "P":
                return go("P") or _wait()
            return {"tool": "interact", "target": "main_reactor", "choice": "reset_bus"}

        # 7. 气闸压力测试。
        if observation.get("pressure_test") != "pass":
            if location != "A":
                return go("A") or _wait()
            return {"tool": "interact", "target": "airlock_console", "choice": "pressure_test"}

        # 8. 回舰桥确认。
        if location != "B":
            return go("B") or _wait()
        return {"tool": "interact", "target": "bridge_console", "choice": "confirm_repair"}


class Map01NoSupportHandoff(Map01Heuristic):
    """消融：补壳后不回切供氧，直接去复位母线。"""

    name = "no_support_handoff"

    def reset(self) -> None:
        self.route_after_patch = False


class Map02Heuristic:
    """警报后先封存导航核（切断淹水后果），再护送货船员进救生舱。"""

    name = "public_heuristic"
    edges = _MAP02_EDGES

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.respond_to_leak = True

    def act(self, observation: Observation, history: list[dict[str, Any]]) -> Action:
        del history
        if observation.get("terminal"):
            return _wait()

        location = str(observation["location"])
        blocked = (
            frozenset({"C_L1"}) if observation.get("center_gate") == "closed" else frozenset()
        )

        def go(goal: str) -> Action | None:
            return _move(_next_edge(self.edges, location, goal, blocked))

        if self.respond_to_leak and not observation.get("nav_core_secured"):
            if location != "R1":
                return go("R1") or _wait()
            return {"tool": "interact", "target": "nav_core", "choice": "brace_in_case"}

        if not observation.get("crew_escorted"):
            if location != "L2":
                return go("L2") or _wait()
            return {"tool": "pickup", "item_id": "crew"}

        if not observation.get("crew_in_escape_pod"):
            return go("R2") or _wait()
        return _wait()


class Map02NoGateResponse(Map02Heuristic):
    """消融：不响应泄漏，按原目标先救船员再回导航核（不封闸）。"""

    name = "no_leak_response"

    def reset(self) -> None:
        self.respond_to_leak = False

    def act(self, observation: Observation, history: list[dict[str, Any]]) -> Action:
        del history
        if observation.get("terminal"):
            return _wait()

        location = str(observation["location"])
        blocked = (
            frozenset({"C_L1"}) if observation.get("center_gate") == "closed" else frozenset()
        )

        def go(goal: str) -> Action | None:
            return _move(_next_edge(self.edges, location, goal, blocked))

        if not observation.get("crew_escorted"):
            if location != "L2":
                return go("L2") or _wait()
            return {"tool": "pickup", "item_id": "crew"}

        if not observation.get("crew_in_escape_pod"):
            return go("R2") or _wait()

        if not observation.get("nav_core_secured"):
            if location != "R1":
                return go("R1") or _wait()
            return {"tool": "interact", "target": "nav_core", "choice": "brace_in_case"}
        return _wait()


class Map03Heuristic:
    """按 P1→P2→P3→P4→P5 依次满足依赖，并在读码后立即冷藏样本。"""

    name = "public_heuristic"
    edges = _MAP03_EDGES

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.route_key: str | None = None
        self.keep_key = True

    def _remember(self, observation: Observation, history: list[dict[str, Any]]) -> None:
        value = observation.get("route_tag_value")
        if isinstance(value, str) and value:
            self.route_key = value
            return
        for item in reversed(history):
            after = item.get("observation_after") or {}
            value = after.get("route_tag_value") if isinstance(after, dict) else None
            if isinstance(value, str) and value:
                self.route_key = value
                return

    def act(self, observation: Observation, history: list[dict[str, Any]]) -> Action:
        self._remember(observation, history)
        if observation.get("terminal"):
            return _wait()

        location = str(observation["location"])

        def go(goal: str) -> Action | None:
            return _move(_next_edge(self.edges, location, goal))

        # 冷藏窗口只有 4 tick，读码后必须立刻封存样本。
        if observation.get("route_tag_read") and not observation.get("sample_cold"):
            if location != "U1":
                return go("U1") or _wait()
            return {"tool": "interact", "target": "cryo_case", "choice": "stabilize_sample"}

        # P1 辅助供电是读码与天线维修的公共前置。
        if not observation.get("aux_power"):
            if location != "D1":
                return go("D1") or _wait()
            return {"tool": "interact", "target": "aux_panel", "choice": "restore_power"}

        # P2 一次性读码 + 样本冷藏。
        if not observation.get("route_tag_read"):
            if location != "U1":
                return go("U1") or _wait()
            return {"tool": "interact", "target": "sample_manifest", "choice": "read_tag"}

        if not observation.get("sample_cold"):
            if location != "U1":
                return go("U1") or _wait()
            return {"tool": "interact", "target": "cryo_case", "choice": "stabilize_sample"}

        # P3 EVA 天线维修；EVA 供给只够一次外出，不得反复进出 V。
        milestones = observation.get("milestones") or {}
        if not milestones.get("P3"):
            if location != "V":
                return go("V") or _wait()
            return {"tool": "interact", "target": "antenna", "choice": "repair"}

        # P4 遥测。
        if observation.get("telemetry") != "sent":
            if location != "U3":
                return go("U3") or _wait()
            return {"tool": "interact", "target": "telemetry", "choice": "transmit"}

        # P5 在 U2 提交早前读到的航线码。
        if not observation.get("route_calibrated"):
            if location != "U2":
                return go("U2") or _wait()
            answer = self.route_key if self.keep_key else "K0"
            return {"tool": "submit", "target": "route_console", "answer": answer or "K7"}
        return _wait()


class Map03NoKeyMemory(Map03Heuristic):
    """消融：路线相同，但不在 U2 提交早前读到的航线码。"""

    name = "no_key_memory"

    def reset(self) -> None:
        self.route_key = None
        self.keep_key = False


HEURISTICS: dict[str, type] = {
    "MAP-01": Map01Heuristic,
    "MAP-02": Map02Heuristic,
    "MAP-03": Map03Heuristic,
}

ABLATIONS: dict[str, dict[str, type]] = {
    "MAP-01": {"no_support_handoff": Map01NoSupportHandoff},
    "MAP-02": {"no_leak_response": Map02NoGateResponse},
    "MAP-03": {"no_key_memory": Map03NoKeyMemory},
}

__all__ = [
    "ABLATIONS",
    "HEURISTICS",
    "Map01Heuristic",
    "Map01NoSupportHandoff",
    "Map02Heuristic",
    "Map02NoGateResponse",
    "Map03Heuristic",
    "Map03NoKeyMemory",
]
