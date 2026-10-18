"""MAP-29 V10 基线：真值 Oracle、公开分诊启发式与四类消融。

公开启发式只用公开信息：`npc_labels`（职业）、`npc_locations`、`heard_answers`
（含 typed_payload）、`physical_evidence`、`comparison_results`。它**不知道**谁在说谎：
先取档案索引得到真值，再比较每个证人的 `OPEN_ACCOUNT` 主张，用 `TIME_BASIS` 是否存在
区分“记忆锚定”（有时间依据）与“部分真实”（无依据、位置对时刻错），最后做固定比对。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map29 import (
    oracle_actions,
)

Action = dict[str, Any]
ARCHIVE_LABEL = "档案看守"


class _Policy:
    name = "policy"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        raise NotImplementedError


def _archive_truth(observation: dict[str, Any]) -> tuple[str, str] | None:
    for record in observation["heard_answers"]:
        payload = record.get("typed_payload", {})
        if "event_time" in payload and "event_location" in payload:
            return str(payload["event_time"]), str(payload["event_location"])
    return None


def _answer(observation: dict[str, Any], npc: str, template: str) -> dict[str, Any] | None:
    for record in reversed(observation["heard_answers"]):
        if record["npc_id"] == npc and record["question_template_id"] == template:
            return dict(record)
    return None


class Map29Triage(_Policy):
    """公开分诊：档案取真值 → 逐个开放叙述 → 找时间锚定者 → 固定比对 → 提交。"""

    name = "public_heuristic"

    def reset(self) -> None:
        super().reset()

    def _walk(self, observation: dict[str, Any], room: str) -> Action | None:
        if observation["location"] == room:
            return None
        if observation["location"] == "H":
            return {"tool": "move", "to": room}
        self.queue = [{"tool": "move", "to": room}]
        return {"tool": "move", "to": "H"}

    def _ask(self, observation: dict[str, Any], npc: str, template: str) -> Action | None:
        if observation["location"] != observation["npc_locations"][npc]:
            return self._walk(observation, observation["npc_locations"][npc])
        return {"tool": "ask", "npc_id": npc, "question_template_id": template}

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        labels = observation["npc_labels"]
        witnesses = [npc for npc in sorted(labels) if labels[npc] != ARCHIVE_LABEL]
        keeper = next(npc for npc in sorted(labels) if labels[npc] == ARCHIVE_LABEL)
        rooms = observation["npc_locations"]

        def at(room: str) -> Action | None:
            return self._walk(observation, room)

        # 1) 依次听三名证人的声型（满足可能的“先听声型”档案前提）
        for npc in witnesses:
            if _answer(observation, npc, "SOUND_PATTERN") is not None:
                continue
            pending = at(rooms[npc])
            if pending is not None:
                return pending
            return {"tool": "ask", "npc_id": npc, "question_template_id": "SOUND_PATTERN"}
        # 2) 档案交叉索引 → 公开真值
        truth = _archive_truth(observation)
        if truth is None:
            pending = at(rooms[keeper])
            if pending is not None:
                return pending
            if _answer(observation, keeper, "ARCHIVE_CROSS_INDEX") is None:
                return {
                    "tool": "ask",
                    "npc_id": keeper,
                    "question_template_id": "ARCHIVE_CROSS_INDEX",
                }
            return {"tool": "wait", "ticks": 1}
        # 3) 逐个开放叙述
        for npc in witnesses:
            if _answer(observation, npc, "OPEN_ACCOUNT") is not None:
                continue
            pending = at(rooms[npc])
            if pending is not None:
                return pending
            return {"tool": "ask", "npc_id": npc, "question_template_id": "OPEN_ACCOUNT"}
        claims = {}
        for npc in witnesses:
            record = _answer(observation, npc, "OPEN_ACCOUNT")
            if record is None:
                continue
            payload = record["typed_payload"]
            claims[npc] = (
                str(payload.get("event_time_claim")),
                str(payload.get("event_location_claim")),
            )
        # 4) 找到时间锚定者：时刻错且有 TIME_BASIS 依据
        anchored: str | None = None
        for npc in sorted(npc for npc, claim in claims.items() if claim[0] != truth[0]):
            basis = _answer(observation, npc, "TIME_BASIS")
            if basis is None:
                pending = at(rooms[npc])
                if pending is not None:
                    return pending
                return {"tool": "ask", "npc_id": npc, "question_template_id": "TIME_BASIS"}
            if basis["typed_payload"].get("basis"):
                anchored = npc
                break
        if anchored is None:
            return {"tool": "wait", "ticks": 1}
        # 5) 物证
        evidence = {item["evidence_id"] for item in observation["physical_evidence"]}
        if not any(item.startswith("STUDY_CLOCK_") for item in evidence):
            pending = at("L")
            if pending is not None:
                return pending
            return {"tool": "investigate", "target_id": "study_clock"}
        if not any(item.startswith("BELL_MARK_") for item in evidence):
            pending = at(truth[1])
            if pending is not None:
                return pending
            return {"tool": "investigate", "target_id": "bell_trace"}
        clock = next(item for item in evidence if item.startswith("STUDY_CLOCK_"))
        bell = next(item for item in evidence if item.startswith("BELL_MARK_"))
        archive = next(
            item
            for item in {
                *evidence,
                *(src for rec in observation["heard_answers"] for src in rec["source_ids"]),
            }
            if item.startswith("ARCHIVE_EVENT_")
        )
        # 6) 固定比对：时间锚定者 + 部分真实者
        if observation["comparison_results"].get(anchored) is None:
            record = _answer(observation, anchored, "OPEN_ACCOUNT")
            basis = _answer(observation, anchored, "TIME_BASIS")
            statements = sorted(
                {
                    *(record["source_ids"] if record else []),
                    *(basis["source_ids"] if basis else []),
                }
            )
            return {
                "tool": "compare_testimony",
                "npc_id": anchored,
                "statement_ids": statements,
                "against_evidence_ids": [clock, archive],
            }
        partial = [
            npc
            for npc, claim in claims.items()
            if npc != anchored and claim[1] == truth[1] and claim[0] != truth[0]
        ]
        if partial and observation["comparison_results"].get(partial[0]) is None:
            record = _answer(observation, partial[0], "OPEN_ACCOUNT")
            return {
                "tool": "compare_testimony",
                "npc_id": partial[0],
                "statement_ids": sorted(record["source_ids"]) if record else [],
                "against_evidence_ids": [archive, bell],
            }
        # 7) 提交
        pending = at("H")
        if pending is not None:
            return pending
        record = _answer(observation, anchored, "OPEN_ACCOUNT")
        basis = _answer(observation, anchored, "TIME_BASIS")
        proof = sorted(
            {
                *(record["source_ids"] if record else []),
                *(basis["source_ids"] if basis else []),
                clock,
                archive,
            }
        )
        return {
            "tool": "submit",
            "event_time": truth[0],
            "event_location": truth[1],
            "unreliable_npc_id": anchored,
            "support_ids": [archive, bell],
            "unreliability_proof_ids": proof,
        }


class Map29NoCompare(Map29Triage):
    name = "no_compare"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = super().act(observation, history)
        if payload["tool"] == "compare_testimony":
            return {"tool": "wait", "ticks": 1}
        return payload


class Map29TrustFirst(Map29Triage):
    """直接采信第一位证人的整套主张（时刻 + 地点），不核对档案。"""

    name = "trust_first"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = super().act(observation, history)
        if payload["tool"] == "submit":
            first = next(
                (
                    record
                    for record in observation["heard_answers"]
                    if record["question_template_id"] == "OPEN_ACCOUNT"
                    and "event_time_claim" in record["typed_payload"]
                ),
                None,
            )
            if first is not None:
                payload = dict(payload)
                payload["event_time"] = str(first["typed_payload"]["event_time_claim"])
                payload["event_location"] = str(first["typed_payload"]["event_location_claim"])
        return payload


class Map29BlindAccuse(Map29Triage):
    """从不比对，直接指认第一位证人。"""

    name = "blind_accuse"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = super().act(observation, history)
        if payload["tool"] == "compare_testimony":
            return {"tool": "wait", "ticks": 1}
        if payload["tool"] == "submit":
            payload = dict(payload)
            payload["unreliability_proof_ids"] = []
        return payload


class Map29SkipArchive(Map29Triage):
    """不取档案索引，直接凭第一位证人的说法提交。"""

    name = "skip_archive"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = super().act(observation, history)
        if payload["tool"] == "ask" and payload.get("question_template_id") == (
            "ARCHIVE_CROSS_INDEX"
        ):
            return {"tool": "wait", "ticks": 1}
        if payload["tool"] == "submit":
            payload = dict(payload)
            payload["event_time"] = "23:40"
            payload["event_location"] = "Y"
        return payload


HEURISTIC = Map29Triage
ABLATIONS: dict[str, type[Any]] = {
    "no_compare": Map29NoCompare,
    "trust_first": Map29TrustFirst,
    "blind_accuse": Map29BlindAccuse,
    "skip_archive": Map29SkipArchive,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map29BlindAccuse",
    "Map29NoCompare",
    "Map29SkipArchive",
    "Map29Triage",
    "Map29TrustFirst",
    "oracle_actions",
]
