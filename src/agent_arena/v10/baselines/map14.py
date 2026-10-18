"""MAP-14 V10 基线：真值 Oracle、九态一致假设启发式与四类消融。

公开启发式只读 `configurations`、`public_statement_cards`、`question_answers`、
`archive_record_if_read`、`questions_remaining` 与公开的“恰一人全真”规则：
先读档案（不计提问预算），再每次挑“能把候选锁型一分为二”的命题，直到候选唯一，
在比对台封存该假设，最后在审判门提交。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map14 import (
    PRIESTS,
    oracle_actions,
)

Action = dict[str, Any]
ADJACENCY: dict[str, tuple[str, ...]] = {"P": ("A",), "A": ("P", "O"), "O": ("A", "J"), "J": ("O",)}
EDGE_OF = {frozenset({"P", "A"}): "P_A", frozenset({"A", "O"}): "A_O", frozenset({"O", "J"}): "O_J"}


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


def _walk(location: str, destination: str) -> list[Action]:
    path = _route(location, destination)
    return [
        {"tool": "move", "edge_id": EDGE_OF[frozenset({path[i], path[i + 1]})]}
        for i in range(len(path) - 1)
    ]


def _consistent_states(
    observation: dict[str, Any], cards: dict[str, Any]
) -> list[tuple[str, str]]:
    """按公开规则重算：谁的答案模式能解释全部已观察答复（+档案排除）。"""

    truth_sets = {claim: set(card["truth_set"]) for claim, card in cards.items()}
    answers = {row["claim_id"]: row["answer"] == "yes" for row in observation["question_answers"]}
    excluded = None
    archive = observation["archive_record_if_read"]
    if archive:
        excluded = archive["excluded"]
    consistent: list[tuple[str, str]] = []
    for config in observation["configurations"]:
        if config == excluded:
            continue
        for priest in PRIESTS:
            ok = True
            for claim, spoken in answers.items():
                truth = config in truth_sets[claim]
                speaker_matches = cards[claim]["speaker"] == priest_name(priest)
                expected = truth if speaker_matches else not truth
                if expected != spoken:
                    ok = False
                    break
            if ok:
                consistent.append((config, priest))
    return consistent


def priest_name(priest: str) -> str:
    return {"P0": "甲", "P1": "乙", "P2": "丙"}[priest]


class Map14Deduction:
    """公开启发式：读档案 → 信息增益式提问 → 封存 → 提交。"""

    name = "public_heuristic"
    #: 是否先读档案。
    read_archive = True
    #: 自设的提问上限（消融 `one_question` 用）。
    question_cap: int | None = None

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.cards: dict[str, Any] = {}

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        if observation["public_statement_cards"]:
            self.cards = observation["public_statement_cards"]
        if observation["gate_open"]:
            return {"tool": "submit_configuration", "choice": observation["configurations"][0]}
        if observation["wrong_submissions_remaining"] == 0:
            return {"tool": "submit_configuration", "choice": observation["configurations"][0]}
        # 1) 先读档案（不占提问预算，缩小候选）
        if self.read_archive and observation["archive_record_if_read"] is None:
            self.queue = _walk(location, "A")
            return self.queue.pop(0) if self.queue else {"tool": "read_archive"}
        # 题面只在 P 公开；需要选命题时先回 P
        if not self.cards:
            self.queue = _walk(location, "P")
            return self.queue.pop(0)
        states = _consistent_states(observation, self.cards)
        configs = sorted({config for config, _ in states})
        config: str | None = None
        can_ask = observation["questions_remaining"] > 0 and (
            self.question_cap is None or len(observation["question_answers"]) < self.question_cap
        )
        if len(configs) == 1 or not can_ask:
            config = configs[0] if configs else list(observation["configurations"])[0]
        else:
            asked = {row["claim_id"] for row in observation["question_answers"]}
            best: tuple[int, str] | None = None
            for claim, card in sorted(self.cards.items()):
                if claim in asked:
                    continue
                truth_set = set(card["truth_set"])
                yes = {item for item in configs if item in truth_set}
                no = set(configs) - yes
                if not yes or not no:
                    continue
                balance = abs(len(yes) - len(no))
                if best is None or balance < best[0]:
                    best = (balance, claim)
            if best is None:
                left = [claim for claim in sorted(self.cards) if claim not in asked]
                if left:
                    self.queue = _walk(location, "P")
                    return self.queue.pop(0) if self.queue else {
                        "tool": "ask",
                        "claim_id": left[0],
                    }
                config = configs[0]
            else:
                self.queue = _walk(location, "P")
                return self.queue.pop(0) if self.queue else {"tool": "ask", "claim_id": best[1]}
        assert config is not None
        priest = next((item for source, item in states if source == config), PRIESTS[0])
        sealed = observation["comparison_record"]
        if sealed is None or sealed["configuration_candidate"] != config:
            self.queue = _walk(location, "O")
            return self.queue.pop(0) if self.queue else {
                "tool": "compare_evidence",
                "choice": config,
                "person_id": priest,
                "support_evidence_ids": sorted(
                    {
                        *(row["evidence_id"] for row in observation["question_answers"]),
                        *(
                            ["ARCHIVE_EXCLUDE"]
                            if observation["archive_record_if_read"] is not None
                            else []
                        ),
                    }
                ),
            }
        self.queue = _walk(location, "J")
        return self.queue.pop(0) if self.queue else {
            "tool": "submit_configuration",
            "choice": config,
        }


class Map14BlindSubmissions:
    """不看证词，按顺序盲交锁型（V9 的旁路）。"""

    name = "blind_two_submissions"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        if observation["gate_open"]:
            return {"tool": "wait", "ticks": 1}
        tried = len(observation["question_answers"])
        del tried
        submitted = observation["wrong_submissions"]
        candidate = observation["configurations"][submitted % len(observation["configurations"])]
        self.queue = _walk(location, "J")
        return self.queue.pop(0) if self.queue else {
            "tool": "submit_configuration",
            "choice": candidate,
        }


class Map14NoSeal(Map14Deduction):
    """正确推理但不封存假设，直接提交（缺接口步骤）。"""

    name = "no_seal"

    def reset(self) -> None:
        super().reset()
        self.config: str | None = None

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        if self.config is not None:
            location = str(observation["location"])
            self.queue = _walk(location, "J")
            if self.queue:
                return self.queue.pop(0)
            return {"tool": "submit_configuration", "choice": self.config}
        payload = super().act(observation, history)
        if payload["tool"] == "compare_evidence":
            self.config = str(payload["choice"])
            location = str(observation["location"])
            self.queue = _walk(location, "J")
            return self.queue.pop(0)
        return payload


class Map14InconsistentSeal(Map14Deduction):
    """封存一个与已观察答复不相容的假设，再提交真值。"""

    name = "inconsistent_seal"

    def reset(self) -> None:
        super().reset()
        self.swapped = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = super().act(observation, history)
        if payload["tool"] == "compare_evidence" and not self.swapped:
            self.swapped = True
            wrong = next(
                config
                for config in observation["configurations"]
                if config != payload["choice"]
            )
            answers = observation["question_answers"]
            support = [answers[0]["evidence_id"]] if answers else []
            return {
                "tool": "compare_evidence",
                "choice": wrong,
                "person_id": PRIESTS[0],
                "support_evidence_ids": support,
            }
        return payload


class Map14WasteQuestions(Map14Deduction):
    """把所有命题都问一遍再推理（信息够但问数超标）。"""

    name = "waste_questions"

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.cards: dict[str, Any] = {}

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        location = str(observation["location"])
        if observation["public_statement_cards"]:
            self.cards = observation["public_statement_cards"]
        if observation["gate_open"]:
            return {"tool": "wait", "ticks": 1}
        asked = {row["claim_id"] for row in observation["question_answers"]}
        remaining = [claim for claim in sorted(self.cards) if claim not in asked]
        if remaining and observation["questions_remaining"] > 0:
            self.queue = _walk(location, "P")
            return self.queue.pop(0) if self.queue else {"tool": "ask", "claim_id": remaining[0]}
        states = _consistent_states(observation, self.cards)
        configs = sorted({config for config, _ in states})
        if not configs:
            return {"tool": "wait", "ticks": 1}
        config = configs[0]
        priest = next(priest for item, priest in states if item == config)
        sealed = observation["comparison_record"]
        if sealed is None or sealed["configuration_candidate"] != config:
            self.queue = _walk(location, "O")
            return self.queue.pop(0) if self.queue else {
                "tool": "compare_evidence",
                "choice": config,
                "person_id": priest,
                "support_evidence_ids": sorted(
                    row["evidence_id"] for row in observation["question_answers"]
                ),
            }
        self.queue = _walk(location, "J")
        return (
            self.queue.pop(0)
            if self.queue
            else {"tool": "submit_configuration", "choice": config}
        )


class Map14OneQuestion(Map14Deduction):
    """只问一条命题就封存提交（信息不足，只能靠运气）。"""

    name = "one_question"
    question_cap = 1


HEURISTIC = Map14Deduction
ABLATIONS: dict[str, type[Any]] = {
    "blind_two_submissions": Map14BlindSubmissions,
    "no_seal": Map14NoSeal,
    "one_question": Map14OneQuestion,
    "waste_questions": Map14WasteQuestions,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map14BlindSubmissions",
    "Map14Deduction",
    "Map14NoSeal",
    "Map14OneQuestion",
    "Map14WasteQuestions",
    "oracle_actions",
]
