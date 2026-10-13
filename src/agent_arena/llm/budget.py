"""Fail-closed request and token budgets for bounded provider experiments."""

from __future__ import annotations

import json
import math
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from time import time
from typing import Any, cast
from uuid import uuid4

from agent_arena.llm.protocol import (
    DecisionProvider,
    DecisionRequest,
    ProviderResponse,
    candidate_selection_response_schema,
    decision_response_schema,
    decision_response_schema_strict,
    planner_response_schema,
    planner_response_schema_strict,
)


class ProviderBudgetExceeded(RuntimeError):
    """Raised when a request must be stopped before it reaches a provider."""


class _FileLockUnavailable(RuntimeError):
    """Internal signal used when a non-blocking OS file lock is already held."""


_REQUEST_LEASE_GUARD = threading.Lock()
_ACTIVE_REQUEST_LEASES: set[str] = set()
_SAFE_PROVIDER_ERROR_CATEGORIES = frozenset(
    {"connection", "http_status", "invalid_response", "provider_error", "timeout"}
)
_TIMEOUT_EXCEPTION_NAMES = frozenset(
    {
        "APITimeoutError",
        "ConnectTimeout",
        "PoolTimeout",
        "ReadTimeout",
        "TimeoutError",
        "WriteTimeout",
    }
)
_CONNECTION_EXCEPTION_NAMES = frozenset(
    {
        "APIConnectionError",
        "ConnectError",
        "ConnectionError",
        "NetworkError",
        "ReadError",
        "RemoteProtocolError",
        "WriteError",
    }
)


def _exception_chain(error: BaseException) -> Iterator[BaseException]:
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _safe_provider_error_details(error: BaseException) -> tuple[str, int | None]:
    chain = tuple(_exception_chain(error))
    names = {type(item).__name__ for item in chain}
    if any(isinstance(item, TimeoutError) for item in chain) or names & _TIMEOUT_EXCEPTION_NAMES:
        return "timeout", None

    for item in chain:
        try:
            status = getattr(item, "status_code", None)
            if type(status) is not int:
                response = getattr(item, "response", None)
                status = getattr(response, "status_code", None)
        except Exception:
            continue
        if type(status) is int and 400 <= status <= 599:
            return "http_status", status

    has_connection_error = any(isinstance(item, ConnectionError) for item in chain)
    if has_connection_error or names & _CONNECTION_EXCEPTION_NAMES:
        return "connection", None
    if any(isinstance(item, json.JSONDecodeError) for item in chain):
        return "invalid_response", None
    return "provider_error", None


@dataclass(frozen=True)
class ProviderBudgetLimits:
    experiment_id: str
    expected_provider: str
    expected_model: str
    expected_world_definition_hash: str
    expected_base_prompt_hash: str
    max_requests: int
    max_tokens: int
    max_output_tokens_per_request: int
    timeout_seconds: int
    input_overhead_tokens: int = 16_384

    def __post_init__(self) -> None:
        identity_values = (
            self.experiment_id,
            self.expected_provider,
            self.expected_model,
            self.expected_world_definition_hash,
            self.expected_base_prompt_hash,
        )
        if any(not value.strip() for value in identity_values):
            raise ValueError("Frozen budget experiment identity fields must not be empty.")
        if (
            min(
                self.max_requests,
                self.max_tokens,
                self.max_output_tokens_per_request,
                self.timeout_seconds,
                self.input_overhead_tokens,
            )
            <= 0
        ):
            raise ValueError("Provider budget limits must all be positive.")


@dataclass(frozen=True)
class ProviderBudgetReservation:
    request_id: str
    input_token_upper_bound: int
    output_token_limit: int
    reserved_tokens: int


@dataclass(frozen=True)
class ProviderBudgetSnapshot:
    experiment_id: str
    requests_used: int
    tokens_used: int
    max_requests: int
    max_tokens: int
    closed_reason: str | None
    deadline_epoch: float


