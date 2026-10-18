"""MAP-03 V10 基线：Oracle（知道真值）、公开启发式与三类消融。

公开策略只读 Observation 与最近 5 条 history（``run_policy`` 截断），因此航线码只能
经 ``write_memory`` 写入的 ``agent_notes`` 跨越长间隔保留。
"""

from __future__ import annotations

import random
import re
from collections import deque
from typing import Any

from agent_arena.v10.runtime.map03 import EDGES, VARIANTS

Action = dict[str, Any]
CODE = re.compile(r"^[A-Z][0-9]$")
_TAG = re.compile(r"TAG:([A-Z][0-9])")


def _path(start: str, goal: str) -> list[str]:
    """返回 start→goal 的边 id 序列（公开拓扑）。"""

    if start == goal:
        return []
    frontier: deque[tuple[str, list[str]]] = deque([(start, [])])
    seen = {start}
    while frontier:
        node, path = frontier.popleft()
        for edge_id, (a, b) in sorted(EDGES.items()):
            if node not in (a, b):
                continue
            other = b if node == a else a
            if other in seen:
                continue
            if other == goal:
                return [*path, edge_id]
            seen.add(other)
            frontier.append((other, [*path, edge_id]))
    raise ValueError(f"不可达：{start}->{goal}")


def oracle_actions(environment_seed: int) -> list[Action]:
    """真值感知 Oracle：最短合法路线 + 读码后写入记忆。"""

    start, lab, code, _, _ = VARIANTS[environment_seed]
    actions: list[Action] = []

    def go(origin: str, goal: str) -> None:
        actions.extend({"tool": "move", "edge_id": edge} for edge in _path(origin, goal))

    go(start, "D1")
    actions.append({"tool": "interact", "target": "aux_panel", "choice": "restore_power"})
    go("D1", lab)
    actions.append({"tool": "interact", "target": "sample_manifest", "choice": "read_tag"})
    actions.append({"tool": "write_memory", "facts": [{"key": "route_code", "value": code}]})
    actions.append({"tool": "interact", "target": "cryo_case", "choice": "stabilize_sample"})
    go(lab, "D3")
    actions.append({"tool": "move", "edge_id": "D3_V"})
    actions.append({"tool": "interact", "target": "antenna", "choice": "repair"})
    actions.append({"tool": "move", "edge_id": "D3_V"})
    go("D3", "U3")
    actions.append({"tool": "interact", "target": "telemetry", "choice": "transmit"})
    go("U3", "U2")
    actions.append({"tool": "submit", "target": "route_console", "answer": code})
    return actions


class Map03Heuristic:
    """公开启发式：按 P1→P5 推进；读码后立即 write_memory，再冷藏；提交 agent_notes 中的码。"""

    name = "public_heuristic"
    write_notes = True
    reread_after_sealing = False

    def reset(self) -> None:
        self.reread_done = False

    def _location(self, observation: dict[str, Any], name: str) -> str:
        return str(observation["object_locations"][name])

    def _go(self, observation: dict[str, Any], goal: str) -> Action:
        path = _path(str(observation["location"]), goal)
        return {"tool": "move", "edge_id": path[0]} if path else {"tool": "wait", "turns": 1}

    def recall(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> str | None:
        for note in observation.get("agent_notes") or []:
            value = str(note.get("value", ""))
            if CODE.match(value):
                return value
        for item in reversed(history):
            match = _TAG.search(str(item.get("result", "")))
            if match:
                return match.group(1)
        return None

    def answer(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> str:
        return self.recall(observation, history) or "A0"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        location = str(observation["location"])
        lab = self._location(observation, "sample_manifest")
        milestones = observation.get("milestones") or {}
        value = observation.get("route_tag_value")
        if isinstance(value, str) and self.write_notes:
            return {"tool": "write_memory", "facts": [{"key": "route_code", "value": value}]}
        if observation.get("route_tag_read") and not observation.get("sample_cold"):
            if location != lab:
                return self._go(observation, lab)
            return {"tool": "interact", "target": "cryo_case", "choice": "stabilize_sample"}
        if not observation.get("aux_power"):
            if location != "D1":
                return self._go(observation, "D1")
            return {"tool": "interact", "target": "aux_panel", "choice": "restore_power"}
        if not observation.get("route_tag_read"):
            if location != lab:
                return self._go(observation, lab)
            return {"tool": "interact", "target": "sample_manifest", "choice": "read_tag"}
        if not milestones.get("P3"):
            if location != "V":
                return self._go(observation, "V")
            return {"tool": "interact", "target": "antenna", "choice": "repair"}
        if location == "V":
            return {"tool": "move", "edge_id": "D3_V"}
        if not milestones.get("P4"):
            if location != "U3":
                return self._go(observation, "U3")
            return {"tool": "interact", "target": "telemetry", "choice": "transmit"}
        if self.reread_after_sealing and not self.reread_done:
            if location != lab:
                return self._go(observation, lab)
            self.reread_done = True
            return {"tool": "interact", "target": "sample_manifest", "choice": "read_tag"}
        if location != "U2":
            return self._go(observation, "U2")
        return {
            "tool": "submit",
            "target": "route_console",
            "answer": self.answer(observation, history),
        }


class Map03NoMemory(Map03Heuristic):
    """消融 no_memory：同一路线，但从不 write_memory；提交时只能用最近 5 条 history，
    取不到就提交最近可见的同格式码（遥测回执码，干扰项）。"""

    name = "no_memory"
    write_notes = False

    def answer(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> str:
        recalled = self.recall(observation, history)
        if recalled:
            return recalled
        for key in ("telemetry_ack_code", "antenna_panel_code"):
            value = observation.get(key)
            if isinstance(value, str):
                return value
        return "A0"


class Map03LateRead(Map03NoMemory):
    """消融 late_read：读码时不做笔记，提交前回实验室重读清单（应被 MANIFEST_SEALED 拒绝）。"""

    name = "late_read"
    reread_after_sealing = True


class Map03RandomGuess(Map03NoMemory):
    """消融 random_guess：不记忆，提交一个格式正确的随机码（policy_seed 决定）。"""

    name = "random_guess"

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def answer(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> str:
        del observation, history
        rng = random.Random(f"map03-guess|{self.seed}")
        return rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + str(rng.randint(0, 9))


HEURISTIC = Map03Heuristic
ABLATIONS: dict[str, type[Map03Heuristic]] = {
    "no_memory": Map03NoMemory,
    "late_read": Map03LateRead,
    "random_guess": Map03RandomGuess,
}

__all__ = ["ABLATIONS", "HEURISTIC", "Map03Heuristic", "oracle_actions"]
