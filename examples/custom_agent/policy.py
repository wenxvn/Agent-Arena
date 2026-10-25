"""示例第三方策略：只读公开 Observation 的确定性策略。

- 不使用任何 Oracle 动作序列，也不读取隐藏真值；
- 默认**不调用模型**（零费用、可离线复现），因此可以直接放进 CI；
- 把 ``use_model=True`` 传入配置后才会通过 ``context.gateway`` 发一次真实请求
  （此时才会计入请求数、token 与费用）。

接入方式见 ``examples/custom_agent/README.md``。
"""

from __future__ import annotations

from typing import Any


class TestFirstPolicy:
    """“先测后动手”的通用公开策略（适用于带 available_tests 的地图）。"""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = dict(config or {})
        self.use_model = bool(self.config.get("use_model", False))
        self._history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ hooks
    def reset(self) -> None:
        self._history = []

    def close(self) -> None:
        self._history = []

    def observe_result(self, outcome: Any) -> None:
        entry = getattr(outcome, "history_entry", None)
        if callable(entry):
            self._history.append(entry())

    def decide(self, observation: dict[str, Any], context: Any) -> dict[str, Any]:
        if self.use_model:
            response = context.gateway.ask(
                _as_public(observation),
                purpose="decision",
                recent_history=context.recent_history_text(limit=5),
            )
            candidate = response.candidate
            if isinstance(candidate, dict) and isinstance(candidate.get("tool"), str):
                return dict(candidate)
            return {"tool": "__invalid__"}
        action = self._public_rule(observation)
        return action

    # ------------------------------------------------------------------ rules
    def _public_rule(self, observation: dict[str, Any]) -> dict[str, Any]:
        tests = [item for item in observation.get("available_tests") or [] if isinstance(item, str)]
        results = observation.get("test_results") or {}
        unused = [item for item in tests if item not in results]
        if unused:
            return {"tool": "run_test", "test_id": unused[0]}

        candidates = observation.get("candidate_sites") or observation.get("candidate_faults") or []
        if isinstance(candidates, list) and len(candidates) == 1:
            only = str(candidates[0])
            tools = _tools(observation)
            if observation.get("sealed_diagnosis") is None and "seal_diagnosis" in tools:
                return {"tool": "seal_diagnosis", "diagnosis_code": only}
            parts = observation.get("parts") or {}
            if isinstance(parts, dict) and only in parts:
                spares = observation.get("spares") or {}
                part = str(parts[only])
                if isinstance(spares, dict) and spares.get(part, 0) > 0:
                    return {"tool": "replace", "part_id": part}
            if "repair" in _tools(observation):
                return {"tool": "repair", "target_id": only}

        if "restart" in _tools(observation) and observation.get("installed_part"):
            return {"tool": "restart"}
        if "observe_signpost" in _tools(observation):
            return {"tool": "observe_signpost"}
        bearings = observation.get("bearings")
        if isinstance(bearings, list) and bearings:
            return {"tool": "move", "bearing": str(bearings[0])}
        return {"tool": "__no_public_action__"}


def _tools(observation: dict[str, Any]) -> set[str]:
    """示例策略用不到的私有契约；这里只用于判断“该动作是否可能被接受”。

    它只读取公开 Observation 的键名，不读取任何隐藏状态。
    """

    del observation
    return {
        "seal_diagnosis",
        "repair",
        "replace",
        "restart",
        "observe_signpost",
    }


def _as_public(observation: dict[str, Any]) -> Any:
    from agent_arena.lab.adapters import PublicObservation

    return PublicObservation.from_environment(observation)


def make_policy(config: dict[str, Any] | None = None) -> TestFirstPolicy:
    """注册表约定的工厂入口。"""

    return TestFirstPolicy(config)


__all__ = ["TestFirstPolicy", "make_policy"]
