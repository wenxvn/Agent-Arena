"""Offline, hand-trace-only audit for MAP-30; no runtime environment or LLM."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
NODES = {"H", "B", "K", "Y", "L", "A", "T", "J"}
EDGES = {frozenset(edge) for edge in (("H", "B"), ("B", "K"), ("K", "Y"), ("H", "L"), ("L", "A"), ("A", "T"), ("K", "T"), ("H", "J"))}
NODE_NPCS = {"A": "ARCHIVE_CLERK", "B": "BANQUET_CLERK", "K": "KITCHEN_COOK", "T": "TOWER_WATCH"}
NODE_EVIDENCE = {
    "A": {"Q4_ARCHIVE_DOCKET"},
    "B": {"B_KEY_STUB_2310"},
    "K": {"K_WAX_PLATE_2322"},
    "T": {"T_CHAIN_REGISTER_2340"},
}
ENTRY_ALLOWED = {
    "Q4_CODEBOOK": {"Q4_CODE_INDEX"},
    "EVENT_1_HANDOFF": {"B_KEY_STUB_2310", "B_WITNESS_HANDOFF"},
    "EVENT_2_WAX": {"K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE"},
    "EVENT_3_SIGNAL": {"T_CHAIN_REGISTER_2340", "T_WITNESS_SIGNAL_ROUTE"},
}
ENTRY_REQUIRED = {
    "Q4_CODEBOOK": {"Q4_CODE_INDEX"},
    "EVENT_1_HANDOFF": {"B_KEY_STUB_2310", "B_WITNESS_HANDOFF"},
    "EVENT_2_WAX": {"K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE"},
    "EVENT_3_SIGNAL": {"T_CHAIN_REGISTER_2340", "T_WITNESS_SIGNAL_ROUTE"},
}
ENTRY_ORDER = ["Q4_CODEBOOK", "EVENT_1_HANDOFF", "EVENT_2_WAX", "EVENT_3_SIGNAL"]
CLAIMS = [
    {"event_id": "EVENT_1_HANDOFF", "time": "23:10", "location": "B", "duty_code": "M4"},
    {"event_id": "EVENT_2_WAX", "time": "23:22", "location": "K", "duty_code": "M4"},
    {"event_id": "EVENT_3_SIGNAL", "time": "23:40", "location": "T", "duty_code": "M4"},
]
REQUIRED_CITATIONS = set(ENTRY_ORDER)


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_oracle(records: list[dict[str, Any]]) -> bytes:
    rows = [json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in records]
    return ("\n".join(rows) + "\n").encode("utf-8")


class CourtReplay:
    def __init__(self, evidence_catalog: dict[str, Any]):
        self.evidence_catalog = evidence_catalog
        self.tick = 0
        self.node = "H"
        self.casebook: dict[str, set[str]] = {}
        self.recent_events: list[dict[str, Any]] = []
        self.records: list[dict[str, Any]] = []
        self.seen_evidence: set[str] = set()
        self.npc_answers: list[dict[str, Any]] = []
        self.current_hypothesis: dict[str, Any] | None = None
        self.chain_reconciled = False
        self.unsupported_formal_accusations = 0
        self.terminal_reason: str | None = None
        self.last_result = "INITIAL"
        self.last_action: dict[str, Any] | None = None
        self.final_claim: dict[str, Any] | None = None
        self.q4_gap_observed = False
        self._record("INITIAL", None)

    def casebook_view(self) -> list[dict[str, Any]]:
        return [{"entry_id": key, "evidence_ids": sorted(ids)} for key, ids in self.casebook.items()]

    def observation(self) -> dict[str, Any]:
        neighbors = sorted(next(n for n in edge if n != self.node) for edge in EDGES if self.node in edge)
        recent = self.recent_events[-5:]
        if "Q4_CODE_INDEX" not in {e for event in recent for e in event.get("evidence_ids", [])} and "Q4_CODEBOOK" in self.casebook:
            self.q4_gap_observed = True
        return {
            "current_tick": self.tick,
            "current_node": self.node,
            "local_neighbors": neighbors,
            "public_alert": "MIDNIGHT_TRIAL_PENDING",
            "visible_local_evidence": sorted(NODE_EVIDENCE.get(self.node, set()) - self.seen_evidence),
            "recent_action_window": recent,
            "casebook": self.casebook_view(),
            "current_hypothesis": self.current_hypothesis,
            "unsupported_formal_accusations": self.unsupported_formal_accusations,
            "last_action_result": self.last_result,
            "terminal": self.terminal_reason is not None,
            "terminal_reason": self.terminal_reason,
        }

    def available_evidence(self) -> set[str]:
        recent_ids = {evidence_id for event in self.recent_events[-5:] for evidence_id in event.get("evidence_ids", [])}
        recorded_ids = {evidence_id for ids in self.casebook.values() for evidence_id in ids}
        return recent_ids | recorded_ids

    def _record(self, result: str, public_payload: dict[str, Any] | None) -> None:
        row = {
            "tick": self.tick,
            "action": self.last_action,
            "result": result,
            "public_payload": public_payload,
        }
        if public_payload:
            row["evidence_ids"] = list(public_payload.get("evidence_ids", []))
        if result != "INITIAL":
            self.recent_events.append(row)
        self.last_result = result
        self.records.append({"action": self.last_action, "result": result, "observation": self.observation()})

    def _advance(self, result: str, payload: dict[str, Any] | None = None) -> None:
        self.tick += 1
        if self.terminal_reason is None and self.tick >= 40:
            self.terminal_reason = "DEADLINE_REACHED"
            result = self.terminal_reason
        self._record(result, payload)

    def step(self, action: dict[str, Any]) -> None:
        if self.terminal_reason:
            raise AssertionError("action after terminal state")
        self.last_action = action
        name = action["name"]
        payload: dict[str, Any] | None = None
        result: str
        if name == "move":
            target = action["to"]
            assert target in NODES and frozenset((self.node, target)) in EDGES, (self.node, target)
            self.node = target
            result = "MOVE_SUCCEEDED"
        elif name == "inspect":
            evidence_id = action["evidence_id"]
            assert evidence_id in NODE_EVIDENCE.get(self.node, set()), (self.node, evidence_id)
            item = self.evidence_catalog[evidence_id]
            self.seen_evidence.add(evidence_id)
            payload = {
                "evidence_ids": [evidence_id],
                "evidence": [{"evidence_id": evidence_id, "source_class": item["source_class"], "fact": item["fact"], "rendered_text": item["answer_text"]}],
            }
            result = f"EVIDENCE_FOUND:{evidence_id}"
        elif name == "interview":
            npc_id = action["npc_id"]
            assert self.node == next(node for node, npc in NODE_NPCS.items() if npc == npc_id), (self.node, npc_id)
            shown_ids = set(action.get("shown_evidence_ids", []))
            shown_entries = set(action.get("shown_casebook_entry_ids", []))
            assert shown_ids.issubset(self.available_evidence()), (shown_ids, self.available_evidence())
            assert shown_entries.issubset(self.casebook), (shown_entries, self.casebook)
            answer = self._interview_answer(npc_id, shown_ids, shown_entries)
            self.seen_evidence.update(answer["evidence_ids"])
            self.npc_answers.append(answer)
            payload = {"evidence_ids": answer["evidence_ids"], "npc_answer": answer}
            result = f"ANSWER_RECEIVED:{answer['answer_id']}"
        elif name == "record":
            entry_id = action["entry_id"]
            evidence_ids = set(action["evidence_ids"])
            assert entry_id in ENTRY_ALLOWED and evidence_ids
            assert evidence_ids.issubset(self.available_evidence()), (entry_id, evidence_ids, self.available_evidence())
            assert evidence_ids.issubset(ENTRY_ALLOWED[entry_id]), (entry_id, evidence_ids)
            if entry_id not in self.casebook:
                assert len(self.casebook) < 4, "four typed evidence slots are full"
                self.casebook[entry_id] = set()
            self.casebook[entry_id].update(evidence_ids)
            result = f"ENTRY_RECORDED:{entry_id}"
            payload = {"entry_id": entry_id, "evidence_ids": sorted(evidence_ids)}
        elif name == "submit_intermediate_hypothesis":
            self.current_hypothesis = {key: value for key, value in action.items() if key != "name"}
            result = "HYPOTHESIS_RECORDED"
            payload = {"hypothesis": self.current_hypothesis}
        elif name == "compare_records":
            entry_ids = set(action["entry_ids"])
            assert entry_ids.issubset(self.casebook), (entry_ids, self.casebook)
            if "Q4_CODEBOOK" not in self.casebook or not ENTRY_REQUIRED["Q4_CODEBOOK"].issubset(self.casebook["Q4_CODEBOOK"]):
                result = "CODE_KEY_NOT_RECORDED"
            elif not REQUIRED_CITATIONS.issubset(entry_ids):
                result = "RECORDS_DO_NOT_ALIGN"
            elif all(entry in self.casebook and ENTRY_REQUIRED[entry].issubset(self.casebook[entry]) for entry in ENTRY_ORDER):
                self.chain_reconciled = True
                result = "CHAIN_COHERENT"
            else:
                result = "RECORDS_DO_NOT_ALIGN"
        elif name == "formal_accuse":
            assert self.node == "J"
            self.final_claim = {key: action[key] for key in ("person_id", "event_claims", "cited_entry_ids")}
            complete_case = (
                REQUIRED_CITATIONS.issubset(set(action["cited_entry_ids"]))
                and self.chain_reconciled
                and all(entry in self.casebook and ENTRY_REQUIRED[entry].issubset(self.casebook[entry]) for entry in ENTRY_ORDER)
            )
            accurate = action["person_id"] == "MARA_VENN" and action["event_claims"] == CLAIMS
            if complete_case and accurate:
                self.terminal_reason = "ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN"
                result = self.terminal_reason
            else:
                self.unsupported_formal_accusations += 1
                if self.unsupported_formal_accusations > 1:
                    self.terminal_reason = "ACCUSATION_LIMIT_EXCEEDED"
                    result = self.terminal_reason
                else:
                    result = "ACCUSATION_NOT_SUSTAINED"
        else:
            raise AssertionError(f"unknown hand-authored action: {name}")
        self._advance(result, payload)

    def _interview_answer(self, npc_id: str, shown_ids: set[str], shown_entries: set[str]) -> dict[str, Any]:
        table = self._npc_table
        if npc_id == "ARCHIVE_CLERK":
            key = "Q4_with_docket" if "Q4_ARCHIVE_DOCKET" in shown_ids else "Q4_without_docket"
        elif npc_id == "BANQUET_CLERK":
            key = "HANDOFF_with_stub" if "B_KEY_STUB_2310" in shown_ids else "HANDOFF_without_stub"
        elif npc_id == "KITCHEN_COOK":
            ready = "EVENT_1_HANDOFF" in shown_entries and ENTRY_REQUIRED["EVENT_1_HANDOFF"].issubset(self.casebook.get("EVENT_1_HANDOFF", set()))
            key = "WAX_with_event_1" if ready else "WAX_without_event_1"
        elif npc_id == "TOWER_WATCH":
            ready = "EVENT_2_WAX" in shown_entries and ENTRY_REQUIRED["EVENT_2_WAX"].issubset(self.casebook.get("EVENT_2_WAX", set()))
            key = "SIGNAL_with_event_2" if ready else "SIGNAL_without_event_2"
        else:
            raise AssertionError(npc_id)
        answer = table[npc_id][key]
        return {
            "npc_id": npc_id,
            "answer_id": answer["answer_id"],
            "evidence_ids": list(answer["evidence_ids"]),
            "rendered_text": answer["rendered_text"],
            "condition_key": key,
        }

    def run(self, actions: list[dict[str, Any]]) -> None:
        for action in actions:
            self.step(action)
        if not self.terminal_reason:
            self.final_claim = self.final_claim or {}

    def metrics(self) -> dict[str, Any]:
        final = self.final_claim or {}
        claims = final.get("event_claims", [])
        correct_count = sum(claim == expected for claim, expected in zip(claims, CLAIMS))
        parsed_times = [claim.get("time") for claim in claims]
        timeline_consistent = parsed_times == ["23:10", "23:22", "23:40"]
        evidence_ids = {evidence_id for ids in self.casebook.values() for evidence_id in ids}
        return {
            "finish_tick": self.tick,
            "success": self.terminal_reason == "ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN",
            "terminal_reason": self.terminal_reason,
            "unsupported_formal_accusations": self.unsupported_formal_accusations,
            "casebook_entry_count": len(self.casebook),
            "casebook_source_count": len(evidence_ids),
            "q4_recorded": "Q4_CODEBOOK" in self.casebook,
            "q4_recalled_after_gap": self.q4_gap_observed and "Q4_CODE_INDEX" in self.casebook.get("Q4_CODEBOOK", set()),
            "event_claim_accuracy": f"{correct_count}/3",
            "timeline_consistent": timeline_consistent,
            "comparison_succeeded": self.chain_reconciled,
            "npc_answer_ids": [answer["answer_id"] for answer in self.npc_answers],
            "npc_condition_keys": [answer["condition_key"] for answer in self.npc_answers],
            "action_rows": len(self.records) - 1,
        }


def audit() -> dict[str, Any]:
    spec = read_yaml(ROOT / "map_spec.yaml")
    rules = read_yaml(ROOT / "evidence_or_rules.yaml")
    hand = read_json(ROOT / "planning" / "hand_traces.json")
    failures = read_yaml(ROOT / "failure_traces" / "cases.yaml")
    seed = read_yaml(ROOT / "planning" / "seed_replay.yaml")
    for path in ROOT.rglob("*.yaml"):
        read_yaml(path)
    assert spec["status"] in {"DESIGN_IN_PROGRESS", "DESIGN_COMPLETE_PENDING_RUNTIME"}
    assert spec["initial_state"]["midnight_deadline_tick"] == 40
    assert spec["evidence_memory"]["casebook_capacity"] == len(ENTRY_ORDER) == 4
    assert spec["topology"]["undirected_edges"][-2]["a"] == "K" and spec["topology"]["undirected_edges"][-2]["b"] == "T"
    assert rules["required_order"] == ["EVENT_1_HANDOFF", "EVENT_2_WAX", "EVENT_3_SIGNAL"]
    assert rules["truth"]["EVENT_1_HANDOFF"]["time"] < rules["truth"]["EVENT_2_WAX"]["time"] < rules["truth"]["EVENT_3_SIGNAL"]["time"]
    assert rules["private_duty_code_index"] == {"M4": "MARA_VENN"}
    catalog = rules["evidence_catalog"]
    assert catalog["Q4_CODE_INDEX"]["fact"] == {"document_id": "Q4", "M4": "MARA_VENN"}
    for event_id, sources in {
        "EVENT_1_HANDOFF": ("B_KEY_STUB_2310", "B_WITNESS_HANDOFF"),
        "EVENT_2_WAX": ("K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE"),
        "EVENT_3_SIGNAL": ("T_CHAIN_REGISTER_2340", "T_WITNESS_SIGNAL_ROUTE"),
    }.items():
        true_event = rules["truth"][event_id]
        for source_id in sources:
            source_fact = catalog[source_id]["fact"]
            assert source_fact["time"] == true_event["time"] and source_fact.get("location", true_event["location"]) == true_event["location"]
            assert source_fact.get("duty_code", source_fact.get("signed_code")) == true_event["duty_code"]
    CourtReplay._npc_table = rules["npc_answer_tables"]
    assert set(catalog) == {"Q4_ARCHIVE_DOCKET", "Q4_CODE_INDEX", "B_KEY_STUB_2310", "B_WITNESS_HANDOFF", "K_WAX_PLATE_2322", "K_WITNESS_WAX_ROUTE", "T_CHAIN_REGISTER_2340", "T_WITNESS_SIGNAL_ROUTE"}
    assert rules["npc_answer_tables"]["KITCHEN_COOK"]["WAX_with_event_1"]["evidence_ids"] == ["K_WITNESS_WAX_ROUTE"]
    assert rules["npc_answer_tables"]["TOWER_WATCH"]["SIGNAL_with_event_2"]["evidence_ids"] == ["T_WITNESS_SIGNAL_ROUTE"]
    assert len(hand["routes"]) == 3
    assert {route["id"] for route in hand["routes"]} == {"event_by_event_archive_first", "physical_records_before_witness_round", "incremental_timeline_hypotheses"}

    route_summaries: dict[str, Any] = {}
    oracle: bytes | None = None
    for route in hand["routes"]:
        replay = CourtReplay(catalog)
        replay.run(route["actions"])
        metrics = replay.metrics()
        assert metrics["terminal_reason"] == route["expected"]["terminal_reason"], (route["id"], metrics)
        for field in ("finish_tick", "success", "unsupported_formal_accusations", "casebook_entry_count", "casebook_source_count", "q4_recalled_after_gap", "event_claim_accuracy", "timeline_consistent"):
            assert metrics[field] == route["expected"][field], (route["id"], field, metrics[field], route["expected"][field])
        assert metrics["comparison_succeeded"]
        if route["id"] == "event_by_event_archive_first":
            oracle = canonical_oracle(replay.records)
            assert len(oracle.splitlines()) == seed["expected_public_oracle_rows"]
            assert replay.q4_gap_observed
            public = oracle.decode("utf-8")
            for forbidden in ("private_truth", "MARA_VENN\"},\"private", "true_person", "private_duty_code_index"):
                assert forbidden not in public
            initial = json.loads(oracle.splitlines()[0])["observation"]
            assert initial["recent_action_window"] == [] and initial["casebook"] == []
            assert initial["visible_local_evidence"] == [] and b"MARA_VENN" not in oracle.splitlines()[0]
        if route["id"] == "physical_records_before_witness_round":
            assert "T_GENERIC_NIGHT_MEMORY" in metrics["npc_answer_ids"]
            assert "T_WITNESS_SIGNAL_ROUTE" in metrics["npc_answer_ids"]
        if route["id"] == "incremental_timeline_hypotheses":
            assert len([a for a in route["actions"] if a["name"] == "submit_intermediate_hypothesis"]) == route["expected"]["hypothesis_count"]
        route_summaries[route["id"]] = metrics

    assert oracle is not None
    oracle_digest = hashlib.sha256(oracle).hexdigest().upper()
    (ROOT / "oracle_trace.jsonl").write_bytes(oracle)
    second = CourtReplay(catalog)
    second.run(hand["routes"][0]["actions"])
    assert canonical_oracle(second.records) == oracle

    failure_summaries: dict[str, Any] = {}
    for case_id, case in failures["cases"].items():
        replay = CourtReplay(catalog)
        replay.run(case["actions"])
        metrics = replay.metrics()
        expected = case["expected"]
        for field in ("terminal_reason", "finish_tick", "unsupported_formal_accusations", "success"):
            assert metrics[field] == expected[field], (case_id, field, metrics, expected)
        for field in ("q4_recorded", "event_claim_accuracy", "timeline_consistent"):
            if field in expected:
                assert metrics[field] == expected[field], (case_id, field, metrics[field], expected[field])
        failure_summaries[case_id] = metrics

    # Exactly one unsupported filing is recoverable when a complete casebook is retained.
    recovery_actions = hand["routes"][0]["actions"][:-1]
    recovery = CourtReplay(catalog)
    recovery.run(recovery_actions)
    wrong = {"name": "formal_accuse", "person_id": "ORIN_VALE", "event_claims": CLAIMS, "cited_entry_ids": ENTRY_ORDER}
    recovery.step(wrong)
    assert recovery.last_result == "ACCUSATION_NOT_SUSTAINED" and recovery.unsupported_formal_accusations == 1
    recovery.step(hand["routes"][0]["actions"][-1])
    assert recovery.terminal_reason == "ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN" and recovery.tick == 26

    # An unrecorded source ages out; Q4 remains available through its append-only casebook entry.
    route_replay = CourtReplay(catalog)
    route_replay.run(hand["routes"][0]["actions"])
    assert "Q4_CODE_INDEX" not in {evidence_id for event in route_replay.recent_events[-5:] for evidence_id in event.get("evidence_ids", [])}
    assert "Q4_CODE_INDEX" in route_replay.casebook["Q4_CODEBOOK"] and route_replay.q4_gap_observed

    # Boundary fixture is a prepared legal state; the action at tick 39 may conclude successfully on tick 40.
    tick_40 = CourtReplay(catalog)
    tick_40.node = "J"
    tick_40.tick = 39
    tick_40.casebook = {entry: set(sources) for entry, sources in ENTRY_REQUIRED.items()}
    tick_40.chain_reconciled = True
    tick_40.step({"name": "formal_accuse", "person_id": "MARA_VENN", "event_claims": CLAIMS, "cited_entry_ids": ENTRY_ORDER})
    assert tick_40.tick == 40 and tick_40.terminal_reason == "ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN"
    deadline = CourtReplay(catalog)
    deadline.node = "H"
    deadline.tick = 39
    deadline.step({"name": "move", "to": "J"})
    assert deadline.tick == 40 and deadline.terminal_reason == "DEADLINE_REACHED"

    # The same K question has no exact information before the event-1 entry and a fixed answer after it is shown.
    conditional = CourtReplay(catalog)
    conditional.node = "K"
    conditional.step({"name": "interview", "npc_id": "KITCHEN_COOK", "topic_id": "WAX_ROUTE", "shown_casebook_entry_ids": []})
    weak_answer = conditional.npc_answers[-1]
    conditional.seen_evidence.add("B_KEY_STUB_2310")
    conditional.seen_evidence.add("B_WITNESS_HANDOFF")
    conditional.casebook["EVENT_1_HANDOFF"] = set(ENTRY_REQUIRED["EVENT_1_HANDOFF"])
    conditional.step({"name": "interview", "npc_id": "KITCHEN_COOK", "topic_id": "WAX_ROUTE", "shown_casebook_entry_ids": ["EVENT_1_HANDOFF"]})
    exact_answer = conditional.npc_answers[-1]
    assert weak_answer["answer_id"] == "K_GENERIC_OVEN_MEMORY" and exact_answer["answer_id"] == "K_WITNESS_WAX_ROUTE"
    before_repeat = dict(exact_answer)
    conditional.step({"name": "interview", "npc_id": "KITCHEN_COOK", "topic_id": "WAX_ROUTE", "shown_casebook_entry_ids": ["EVENT_1_HANDOFF"]})
    assert conditional.npc_answers[-1] == before_repeat

    # Every authored route and failure ends before the hearing boundary unless intended otherwise.
    assert all(m["finish_tick"] < 40 for m in list(route_summaries.values()) + list(failure_summaries.values()))
    reference = {
        "map_id": "MAP-30",
        "result": "MAP30_LONG_GAP_EVIDENCE_CHAIN_AND_CAUTION_REPLAYED",
        "runtime_verified": False,
        "routes": route_summaries,
        "failures": failure_summaries,
        "wrong_filing_recovery": {"unsupported_formal_accusations_before_success": 1, "finish_tick": recovery.tick, "success": True},
        "tick_40_boundary": {"correct_final_action_at_tick_39": tick_40.terminal_reason, "finish_tick": tick_40.tick, "unresolved_at_tick_40": deadline.terminal_reason},
        "conditional_interview": {"before": weak_answer["answer_id"], "after": exact_answer["answer_id"], "same_state_repeat_fixed": True},
        "oracle_rows": len(oracle.splitlines()),
        "oracle_sha256": oracle_digest,
        "seed0_double_replay_byte_identical": True,
    }
    (ROOT / "planning" / "map30_reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return reference


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
