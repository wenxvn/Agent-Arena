"""V10 独立、fail-closed 的 append-only 预算账本。

与 V8/V9 账本的区别：

- V10 自己的文件与 experiment_id，不写入 ``runs/v8``、``runs/v9``；
- 登记的单请求输入上限为 16384 token（V10 公开规则 + Observation 比 V8 更长），
  输出上限 1024 token；预留按上限计算，结算按供应商真实 usage；
- **全局额度共享**：``prior_spend`` 由调用方传入（此前 V10 账本已结算 + 未知预留），
  本账本每次预留都把它计入，不允许通过拆分账本绕开 ¥10 上限；
- 未知消费（usage 缺失、传输结果未确认）立即封账，预留不释放；
- 记录 ``episode_started`` / ``episode_completed``，供逐局审计与幂等续跑。
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

CAP_CNY = Decimal("10")
MAX_EPISODES = 60
MAX_REQUESTS_GLOBAL = 3_000
MAX_INPUT_TOKENS_PER_REQUEST = 16_384
MAX_OUTPUT_TOKENS_PER_REQUEST = 1_024
WARN_FRACTIONS = (Decimal("0.50"), Decimal("0.80"))
PRICE_URL = "https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash"

_APPEND_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class PriceSheet:
    currency: str
    input_uncached_per_million: Decimal
    input_cached_per_million: Decimal
    output_per_million: Decimal

    def cost(self, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> Decimal:
        if min(input_tokens, output_tokens, cached_input_tokens) < 0:
            raise ValueError("Token usage cannot be negative.")
        if cached_input_tokens > input_tokens:
            raise ValueError("Cached input tokens cannot exceed total input tokens.")
        uncached = input_tokens - cached_input_tokens
        return (
            Decimal(uncached) * self.input_uncached_per_million
            + Decimal(cached_input_tokens) * self.input_cached_per_million
            + Decimal(output_tokens) * self.output_per_million
        ) / Decimal(1_000_000)

    def reserve_per_request(self) -> Decimal:
        return self.cost(MAX_INPUT_TOKENS_PER_REQUEST, MAX_OUTPUT_TOKENS_PER_REQUEST)


PRICE_SHEETS = {
    "CNY": PriceSheet(
        "CNY",
        input_uncached_per_million=Decimal("1"),
        input_cached_per_million=Decimal("0.02"),
        output_per_million=Decimal("2"),
    ),
}


class V10BudgetClosed(RuntimeError):
    """Raised when the V10 ledger must not send another provider request."""


def ledger_spend(path: Path) -> tuple[Decimal, Decimal, int]:
    """读取任一 V10/V9 格式账本：``(settled, pending_reserved, request_count)``。

    未知消费的失败请求保留预留（``full_reservation_retained``），因此按预留计入。
    """

    if not path.is_file():
        return Decimal(0), Decimal(0), 0
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    reserved = {
        str(event["request_id"]): Decimal(str(event["reserved_cost"]))
        for event in events
        if event["event"] == "request_reserved"
    }
    settled = Decimal(0)
    for event in events:
        if event["event"] == "request_settled":
            reserved.pop(str(event.get("request_id")), None)
            settled += Decimal(str(event.get("actual_cost", "0")))
        elif event["event"] == "request_failed" and not event.get("unknown_spend"):
            reserved.pop(str(event.get("request_id")), None)
    pending = sum(reserved.values(), Decimal(0))
    requests = sum(1 for event in events if event["event"] == "request_reserved")
    return settled, pending, requests


def global_spend(paths: list[Path]) -> tuple[Decimal, Decimal, int]:
    settled = pending = Decimal(0)
    requests = 0
    for path in paths:
        item_settled, item_pending, item_requests = ledger_spend(path)
        settled += item_settled
        pending += item_pending
        requests += item_requests
    return settled, pending, requests


class V10BudgetLedger:
    def __init__(
        self,
        path: Path,
        *,
        currency: str,
        model: str,
        source_hashes: dict[str, str],
        prior_spend: Decimal = Decimal(0),
        prior_requests: int = 0,
        resume: bool = False,
        max_cost: Decimal = CAP_CNY,
    ) -> None:
        if currency not in PRICE_SHEETS:
            raise ValueError("V10 计费货币必须是 CNY。")
        self.path = path.resolve()
        self.prices = PRICE_SHEETS[currency]
        self.model = model
        self.source_hashes = dict(source_hashes)
        self.max_cost = min(max_cost, CAP_CNY)
        self.prior_spend = Decimal(prior_spend)
        self.prior_requests = int(prior_requests)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if resume:
            if not self.path.is_file():
                raise FileNotFoundError("V10 账本不存在，无法恢复。")
            events = self.read_events()
            created = next(
                (event for event in events if event["event"] == "experiment_created"), None
            )
            if created is None:
                raise V10BudgetClosed("V10 账本缺少实验登记。")
            if (
                created.get("model") != model
                or created.get("currency") != currency
                or created.get("source_hashes") != self.source_hashes
            ):
                raise V10BudgetClosed("V10 恢复参数与账本不一致。")
            self.experiment_id = str(created["experiment_id"])
            self._audit_open_requests(events)
        else:
            if self.path.exists():
                raise FileExistsError("拒绝复用已存在的 V10 账本。")
            self.experiment_id = str(uuid4())
            self._append(
                "experiment_created",
                experiment_id=self.experiment_id,
                model=model,
                currency=currency,
                rates_per_million={
                    "input_uncached": str(self.prices.input_uncached_per_million),
                    "input_cached": str(self.prices.input_cached_per_million),
                    "output": str(self.prices.output_per_million),
                },
                price_source=PRICE_URL,
                source_hashes=self.source_hashes,
                max_episodes=MAX_EPISODES,
                max_requests_global=MAX_REQUESTS_GLOBAL,
                max_input_tokens_per_request=MAX_INPUT_TOKENS_PER_REQUEST,
                max_output_tokens_per_request=MAX_OUTPUT_TOKENS_PER_REQUEST,
                max_cost=str(self.max_cost),
                prior_spend=str(self.prior_spend),
                prior_requests=self.prior_requests,
                warn_fractions=[str(item) for item in WARN_FRACTIONS],
            )

    # ---------------------------------------------------------------- storage
    def read_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), 1
        ):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise V10BudgetClosed(f"V10 账本第 {line_number} 行损坏。") from exc
            if not isinstance(event, dict) or not isinstance(event.get("event"), str):
                raise V10BudgetClosed(f"V10 账本第 {line_number} 行记录非法。")
            events.append(event)
        return events

    def _append(self, event: str, **fields: Any) -> dict[str, Any]:
        row = {"at": _now(), "event": event, **fields}
        serialized = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with _APPEND_LOCK, self.path.open("ab") as stream:
            stream.write((serialized + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        return row

    def _audit_open_requests(self, events: list[dict[str, Any]]) -> None:
        pending: set[str] = set()
        for event in events:
            request_id = event.get("request_id")
            if not isinstance(request_id, str):
                continue
            if event["event"] == "request_reserved":
                pending.add(request_id)
            elif event["event"] in {"request_settled", "request_failed"}:
                pending.discard(request_id)
        if pending:
            self._append(
                "experiment_closed",
                reason="UNKNOWN_SPEND_AFTER_INTERRUPTED_REQUEST",
                unresolved_request_count=len(pending),
            )
            raise V10BudgetClosed("存在未结算请求，V10 账本关闭。")
        if any(event["event"] == "experiment_closed" for event in events):
            raise V10BudgetClosed("V10 账本已关闭，不能恢复。")

    @property
    def closed(self) -> bool:
        return any(event["event"] == "experiment_closed" for event in self.read_events())

    def _ensure_open(self) -> list[dict[str, Any]]:
        events = self.read_events()
        if any(event["event"] == "experiment_closed" for event in events):
            raise V10BudgetClosed("V10 实验账本已关闭。")
        return events

    # ---------------------------------------------------------------- episodes
    def start_episode(self, episode_id: str, *, map_id: str, seed: int, condition_id: str) -> None:
        events = self._ensure_open()
        started = {
            event.get("episode_id") for event in events if event["event"] == "episode_started"
        }
        completed = {
            event.get("episode_id") for event in events if event["event"] == "episode_completed"
        }
        if episode_id in completed:
            return
        if episode_id not in started and len(started) >= MAX_EPISODES:
            raise V10BudgetClosed("V10 登记 episode 上限已到。")
        if episode_id not in started:
            self._append(
                "episode_started",
                episode_id=episode_id,
                map_id=map_id,
                seed=seed,
                condition_id=condition_id,
            )

    def complete_episode(
        self, episode_id: str, *, status: str, success: bool, decision_count: int
    ) -> None:
        events = self._ensure_open()
        if any(
            event["event"] == "episode_completed" and event.get("episode_id") == episode_id
            for event in events
        ):
            return
        self._append(
            "episode_completed",
            episode_id=episode_id,
            status=status,
            success=success,
            decision_count=decision_count,
        )

    def completed_episode_ids(self) -> set[str]:
        return {
            str(event["episode_id"])
            for event in self.read_events()
            if event["event"] == "episode_completed"
        }

    # ---------------------------------------------------------------- budget
    def _pending_cost(self, events: list[dict[str, Any]]) -> Decimal:
        reserved = {
            str(event["request_id"]): Decimal(str(event["reserved_cost"]))
            for event in events
            if event["event"] == "request_reserved"
        }
        for event in events:
            if event["event"] == "request_settled":
                reserved.pop(str(event.get("request_id")), None)
            elif event["event"] == "request_failed" and not event.get("unknown_spend"):
                reserved.pop(str(event.get("request_id")), None)
        return sum(reserved.values(), Decimal(0))

    def _settled_cost(self, events: list[dict[str, Any]]) -> Decimal:
        return sum(
            (
                Decimal(str(event.get("actual_cost", "0")))
                for event in events
                if event["event"] == "request_settled"
            ),
            Decimal(0),
        )

    def projected_cost(self) -> Decimal:
        events = self.read_events()
        return self.prior_spend + self._settled_cost(events) + self._pending_cost(events)

    def remaining(self) -> Decimal:
        return self.max_cost - self.projected_cost()

    def reserve_request(
        self,
        episode_id: str,
        *,
        decision_index: int,
        request_hash: str,
        retry: bool = False,
    ) -> str:
        events = self._ensure_open()
        reservations = sum(1 for event in events if event["event"] == "request_reserved")
        if self.prior_requests + reservations >= MAX_REQUESTS_GLOBAL:
            self.close("GLOBAL_REQUEST_LIMIT")
            raise V10BudgetClosed("V10 全局请求上限已到。")
        projected = self.prior_spend + self._settled_cost(events) + self._pending_cost(events)
        if projected + self.prices.reserve_per_request() > self.max_cost:
            self.close("GLOBAL_COST_RESERVATION_LIMIT")
            raise V10BudgetClosed("V10 ¥10 硬上限将被突破。")
        request_id = str(uuid4())
        self._append(
            "request_reserved",
            request_id=request_id,
            episode_id=episode_id,
            decision_index=decision_index,
            request_hash=request_hash,
            retry=retry,
            max_input_tokens=MAX_INPUT_TOKENS_PER_REQUEST,
            max_output_tokens=MAX_OUTPUT_TOKENS_PER_REQUEST,
            reserved_cost=str(self.prices.reserve_per_request()),
            currency=self.prices.currency,
        )
        return request_id

    def settle_request(
        self,
        request_id: str,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        cached_input_tokens: int | None,
        latency_ms: int,
        decision_payload: dict[str, Any],
    ) -> None:
        events = self._ensure_open()
        reservation = next(
            (
                event
                for event in reversed(events)
                if event["event"] == "request_reserved" and event.get("request_id") == request_id
            ),
            None,
        )
        if reservation is None:
            self.close("SETTLEMENT_WITHOUT_RESERVATION", request_id=request_id)
            raise V10BudgetClosed("结算请求没有对应预留。")
        if input_tokens is None or output_tokens is None:
            self.close("UNKNOWN_PROVIDER_USAGE", request_id=request_id)
            raise V10BudgetClosed("供应商 usage 缺失，V10 账本关闭。")
        cached = cached_input_tokens if cached_input_tokens is not None else 0
        if (
            input_tokens < 0
            or output_tokens < 0
            or cached < 0
            or input_tokens > MAX_INPUT_TOKENS_PER_REQUEST
            or output_tokens > MAX_OUTPUT_TOKENS_PER_REQUEST
            or cached > input_tokens
        ):
            self.close("PROVIDER_USAGE_OUTSIDE_REGISTERED_CAP", request_id=request_id)
            raise V10BudgetClosed("供应商 usage 超出登记上限。")
        cost = self.prices.cost(input_tokens, output_tokens, cached)
        self._append(
            "request_settled",
            request_id=request_id,
            episode_id=reservation["episode_id"],
            decision_index=reservation["decision_index"],
            request_hash=reservation["request_hash"],
            decision_payload=decision_payload,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_usage_reported=cached_input_tokens is not None,
            latency_ms=latency_ms,
            actual_cost=str(cost),
            currency=self.prices.currency,
        )
        self._maybe_warn()

    def _maybe_warn(self) -> None:
        events = self.read_events()
        projected = self.prior_spend + self._settled_cost(events) + self._pending_cost(events)
        fraction = projected / self.max_cost
        already = {
            Decimal(str(event["fraction"]))
            for event in events
            if event["event"] == "budget_warning"
        }
        for threshold in WARN_FRACTIONS:
            if fraction >= threshold and threshold not in already:
                self._append(
                    "budget_warning",
                    fraction=str(threshold),
                    projected_cost=str(projected),
                    max_cost=str(self.max_cost),
                    currency=self.prices.currency,
                )

    def fail_request(
        self,
        request_id: str,
        *,
        error_category: str,
        latency_ms: int,
        retryable: bool,
        unknown_spend: bool = True,
    ) -> None:
        events = self._ensure_open()
        reservation = next(
            (
                event
                for event in reversed(events)
                if event["event"] == "request_reserved" and event.get("request_id") == request_id
            ),
            None,
        )
        if reservation is None:
            self.close("FAILURE_WITHOUT_RESERVATION", request_id=request_id)
            raise V10BudgetClosed("失败请求没有对应预留。")
        self._append(
            "request_failed",
            request_id=request_id,
            episode_id=reservation["episode_id"],
            decision_index=reservation["decision_index"],
            request_hash=reservation["request_hash"],
            error_category=error_category,
            latency_ms=latency_ms,
            retryable=retryable,
            unknown_spend=unknown_spend,
            full_reservation_retained=unknown_spend,
        )
        if unknown_spend:
            # 消费未知：保留预留并立即封账，不释放额度、不再自动发请求。
            self.close("UNKNOWN_PROVIDER_SPEND", request_id=request_id)

    def record(self, event: str, **fields: Any) -> dict[str, Any]:
        self._ensure_open()
        return self._append(event, **fields)

    def close(self, reason: str, **fields: Any) -> None:
        if not self.closed:
            self._append("experiment_closed", reason=reason, **fields)

    def consecutive_provider_errors(self) -> int:
        count = 0
        for event in self.read_events():
            if event["event"] == "request_failed":
                count += 1
            elif event["event"] == "request_settled":
                count = 0
        return count

    def episode_usage(self, episode_id: str) -> dict[str, Any]:
        events = self.read_events()
        settled = [
            event
            for event in events
            if event["event"] == "request_settled" and event.get("episode_id") == episode_id
        ]
        failed = [
            event
            for event in events
            if event["event"] == "request_failed" and event.get("episode_id") == episode_id
        ]
        cost = sum(
            (Decimal(str(event.get("actual_cost", "0"))) for event in settled), Decimal(0)
        )
        return {
            "requests": len(settled),
            "failed_requests": len(failed),
            "input_tokens": sum(int(event["input_tokens"]) for event in settled),
            "output_tokens": sum(int(event["output_tokens"]) for event in settled),
            "cached_input_tokens": sum(
                int(event.get("cached_input_tokens") or 0) for event in settled
            ),
            "cost": str(cost),
            "currency": self.prices.currency,
            "provider_wall_seconds": round(
                sum(
                    float(event.get("latency_ms", 0)) / 1000 for event in [*settled, *failed]
                ),
                3,
            ),
        }

    def snapshot(self) -> dict[str, Any]:
        events = self.read_events()
        return {
            "experiment_id": self.experiment_id,
            "currency": self.prices.currency,
            "max_cost": str(self.max_cost),
            "prior_spend": str(self.prior_spend),
            "settled_cost": str(self._settled_cost(events)),
            "pending_reserved_cost": str(self._pending_cost(events)),
            "projected_cost": str(
                self.prior_spend + self._settled_cost(events) + self._pending_cost(events)
            ),
            "request_attempts": sum(
                1 for event in events if event["event"] == "request_reserved"
            ),
            "settled_requests": sum(
                1 for event in events if event["event"] == "request_settled"
            ),
            "failed_requests": sum(
                1 for event in events if event["event"] == "request_failed"
            ),
            "episodes_started": sum(
                1 for event in events if event["event"] == "episode_started"
            ),
            "episodes_completed": sum(
                1 for event in events if event["event"] == "episode_completed"
            ),
            "warnings": [
                event["fraction"] for event in events if event["event"] == "budget_warning"
            ],
            "closed": any(event["event"] == "experiment_closed" for event in events),
        }


__all__ = [
    "CAP_CNY",
    "MAX_EPISODES",
    "MAX_INPUT_TOKENS_PER_REQUEST",
    "MAX_OUTPUT_TOKENS_PER_REQUEST",
    "MAX_REQUESTS_GLOBAL",
    "PRICE_SHEETS",
    "PriceSheet",
    "V10BudgetClosed",
    "V10BudgetLedger",
    "global_spend",
    "ledger_spend",
]
