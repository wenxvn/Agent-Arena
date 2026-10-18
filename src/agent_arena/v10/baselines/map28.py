"""MAP-28 V10 基线：真值 Oracle、公开文本启发式与四类消融。

公开启发式只读 Observation 的 `observed_evidence`（含公开 `fact` 文本）、
`recorded_evidence_ids`、`persons`、`entry_paths` 与房间邻接：

- 先到 V/S/K/A 四个来源取证并逐条 `record`；
- 人物取档案登记文本里的姓名；路径取锁芯日志“从 X 侧”一句（H→BANQUET_H_V、
  G→GUARD_G_V、S→SECRET_S_V）；进入/离开分钟优先取锁芯精确分钟，缺出口日志时
  取物证时间窗中点；
- 每栏引用两个不同来源类别，且**剔除与所选值冲突的已记录证据**（例如把 H 路径
  误记成 G 的证词）。
"""

from __future__ import annotations

import re
from typing import Any

from agent_arena.v10.runtime.map28 import (
    CASES,
    CLAIM_FIELDS,
    EDGES,
    oracle_actions,
)

Action = dict[str, Any]
_SIDE_TO_PATH = {"H": "BANQUET_H_V", "G": "GUARD_G_V", "S": "SECRET_S_V"}
_SIDE = re.compile(r"从 ([HGS]) 侧")
_WRONG_SIDE = re.compile(r"路径误记为 ([HGS]) 侧")
_TIMES = re.compile(r"(\d{2}:\d{2})")
_WINDOW = re.compile(r"(\d{2}:\d{2})-(\d{2}:\d{2})")
_NAMED = re.compile(r"(?:匹配|登记给)\s*([A-Za-z]+)")

ADJ: dict[str, tuple[str, ...]] = {}
for _edge_id, (_a, _b) in EDGES.items():
    ADJ.setdefault(_a, ())
    ADJ.setdefault(_b, ())
    ADJ[_a] = (*ADJ[_a], _b)
    ADJ[_b] = (*ADJ[_b], _a)

SOURCES: tuple[tuple[str, Action, str], ...] = (
    ("V", {"tool": "investigate", "target_id": "vault_lock_events"}, "LOCK_"),
    ("S", {"tool": "investigate", "target_id": "footprint_trail"}, "PRINT_"),
    ("K", {"tool": "interview", "witness_id": "kitchen_cook"}, "WITNESS_"),
    ("A", {"tool": "read_record", "record_id": "key_registry"}, "KEY_REGISTER_"),
)


def _route(start: str, destination: str) -> list[str]:
    if start == destination:
        return [start]
    queue: list[list[str]] = [[start]]
    seen = {start}
    while queue:
        path = queue.pop(0)
        for neighbor in ADJ[path[-1]]:
            if neighbor == destination:
                return [*path, neighbor]
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append([*path, neighbor])
    raise ValueError(f"no route {start}->{destination}")


def _midpoint(window: tuple[str, str]) -> str:
    def minutes(value: str) -> int:
        hour, minute = value.split(":")
        return int(hour) * 60 + int(minute)

    total = (minutes(window[0]) + minutes(window[1])) // 2
    return f"{total // 60:02d}:{total % 60:02d}"


def derive(observation: dict[str, Any]) -> dict[str, str]:
    """从公开 `fact` 文本推出四个字段（不读密封真值）。"""

    facts = {item["evidence_id"]: item["fact"] for item in observation["observed_evidence"]}
    person: str | None = None
    path: str | None = None
    entry: str | None = None
    exit_: str | None = None
    for evidence_id, fact in sorted(facts.items()):
        del evidence_id
        named = _NAMED.search(fact)
        if named and person is None:
            person = named.group(1).upper()
        side = _SIDE.search(fact)
        if side and path is None:
            path = _SIDE_TO_PATH[side.group(1)]
        windows = _WINDOW.findall(fact)
        if windows:
            if entry is None:
                entry = _midpoint(windows[0])
            if exit_ is None and len(windows) >= 2:
                exit_ = _midpoint(windows[1])
            continue
        times = _TIMES.findall(fact)
        if times and "开启 V 锁舌" in fact and entry is None:
            entry = times[0]
        if times and "退出" in fact and exit_ is None:
            exit_ = times[0]
    return {
        "person_id": person or "",
        "entry_path_id": path or "",
        "entry_time": entry or "",
        "exit_time": exit_ or "",
    }


