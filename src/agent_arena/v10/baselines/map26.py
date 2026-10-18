"""MAP-26 V10 基线：真值 Oracle、公开信息增益启发式与四类消融。

公开启发式只读 `test_partitions` / `test_results` / `candidate_faults` / `spares` /
`wear` 与公开规则：跑测试直到候选唯一，换对应备件并重启。诊断不是必需，但盲换更费备件。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.map26 import FAULTS, PARTS, oracle_actions

Action = dict[str, Any]


def _score(partitions: dict[str, dict[str, str]], test: str, candidates: set[str]) -> int:
    counts: dict[str, int] = {}
    for fault in candidates:
        reading = partitions[test][fault]
        counts[reading] = counts.get(reading, 0) + 1
    return max(counts.values()) if counts else 0


class Map26InfoGain:
    """公开启发式：测试到候选唯一 → 换件 → 重启。"""

    name = "public_heuristic"

    def reset(self) -> None:
        self.queue: list[Action] = []

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        if self.queue:
            return self.queue.pop(0)
        candidates = set(observation["candidate_faults"])
        available = set(observation["available_tests"])
        if len(candidates) > 1 and available:
            test = min(
                available,
                key=lambda name: (_score(observation["test_partitions"], name, candidates), name),
            )
            return {"tool": "run_test", "test_id": test}
        fault = sorted(candidates)[0]
        part = PARTS[fault]
        if observation["installed_part"] != part:
            if observation["spares"].get(part, 0) <= 0:
                return {"tool": "restart"}
            return {"tool": "replace", "part_id": part}
        return {"tool": "restart"}


class Map26NoDiagnosis:
    """不测试，按 P1→P2→P3 盲换（V9 的旁路）。"""

    name = "no_diagnosis"

    def reset(self) -> None:
        self.index = 0
        self.mode = "replace"

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        order = ["P1", "P2", "P3"]
        if self.index >= len(order):
            return {"tool": "restart"}
        if self.mode == "replace":
            self.mode = "restart"
            return {"tool": "replace", "part_id": order[self.index]}
        self.mode = "replace"
        self.index += 1
        return {"tool": "restart"}


class Map26RollbackLoop:
    """诊断正确但由于回滚丢掉了备件，只能改用其它备件。"""

    name = "rollback_loop"

    def reset(self) -> None:
        self.queue: list[Action] = []
        self.rolled = False
        self.inner = Map26InfoGain()
        self.inner.reset()

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        payload = self.queue.pop(0) if self.queue else self.inner.act(observation, history)
        if payload["tool"] == "replace" and not self.rolled:
            self.rolled = True
            self.queue = [{"tool": "restart"}]
            return {"tool": "rollback"}
        return payload


class Map26TestButIgnore:
    """跑完测试但换一个错误备件。"""

    name = "test_but_ignore"

    def reset(self) -> None:
        return None

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        candidates = set(observation["candidate_faults"])
        available = set(observation["available_tests"])
        if len(candidates) > 1 and available:
            return {"tool": "run_test", "test_id": sorted(available)[0]}
        wrong = next(
            (
                PARTS[fault]
                for fault in FAULTS
                if fault not in candidates and observation["spares"].get(PARTS[fault], 0) > 0
            ),
            None,
        )
        if wrong is None:
            return {"tool": "restart"}
        if observation["installed_part"] != wrong:
            return {"tool": "replace", "part_id": wrong}
        return {"tool": "restart"}


HEURISTIC = Map26InfoGain
ABLATIONS: dict[str, type[Any]] = {
    "no_diagnosis": Map26NoDiagnosis,
    "test_but_ignore": Map26TestButIgnore,
}

__all__ = [
    "ABLATIONS",
    "HEURISTIC",
    "Map26InfoGain",
    "Map26NoDiagnosis",
    "Map26RollbackLoop",
    "Map26TestButIgnore",
    "oracle_actions",
]
