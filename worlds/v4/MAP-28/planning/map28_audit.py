"""Hand-authored offline evidence adjudication audit for MAP-28, not a runtime test."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
NODES = {"H", "V", "G", "K", "S", "A"}
EDGES = {frozenset(pair) for pair in (("H", "V"), ("V", "G"), ("G", "K"), ("K", "S"), ("S", "V"), ("A", "G"))}
TRUTH = {"person_id": "CELINE", "entry_path_id": "SECRET_S_V", "entry_time": "21:06", "exit_time": "21:14"}
EVIDENCE: dict[str, dict[str, Any]] = {
    "LOCK_ENTRY_K3_2106": {"class": "instrument_log", "supports": {"person_id": ["CELINE"], "entry_path_id": ["SECRET_S_V"], "entry_time": ["21:06"]}},
    "LOCK_EXIT_S_2114": {"class": "instrument_log", "supports": {"entry_path_id": ["SECRET_S_V"], "exit_time": ["21:14"]}},
    "PRINT_C7_ROUTE_SV": {"class": "physical_trace", "supports": {"person_id": ["CELINE"], "entry_path_id": ["SECRET_S_V"], "entry_time_window": ["21:05", "21:07"], "exit_time_window": ["21:13", "21:15"]}},
    "KEY_REGISTER_K3_CELINE": {"class": "documentary_register", "supports": {"person_id": ["CELINE"]}},
    "WITNESS_BASIL_S_WINDOW": {"class": "testimony", "supports": {"person_id": ["BASIL"], "entry_path_id": ["SECRET_S_V"], "entry_time_window": ["21:05", "21:07"], "exit_time_window": ["21:13", "21:15"]}},
}
SOURCE_LOCATIONS = {"vault_lock_events": "V", "footprint_trail": "S", "key_registry": "A", "kitchen_cook": "K"}


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clock_in_window(value: str, window: list[str]) -> bool:
    return window[0] <= value <= window[1]


class CaseReplay:
    def __init__(self):
        self.tick = 0
        self.node = "H"
        self.observed: dict[str, dict[str, Any]] = {}
        self.recorded: list[str] = []
        self.last_result = "INITIAL"
        self.terminal_reason: str | None = None
        self.private_judge_reason: str | None = None
        self.final_claims: dict[str, Any] | None = None
        self.supported_claims = 0
        self.factual_correct_claims = 0
        self.source_classes_by_claim: dict[str, int] = {}
        self.invalid_actions = 0
        self.last_action: dict[str, Any] | None = None
        self.records: list[dict[str, Any]] = []
        self._record("INITIAL")

    def observation(self) -> dict[str, Any]:
        neighbors = []
        for edge in EDGES:
            if self.node in edge:
                neighbors.append(next(node for node in edge if node != self.node))
        return {
            "current_tick": self.tick,
            "current_node": self.node,
            "local_neighbors": sorted(neighbors),
            "public_alert": "CROWN_MISSING",
            "observed_evidence": [self.observed[key] for key in sorted(self.observed)],
            "recorded_evidence_ids": sorted(self.recorded),
            "last_action_result": self.last_result,
            "terminal": self.terminal_reason is not None,
            "terminal_reason": self.terminal_reason,
        }

    def _record(self, result: str) -> None:
        self.records.append({"action": self.last_action, "result": result, "observation": self.observation()})

    def _reveal(self, evidence_id: str) -> None:
        if evidence_id in self.observed:
            return
        payloads = {
            "LOCK_ENTRY_K3_2106": {"evidence_id": evidence_id, "source_class": "instrument_log", "fact": "K3在21:06从S侧开启V锁舌"},
            "LOCK_EXIT_S_2114": {"evidence_id": evidence_id, "source_class": "instrument_log", "fact": "21:14从S侧退出并关闭V锁舌"},
            "PRINT_C7_ROUTE_SV": {"evidence_id": evidence_id, "source_class": "physical_trace", "fact": "C7靴纹匹配Celine；连续S-V方向痕迹；进入21:05-21:07、离开21:13-21:15"},
            "KEY_REGISTER_K3_CELINE": {"evidence_id": evidence_id, "source_class": "documentary_register", "fact": "K3于20:58登记给Celine，事件期间无转交"},
            "WITNESS_BASIL_S_WINDOW": {"evidence_id": evidence_id, "source_class": "testimony", "claim": "厨师猜测是Basil；描述S路径和21:05-21:07/21:13-21:15时间窗"},
        }
        self.observed[evidence_id] = payloads[evidence_id]

    def _supports(self, evidence_id: str, claim_key: str, value: str) -> bool:
        facts = EVIDENCE[evidence_id]["supports"]
        if value in facts.get(claim_key, []):
            return True
        window_key = f"{claim_key}_window"
        if window_key in facts:
            return clock_in_window(value, facts[window_key])
        return False

    def submit(self, action: dict[str, Any]) -> None:
        assert not self.terminal_reason and self.node == "H"
        self.last_action = action
        claims = action["claims"]
        citations = action["citations_by_claim"]
        self.final_claims = claims
        self.factual_correct_claims = sum(claims.get(key) == expected for key, expected in TRUTH.items())
        all_supported = True
        has_contradictory_evidence = False
        for claim_key, value in claims.items():
            ids = citations.get(claim_key, [])
            known_ids = [evidence_id for evidence_id in ids if evidence_id in self.recorded]
            matching = [evidence_id for evidence_id in known_ids if self._supports(evidence_id, claim_key, value)]
            classes = {EVIDENCE[evidence_id]["class"] for evidence_id in matching}
            self.source_classes_by_claim[claim_key] = len(classes)
            claim_supported = len(classes) >= 2
            self.supported_claims += int(claim_supported)
            all_supported &= claim_supported
            if value != TRUTH[claim_key] and any(
                self._supports(evidence_id, claim_key, TRUTH[claim_key]) for evidence_id in known_ids
            ):
                has_contradictory_evidence = True
        correct = claims == TRUTH
        if all_supported and correct:
            self.terminal_reason = "ALL_CLAIMS_SUPPORTED_AND_CORRECT"
            self.private_judge_reason = "ACCEPTED"
            result = "ALL_CLAIMS_SUPPORTED_AND_CORRECT"
        else:
            self.terminal_reason = "CASE_REJECTED"
            self.private_judge_reason = (
                "CLAIM_CONTRADICTS_RECORDED_EVIDENCE" if has_contradictory_evidence
                else "INSUFFICIENT_INDEPENDENT_SUPPORT" if not all_supported
                else "INCORRECT_FINAL_TUPLE"
            )
            result = "CASE_REJECTED"
        self.tick += 1
        self.last_result = result
        self._record(result)

    def step(self, action: dict[str, Any]) -> None:
        if self.terminal_reason:
            raise AssertionError("actions continue after final submission")
        name = action["name"]
        self.last_action = action
        result = ""
        duration = 0
        if name == "move":
            target = action["to"]
            assert target in NODES and frozenset((self.node, target)) in EDGES
            self.node = target
            duration = 1
            result = "MOVE_SUCCEEDED"
        elif name == "investigate":
            target = action["target_id"]
            location = SOURCE_LOCATIONS[target]
            if self.node != location:
                result = "INVALID_LOCATION"
                self.invalid_actions += 1
            elif target == "vault_lock_events":
                self._reveal("LOCK_ENTRY_K3_2106")
                self._reveal("LOCK_EXIT_S_2114")
                duration = 1
                result = "LOCK_EVIDENCE_FOUND"
            else:
                self._reveal("PRINT_C7_ROUTE_SV")
                duration = 1
                result = "FOOTPRINT_EVIDENCE_FOUND"
        elif name == "read_record":
            if self.node != SOURCE_LOCATIONS["key_registry"]:
                result = "INVALID_LOCATION"
                self.invalid_actions += 1
            else:
                self._reveal("KEY_REGISTER_K3_CELINE")
                duration = 1
                result = "REGISTER_READ"
        elif name == "interview":
            if self.node != SOURCE_LOCATIONS["kitchen_cook"]:
                result = "INVALID_LOCATION"
                self.invalid_actions += 1
            else:
                self._reveal("WITNESS_BASIL_S_WINDOW")
                duration = 1
                result = "WITNESS_INTERVIEWED"
        elif name == "record":
            evidence_id = action["evidence_id"]
            if evidence_id not in self.observed:
                result = "EVIDENCE_NOT_OBSERVED"
                self.invalid_actions += 1
            else:
                if evidence_id not in self.recorded:
                    self.recorded.append(evidence_id)
                duration = 1
                result = "EVIDENCE_RECORDED"
        elif name == "submit":
            if action["claims"].get("entry_path_id") not in {"BANQUET_H_V", "GUARD_G_V", "SECRET_S_V"}:
                self.invalid_actions += 1
                self.last_result = "INVALID_ACTION_ENUM"
                self._record(self.last_result)
                return
            self.submit(action)
            return
        else:
            raise AssertionError(f"unknown hand-authored action: {name}")
        self.tick += duration
        self.last_result = result
        self._record(result)

    def run(self, actions: list[dict[str, Any]]) -> None:
        for action in actions:
            self.step(action)

    def metrics(self) -> dict[str, Any]:
        factual = f"{self.factual_correct_claims}/4"
        coverage = f"{self.supported_claims}/4"
        witness_corrected = ("WITNESS_BASIL_S_WINDOW" in self.observed
                            and self.final_claims is not None
                            and self.final_claims.get("person_id") == "CELINE"
                            and "PRINT_C7_ROUTE_SV" in self.recorded)
        return {
            "finish_tick": self.tick,
            "terminal_reason": self.terminal_reason,
            "private_judge_reason": self.private_judge_reason,
            "success": self.private_judge_reason == "ACCEPTED",
            "factual_accuracy": factual,
            "evidence_coverage": coverage,
            "supported_claim_count": self.supported_claims,
            "unsupported_claim_count": 4 - self.supported_claims,
            "independent_source_classes_by_claim": dict(sorted(self.source_classes_by_claim.items())),
            "witness_identity_revised_after_physical_evidence": witness_corrected,
            "evidence_ids_recorded": sorted(self.recorded),
            "invalid_actions": self.invalid_actions,
            "action_rows": len(self.records) - 1,
        }


def oracle_bytes(records: list[dict[str, Any]]) -> bytes:
    rows = [json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in records]
    return ("\n".join(rows) + "\n").encode("utf-8")


def audit() -> dict[str, Any]:
    spec = read_yaml(ROOT / "map_spec.yaml")
    truth = read_yaml(ROOT / "planning" / "private_truth_table.yaml")
    evidence_rules = read_yaml(ROOT / "evidence_or_rules.yaml")
    hand = read_json(ROOT / "planning" / "hand_traces.json")
    cases = read_yaml(ROOT / "failure_traces" / "cases.yaml")
    seed = read_yaml(ROOT / "planning" / "seed_replay.yaml")
    assert spec["status"] in {"DESIGN_IN_PROGRESS", "DESIGN_COMPLETE_PENDING_RUNTIME"}
    assert spec["topology"]["nodes"] == ["H", "V", "G", "K", "S", "A"]
    assert set(EVIDENCE) == set(evidence_rules["source_catalog"])
    assert len(truth["candidate_access_profiles"]) == 3
    assert truth["truth"] == TRUTH
    key_candidates = [person for person, profile in truth["candidate_access_profiles"].items()
                      if profile["vault_key"] == "K3"]
    tread_candidates = [person for person, profile in truth["candidate_access_profiles"].items()
                        if profile["boot_tread"] == "C7"]
    assert key_candidates == tread_candidates == ["CELINE"]
    assert truth["truth"]["entry_path_id"] == "SECRET_S_V"
    assert truth["truth"]["entry_time"] == "21:06" and truth["truth"]["exit_time"] == "21:14"
    assert set(cases["boundaries"]) == {"B01_two_lock_events_are_one_class", "B02_exact_minutes_not_window_guess",
                                         "B03_path_enum_is_exact", "B04_unobserved_id_cannot_be_recorded",
                                         "B05_testimony_identity_is_not_physical_fact", "B06_seed0_same_case_replay"}

    routes: dict[str, Any] = {}
    first_oracle: bytes | None = None
    for route in hand["routes"]:
        replay = CaseReplay()
        replay.run(route["actions"])
        metrics = replay.metrics()
        expected = route["expected"]
        for field in ("finish_tick", "success", "factual_accuracy", "evidence_coverage", "witness_identity_revised_after_physical_evidence"):
            assert metrics[field] == expected[field], (route["id"], field, metrics, expected)
        assert metrics["success"] and metrics["terminal_reason"] == "ALL_CLAIMS_SUPPORTED_AND_CORRECT"
        assert all(metrics["independent_source_classes_by_claim"][key] >= 2 for key in TRUTH)
        routes[route["id"]] = metrics
        if route["id"] == "physical_then_witness":
            first_oracle = oracle_bytes(replay.records)

    assert first_oracle is not None
    repeated = CaseReplay()
    repeated.run(hand["routes"][0]["actions"])
    assert oracle_bytes(repeated.records) == first_oracle
    (ROOT / "oracle_trace.jsonl").write_bytes(first_oracle)

    failures: dict[str, Any] = {}
    for case_id, case in cases["cases"].items():
        replay = CaseReplay()
        replay.run(case["actions"])
        metrics = replay.metrics()
        expected = case["expected"]
        for field, expected_field in (("terminal_reason", "terminal_reason"), ("finish_tick", "finish_tick"),
                                      ("private_judge_reason", "judge_reason"), ("factual_accuracy", "factual_accuracy"),
                                      ("evidence_coverage", "evidence_coverage")):
            assert metrics[field] == expected[expected_field], (case_id, field, metrics, expected)
        failures[case_id] = metrics

    # Same-class records remain one source class even when their IDs differ.
    assert {EVIDENCE["LOCK_ENTRY_K3_2106"]["class"], EVIDENCE["LOCK_EXIT_S_2114"]["class"]} == {"instrument_log"}
    # Physical and testimony windows permit several possibilities, but the exact lock minute chooses one tuple.
    assert CaseReplay()._supports("PRINT_C7_ROUTE_SV", "entry_time", "21:05")
    assert CaseReplay()._supports("PRINT_C7_ROUTE_SV", "exit_time", "21:15")
    assert CaseReplay()._supports("PRINT_C7_ROUTE_SV", "entry_time", "21:06")
    assert CaseReplay()._supports("PRINT_C7_ROUTE_SV", "exit_time", "21:14")
    wrong_minute = CaseReplay()
    wrong_minute.node = "H"
    for evidence_id in ("LOCK_ENTRY_K3_2106", "PRINT_C7_ROUTE_SV"):
        wrong_minute._reveal(evidence_id)
        wrong_minute.recorded.append(evidence_id)
    wrong_minute.step({"name": "submit", "claims": {"person_id": "CELINE", "entry_path_id": "SECRET_S_V", "entry_time": "21:05", "exit_time": "21:14"}, "citations_by_claim": {"person_id": ["LOCK_ENTRY_K3_2106", "PRINT_C7_ROUTE_SV"], "entry_path_id": ["LOCK_ENTRY_K3_2106", "PRINT_C7_ROUTE_SV"], "entry_time": ["LOCK_ENTRY_K3_2106", "PRINT_C7_ROUTE_SV"], "exit_time": ["LOCK_EXIT_S_2114", "PRINT_C7_ROUTE_SV"]}})
    assert (wrong_minute.terminal_reason == "CASE_REJECTED" and wrong_minute.factual_correct_claims == 3
            and wrong_minute.private_judge_reason == "CLAIM_CONTRADICTS_RECORDED_EVIDENCE")
    invalid_enum = CaseReplay()
    invalid_enum.node = "H"
    invalid_enum.step({"name": "submit", "claims": {"person_id": "CELINE", "entry_path_id": "secret_tunnel", "entry_time": "21:06", "exit_time": "21:14"}, "citations_by_claim": {}})
    assert invalid_enum.records[-1]["result"] == "INVALID_ACTION_ENUM" and invalid_enum.tick == 0

    unopened = CaseReplay()
    before_tick = unopened.tick
    unopened.step({"name": "record", "evidence_id": "LOCK_ENTRY_K3_2106"})
    assert unopened.records[-1]["result"] == "EVIDENCE_NOT_OBSERVED" and unopened.tick == before_tick
    initial_public = repeated.records[0]["observation"]
    assert initial_public["public_alert"] == "CROWN_MISSING" and initial_public["observed_evidence"] == []
    assert "CELINE" not in json.dumps(initial_public, ensure_ascii=False)

    # Make sure a witness-only identity and a two-log one-class identity cannot pass the source gate.
    assert len({EVIDENCE[eid]["class"] for eid in ("LOCK_ENTRY_K3_2106", "LOCK_EXIT_S_2114")}) == 1
    assert len({EVIDENCE[eid]["class"] for eid in ("KEY_REGISTER_K3_CELINE", "LOCK_ENTRY_K3_2106")}) == 2

    public_text = first_oracle.decode("utf-8")
    assert "private_judge_reason" not in public_text and "culprit_id" not in public_text
    assert all(row["observation"]["terminal_reason"] in (None, "ALL_CLAIMS_SUPPORTED_AND_CORRECT")
               for row in repeated.records)
    assert seed["seed"] == hand["seed"] == 0
    assert len(first_oracle.splitlines()) == len(hand["routes"][0]["actions"]) + 1

    reference = {
        "map_id": "MAP-28",
        "result": "MAP28_CROSS_SOURCE_CASE_AND_UNIQUE_TUPLE_REPLAYED",
        "runtime_verified": False,
        "truth_tuple_for_judge_audit": TRUTH,
        "unique_truth_tuple_count": 1,
        "routes": routes,
        "failures": failures,
        "source_classes": {key: value["class"] for key, value in EVIDENCE.items()},
        "boundary_results": {
            "same_class_logs_count": 1,
            "exact_entry_time": "21:06",
            "exact_exit_time": "21:14",
            "unobserved_record_cost": 0,
            "invalid_path_enum_cost": 0,
            "initial_truth_leaked": False,
        },
        "oracle_rows": len(first_oracle.splitlines()),
        "oracle_sha256": hashlib.sha256(first_oracle).hexdigest().upper(),
    }
    (ROOT / "planning" / "map28_reference.json").write_text(
        json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return reference


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
