"""Hand-authored offline replay audit for MAP-26; does not instantiate a runtime environment."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
PARTS = {"power_regulator", "antenna_coupler", "software_image"}
EDGES = {frozenset(pair) for pair in (("T", "D"), ("D", "A"), ("A", "B"))}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class HandReplay:
    def __init__(self, fixture: dict[str, Any]):
        self.fixture = fixture
        self.fault_part = fixture["fault_part"]
        self.readings = fixture["readings"]
        self.tick = 0
        self.node = "T"
        self.spares_at_b = 2
        self.carried: list[str] = []
        self.installed: dict[str, str] = {}
        self.prior_slot: dict[str, str | None] = {}
        self.last_failed_part: str | None = None
        self.failed_by_part = {part: 0 for part in PARTS}
        self.test_readings: dict[str, str] = {}
        self.log_readings: list[str] = []
        self.wrong_replace_durations: list[int] = []
        self.wrong_replacements = 0
        self.rollback_count = 0
        self.test_action_count = 0
        self.repeated_test_count = 0
        self.action_attempts = 0
        self.valid_action_count = 0
        self.communication_restored = False
        self.terminal_reason: str | None = None
        self.latest_result = "INITIAL"
        self.records: list[dict[str, Any]] = []
        self._record("INITIAL")

    @property
    def spare_units_remaining(self) -> int:
        return self.spares_at_b + len(self.carried)

    def _record(self, result: str) -> None:
        self.records.append({"tick": self.tick, "node": self.node, "result": result,
                             "observation": self.observation()})

    def observation(self) -> dict[str, Any]:
        return {
            "current_tick": self.tick,
            "current_node": self.node,
            "alert": "COMMUNICATION_LOST",
            "log_readings": list(self.log_readings),
            "test_readings": dict(sorted(self.test_readings.items())),
            "spare_units_at_B": self.spares_at_b,
            "carried_spare_units": list(self.carried),
            "installed_candidates": dict(sorted(self.installed.items())),
            "last_action_result": self.latest_result,
            "communication_restored": self.communication_restored,
            "terminal": self.terminal_reason is not None,
            "terminal_reason": self.terminal_reason,
            "last_action_error_code": None,
        }

    def step(self, action: dict[str, Any]) -> None:
        if self.terminal_reason is not None:
            raise AssertionError("hand trace continues after terminal state")
        self.action_attempts += 1
        name = action["name"]
        result = ""
        duration = 0
        if name == "move":
            target = action["to"]
            assert target in {"T", "D", "A", "B"} and frozenset((self.node, target)) in EDGES
            self.node = target
            duration = 1
            result = "MOVE_SUCCEEDED"
        elif name == "read_log":
            assert self.node == "D" and action["log_id"] == "COMM_LOSS_LAST_TRANSMIT"
            value = "TRANSMIT_SURGE_BEFORE_LINK_LOSS_POWER_OR_DOWNSTREAM"
            self.log_readings.append(value)
            duration = 1
            result = "LOG_READ"
        elif name == "test":
            assert self.node == "D" and action["test_id"] in self.readings
            test_id = action["test_id"]
            value = self.readings[test_id]
            previous = self.test_readings.get(test_id)
            assert previous is None or previous == value, "same-seed repeated test changed its reading"
            if previous is not None:
                self.repeated_test_count += 1
            self.test_action_count += 1
            self.test_readings[test_id] = value
            duration = 1
            result = f"TEST_COMPLETED:{test_id}:{value}"
        elif name == "take_spare":
            part = action["part_id"]
            assert self.node == "B" and part in PARTS and self.spares_at_b > 0
            assert len(self.carried) < 2
            self.spares_at_b -= 1
            self.carried.append(part)
            duration = 1
            result = f"SPARE_TAKEN:{part}"
        elif name == "replace":
            part = action["part_id"]
            assert self.node == "A" and part in PARTS and part in self.carried
            self.carried.remove(part)
            self.prior_slot[part] = self.installed.get(part)
            self.installed[part] = "installed_candidate"
            if part == self.fault_part:
                duration = 1
                result = "SELECTED_COMPONENT_REPLACED_RESTART_REQUIRED"
                self.last_failed_part = None
            else:
                duration = 1 + self.failed_by_part[part]
                self.failed_by_part[part] += 1
                self.wrong_replace_durations.append(duration)
                self.wrong_replacements += 1
                self.last_failed_part = part
                result = {
                    "power_regulator": "POWER_SELF_TEST_OK_LINK_STILL_DOWN",
                    "antenna_coupler": "ANTENNA_SELF_TEST_OK_LINK_STILL_DOWN",
                    "software_image": "SOFTWARE_SELF_TEST_OK_LINK_STILL_DOWN",
                }[part]
        elif name == "rollback":
            assert self.node == "A" and self.last_failed_part is not None
            part = self.last_failed_part
            assert len(self.carried) < 2
            self.carried.append(part)
            previous = self.prior_slot[part]
            if previous is None:
                self.installed.pop(part, None)
            else:
                self.installed[part] = previous
            self.last_failed_part = None
            self.rollback_count += 1
            duration = 1
            result = "ROLLBACK_COMPLETED"
        elif name == "restart":
            assert self.node == "A"
            duration = 1
            if self.fault_part in self.installed:
                self.communication_restored = True
                result = "COMMUNICATION_RESTORED"
                self.terminal_reason = "ALL_OBJECTIVES_COMPLETE" if self.spare_units_remaining >= 1 else "SPARES_EXHAUSTED"
            else:
                result = "RESTART_LINK_STILL_DOWN"
        else:
            raise AssertionError(f"unknown hand-authored action: {name}")

        self.tick += duration
        self.valid_action_count += 1
        if (name == "replace" and self.spare_units_remaining == 0
                and not self.communication_restored):
            self.terminal_reason = "SPARES_EXHAUSTED"
        self.latest_result = result
        self._record(result)

    def run(self, actions: list[dict[str, Any]]) -> None:
        for action in actions:
            self.step(action)

    def metrics(self) -> dict[str, Any]:
        return {
            "finish_tick": self.tick,
            "communication_restored": self.communication_restored,
            "terminal_reason": self.terminal_reason,
            "spare_units_remaining": self.spare_units_remaining,
            "wrong_replacements": self.wrong_replacements,
            "wrong_replace_durations": list(self.wrong_replace_durations),
            "same_part_retry_attempts": sum(max(count - 1, 0) for count in self.failed_by_part.values()),
            "rollback_count": self.rollback_count,
            "test_action_count": self.test_action_count,
            "repeated_test_count": self.repeated_test_count,
            "test_consistency_violations": 0,
            "valid_action_rate": self.valid_action_count / self.action_attempts if self.action_attempts else 1.0,
            "spare_units_consumed": 2 - self.spare_units_remaining,
            "test_readings": dict(sorted(self.test_readings.items())),
            "action_rows": len(self.records) - 1,
        }


def public_oracle(records: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in records]
    return ("\n".join(lines) + "\n").encode("utf-8")


def changed_after_feedback(actions: list[dict[str, Any]], fault_part: str) -> bool | None:
    for index, action in enumerate(actions):
        if action["name"] != "replace" or action["part_id"] == fault_part:
            continue
        for following in actions[index + 1:]:
            if following["name"] in {"replace", "rollback", "test"}:
                return following["name"] in {"rollback", "test"}
    return None


def audit() -> dict[str, Any]:
    spec = read_yaml(ROOT / "map_spec.yaml")
    fixture = read_yaml(ROOT / "planning" / "private_seed_reference.yaml")
    hand = read_json(ROOT / "planning" / "hand_traces.json")
    failures = read_yaml(ROOT / "failure_traces" / "cases.yaml")
    assert spec["status"] in {"DESIGN_IN_PROGRESS", "DESIGN_COMPLETE_PENDING_RUNTIME"}
    assert spec["topology"]["nodes"] == ["T", "D", "A", "B"]
    assert spec["initial_state"]["spare_units_at_B"] == 2
    assert set(fixture["supported_seed_fixtures"]) == {0, 1, 2}
    assert {row["alert"] for row in fixture["initial_public_observation_by_seed"].values()} == {"COMMUNICATION_LOST"}

    route_summaries: dict[str, Any] = {}
    oracle_bytes: bytes | None = None
    for route in hand["routes"]:
        replay = HandReplay(fixture["supported_seed_fixtures"][hand["seed"]])
        replay.run(route["actions"])
        metrics = replay.metrics()
        metrics["feedback_to_changed_action"] = changed_after_feedback(
            route["actions"], fixture["supported_seed_fixtures"][hand["seed"]]["fault_part"]
        )
        assert metrics["communication_restored"] and metrics["terminal_reason"] == "ALL_OBJECTIVES_COMPLETE"
        assert metrics["finish_tick"] == route["expected"]["tick"]
        assert metrics["spare_units_remaining"] == route["expected"]["uninstalled_spares_remaining"] == 1
        assert metrics["wrong_replacements"] == route["expected"].get("wrong_replacements", 0)
        assert replay.terminal_reason is not None
        if route["id"] == "diagnose_first":
            assert replay.test_readings == fixture["supported_seed_fixtures"][0]["readings"]
            oracle_bytes = public_oracle(replay.records)
        else:
            assert replay.rollback_count == 1 and replay.last_failed_part is None
            assert route["expected"]["feedback_to_changed_action"] is True
            assert metrics["feedback_to_changed_action"] is True
        route_summaries[route["id"]] = metrics

    assert oracle_bytes is not None
    second_replay = HandReplay(fixture["supported_seed_fixtures"][0])
    second_replay.run(hand["routes"][0]["actions"])
    assert public_oracle(second_replay.records) == oracle_bytes
    oracle_path = ROOT / "oracle_trace.jsonl"
    oracle_path.write_bytes(oracle_bytes)

    failure_summaries: dict[str, Any] = {}
    for case_id, case in failures["cases"].items():
        replay = HandReplay(fixture["supported_seed_fixtures"][failures["seed"]])
        replay.run(case["actions"])
        metrics = replay.metrics()
        expected = case["expected"]
        assert replay.terminal_reason == expected["terminal_reason"] == "SPARES_EXHAUSTED"
        assert metrics["finish_tick"] == expected["tick"], (case_id, metrics)
        assert metrics["spare_units_remaining"] == expected["spare_units_remaining"] == 0
        assert metrics["wrong_replacements"] == expected["wrong_replacements"]
        if "wrong_replace_durations" in expected:
            assert metrics["wrong_replace_durations"] == expected["wrong_replace_durations"]
        if "test_readings" in expected:
            assert metrics["test_readings"] == expected["test_readings"]
        failure_summaries[case_id] = metrics

    assert route_summaries["diagnose_first"]["finish_tick"] == 11
    assert route_summaries["feedback_then_correct"]["finish_tick"] == 16
    assert route_summaries["feedback_then_correct"]["rollback_count"] == 1
    assert failure_summaries["F02_repeat_same_wrong_part"]["wrong_replace_durations"] == [1, 2]
    assert fixture["supported_seed_fixtures"][0]["readings"]["antenna_loopback"] == "ANTENNA_LOOPBACK_OPEN"
    assert fixture["supported_seed_fixtures"][1]["readings"]["antenna_loopback"] == "ANTENNA_LOOPBACK_OK"

    reading_matrix = {}
    for seed, seed_fixture in fixture["supported_seed_fixtures"].items():
        replay = HandReplay(seed_fixture)
        replay.node = "D"
        reading_actions = [{"name": "test", "test_id": key} for key in seed_fixture["readings"]]
        reading_actions.append({"name": "test", "test_id": "antenna_loopback"})
        replay.run(reading_actions)
        assert replay.test_readings == seed_fixture["readings"]
        assert replay.repeated_test_count == 1
        reading_matrix[seed] = replay.test_readings

    rollback_retry = HandReplay(fixture["supported_seed_fixtures"][0])
    rollback_retry.node = "A"
    rollback_retry.spares_at_b = 1
    rollback_retry.carried.append("power_regulator")
    rollback_retry.run([
        {"name": "replace", "part_id": "power_regulator"},
        {"name": "rollback"},
        {"name": "replace", "part_id": "power_regulator"},
    ])
    assert rollback_retry.wrong_replace_durations == [1, 2]
    assert rollback_retry.rollback_count == 1 and rollback_retry.spare_units_remaining == 1

    boundary_results = {}
    for boundary_id, part in (("B02_wrong_last_spare", "power_regulator"),
                              ("B06_correct_last_spare", "antenna_coupler")):
        replay = HandReplay(fixture["supported_seed_fixtures"][0])
        replay.node = "A"
        replay.spares_at_b = 0
        replay.carried.append(part)
        replay.step({"name": "replace", "part_id": part})
        assert replay.terminal_reason == "SPARES_EXHAUSTED"
        boundary_results[boundary_id] = {"terminal_reason": replay.terminal_reason,
                                         "communication_restored": replay.communication_restored,
                                         "spare_units_remaining": replay.spare_units_remaining}

    assert all(fixture["initial_public_observation_by_seed"][seed] == {"alert": "COMMUNICATION_LOST"}
               for seed in fixture["initial_public_observation_by_seed"])
    public_text = oracle_bytes.decode("utf-8")
    for forbidden in ("FAULT_ANTENNA_OPEN", "FAULT_POWER_UNDERVOLTAGE", "FAULT_SOFTWARE_CORRUPT", "fault_part", "supported_seed_fixtures"):
        assert forbidden not in public_text

    reference = {
        "map_id": "MAP-26",
        "result": "MAP26_HAND_DIAGNOSTIC_AND_CORRECTION_ROUTES_REPLAYED",
        "runtime_verified": False,
        "routes": route_summaries,
        "failures": failure_summaries,
        "test_reading_matrix_by_seed": reading_matrix,
        "rollback_retry_durations": rollback_retry.wrong_replace_durations,
        "last_spare_boundaries": boundary_results,
        "seed_initial_observations_equivalent": True,
        "repeated_test_consistency": "same fixture yields immutable typed reading",
        "oracle_rows": len(oracle_bytes.splitlines()),
        "oracle_sha256": hashlib.sha256(oracle_bytes).hexdigest().upper(),
    }
    (ROOT / "planning" / "map26_reference.json").write_text(
        json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return reference


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
