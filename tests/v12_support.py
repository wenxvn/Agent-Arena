"""V12 测试共享工具：确定性 Provider、临时服务与配置构造。

不联网、不读本机 `.env`；所有 Provider 都是测试替身。
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from agent_arena.llm.protocol import DecisionRequest, ProviderResponse
from agent_arena.web.schemas import (
    OFFLINE_MODEL,
    OFFLINE_PROVIDER,
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
    RunConfig,
    RunMode,
)


class StubProvider:
    """按顺序返回固定候选；可注入异常或缺失 usage。"""

    def __init__(
        self,
        candidates: list[Any],
        *,
        input_tokens: int | None = 800,
        output_tokens: int | None = 120,
        error: Exception | None = None,
        error_after: int | None = None,
    ) -> None:
        self.candidates = list(candidates)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.error = error
        self.error_after = error_after
        self.calls: list[DecisionRequest] = []

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        self.calls.append(request)
        if self.error is not None and (
            self.error_after is None or len(self.calls) > self.error_after
        ):
            raise self.error
        index = len(self.calls) - 1
        candidate = self.candidates[index] if index < len(self.candidates) else {"tool": "__done__"}
        return ProviderResponse(
            candidate=candidate,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cached_input_tokens=0,
        )


def simulated_config(
    map_id: str,
    agent: str = "basic.v1",
    *,
    seed: int = 0,
    agent_config: dict[str, Any] | None = None,
    max_decisions: int = 20,
    max_requests: int = 60,
    max_input_tokens: int = 400_000,
    max_output_tokens: int = 8_000,
    max_cost_cny: str = "1.00",
    policy_seed: int = 0,
) -> RunConfig:
    return RunConfig(
        map_id=map_id,
        environment_seed=seed,
        mode=RunMode.SIMULATED,
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        agent=agent,
        agent_config=dict(agent_config or {}),
        policy_seed=policy_seed,
        max_decisions=max_decisions,
        max_requests=max_requests,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        max_cost_cny=Decimal(max_cost_cny),
    )


def live_config(
    map_id: str,
    agent: str = "basic.v1",
    *,
    seed: int = 0,
    agent_config: dict[str, Any] | None = None,
    max_decisions: int = 10,
    max_requests: int = 20,
    max_cost_cny: str = "1.00",
) -> RunConfig:
    return RunConfig(
        map_id=map_id,
        environment_seed=seed,
        mode=RunMode.LIVE,
        provider_id="openai_compatible",
        model="mimo-v2.6-flash",
        agent=agent,
        agent_config=dict(agent_config or {}),
        max_decisions=max_decisions,
        max_requests=max_requests,
        max_input_tokens=400_000,
        max_output_tokens=8_000,
        max_cost_cny=Decimal(max_cost_cny),
    )


def offline_config(map_id: str, *, seed: int = 0, max_decisions: int = 20) -> RunConfig:
    return RunConfig(
        map_id=map_id,
        environment_seed=seed,
        mode=RunMode.OFFLINE,
        provider_id=OFFLINE_PROVIDER,
        model=OFFLINE_MODEL,
        agent="public_heuristic_policy",
        max_decisions=max_decisions,
        max_requests=1,
        max_input_tokens=200_000,
        max_output_tokens=8_000,
        max_cost_cny=Decimal("0.01"),
    )


def run_dir(base: Path) -> Path:
    return base / "runs" / "web"


def lab_dir(base: Path) -> Path:
    return base / "runs" / "lab"


def no_leak(payload: Any) -> None:
    """断言公开载荷里没有隐藏真值/密钥键。"""

    import json

    text = json.dumps(payload, ensure_ascii=False, default=str).lower()
    for forbidden in (
        "sealed_truth",
        "truth_seal",
        "judge_state",
        "oracle_actions",
        "answer_key",
        "openai_api_key",
        "sk-",
    ):
        assert forbidden not in text, f"载荷泄露 {forbidden}"
