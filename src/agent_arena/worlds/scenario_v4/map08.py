"""V4 MAP-08, active leak diagnosis under rising pressure."""

from __future__ import annotations

from typing import Any

from agent_arena.worlds.scenario_v4.base import ScenarioV4Environment
from agent_arena.worlds.scenario_v4.models import (
    ScenarioV4Action,
    V4Map08Observation,
    V4Status,
)

EDGES = {
    "A_B": ("A", "B"),
    "B_C": ("B", "C"),
    "C_D": ("C", "D"),
    "D_E": ("D", "E"),
    "E_F": ("E", "F"),
    "F_A": ("F", "A"),
    "X_A": ("X", "A"),
    "X_C": ("X", "C"),
    "Y_D": ("Y", "D"),
    "Y_F": ("Y", "F"),
}
LEAK_BY_SEED = {
    **{seed: "B" for seed in range(0, 4)},
    **{seed: "D" for seed in range(4, 8)},
    **{seed: "F" for seed in range(8, 12)},
}
SIGNATURES = {
    "B": {"X": "pulse_amber", "Y": "pulse_slate"},
    "D": {"X": "pulse_slate", "Y": "pulse_cobalt"},
    "F": {"X": "pulse_slate", "Y": "pulse_slate"},
}
ADJACENCY = {
    node: tuple(
        sorted(other for edge in EDGES.values() if node in edge for other in edge if other != node)
    )
    for node in ("A", "B", "C", "D", "E", "F", "X", "Y")
}


