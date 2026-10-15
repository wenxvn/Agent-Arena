"""Hand-authored deterministic query and testimony audit for MAP-29; no LLM or runtime environment."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
NODES = {"H", "L", "K", "Y", "G"}
EDGES = {frozenset(pair) for pair in (("H", "L"), ("H", "K"), ("H", "Y"), ("H", "G"))}
TRUTH = {"event_time": "23:40", "event_location": "Y"}
NPC_LOCATIONS = {"A": "L", "B": "K", "C": "Y", "D": "G"}
UNRELIABILITY_PROOF = {
    "A": {"A_TIME_CLAIM_0005", "A_TIME_BASIS_STOPPED_0000", "STUDY_CLOCK_STOPPED_0000", "ARCHIVE_EVENT_2340_Y"},
    "B": {"B_LOCATION_CLAIM_L", "ARCHIVE_EVENT_2340_Y", "YARD_BELL_MARK_2340"},
}
FIXED_ANSWERS: dict[tuple[str, str], dict[str, Any]] = {
    ("A", "OPEN_ACCOUNT"): {"answer_id": "A_OPEN_ACCOUNT", "evidence_ids": ["A_TIME_CLAIM_0005", "A_LOCATION_CLAIM_Y"], "payload": {"event_time_claim": "00:05", "event_location_claim": "Y"}, "rendered_text": "我记得铃在00:05响，声源方向像是庭院。"},
    ("A", "TIME_BASIS"): {"answer_id": "A_TIME_BASIS", "evidence_ids": ["A_TIME_BASIS_STOPPED_0000"], "payload": {"basis": "study_clock_stopped_at_00_00"}, "rendered_text": "我看的是书房那只钟；后来才发现它停在00:00。"},
    ("B", "OPEN_ACCOUNT"): {"answer_id": "B_OPEN_ACCOUNT", "evidence_ids": ["B_TIME_CLAIM_2340", "B_LOCATION_CLAIM_L"], "payload": {"event_time_claim": "23:40", "event_location_claim": "L"}, "rendered_text": "那声铃大约在23:40，我记得是在书房L。"},
    ("B", "LOCATION_BASIS"): {"answer_id": "B_LOCATION_BASIS", "evidence_ids": ["B_LOCATION_CLAIM_L"], "payload": {"repeated_location_claim": "L"}, "rendered_text": "我还是坚持说是在书房L。"},
    ("C", "OPEN_ACCOUNT"): {"answer_id": "C_SOUND_ONLY", "evidence_ids": ["C_SOUND_ONLY"], "payload": {"event_time_claim": "UNKNOWN", "event_location_claim": "UNKNOWN", "sound_pattern": "DOUBLE_LOW_HIGH"}, "rendered_text": "我只听见两声低高音；不知道准确时间，也不知道从哪间房传来。"},
    ("C", "SOUND_PATTERN"): {"answer_id": "C_SOUND_ONLY", "evidence_ids": ["C_SOUND_ONLY"], "payload": {"sound_pattern": "DOUBLE_LOW_HIGH"}, "rendered_text": "听起来是低音后接高音的双响。"},
    ("D", "OPEN_ACCOUNT"): {"answer_id": "D_ARCHIVE_EXISTS", "evidence_ids": ["D_ARCHIVE_EXISTS"], "payload": {"archive_exists": True}, "rendered_text": "守门铃事件簿保存在我这里，但要查索引才能定位那一条。"},
    ("D", "ARCHIVE_CROSS_INDEX"): {"answer_id": "ARCHIVE_EVENT_2340_Y", "evidence_ids": ["ARCHIVE_EVENT_2340_Y"], "payload": {"event_time": "23:40", "event_location": "Y"}, "rendered_text": "交叉索引记载：23:40，庭院Y银铃撞击一次。"},
}
DEFAULT_ANSWERS = {
    "A": {"answer_id": "A_NO_ADDITIONAL_KNOWLEDGE", "evidence_ids": [], "payload": {"scope": "no_additional_knowledge"}, "rendered_text": "我没有其他可补充的事实。"},
    "B": {"answer_id": "B_NO_ADDITIONAL_KNOWLEDGE", "evidence_ids": [], "payload": {"scope": "no_additional_knowledge"}, "rendered_text": "我没有其他可补充的事实。"},
    "C": {"answer_id": "C_NO_ADDITIONAL_KNOWLEDGE", "evidence_ids": [], "payload": {"scope": "no_additional_knowledge"}, "rendered_text": "我不知道更多。"},
    "D": {"answer_id": "D_NO_ADDITIONAL_KNOWLEDGE", "evidence_ids": [], "payload": {"scope": "no_additional_knowledge"}, "rendered_text": "档案里没有这类索引。"},
}


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class WitnessReplay:
    def __init__(self):
        self.tick = 0
        self.node = "H"
        self.questions_remaining = 8
        self.questions_used = 0
        self.question_calls: Counter[tuple[str, str]] = Counter()
        self.heard_answer_ids: list[str] = []
        self.heard_answers: list[dict[str, Any]] = []
        self.known_evidence: set[str] = set()
        self.physical_evidence: set[str] = set()
        self.physical_payloads: dict[str, str] = {}
        self.comparisons: dict[str, str] = {}
        self.last_result = "INITIAL"
        self.terminal_reason: str | None = None
        self.private_judge_reason: str | None = None
        self.final_claim: dict[str, Any] | None = None
        self.factual_correct_fields = 0
        self.unique_information_ids: set[str] = set()
        self.redundant_questions = 0
        self.records: list[dict[str, Any]] = []
        self.last_action: dict[str, Any] | None = None
        self._record("INITIAL")

    def observation(self) -> dict[str, Any]:
        neighbors = sorted(next(n for n in edge if n != self.node) for edge in EDGES if self.node in edge)
        return {
            "current_tick": self.tick,
            "current_node": self.node,
            "local_neighbors": neighbors,
            "public_alert": "BELL_EVENT_REPORTED",
            "questions_remaining": self.questions_remaining,
            "questions_used": self.questions_used,
            "heard_answers_with_source_ids": list(self.heard_answers),
            "physical_evidence_seen": [
                {"evidence_id": evidence_id, "source_class": "physical_trace", "fact": fact}
                for evidence_id, fact in sorted(self.physical_payloads.items())
            ],
            "comparison_results": dict(sorted(self.comparisons.items())),
            "last_action_result": self.last_result,
            "terminal": self.terminal_reason is not None,
            "terminal_reason": self.terminal_reason,
        }

    def _record(self, result: str) -> None:
        self.records.append({"action": self.last_action, "result": result, "observation": self.observation()})

    def step(self, action: dict[str, Any]) -> None:
        if self.terminal_reason:
            raise AssertionError("action after terminal submission")
        self.last_action = action
        name = action["name"]
        duration = 0
        if name == "move":
            target = action["to"]
            assert target in NODES and frozenset((self.node, target)) in EDGES
            self.node = target
            duration = 1
            result = "MOVE_SUCCEEDED"
        elif name == "ask":
            npc, template = action["npc_id"], action["question_template_id"]
            assert npc in NPC_LOCATIONS and self.node == NPC_LOCATIONS[npc]
            if template not in {"OPEN_ACCOUNT", "TIME_BASIS", "LOCATION_BASIS", "ARCHIVE_CROSS_INDEX", "SOUND_PATTERN"}:
                result = "INVALID_QUESTION_TEMPLATE"
            elif self.questions_remaining == 0:
                result = "QUESTION_BUDGET_EXHAUSTED"
            else:
                key = (npc, template)
                answer = FIXED_ANSWERS.get(key, DEFAULT_ANSWERS[npc])
                self.questions_remaining -= 1
                self.questions_used += 1
                self.question_calls[key] += 1
                duration = 1
                if self.question_calls[key] > 1:
                    self.redundant_questions += 1
                answer_id = answer["answer_id"]
                if answer_id in self.heard_answer_ids:
                    pass
                else:
                    self.heard_answer_ids.append(answer_id)
                    self.unique_information_ids.update(answer["evidence_ids"])
                self.known_evidence.update(answer["evidence_ids"])
                self.heard_answers.append({
                    "npc_id": npc,
                    "question_template_id": template,
                    "answer_id": answer_id,
                    "source_evidence_ids": list(answer["evidence_ids"]),
                    "typed_payload": answer["payload"],
                    "rendered_text": answer["rendered_text"],
                })
                result = f"ANSWER_RECEIVED:{answer_id}"
        elif name == "investigate":
            target = action["target_id"]
            expected_location = {"study_clock": "L", "courtyard_bell_trace": "Y"}[target]
            assert self.node == expected_location
            evidence_id = {"study_clock": "STUDY_CLOCK_STOPPED_0000", "courtyard_bell_trace": "YARD_BELL_MARK_2340"}[target]
            fact = {"study_clock": "study_clock_stopped_at_00_00", "courtyard_bell_trace": "courtyard_bell_marked_single_strike_at_23_40"}[target]
            self.physical_evidence.add(evidence_id)
            self.physical_payloads[evidence_id] = fact
            self.known_evidence.add(evidence_id)
            self.unique_information_ids.add(evidence_id)
            duration = 1
            result = f"EVIDENCE_FOUND:{evidence_id}"
        elif name == "compare_testimony":
            npc = action["npc_id"]
            statement_ids = set(action["statement_ids"])
            evidence_ids = set(action["against_evidence_ids"])
            assert statement_ids.issubset(self.known_evidence) and evidence_ids.issubset(self.known_evidence)
            if npc == "A" and {"A_TIME_CLAIM_0005", "A_TIME_BASIS_STOPPED_0000"}.issubset(statement_ids) and {"STUDY_CLOCK_STOPPED_0000", "ARCHIVE_EVENT_2340_Y"}.issubset(evidence_ids):
                result = "TIME_CLAIM_CONTRADICTED_AND_EXPLAINED"
                self.comparisons["A"] = result
            elif npc == "B" and "B_LOCATION_CLAIM_L" in statement_ids and {"ARCHIVE_EVENT_2340_Y", "YARD_BELL_MARK_2340"}.issubset(evidence_ids):
                result = "LOCATION_CLAIM_CONTRADICTED"
                self.comparisons["B"] = result
            elif npc == "C" and "C_SOUND_ONLY" in statement_ids:
                result = "KNOWLEDGE_LIMIT_NOT_UNRELIABILITY"
            elif npc == "D" and "ARCHIVE_EVENT_2340_Y" in evidence_ids and "YARD_BELL_MARK_2340" in evidence_ids:
                result = "ARCHIVE_MATCHES_PHYSICAL_EVIDENCE"
            else:
                result = "COMPARE_INSUFFICIENT_EVIDENCE"
            duration = 1
        elif name == "submit":
            self._submit(action)
            return
        else:
            raise AssertionError(f"unknown hand-authored action: {name}")
        self.tick += duration
        self.last_result = result
        self._record(result)

    def _submit(self, action: dict[str, Any]) -> None:
        assert self.node == "H"
        self.final_claim = {key: action[key] for key in ("event_time", "event_location", "unreliable_npc_id")}
        self.factual_correct_fields = sum((action["event_time"] == TRUTH["event_time"], action["event_location"] == TRUTH["event_location"]))
        required_support = {"ARCHIVE_EVENT_2340_Y", "YARD_BELL_MARK_2340"}
        support_ids = set(action.get("support_ids", []))
        proof_ids = set(action.get("unreliability_proof_ids", []))
        time_location_supported = required_support.issubset(support_ids & self.known_evidence)
        npc = action["unreliable_npc_id"]
        required_proof = UNRELIABILITY_PROOF.get(npc, set())
        unreliability_proven = bool(required_proof) and npc in self.comparisons and required_proof.issubset(proof_ids & self.known_evidence)
        if action["event_time"] != TRUTH["event_time"]:
            self.private_judge_reason = "WRONG_EVENT_TIME"
        elif action["event_location"] != TRUTH["event_location"]:
            self.private_judge_reason = "WRONG_EVENT_LOCATION"
        elif not unreliability_proven:
            self.private_judge_reason = "NO_PROVEN_UNRELIABLE_WITNESS"
        elif not time_location_supported:
            self.private_judge_reason = "MISSING_INDEPENDENT_EVENT_SUPPORT"
        else:
            self.private_judge_reason = "ACCEPTED"
        success = self.private_judge_reason == "ACCEPTED"
        self.terminal_reason = "ALL_OBJECTIVES_COMPLETE" if success else "CASE_REJECTED"
        self.tick += 1
        self.last_result = self.terminal_reason
        self._record(self.last_result)

    def run(self, actions: list[dict[str, Any]]) -> None:
        for action in actions:
            self.step(action)

    def metrics(self) -> dict[str, Any]:
        correct = self.factual_correct_fields
        reliability_proven = bool(self.final_claim and self.final_claim["unreliable_npc_id"] in self.comparisons)
        success = self.private_judge_reason == "ACCEPTED"
        supported_fields = correct + int(reliability_proven)
        return {
            "finish_tick": self.tick,
            "terminal_reason": self.terminal_reason,
            "private_judge_reason": self.private_judge_reason,
            "success": success,
            "questions_used": self.questions_used,
            "questions_remaining": self.questions_remaining,
            "repeated_question_count": self.redundant_questions,
            "unique_answer_count": len(self.heard_answer_ids),
            "useful_information_gain": len(self.unique_information_ids),
            "supported_event_fields": f"{correct}/2",
            "unreliable_witness_proven": reliability_proven,
            "question_efficiency": f"{supported_fields}/{self.questions_used}" if self.questions_used else f"{supported_fields}/0",
            "wasted_or_redundant_question_rate": self.redundant_questions / self.questions_used if self.questions_used else 0.0,
            "comparison_results": dict(sorted(self.comparisons.items())),
            "physical_evidence_seen": sorted(self.physical_evidence),
            "conclusion_accuracy": f"{correct}/2",
            "action_rows": len(self.records) - 1,
        }


def oracle_bytes(records: list[dict[str, Any]]) -> bytes:
    rows = [json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in records]
    return ("\n".join(rows) + "\n").encode("utf-8")


def audit() -> dict[str, Any]:
    spec = read_yaml(ROOT / "map_spec.yaml")
    answers = read_yaml(ROOT / "planning" / "private_answer_tables.yaml")
    evidence = read_yaml(ROOT / "evidence_or_rules.yaml")
    hand = read_json(ROOT / "planning" / "hand_traces.json")
    failures = read_yaml(ROOT / "failure_traces" / "cases.yaml")
    seed = read_yaml(ROOT / "planning" / "seed_replay.yaml")
    assert spec["status"] in {"DESIGN_IN_PROGRESS", "DESIGN_COMPLETE_PENDING_RUNTIME"}
    assert spec["initial_state"]["questions_remaining"] == 8
    assert set(NPC_LOCATIONS) == set(answers["npcs"]) == {"A", "B", "C", "D"}
    assert answers["truth"] == TRUTH
    rendered_by_pair = {
        (npc_id, template_id): answer["rendered_text"]
        for npc_id, npc in answers["npcs"].items()
        for template_id, answer in npc["answers"].items()
    }
    for key, answer in FIXED_ANSWERS.items():
        assert rendered_by_pair[key] == answer["rendered_text"], (key, rendered_by_pair[key], answer["rendered_text"])
    assert set(failures["boundaries"]) == {"B01_eighth_and_ninth_question", "B02_repeated_question_is_not_new_evidence",
                                             "B03_physical_inspection_is_not_a_question", "B04_stopped_clock_only_explains_bias",
                                             "B05_testimony_does_not_mutate_physical_record", "B06_seed0_answer_replay"}
    assert evidence["evidence_catalog"]["YARD_BELL_MARK_2340"]["class"] == "physical_trace"
    assert evidence["evidence_catalog"]["ARCHIVE_EVENT_2340_Y"]["class"] == "documentary_record"

    routes = {}
    public_oracle: bytes | None = None
    for route in hand["routes"]:
        replay = WitnessReplay()
        replay.run(route["actions"])
        metrics = replay.metrics()
        expected = route["expected"]
        for field in ("finish_tick", "questions_used", "questions_remaining", "success", "event_time", "event_location", "unreliable_npc_id", "question_efficiency"):
            if field in {"event_time", "event_location", "unreliable_npc_id"}:
                actual = replay.final_claim[field]
            else:
                actual = metrics[field]
            assert actual == expected[field], (route["id"], field, actual, expected[field])
        assert metrics["success"] and replay.comparisons.get("A") == "TIME_CLAIM_CONTRADICTED_AND_EXPLAINED"
        routes[route["id"]] = metrics
        if route["id"] == "high_information_first":
            public_oracle = oracle_bytes(replay.records)

    assert public_oracle is not None
    second = WitnessReplay()
    second.run(hand["routes"][1]["actions"])
    assert oracle_bytes(second.records) == public_oracle
    (ROOT / "oracle_trace.jsonl").write_bytes(public_oracle)

    failure_summaries = {}
    for case_id, case in failures["cases"].items():
        replay = WitnessReplay()
        replay.run(case["actions"])
        metrics = replay.metrics()
        expected = case["expected"]
        for field, expected_field in (("terminal_reason", "terminal_reason"), ("private_judge_reason", "judge_reason"),
                                      ("finish_tick", "finish_tick"), ("questions_used", "questions_used"),
                                      ("conclusion_accuracy", "factual_accuracy")):
            assert metrics[field] == expected[expected_field], (case_id, field, metrics, expected)
        failure_summaries[case_id] = metrics

    # Eight valid repeated queries preserve the answer; a ninth attempt changes neither tick nor budget.
    budget = WitnessReplay()
    budget.node = "L"
    for _ in range(8):
        budget.step({"name": "ask", "npc_id": "A", "question_template_id": "OPEN_ACCOUNT"})
    assert budget.questions_remaining == 0 and budget.questions_used == 8
    assert len(set(budget.heard_answer_ids)) == 1 and budget.redundant_questions == 7
    assert len(budget.heard_answers) == 8 and all(answer == budget.heard_answers[0] for answer in budget.heard_answers)
    before = (budget.tick, budget.questions_used)
    budget.step({"name": "ask", "npc_id": "A", "question_template_id": "OPEN_ACCOUNT"})
    assert budget.records[-1]["result"] == "QUESTION_BUDGET_EXHAUSTED"
    assert (budget.tick, budget.questions_used) == before

    # A lie cannot alter the courtyard physical record; physical inspection consumes time but no question.
    contradiction = WitnessReplay()
    contradiction.node = "K"
    contradiction.step({"name": "ask", "npc_id": "B", "question_template_id": "OPEN_ACCOUNT"})
    contradiction.node = "Y"
    q_before = contradiction.questions_used
    contradiction.step({"name": "investigate", "target_id": "courtyard_bell_trace"})
    assert contradiction.questions_used == q_before and "YARD_BELL_MARK_2340" in contradiction.physical_evidence
    assert contradiction.known_evidence.intersection({"B_LOCATION_CLAIM_L", "YARD_BELL_MARK_2340"}) == {"B_LOCATION_CLAIM_L", "YARD_BELL_MARK_2340"}
    assert evidence["evidence_catalog"]["STUDY_CLOCK_STOPPED_0000"]["supports"].get("event_time") is None

    assert seed["seed"] == hand["seed"] == 0
    assert len(public_oracle.splitlines()) == len(hand["routes"][1]["actions"]) + 1
    initial = json.loads(public_oracle.splitlines()[0])["observation"]
    assert initial["questions_remaining"] == 8 and initial["heard_answers_with_source_ids"] == []
    final_observation = json.loads(public_oracle.splitlines()[-2])["observation"]
    assert any(answer["rendered_text"].startswith("交叉索引记载") for answer in final_observation["heard_answers_with_source_ids"])
    assert any(item["fact"] == "courtyard_bell_marked_single_strike_at_23_40" for item in final_observation["physical_evidence_seen"])
    for forbidden in ("private_answer_tables", "true_event_time", "private_judge_reason"):
        assert forbidden not in public_oracle.decode("utf-8")

    reference = {
        "map_id": "MAP-29",
        "result": "MAP29_DETERMINISTIC_QUERY_SELECTION_AND_SOURCE_COMPARISON_REPLAYED",
        "runtime_verified": False,
        "routes": routes,
        "failures": failure_summaries,
        "question_budget_boundary": {"valid_eighth": budget.questions_used, "remaining_after_eighth": budget.questions_remaining, "ninth": "QUESTION_BUDGET_EXHAUSTED_NO_COST"},
        "repeated_same_question": {"calls": 8, "unique_answer_ids": len(set(budget.heard_answer_ids)), "repeated_question_count": budget.redundant_questions, "all_payloads_fixed": True},
        "physical_record_unchanged_after_B_claim": "YARD_BELL_MARK_2340",
        "oracle_rows": len(public_oracle.splitlines()),
        "oracle_sha256": hashlib.sha256(public_oracle).hexdigest().upper(),
    }
    (ROOT / "planning" / "map29_reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return reference


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
