"""MAP-13 V10 基线：真值 Oracle、公开暴力枚举启发式与四类消融。

公开启发式只读 `symbols`、`observed_clues`（含文本）、`recorded_clue_ids` 与公开规则：
从碑文文本里解析出四个符号角色，对 24 种排列暴力筛选，记录全部 5 条后试排并验证。
"""

from __future__ import annotations

import re
from typing import Any

from agent_arena.v10.runtime.map13 import SLOTS, oracle_actions

Action = dict[str, Any]
ROOM_CLUES = (
    ("N", "N_SUN_NOT_END"),
    ("E", "E_EYE_RIGHT_OF_REED"),
    ("S", "S_ARMOR_ADJACENT_TO_SUN"),
    ("W", "W_REED_NOT_FIRST"),
)
_TEXT_SUN = re.compile(r"^(\S)神不得居于两端")
_TEXT_EYE = re.compile(r"^(\S)神位于(\S)神右侧")
_TEXT_ARMOR = re.compile(r"^(\S)神须与(\S)神相邻")
_TEXT_REED = re.compile(r"^(\S)神不得居于首槽")


def _parse_roles(texts: dict[str, str]) -> dict[str, str] | None:
    roles: dict[str, str] = {}
    for _clue_id, text in texts.items():
        if match := _TEXT_SUN.match(text):
            roles["sun"] = match.group(1)
        elif match := _TEXT_EYE.match(text):
            roles["eye"], roles["reed"] = match.group(1), match.group(2)
        elif match := _TEXT_ARMOR.match(text):
            roles["armor"], roles["sun"] = match.group(1), match.group(2)
        elif match := _TEXT_REED.match(text):
            roles["reed"] = match.group(1)
    if set(roles) != {"sun", "eye", "reed", "armor"}:
        return None
    return roles


def _solve(symbols: list[str], roles: dict[str, str]) -> dict[str, str] | None:
    from itertools import permutations

    for order in permutations(symbols):
        layout = dict(zip(SLOTS, order, strict=True))
        position = {slot: index + 1 for index, slot in enumerate(SLOTS)}
        by_symbol = {symbol: position[slot] for slot, symbol in layout.items()}
        sun = by_symbol[roles["sun"]]
        eye = by_symbol[roles["eye"]]
        reed = by_symbol[roles["reed"]]
        armor = by_symbol[roles["armor"]]
        if sun in (1, 4):
            continue
        if eye <= reed:
            continue
        if abs(armor - sun) != 1:
            continue
        if reed == 1:
            continue
        return layout
    return None


class Map13BruteForce:
    """公开启发式：读全五条 → 逐条记录 → 暴力枚举 → 试排验证。"""

    name = "public_heuristic"

    def __init__(self, *, use_nail: bool = True) -> None:
        self.use_nail = use_nail

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.stage = "read_C"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        observed = {item["clue_id"] for item in observation["observed_clues"]}
        recorded = set(observation["recorded_clue_ids"])
        texts = {item["clue_id"]: item["text"] for item in observation["observed_clues"]}

        if self.use_nail and "ORIENTATION_ORDER" not in observed:
            if location != "C":
                self.queue = [{"tool": "move", "edge_id": f"C_{location}"}]
                return self.queue.pop(0)
            return {"tool": "read_inscription", "room": "C"}
        for slot, clue_id in ROOM_CLUES:
            if clue_id in observed:
                continue
            if location != slot:
                if location == "C":
                    self.queue = [{"tool": "move", "edge_id": f"C_{slot}"}]
                else:
                    self.queue = [
                        {"tool": "move", "edge_id": f"C_{location}"},
                        {"tool": "move", "edge_id": f"C_{slot}"},
                    ]
                return self.queue.pop(0)
            return {"tool": "read_inscription", "room": slot}
        targets = ["ORIENTATION_ORDER"] if self.use_nail else []
        targets += [clue_id for _, clue_id in ROOM_CLUES]
        for clue_id in targets:
            if clue_id in recorded:
                continue
            if location != "C":
                self.queue = [{"tool": "move", "edge_id": f"C_{location}"}]
                return self.queue.pop(0)
            return {"tool": "record_constraint", "clue_id": clue_id}
        roles = _parse_roles(texts)
        if roles is None:
            return {"tool": "read_inscription", "room": "C"}
        layout = _solve([str(symbol) for symbol in observation["symbols"]], roles)
        if layout is None:
            return {"tool": "read_inscription", "room": "C"}
        if observation["trial_layout"] is None:
            return {"tool": "set_trial_layout", "layout_by_room": layout}
        if not observation["gate_open"]:
            return {"tool": "verify_layout"}
        return {"tool": "read_inscription", "room": "C"}


class Map13NoRecord(Map13BruteForce):
    """只读不记（V9 的旁路：记录不参与判定）。"""

    name = "no_record"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = super().act(observation, history)
        if payload["tool"] == "record_constraint":
            return {"tool": "move", "edge_id": "C_N"}
        return payload


class Map13NoNail(Map13BruteForce):
    """不读方向钉（OPTIONAL 机制，质量上限 4/5）。"""

    name = "no_direction_nail"

    def __init__(self) -> None:
        super().__init__(use_nail=False)


class Map13BlindGuess(Map13BruteForce):
    """三条盲猜排列（不读碑文）。"""

    name = "blind_guess"

    def reset(self) -> None:
        super().reset()
        self.guesses = [
            {"N": "日", "E": "眼", "S": "芦", "W": "甲"},
            {"N": "甲", "E": "芦", "S": "日", "W": "眼"},
            {"N": "眼", "E": "甲", "S": "日", "W": "芦"},
        ]
        self.index = 0

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if observation["gate_open"]:
            return {"tool": "verify_layout"}
        if self.index >= len(self.guesses):
            return {"tool": "verify_layout"}
        if observation["trial_layout"] is None:
            layout = dict(self.guesses[self.index])
            layout = {
                slot: (
                    layout[slot]
                    if layout[slot] in observation["symbols"]
                    else observation["symbols"][index % 4]
                )
                for index, slot in enumerate(SLOTS)
            }
            self.index += 1
            return {"tool": "set_trial_layout", "layout_by_room": layout}
        return {"tool": "verify_layout"}


class Map13OnlyNail(Map13BruteForce):
    """只记录方向钉（不足以验证）。"""

    name = "record_only_nail"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = super().act(observation, history)
        recorded = list(observation["recorded_clue_ids"])
        if payload["tool"] == "record_constraint" and payload["clue_id"] != "ORIENTATION_ORDER":
            if len(recorded) >= 1:
                return {
                    "tool": "set_trial_layout",
                    "layout_by_room": dict(observation["trial_layout"] or {}),
                }
        return payload


HEURISTIC = Map13BruteForce
ABLATIONS: dict[str, type[Any]] = {
    "no_record": Map13NoRecord,
    "no_direction_nail": Map13NoNail,
    "blind_guess": Map13BlindGuess,
    "record_only_nail": Map13OnlyNail,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map13BlindGuess",
    "Map13BruteForce",
    "Map13NoNail",
    "Map13NoRecord",
    "Map13OnlyNail",
    "oracle_actions",
]