class ProviderBudgetController:
    """Persist and enforce one serial budget across multiple CLI invocations."""

    _SCHEMA_VERSION = 2
    _SUPPORTED_SCHEMA_VERSIONS = frozenset({1, _SCHEMA_VERSION})

    def __init__(self, limits: ProviderBudgetLimits, ledger_path: Path) -> None:
        self.limits = limits
        self.ledger_path = ledger_path
        self._lock_path = ledger_path.with_name(f"{ledger_path.name}.lock")
        self._request_lease_path = ledger_path.with_name(f"{ledger_path.name}.request.lock")
        self._invocation_lease_path = ledger_path.with_name(f"{ledger_path.name}.invocation.lock")
        self._thread_lock = threading.RLock()
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.request_lease():
            with self._transaction() as state:
                self._recover_abandoned_request(state)

    @contextmanager
    def request_lease(self) -> Iterator[None]:
        """Serialize whole provider attempts and protect active reservations from recovery."""

        with _named_process_lease(self._request_lease_path):
            yield

    @contextmanager
    def invocation_lease(self) -> Iterator[None]:
        """Prevent separate CLI invocations from interleaving one registered experiment."""

        with _named_process_lease(self._invocation_lease_path):
            yield

    def reserve(
        self,
        *,
        input_token_upper_bound: int,
        context: str,
        provider: str,
        model: str,
    ) -> ProviderBudgetReservation:
        if input_token_upper_bound < 0:
            raise ValueError("input_token_upper_bound cannot be negative.")
        if provider != self.limits.expected_provider or model != self.limits.expected_model:
            raise ProviderBudgetExceeded(
                "Provider or model does not match the frozen budget ledger."
            )
        failure: str | None = None
        reservation: ProviderBudgetReservation | None = None
        with self._transaction() as state:
            failure = self._closed_reason(state)
            if failure is None and state["in_flight_request_id"] is not None:
                failure = "A provider request is already in flight; concurrency is limited to one."
            if failure is None and time() >= float(state["deadline_epoch"]):
                state["closed_reason"] = "global_timeout"
                failure = "The experiment-wide provider timeout has expired."
            if failure is None:
                requests_used = int(state["requests_used"])
                if requests_used >= self.limits.max_requests:
                    state["closed_reason"] = "request_budget_exhausted"
                    failure = "The experiment-wide provider request budget is exhausted."
            if failure is None:
                tokens_used = int(state["tokens_used"])
                remaining_tokens = self.limits.max_tokens - tokens_used
                output_limit = min(
                    self.limits.max_output_tokens_per_request,
                    remaining_tokens - input_token_upper_bound,
                )
                if output_limit <= 0:
                    state["closed_reason"] = "token_budget_exhausted"
                    failure = "The remaining token budget cannot reserve this request."
            if failure is None:
                assert output_limit > 0
                reserved_tokens = input_token_upper_bound + output_limit
                request_id = str(uuid4())
                requests = cast(list[dict[str, Any]], state["requests"])
                requests.append(
                    {
                        "request_id": request_id,
                        "context": _safe_label(context),
                        "provider": _safe_label(provider),
                        "model": _safe_label(model),
                        "created_at": _utc_now(),
                        "status": "reserved",
                        "input_token_upper_bound": input_token_upper_bound,
                        "output_token_limit": output_limit,
                        "reserved_tokens": reserved_tokens,
                    }
                )
                state["requests_used"] = requests_used + 1
                state["in_flight_request_id"] = request_id
                reservation = ProviderBudgetReservation(
                    request_id=request_id,
                    input_token_upper_bound=input_token_upper_bound,
                    output_token_limit=output_limit,
                    reserved_tokens=reserved_tokens,
                )
        if failure is not None:
            raise ProviderBudgetExceeded(failure)
        assert reservation is not None
        return reservation

    def complete(self, reservation: ProviderBudgetReservation, response: ProviderResponse) -> None:
        failure: str | None = None
        with self._transaction() as state:
            event = self._in_flight_event(state, reservation.request_id)
            if event is None:
                failure = "The budget ledger no longer has this request reservation."
            else:
                input_tokens = response.input_tokens
                output_tokens = response.output_tokens
                if (
                    type(input_tokens) is not int
                    or type(output_tokens) is not int
                    or input_tokens < 0
                    or output_tokens < 0
                ):
                    self._close_unknown_usage(state, event, reservation)
                    failure = (
                        "Provider token usage is missing; the experiment budget is now closed."
                    )
                elif (
                    input_tokens > reservation.input_token_upper_bound
                    or output_tokens > reservation.output_token_limit
                    or input_tokens + output_tokens > reservation.reserved_tokens
                ):
                    state["tokens_used"] = int(state["tokens_used"]) + input_tokens + output_tokens
                    event.update(
                        {
                            "status": "budget_violation",
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "completed_at": _utc_now(),
                        }
                    )
                    state["closed_reason"] = "provider_exceeded_reservation"
                    state["in_flight_request_id"] = None
                    failure = (
                        "Provider usage exceeded its pre-request reservation; "
                        "no further calls are allowed."
                    )
                else:
                    state["tokens_used"] = int(state["tokens_used"]) + input_tokens + output_tokens
                    timed_out = time() >= float(state["deadline_epoch"])
                    event.update(
                        {
                            "status": "completed_after_timeout" if timed_out else "completed",
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "completed_at": _utc_now(),
                        }
                    )
                    state["in_flight_request_id"] = None
                    if timed_out:
                        state["closed_reason"] = "global_timeout"
                        failure = (
                            "The experiment-wide provider timeout expired while the request "
                            "was in flight."
                        )
        if failure is not None:
            raise ProviderBudgetExceeded(failure)

    def fail(
        self,
        reservation: ProviderBudgetReservation,
        *,
        error_category: str,
        http_status: int | None = None,
    ) -> None:
        if (
            not isinstance(error_category, str)
            or error_category not in _SAFE_PROVIDER_ERROR_CATEGORIES
        ):
            raise ValueError("error_category is not an allowed provider error category.")
        if error_category == "http_status":
            if type(http_status) is not int or not 400 <= http_status <= 599:
                raise ValueError("http_status category requires a 4xx or 5xx status.")
        elif http_status is not None:
            raise ValueError("http_status is only valid for the http_status category.")
        with self._transaction() as state:
            event = self._in_flight_event(state, reservation.request_id)
            if event is not None:
                state["tokens_used"] = int(state["tokens_used"]) + reservation.reserved_tokens
                event.update(
                    {
                        "status": "unknown_spend_after_provider_error",
                        "charged_reservation_tokens": reservation.reserved_tokens,
                        "error_category": error_category,
                        "completed_at": _utc_now(),
                    }
                )
                if http_status is not None:
                    event["http_status"] = http_status
                state["closed_reason"] = "provider_error_unknown_spend"
                state["in_flight_request_id"] = None

    def snapshot(self) -> ProviderBudgetSnapshot:
        with self._transaction() as state:
            return ProviderBudgetSnapshot(
                experiment_id=str(state["experiment_id"]),
                requests_used=int(state["requests_used"]),
                tokens_used=int(state["tokens_used"]),
                max_requests=self.limits.max_requests,
                max_tokens=self.limits.max_tokens,
                closed_reason=(
                    str(state["closed_reason"]) if state["closed_reason"] is not None else None
                ),
                deadline_epoch=float(state["deadline_epoch"]),
            )

    @property
    def should_stop(self) -> bool:
        current = self.snapshot()
        return (
            current.closed_reason is not None
            or current.requests_used >= current.max_requests
            or current.tokens_used >= current.max_tokens
        )

    @contextmanager
    def _transaction(self) -> Iterator[dict[str, Any]]:
        with self._thread_lock:
            with _process_file_lock(self._lock_path):
                state = self._read_state()
                try:
                    yield state
                finally:
                    self._write_state(state)

    def _read_state(self) -> dict[str, Any]:
        if not self.ledger_path.exists():
            now = time()
            return {
                "schema_version": self._SCHEMA_VERSION,
                "experiment_id": self.limits.experiment_id,
                "limits": asdict(self.limits),
                "created_at": _utc_now(),
                "deadline_epoch": now + self.limits.timeout_seconds,
                "requests_used": 0,
                "tokens_used": 0,
                "closed_reason": None,
                "in_flight_request_id": None,
                "requests": [],
            }
        try:
            parsed = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderBudgetExceeded(
                "The provider budget ledger is unreadable; refusing requests."
            ) from exc
        if not isinstance(parsed, dict):
            raise ProviderBudgetExceeded(
                "The provider budget ledger is invalid; refusing requests."
            )
        schema_version = parsed.get("schema_version")
        if type(schema_version) is not int or schema_version not in self._SUPPORTED_SCHEMA_VERSIONS:
            raise ProviderBudgetExceeded("The provider budget ledger version is unsupported.")
        if parsed.get("experiment_id") != self.limits.experiment_id:
            raise ProviderBudgetExceeded("The ledger belongs to a different experiment.")
        if parsed.get("limits") != asdict(self.limits):
            raise ProviderBudgetExceeded(
                "The ledger limits do not match this run; refusing requests."
            )
        if not isinstance(parsed.get("requests"), list):
            raise ProviderBudgetExceeded("The provider budget ledger request list is invalid.")
        state = cast(dict[str, Any], parsed)
        self._validate_state(state)
        state["schema_version"] = self._SCHEMA_VERSION
        return state

    def _validate_state(self, state: dict[str, Any]) -> None:
        requests_used = state.get("requests_used")
        tokens_used = state.get("tokens_used")
        deadline_epoch = state.get("deadline_epoch")
        closed_reason = state.get("closed_reason")
        in_flight_request_id = state.get("in_flight_request_id")
        requests = cast(list[Any], state["requests"])
        if (
            type(requests_used) is not int
            or requests_used < 0
            or requests_used > self.limits.max_requests
            or requests_used != len(requests)
            or type(tokens_used) is not int
            or tokens_used < 0
            or not isinstance(deadline_epoch, (int, float))
            or isinstance(deadline_epoch, bool)
            or not math.isfinite(deadline_epoch)
            or not isinstance(state.get("created_at"), str)
            or not state["created_at"]
            or (closed_reason is not None and not isinstance(closed_reason, str))
            or (in_flight_request_id is not None and not isinstance(in_flight_request_id, str))
        ):
            raise ProviderBudgetExceeded("The provider budget ledger state is invalid.")

        known_statuses = {
            "reserved",
            "completed",
            "completed_after_timeout",
            "budget_violation",
            "unknown_spend_after_provider_error",
            "abandoned_unknown_spend",
            "usage_missing_unknown_spend",
        }
        required_close_reasons = {
            "completed_after_timeout": "global_timeout",
            "budget_violation": "provider_exceeded_reservation",
            "unknown_spend_after_provider_error": "provider_error_unknown_spend",
            "abandoned_unknown_spend": "abandoned_request_unknown_spend",
            "usage_missing_unknown_spend": "usage_missing_unknown_spend",
        }
        reservation_charges = 0
        request_ids: set[str] = set()
        reserved_events: list[dict[str, Any]] = []
        for raw_event in requests:
            if not isinstance(raw_event, dict):
                raise ProviderBudgetExceeded("The provider budget ledger request list is invalid.")
            event = cast(dict[str, Any], raw_event)
            request_id = event.get("request_id")
            status = event.get("status")
            input_upper = event.get("input_token_upper_bound")
            output_limit = event.get("output_token_limit")
            reserved_tokens = event.get("reserved_tokens")
            if (
                not isinstance(request_id, str)
                or not request_id
                or request_id in request_ids
                or not isinstance(status, str)
                or status not in known_statuses
                or type(input_upper) is not int
                or input_upper < 0
                or type(output_limit) is not int
                or output_limit <= 0
                or type(reserved_tokens) is not int
                or reserved_tokens != input_upper + output_limit
            ):
                raise ProviderBudgetExceeded("The provider budget ledger request event is invalid.")
            required_reason = required_close_reasons.get(status)
            if required_reason is not None and closed_reason != required_reason:
                raise ProviderBudgetExceeded(
                    "The provider budget ledger close reason does not match its failed request."
                )
            error_category = event.get("error_category")
            http_status = event.get("http_status")
            if status == "unknown_spend_after_provider_error":
                if error_category is not None and (
                    not isinstance(error_category, str)
                    or error_category not in _SAFE_PROVIDER_ERROR_CATEGORIES
                ):
                    raise ProviderBudgetExceeded(
                        "The provider budget ledger error category is invalid."
                    )
                if http_status is not None and (
                    type(http_status) is not int
                    or not 400 <= http_status <= 599
                    or error_category != "http_status"
                ):
                    raise ProviderBudgetExceeded(
                        "The provider budget ledger HTTP status is invalid."
                    )
                if error_category == "http_status" and http_status is None:
                    raise ProviderBudgetExceeded(
                        "The provider budget ledger HTTP error status is missing."
                    )
            elif error_category is not None or http_status is not None:
                raise ProviderBudgetExceeded(
                    "Provider error metadata is attached to a non-provider-error request."
                )
            request_ids.add(request_id)
            if status == "reserved":
                reserved_events.append(event)
            elif status in {"completed", "completed_after_timeout", "budget_violation"}:
                input_tokens = event.get("input_tokens")
                output_tokens = event.get("output_tokens")
                if (
                    type(input_tokens) is not int
                    or input_tokens < 0
                    or type(output_tokens) is not int
                    or output_tokens < 0
                ):
                    raise ProviderBudgetExceeded("The provider budget ledger usage is invalid.")
                violated = (
                    input_tokens > input_upper
                    or output_tokens > output_limit
                    or input_tokens + output_tokens > reserved_tokens
                )
                if (status == "budget_violation") != violated:
                    raise ProviderBudgetExceeded("The provider budget ledger status is invalid.")
                reservation_charges += input_tokens + output_tokens
            else:
                charged = event.get("charged_reservation_tokens")
                if type(charged) is not int or charged != reserved_tokens:
                    raise ProviderBudgetExceeded("The provider budget ledger charge is invalid.")
                reservation_charges += charged

        expected_in_flight = (
            reserved_events[0].get("request_id") if len(reserved_events) == 1 else None
        )
        if (
            len(reserved_events) > 1
            or in_flight_request_id != expected_in_flight
            or tokens_used != reservation_charges
            or (
                tokens_used > self.limits.max_tokens
                and closed_reason != "provider_exceeded_reservation"
            )
            or (closed_reason is not None and in_flight_request_id is not None)
        ):
            raise ProviderBudgetExceeded("The provider budget ledger counters are inconsistent.")

    def _write_state(self, state: dict[str, Any]) -> None:
        temp_path = self.ledger_path.with_name(
            f"{self.ledger_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(self.ledger_path)
        if os.name != "nt":
            directory_fd = os.open(self.ledger_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)

    def _recover_abandoned_request(self, state: dict[str, Any]) -> None:
        request_id = state.get("in_flight_request_id")
        if request_id is None:
            return
        requests = cast(list[dict[str, Any]], state["requests"])
        event = next((item for item in requests if item.get("request_id") == request_id), None)
        if event is None:
            state["closed_reason"] = "corrupt_in_flight_reservation"
            state["in_flight_request_id"] = None
            return
        charge = int(event.get("reserved_tokens", 0))
        state["tokens_used"] = int(state["tokens_used"]) + charge
        event.update(
            {
                "status": "abandoned_unknown_spend",
                "charged_reservation_tokens": charge,
                "completed_at": _utc_now(),
            }
        )
        state["closed_reason"] = "abandoned_request_unknown_spend"
        state["in_flight_request_id"] = None

    def _closed_reason(self, state: dict[str, Any]) -> str | None:
        reason = state.get("closed_reason")
        if reason is None:
            return None
        return f"The experiment budget is closed ({reason})."

    def _in_flight_event(self, state: dict[str, Any], request_id: str) -> dict[str, Any] | None:
        if state.get("in_flight_request_id") != request_id:
            return None
        requests = cast(list[dict[str, Any]], state["requests"])
        return next((item for item in requests if item.get("request_id") == request_id), None)

    def _close_unknown_usage(
        self,
        state: dict[str, Any],
        event: dict[str, Any],
        reservation: ProviderBudgetReservation,
    ) -> None:
        state["tokens_used"] = int(state["tokens_used"]) + reservation.reserved_tokens
        event.update(
            {
                "status": "usage_missing_unknown_spend",
                "charged_reservation_tokens": reservation.reserved_tokens,
                "completed_at": _utc_now(),
            }
        )
        state["closed_reason"] = "usage_missing_unknown_spend"
        state["in_flight_request_id"] = None


class BudgetedDecisionProvider:
    """Add a durable budget reservation around one provider adapter."""

    def __init__(
        self,
        provider: DecisionProvider,
        controller: ProviderBudgetController,
        *,
        context: str,
        provider_name: str,
        model_name: str,
    ) -> None:
        self._provider = provider
        self._controller = controller
        self._context = context
        self._provider_name = provider_name
        self._model_name = model_name

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        limits = self._controller.limits
        input_upper = estimate_input_tokens_upper_bound(
            request, overhead_tokens=limits.input_overhead_tokens
        )
        with self._controller.request_lease():
            reservation = self._controller.reserve(
                input_token_upper_bound=input_upper,
                context=self._context,
                provider=self._provider_name,
                model=self._model_name,
            )
            bounded_request = replace(request, max_output_tokens=reservation.output_token_limit)
            try:
                response = self._provider.decide(bounded_request)
            except Exception as exc:
                error_category, http_status = _safe_provider_error_details(exc)
                self._controller.fail(
                    reservation,
                    error_category=error_category,
                    http_status=http_status,
                )
                status_detail = (
                    f", http_status={http_status}" if http_status is not None else ""
                )
                raise ProviderBudgetExceeded(
                    "Provider request failed "
                    f"(error_category={error_category}{status_detail}); the reserved amount "
                    "was charged and the budget is closed."
                ) from exc
            if not isinstance(response, ProviderResponse):
                self._controller.fail(reservation, error_category="invalid_response")
                raise ProviderBudgetExceeded(
                    "Provider returned an invalid response "
                    "(error_category=invalid_response); budget closed."
                )
            self._controller.complete(reservation, response)
            return response


def estimate_input_tokens_upper_bound(request: DecisionRequest, *, overhead_tokens: int) -> int:
    """Reserve UTF-8 bytes plus schema and fixed adapter overhead before calling a provider."""

    model_dump_json = getattr(request.observation, "model_dump_json", None)
    if not callable(model_dump_json):
        raise ProviderBudgetExceeded("Cannot bound tokens for an unstructured observation.")
    observation_json = model_dump_json()
    if not isinstance(observation_json, str):
        raise ProviderBudgetExceeded("Cannot bound tokens for an invalid observation.")
    text_parts = [
        request.system_prompt,
        observation_json,
        request.memory_data or "",
        request.runtime_feedback or "",
        request.invalid_output_reason or "",
        request.recent_history or "",
        request.plan_data or "",
    ]
    text_bytes = sum(len(part.encode("utf-8")) for part in text_parts)
    schemas = (
        decision_response_schema(request.action_contract_version),
        decision_response_schema_strict(request.action_contract_version),
        candidate_selection_response_schema(),
        planner_response_schema(),
        planner_response_schema_strict(),
    )
    schema_bytes = max(
        len(json.dumps(schema, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        for schema in schemas
    )
    # UTF-8 byte count bounds byte-pair input tokens for visible payload text;
    # fixed overhead covers adapter framing, role markers, and provider schema transport.
    return text_bytes + schema_bytes + overhead_tokens


@contextmanager
def _named_process_lease(lock_path: Path) -> Iterator[None]:
    lease_key = str(lock_path.resolve())
    with _REQUEST_LEASE_GUARD:
        if lease_key in _ACTIVE_REQUEST_LEASES:
            raise ProviderBudgetExceeded(
                "Another invocation is using this experiment budget; refusing to overlap."
            )
        _ACTIVE_REQUEST_LEASES.add(lease_key)
    try:
        try:
            with _process_file_lock(lock_path, blocking=False):
                yield
        except _FileLockUnavailable as exc:
            raise ProviderBudgetExceeded(
                "Another invocation is using this experiment budget; refusing to overlap."
            ) from exc
    finally:
        with _REQUEST_LEASE_GUARD:
            _ACTIVE_REQUEST_LEASES.discard(lease_key)


@contextmanager
def _process_file_lock(lock_path: Path, *, blocking: bool = True) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            msvcrt_any = cast(Any, msvcrt)
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            mode = msvcrt_any.LK_LOCK if blocking else msvcrt_any.LK_NBLCK
            try:
                msvcrt_any.locking(handle.fileno(), mode, 1)
            except OSError as exc:
                if not blocking:
                    raise _FileLockUnavailable from exc
                raise
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt_any.locking(handle.fileno(), msvcrt_any.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl_any = cast(Any, fcntl)
            mode = fcntl_any.LOCK_EX
            if not blocking:
                mode |= fcntl_any.LOCK_NB
            try:
                fcntl_any.flock(handle.fileno(), mode)
            except OSError as exc:
                if not blocking:
                    raise _FileLockUnavailable from exc
                raise
            try:
                yield
            finally:
                fcntl_any.flock(handle.fileno(), fcntl_any.LOCK_UN)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_label(value: str) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())[:160]