class Map08Environment(ScenarioV4Environment):
    map_id = "MAP-08"

    def __init__(
        self,
        *,
        step_limit: int = 100,
        edges: dict[str, tuple[str, str]] | None = None,
        signatures: dict[str, dict[str, str]] | None = None,
        leak_by_seed: dict[int, str] | None = None,
        water_limit: float = 7.0,
        sealant_count: int = 1,
        test_ticks: int = 2,
        wrong_repair_ticks: int = 4,
    ) -> None:
        # Optional parameters let the V6 fixture layer build independent diagnosis
        # matrices. Defaults reproduce the reviewed V4 MAP-08 scene exactly.
        self.step_limit = step_limit
        self.edges = edges if edges is not None else EDGES
        self.signatures = signatures if signatures is not None else SIGNATURES
        self.leak_by_seed = leak_by_seed if leak_by_seed is not None else LEAK_BY_SEED
        self.water_limit = water_limit
        self.initial_sealant_count = sealant_count
        self.test_ticks = test_ticks
        self.wrong_repair_ticks = wrong_repair_ticks
        self.seed = 0
        self.status = V4Status.RUNNING
        self.terminal_reason = None
        self.step_count = 0
        self._reset_state(0)

    @property
    def tick(self) -> int:
        return self.current_tick

    def _reset_state(self, seed: int) -> None:
        if seed not in self.leak_by_seed:
            raise ValueError("MAP-08 only defines the registered seed IDs.")
        self.true_leak = self.leak_by_seed[seed]
        self.location = "A"
        self.current_tick = 0
        self.water = 1.0
        self.sealant_count = self.initial_sealant_count
        self.sealed = False
        self.test_results: dict[str, str] = {}
        self.last_action_result = "INITIAL"
        self.first_test_station: str | None = None
        self.tests_run = 0
        self.travel_ticks = 0
        self.peak_water = self.water

    @property
    def candidate_sites(self) -> tuple[str, ...]:
        return tuple(sorted(self.signatures))

    @property
    def test_stations(self) -> tuple[str, ...]:
        return tuple(sorted({station for row in self.signatures.values() for station in row}))

    def _test_semantics(self) -> dict[str, str]:
        return {
            station: "；".join(
                f"{site} 读数为 {self.signatures[site][station]}" for site in self.candidate_sites
            )
            for station in self.test_stations
        }

    def _observation(self) -> V4Map08Observation:
        visible = tuple(
            f"{edge_id}:{other}"
            for edge_id, endpoints in sorted(self.edges.items())
            if self.location in endpoints
            for other in endpoints
            if other != self.location
        )
        sites = self.candidate_sites
        prior = {site: 1.0 / len(sites) for site in sites}
        return V4Map08Observation(
            location=self.location,
            visible_edges=visible,
            current_tick=self.current_tick,
            current_core_water=self.water,
            baseline_sensor_reading="flat",
            published_candidate_set=sites,
            published_prior=prior,
            known_test_semantics=self._test_semantics(),
            sealant_count=self.sealant_count,
            test_results=dict(self.test_results),
            last_action_result=self.last_action_result,
            terminal=self.is_terminal,
            terminal_reason=self.terminal_reason,
        )

    def _advance_pressure(self, duration: int) -> bool:
        for _ in range(duration):
            self.current_tick += 1
            if not self.sealed:
                self.water += 0.5
            self.peak_water = max(self.peak_water, self.water)
            if self.water > self.water_limit:
                self.status = V4Status.FAILURE
                self.terminal_reason = "CORE_WATER_LIMIT_EXCEEDED"
                return False
        return True

    def _apply(self, action: ScenarioV4Action) -> str:
        if action.tool == "move":
            edge = action.edge_id
            if edge not in self.edges or self.location not in self.edges[edge]:
                return self._reject("INVALID_EDGE")
            if not self._advance_pressure(1):
                return self._finish("CORE_WATER_LIMIT_EXCEEDED")
            self.location = next(node for node in self.edges[edge] if node != self.location)
            self.travel_ticks += 1
            return self._finish("MOVE_SUCCEEDED")
        if action.tool == "inspect":
            if action.target_id != "ordinary_sensor":
                return self._reject("INVALID_INSPECT_TARGET")
            if not self._advance_pressure(1):
                return self._finish("CORE_WATER_LIMIT_EXCEEDED")
            return self._finish("SENSOR_FLAT")
        if action.tool == "wait":
            if not self._advance_pressure(1):
                return self._finish("CORE_WATER_LIMIT_EXCEEDED")
            return self._finish("WAITED_ONE_TICK")
        if action.tool != "interact":
            return self._reject("ACTION_NOT_AVAILABLE")
        if action.operation in {f"pressure_test_{station}" for station in self.test_stations}:
            assert action.operation is not None
            station = action.operation.removeprefix("pressure_test_")
            if action.target_id != station or self.location != station:
                return self._reject("INVALID_TEST_LOCATION")
            if self.first_test_station is None:
                self.first_test_station = station
            if not self._advance_pressure(self.test_ticks):
                return self._finish("CORE_WATER_LIMIT_EXCEEDED")
            result = self.signatures[self.true_leak][station]
            self.test_results[station] = result
            self.tests_run += 1
            return self._finish(result)
        if action.operation == "repair_leak":
            if action.target_id not in self.signatures or self.location != action.target_id:
                return self._reject("INVALID_REPAIR_LOCATION")
            if self.sealant_count != self.initial_sealant_count:
                return self._reject("NO_SEALANT")
            correct = action.target_id == self.true_leak
            if not self._advance_pressure(1 if correct else self.wrong_repair_ticks):
                return self._finish("CORE_WATER_LIMIT_EXCEEDED")
            self.sealant_count = 0
            if correct:
                self.sealed = True
                self.status = V4Status.SUCCESS
                self.terminal_reason = "LEAK_SEALED"
                return self._finish("LEAK_SEALED")
            self.status = V4Status.FAILURE
            self.terminal_reason = "SEALANT_MISUSED"
            return self._finish("SEALANT_MISUSED")
        return self._reject("INVALID_OPERATION")

    def _reject(self, reason: str) -> str:
        self.last_action_result = reason
        return reason

    def _invalid_action(self) -> str:
        return self._reject("INVALID_ACTION_SCHEMA")

    def _finish(self, result: str) -> str:
        self.last_action_result = result
        return result

    def judge_state(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "seed": self.seed,
            "true_leak": self.true_leak,
            "location": self.location,
            "tick": self.current_tick,
            "water": self.water,
            "sealant_count": self.sealant_count,
            "sealed": self.sealed,
            "test_results": dict(sorted(self.test_results.items())),
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
        }

    def metrics(self) -> dict[str, Any]:
        remaining = set(self.signatures)
        candidate_set_sizes = [len(remaining)]
        for test_id, reading in self.test_results.items():
            remaining = {
                site for site in remaining if self.signatures[site][test_id] == reading
            }
            candidate_set_sizes.append(len(remaining))
        return {
            "success": self.is_success,
            "diagnosis_accuracy": self.sealed
            and self.true_leak in self.test_results
            or self.sealed,
            "first_test_station": self.first_test_station,
            "candidate_set_sizes": candidate_set_sizes,
            "tests_run": self.tests_run,
            "travel_ticks": self.travel_ticks,
            "repair_tick": self.current_tick if self.sealed else None,
            "peak_core_water": self.peak_water,
            "terminal_reason": self.terminal_reason,
        }
