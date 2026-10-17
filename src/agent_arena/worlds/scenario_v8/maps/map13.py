"""MAP-13｜四神之门：显式符号约束满足与“房间图 / 碑文阅读序”分离。

本图与同世界另两图的机制差异：MAP-14 的陈述有真假与说谎者，需在锁型×诚实者
假设中找一致解；MAP-15 的规则随 tick 奇偶变化，需要归纳与迁移；本图五条信息
全部为真、规则静态，核心是把星形移动拓扑与碑文阅读序 `N→E→S→W` 分开，逐条
传播约束到唯一排列，并在最多两次错误开门内完成。失败码与状态变量与另两图不重叠。

动作契约（每个动作 1 tick；``set_trial_layout`` 不消耗开门次数）：

- ``move``：只走 `C_N / C_E / C_S / C_W`，四间外室之间没有直连。
- ``read_inscription``：只能在自己所在房间读；观察与记录是两件事。
- ``record_constraint``：只在 C，只能记录已读碑文。
- ``set_trial_layout``：只在 C，必须恰含 N/E/S/W 四槽且四符号各一次。
- ``verify_layout``：只在 C，正确开门；错误则 ``STATE_RESET``（清空试排并计错）。

指标口径（与 docs/v7/maps/MAP-13.md 一致）：

- ``map13.constraint_satisfaction_ratio``：最后一次试排满足的房间谓词数 + 方向钉
  是否已读，分母 5（4 条房间约束 + 方向钉）；无试排 → 0/5。
- ``map13.correct_sequence``：最后一次试排是否等于唯一解（0/1）。
- ``map13.illegal_door_attempts``：被拒绝的 ``verify_layout`` 次数（含未成型试排
  与错排）；0 合法。
- ``map13.state_resets``：错排触发的 ``STATE_RESET`` 次数；0 合法。
- ``map13.completion_ticks``：成功终局 tick；失败 → None。

唯一解与约束表只存在裁判侧，不进 Observation。
"""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action


