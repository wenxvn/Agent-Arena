"""受控模型调用网关：策略唯一的 Provider 出口。

设计要点：

- 每次请求都先 ``RunBudget.reserve`` 再 ``settle``；请求/token/费用三道门禁与 V11
  完全一致，Planner / Reflection 的额外调用**同样计费**；
- 未知 usage、未确认传输结果一律 fail-closed（``unknown_spend``），不自动重试；
- 网关只接收公开 ``PublicObservation``，不接收 Environment 或私有状态；
- 网关不保存 prompt 正文，只保存可审计的请求元数据。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from agent_arena.lab.adapters import PublicObservation
from agent_arena.llm.bailian import DecisionProviderError
from agent_arena.llm.protocol import DecisionProvider, DecisionRequest
from agent_arena.web.budget import BudgetExceeded, RunBudget, UnknownUsageError
from agent_arena.worlds.scenario_v8.models import V8Observation

MAX_ESTIMATED_INPUT_TOKENS = 16_384
MIN_ESTIMATED_INPUT_TOKENS = 512


class GatewayError(RuntimeError):
    """网关可预期失败；``category`` 写入终局码。"""

    def __init__(self, category: str, *, unknown_spend: bool = False) -> None:
        super().__init__(category)
        self.category = category
        self.unknown_spend = unknown_spend


class GatewayBudgetExceeded(GatewayError):
    """预算门禁拒绝继续发请求。"""


class GatewayProviderError(GatewayError):
    """Provider 失败或结果未确认。"""


@dataclass(frozen=True)
class GatewayResponse:
    candidate: Any
    input_tokens: int
    output_tokens: int
    latency_ms: int
    request_index: int


@dataclass
class GatewayStats:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    purposes: dict[str, int] = field(default_factory=dict)
    log: list[dict[str, Any]] = field(default_factory=list)

    def record(self, *, purpose: str, latency_ms: int, index: int) -> None:
        self.requests += 1
        self.latency_ms += latency_ms
        self.purposes[purpose] = self.purposes.get(purpose, 0) + 1
        self.log.append({"request_index": index, "purpose": purpose, "latency_ms": latency_ms})

    def snapshot(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "purposes": dict(self.purposes),
        }


def estimate_input_tokens(*parts: str | None) -> int:
    """保守估算输入 token（字节数 / 2），与 V11 同口径。"""

    text = "".join(part or "" for part in parts)
    return max(
        MIN_ESTIMATED_INPUT_TOKENS,
        min(MAX_ESTIMATED_INPUT_TOKENS, len(text.encode("utf-8")) // 2),
    )


class DecisionGateway:
    """把 Provider + 预算包装成一个只能被策略调用的方法。"""

    def __init__(
        self,
        provider: DecisionProvider,
        budget: RunBudget,
        *,
        system_prompt: str,
        output_limit: int,
        action_contract_version: str = "scenario_v4",
    ) -> None:
        self._provider = provider
        self._budget = budget
        self._system_prompt = system_prompt
        self._output_limit = output_limit
        self._action_contract_version = action_contract_version
        self.stats = GatewayStats()

    # ------------------------------------------------------------------ queries
    @property
    def requests(self) -> int:
        return self.stats.requests

    def snapshot(self) -> dict[str, Any]:
        return {**self._budget.snapshot(), **self.stats.snapshot()}

    # -------------------------------------------------------------------- calls
    def ask(
        self,
        observation: PublicObservation,
        *,
        purpose: str = "decision",
        memory_data: str | None = None,
        plan_data: str | None = None,
        recent_history: str | None = None,
        runtime_feedback: str | None = None,
        correction: bool = False,
        invalid_output_reason: str | None = None,
        output_contract: str = "action",
        max_output_tokens: int | None = None,
        system_prompt: str | None = None,
        estimate_text: str | None = None,
    ) -> GatewayResponse:
        """发送一次请求；任何不确定结果都抛 ``GatewayError``。"""

        prompt = system_prompt if system_prompt is not None else self._system_prompt
        observation_text = observation.as_json()
        # ``estimate_text`` 用于复刻 V11 的“完整历史”预估口径；此时不再叠加窗口文本。
        history_for_estimate = (
            estimate_text if estimate_text is not None else recent_history
        )
        estimated = estimate_input_tokens(
            prompt, observation_text, memory_data, plan_data, history_for_estimate
        )
        output_limit = min(max_output_tokens or self._output_limit, self._output_limit)
        try:
            self._budget.reserve(
                estimated_input_tokens=estimated, output_limit=output_limit
            )
        except BudgetExceeded as exc:
            raise GatewayBudgetExceeded(exc.reason) from exc

        request = DecisionRequest(
            observation=V8Observation(**observation.as_dict()),
            system_prompt=prompt,
            correction=correction,
            memory_data=memory_data,
            runtime_feedback=runtime_feedback,
            invalid_output_reason=invalid_output_reason,
            recent_history=recent_history,
            output_contract=output_contract,  # type: ignore[arg-type]
            plan_data=plan_data,
            max_output_tokens=output_limit,
            action_contract_version=self._action_contract_version,  # type: ignore[arg-type]
        )
        started = time.monotonic()
        try:
            response = self._provider.decide(request)
        except DecisionProviderError as exc:
            self._budget.fail(unknown_spend=exc.unknown_spend)
            raise GatewayProviderError(
                exc.error_category, unknown_spend=bool(exc.unknown_spend)
            ) from exc
        except Exception as exc:  # noqa: BLE001 - unconfirmed transport outcome
            self._budget.fail(unknown_spend=True)
            raise GatewayProviderError(
                type(exc).__name__, unknown_spend=True
            ) from exc
        latency = max(0, round((time.monotonic() - started) * 1000))
        try:
            self._budget.settle(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_input_tokens=response.cached_input_tokens,
            )
        except UnknownUsageError as exc:
            raise GatewayProviderError(
                "unknown_provider_usage", unknown_spend=True
            ) from exc
        except BudgetExceeded as exc:
            raise GatewayBudgetExceeded(
                f"provider_usage_exceeded_registered_cap:{exc.reason}"
            ) from exc

        index = self.stats.requests + 1
        self.stats.input_tokens += int(response.input_tokens or 0)
        self.stats.output_tokens += int(response.output_tokens or 0)
        self.stats.record(purpose=purpose, latency_ms=latency, index=index)
        return GatewayResponse(
            candidate=response.candidate,
            input_tokens=int(response.input_tokens or 0),
            output_tokens=int(response.output_tokens or 0),
            latency_ms=latency,
            request_index=index,
        )

    def ask_json(
        self, observation: PublicObservation, *, purpose: str, **kwargs: Any
    ) -> tuple[dict[str, Any], GatewayResponse]:
        """请求一个 JSON 对象；非对象输出视为空对象（由调用方降级）。"""

        response = self.ask(observation, purpose=purpose, **kwargs)
        candidate = response.candidate
        if isinstance(candidate, dict):
            return dict(candidate), response
        if isinstance(candidate, str):
            try:
                parsed = json.loads(candidate)
            except ValueError:
                return {}, response
            if isinstance(parsed, dict):
                return parsed, response
        return {}, response


__all__ = [
    "DecisionGateway",
    "GatewayBudgetExceeded",
    "GatewayError",
    "GatewayProviderError",
    "GatewayResponse",
    "GatewayStats",
    "estimate_input_tokens",
]
