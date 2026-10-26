"""``memory.v1``：结构化公开记忆。

只记录**公开**观察与动作结果，不读取隐藏真值：

- ``state.*``：公开观察字段的最新值（长结构压成摘要，不写全量）；
- ``result.*``：最近一次动作结果与被拒计数，便于避免重复被拒；
- ``milestone.*``：公开进度标志（如遗迹打卡、装件、链条核对）。

记忆按容量与字符上限淘汰（LRU），``enabled=False`` 时完全关闭并只发一条消融事件。
默认**不增加**模型请求，因此与 ``basic.v1`` 的差异只来自额外上下文。
"""

from __future__ import annotations

import json
from typing import Any

from agent_arena.lab.adapters import (
    AgentContext,
    PublicActionResult,
    PublicEpisodeContext,
    PublicObservation,
)
from agent_arena.lab.contracts import AgentDecision, AgentEvent, AgentIdentity
from agent_arena.lab.policies.base import extract_action_candidate, memory_block
from agent_arena.lab.registry import get_agent

#: 公开进度标志：出现即为里程碑（字段名来自各图 PUBLIC_FIELDS）。
MILESTONE_FIELDS: dict[str, str] = {
    "ruin_recorded": "遗迹已打卡",
    "sealed_diagnosis": "诊断已封存",
    "installed_part": "已安装备件",
    "chain_reconciled": "证据链已核对",
    "goal_recorded": "目标已记录",
    "recovery_status": "恢复状态变化",
}


def _compact(value: Any, *, limit: int = 160) -> str:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, (int, float, bool)) or value is None:
        return json.dumps(value)
    if isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if len(text) <= limit:
            return text
        return f"<dict {len(value)} keys>"
    if isinstance(value, (list, tuple)):
        text = json.dumps(list(value), ensure_ascii=False, default=str)
        if len(text) <= limit:
            return text
        return f"<list {len(value)} items>"
    return str(value)[:limit]


class MemoryPolicy:
    agent_id = "memory.v1"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        registration = get_agent(self.agent_id)
        self._identity = registration.identity
        self.config = registration.normalize_config(config)
        self.enabled = bool(self.config.get("enabled", True))
        self.capacity = max(1, int(self.config.get("capacity", 24)))
        self.max_chars = max(200, int(self.config.get("max_chars", 1_200)))
        self.history_window = int(self.config.get("history_window", 5))
        #: 路线日志（DCR-V12-03）：按步把方位写进环境 agent_notes 的 path_state。
        self.route_log = bool(self.config.get("route_log", False))
        self.route_write_every = max(1, int(self.config.get("route_write_every", 2)))
        self.route_write_limit = max(1, int(self.config.get("route_write_limit", 24)))
        self._route: list[str] = []
        self._route_writes = 0
        self._pending_route_write = False
        self._facts: dict[str, dict[str, Any]] = {}
        self._seq = 0
        self._updates = 0
        self._evictions = 0
        self._announced = False

    # ---------------------------------------------------------------- lifecycle
    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    def reset(self, context: PublicEpisodeContext) -> None:
        self._facts = {}
        self._seq = 0
        self._updates = 0
        self._evictions = 0
        self._announced = False
        self._route = []
        self._route_writes = 0
        self._pending_route_write = False
        self._record("fact", "episode.map_id", context.map_id)
        self._record("fact", "episode.seed", context.environment_seed)
        self._record("fact", "episode.decision_budget", context.decision_budget)

    def close(self) -> None:
        self._facts = {}

    # ------------------------------------------------------------------ memory
    def _record(self, kind: str, key: str, value: Any) -> str:
        """写入/更新一条记忆；返回 ``added`` / ``updated`` / ``unchanged``。"""

        self._seq += 1
        existing = self._facts.get(key)
        if existing is not None and existing["value"] == value:
            existing["seq"] = self._seq
            return "unchanged"
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
            if key in {"goal"}:
                continue
            compact = _compact(value)
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
        outcome_kind = self._record("result", key, total)
        if outcome_kind == "added":
            counts["added"] += 1
        elif outcome_kind == "updated":
            counts["updated"] += 1
        if outcome.result:
            last = self._record("result", "result.last", f"{label}: {outcome.result}")
            if last == "added":
                counts["added"] += 1
            elif last == "updated":
                counts["updated"] += 1
        counts["evicted"] = self._evictions
        return counts

    # ------------------------------------------------------------------ decide
    def decide(
        self, observation: PublicObservation, context: AgentContext
    ) -> AgentDecision:
        counts = self._observe(observation)
        self._updates += counts["added"] + counts["updated"]

        # 路线日志：本次决策若只是"把刚走过的方位写进环境"，不调用模型（0 请求）。
        if self.enabled and self.route_log and self._pending_route_write:
            self._pending_route_write = False
            if self._route_writes < self.route_write_limit:
                self._route_writes += 1
                value = ",".join(self._route)
                return AgentDecision(
                    action={
                        "tool": "write_memory",
                        "facts": [{"key": "path_state", "value": value}],
                    },
                    decision_reason=None,
                    memory_event=AgentEvent(
                        kind="memory",
                        event="route_logged",
                        decision_index=context.decision_index,
                        summary=f"路线日志 #{self._route_writes}：写入 {len(self._route)} 个方位。",
                        payload={
                            "route_length": len(self._route),
                            "route_writes": self._route_writes,
                            "route_write_limit": self.route_write_limit,
                        },
                        requests=0,
                    ),
                    requests=0,
                )

        block = memory_block(self._ordered(), max_chars=self.max_chars) if self.enabled else None
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
                payload={"enabled": False},
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
                    "block_chars": len(block or ""),
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
        # 记录被接受的 move 方位；达到写入间隔就安排一次 path_state 写入。
        action = outcome.action
        if (
            self.route_log
            and isinstance(action, dict)
            and action.get("tool") == "move"
            and not outcome.rejected
            and not outcome.invalid
        ):
            bearing = action.get("bearing")
            if isinstance(bearing, str):
                self._route.append(bearing)
                self._record("route", "route.path", ",".join(self._route))
                if len(self._route) % self.route_write_every == 0:
                    self._pending_route_write = True

    def _ordered(self) -> list[dict[str, Any]]:
        items = sorted(self._facts.values(), key=lambda item: -int(item["seq"]))
        return [dict(item) for item in items]

    # --------------------------------------------------------------- diagnostics
    def snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "size": len(self._facts),
            "capacity": self.capacity,
            "updates": self._updates,
            "evictions": self._evictions,
            "route_log": self.route_log,
            "route_length": len(self._route),
            "route_writes": self._route_writes,
            "facts": self._ordered(),
        }


__all__ = ["MILESTONE_FIELDS", "MemoryPolicy"]