class Map13Environment(MapEnvironment):
    map_id = "MAP-13"
    title = "四神之门"
    world = "pyramid"
    level = "简单"
    EDGES = {
        "C_N": ("C", "N"),
        "C_E": ("C", "E"),
        "C_S": ("C", "S"),
        "C_W": ("C", "W"),
    }
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {
            frozenset({"tool", "edge_id"}),
            frozenset({"tool", "edge_id", "from_node", "to_node"}),
        },
        "read_inscription": {frozenset({"tool", "room"})},
        "record_constraint": {frozenset({"tool", "clue_id"})},
        "set_trial_layout": {frozenset({"tool", "layout_by_room"})},
        "verify_layout": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "visible_neighbors",
            "current_tick",
            "observed_clues",
            "recorded_clue_ids",
            "trial_layout",
            "incorrect_attempts",
            "remaining_incorrect_attempts",
            "gate_open",
            "goal",
        }
    )
    ROOMS = ("C", "N", "E", "S", "W")
    ROOM_ORDER = {"C": -1, "N": 0, "E": 1, "S": 2, "W": 3}
    SLOTS = ("N", "E", "S", "W")
    READING_ORDER = ("N", "E", "S", "W")
    SYMBOLS = ("日", "眼", "芦", "甲")
    MAX_INCORRECT_ATTEMPTS = 3
    #: 裁判侧唯一解；任何公开面都不出现。
    TARGET_LAYOUT = {"N": "甲", "E": "日", "S": "芦", "W": "眼"}
    CLUES = {
        "ORIENTATION_ORDER": (
            "C",
            "从北室起，按N→E→S→W顺时针读为槽位1至4；右侧表示编号更大，相邻表示编号差1。",
        ),
        "N_SUN_NOT_END": ("N", "日神不得居于两端。"),
        "E_EYE_RIGHT_OF_REED": ("E", "眼神位于芦神右侧。"),
        "S_ARMOR_ADJACENT_TO_SUN": ("S", "甲神须与日神相邻。"),
        "W_REED_NOT_FIRST": ("W", "芦神不得居于首槽。"),
    }

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ state
    def _reset_state(self, seed: int) -> None:
        del seed
        self.node = "C"
        self.items = []
        self.observed: list[str] = []
        self.recorded: list[str] = []
        self.trial_layout: dict[str, str] | None = None
        self.last_attempted_layout: dict[str, str] | None = None
        self.incorrect_attempts = 0
        self.illegal_door_attempts = 0
        self.state_resets = 0
        self.gate_open = False

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        neighbour_of = {
            edge_id: (second if first == self.node else first)
            for edge_id, (first, second) in self.EDGES.items()
            if self.node in (first, second)
        }
        neighbours = sorted(
            neighbour_of.values(), key=lambda room: self.ROOM_ORDER.get(room, 99)
        )
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "visible_neighbors": neighbours,
            "current_tick": self.tick_count,
            "observed_clues": [
                {"clue_id": clue_id, "text": self.CLUES[clue_id][1]}
                for clue_id in self.observed
            ],
            "recorded_clue_ids": list(self.recorded),
            "trial_layout": dict(self.trial_layout) if self.trial_layout else None,
            "incorrect_attempts": self.incorrect_attempts,
            "remaining_incorrect_attempts": max(
                0, self.MAX_INCORRECT_ATTEMPTS - 1 - self.incorrect_attempts
            ),
            "gate_open": self.gate_open,
            "goal": "读取方向钉与四条碑文，把四符号各放入 N/E/S/W 并验证开门。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "move":
            return self._move(action)
        if tool == "read_inscription":
            return self._read(action)
        if tool == "record_constraint":
            return self._record(action)
        if tool == "set_trial_layout":
            return self._set_layout(action)
        if tool == "verify_layout":
            return self._verify()
        return "ACTION_NOT_ALLOWED"

    def _move(self, action: V8Action) -> str:
        edge = self.EDGES.get(action.edge_id or "")
        if edge is None:
            return "INVALID_EDGE"
        if self.node not in edge:
            return "INVALID_EDGE"
        if action.from_node is not None and action.from_node != self.node:
            return "INVALID_LOCATION"
        destination = edge[1] if edge[0] == self.node else edge[0]
        if action.to_node is not None and action.to_node != destination:
            return "INVALID_EDGE"
        self.node = destination
        return f"ARRIVED:{destination}"

    def _read(self, action: V8Action) -> str:
        room = action.room
        if room not in self.ROOMS:
            return "INVALID_LOCATION"
        if room != self.node:
            return "INVALID_LOCATION"
        clue_id = next(
            (key for key, (home, _text) in self.CLUES.items() if home == room), None
        )
        if clue_id is None:  # pragma: no cover - every room has exactly one clue
            return "NO_INSCRIPTION"
        if clue_id not in self.observed:
            self.observed.append(clue_id)
        return f"inscription:{self.CLUES[clue_id][1]}"

    def _record(self, action: V8Action) -> str:
        if self.node != "C":
            return "INVALID_LOCATION"
        clue_id = action.clue_id
        if clue_id is None or clue_id not in self.CLUES:
            return "CLUE_NOT_OBSERVED"
        if clue_id not in self.observed:
            return "CLUE_NOT_OBSERVED"
        if clue_id in self.recorded:
            return "CLUE_ALREADY_RECORDED"
        self.recorded.append(clue_id)
        return f"recorded:{clue_id}"

    def _set_layout(self, action: V8Action) -> str:
        if self.node != "C":
            return "INVALID_LOCATION"
        layout = action.layout_by_room
        if not isinstance(layout, dict) or not self._is_complete_layout(layout):
            return "INVALID_LAYOUT"
        self.trial_layout = {str(slot): str(layout[slot]) for slot in self.SLOTS}
        return "trial_layout_set"

    def _is_complete_layout(self, layout: Any) -> bool:
        if not isinstance(layout, dict):
            return False
        if set(layout) != set(self.SLOTS):
            return False
        values = [layout[slot] for slot in self.SLOTS]
        return sorted(values) == sorted(self.SYMBOLS)

    def _verify(self) -> str:
        if self.node != "C":
            return "INVALID_LOCATION"
        layout = self.trial_layout
        if layout is None or not self._is_complete_layout(layout):
            self.illegal_door_attempts += 1
            return "ILLEGAL_DOOR"
        self.last_attempted_layout = dict(layout)
        if layout == self.TARGET_LAYOUT:
            self.gate_open = True
            self._succeed("GATE_OPENED")
            return "GATE_OPENED"
        self.incorrect_attempts += 1
        self.illegal_door_attempts += 1
        self.state_resets += 1
        self.trial_layout = None
        if self.incorrect_attempts >= self.MAX_INCORRECT_ATTEMPTS:
            self._fail("INCORRECT_ATTEMPT_LIMIT")
            return "STATE_RESET"
        return "STATE_RESET"

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "tick": self.tick_count,
            "target_layout": dict(self.TARGET_LAYOUT),
            "observed": list(self.observed),
            "recorded": list(self.recorded),
            "trial_layout": dict(self.trial_layout) if self.trial_layout else None,
            "last_attempted_layout": (
                dict(self.last_attempted_layout) if self.last_attempted_layout else None
            ),
            "incorrect_attempts": self.incorrect_attempts,
            "illegal_door_attempts": self.illegal_door_attempts,
            "state_resets": self.state_resets,
            "gate_open": self.gate_open,
        }

    def _layout_for_metrics(self) -> dict[str, str] | None:
        return self.last_attempted_layout or self.trial_layout

    def _satisfied_constraints(self) -> int:
        layout = self._layout_for_metrics()
        if layout is None:
            return 0
        position = {
            slot: index + 1 for index, slot in enumerate(self.READING_ORDER)
        }
        by_symbol = {symbol: position[slot] for slot, symbol in layout.items()}
        satisfied = 0
        if by_symbol["日"] in {2, 3}:
            satisfied += 1
        if by_symbol["眼"] > by_symbol["芦"]:
            satisfied += 1
        if abs(by_symbol["甲"] - by_symbol["日"]) == 1:
            satisfied += 1
        if by_symbol["芦"] != 1:
            satisfied += 1
        if "ORIENTATION_ORDER" in self.observed:
            satisfied += 1
        return satisfied

    def metrics(self) -> dict[str, Any]:
        layout = self._layout_for_metrics()
        return {
            "map13.constraint_satisfaction_ratio": {
                "numerator": self._satisfied_constraints(),
                "denominator": 5,
            },
            "map13.correct_sequence": int(layout == self.TARGET_LAYOUT),
            "map13.illegal_door_attempts": self.illegal_door_attempts,
            "map13.state_resets": self.state_resets,
            "map13.completion_ticks": self.tick_count if self.is_success else None,
        }


