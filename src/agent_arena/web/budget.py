"""V11 单局预算门禁：请求、token、费用三道硬限制。

费用限制只在能确认计价时启用（当前为 MiMo 公开价）。其它模型仍以请求数与
token 上限作为硬门禁，费用只显示“未知 / 不估算”，不假装能精确限制人民币。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from agent_arena.v10.ledger import PRICE_SHEETS, PriceSheet

MIMO_PRICE: PriceSheet = PRICE_SHEETS["CNY"]


class BudgetExceeded(RuntimeError):
    """预算门禁拒绝继续发送请求。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class UnknownUsageError(BudgetExceeded):
    """Provider 没有返回可确认的 usage；必须 fail-closed。"""


@dataclass(frozen=True)
class BudgetLimits:
    max_requests: int
    max_input_tokens: int
    max_output_tokens: int
    max_cost_cny: Decimal
    price: PriceSheet | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "max_requests": self.max_requests,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_cost_cny": str(self.max_cost_cny),
            "currency": self.price.currency if self.price else None,
            "cost_enforced": self.price is not None,
        }


def price_for_model(model: str) -> PriceSheet | None:
    """只有 MiMo 有本项目登记的公开价；其它模型不启用金额硬门禁。"""

    return MIMO_PRICE if "mimo" in model.lower() else None


class RunBudget:
    def __init__(self, limits: BudgetLimits) -> None:
        self.limits = limits
        self.requests = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost = Decimal(0)
        self.reserved_input = 0
        self.reserved_output = 0
        self.unknown_spend = False
        self.overrun = False
        self._open_reservation = False

    # ------------------------------------------------------------------ checks
    def reserve(self, *, estimated_input_tokens: int, output_limit: int) -> None:
        if self._open_reservation:
            raise BudgetExceeded("internal_double_reservation")
        if self.unknown_spend:
            raise BudgetExceeded("unknown_spend_closed")
        if self.requests + 1 > self.limits.max_requests:
            raise BudgetExceeded("request_limit_exceeded")
        if self.input_tokens + estimated_input_tokens > self.limits.max_input_tokens:
            raise BudgetExceeded("input_token_limit_exceeded")
        if self.output_tokens + output_limit > self.limits.max_output_tokens:
            raise BudgetExceeded("output_token_limit_exceeded")
        if self.limits.price is not None:
            projected = self.cost + self.limits.price.cost(estimated_input_tokens, output_limit)
            if projected > self.limits.max_cost_cny:
                raise BudgetExceeded("cost_limit_exceeded")
        self._open_reservation = True
        self.reserved_input = estimated_input_tokens
        self.reserved_output = output_limit

    def settle(
        self,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        cached_input_tokens: int | None = None,
    ) -> None:
        if not self._open_reservation:
            raise BudgetExceeded("settle_without_reservation")
        if input_tokens is None or output_tokens is None:
            self.unknown_spend = True
            self._open_reservation = False
            raise UnknownUsageError("unknown_provider_usage")
        if input_tokens < 0 or output_tokens < 0:
            self.unknown_spend = True
            self._open_reservation = False
            raise UnknownUsageError("negative_provider_usage")
        cached = max(0, cached_input_tokens or 0)
        if cached > input_tokens:
            self.unknown_spend = True
            self._open_reservation = False
            raise UnknownUsageError("cached_tokens_exceed_input")
        self._open_reservation = False
        self.reserved_input = 0
        self.reserved_output = 0
        self.requests += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        if self.limits.price is not None:
            self.cost += self.limits.price.cost(input_tokens, output_tokens, cached)
        if (
            self.requests > self.limits.max_requests
            or self.input_tokens > self.limits.max_input_tokens
            or self.output_tokens > self.limits.max_output_tokens
            or (
                self.limits.price is not None
                and self.cost > self.limits.max_cost_cny
            )
        ):
            self.overrun = True
            raise BudgetExceeded("provider_usage_exceeded_registered_cap")

    def fail(self, *, unknown_spend: bool) -> None:
        """失败结算：未知消费保留预留（防止重复计费），已知失败释放预留。"""

        if not self._open_reservation:
            return
        self._open_reservation = False
        if unknown_spend:
            self.unknown_spend = True
            # 保留 reserved_*，让快照显示“可能已消费”的上界。
        else:
            self.reserved_input = 0
            self.reserved_output = 0

    # ------------------------------------------------------------------ report
    def used_input_tokens(self) -> int:
        return self.input_tokens + self.reserved_input

    def used_output_tokens(self) -> int:
        return self.output_tokens + self.reserved_output

    def projected_cost(self) -> Decimal | None:
        if self.limits.price is None:
            return None
        reserve = (
            self.limits.price.cost(self.reserved_input, self.reserved_output)
            if self.reserved_input or self.reserved_output
            else Decimal(0)
        )
        return self.cost + reserve

    def remaining_cost(self) -> Decimal | None:
        projected = self.projected_cost()
        return None if projected is None else self.limits.max_cost_cny - projected

    def snapshot(self) -> dict[str, Any]:
        projected = self.projected_cost()
        return {
            **self.limits.public_dict(),
            "requests": self.requests,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reserved_input_tokens": self.reserved_input,
            "reserved_output_tokens": self.reserved_output,
            "cost_settled_cny": str(self.cost),
            "cost_projected_cny": None if projected is None else str(projected),
            "cost_unknown": self.unknown_spend,
            "overrun": self.overrun,
            "limits": self.limits.public_dict(),
        }


__all__ = [
    "MIMO_PRICE",
    "BudgetExceeded",
    "BudgetLimits",
    "RunBudget",
    "UnknownUsageError",
    "price_for_model",
]
