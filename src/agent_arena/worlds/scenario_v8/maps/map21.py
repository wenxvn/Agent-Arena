"""MAP-21｜喷发倒计时：隐藏喷发时刻、贝叶斯测量与撤离停手决策。

本图与同世界另两图的机制差异：MAP-19/20 都是确定性的热/水控制题；本图没有
温度或流量，主机制是“喷发时刻只可能是 12/16/20 且不可见，唯一信息动作是一次
耗时 2 tick 的有噪测量”。玩家要在“多取一档样品”和“赶上最早喷发”之间停手。

指标口径（与 V7 卡片一致）：
- ``risk_exposure_integral`` = Σ_tick ``P(T <= t | 当前公开后验)``，只累计仍在 E
  之外且尚未死亡的 tick；抵 E 的 tick 不计，死亡 tick 计入。
- ``evacuation_coverage`` = 已撤出单位 / 已投入单位；单位 = 人员 1 + 已采样品 1
  + 已取得测量记录 1。
- ``false_safety_claims``：现有动作集没有“安全承诺”动作，按 V8-DCR-021 返回
  ``None``（UNAVAILABLE），不报假 0。
- ``late_evacuation``：终局为 ``FATAL_ERUPTION`` 记 1，成功撤离记 0，运行中为
  ``None``。
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.models import V8Action, V8Status

NODES = ("O", "R", "W", "S", "E")
EDGES: dict[str, tuple[str, str, int]] = {
    "O_R": ("O", "R", 1),
    "R_W": ("R", "W", 2),
    "W_S": ("W", "S", 2),
    "S_E": ("S", "E", 2),
    "O_E": ("O", "E", 6),
}
ERUPTION_TICKS = (12, 16, 20)
PRIOR = (0.2, 0.5, 0.3)
EARLY_LIKELIHOOD = (0.8, 0.3, 0.1)
EARLY_POSTERIOR = (8 / 17, 15 / 34, 3 / 34)
LATE_POSTERIOR = (2 / 33, 35 / 66, 9 / 22)
SAMPLES: dict[str, dict[str, Any]] = {
    "R_SURFACE_ASH": {"node": "R", "ticks": 1, "points": 5, "reinforced": 5},
    "W_LAYERED_CORE": {"node": "W", "ticks": 5, "points": 12, "reinforced": 20},
    "S_DEEP_ISOTOPE": {"node": "S", "ticks": 6, "points": 40, "reinforced": 50},
}


def _seed_fixture(seed: int) -> tuple[int, float]:
    """Deterministic hidden state: seed 0 matches the private V4 fixture."""

    if seed == 0:
        return 16, 0.42
    digest = sha256(f"map21|{seed}".encode()).digest()
    first = int.from_bytes(digest[:8], "big") / 2**64
    second = int.from_bytes(digest[8:16], "big") / 2**64
    cumulative = 0.0
    eruption = ERUPTION_TICKS[-1]
    for tick, weight in zip(ERUPTION_TICKS, PRIOR, strict=True):
        cumulative += weight
        if first < cumulative:
            eruption = tick
            break
    return eruption, second


class Map21Environment(MapEnvironment):
    map_id = "MAP-21"
    title = "喷发倒计时"
    world = "volcano"
    level = "困难"
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "edge_id"})},
        "measure": {frozenset({"tool"})},
        "reinforce_sample_case": {frozenset({"tool"})},
        "collect_and_carry_sample": {frozenset({"tool", "sample_id"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "elapsed_tick",
            "location",
            "in_transit_edge",
            "available_edges",
            "measurement_available",
            "returned_measurement",
            "posterior_over_eruption_ticks",
            "visible_local_sample_tier",
            "reinforcement_kit_available",
            "carried_sample_tier",
            "goal",
        }
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    def _reset_state(self, seed: int) -> None:
        self.eruption_tick, self.measurement_draw = _seed_fixture(seed)
        self.node = "O"
        self.measurement_used = False
        self.measurement_outcome: str | None = None
        self.posterior = list(PRIOR)
        self.reinforced_site: str | None = None
        self.carried_sample: str | None = None
        self.sample_points = 0
        self.sample_collected = False
        self.exposure = 0.0
        self.exposure_cursor = 0
        self.pending_move: dict[str, Any] | None = None
        self.terminal_score = 0
        self._cost = 0

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        edges = {
            edge_id: {"to": self._other(edge_id), "ticks": spec[2]}
            for edge_id, spec in sorted(EDGES.items())
            if self.node in spec[:2]
        }
        here = next(
            (
                {"sample_id": sample_id, "tier": sample_id.split("_")[0]}
                for sample_id, spec in SAMPLES.items()
                if spec["node"] == self.node and not self.sample_collected
            ),
            None,
        )
        return {
            "elapsed_tick": self.tick_count,
            "location": self.node,
            "in_transit_edge": (
                self.pending_move["edge_id"] if self.pending_move else None
            ),
            "available_edges": edges,
            "measurement_available": self.node == "O" and not self.measurement_used,
            "returned_measurement": self.measurement_outcome,
            "posterior_over_eruption_ticks": {
                str(tick): round(weight, 12)
                for tick, weight in zip(ERUPTION_TICKS, self.posterior, strict=True)
            },
            "visible_local_sample_tier": here,
            "reinforcement_kit_available": (
                self.reinforced_site is None and self.node in ("W", "S")
            ),
            "carried_sample_tier": self.carried_sample,
            "goal": (
                "在隐藏喷发时刻前进入 E 撤离；可选一次 2 tick 测量、一件样品和一次"
                " 1 tick 加固。喷发同步抵 E 时撤离优先。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _other(self, edge_id: str) -> str:
        a, b, _ = EDGES[edge_id]
        return b if self.node == a else a

    def _apply(self, action: V8Action) -> str:
        self._cost = 0
        if self.pending_move is not None:
            return "IN_TRANSIT"
        if action.tool == "move":
            return self._move(action)
        if action.tool == "measure":
            return self._measure()
        if action.tool == "reinforce_sample_case":
            return self._reinforce()
        if action.tool == "collect_and_carry_sample":
            return self._collect(action)
        return "ACTION_NOT_ALLOWED"

    def _move(self, action: V8Action) -> str:
        edge_id = action.edge_id
        if edge_id not in EDGES:
            return "INVALID_EDGE"
        a, b, ticks = EDGES[edge_id]
        if self.node not in (a, b):
            return "EDGE_NOT_ADJACENT"
        destination = b if self.node == a else a
        self._cost = ticks
        self.pending_move = {
            "edge_id": edge_id,
            "to": destination,
            "arrival": self.tick_count + ticks,
        }
        return f"MOVING:{edge_id}"

    def _measure(self) -> str:
        if self.node != "O":
            return "MEASUREMENT_ONLY_AT_O"
        if self.measurement_used:
            return "MEASUREMENT_ALREADY_USED"
        self._cost = 2
        self.measurement_used = True
        index = ERUPTION_TICKS.index(self.eruption_tick)
        outcome = (
            "EARLY_WARNING"
            if self.measurement_draw < EARLY_LIKELIHOOD[index]
            else "LATE_WARNING"
        )
        self.measurement_outcome = outcome
        posterior = (
            EARLY_POSTERIOR if outcome == "EARLY_WARNING" else LATE_POSTERIOR
        )
        self.posterior = list(posterior)
        return f"MEASURED:{outcome}"

    def _reinforce(self) -> str:
        if self.node not in ("W", "S"):
            return "REINFORCEMENT_ONLY_AT_W_OR_S"
        if self.reinforced_site is not None:
            return "REINFORCEMENT_KIT_USED"
        self._cost = 1
        self.reinforced_site = self.node
        return f"SAMPLE_CASE_REINFORCED:{self.node}"

    def _collect(self, action: V8Action) -> str:
        sample_id = action.sample_id
        if sample_id not in SAMPLES:
            return "INVALID_SAMPLE_ID"
        spec = SAMPLES[sample_id]
        if self.node != spec["node"]:
            return "SAMPLE_NOT_HERE"
        if self.sample_collected:
            return "SAMPLE_ALREADY_COLLECTED"
        self._cost = spec["ticks"]
        self.sample_collected = True
        self.carried_sample = sample_id
        reinforced = self.reinforced_site == self.node
        self.sample_points = spec["reinforced"] if reinforced else spec["points"]
        return f"SAMPLE_COLLECTED:{sample_id}"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    def _risk(self, tick: int) -> float:
        return sum(
            weight
            for threshold, weight in zip(ERUPTION_TICKS, self.posterior, strict=True)
            if threshold <= tick
        )

    def _after_tick(self) -> None:
        if self.status is not V8Status.RUNNING:
            return
        while self.exposure_cursor < self.tick_count:
            self.exposure_cursor += 1
            tick = self.exposure_cursor
            if self.pending_move is not None and tick >= self.pending_move["arrival"]:
                self.node = self.pending_move["to"]
                self.pending_move = None
            if self.node == "E":
                self._succeed("EVACUATED_BEFORE_ERUPTION")
                self.terminal_score = (
                    100 + self.sample_points + (2 if self.measurement_used else 0)
                )
                return
            self.exposure += self._risk(tick)
            if tick >= self.eruption_tick:
                self._fail("FATAL_ERUPTION")
                self.terminal_score = 0
                return

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "tick": self.tick_count,
            "location": self.node,
            "eruption_tick": self.eruption_tick,
            "measurement_outcome": self.measurement_outcome,
            "posterior": list(self.posterior),
            "carried_sample": self.carried_sample,
            "sample_points": self.sample_points,
            "reinforced_site": self.reinforced_site,
            "exposure": self.exposure,
            "terminal_score": self.terminal_score,
            "status": self.status.value,
            "terminal_reason": self.terminal_reason,
            "counters": dict(sorted(self.counters.items())),
        }

    def metrics(self) -> dict[str, Any]:
        invested = (
            1
            + (1 if self.sample_collected else 0)
            + (1 if self.measurement_used else 0)
        )
        evacuated = invested if self.is_success else 0
        return {
            "map21.risk_exposure_integral": round(self.exposure, 6),
            "map21.evacuation_coverage": {
                "numerator": evacuated,
                "denominator": invested,
            },
            "map21.false_safety_claims": None,
            "map21.late_evacuation": (
                None
                if self.status is V8Status.RUNNING
                else int(self.terminal_reason == "FATAL_ERUPTION")
            ),
        }


ORACLE_CASES: tuple[dict[str, Any], ...] = (
    {
        "trace_id": "exact_boundary_medium_sample",
        "seed": 0,
        "actions": [
            {"tool": "move", "edge_id": "O_R"},
            {"tool": "move", "edge_id": "R_W"},
            {"tool": "collect_and_carry_sample", "sample_id": "W_LAYERED_CORE"},
            {"tool": "move", "edge_id": "W_S"},
            {"tool": "move", "edge_id": "S_E"},
        ],
        "expect_success": True,
    },
    {
        "trace_id": "early_evacuation",
        "seed": 0,
        "actions": [{"tool": "move", "edge_id": "O_E"}],
        "expect_success": True,
    },
    {
        "trace_id": "deep_reinforced_sample",
        "seed": 0,
        "actions": [
            {"tool": "move", "edge_id": "O_R"},
            {"tool": "move", "edge_id": "R_W"},
            {"tool": "move", "edge_id": "W_S"},
            {"tool": "reinforce_sample_case"},
            {"tool": "collect_and_carry_sample", "sample_id": "S_DEEP_ISOTOPE"},
            {"tool": "move", "edge_id": "S_E"},
        ],
        "expect_success": True,
    },
)


FIXTURES = (
    {
        "name": "medium_sample_arrives_at_twelve",
        "seed": 0,
        "actions": list(ORACLE_CASES[0]["actions"]),
        "expect": {
            "map21.risk_exposure_integral": 0.0,
            "map21.evacuation_coverage": 1.0,
            "map21.late_evacuation": 0,
        },
    },
    {
        "name": "deep_sample_exposure_until_fourteen",
        "seed": 0,
        "actions": list(ORACLE_CASES[2]["actions"]),
        "expect": {
            "map21.risk_exposure_integral": 0.4,
            "map21.evacuation_coverage": 1.0,
            "map21.late_evacuation": 0,
        },
    },
    {
        "name": "staying_past_eruption_is_fatal",
        "seed": 0,
        "actions": [
            {"tool": "move", "edge_id": "O_R"},
            {"tool": "move", "edge_id": "R_W"},
            {"tool": "move", "edge_id": "W_S"},
            {"tool": "reinforce_sample_case"},
            {"tool": "collect_and_carry_sample", "sample_id": "S_DEEP_ISOTOPE"},
            {"tool": "move", "edge_id": "W_S"},
            {"tool": "move", "edge_id": "W_S"},
        ],
        "expect": {
            "map21.risk_exposure_integral": 1.5,
            "map21.evacuation_coverage": 0.0,
            "map21.late_evacuation": 1,
        },
    },
)


__all__ = ["FIXTURES", "ORACLE_CASES", "Map21Environment"]