def _move(edge_id: str, source: str, destination: str) -> dict[str, Any]:
    return {
        "tool": "move",
        "edge_id": edge_id,
        "from_node": source,
        "to_node": destination,
    }


def _read(room: str) -> dict[str, Any]:
    return {"tool": "read_inscription", "room": room}


def _record(clue_id: str) -> dict[str, Any]:
    return {"tool": "record_constraint", "clue_id": clue_id}


def _layout(north: str, east: str, south: str, west: str) -> dict[str, Any]:
    return {
        "tool": "set_trial_layout",
        "layout_by_room": {"N": north, "E": east, "S": south, "W": west},
    }


VERIFY = {"tool": "verify_layout"}


#: 论文两条 20 tick 手写路线，动作即逐步动作（worlds/v4/MAP-13/oracle_trace.jsonl）。
_CONSTRAINT_ACTIONS: list[dict[str, Any]] = [
    _read("C"),
    _record("ORIENTATION_ORDER"),
    _move("C_N", "C", "N"),
    _read("N"),
    _move("C_N", "N", "C"),
    _record("N_SUN_NOT_END"),
    _move("C_E", "C", "E"),
    _read("E"),
    _move("C_E", "E", "C"),
    _record("E_EYE_RIGHT_OF_REED"),
    _move("C_S", "C", "S"),
    _read("S"),
    _move("C_S", "S", "C"),
    _record("S_ARMOR_ADJACENT_TO_SUN"),
    _move("C_W", "C", "W"),
    _read("W"),
    _move("C_W", "W", "C"),
    _record("W_REED_NOT_FIRST"),
    _layout("甲", "日", "芦", "眼"),
    VERIFY,
]

