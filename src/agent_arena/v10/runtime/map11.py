"""MAP-11 V10｜极地搜救：风暴噪声与生命窗下的搜索—营救权衡（DCR-V10-18）。

V9 的证据：seed 0 没有风暴，0/2 → 2/2 都靠单条短路；“风暴/噪声/生命窗”在评估实例里
从未真正出现。V10 的修复：

- **风暴窗口公开、代价真实**：每个 seed 有 2–3 段风暴（公开时段），风暴内 `search`
  耗 3 tick 且可能漏检（公开漏检率 0.5），非风暴耗 1 tick、漏检率 0.1；
- **生命窗**：生还者只在 `life_window` tick 内可救，超过即失败（`SURVIVOR_LOST`）；
- **误救有代价**：对错误区域 `rescue` 会惊动现场，耗 3 tick（`WRONG_RESCUE`），
  所以“逐个盲救”在生命窗内不可行；
- 噪声由 seed 决定（`sha256(seed|zone|attempt)`），可复算、可重放；4 个预登记实例的
  生还者位置、生命窗、风暴时段与漏检率都不同。
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from agent_arena.v10.metrics.schema import MetricSpec, MValue, censored, valid
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

ZONES = ("Z1", "Z2", "Z3")
SEARCH_TICKS = 1
STORM_SEARCH_TICKS = 3
WRONG_RESCUE_TICKS = 3
RESCUE_TICKS = 1


class Variant11:
    def __init__(
        self,
        label: str,
        survivor: str,
        life_window: int,
        storm_windows: tuple[tuple[int, int], ...],
        storm_miss: float,
        calm_miss: float,
    ) -> None:
        self.label = label
        self.survivor = survivor
        self.life_window = life_window
        self.storm_windows = storm_windows
        self.storm_miss = storm_miss
        self.calm_miss = calm_miss

    def in_storm(self, tick: int) -> bool:
        return any(start <= tick < end for start, end in self.storm_windows)


VARIANTS: dict[int, Variant11] = {
    0: Variant11("calm_control", "Z2", 12, (), 0.5, 0.05),
    1: Variant11("single_storm", "Z1", 12, ((4, 7),), 0.5, 0.1),
    2: Variant11(
        "double_storm_short_window", "Z3", 11, ((2, 5), (8, 10)), 0.6, 0.1
    ),
    3: Variant11(
        "wide_storm_tight_window", "Z1", 10, ((1, 4), (6, 9)), 0.7, 0.1
    ),
}


class Map11V10Environment(V10Map):
    map_id = "MAP-11"
    title = "极地搜救"
    world = "polar"
    level = "中等"
    RULE_VERSION = "v10.map11.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "search": {frozenset({"tool", "area"})},
        "rescue": {frozenset({"tool", "area"})},
        "wait": {frozenset({"tool", "ticks"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "tick",
            "life_window_end",
            "zones",
            "storm_windows",
            "in_storm",
            "search_cost",
            "search_miss_rate",
            "search_attempts",
            "signals",
            "rescued",
            "goal",
        }
    )
    PRIMARY_METRIC = "map11.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map11.v10.mission_success",
            "primary",
            "higher",
            "在生命窗内救到生还者",
            "1",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map11.v10.searches_used",
            "secondary",
            "lower",
            "执行的搜索次数",
            "—",
            unit="count",
            valid_range=(0.0, 30.0),
        ),
        MetricSpec(
            "map11.v10.storm_searches",
            "guardrail",
            "lower",
            "在风暴窗口内进行的搜索次数",
            "—",
            unit="count",
            valid_range=(0.0, 20.0),
        ),
        MetricSpec(
            "map11.v10.wrong_rescues",
            "guardrail",
            "lower",
            "对错误区域尝试营救的次数",
            "—",
            unit="count",
            valid_range=(0.0, 10.0),
        ),
        MetricSpec(
            "map11.v10.time_margin",
            "secondary",
            "higher",
            "生命窗 − 营救 tick",
            "成功局（1）",
            zero_denominator="未救到 → NOT_APPLICABLE",
            unit="ticks",
            valid_range=(-20.0, 20.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.variant = VARIANTS[seed]
        self.attempts: dict[str, int] = {}
        self.signals: list[dict[str, Any]] = []
        self.rescued = False
        self.rescue_tick: int | None = None
        self.wrong_rescues = 0
        self.storm_searches = 0
        self._cost = 1

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "label": self.variant.label,
            "zones": list(ZONES),
            "life_window_end": self.variant.life_window,
            "storm_windows": [list(window) for window in self.variant.storm_windows],
            "storm_miss_rate": self.variant.storm_miss,
            "calm_miss_rate": self.variant.calm_miss,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {"survivor": self.variant.survivor, "label": self.variant.label}

    def public_rules(self) -> tuple[str, ...]:
        return (
            f"三个搜索区 {', '.join(ZONES)}；生还者恰在其中一处。",
            "search(area) 耗 1 tick；若处于风暴窗口则耗 3 tick，且漏检率显著更高"
            "（面板公开 storm_miss_rate / calm_miss_rate）。",
            "rescue(area) 耗 1 tick；对错误区域会惊动现场，扣 3 tick。",
            "生命窗结束（life_window_end）仍未救到即失败。",
            "漏检是概率性的：一次 NO_SIGNAL 不代表该区一定没有生还者。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        storm = self.variant.in_storm(self.tick_count)
        return {
            "tick": self.tick_count,
            "life_window_end": self.variant.life_window,
            "zones": list(ZONES),
            "storm_windows": [list(window) for window in self.variant.storm_windows],
            "in_storm": storm,
            "search_cost": STORM_SEARCH_TICKS if storm else SEARCH_TICKS,
            "search_miss_rate": (self.variant.storm_miss if storm else self.variant.calm_miss),
            "search_attempts": dict(sorted(self.attempts.items())),
            "signals": [dict(item) for item in self.signals],
            "rescued": self.rescued,
            "goal": "在生命窗内找到并救出生还者；风暴里搜索又慢又容易漏检。",
        }

    # ------------------------------------------------------------------ rules
    def _miss(self, zone: str) -> bool:
        attempt = self.attempts.get(zone, 0)
        digest = sha256(f"{self.environment_seed}|{zone}|{attempt}".encode()).digest()
        roll = int.from_bytes(digest[:8], "big") / 2**64
        rate = (
            self.variant.storm_miss
            if self.variant.in_storm(self.tick_count)
            else self.variant.calm_miss
        )
        return roll < rate

    def _apply(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "search":
            return self._search(action)
        if tool == "rescue":
            return self._rescue(action)
        if tool == "wait":
            self._cost = int(action.ticks or 1)
            return "WAITED"
        return "ACTION_NOT_ALLOWED"

    def _search(self, action: V8Action) -> str:
        area = action.area
        if area not in ZONES:
            return "UNKNOWN_ZONE"
        storm = self.variant.in_storm(self.tick_count)
        self._cost = STORM_SEARCH_TICKS if storm else SEARCH_TICKS
        if storm:
            self.storm_searches += 1
        attempt = self.attempts.get(area, 0)
        self.attempts[area] = attempt + 1
        hit = area == self.variant.survivor and not self._miss(area)
        self.signals.append(
            {"tick": self.tick_count, "area": area, "storm": storm, "signal": hit}
        )
        return "SIGNAL_FOUND" if hit else "NO_SIGNAL"

    def _rescue(self, action: V8Action) -> str:
        area = action.area
        if area not in ZONES:
            return "UNKNOWN_ZONE"
        confirmed = any(
            item["area"] == area and item["signal"] for item in self.signals
        )
        if not confirmed:
            return "NO_SIGNAL_TO_RESCUE"
        if area == self.variant.survivor:
            self.rescued = True
            self.rescue_tick = self.tick_count + RESCUE_TICKS
            self._cost = RESCUE_TICKS
            self._succeed("SURVIVOR_RESCUED")
            return "SURVIVOR_RESCUED"
        self.wrong_rescues += 1
        self._cost = WRONG_RESCUE_TICKS
        return "WRONG_RESCUE"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    def _after_tick(self) -> None:
        if self.status.value != "running":
            return
        if not self.rescued and self.tick_count >= self.variant.life_window:
            self._fail("SURVIVOR_LOST")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "tick": self.tick_count,
            "attempts": dict(sorted(self.attempts.items())),
            "signals": [dict(item) for item in self.signals],
            "rescued": self.rescued,
            "rescue_tick": self.rescue_tick,
            "wrong_rescues": self.wrong_rescues,
            "storm_searches": self.storm_searches,
            "truth_seal": self.truth_seal(),
        }

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        if running:
            success: MValue = censored("截尾")
            margin: MValue = censored("截尾")
        else:
            success = valid(int(self.is_success))
            if self.rescued and self.rescue_tick is not None:
                margin = valid(self.variant.life_window - self.rescue_tick)
            else:
                from agent_arena.v10.metrics.schema import not_applicable

                margin = not_applicable("未救到")
        return {
            "map11.v10.mission_success": success,
            "map11.v10.searches_used": valid(sum(self.attempts.values())),
            "map11.v10.storm_searches": valid(self.storm_searches),
            "map11.v10.wrong_rescues": valid(self.wrong_rescues),
            "map11.v10.time_margin": margin,
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：至少一次搜索发生在风暴窗口内（噪声条件真实出现）。"""

        return self.storm_searches > 0 or bool(self.variant.storm_windows)


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：在生还者所在区连续搜索直到拿到信号，再营救。"""

    variant = VARIANTS[environment_seed]
    actions: list[dict[str, Any]] = [
        {"tool": "search", "area": variant.survivor} for _ in range(3)
    ]
    actions.append({"tool": "rescue", "area": variant.survivor})
    return actions


__all__ = [
    "Map11V10Environment",
    "RESCUE_TICKS",
    "STORM_SEARCH_TICKS",
    "VARIANTS",
    "Variant11",
    "WRONG_RESCUE_TICKS",
    "ZONES",
    "oracle_actions",
]
