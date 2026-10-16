"""V4 MAP-26, deterministic diagnosis, corrective feedback, and spare budget."""

from __future__ import annotations

import json
from typing import Any

from agent_arena.worlds.scenario_v4.base import ScenarioV4Environment
from agent_arena.worlds.scenario_v4.models import (
    ScenarioV4Action,
    V4Map26Observation,
    V4Status,
)

PARTS = ("power_regulator", "antenna_coupler", "software_image")
EDGES = {frozenset(("T", "D")), frozenset(("D", "A")), frozenset(("A", "B"))}
NODES = ("T", "D", "A", "B")
FAULT_BY_SEED = {0: "antenna_coupler", 1: "power_regulator", 2: "software_image"}
TESTS = ("bus_load", "antenna_loopback", "software_checksum")
LOG_ID = "COMM_LOSS_LAST_TRANSMIT"
TEST_PART = {
    "bus_load": "power_regulator",
    "antenna_loopback": "antenna_coupler",
    "software_checksum": "software_image",
}
TEST_POSITIVE = {
    "bus_load": "BUS_VOLTAGE_DROOP",
    "antenna_loopback": "ANTENNA_LOOPBACK_OPEN",
    "software_checksum": "IMAGE_CHECKSUM_MISMATCH",
}
TEST_NEGATIVE = {
    "bus_load": "BUS_VOLTAGE_STABLE",
    "antenna_loopback": "ANTENNA_LOOPBACK_OK",
    "software_checksum": "IMAGE_CHECKSUM_VALID",
}
FULL_FEEDBACK = {
    "power_regulator": "POWER_SELF_TEST_OK_LINK_STILL_DOWN",
    "antenna_coupler": "ANTENNA_SELF_TEST_OK_LINK_STILL_DOWN",
    "software_image": "SOFTWARE_SELF_TEST_OK_LINK_STILL_DOWN",
}


