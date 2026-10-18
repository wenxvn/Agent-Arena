"""MAP-30 V10 基线：真值 Oracle、公开链条启发式与四类消融。

公开启发式只读 Observation 的 `entry_requirements`、`npc_locations`、
`evidence_locations`、`visible_local_evidence`、`recent_action_window`、`casebook`
与 `courtroom_node`：

1. 先到档案房：inspect 封套物证 → 向档案看守要交叉索引 → `record(Q4_CODEBOOK)`；
   公开 payload 给出“值班代号 ↔ 人名”映射，从而知道哪些事件物证属于本案；
2. 按 `entry_requirements` 顺序巡房：inspect 本条目物证；若 `duty_code` 不在映射里
   就是诱饵事件（记录但不引用）；否则向该房间证人出示本事件物证 + 已完整的前序
   条目，拿到证人确认后 `record` 成对补全；
3. `compare_records` 核对链条，再到 `courtroom_node` 提交指控。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map30 import (
    ADJACENCY,
    COURTROOM,
    oracle_actions,
)

Action = dict[str, Any]
EXPLORE_ORDER = ("L", "K", "T", "A", "B")


def _route(start: str, destination: str) -> list[str]:
    if start == destination:
        return [start]
    queue: list[list[str]] = [[start]]
    seen = {start}
    while queue:
        path = queue.pop(0)
        for neighbor in ADJACENCY[path[-1]]:
            if neighbor == destination:
                return [*path, neighbor]
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append([*path, neighbor])
    raise ValueError(f"no route {start}->{destination}")


class Map30Chain:
    name = "public_heuristic"

    def __init__(self, *, record: bool = True) -> None:
        self.record = record

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.spec: dict[str, dict[str, Any]] = {}
        self.code_map: dict[str, str] = {}
        self.true_entries: list[str] = []
        self.processed: set[str] = set()
        self.skip_entries: set[str] = set()
        self.archive_asked = False

    # ------------------------------------------------------------------ helpers
    def _note(self, observation: dict[str, Any]) -> None:
        for evidence_id, value in observation["visible_local_evidence"].items():
            self.spec[evidence_id] = value
        for entry in observation["recent_action_window"]:
            payload = entry.get("payload")
            if payload and "document_id" in payload:
                self.code_map = {
                    key: value for key, value in payload.items() if key != "document_id"
                }

    def _walk(self, observation: dict[str, Any], destination: str) -> Action | None:
        if observation["location"] == destination:
            return None
        route = _route(observation["location"], destination)
        self.queue = [{"tool": "move", "to": step} for step in route[2:]]
        return {"tool": "move", "to": route[1]}

    def _witness_at(self, observation: dict[str, Any], room: str) -> str | None:
        for npc, home in sorted(observation["npc_locations"].items()):
            if home == room:
                return str(npc)
        return None

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        self._note(observation)
        if self.queue:
            return self.queue.pop(0)
        requirements = observation["entry_requirements"]
        locations = observation["evidence_locations"]
        recorded = {item for ids in observation["casebook"].values() for item in ids}

        # 第 1 步：档案索引
        archive_evidence = next(
            (
                evidence_id
                for evidence_id in locations
                if evidence_id not in {ids[0] for ids in requirements.values()}
            ),
            None,
        )
        if "Q4_CODEBOOK" not in observation["casebook"] and archive_evidence is not None:
            room = str(locations[archive_evidence])
            move = self._walk(observation, room)
            if move is not None:
                return move
            if archive_evidence in observation["visible_local_evidence"]:
                return {"tool": "inspect", "evidence_id": archive_evidence}
            witness = self._witness_at(observation, room)
            if witness is not None and not self.archive_asked:
                self.archive_asked = True
                return {
                    "tool": "interview",
                    "npc_id": witness,
                    "topic_id": "Q4_CODEBOOK",
                    "shown_evidence_ids": [archive_evidence],
                    "shown_casebook_entry_ids": [],
                }
            answer = next(
                (
                    entry["object_id"]
                    for entry in observation["recent_action_window"]
                    if entry.get("payload")
                ),
                None,
            )
            if self.record and answer is not None and "Q4_CODEBOOK" not in observation["casebook"]:
                return {
                    "tool": "record",
                    "entry_id": "Q4_CODEBOOK",
                    "evidence_ids": [str(answer)],
                }
        if not self.code_map:
            return {"tool": "wait", "ticks": 1}

        # 第 2 步：按条目顺序补全
        codes = set(self.code_map)
        for entry_id, ids in requirements.items():
            if entry_id in self.processed:
                continue
            if entry_id in self.skip_entries:
                self.processed.add(entry_id)
                continue
            evidence_id, answer_id = ids[0], str(ids[1])
            room = str(locations[evidence_id])
            move = self._walk(observation, room)
            if move is not None:
                return move
            if evidence_id in observation["visible_local_evidence"]:
                return {"tool": "inspect", "evidence_id": evidence_id}
            spec = self.spec.get(evidence_id) or {}
            is_true = spec.get("duty_code") in codes
            if not is_true:
                self.processed.add(entry_id)
                continue
            if not self.record:
                self.true_entries.append(entry_id)
                self.processed.add(entry_id)
                continue
            if evidence_id not in recorded:
                return {
                    "tool": "record",
                    "entry_id": entry_id,
                    "evidence_ids": [evidence_id],
                }
            if answer_id not in recorded:
                window_ids = {
                    str(entry["object_id"]) for entry in observation["recent_action_window"]
                }
                if answer_id in window_ids:
                    return {
                        "tool": "record",
                        "entry_id": entry_id,
                        "evidence_ids": [answer_id],
                    }
                complete = [
                    other
                    for other in self.true_entries
                    if set(requirements[other]) <= set(observation["casebook"].get(other, []))
                ]
                witness = self._witness_at(observation, room)
                if witness is None:
                    self.processed.add(entry_id)
                    continue
                return {
                    "tool": "interview",
                    "npc_id": witness,
                    "topic_id": entry_id,
                    "shown_evidence_ids": [evidence_id],
                    "shown_casebook_entry_ids": complete,
                }
            self.true_entries.append(entry_id)
            self.processed.add(entry_id)

        required = [*self.true_entries, "Q4_CODEBOOK"]
        if not observation["chain_reconciled"]:
            return {"tool": "compare_records", "entry_ids": required}
        move = self._walk(observation, COURTROOM)
        if move is not None:
            return move
        claims = [
            {
                "event_id": entry_id,
                "time": self.spec[requirements[entry_id][0]]["time"],
                "location": self.spec[requirements[entry_id][0]]["location"],
                "duty_code": self.spec[requirements[entry_id][0]]["duty_code"],
            }
            for entry_id in self.true_entries
        ]
        return {
            "tool": "formal_accuse",
            "person_id": next(iter(self.code_map.values()), ""),
            "event_claims": claims,
            "cited_entry_ids": required,
        }


class Map30NoCasebook(Map30Chain):
    name = "no_casebook"

    def __init__(self) -> None:
        super().__init__(record=False)

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = super().act(observation, history)
        if payload["tool"] in ("record", "interview"):
            return {"tool": "wait", "ticks": 1}
        return payload


class Map30LateGuess(Map30Chain):
    name = "late_guess"

    def reset(self) -> None:
        super().reset()
        self.done = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.done:
            return {"tool": "wait", "ticks": 1}
        self.done = True
        return {
            "tool": "formal_accuse",
            "person_id": "UNKNOWN",
            "event_claims": [],
            "cited_entry_ids": [],
        }


class Map30EvidenceShuffle(Map30Chain):
    name = "evidence_shuffle"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = super().act(observation, history)
        if payload["tool"] == "formal_accuse":
            payload = dict(payload)
            claims = list(payload["event_claims"])
            if len(claims) >= 2:
                claims[0], claims[1] = claims[1], claims[0]
            payload["event_claims"] = claims
        return payload


class Map30WindowDelay(Map30Chain):
    """证人确认后延迟 5 次无关追问再入卷：确认已飞出 5 条窗口，配对被窗口拒绝。"""

    name = "window_delay"

    def reset(self) -> None:
        super().reset()
        self.stall = 0
        self.stall_npc: str | None = None
        self.stall_topic: str | None = None
        self.pending_record: tuple[str, str] | None = None

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        if self.stall > 0:
            self.stall -= 1
            return {
                "tool": "interview",
                "npc_id": self.stall_npc,
                "topic_id": self.stall_topic,
                "shown_evidence_ids": [],
                "shown_casebook_entry_ids": [],
            }
        if self.pending_record is not None:
            entry_id, answer_id = self.pending_record
            self.pending_record = None
            self.skip_entries.add(entry_id)
            return {"tool": "record", "entry_id": entry_id, "evidence_ids": [answer_id]}
        payload = super().act(observation, history)
        if payload["tool"] == "interview" and payload.get("topic_id") != "Q4_CODEBOOK":
            entry_id = str(payload["topic_id"])
            others = [item for item in observation["entry_requirements"] if item != entry_id]
            if others and self.stall_npc is None:
                self.stall_npc = str(payload["npc_id"])
                self.stall_topic = others[0]
                self.stall = 5
                answer = str(observation["entry_requirements"][entry_id][1])
                self.pending_record = (entry_id, answer)
        return payload


HEURISTIC = Map30Chain
ABLATIONS: dict[str, type[Any]] = {
    "no_casebook": Map30NoCasebook,
    "late_guess": Map30LateGuess,
    "evidence_shuffle": Map30EvidenceShuffle,
    "window_delay": Map30WindowDelay,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map30Chain",
    "Map30EvidenceShuffle",
    "Map30LateGuess",
    "Map30NoCasebook",
    "Map30WindowDelay",
    "oracle_actions",
]