_ENUMERATION_ACTIONS: list[dict[str, Any]] = [
    _read("C"),
    _move("C_W", "C", "W"),
    _read("W"),
    _move("C_W", "W", "C"),
    _move("C_S", "C", "S"),
    _read("S"),
    _move("C_S", "S", "C"),
    _move("C_E", "C", "E"),
    _read("E"),
    _move("C_E", "E", "C"),
    _move("C_N", "C", "N"),
    _read("N"),
    _move("C_N", "N", "C"),
    _record("ORIENTATION_ORDER"),
    _record("W_REED_NOT_FIRST"),
    _record("S_ARMOR_ADJACENT_TO_SUN"),
    _record("E_EYE_RIGHT_OF_REED"),
    _record("N_SUN_NOT_END"),
    _layout("甲", "日", "芦", "眼"),
    VERIFY,
]

ORACLE_CASES = (
    {
        "trace_id": "constraint_propagation",
        "seed": 0,
        "actions": list(_CONSTRAINT_ACTIONS),
        "expect_success": True,
    },
    {
        "trace_id": "systematic_enumeration",
        "seed": 0,
        "actions": list(_ENUMERATION_ACTIONS),
        "expect_success": True,
    },
)

FIXTURES = (
    {
        "name": "constraint_propagation_full_evidence",
        "seed": 0,
        "actions": list(_CONSTRAINT_ACTIONS),
        "expect": {
            "map13.completion_ticks": 20,
            "map13.constraint_satisfaction_ratio": 1.0,
            "map13.correct_sequence": 1,
            "map13.illegal_door_attempts": 0,
            "map13.state_resets": 0,
        },
    },
    {
        "name": "three_blind_guesses_exhaust_tolerance",
        "seed": 0,
        "actions": [
            _layout("甲", "眼", "芦", "日"),
            VERIFY,
            _layout("日", "甲", "芦", "眼"),
            VERIFY,
            _layout("甲", "日", "眼", "芦"),
            VERIFY,
        ],
        "expect": {
            "map13.state_resets": 3,
            "map13.illegal_door_attempts": 3,
            "map13.correct_sequence": 0,
            "map13.constraint_satisfaction_ratio": 0.6,
            "map13.completion_ticks": None,
        },
    },
    {
        "name": "two_wrong_then_correct_still_opens",
        "seed": 0,
        "actions": [
            _layout("甲", "眼", "芦", "日"),
            VERIFY,
            _layout("日", "甲", "芦", "眼"),
            VERIFY,
            _layout("甲", "日", "芦", "眼"),
            VERIFY,
        ],
        "expect": {
            "map13.state_resets": 2,
            "map13.illegal_door_attempts": 2,
            "map13.correct_sequence": 1,
            "map13.completion_ticks": 6,
            "map13.constraint_satisfaction_ratio": 0.8,
        },
    },
    {
        "name": "verify_without_layout_is_illegal_door",
        "seed": 0,
        "actions": [VERIFY],
        "expect": {
            "map13.illegal_door_attempts": 1,
            "map13.state_resets": 0,
            "map13.correct_sequence": 0,
            "map13.constraint_satisfaction_ratio": 0.0,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map13Environment"]
