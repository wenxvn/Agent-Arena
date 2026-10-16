"""Fail-closed budget ledger for the separately registered V6 pilot.

Independent of the closed V2 and V5 ledgers: V6 uses its own namespace, caps,
and registry, and never opens or mutates a historical ledger.
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

MAX_EPISODES = 47
MAX_DECISIONS_PER_EPISODE = 100
MAX_RETRIES_PER_EPISODE = 1
MAX_REQUESTS_PER_EPISODE = MAX_DECISIONS_PER_EPISODE + MAX_RETRIES_PER_EPISODE
MAX_REQUESTS_GLOBAL = 1_000
MAX_INPUT_TOKENS_PER_REQUEST = 8_192
MAX_OUTPUT_TOKENS_PER_REQUEST = 1_024
MAX_RESERVED_TOKENS_GLOBAL = MAX_REQUESTS_GLOBAL * (
    MAX_INPUT_TOKENS_PER_REQUEST + MAX_OUTPUT_TOKENS_PER_REQUEST
)
MAX_EPISODE_SECONDS = 12 * 60
MAX_PROVIDER_SECONDS_GLOBAL = 180 * 60
PRICE_URL = "https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash"


@dataclass(frozen=True)
class PriceSheet:
    currency: str
    input_uncached_per_million: Decimal
    input_cached_per_million: Decimal
    output_per_million: Decimal
    max_cost: Decimal

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
        max_cost=Decimal("11.00"),
    ),
    "USD": PriceSheet(
        "USD",
        input_uncached_per_million=Decimal("0.14"),
        input_cached_per_million=Decimal("0.0028"),
        output_per_million=Decimal("0.28"),
        max_cost=Decimal("1.44"),
    ),
}

_APPEND_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class PilotBudgetClosed(RuntimeError):
    """Raised when a V6 ledger must not send another Provider request."""


class V6BudgetLedger:
    """Append-only local ledger; it never opens or mutates V2/V5 ledgers."""

    def __init__(
        self,
        path: Path,
        *,
        currency: str,
        model: str,
        source_hashes: dict[str, str],
        resume: bool = False,
    ) -> None:
        if currency not in PRICE_SHEETS:
            raise ValueError("Billing currency must be CNY or USD.")
        self.path = path.resolve()
        self.prices = PRICE_SHEETS[currency]
        self.model = model
        self.source_hashes = dict(source_hashes)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if resume:
            if not self.path.is_file():
                raise FileNotFoundError("The requested V6 ledger does not exist.")
            events = self.read_events()
            created = next((event for event in events if event["event"] == "pilot_created"), None)
            if created is None:
                raise PilotBudgetClosed("V6 ledger has no valid pilot registration.")
            if created.get("model") != model or created.get("currency") != currency:
                raise PilotBudgetClosed("V6 resume settings do not match the original ledger.")
            if created.get("source_hashes") != self.source_hashes:
                raise PilotBudgetClosed("V6 source hashes changed since the ledger was created.")
            self.experiment_id = str(created["experiment_id"])
            self._audit_open_requests(events)
        else:
            if self.path.exists():
                raise FileExistsError("Refusing to reuse an existing V6 ledger.")
            self.experiment_id = str(uuid4())
            self._append(
                "pilot_created",
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
                max_reserved_tokens_global=MAX_RESERVED_TOKENS_GLOBAL,
                max_episode_seconds=MAX_EPISODE_SECONDS,
                max_provider_seconds_global=MAX_PROVIDER_SECONDS_GLOBAL,
                max_cost=str(self.prices.max_cost),
            )

    def read_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PilotBudgetClosed(f"V6 ledger is malformed at line {line_number}.") from exc
            if not isinstance(event, dict) or not isinstance(event.get("event"), str):
                raise PilotBudgetClosed(f"V6 ledger has an invalid record at line {line_number}.")
            events.append(event)
        return events

    def _append(self, event: str, **fields: Any) -> dict[str, Any]:
        row = {"at": _now(), "event": event, **fields}
        serialized = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        encoded = (serialized + "\n").encode("utf-8")
        with _APPEND_LOCK, self.path.open("ab") as stream:
            stream.write(encoded)
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
                "pilot_closed",
                reason="UNKNOWN_SPEND_AFTER_INTERRUPTED_REQUEST",
                unresolved_request_count=len(pending),
            )
            raise PilotBudgetClosed("An interrupted request has unknown spend; V6 pilot is closed.")
        if any(event["event"] == "pilot_closed" for event in events):
            raise PilotBudgetClosed("The V6 pilot ledger is closed and cannot be resumed.")

    @property
    def closed(self) -> bool:
        return any(event["event"] == "pilot_closed" for event in self.read_events())

    def _ensure_open(self) -> list[dict[str, Any]]:
        events = self.read_events()
        if any(event["event"] == "pilot_closed" for event in events):
            raise PilotBudgetClosed("The V6 pilot ledger is closed.")
        return events

    def start_episode(self, episode_id: str, *, map_id: str, seed: int, condition_id: str) -> None:
        events = self._ensure_open()
        existing = {
            event.get("episode_id") for event in events if event["event"] == "episode_started"
        }
        completed = {
            event.get("episode_id") for event in events if event["event"] == "episode_completed"
        }
        if episode_id in completed:
            return
        if episode_id not in existing and len(existing) >= MAX_EPISODES:
            raise PilotBudgetClosed("The registered V6 episode limit has been reached.")
        if episode_id not in existing:
            self._append(
                "episode_started",
                episode_id=episode_id,
                map_id=map_id,
                seed=seed,
                condition_id=condition_id,
            )

    def reserve_request(
        self,
        episode_id: str,
        *,
        decision_index: int,
        request_hash: str,
        retry: bool = False,
    ) -> str:
        events = self._ensure_open()
        reservations = [event for event in events if event["event"] == "request_reserved"]
        episode_reservations = [
            event for event in reservations if event.get("episode_id") == episode_id
        ]
        if len(reservations) >= MAX_REQUESTS_GLOBAL:
            self.close("GLOBAL_REQUEST_LIMIT")
            raise PilotBudgetClosed("Global request attempt limit reached.")
        if len(episode_reservations) >= MAX_REQUESTS_PER_EPISODE:
            self.close("EPISODE_REQUEST_LIMIT")
            raise PilotBudgetClosed("Episode request attempt limit reached.")
        next_reserved_tokens = (
            len(reservations) * (MAX_INPUT_TOKENS_PER_REQUEST + MAX_OUTPUT_TOKENS_PER_REQUEST)
            + MAX_INPUT_TOKENS_PER_REQUEST
            + MAX_OUTPUT_TOKENS_PER_REQUEST
        )
        if next_reserved_tokens > MAX_RESERVED_TOKENS_GLOBAL:
            self.close("GLOBAL_TOKEN_RESERVATION_LIMIT")
            raise PilotBudgetClosed("Global reserved token limit reached.")
        reserved_cost = sum(
            (Decimal(str(event["reserved_cost"])) for event in reservations), Decimal(0)
        )
        next_cost = reserved_cost + self.prices.reserve_per_request()
        if next_cost > self.prices.max_cost:
            self.close("GLOBAL_COST_RESERVATION_LIMIT")
            raise PilotBudgetClosed("Global cost reservation limit reached.")
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
        reservation = next(
            (
                event
                for event in reversed(self.read_events())
                if event["event"] == "request_reserved" and event.get("request_id") == request_id
            ),
            None,
        )
        if reservation is None:
            self.close("SETTLEMENT_WITHOUT_RESERVATION", request_id=request_id)
            raise PilotBudgetClosed("Provider usage has no matching V6 reservation.")
        if input_tokens is None or output_tokens is None:
            self.close("UNKNOWN_PROVIDER_USAGE", request_id=request_id)
            raise PilotBudgetClosed("Provider usage is unknown; the full V6 pilot is closed.")
        cached_tokens_for_cost = cached_input_tokens if cached_input_tokens is not None else 0
        if (
            input_tokens < 0
            or output_tokens < 0
            or cached_tokens_for_cost < 0
            or input_tokens > MAX_INPUT_TOKENS_PER_REQUEST
            or output_tokens > MAX_OUTPUT_TOKENS_PER_REQUEST
            or cached_tokens_for_cost > input_tokens
        ):
            self.close("PROVIDER_USAGE_OUTSIDE_REGISTERED_CAP", request_id=request_id)
            raise PilotBudgetClosed("Provider usage exceeded or violated the V6 request cap.")
        cost = self.prices.cost(input_tokens, output_tokens, cached_tokens_for_cost)
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
        reserved = sum(
            (
                Decimal(str(event["reserved_cost"]))
                for event in self.read_events()
                if event["event"] == "request_reserved"
            ),
            Decimal(0),
        )
        if reserved > self.prices.max_cost:
            self.close("GLOBAL_COST_RESERVATION_LIMIT")
            raise PilotBudgetClosed("Global cost reservation limit reached.")

    def fail_request(
        self,
        request_id: str,
        *,
        error_category: str,
        latency_ms: int,
        retryable: bool,
        unknown_spend: bool = True,
    ) -> None:
        reservation = next(
            (
                event
                for event in reversed(self.read_events())
                if event["event"] == "request_reserved" and event.get("request_id") == request_id
            ),
            None,
        )
        if reservation is None:
            self.close("FAILURE_WITHOUT_RESERVATION", request_id=request_id)
            raise PilotBudgetClosed("Provider error has no matching V6 reservation.")
        self._append(
            "request_failed",
            request_id=request_id,
            episode_id=reservation["episode_id"],
            decision_index=reservation["decision_index"],
            request_hash=reservation["request_hash"],
            retry=reservation["retry"],
            error_category=error_category,
            latency_ms=latency_ms,
            retryable=retryable,
            unknown_spend=unknown_spend,
            full_reservation_retained=True,
        )

    def record(self, event: str, **fields: Any) -> dict[str, Any]:
        self._ensure_open()
        return self._append(event, **fields)

    def close(self, reason: str, **fields: Any) -> None:
        if not self.closed:
            self._append("pilot_closed", reason=reason, **fields)

    def completed_episode_ids(self) -> set[str]:
        return {
            str(event["episode_id"])
            for event in self.read_events()
            if event["event"] == "episode_completed"
        }

    def consecutive_errors(self) -> int:
        count = 0
        for event in self.read_events():
            if event["event"] == "request_failed":
                count += 1
            elif event["event"] == "request_settled":
                count = 0
        return count

    def provider_wall_seconds(self) -> float:
        return sum(
            float(event.get("latency_ms", 0)) / 1_000
            for event in self.read_events()
            if event["event"] in {"request_settled", "request_failed"}
        )

    def snapshot(self) -> dict[str, object]:
        events = self.read_events()
        reservations = [event for event in events if event["event"] == "request_reserved"]
        actual_cost = sum(
            (
                Decimal(str(event.get("actual_cost", "0")))
                for event in events
                if event["event"] == "request_settled"
            ),
            Decimal(0),
        )
        reserved_cost = sum(
            (Decimal(str(event.get("reserved_cost", "0"))) for event in reservations), Decimal(0)
        )
        return {
            "experiment_id": self.experiment_id,
            "currency": self.prices.currency,
            "request_attempts": len(reservations),
            "reserved_tokens": len(reservations)
            * (MAX_INPUT_TOKENS_PER_REQUEST + MAX_OUTPUT_TOKENS_PER_REQUEST),
            "reserved_cost": str(reserved_cost),
            "actual_cost_from_reported_usage": str(actual_cost),
            "provider_wall_seconds": round(self.provider_wall_seconds(), 3),
            "closed": any(event["event"] == "pilot_closed" for event in events),
        }
