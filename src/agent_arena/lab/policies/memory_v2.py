"""``memory.v2``：可审计的路线记忆（P0-2 / V13-03-02 … 03-06）。

与 ``memory.v1`` 的差别（**默认行为不同，所以必须是新版本号**）：

| 维度 | ``memory.v1`` | ``memory.v2`` |
|---|---|---|
| 路线日志 | `route_log=False`（默认关） | `route_log=True`（默认开） |
| 路线写入机制 | 只有环境 `write_memory` 一种 | `route_mode` 显式选择 `env_write` / `context_only` |
| 循环/折返 | 不区分 | 记录 `loops` / `backtracks` / `retries` |
| 压缩/去重 | 无 | `compress` / `dedupe` 可关 |
| 相关性 | 无 | `relevance`：优先渲染路线与里程碑 |
| 诊断 | 只有规模 | 三类瓶颈分类（无记录 / 记录过短 / 记录未被引用） |

硬约束：

- 路线**只从被接受的公开 ``move`` 结果累积**；被拒/非法动作只计入 ``rejected``，
  绝不写进路线（否则"走过的路"会被伪造）；
- `route_mode=env_write` 时，写入是一次真实的 ``write_memory`` 动作，占用决策与
  动作预算，成功/失败都计入事件；`context_only` 时不发动作，机制标签不同，
  **两者不可互相冒充**；
- 渲染进 prompt 的文本有字符上限；本类不增加任何模型请求。
"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.adapters import (
    AgentContext,
    PublicActionResult,
    PublicEpisodeContext,
    PublicObservation,
)
from agent_arena.lab.contracts import AgentDecision, AgentEvent, AgentIdentity
from agent_arena.lab.policies.base import extract_action_candidate, memory_block
from agent_arena.lab.policies.memory import MILESTONE_FIELDS, _compact
from agent_arena.lab.registry import get_agent

ROUTE_MODE_ENV_WRITE = "env_write"
ROUTE_MODE_CONTEXT_ONLY = "context_only"
ROUTE_MODES = (ROUTE_MODE_ENV_WRITE, ROUTE_MODE_CONTEXT_ONLY)

OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}

#: 三类瓶颈（与 ``docs/v13/memory-study.md`` 的分类一致）。
BOTTLENECK_NONE = "NO_RECORD"
BOTTLENECK_SHORT = "RECORDED_TOO_SHORT"
BOTTLENECK_UNREFERENCED = "RECORDED_NOT_REFERENCED"
BOTTLENECK_OK = "RECORDED_AND_RENDERED"


class MemoryV2Policy:
    agent_id = "memory.v2"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        registration = get_agent(self.agent_id)
        self._identity = registration.identity
        self.config = registration.normalize_config(config)
        self.enabled = bool(self.config.get("enabled", True))
        self.capacity = max(1, int(self.config.get("capacity", 32)))
        self.max_chars = max(200, int(self.config.get("max_chars", 1_600)))
        self.history_window = int(self.config.get("history_window", 5))
        self.route_log = bool(self.config.get("route_log", True))
        self.route_mode = str(self.config.get("route_mode", ROUTE_MODE_ENV_WRITE))
        if self.route_mode not in ROUTE_MODES:
            raise ValueError(f"route_mode 只能是 {ROUTE_MODES}，收到 {self.route_mode}")
        self.route_write_every = max(1, int(self.config.get("route_write_every", 2)))
        self.route_write_limit = max(1, int(self.config.get("route_write_limit", 24)))
        self.compress = bool(self.config.get("compress", True))
        self.dedupe = bool(self.config.get("dedupe", True))
        self.relevance = bool(self.config.get("relevance", True))
        self._reset_state()

    def _reset_state(self) -> None:
        self._facts: dict[str, dict[str, Any]] = {}
        self._seq = 0
        self._updates = 0
        self._evictions = 0
        self._route: list[str] = []
        self._route_writes = 0
        self._pending_route_write = False
        self._write_attempts = 0
        self._write_accepted = 0
        self._write_rejected = 0
        self._rejected_moves = 0
        self._invalid_moves = 0
        self._loops = 0
        self._backtracks = 0
        self._render_count = 0
        self._last_block_chars = 0
        self._announced = False

    # ---------------------------------------------------------------- lifecycle
    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def reset(self, context: PublicEpisodeContext) -> None:
        self._reset_state()
        self._record("fact", "episode.map_id", context.map_id)
        self._record("fact", "episode.seed", context.environment_seed)
        self._record("fact", "episode.decision_budget", context.decision_budget)
        self._record("fact", "episode.route_mode", self.route_mode)

    def close(self) -> None:
        self._facts = {}

    # ------------------------------------------------------------------ memory
    def _record(self, kind: str, key: str, value: Any) -> str:
        self._seq += 1
        existing = self._facts.get(key)
        if existing is not None and existing["value"] == value:
            existing["seq"] = self._seq
            return "unchanged"
        if self.dedupe and existing is not None:
            # 去重：同一 key 的旧值被新值替换，不保留历史副本（避免容量被历史挤满）。
            self._facts[key] = {
                "kind": kind,
                "key": key,
                "value": value,
                "seq": self._seq,
            }
            return "updated"
        self._facts[key] = {
            "kind": kind,
            "key": key,
            "value": value,
            "seq": self._seq,
        }
        self._evict()
        return "updated" if existing is not None else "added"

    def _evict(self) -> None:
        while len(self._facts) > self.capacity:
            oldest = min(self._facts.values(), key=lambda item: int(item["seq"]))
            self._facts.pop(str(oldest["key"]), None)
            self._evictions += 1

    def _observe(self, observation: PublicObservation) -> dict[str, int]:
        counts = {"added": 0, "updated": 0, "evicted": 0}
        for key, value in sorted(observation.fields.items()):
            if key in {"goal", "agent_notes"}:
                continue
            compact = _compact(value, limit=200 if self.compress else 400)
            outcome = self._record("state", f"state.{key}", compact)
            if outcome == "added":
                counts["added"] += 1
            elif outcome == "updated":
                counts["updated"] += 1
            if key in MILESTONE_FIELDS and value:
                milestone = self._record(
                    "milestone", f"milestone.{key}", MILESTONE_FIELDS[key]
                )
                if milestone == "added":
                    counts["added"] += 1
        counts["evicted"] = self._evictions
        return counts

    def _observe_result(self, outcome: PublicActionResult) -> dict[str, int]:
        counts = {"added": 0, "updated": 0, "evicted": 0}
        tool = ""
        if isinstance(outcome.action, dict):
            tool = str(outcome.action.get("tool") or "")
        label = tool or "invalid"
        status = "rejected" if outcome.rejected else ("invalid" if outcome.invalid else "ok")
        key = f"result.{label}.{status}"
        previous = self._facts.get(key, {}).get("value", "0")
        try:
            total = int(previous) + 1
        except (TypeError, ValueError):
            total = 1
        kind = self._record("result", key, total)
        if kind in {"added", "updated"}:
            counts[kind] += 1
        if outcome.result:
            last = self._record("result", "result.last", f"{label}: {outcome.result}")
            if last in {"added", "updated"}:
                counts[last] += 1
        counts["evicted"] = self._evictions
        return counts

    # ------------------------------------------------------------------- route
    def _route_text(self) -> str:
        return ",".join(self._route)

    def _track_route(self, outcome: PublicActionResult) -> None:
        """只累积**被接受**的公开 move；被拒/非法只计数。"""

        action = outcome.action
        if not isinstance(action, dict) or action.get("tool") != "move":
            return
        if outcome.invalid:
            self._invalid_moves += 1
            return
        if outcome.rejected:
            self._rejected_moves += 1
            return
        bearing = action.get("bearing")
        if not isinstance(bearing, str):
            return
        if self._route and OPPOSITE.get(bearing) == self._route[-1]:
            self._backtracks += 1
        if bearing in self._route:
            self._loops += 1
        self._route.append(bearing)
        self._record("route", "route.path", self._route_text())
        self._record(
            "route",
            "route.stats",
            {
                "accepted": len(self._route),
                "rejected": self._rejected_moves,
                "invalid": self._invalid_moves,
                "loops": self._loops,
                "backtracks": self._backtracks,
            },
        )
        if len(self._route) % self.route_write_every == 0:
            if self.route_mode == ROUTE_MODE_ENV_WRITE:
                self._pending_route_write = True
            # context_only：不安排动作，只在下一轮决策的 memory 块里渲染。

    def _ordered(self) -> list[dict[str, Any]]:
        items = sorted(self._facts.values(), key=lambda item: -int(item["seq"]))
        if not self.relevance:
            return [dict(item) for item in items]
        # 相关性：路线与里程碑优先，其次最近状态，最后是结果计数。
        rank = {"route": 0, "milestone": 1, "state": 2, "result": 3, "fact": 4}

        def sort_key(item: dict[str, Any]) -> tuple[int, int]:
            return (rank.get(str(item.get("kind")), 9), -int(item["seq"]))

        return [dict(item) for item in sorted(items, key=sort_key)]

    # ------------------------------------------------------------------ decide
    def decide(
        self, observation: PublicObservation, context: AgentContext
    ) -> AgentDecision:
        counts = self._observe(observation)
        self._updates += counts["added"] + counts["updated"]

        # env_write 模式：这次决策是一次真实 write_memory 动作（0 请求，但占决策）。
        if self.enabled and self.route_log and self._pending_route_write:
            self._pending_route_write = False
            if self._route_writes < self.route_write_limit:
                self._route_writes += 1
                self._write_attempts += 1
                return AgentDecision(
                    action={
                        "tool": "write_memory",
                        "facts": [{"key": "path_state", "value": self._route_text()}],
                    },
                    decision_reason=None,
                    memory_event=AgentEvent(
                        kind="memory",
                        event="route_logged",
                        decision_index=context.decision_index,
                        summary=(
                            f"路线日志 #{self._route_writes}：写入 {len(self._route)} 个方位"
                            f"（机制 {self.route_mode}，占 1 次决策）。"
                        ),
                        payload={
                            "mechanism": self.route_mode,
                            "route_length": len(self._route),
                            "route_writes": self._route_writes,
                            "route_write_limit": self.route_write_limit,
                            "loops": self._loops,
                            "backtracks": self._backtracks,
                            "rejected_moves": self._rejected_moves,
                        },
                        requests=0,
                    ),
                    requests=0,
                )

        block = memory_block(self._ordered(), max_chars=self.max_chars) if self.enabled else None
        self._last_block_chars = len(block or "")
        if block:
            self._render_count += 1
        response = context.gateway.ask(
            observation,
            purpose="decision",
            memory_data=block,
            recent_history=context.recent_history_text(limit=self.history_window),
            correction=context.invalid_streak > 0,
            invalid_output_reason="schema" if context.invalid_streak else None,
            estimate_text=context.full_history_text(),
        )
        memory_event: AgentEvent | None = None
        if not self.enabled and not self._announced:
            self._announced = True
            memory_event = AgentEvent(
                kind="ablation",
                event="memory_disabled",
                decision_index=context.decision_index,
                summary="记忆关闭（消融臂）：仅使用 5 步公开历史。",
                payload={"enabled": False, "version": "v2"},
            )
        elif self.enabled and (counts["added"] or counts["updated"]):
            memory_event = AgentEvent(
                kind="memory",
                event="memory_updated",
                decision_index=context.decision_index,
                summary=(
                    f"记忆更新：新增 {counts['added']} 条、更新 {counts['updated']} 条，"
                    f"当前 {len(self._facts)} 条。"
                ),
                payload={
                    "added": counts["added"],
                    "updated": counts["updated"],
                    "evicted": counts["evicted"],
                    "size": len(self._facts),
                    "capacity": self.capacity,
                    "block_chars": self._last_block_chars,
                    "route_length": len(self._route),
                },
            )
        return AgentDecision(
            action=extract_action_candidate(response.candidate),
            decision_reason=None,
            memory_event=memory_event,
            requests=1,
        )

    def observe_result(self, outcome: PublicActionResult) -> None:
        if not self.enabled:
            return
        self._observe_result(outcome)
        # env_write 模式下的写入结果要单独记账（成功/被拒都算机制证据）。
        action = outcome.action
        if (
            isinstance(action, dict)
            and action.get("tool") == "write_memory"
            and self.route_mode == ROUTE_MODE_ENV_WRITE
        ):
            if outcome.rejected or outcome.invalid:
                self._write_rejected += 1
            else:
                self._write_accepted += 1
            return
        if self.route_log:
            self._track_route(outcome)

    # --------------------------------------------------------------- diagnostics
    def bottleneck(self) -> str:
        """三类记忆瓶颈的确定性分类（不含对模型心理的推断）。"""

        if not self.enabled:
            return "DISABLED"
        if not self._route and not self._write_attempts:
            return BOTTLENECK_NONE
        if self._route and self._write_attempts and self._write_accepted == 0:
            return "WRITE_REJECTED_INTERFACE"
        written = self._write_accepted if self.route_mode == ROUTE_MODE_ENV_WRITE else len(
            self._route
        )
        if self._route and written < max(3, len(self._route) // 2):
            return BOTTLENECK_SHORT
        if self._route and self._render_count == 0:
            return BOTTLENECK_UNREFERENCED
        return BOTTLENECK_OK

    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "version": "v2",
            "route_mode": self.route_mode,
            "route_log": self.route_log,
            "route_length": len(self._route),
            "route_writes": self._route_writes,
            "route_write_limit": self.route_write_limit,
            "write_attempts": self._write_attempts,
            "write_accepted": self._write_accepted,
            "write_rejected": self._write_rejected,
            "rejected_moves": self._rejected_moves,
            "invalid_moves": self._invalid_moves,
            "loops": self._loops,
            "backtracks": self._backtracks,
            "render_count": self._render_count,
            "block_chars": self._last_block_chars,
            "size": len(self._facts),
            "capacity": self.capacity,
            "updates": self._updates,
            "evictions": self._evictions,
            "bottleneck": self.bottleneck(),
            "route_preview": self._route_text()[:400],
        }


def make_memory_v2(config: dict[str, Any] | None = None) -> MemoryV2Policy:
    return MemoryV2Policy(config)


__all__ = [
    "BOTTLENECK_NONE",
    "BOTTLENECK_OK",
    "BOTTLENECK_SHORT",
    "BOTTLENECK_UNREFERENCED",
    "ROUTE_MODES",
    "ROUTE_MODE_CONTEXT_ONLY",
    "ROUTE_MODE_ENV_WRITE",
    "MemoryV2Policy",
    "make_memory_v2",
]
