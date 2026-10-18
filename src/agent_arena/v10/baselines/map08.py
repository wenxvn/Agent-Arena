"""MAP-08 V10 基线：真值 Oracle、公开信息增益启发式与四类消融。"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map08 import SITES, oracle_actions

Action = dict[str, Any]


def _split_score(partitions: dict[str, dict[str, str]], test: str, candidates: set[str]) -> int:
    readings: dict[str, int] = {}
    for site in candidates:
        reading = partitions[test][site]
        readings[reading] = readings.get(reading, 0) + 1
    values = sorted(readings.values(), reverse=True)
    return values[0] if values else 0


class Map08InfoGain:
    """公开启发式：按分区表挑“最能把候选一分为二”的测试，唯一后封存修复。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        candidates = set(observation["candidate_sites"])
        if observation["sealed_diagnosis"] is not None:
            return {"tool": "repair", "target_id": observation["sealed_diagnosis"]}
        if len(candidates) > 1:
            available = set(observation["available_tests"])
            if available:
                test = min(
                    available,
                    key=lambda name: (
                        _split_score(observation["test_partitions"], name, candidates),
                        name,
                    ),
                )
                return {"tool": "run_test", "test_id": test}
            return {"tool": "wait"}
        return {"tool": "seal_diagnosis", "diagnosis_code": sorted(candidates)[0]}


class Map08NoHypothesis:
    """不测试，直接封存并修复（V9 的旁路）。"""

    name = "no_hypothesis"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        candidates = sorted(observation["candidate_sites"])
        self.queue = [{"tool": "repair", "target_id": candidates[0]}]
        return {"tool": "seal_diagnosis", "diagnosis_code": candidates[0]}


class Map08SingleTest:
    """只跑一个测试就封存（信息不足）。"""

    name = "single_test"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        candidates = set(observation["candidate_sites"])
        if observation["sealed_diagnosis"] is not None:
            return {"tool": "repair", "target_id": observation["sealed_diagnosis"]}
        if not observation["test_results"]:
            return {"tool": "run_test", "test_id": "T1"}
        target = sorted(candidates)[0]
        self.queue = [{"tool": "repair", "target_id": target}]
        return {"tool": "seal_diagnosis", "diagnosis_code": target}


class Map08BlindRepairs:
    """逐个站点盲修（没有封存诊断）。"""

    name = "blind_repairs"

    def reset(self) -> None:
        self.index = 0

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.index >= len(SITES):
            return {"tool": "wait"}
        self.index += 1
        return {"tool": "repair", "target_id": SITES[self.index - 1]}


class Map08OverTesting:
    """把三个测试全部跑完再封存（信息够但更慢）。"""

    name = "over_testing"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        available = observation["available_tests"]
        if available:
            return {"tool": "run_test", "test_id": available[0]}
        candidates = sorted(observation["candidate_sites"])
        if observation["sealed_diagnosis"] is not None:
            return {"tool": "repair", "target_id": observation["sealed_diagnosis"]}
        self.queue = [{"tool": "repair", "target_id": candidates[0]}]
        return {"tool": "seal_diagnosis", "diagnosis_code": candidates[0]}


HEURISTIC = Map08InfoGain
ABLATIONS: dict[str, type[Any]] = {
    "no_hypothesis": Map08NoHypothesis,
    "single_test": Map08SingleTest,
    "blind_repairs": Map08BlindRepairs,
    "over_testing": Map08OverTesting,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map08BlindRepairs",
    "Map08InfoGain",
    "Map08NoHypothesis",
    "Map08OverTesting",
    "Map08SingleTest",
    "oracle_actions",
]
