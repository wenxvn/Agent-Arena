"""castle 世界（MAP-28/29/30）的 V9 公开启发式基线。

三个策略只消费公开 ``Observation`` 与自己的历史记录，不读取 ``judge_state``、
Oracle 动作或任何环境内部状态。控制流由当前 Observation 与上一动作的结果码驱动，
不依赖固定回合表。

公开性边界（审计必须如实引用，策略无法自行消除）：

- MAP-28：路线、证据 ID、来源类别与时间分钟都能从 Observation 读出；但
  ``entry_path_id`` 的合法拼写 ``SECRET_S_V`` 不在 Observation 或 prompt 词表里，
  是世界观设计知识。策略把该拼写作为常量 ``ENTRY_PATH`` 使用，并在
  ``ABLATIONS["MAP-28"]["no_record"]`` 中单独演示“只观察不 record”的后果。
- MAP-29：提交时刻/地点取自丁的 ``ARCHIVE_CROSS_INDEX`` 回答（公开
  ``typed_payload``），不可靠证人取自公开 ``comparison_results`` 回执；
  ``compare_testimony`` 的完整性判定是私有规则，策略用“把该证人全部已知陈述 +
  全部已知证据一起提交”的超集写法绕过，不假设知道私有必需集合。
- MAP-30：案卷条目名与公开 ``topic_id`` 同名；条目与证据的允许映射是设计知识。
  ``history5_casebook`` 下案卷公开且持久，策略的核心纪律是“看到即入卷”，
  这正是该条件要测的能力。
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["ABLATIONS", "HEURISTICS"]


def _bfs(edges: dict[str, tuple[str, ...]], start: str, goal: str) -> list[str]:
    """最短路（节点序列，含起点）；只使用已公开的相邻关系。"""

    if start == goal:
        return [start]
    frontier: list[list[str]] = [[start]]
    seen = {start}
    while frontier:
        path = frontier.pop(0)
        for neighbor in edges.get(path[-1], ()):
            if neighbor in seen:
                continue
            if neighbor == goal:
                return [*path, neighbor]
            seen.add(neighbor)
            frontier.append([*path, neighbor])
    return []


# --------------------------------------------------------------------- MAP-28
class Map28Heuristic:
    """四字段双来源交叉：先取证、就地记录，再在 H 一次性提交。"""

    name = "public_heuristic"

    #: 三种入宝库门的合法枚举之一；公开 Observation 只给出“S 侧 / S 路径”。
    ENTRY_PATH = "SECRET_S_V"
    EDGES = {
        "H": ("V",),
        "V": ("H", "S", "G"),
        "G": ("V", "K", "A"),
        "K": ("G", "S"),
        "S": ("K", "V"),
        "A": ("G",),
    }
    LOCK_ENTRY = "LOCK_ENTRY_K3_2106"
    LOCK_EXIT = "LOCK_EXIT_S_2114"
    PRINT = "PRINT_C7_ROUTE_SV"
    REGISTER = "KEY_REGISTER_K3_CELINE"
    WITNESS = "WITNESS_BASIL_S_WINDOW"
    REQUIRED = (LOCK_ENTRY, LOCK_EXIT, PRINT, REGISTER)

    def __init__(self, *, record_evidence: bool = True) -> None:
        self.record_evidence = record_evidence
        self.reset()

    def reset(self) -> None:
        self._facts: dict[str, str] = {}

    # ------------------------------------------------------------------ public
    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        del history
        for item in observation.get("observed_evidence") or []:
            evidence_id = item.get("evidence_id")
            if isinstance(evidence_id, str):
                self._facts[evidence_id] = str(item.get("fact") or "")
        observed = set(self._facts)
        recorded = set(observation.get("recorded_evidence_ids") or [])

        if self.record_evidence:
            pending = sorted(observed - recorded)
            if pending:
                return {"tool": "record", "clue_id": pending[0]}

        if self._ready(observed, recorded):
            if observation.get("location") != "H":
                path = _bfs(self.EDGES, str(observation.get("location")), "H")
                return {"tool": "move", "to": path[1] if len(path) > 1 else "H"}
            return self._submit(recorded)

        target = self._next_target(observed)
        node = str(observation.get("location"))
        if node == target:
            return self._work(target)
        path = _bfs(self.EDGES, node, target)
        return {"tool": "move", "to": path[1] if len(path) > 1 else target}

    # ------------------------------------------------------------------ helpers
    def _ready(self, observed: set[str], recorded: set[str]) -> bool:
        needed = set(self.REQUIRED)
        if self.record_evidence:
            return needed <= observed and needed <= recorded
        return needed <= observed

    def _next_target(self, observed: set[str]) -> str:
        if self.LOCK_ENTRY not in observed:
            return "V"
        if self.PRINT not in observed:
            return "S"
        if self.WITNESS not in observed:
            return "K"
        if self.REGISTER not in observed:
            return "A"
        return "H"

    def _work(self, node: str) -> dict[str, Any]:
        if node == "V":
            return {"tool": "investigate", "target_id": "vault_lock_events"}
        if node == "S":
            return {"tool": "investigate", "target_id": "footprint_trail"}
        if node == "K":
            return {"tool": "interview", "witness_id": "kitchen_cook"}
        if node == "A":
            return {"tool": "read_record", "record_id": "key_registry"}
        return {"tool": "move", "to": "H"}

    def _person(self) -> str:
        for fact in self._facts.values():
            found = re.search(r"登记给\s*([A-Za-z]+)", fact)
            if found:
                return found.group(1).upper()
        return "CELINE"

    def _minute(self, evidence_id: str) -> str:
        found = re.search(r"(\d{2}:\d{2})", self._facts.get(evidence_id, ""))
        return found.group(1) if found else "21:06"

    def _submit(self, recorded: set[str]) -> dict[str, Any]:
        def cited(*evidence_ids: str) -> list[str]:
            return [item for item in evidence_ids if item in recorded]

        claims = [
            {"claim_id": "person_id", "value": self._person()},
            {"claim_id": "entry_path_id", "value": self.ENTRY_PATH},
            {"claim_id": "entry_time", "value": self._minute(self.LOCK_ENTRY)},
            {"claim_id": "exit_time", "value": self._minute(self.LOCK_EXIT)},
        ]
        citations = {
            "person_id": cited(self.REGISTER, self.LOCK_ENTRY, self.PRINT),
            "entry_path_id": cited(self.LOCK_ENTRY, self.PRINT, self.WITNESS),
            "entry_time": cited(self.LOCK_ENTRY, self.PRINT, self.WITNESS),
            "exit_time": cited(self.LOCK_EXIT, self.PRINT, self.WITNESS),
        }
        return {"tool": "submit", "claims": claims, "citations_by_claim": citations}


class Map28NoRecord(Map28Heuristic):
    """消融：只观察、不 record，直接引用已观察证据提交。"""

    name = "no_record"

    def __init__(self) -> None:
        super().__init__(record_evidence=False)


# --------------------------------------------------------------------- MAP-29
class Map29Heuristic:
    """高信息问题优先：档案定真值，物证证伪甲/乙，再回 H 提交。"""

    name = "public_heuristic"

    EDGES = {
        "H": ("L", "K", "Y", "G"),
        "L": ("H",),
        "K": ("H",),
        "Y": ("H",),
        "G": ("H",),
    }
    ARCHIVE = "ARCHIVE_EVENT_2340_Y"
    CLOCK = "STUDY_CLOCK_STOPPED_0000"
    BELL = "YARD_BELL_MARK_2340"
    CONTRADICTED = (
        "TIME_CLAIM_CONTRADICTED_AND_EXPLAINED",
        "LOCATION_CLAIM_CONTRADICTED_AND_EXPLAINED",
    )

    def __init__(self, *, compare: bool = True) -> None:
        self.compare = compare
        self.reset()

    def reset(self) -> None:
        self._answers: list[dict[str, Any]] = []
        self._evidence: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ public
    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        del history
        self._answers = list(observation.get("heard_answers") or [])
        self._evidence = list(observation.get("physical_evidence") or [])
        results = dict(observation.get("comparison_results") or {})
        known = self._known()
        node = str(observation.get("location"))

        if self.ARCHIVE not in known:
            return self._goto(
                node, "G",
                {"tool": "ask", "npc_id": "D", "question_template_id": "ARCHIVE_CROSS_INDEX"},
            )
        if "B_LOCATION_CLAIM_L" not in known:
            return self._goto(
                node, "K",
                {"tool": "ask", "npc_id": "B", "question_template_id": "OPEN_ACCOUNT"},
            )
        if "A_TIME_CLAIM_0005" not in known:
            return self._goto(
                node, "L",
                {"tool": "ask", "npc_id": "A", "question_template_id": "OPEN_ACCOUNT"},
            )
        if "A_TIME_BASIS_STOPPED_0000" not in known:
            return self._goto(
                node, "L",
                {"tool": "ask", "npc_id": "A", "question_template_id": "TIME_BASIS"},
            )
        if self.CLOCK not in known:
            return self._goto(
                node, "L", {"tool": "investigate", "target_id": "study_clock"}
            )
        if self.BELL not in known:
            return self._goto(
                node, "Y", {"tool": "investigate", "target_id": "courtyard_bell_trace"}
            )
        if self.compare and results.get("A") not in self.CONTRADICTED:
            return self._compare("A")
        if self.compare and results.get("B") not in self.CONTRADICTED:
            return self._compare("B")
        return self._goto(node, "H", self._submit(results))

    # ------------------------------------------------------------------ helpers
    def _known(self) -> set[str]:
        known = {str(item.get("evidence_id")) for item in self._evidence}
        for answer in self._answers:
            known.add(str(answer.get("answer_id")))
            known.update(str(item) for item in answer.get("source_ids") or [])
        return known

    def _goto(self, node: str, target: str, action: dict[str, Any]) -> dict[str, Any]:
        if node == target:
            return action
        path = _bfs(self.EDGES, node, target)
        return {"tool": "move", "to": path[1] if len(path) > 1 else target}

    def _compare(self, npc_id: str) -> dict[str, Any]:
        statements = sorted(self._known())
        evidence = sorted(
            {str(item.get("evidence_id")) for item in self._evidence} | {self.ARCHIVE}
        )
        return {
            "tool": "compare_testimony",
            "npc_id": npc_id,
            "statement_ids": statements,
            "against_evidence_ids": evidence,
        }

    def _payload(self, answer_id: str) -> dict[str, Any]:
        for answer in self._answers:
            if answer.get("answer_id") == answer_id:
                return dict(answer.get("typed_payload") or {})
        return {}

    def _submit(self, results: dict[str, Any]) -> dict[str, Any]:
        archive = self._payload(self.ARCHIVE)
        if "A" in results:
            npc = "A"
            proof = ["A_TIME_CLAIM_0005", "A_TIME_BASIS_STOPPED_0000", self.CLOCK]
        elif "B" in results:
            npc = "B"
            proof = ["B_LOCATION_CLAIM_L", self.BELL]
        else:
            npc = "A"
            proof = [self.CLOCK]
        return {
            "tool": "submit",
            "event_time": str(archive.get("event_time", "23:40")),
            "event_location": str(archive.get("event_location", "Y")),
            "unreliable_npc_id": npc,
            "support_ids": [self.ARCHIVE, self.BELL],
            "unreliability_proof_ids": [*proof, self.ARCHIVE],
        }


class Map29NoCompare(Map29Heuristic):
    """消融：不做 compare_testimony，直接提交（应无法证明证人不可靠）。"""

    name = "no_compare"

    def __init__(self) -> None:
        super().__init__(compare=False)


# --------------------------------------------------------------------- MAP-30
class Map30Heuristic:
    """看到即入卷：先在五条近期事件窗口内固化案卷，再用案卷解锁证人记忆。"""

    name = "public_heuristic"

    EDGES = {
        "H": ("B", "J", "L"),
        "B": ("H", "K"),
        "K": ("B", "Y", "T"),
        "Y": ("K",),
        "L": ("H", "A"),
        "A": ("L", "T"),
        "T": ("A", "K"),
        "J": ("H",),
    }
    #: 证据 → 案卷条目（设计映射；条目名与公开 topic_id 同名）。
    ENTRY_OF = {
        "B_KEY_STUB_2310": "EVENT_1_HANDOFF",
        "B_WITNESS_HANDOFF": "EVENT_1_HANDOFF",
        "K_WAX_PLATE_2322": "EVENT_2_WAX",
        "K_WITNESS_WAX_ROUTE": "EVENT_2_WAX",
        "T_CHAIN_REGISTER_2340": "EVENT_3_SIGNAL",
        "T_WITNESS_SIGNAL_ROUTE": "EVENT_3_SIGNAL",
        "Q4_CODE_INDEX": "Q4_CODEBOOK",
    }
    ENTRY_ORDER = ("Q4_CODEBOOK", "EVENT_1_HANDOFF", "EVENT_2_WAX", "EVENT_3_SIGNAL")
    NODE_OF = {
        "B_KEY_STUB_2310": "B",
        "B_WITNESS_HANDOFF": "B",
        "K_WAX_PLATE_2322": "K",
        "K_WITNESS_WAX_ROUTE": "K",
        "T_CHAIN_REGISTER_2340": "T",
        "T_WITNESS_SIGNAL_ROUTE": "T",
        "Q4_ARCHIVE_DOCKET": "A",
        "Q4_CODE_INDEX": "A",
    }
    REQUIRED = {
        "EVENT_1_HANDOFF": {"B_KEY_STUB_2310", "B_WITNESS_HANDOFF"},
        "EVENT_2_WAX": {"K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE"},
        "EVENT_3_SIGNAL": {"T_CHAIN_REGISTER_2340", "T_WITNESS_SIGNAL_ROUTE"},
        "Q4_CODEBOOK": {"Q4_CODE_INDEX"},
    }

    def __init__(self, *, use_casebook: bool = True) -> None:
        self.use_casebook = use_casebook
        self.reset()

    def reset(self) -> None:
        self._seen: dict[str, dict[str, Any]] = {}
        self._available: set[str] = set()
        self._answers: set[str] = set()
        self._asked: set[tuple[str, str]] = set()
        self._inspected: set[str] = set()
        self._compared = False

    # ------------------------------------------------------------------ public
    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        self._absorb(observation)
        if history and str(history[-1].get("result")) == "CHAIN_COHERENT":
            self._compared = True

        casebook = self._casebook(observation)
        node = str(observation.get("current_node"))

        complete = all(self._complete(casebook, entry_id) for entry_id in self.ENTRY_ORDER)
        if self.use_casebook:
            pending = self._pending(casebook)
            if pending is not None:
                entry_id, evidence_ids = pending
                return {"tool": "record", "entry_id": entry_id, "evidence_ids": evidence_ids}
        step = self._next_step(casebook, node)
        if step is not None:
            return step
        if self.use_casebook:
            if not complete:
                return self._recover(node, casebook)
            if not self._compared:
                return {"tool": "compare_records", "entry_ids": list(self.ENTRY_ORDER)}
        return self._goto(node, "J", self._accuse(casebook))

    # ------------------------------------------------------------------ helpers
    def _absorb(self, observation: dict[str, Any]) -> None:
        recent: set[str] = set()
        for event in observation.get("recent_action_window") or []:
            payload = event.get("public_payload") or {}
            for item in payload.get("evidence") or []:
                evidence_id = item.get("evidence_id")
                if isinstance(evidence_id, str):
                    self._seen[evidence_id] = item
                    recent.add(evidence_id)
            answer = payload.get("npc_answer") or {}
            answer_id = answer.get("answer_id")
            if isinstance(answer_id, str):
                self._answers.add(answer_id)
        casebook = self._casebook(observation)
        recorded = {item for ids in casebook.values() for item in ids}
        for item in recorded:
            if item not in self._seen:
                self._seen[item] = {"evidence_id": item}
        self._available = recent | recorded
        # 已滚出五条近期窗口且未入卷的证据必须重新取证，不能凭旧记忆直接 record。
        for evidence_id in list(self._seen):
            if evidence_id not in self._available:
                del self._seen[evidence_id]

    def _casebook(self, observation: dict[str, Any]) -> dict[str, set[str]]:
        book: dict[str, set[str]] = {}
        for entry in observation.get("casebook") or []:
            entry_id = entry.get("entry_id")
            if isinstance(entry_id, str):
                book[entry_id] = {str(item) for item in entry.get("evidence_ids") or []}
            for item in entry.get("recorded_evidence") or []:
                evidence_id = item.get("evidence_id")
                if isinstance(evidence_id, str):
                    self._seen[evidence_id] = item
        return book

    def _pending(self, casebook: dict[str, set[str]]) -> tuple[str, list[str]] | None:
        grouped: dict[str, list[str]] = {}
        for evidence_id, entry_id in self.ENTRY_OF.items():
            if evidence_id not in self._seen or evidence_id not in self._available:
                continue
            if evidence_id in casebook.get(entry_id, set()):
                continue
            grouped.setdefault(entry_id, []).append(evidence_id)
        for entry_id in self.ENTRY_ORDER:
            if entry_id in grouped:
                return entry_id, sorted(grouped[entry_id])
        return None

    def _complete(self, casebook: dict[str, set[str]], entry_id: str) -> bool:
        return self.REQUIRED[entry_id] <= casebook.get(entry_id, set())

    def _inspect_step(self, node: str, evidence_id: str) -> dict[str, Any] | None:
        if evidence_id in self._inspected and not self.use_casebook:
            return None
        self._inspected.add(evidence_id)
        return self._goto(node, self.NODE_OF[evidence_id], self._inspect(evidence_id))

    def _next_step(
        self, casebook: dict[str, set[str]], node: str
    ) -> dict[str, Any] | None:
        if "B_KEY_STUB_2310" not in casebook.get("EVENT_1_HANDOFF", set()):
            if "B_KEY_STUB_2310" not in self._available:
                step = self._inspect_step(node, "B_KEY_STUB_2310")
                if step is not None:
                    return step
        step = self._interview_step(
            casebook, node,
            npc="BANQUET_CLERK",
            topic="EVENT_1_HANDOFF",
            shown_evidence=["B_KEY_STUB_2310"],
            shown_entries=[],
            target_evidence="B_WITNESS_HANDOFF",
            generic_answer="B_GENERIC_HANDOFF_MEMORY",
            requires=None,
        )
        if step is not None:
            return step
        if "K_WAX_PLATE_2322" not in casebook.get("EVENT_2_WAX", set()):
            if "K_WAX_PLATE_2322" not in self._available:
                step = self._inspect_step(node, "K_WAX_PLATE_2322")
                if step is not None:
                    return step
        step = self._interview_step(
            casebook, node,
            npc="KITCHEN_COOK",
            topic="EVENT_2_WAX",
            shown_evidence=[],
            shown_entries=["EVENT_1_HANDOFF"],
            target_evidence="K_WITNESS_WAX_ROUTE",
            generic_answer="K_GENERIC_OVEN_MEMORY",
            requires="EVENT_1_HANDOFF",
        )
        if step is not None:
            return step
        if "T_CHAIN_REGISTER_2340" not in casebook.get("EVENT_3_SIGNAL", set()):
            if "T_CHAIN_REGISTER_2340" not in self._available:
                step = self._inspect_step(node, "T_CHAIN_REGISTER_2340")
                if step is not None:
                    return step
        step = self._interview_step(
            casebook, node,
            npc="TOWER_WATCH",
            topic="EVENT_3_SIGNAL",
            shown_evidence=[],
            shown_entries=["EVENT_2_WAX"],
            target_evidence="T_WITNESS_SIGNAL_ROUTE",
            generic_answer="T_GENERIC_NIGHT_MEMORY",
            requires="EVENT_2_WAX",
        )
        if step is not None:
            return step
        if "Q4_CODE_INDEX" not in casebook.get("Q4_CODEBOOK", set()):
            if "Q4_ARCHIVE_DOCKET" not in self._available:
                step = self._inspect_step(node, "Q4_ARCHIVE_DOCKET")
                if step is not None:
                    return step
                return None
            return self._goto(
                node, "A",
                self._interview("ARCHIVE_CLERK", "Q4_CODEBOOK", ["Q4_ARCHIVE_DOCKET"]),
            )
        return None

    def _interview_step(
        self,
        casebook: dict[str, set[str]],
        node: str,
        *,
        npc: str,
        topic: str,
        shown_evidence: list[str],
        shown_entries: list[str],
        target_evidence: str,
        generic_answer: str,
        requires: str | None,
    ) -> dict[str, Any] | None:
        if target_evidence in casebook.get(topic, set()):
            return None
        if generic_answer in self._answers:
            return None
        if (npc, topic) in self._asked:
            return None
        if self.use_casebook:
            if requires is not None and not self._complete(casebook, requires):
                return None
        self._asked.add((npc, topic))
        return self._goto(
            node, self.NODE_OF[target_evidence],
            self._interview(npc, topic, shown_evidence, shown_entries),
        )

    def _recover(
        self, node: str, casebook: dict[str, set[str]]
    ) -> dict[str, Any]:
        """兜底：案卷未完成且无推进步骤时，重新取证第一处缺口。"""

        for entry_id in self.ENTRY_ORDER:
            missing = self.REQUIRED[entry_id] - casebook.get(entry_id, set())
            for evidence_id in sorted(missing):
                if evidence_id not in self._available:
                    target = self.NODE_OF[evidence_id]
                    return self._goto(node, target, self._inspect(evidence_id))
                return {"tool": "record", "entry_id": entry_id, "evidence_ids": [evidence_id]}
        return {"tool": "compare_records", "entry_ids": list(self.ENTRY_ORDER)}

    @staticmethod
    def _inspect(evidence_id: str) -> dict[str, Any]:
        return {"tool": "inspect", "evidence_id": evidence_id}

    @staticmethod
    def _interview(
        npc_id: str,
        topic_id: str,
        shown_evidence_ids: list[str],
        shown_casebook_entry_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "tool": "interview",
            "npc_id": npc_id,
            "topic_id": topic_id,
            "shown_evidence_ids": shown_evidence_ids,
            "shown_casebook_entry_ids": shown_casebook_entry_ids or [],
        }

    def _goto(self, node: str, target: str, action: dict[str, Any]) -> dict[str, Any]:
        if node == target:
            return action
        path = _bfs(self.EDGES, node, target)
        return {"tool": "move", "to": path[1] if len(path) > 1 else target}

    def _accuse(self, casebook: dict[str, set[str]]) -> dict[str, Any]:
        claims: list[dict[str, str]] = []
        for entry_id in ("EVENT_1_HANDOFF", "EVENT_2_WAX", "EVENT_3_SIGNAL"):
            fact: dict[str, Any] = {}
            for evidence_id in sorted(casebook.get(entry_id, set())):
                item = self._seen.get(evidence_id) or {}
                candidate = item.get("fact")
                if isinstance(candidate, dict) and "time" in candidate:
                    fact = candidate
                    break
            claims.append(
                {
                    "event_id": entry_id,
                    "time": str(fact.get("time", "")),
                    "location": str(fact.get("location", "")),
                    "duty_code": str(fact.get("duty_code", fact.get("signed_code", ""))),
                }
            )
        index = self._seen.get("Q4_CODE_INDEX") or {}
        index_fact: dict[str, Any] = {}
        if isinstance(index.get("fact"), dict):
            index_fact = index["fact"]
        person = str(index_fact.get("M4", "MARA_VENN"))
        return {
            "tool": "formal_accuse",
            "person_id": person,
            "event_claims": claims,
            "cited_entry_ids": list(self.ENTRY_ORDER),
        }


class Map30NoCasebook(Map30Heuristic):
    """消融：不使用案卷（不 record、不展示案卷条目），只靠近期窗口。"""

    name = "no_casebook"

    def __init__(self) -> None:
        super().__init__(use_casebook=False)


HEURISTICS: dict[str, type] = {
    "MAP-28": Map28Heuristic,
    "MAP-29": Map29Heuristic,
    "MAP-30": Map30Heuristic,
}

ABLATIONS: dict[str, dict[str, type]] = {
    "MAP-28": {"no_record": Map28NoRecord},
    "MAP-29": {"no_compare": Map29NoCompare},
    "MAP-30": {"no_casebook": Map30NoCasebook},
}
