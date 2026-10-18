"""MAP-23 V10 基线：真值 Oracle、公开线索分诊启发式与四类消融。

公开启发式只读 `clues_received`（含 supports）、`scout_cost`、`neighbors` 与公开的
“先买线索再出手”规则：按性价比依次侦察 N/R/H 直到候选唯一，再 mark 并前往调查。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map23 import ENTRANCES, oracle_actions

Action = dict[str, Any]
SCOUT_ORDER = ("N", "R", "H")


def _candidates(observation: dict[str, Any]) -> set[str]:
    allowed = set(ENTRANCES)
    for clue in observation["clues_received"]:
        allowed &= set(clue["supports"])
    return allowed


def _moves(location: str, destination: str) -> list[Action]:
    if location == destination:
        return []
    if location == "A":
        return [{"tool": "move", "to": destination}]
    if destination == "A":
        return [{"tool": "move", "to": "A"}]
    return [{"tool": "move", "to": "A"}, {"tool": "move", "to": destination}]


class Map23ScoutThenAct:
    """公开启发式：按性价比侦察直到候选唯一，再 mark 与调查。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        scouted = {clue["station"] for clue in observation["clues_received"]}
        candidates = _candidates(observation)
        if len(candidates) > 1:
            station = next((name for name in SCOUT_ORDER if name not in scouted), None)
            if station is not None:
                self.queue = [
                    *_moves(location, station),
                    {"tool": "scout"},
                    {"tool": "move", "to": "A"},
                ]
                return self.queue.pop(0)
        target = sorted(candidates)[0]
        self.queue = [
            {"tool": "mark", "choice": target},
            *_moves(location, target),
            {"tool": "investigate", "entrance": target},
        ]
        return self.queue.pop(0)


class Map23NoScout:
    """完全不侦察，直接调查（被接口规则拒绝）。"""

    name = "no_scout"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        target = ENTRANCES[0]
        self.queue = [
            {"tool": "mark", "choice": target},
            *_moves(location, target),
            {"tool": "investigate", "entrance": target},
        ]
        return self.queue.pop(0)


class Map23SingleClue:
    """只侦察一次（最便宜的 N），候选二义时任选一个。"""

    name = "single_clue"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        if not observation["clues_received"]:
            self.queue = [*_moves(location, "N"), {"tool": "scout"}, {"tool": "move", "to": "A"}]
            return self.queue.pop(0)
        target = sorted(_candidates(observation))[0]
        self.queue = [
            {"tool": "mark", "choice": target},
            *_moves(location, target),
            {"tool": "investigate", "entrance": target},
        ]
        return self.queue.pop(0)


class Map23IgnoreClue:
    """侦察后仍去被线索排除的入口（无视反证）。"""

    name = "ignore_counterevidence"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        if not observation["clues_received"]:
            self.queue = [
                *_moves(location, "N"),
                {"tool": "scout"},
                {"tool": "move", "to": "A"},
            ]
            return self.queue.pop(0)
        excluded = [entry for entry in ENTRANCES if entry not in _candidates(observation)]
        target = excluded[0] if excluded else ENTRANCES[0]
        self.queue = [
            {"tool": "mark", "choice": target},
            *_moves(location, target),
            {"tool": "investigate", "entrance": target},
        ]
        return self.queue.pop(0)


class Map23ScoutEverything:
    """把所有侦察站都买下来再出手（信息最全但花光补给）。"""

    name = "scout_everything"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        scouted = {clue["station"] for clue in observation["clues_received"]}
        station = next((name for name in SCOUT_ORDER if name not in scouted), None)
        if station is not None:
            self.queue = [
                *_moves(location, station),
                {"tool": "scout"},
                {"tool": "move", "to": "A"},
            ]
            return self.queue.pop(0)
        target = sorted(_candidates(observation))[0]
        self.queue = [
            {"tool": "mark", "choice": target},
            *_moves(location, target),
            {"tool": "investigate", "entrance": target},
        ]
        return self.queue.pop(0)


HEURISTIC = Map23ScoutThenAct
ABLATIONS: dict[str, type[Any]] = {
    "no_scout": Map23NoScout,
    "single_clue": Map23SingleClue,
    "ignore_counterevidence": Map23IgnoreClue,
    "scout_everything": Map23ScoutEverything,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map23IgnoreClue",
    "Map23NoScout",
    "Map23ScoutEverything",
    "Map23ScoutThenAct",
    "Map23SingleClue",
    "oracle_actions",
]
