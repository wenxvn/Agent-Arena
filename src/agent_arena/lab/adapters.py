"""V10 公开契约与 Lab 策略公共上下文之间的桥。

安全边界（V12 硬约束）：

- 策略只能看到本回合公开 ``Observation``、公开动作契约、公开历史与 episode-local
  记忆/计划；看不到 ``judge_state`` / ``sealed_truth`` / Oracle 解；
- 策略不能持有 Environment 对象，也不能直接调用 Provider SDK；
- 所有落盘上下文都要能序列化，且经过 forbidden-key 扫描。

本模块只做**只读投影**，不修改 V10 运行时。
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

#: 绝不允许出现在策略可见上下文里的键（不区分大小写，按子串匹配）。
FORBIDDEN_PUBLIC_KEYS: tuple[str, ...] = (
    "sealed_truth",
    "truth_seal",
    "judge_state",
    "oracle",
    "answer_key",
    "ground_truth",
    "hidden_solution",
    "solution_path",
)

_CORE_FIELDS = frozenset({"map_id", "terminal", "terminal_reason", "last_action_result"})


class LeakageError(RuntimeError):
    """公共上下文里出现了隐藏真值字段。"""


def _scan(value: Any, *, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = str(key)
            lowered = name.lower()
            if any(forbidden in lowered for forbidden in FORBIDDEN_PUBLIC_KEYS):
                found.append(f"{path}.{name}" if path else name)
            found.extend(_scan(item, path=f"{path}.{name}" if path else name))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_scan(item, path=f"{path}[{index}]"))
    return found


def assert_public(payload: Any, *, where: str) -> None:
    """拒绝任何含隐藏真值键的公开载荷。"""

    hits = _scan(payload)
    if hits:
        raise LeakageError(f"{where} 含隐藏真值字段：{', '.join(sorted(set(hits))[:5])}")


@dataclass(frozen=True)
class PublicObservation:
    """一回合的公开观察：核心字段 + 该图声明的公开字段。"""

    map_id: str
    terminal: bool
    terminal_reason: str | None
    last_action_result: str
    fields: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_environment(cls, payload: Mapping[str, Any]) -> PublicObservation:
        data = dict(payload)
        assert_public(data, where="observation")
        map_id = str(data.get("map_id", ""))
        extras = {key: value for key, value in data.items() if key not in _CORE_FIELDS}
        return cls(
            map_id=map_id,
            terminal=bool(data.get("terminal")),
            terminal_reason=(
                None if data.get("terminal_reason") is None else str(data["terminal_reason"])
            ),
            last_action_result=str(data.get("last_action_result", "")),
            fields=extras,
        )

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "map_id": self.map_id,
            "terminal": self.terminal,
            "terminal_reason": self.terminal_reason,
            "last_action_result": self.last_action_result,
            **self.fields,
        }
        return payload

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True)

    def get(self, key: str, default: Any = None) -> Any:
        if key in _CORE_FIELDS:
            return getattr(self, key, default)
        return self.fields.get(key, default)


@dataclass(frozen=True)
class PublicActionResult:
    """一次已执行的公开动作结果（含非法/被拒标记）。"""

    decision_index: int
    action: dict[str, Any] | None
    result: str
    status: str
    rejected: bool
    invalid: bool
    terminal: bool
    observation: PublicObservation

    def history_entry(self) -> dict[str, Any]:
        """与 V11 ``execute_live`` 逐字一致的 5 步历史条目。"""

        action = (
            self.action
            if self.action is not None
            else {"invalid_output": "<unparsed>"}
        )
        return {"action": action, "result": self.result}

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_index": self.decision_index,
            "action": None if self.action is None else dict(self.action),
            "result": self.result,
            "status": self.status,
            "rejected": self.rejected,
            "invalid": self.invalid,
            "terminal": self.terminal,
        }


@dataclass(frozen=True)
class PublicEpisodeContext:
    """一局开始时交给策略的公共上下文（不含任何环境对象）。"""

    run_id: str
    experiment_id: str | None
    map_id: str
    environment_seed: int
    agent_id: str
    agent_version: str
    agent_config: Mapping[str, Any]
    decision_budget: int
    max_requests: int
    public_rules: tuple[str, ...]
    action_contract: str
    system_prompt: str
    history_window: int
    mode: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "map_id": self.map_id,
            "environment_seed": self.environment_seed,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "agent_config": dict(self.agent_config),
            "decision_budget": self.decision_budget,
            "max_requests": self.max_requests,
            "public_rules": list(self.public_rules),
            "action_contract": self.action_contract,
            "system_prompt": self.system_prompt,
            "history_window": self.history_window,
            "mode": self.mode,
        }


@dataclass(frozen=True)
class AgentContext:
    """每次 ``decide`` 的公共上下文；网关是唯一的模型调用出口。"""

    decision_index: int
    remaining_decisions: int
    history: tuple[PublicActionResult, ...]
    gateway: Any
    invalid_streak: int = 0
    reject_streak: int = 0
    no_progress_streak: int = 0
    #: 本局累计非法动作数（V11 ``execute_live`` 的 ``correction`` 判据）。
    invalid_total: int = 0

    def recent_history_text(self, *, limit: int = 5) -> str | None:
        if not self.history:
            return None
        window = self.history[-limit:] if limit else ()
        payload = [item.history_entry() for item in window]
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def full_history_text(self) -> str | None:
        """完整历史的 JSON（V11 的 token 预估口径用完整列表）。"""

        if not self.history:
            return None
        return json.dumps(
            [item.history_entry() for item in self.history], ensure_ascii=False
        )


def public_history(entries: Iterable[dict[str, Any]], *, limit: int = 5) -> str | None:
    """把公开历史条目渲染成模型可见文本（与 V11 窗口语义一致）。"""

    items = [dict(item) for item in entries]
    if not items:
        return None
    return json.dumps(items[-limit:] if limit else items, ensure_ascii=False, sort_keys=True)


__all__ = [
    "FORBIDDEN_PUBLIC_KEYS",
    "AgentContext",
    "LeakageError",
    "PublicActionResult",
    "PublicEpisodeContext",
    "PublicObservation",
    "assert_public",
    "public_history",
]
