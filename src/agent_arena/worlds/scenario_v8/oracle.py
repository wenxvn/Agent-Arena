"""Oracle replay for the V8 maps.

The oracle files under ``worlds/v4/MAP-XX/oracle_trace.jsonl`` are judge-side
material. This module replays them through the real ``step`` entry point and
checks only the machine-readable expectations (location, phase, tick, terminal).
Free-text expectations are reported but never treated as assertions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_arena.worlds.scenario_v8.base import MapEnvironment
from agent_arena.worlds.scenario_v8.catalog import create_environment, oracle_path
from agent_arena.worlds.scenario_v8.models import V8Action

_ERROR_MARKERS = ("INVALID", "NOT_ALLOWED", "REJECTED", "MISMATCH", "NOT_VISIBLE")

#: Keys some paper oracles use as annotations rather than action fields.
_ANNOTATION_KEYS = frozenset({"location", "from", "at"})


def normalize_action_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Fold the paper-oracle dialects onto the V8 action shape.

    Some oracle files use ``name``/``action`` instead of ``tool`` and repeat the
    acting location inside the action. Only the oracle *replay* uses this
    normalisation; the live runner never accepts these synonyms.
    """

    normalized = dict(payload)
    if "tool" not in normalized:
        for key in ("name", "action"):
            if isinstance(normalized.get(key), str):
                normalized["tool"] = normalized.pop(key)
                break
    for key in _ANNOTATION_KEYS:
        normalized.pop(key, None)
    return normalized


@dataclass(frozen=True)
class ReplayOutcome:
    map_id: str
    trace_id: str
    actions: int
    status: str
    terminal_reason: str | None
    failures: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


def load_oracle_groups(map_id: str) -> dict[str, list[dict[str, Any]]]:
    path = oracle_path(map_id)
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        trace_id = str(row.get("trace_id", "default"))
        groups.setdefault(trace_id, []).append(row)
    return groups


def _expected_checks(
    expected: str,
    environment: MapEnvironment,
    observation: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    for token in [item.strip() for item in expected.split(";") if item.strip()]:
        if token.startswith("location="):
            want = token.split("=", 1)[1]
            if observation.get("location") != want:
                problems.append(f"expected location={want}, got {observation.get('location')}")
        elif token.startswith("phase="):
            want_int = int(token.split("=", 1)[1])
            if observation.get("tide_phase") != want_int:
                problems.append(f"expected phase={want_int}, got {observation.get('tide_phase')}")
        elif token.startswith("tick="):
            want_tick = int(token.split("=", 1)[1])
            if environment.tick_count != want_tick:
                problems.append(f"expected tick={want_tick}, got {environment.tick_count}")
        elif token.startswith("terminal="):
            want_status = token.split("=", 1)[1]
            if environment.status.value != want_status:
                problems.append(
                    f"expected terminal={want_status}, got {environment.status.value}"
                )
    return problems


def replay_group(
    map_id: str,
    rows: list[dict[str, Any]],
    *,
    trace_id: str = "default",
    step_limit: int = 200,
    seed: int | None = None,
) -> ReplayOutcome:
    if seed is None:
        first_seed = rows[0].get("seed_id") if rows else None
        seed = int(first_seed) if isinstance(first_seed, int) else 0
    environment = create_environment(map_id, seed=seed, step_limit=step_limit)
    failures: list[str] = []
    actions = 0
    for row in rows:
        action_payload = row.get("action")
        if not isinstance(action_payload, dict):
            failures.append(f"step {row.get('step')} has no action object")
            continue
        at = row.get("at")
        if isinstance(at, str) and environment.observe().get("location") != at:
            failures.append(
                f"step {row.get('step')} starts at {environment.observe().get('location')},"
                f" oracle says {at}"
            )
        try:
            action = V8Action.model_validate(normalize_action_payload(action_payload), strict=True)
        except Exception as exc:  # noqa: BLE001 - reported as an oracle failure
            failures.append(f"step {row.get('step')} action schema: {type(exc).__name__}")
            continue
        result = environment.step(action)
        actions += 1
        if result.result.startswith(_ERROR_MARKERS):
            expected = str(row.get("expected", ""))
            # Refusals are only a problem when the oracle claims progress.
            if "=" in expected and not expected.startswith(("phase=", "tick=")):
                failures.append(f"step {row.get('step')} refused: {result.result}")
        expected_value = row.get("expected")
        if isinstance(expected_value, str):
            failures.extend(
                f"step {row.get('step')}: {problem}"
                for problem in _expected_checks(expected_value, environment, result.observation)
            )
        if environment.is_terminal and row is not rows[-1]:
            if environment.is_success:
                failures.append(f"step {row.get('step')}: success ended the trace early")
                break
    return ReplayOutcome(
        map_id=map_id,
        trace_id=trace_id,
        actions=actions,
        status=environment.status.value,
        terminal_reason=environment.terminal_reason,
        failures=tuple(failures),
    )


def replay_all(map_id: str) -> list[ReplayOutcome]:
    return [
        replay_group(map_id, rows, trace_id=trace_id)
        for trace_id, rows in load_oracle_groups(map_id).items()
    ]


def replay_path(path: Path, map_id: str) -> list[ReplayOutcome]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        groups.setdefault(str(row.get("trace_id", "default")), []).append(row)
    return [
        replay_group(map_id, rows, trace_id=trace_id) for trace_id, rows in groups.items()
    ]


__all__ = [
    "ReplayOutcome",
    "load_oracle_groups",
    "replay_all",
    "replay_group",
    "replay_path",
]