def _conflicts(field: str, value: str, fact: str) -> bool:
    if field == "entry_path_id":
        side = _SIDE.search(fact)
        if side and _SIDE_TO_PATH[side.group(1)] != value:
            return True
        wrong = _WRONG_SIDE.search(fact)
        if wrong and _SIDE_TO_PATH[wrong.group(1)] != value:
            return True
    if field == "person_id":
        named = _NAMED.search(fact)
        if named and named.group(1).upper() != value:
            return True
    if field in ("entry_time", "exit_time"):
        windows = _WINDOW.findall(fact)
        if windows:
            index = 1 if field == "exit_time" else 0
            if index < len(windows) and not (windows[index][0] <= value <= windows[index][1]):
                return True
        times = _TIMES.findall(fact)
        if times and "退出" in fact and field == "entry_time" and times[0] != value:
            return True
        if times and "开启 V 锁舌" in fact and field == "exit_time" and times[0] != value:
            return True
    return False


class Map28Heuristic:
    """只用公开 fact 文本的规则启发式。"""

    name = "public_heuristic"

    def __init__(self, *, record: bool = True, cite_all: bool = False) -> None:
        self.record = record
        self.cite_all = cite_all

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        observed = [item["evidence_id"] for item in observation["observed_evidence"]]
        recorded = list(observation["recorded_evidence_ids"])

        if self.record:
            pending = [item for item in observed if item not in recorded]
            if pending:
                return {"tool": "record", "clue_id": pending[0]}

        for room, action, marker in SOURCES:
            if any(item.startswith(marker) for item in observed):
                continue
            if location != room:
                self.queue = [
                    {"tool": "move", "to": step} for step in _route(location, room)[1:]
                ]
                return self.queue.pop(0)
            return action

        claims = derive(observation)
        classes = {
            item["evidence_id"]: item["source_class"]
            for item in observation["observed_evidence"]
        }
        facts = {item["evidence_id"]: item["fact"] for item in observation["observed_evidence"]}
        citations: dict[str, list[str]] = {}
        for field in CLAIM_FIELDS:
            if self.cite_all:
                citations[field] = sorted(observed if not self.record else recorded)
                continue
            chosen: list[str] = []
            for evidence_id in (recorded if self.record else observed):
                if _conflicts(field, claims[field], facts.get(evidence_id, "")):
                    continue
                chosen.append(evidence_id)
                if len({classes.get(item) for item in chosen}) >= 2:
                    break
            citations[field] = chosen
        self.queue = [{"tool": "move", "to": step} for step in _route(location, "H")[1:]]
        submit = {
            "tool": "submit",
            "claims": [{"claim_id": field, "value": claims[field]} for field in CLAIM_FIELDS],
            "citations_by_claim": citations,
        }
        return self.queue.pop(0) if self.queue else submit


class Map28NoRecord(Map28Heuristic):
    name = "no_record"

    def __init__(self) -> None:
        super().__init__(record=False, cite_all=True)


class Map28CiteAll(Map28Heuristic):
    name = "cite_all"

    def __init__(self) -> None:
        super().__init__(record=True, cite_all=True)


class Map28SingleSource(Map28Heuristic):
    name = "single_source"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = super().act(observation, history)
        if payload["tool"] == "submit":
            payload = dict(payload)
            payload["citations_by_claim"] = {
                field: ids[:1] for field, ids in payload["citations_by_claim"].items()
            }
        return payload


class Map28BlindSubmit:
    name = "blind_submit"

    def reset(self) -> None:
        self.done = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.done:
            return {"tool": "wait", "ticks": 1}
        self.done = True
        claims = {
            "person_id": observation["persons"][0],
            "entry_path_id": observation["entry_paths"][0],
            "entry_time": "21:06",
            "exit_time": "21:14",
        }
        return {
            "tool": "submit",
            "claims": [{"claim_id": field, "value": claims[field]} for field in CLAIM_FIELDS],
            "citations_by_claim": {field: [] for field in CLAIM_FIELDS},
        }


HEURISTIC = Map28Heuristic
ABLATIONS: dict[str, type[Any]] = {
    "no_record": Map28NoRecord,
    "single_source": Map28SingleSource,
    "cite_all": Map28CiteAll,
    "blind_submit": Map28BlindSubmit,
}

__all__ = [
    "ABLATIONS",
    "CASES",
    "HEURISTIC",
    "Map28BlindSubmit",
    "Map28CiteAll",
    "Map28Heuristic",
    "Map28NoRecord",
    "Map28SingleSource",
    "derive",
    "oracle_actions",
]