class Map26Environment(ScenarioV4Environment):
    map_id = "MAP-26"

    def __init__(
        self,
        *,
        feedback_mode: str = "full",
        step_limit: int = 100,
        parts: tuple[str, ...] | None = None,
        fault_part: str | None = None,
        spares: int = 2,
        carry_capacity: int = 2,
        nodes: tuple[str, ...] | None = None,
        edges: set[frozenset[str]] | None = None,
        log_id: str = LOG_ID,
    ) -> None:
        if feedback_mode not in {"full", "hidden", "structured"}:
            raise ValueError("MAP-26 feedback mode must be full, hidden, or structured.")
        # Optional parameters let the V6 fixture layer build independent fault and
        # spare-budget instances. Defaults reproduce the reviewed V4 MAP-26 scene.
        self.feedback_mode = feedback_mode
        self.step_limit = step_limit
        self.parts = parts if parts is not None else PARTS
        self.fault_part_override = fault_part
        self.initial_spares = spares
        self.carry_capacity = carry_capacity
        self.nodes = nodes if nodes is not None else NODES
        self.edges = edges if edges is not None else EDGES
        self.log_id = log_id
        self.seed = 0
        self.status = V4Status.RUNNING
        self.terminal_reason = None
        self.step_count = 0
        self._reset_state(0)

    @property
    def tick(self) -> int:
        return self.current_tick

    def _reset_state(self, seed: int) -> None:
        if seed not in FAULT_BY_SEED:
            raise ValueError("MAP-26 only defines seed IDs 0, 1, and 2.")
        self.fault_part = self.fault_part_override or FAULT_BY_SEED[seed]
        self.node = "T"
        self.current_tick = 0
        self.spares_at_b = self.initial_spares
        self.carried: list[str] = []
        self.installed: dict[str, str] = {}
        self.prior_slot: dict[str, str | None] = {}
        self.last_failed_part: str | None = None
        self.failed_by_part = {part: 0 for part in self.parts}
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
        self.latest_result = "INITIAL"
        self.latest_error: str | None = None
        self.action_history: list[tuple[str, str | None]] = []

    @property
    def uninstalled_spares(self) -> int:
        return self.spares_at_b + len(self.carried)

    def _observation(self) -> V4Map26Observation:
        return V4Map26Observation(
            current_tick=self.current_tick,
            current_node=self.node,
            alert="COMMUNICATION_LOST",
            log_readings=tuple(self.log_readings),
            test_readings=dict(self.test_readings),
            spare_units_at_B=self.spares_at_b,
            carried_spare_units=tuple(self.carried),
            installed_candidates=dict(self.installed),
            last_action_result=self.latest_result,
            communication_restored=self.communication_restored,
            last_action_error_code=self.latest_error,
            terminal=self.is_terminal,
            terminal_reason=self.terminal_reason,
        )

    def _apply(self, action: ScenarioV4Action) -> str:
        self.action_attempts += 1
        name = action.tool
        part: str | None = action.part_id
        if name == "move":
            target = action.to
            if target not in self.nodes or frozenset((self.node, target)) not in self.edges:
                return self._reject("INVALID_LOCATION")
            self.node = target
            return self._accept("MOVE_SUCCEEDED", duration=1)
        if name == "read_log":
            if self.node != "D" or action.log_id != self.log_id:
                return self._reject("INVALID_LOCATION")
            reading = "TRANSMIT_SURGE_BEFORE_LINK_LOSS_POWER_OR_DOWNSTREAM"
            self.log_readings.append(reading)
            return self._accept("LOG_READ", duration=1)
        if name == "test":
            if self.node != "D" or action.test_id not in TEST_PART:
                return self._reject("INVALID_TEST_ID" if self.node == "D" else "INVALID_LOCATION")
            assert action.test_id is not None
            part_for_test = TEST_PART[action.test_id]
            reading = (
                TEST_POSITIVE[action.test_id]
                if self.fault_part == part_for_test
                else TEST_NEGATIVE[action.test_id]
            )
            prior = self.test_readings.get(action.test_id)
            if prior is not None:
                self.repeated_test_count += 1
            self.test_readings[action.test_id] = reading
            self.test_action_count += 1
            return self._accept(f"TEST_COMPLETED:{action.test_id}:{reading}", duration=1)
        if name == "take_spare":
            if self.node != "B":
                return self._reject("INVALID_LOCATION")
            if part not in self.parts:
                return self._reject("INVALID_PART_ID")
            if self.spares_at_b <= 0 or len(self.carried) >= self.carry_capacity:
                return self._reject("NO_SPARE_AVAILABLE")
            self.spares_at_b -= 1
            self.carried.append(part)
            return self._accept(f"SPARE_TAKEN:{part}", duration=1)
        if name == "replace":
            if self.node != "A":
                return self._reject("INVALID_LOCATION")
            if part not in self.parts or part not in self.carried:
                return self._reject("INVALID_PART_ID")
            self.carried.remove(part)
            self.prior_slot[part] = self.installed.get(part)
            self.installed[part] = "installed_candidate"
            if part == self.fault_part:
                result = "SELECTED_COMPONENT_REPLACED_RESTART_REQUIRED"
                duration = 1
                self.last_failed_part = None
            else:
                duration = 1 + self.failed_by_part[part]
                self.failed_by_part[part] += 1
                self.wrong_replace_durations.append(duration)
                self.wrong_replacements += 1
                self.last_failed_part = part
                result = self._feedback_for_wrong_replacement(part, FULL_FEEDBACK[part])
            result = self._accept(result, duration=duration)
            if self.uninstalled_spares == 0 and not self.communication_restored:
                self.status = V4Status.FAILURE
                self.terminal_reason = "SPARES_EXHAUSTED"
                result = "SPARES_EXHAUSTED"
            self.action_history.append(("replace", part))
            return self._finish(result)
        if name == "rollback":
            if self.node != "A" or self.last_failed_part is None:
                return self._reject("INVALID_ROLLBACK")
            failed = self.last_failed_part
            if len(self.carried) >= self.carry_capacity:
                return self._reject("CARRY_CAPACITY_EXCEEDED")
            self.carried.append(failed)
            previous = self.prior_slot.get(failed)
            if previous is None:
                self.installed.pop(failed, None)
            else:
                self.installed[failed] = previous
            self.last_failed_part = None
            self.rollback_count += 1
            self.action_history.append(("rollback", failed))
            return self._accept("ROLLBACK_COMPLETED", duration=1)
        if name == "restart":
            if self.node != "A":
                return self._reject("INVALID_LOCATION")
            self.action_history.append(("restart", None))
            self.valid_action_count += 1
            self.current_tick += 1
            if self.fault_part in self.installed:
                self.communication_restored = True
                if self.uninstalled_spares >= 1:
                    self.status = V4Status.SUCCESS
                    self.terminal_reason = "ALL_OBJECTIVES_COMPLETE"
                    return self._finish("COMMUNICATION_RESTORED")
                self.status = V4Status.FAILURE
                self.terminal_reason = "SPARES_EXHAUSTED"
                return self._finish("SPARES_EXHAUSTED")
            return self._finish("RESTART_LINK_STILL_DOWN")
        return self._reject("ACTION_NOT_AVAILABLE")

    def _reject(self, reason: str) -> str:
        self.latest_error = reason
        self.latest_result = reason
        self.action_history.append(("invalid", reason))
        return reason

    def _invalid_action(self) -> str:
        return self._reject("INVALID_ACTION_SCHEMA")

    def _feedback_for_wrong_replacement(self, part: str, full_feedback: str) -> str:
        if self.feedback_mode == "full":
            return full_feedback
        if self.feedback_mode == "hidden":
            return "REPLACEMENT_FEEDBACK_HIDDEN"
        return json.dumps(
            {
                "event": "wrong_replacement_feedback",
                "tested_part": part,
                "self_test": "passed",
                "communication": "still_down",
                "fault_component": "unknown",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _accept(self, result: str, *, duration: int) -> str:
        self.current_tick += duration
        self.valid_action_count += 1
        self.latest_error = None
        self.latest_result = result
        return result

    def _finish(self, result: str) -> str:
        self.latest_error = (
            None if result not in {"INVALID_ROLLBACK", "SPARES_EXHAUSTED"} else result
        )
        self.latest_result = result
        return result

    def judge_state(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "seed": self.seed,
            "fault_part": self.fault_part,
            "node": self.node,
            "tick": self.current_tick,
            "spares_at_B": self.spares_at_b,
            "carried": list(self.carried),
            "installed": dict(sorted(self.installed.items())),
            "failed_by_part": dict(self.failed_by_part),
            "test_readings": dict(sorted(self.test_readings.items())),
            "log_readings": list(self.log_readings),
            "communication_restored": self.communication_restored,
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
        }

    def metrics(self) -> dict[str, Any]:
        changed_after_feedback = False
        for index, (name, part) in enumerate(self.action_history):
            if name != "replace" or part == self.fault_part:
                continue
            changed_after_feedback = any(
                next_name in {"rollback", "test"}
                for next_name, _ in self.action_history[index + 1 :]
            )
            if changed_after_feedback:
                break
        return {
            "success": self.is_success,
            "communication_restored": self.communication_restored,
            "finish_tick": self.current_tick,
            "tests_run": self.test_action_count,
            "repeated_test_count": self.repeated_test_count,
            "wrong_replacement_attempts": self.wrong_replacements,
            "same_part_retry_attempts": sum(
                max(count - 1, 0) for count in self.failed_by_part.values()
            ),
            "rollback_count": self.rollback_count,
            "feedback_to_changed_action": changed_after_feedback,
            "spare_units_consumed": self.initial_spares - self.uninstalled_spares,
            "spare_units_remaining": self.uninstalled_spares,
            "valid_action_rate": self.valid_action_count / self.action_attempts
            if self.action_attempts
            else 1.0,
            "terminal_reason": self.terminal_reason,
        }
