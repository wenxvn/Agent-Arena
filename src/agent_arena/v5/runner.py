"""Bounded V5 episode execution over the isolated V4 environments."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import DecisionProviderError
from agent_arena.llm.protocol import DecisionProvider, DecisionRequest
from agent_arena.v5.budget import (
    MAX_DECISIONS_PER_EPISODE,
    MAX_EPISODE_SECONDS,
    MAX_INPUT_TOKENS_PER_REQUEST,
    MAX_PROVIDER_SECONDS_GLOBAL,
    PilotBudgetClosed,
    V5BudgetLedger,
)
from agent_arena.v5.prompts import (
    condition_memory,
    initial_map08_hypothesis_table,
    public_history,
    system_prompt,
)
from agent_arena.worlds.scenario_v4 import ScenarioV4Action, create_environment
from agent_arena.worlds.scenario_v4.catalog import source_hash
from agent_arena.worlds.scenario_v4.models import V4HypothesisTable

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_REVERSE_BEARING = {
    "N": "S",
    "NE": "SW",
    "E": "W",
    "SE": "NW",
    "S": "N",
    "SW": "NE",
    "W": "E",
    "NW": "SE",
}
_MAP22_PREFIX_MOVES = 12


@dataclass(frozen=True)
class V5EpisodeSpec:
    map_id: str
    condition_id: str
    seed: int
    sample_unit: str

    @property
    def episode_id(self) -> str:
        return f"{self.map_id.lower()}__{self.condition_id}__seed_{self.seed}"


def registered_matrix() -> list[V5EpisodeSpec]:
    """Return the complete pre-registered 39-episode V5 matrix."""

    episodes: list[V5EpisodeSpec] = []
    paired_maps = {
        "MAP-08": ("no_hypothesis_table", "hypothesis_table"),
        "MAP-16": ("react", "constraint_table"),
        "MAP-18": ("alert_off", "alert_on"),
        "MAP-22": ("history5", "history5_graph_memory"),
        "MAP-30": ("history_full", "history5", "history5_casebook"),
    }
    for map_id, conditions in paired_maps.items():
        sample_unit = "independent_seeded_instance" if map_id == "MAP-08" else "fixed_scene_repeat"
        seeds = (0, 4, 8) if map_id == "MAP-08" else (0, 1, 2)
        episodes.extend(
            V5EpisodeSpec(map_id, condition, seed, sample_unit)
            for condition in conditions
            for seed in seeds
        )
    episodes.extend(
        V5EpisodeSpec("MAP-26", "free_diagnosis", seed, "independent_seeded_fault")
        for seed in (0, 1, 2)
    )
    episodes.extend(
        V5EpisodeSpec("MAP-26", condition, 0, "same_seed_standardized_recovery_prefix")
        for condition in ("recovery_full", "recovery_hidden", "recovery_structured")
    )
    if len(episodes) != 39 or len({episode.episode_id for episode in episodes}) != 39:
        raise AssertionError("The pre-registered matrix must contain exactly 39 unique episodes.")
    return episodes


def _context_policy(spec: V5EpisodeSpec) -> str:
    base = "current_public_observation_and_last_five_public_actions"
    if spec.map_id == "MAP-30":
        if spec.condition_id == "history_full":
            return "current_public_observation_and_complete_public_history"
        if spec.condition_id == "history5_casebook":
            return f"{base}_and_recorded_casebook"
    if spec.map_id == "MAP-22" and spec.condition_id == "history5_graph_memory":
        return f"{base}_and_agent_owned_graph_memory"
    if spec.map_id == "MAP-08" and spec.condition_id == "hypothesis_table":
        return f"{base}_and_agent_owned_hypothesis_table"
    if spec.map_id == "MAP-16" and spec.condition_id == "constraint_table":
        return f"{base}_and_public_derived_constraint_table"
    if spec.map_id == "MAP-26" and spec.condition_id.startswith("recovery_"):
        return f"{base}_and_registered_recovery_feedback"
    return base


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PilotBudgetClosed(f"Public trace is malformed at line {line_number}.") from exc
        if not isinstance(row, dict):
            raise PilotBudgetClosed(f"Public trace row {line_number} is not an object.")
        rows.append(row)
    return rows


def _trace_path(episode_dir: Path) -> Path:
    return episode_dir / "agent_trace.jsonl"


def _observation_dict(environment: Any) -> dict[str, Any]:
    return cast(dict[str, Any], environment.observe().model_dump(mode="json"))


def _apply_prefix_action(environment: Any, payload: dict[str, Any]) -> dict[str, Any]:
    before = _observation_dict(environment)
    action = ScenarioV4Action.model_validate(payload, strict=True)
    result = environment.step(action)
    return {
        "event": "prefix_action",
        "action": action.model_dump(mode="json", exclude_none=True),
        "result": result.result,
        "observation_before": before,
        "observation_after": cast(dict[str, Any], result.observation.model_dump(mode="json")),
    }


def _map22_prepare_prefix(
    environment: Any, *, memory_enabled: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_path = REPOSITORY_ROOT / "worlds" / "v4" / "MAP-22" / "planning" / "hand_traces.json"
    route = json.loads(source_path.read_text(encoding="utf-8"))["strategies"][
        "external_graph_memory_euler_tour"
    ]
    directions = route["directions"][:_MAP22_PREFIX_MOVES]
    if len(directions) != _MAP22_PREFIX_MOVES:
        raise ValueError("MAP-22 matched prefix source is incomplete.")
    rows: list[dict[str, Any]] = []
    movement_history: list[dict[str, Any]] = []
    recorded_nodes: set[str] = set()
    recorded_edges: set[frozenset[str]] = set()
    for bearing in directions:
        rows.append(_apply_prefix_action(environment, {"tool": "observe_signpost"}))
        observation = environment.observe()
        detail = observation.inspected_current_sign_detail
        if detail is None:
            raise AssertionError("MAP-22 local sign observation is missing.")
        origin_sign = detail["sign_id"]
        if memory_enabled and origin_sign not in recorded_nodes:
            rows.append(
                _apply_prefix_action(
                    environment,
                    {
                        "tool": "write_memory",
                        "facts": [
                            {
                                "fact_type": "node_page",
                                "sign_id": origin_sign,
                                "exit_bearings": list(observation.visible_exit_bearings),
                            }
                        ],
                    },
                )
            )
            recorded_nodes.add(origin_sign)
        move_row = _apply_prefix_action(environment, {"tool": "move", "bearing": bearing})
        rows.append(move_row)
        movement_history.append(
            {"action": move_row["action"], "result": move_row["result"], "tick": environment.tick}
        )
        if environment.is_terminal:
            raise AssertionError("MAP-22 shared prefix unexpectedly became terminal.")
        rows.append(_apply_prefix_action(environment, {"tool": "observe_signpost"}))
        arrival = environment.observe()
        arrival_detail = arrival.inspected_current_sign_detail
        if arrival_detail is None:
            raise AssertionError("MAP-22 arrival sign observation is missing.")
        destination_sign = arrival_detail["sign_id"]
        facts: list[dict[str, Any]] = []
        if memory_enabled and destination_sign not in recorded_nodes:
            facts.append(
                {
                    "fact_type": "node_page",
                    "sign_id": destination_sign,
                    "exit_bearings": list(arrival.visible_exit_bearings),
                }
            )
            recorded_nodes.add(destination_sign)
        edge = frozenset((origin_sign, destination_sign))
        if memory_enabled and edge not in recorded_edges:
            facts.append(
                {
                    "fact_type": "traversed_edge_page",
                    "from_sign_id": origin_sign,
                    "departure_bearing": bearing,
                    "to_sign_id": destination_sign,
                    "arrival_reverse_bearing": _REVERSE_BEARING[bearing],
                }
            )
            recorded_edges.add(edge)
        if facts:
            rows.append(_apply_prefix_action(environment, {"tool": "write_memory", "facts": facts}))
    # Leave identical last-action feedback in both paired conditions.
    rows.append(_apply_prefix_action(environment, {"tool": "observe_signpost"}))
    if environment.node != "L" or environment.tick != _MAP22_PREFIX_MOVES:
        raise AssertionError("MAP-22 prefix must end at the ruin after the same twelve moves.")
    return rows, movement_history


def _hand_trace_route(map_id: str, route_id: str) -> dict[str, Any]:
    path = REPOSITORY_ROOT / "worlds" / "v4" / map_id / "planning" / "hand_traces.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    route = next((item for item in data["routes"] if item["id"] == route_id), None)
    if route is None:
        raise ValueError(f"Missing registered {map_id} prefix source {route_id}.")
    return cast(dict[str, Any], route)


def _source_action(action: dict[str, Any]) -> dict[str, Any]:
    payload = {"tool": action["name"]}
    payload.update({key: value for key, value in action.items() if key != "name"})
    if action["name"] == "interview":
        payload.setdefault("shown_evidence_ids", [])
        payload.setdefault("shown_casebook_entry_ids", [])
    return payload


def _prepare_prefix(
    environment: Any, spec: V5EpisodeSpec
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if spec.map_id == "MAP-22":
        return _map22_prepare_prefix(
            environment,
            memory_enabled=spec.condition_id == "history5_graph_memory",
        )
    if spec.map_id == "MAP-26" and spec.condition_id.startswith("recovery_"):
        route = _hand_trace_route("MAP-26", "feedback_then_correct")
        rows = [
            _apply_prefix_action(environment, _source_action(action))
            for action in route["actions"][:7]
        ]
        if (
            environment.node != "A"
            or environment.tick != 7
            or environment.uninstalled_spares != 1
            or environment.last_failed_part != "power_regulator"
        ):
            raise AssertionError(
                "MAP-26 recovery prefix did not produce the registered failure state."
            )
        return rows, [
            {
                "action": row["action"],
                "result": row["result"],
                "tick": row["observation_after"]["current_tick"],
            }
            for row in rows
        ]
    if spec.map_id == "MAP-30":
        route = _hand_trace_route("MAP-30", "event_by_event_archive_first")
        rows = [
            _apply_prefix_action(environment, _source_action(action))
            for action in route["actions"][:-1]
        ]
        if environment.node != "J" or environment.is_terminal:
            raise AssertionError(
                "MAP-30 paired prefix must stop in the courtroom before accusation."
            )
        return rows, []
    return [], []


def _replay_prefix(environment: Any, saved_prefix: list[dict[str, Any]]) -> None:
    for row in saved_prefix:
        before = _observation_dict(environment)
        if before != row["observation_before"]:
            raise PilotBudgetClosed("Deterministic prefix replay diverged from the saved trace.")
        result = environment.step(ScenarioV4Action.model_validate(row["action"], strict=True))
        if (
            result.result != row["result"]
            or result.observation.model_dump(mode="json") != row["observation_after"]
        ):
            raise PilotBudgetClosed("Deterministic prefix action no longer reproduces its trace.")


_MAP_ACTION_SHAPES: dict[str, dict[str, set[frozenset[str]]]] = {
    "MAP-08": {
        "move": {frozenset({"tool", "edge_id"})},
        "inspect": {frozenset({"tool", "target_id"})},
        "interact": {frozenset({"tool", "target_id", "operation"})},
        "wait": {frozenset({"tool", "turns"})},
    },
    "MAP-16": {
        "inspect_network": {frozenset({"tool"})},
        "set_route": {frozenset({"tool", "train_id", "next_node"})},
        "occupy_siding": {frozenset({"tool", "train_id", "next_node"})},
        "release_section": {frozenset({"tool", "train_id", "section_id"})},
        "move_train": {frozenset({"tool"})},
    },
    "MAP-18": {"set_timetable": {frozenset({"tool", "tick", "operations"})}},
    "MAP-22": {
        "observe_signpost": {frozenset({"tool"})},
        "move": {frozenset({"tool", "bearing"})},
        "write_memory": {frozenset({"tool", "facts"})},
        "check_goal": {frozenset({"tool"})},
        "return_to_camp": {frozenset({"tool"})},
    },
    "MAP-26": {
        "move": {frozenset({"tool", "to"})},
        "read_log": {frozenset({"tool", "log_id"})},
        "test": {frozenset({"tool", "test_id"})},
        "take_spare": {frozenset({"tool", "part_id"})},
        "replace": {frozenset({"tool", "part_id"})},
        "rollback": {frozenset({"tool"})},
        "restart": {frozenset({"tool"})},
    },
    "MAP-30": {
        "move": {frozenset({"tool", "to"})},
        "inspect": {frozenset({"tool", "evidence_id"})},
        "interview": {
            frozenset(
                {
                    "tool",
                    "npc_id",
                    "topic_id",
                    "shown_evidence_ids",
                    "shown_casebook_entry_ids",
                }
            )
        },
        "record": {frozenset({"tool", "entry_id", "evidence_ids"})},
        "submit_intermediate_hypothesis": {
            frozenset({"tool", "candidate_person", "confidence", "event_ids_known"})
        },
        "compare_records": {frozenset({"tool", "entry_ids"})},
        "formal_accuse": {
            frozenset({"tool", "person_id", "event_claims", "cited_entry_ids"})
        },
    },
}


def _clean_candidate(
    candidate: object, *, map_id: str
) -> tuple[ScenarioV4Action | None, dict[str, Any] | None]:
    if (
        not isinstance(candidate, dict)
        or set(candidate) != {"decision_reason", "action", "agent_hypothesis_table"}
        or not isinstance(candidate.get("decision_reason"), str)
        or len(candidate["decision_reason"]) > 280
        or not isinstance(candidate.get("action"), dict)
    ):
        return None, None
    payload = dict(candidate["action"])
    if payload.get("tool") == "set_timetable" and isinstance(payload.get("operations"), dict):
        payload["operations"] = {
            train: operation
            for train, operation in payload["operations"].items()
            if operation is not None
        }
    table_payload = candidate["agent_hypothesis_table"]
    if table_payload is not None and not isinstance(table_payload, dict):
        return None, None
    try:
        action = ScenarioV4Action.model_validate(payload, strict=True)
    except (ValidationError, TypeError, ValueError):
        return None, None
    allowed_shapes = _MAP_ACTION_SHAPES.get(map_id, {}).get(action.tool, set())
    if frozenset(action.model_fields_set) not in allowed_shapes:
        return None, None
    table: dict[str, Any] | None = None
    if isinstance(table_payload, dict):
        try:
            table = V4HypothesisTable.model_validate(table_payload, strict=True).model_dump(
                mode="json"
            )
        except (ValidationError, TypeError, ValueError):
            table = None
    return action, table


def _validate_hypothesis_update(
    table: dict[str, Any] | None, observation: Any, condition_id: str
) -> tuple[dict[str, Any] | None, str]:
    if condition_id != "hypothesis_table":
        return None, "not_enabled"
    if table is None:
        return None, "missing_or_invalid"
    if table.get("test_X_result") != observation.test_results.get("X"):
        return None, "test_result_not_grounded"
    if table.get("test_Y_result") != observation.test_results.get("Y"):
        return None, "test_result_not_grounded"
    return table, "updated"


def _runtime_decision_payload(
    candidate: object,
    *,
    decision_index: int,
    observation: Any,
    condition_id: str,
) -> dict[str, Any]:
    action, raw_table = _clean_candidate(candidate, map_id=observation.map_id)
    table, table_status = _validate_hypothesis_update(raw_table, observation, condition_id)
    return {
        "decision_index": decision_index,
        "action": action.model_dump(mode="json", exclude_none=True) if action else None,
        "invalid_action": action is None,
        "agent_hypothesis_table": table,
        "hypothesis_table_status": table_status,
    }


def _append_decision(
    environment: Any,
    trace_path: Path,
    ledger: V5BudgetLedger,
    spec: V5EpisodeSpec,
    episode_id: str,
    decision_payload: dict[str, Any],
    request_id: str,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_input_tokens: int | None,
    latency_ms: int,
) -> tuple[dict[str, Any], Any]:
    before = _observation_dict(environment)
    if decision_payload["invalid_action"]:
        result = environment.reject_invalid_action()
        action_payload = None
    else:
        action_payload = decision_payload["action"]
        action = ScenarioV4Action.model_validate(action_payload, strict=True)
        result = environment.step(action)
    row = {
        "event": "decision",
        "episode_id": episode_id,
        "decision_index": decision_payload["decision_index"],
        "request_id": request_id,
        "action": action_payload,
        "invalid_output_reason": "schema_error" if decision_payload["invalid_action"] else None,
        "result": result.result,
        "status": result.status.value,
        "observation_before": before,
        "observation_after": result.observation.model_dump(mode="json"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
        "latency_ms": latency_ms,
        "agent_hypothesis_table": decision_payload["agent_hypothesis_table"],
        "hypothesis_table_status": decision_payload["hypothesis_table_status"],
        "state_hash_after": environment.state_hash(),
    }
    _append_jsonl(trace_path, row)
    ledger.record(
        "decision_checkpoint",
        episode_id=episode_id,
        decision_index=decision_payload["decision_index"],
        request_id=request_id,
        state_hash=environment.state_hash(),
        result=result.result,
        v4_status=result.status.value,
    )
    return row, result


def _request_input_upper_bound_bytes(request: DecisionRequest) -> int:
    """Conservative UTF-8 byte upper bound for the text supplied to MiMo."""

    parts: list[str] = []
    if request.memory_data:
        parts.append(request.memory_data)
    if not isinstance(request.observation, BaseModel):
        raise TypeError("V5 requests require an allowlisted structured Observation.")
    parts.append(f"当前观察：{request.observation.model_dump_json()}")
    if request.plan_data:
        parts.append(f"当前计划状态（公开结构化数据）：{request.plan_data}")
    if request.runtime_feedback:
        parts.append(f"运行时提醒（仅来自公开轨迹）：{request.runtime_feedback}")
    if request.recent_history:
        parts.append(f"最近公开轨迹（仅供参考）：{request.recent_history}")
    parts.append("请只返回规定的 JSON 结构。")
    # Allow 256 provider framing/control tokens beyond the UTF-8 payload bytes.
    return len(request.system_prompt.encode("utf-8")) + len("\n".join(parts).encode("utf-8")) + 256


def _failure_classifications(
    *,
    map_id: str,
    outcome: str,
    terminal_reason: str | None,
    metrics: dict[str, Any],
    decision_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Assign only failure codes backed by retained trace or judge evidence."""

    evidence: list[dict[str, Any]] = []
    if outcome != "success":
        if outcome in {"provider_error", "provider_error_limit", "unknown_provider_spend"}:
            evidence.append({"code": "PROVIDER_ERROR", "basis": {"episode_outcome": outcome}})
        if outcome == "input_context_limit":
            evidence.append(
                {"code": "INPUT_BUDGET_EXCEEDED", "basis": {"episode_outcome": outcome}}
            )
        if outcome in {"episode_timeout", "global_provider_timeout", "decision_limit", "censored"}:
            evidence.append({"code": "TIMEOUT", "basis": {"episode_outcome": outcome}})
    if terminal_reason in {"ACTION_LIMIT_REACHED", "STEP_LIMIT_REACHED", "DEADLINE_REACHED"}:
        evidence.append({"code": "TIMEOUT", "basis": {"terminal_reason": terminal_reason}})

    invalid_rows = [
        row
        for row in decision_rows
        if row.get("invalid_output_reason") is not None
        or (isinstance(row.get("result"), str) and row["result"].startswith("INVALID_"))
    ]
    if invalid_rows:
        evidence.append(
            {
                "code": "INVALID_ACTION",
                "basis": {"decision_indices": [row.get("decision_index") for row in invalid_rows]},
            }
        )

    if map_id == "MAP-08":
        if terminal_reason == "SEALANT_MISUSED":
            evidence.append(
                {"code": "WRONG_HYPOTHESIS", "basis": {"terminal_reason": terminal_reason}}
            )
        elif terminal_reason == "CORE_WATER_LIMIT_EXCEEDED":
            evidence.append(
                {"code": "RESOURCE_EXHAUSTION", "basis": {"terminal_reason": terminal_reason}}
            )
    elif map_id == "MAP-16":
        conflicts = {
            key: value
            for key, value in metrics.items()
            if key.endswith("_count")
            and key not in {"deadlock_count", "route_action_count"}
            and value
        }
        safety_conflicts = {
            key: value
            for key, value in conflicts.items()
            if key
            in {
                "section_reservation_conflict_count",
                "head_on_swap_count",
                "node_capacity_conflict_count",
                "siding_capacity_conflict_count",
            }
        }
        if safety_conflicts:
            evidence.append({"code": "SAFETY_VIOLATION", "basis": {"conflicts": safety_conflicts}})
        if metrics.get("deadlock_count", 0):
            evidence.append(
                {"code": "NO_REPLAN", "basis": {"deadlock_count": metrics["deadlock_count"]}}
            )
    elif map_id == "MAP-18":
        counts = metrics.get("failure_counts")
        safety_counts = (
            {
                key: value
                for key, value in counts.items()
                if key in {"HEAD_ON_COLLISION", "SEGMENT_CAPACITY", "STATION_CAPACITY_EXCEEDED"}
                and value
            }
            if isinstance(counts, dict)
            else {}
        )
        if safety_counts:
            evidence.append(
                {"code": "SAFETY_VIOLATION", "basis": {"failure_counts": safety_counts}}
            )
        if terminal_reason == "DEADLINE_SERVICE_BELOW_70":
            evidence.append({"code": "TIMEOUT", "basis": {"terminal_reason": terminal_reason}})
    elif map_id == "MAP-22" and terminal_reason == "STEP_LIMIT_REACHED":
        evidence.append({"code": "TIMEOUT", "basis": {"terminal_reason": terminal_reason}})
    elif map_id == "MAP-26":
        if terminal_reason == "SPARES_EXHAUSTED":
            evidence.append(
                {"code": "RESOURCE_EXHAUSTION", "basis": {"terminal_reason": terminal_reason}}
            )
        if metrics.get("same_part_retry_attempts", 0):
            evidence.append(
                {
                    "code": "REPEATED_ACTION",
                    "basis": {"same_part_retry_attempts": metrics["same_part_retry_attempts"]},
                }
            )
    elif map_id == "MAP-30":
        publicly_seen_q4 = any(
            "Q4_CODE_INDEX" in str(row.get("result", ""))
            or "Q4_CODE_INDEX" in json.dumps(row.get("observation_after", {}), ensure_ascii=False)
            for row in decision_rows
        )
        if (
            publicly_seen_q4
            and metrics.get("q4_gap_observed") is True
            and metrics.get("q4_recalled_after_gap") is False
        ):
            evidence.append(
                {
                    "code": "MEMORY_LOSS",
                    "basis": {
                        "public_q4_evidence_seen": True,
                        "q4_gap_observed": True,
                        "q4_recalled_after_gap": False,
                    },
                }
            )
        if metrics.get("unsupported_formal_accusations", 0):
            evidence.append(
                {
                    "code": "UNSUPPORTED_CLAIM",
                    "basis": {
                        "unsupported_formal_accusations": metrics["unsupported_formal_accusations"]
                    },
                }
            )
        if terminal_reason == "DEADLINE_REACHED":
            evidence.append({"code": "TIMEOUT", "basis": {"terminal_reason": terminal_reason}})

    unique: dict[str, dict[str, Any]] = {}
    for item in evidence:
        unique.setdefault(item["code"], item)
    if not unique and outcome == "success":
        return []
    if not unique:
        return [{"code": "UNCLASSIFIED_OUTCOME", "basis": {"episode_outcome": outcome}}]
    return list(unique.values())


def _episode_usage(events: list[dict[str, Any]], episode_id: str, currency: str) -> dict[str, Any]:
    reservations = [
        event
        for event in events
        if event["event"] == "request_reserved" and event.get("episode_id") == episode_id
    ]
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
    cached = [event.get("cached_input_tokens") for event in settled]
    return {
        "request_attempts": len(reservations),
        "settled_requests": len(settled),
        "failed_requests": len(failed),
        "unknown_spend_failures": sum(bool(event.get("unknown_spend")) for event in failed),
        "input_tokens": sum(int(event["input_tokens"]) for event in settled),
        "output_tokens": sum(int(event["output_tokens"]) for event in settled),
        "cached_input_tokens": sum(int(value) for value in cached if isinstance(value, int)),
        "cache_usage_reported_for_all_settled_requests": (
            all(isinstance(value, int) for value in cached) if settled else None
        ),
        "reserved_cost": str(
            sum((Decimal(str(event["reserved_cost"])) for event in reservations), Decimal(0))
        ),
        "reported_usage_cost": str(
            sum((Decimal(str(event["actual_cost"])) for event in settled), Decimal(0))
        ),
        "currency": currency,
        "provider_wall_seconds": round(
            sum(float(event.get("latency_ms", 0)) / 1_000 for event in [*settled, *failed]),
            3,
        ),
    }


class V5PilotRunner:
    def __init__(
        self,
        *,
        provider: DecisionProvider,
        settings: RuntimeSettings,
        ledger: V5BudgetLedger,
        output_dir: Path,
        progress: Callable[[dict[str, Any]], None] | None = None,
        offline_gate_hash: str | None = None,
        runtime_commit: str | None = None,
        runtime_tree_hash: str | None = None,
        decision_limit: int = MAX_DECISIONS_PER_EPISODE,
    ) -> None:
        if not 1 <= decision_limit <= MAX_DECISIONS_PER_EPISODE:
            raise ValueError("V5 decision_limit must be within the registered 1..100 range.")
        self.provider = provider
        self.settings = settings
        self.ledger = ledger
        self.output_dir = output_dir
        self.progress = progress or (lambda _: None)
        self.offline_gate_hash = offline_gate_hash
        self.runtime_commit = runtime_commit
        self.runtime_tree_hash = runtime_tree_hash
        self.decision_limit = decision_limit

    def run(self, spec: V5EpisodeSpec, *, resume: bool = False) -> dict[str, Any]:
        episode_id = spec.episode_id
        completed = self.ledger.completed_episode_ids()
        if episode_id in completed:
            return {"episode_id": episode_id, "status": "already_completed"}
        self.ledger.start_episode(
            episode_id,
            map_id=spec.map_id,
            seed=spec.seed,
            condition_id=spec.condition_id,
        )
        self.progress(
            {
                "event": "episode_started",
                "episode_id": episode_id,
                "map_id": spec.map_id,
                "condition_id": spec.condition_id,
                "seed": spec.seed,
            }
        )
        episode_dir = self.output_dir / "episodes" / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        trace_path = _trace_path(episode_dir)
        source_digest = source_hash(spec.map_id)
        environment = create_environment(
            spec.map_id,
            seed=spec.seed,
            condition_id=spec.condition_id,
            step_limit=100,
        )
        prefix_rows, prefix_history = _prepare_prefix(environment, spec)
        if trace_path.exists():
            trace_rows = _read_jsonl(trace_path)
            saved_prefix = [row for row in trace_rows if row.get("event") == "prefix_action"]
            if saved_prefix != prefix_rows:
                self.ledger.close("PREFIX_OR_RUNTIME_CHANGED", episode_id=episode_id)
                raise PilotBudgetClosed("Saved episode prefix differs from current frozen prefix.")
            environment.reset(spec.seed)
            _replay_prefix(environment, saved_prefix)
            decision_rows = [row for row in trace_rows if row.get("event") == "decision"]
            history = self._history_from_trace(spec, trace_rows, prefix_history)
            hypothesis_table = self._hypothesis_from_trace(spec, decision_rows)
            self._replay_decisions(environment, decision_rows)
        else:
            trace_rows = prefix_rows
            decision_rows = []
            history = prefix_history
            hypothesis_table = (
                initial_map08_hypothesis_table()
                if spec.condition_id == "hypothesis_table"
                else None
            )
            self._write_initial_trace(trace_path, spec, episode_id, source_digest, prefix_rows)
            _write_json_atomic(
                episode_dir / "episode_manifest.json",
                {
                    "episode_id": episode_id,
                    "experiment_id": self.ledger.experiment_id,
                    "map_id": spec.map_id,
                    "condition_id": spec.condition_id,
                    "seed": spec.seed,
                    "sample_unit": spec.sample_unit,
                    "condition_source_hash": source_digest,
                    "runtime_commit": self.runtime_commit,
                    "runtime_tree_hash": self.runtime_tree_hash,
                    "offline_gate_hash": self.offline_gate_hash,
                    "status": "running",
                    "started_at": _utc_now(),
                    "model": self.settings.model_name,
                    "provider": self.settings.provider,
                    "base_url_host": self.settings.base_url.split("/")[2]
                    if self.settings.base_url
                    else None,
                    "runtime_contract": "scenario_v4",
                    "temperature": 0,
                    "max_output_tokens": 1_024,
                    "max_decisions_per_episode": self.decision_limit,
                    "reasoning_effort": self.settings.reasoning_effort,
                    "prompt_sha256": _sha256(
                        system_prompt(spec.map_id, spec.condition_id).encode()
                    ),
                },
            )

        self._settle_uncheckpointed_response(
            environment,
            spec,
            episode_id,
            trace_path,
            decision_rows,
        )
        decision_rows = _read_jsonl(trace_path)
        decision_count = sum(row.get("event") == "decision" for row in decision_rows)
        history = self._history_from_trace(spec, decision_rows, prefix_history)
        hypothesis_table = self._hypothesis_from_trace(
            spec,
            [row for row in decision_rows if row.get("event") == "decision"],
        )
        started_at = self._episode_started_at(episode_id)
        episode_start_epoch = datetime.fromisoformat(started_at).timestamp()
        episode_start_monotonic = time.monotonic()
        recovery_pending = self._pending_recovery_retry(episode_id)
        retry_used = self._episode_retry_used(episode_id)
        outcome = "running"

        while environment.status.value == "running" and decision_count < self.decision_limit:
            elapsed = max(
                time.time() - episode_start_epoch, time.monotonic() - episode_start_monotonic
            )
            if elapsed >= MAX_EPISODE_SECONDS:
                outcome = "episode_timeout"
                break
            if self.ledger.provider_wall_seconds() >= MAX_PROVIDER_SECONDS_GLOBAL:
                self.ledger.close("GLOBAL_PROVIDER_WALL_LIMIT")
                outcome = "global_provider_timeout"
                break

            observation = environment.observe()
            memory_data = condition_memory(
                spec.map_id, spec.condition_id, observation, hypothesis_table
            )
            if spec.map_id == "MAP-26" and spec.condition_id.startswith("recovery_"):
                memory_data = self._feedback_instruction(spec.condition_id, observation)
            history_limit = None if spec.condition_id == "history_full" else 5
            recent = public_history(history, limit=history_limit)
            request = DecisionRequest(
                observation=observation,
                system_prompt=system_prompt(spec.map_id, spec.condition_id),
                correction=False,
                memory_data=memory_data,
                recent_history=recent,
                max_output_tokens=1_024,
                action_contract_version="scenario_v4",
            )
            request_hash = self._request_hash(request)
            input_upper_bound = _request_input_upper_bound_bytes(request)
            if input_upper_bound > MAX_INPUT_TOKENS_PER_REQUEST:
                _append_jsonl(
                    trace_path,
                    {
                        "event": "request_context_rejected",
                        "episode_id": episode_id,
                        "decision_index": decision_count + 1,
                        "utf8_input_upper_bound_bytes": input_upper_bound,
                        "input_token_cap": MAX_INPUT_TOKENS_PER_REQUEST,
                    },
                )
                self.ledger.close(
                    "REQUEST_CONTEXT_EXCEEDS_REGISTERED_INPUT_CAP",
                    episode_id=episode_id,
                    decision_index=decision_count + 1,
                    utf8_input_upper_bound_bytes=input_upper_bound,
                )
                outcome = "input_context_limit"
                break
            retry = recovery_pending
            if retry and not self._previous_failed_hash_matches(
                episode_id, decision_count + 1, request_hash
            ):
                self.ledger.close("RECOVERY_REQUEST_CHANGED", episode_id=episode_id)
                raise PilotBudgetClosed("Frozen recovery request changed; pilot is closed.")
            request_id = self.ledger.reserve_request(
                episode_id,
                decision_index=decision_count + 1,
                request_hash=request_hash,
                retry=retry,
            )
            recovery_pending = False
            if retry:
                retry_used = True
            self.progress(
                {
                    "event": "request_started",
                    "episode_id": episode_id,
                    "decision_index": decision_count + 1,
                    "retry": retry,
                }
            )
            request_started = time.monotonic()
            try:
                response = self.provider.decide(request)
            except DecisionProviderError as exc:
                latency_ms = max(0, round((time.monotonic() - request_started) * 1_000))
                category = exc.error_category[:80]
                self.ledger.fail_request(
                    request_id,
                    error_category=category,
                    latency_ms=latency_ms,
                    retryable=exc.retryable,
                    unknown_spend=exc.unknown_spend,
                )
                if exc.unknown_spend:
                    self.ledger.close("UNKNOWN_PROVIDER_SPEND", episode_id=episode_id)
                    outcome = "unknown_provider_spend"
                    break
                if self.ledger.consecutive_errors() >= 2:
                    self.ledger.close("TWO_CONSECUTIVE_PROVIDER_ERRORS", episode_id=episode_id)
                    outcome = "provider_error_limit"
                    break
                if exc.retryable and not retry_used:
                    recovery_pending = True
                    _append_jsonl(
                        trace_path,
                        {
                            "event": "provider_error",
                            "episode_id": episode_id,
                            "decision_index": decision_count + 1,
                            "request_id": request_id,
                            "error_category": category,
                            "retry_scheduled": True,
                            "latency_ms": latency_ms,
                        },
                    )
                    self.progress(
                        {
                            "event": "provider_retry_scheduled",
                            "episode_id": episode_id,
                            "decision_index": decision_count + 1,
                            "error_category": category,
                        }
                    )
                    continue
                outcome = "provider_error"
                break
            except Exception as exc:
                category = type(exc).__name__[:80]
                latency_ms = max(0, round((time.monotonic() - request_started) * 1_000))
                self.ledger.fail_request(
                    request_id,
                    error_category=category,
                    latency_ms=latency_ms,
                    retryable=False,
                )
                self.ledger.close("UNKNOWN_PROVIDER_SPEND", episode_id=episode_id)
                outcome = "unknown_provider_spend"
                break

            latency_ms = max(0, round((time.monotonic() - request_started) * 1_000))
            payload = _runtime_decision_payload(
                response.candidate,
                decision_index=decision_count + 1,
                observation=observation,
                condition_id=spec.condition_id,
            )
            self.ledger.settle_request(
                request_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_input_tokens=response.cached_input_tokens,
                latency_ms=latency_ms,
                decision_payload=payload,
            )
            row, _ = _append_decision(
                environment,
                trace_path,
                self.ledger,
                spec,
                episode_id,
                payload,
                request_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_input_tokens=response.cached_input_tokens,
                latency_ms=latency_ms,
            )
            decision_rows.append(row)
            decision_count += 1
            if spec.map_id == "MAP-30" and spec.condition_id == "history_full":
                history = self._history_from_trace(spec, _read_jsonl(trace_path), prefix_history)
            else:
                history.append(
                    {
                        "action": row["action"],
                        "result": row["result"],
                        "tick": row["observation_after"].get(
                            "tick", row["observation_after"].get("current_tick")
                        ),
                    }
                )
            if payload["agent_hypothesis_table"] is not None:
                hypothesis_table = payload["agent_hypothesis_table"]
            self.progress(
                {
                    "event": "decision_settled",
                    "episode_id": episode_id,
                    "decision_index": decision_count,
                    "result": row["result"],
                    "v4_status": row["status"],
                    "latency_ms": latency_ms,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                }
            )
            if environment.status.value != "running":
                break

        if outcome == "running":
            outcome = (
                "success"
                if environment.is_success
                else "failure"
                if environment.status.value == "scenario_failure"
                else "censored"
                if environment.status.value == "step_limit_reached"
                else "decision_limit"
                if decision_count >= self.decision_limit
                else "incomplete"
            )
        judge_path = episode_dir / "judge_metrics.json"
        ledger_events = self.ledger.read_events()
        episode_usage = _episode_usage(ledger_events, episode_id, self.ledger.prices.currency)
        terminal_reason = environment.terminal_reason
        failure_classifications = _failure_classifications(
            map_id=spec.map_id,
            outcome=outcome,
            terminal_reason=terminal_reason,
            metrics=environment.metrics(),
            decision_rows=decision_rows,
        )
        judge_data = {
            "episode_id": episode_id,
            "map_id": spec.map_id,
            "condition_id": spec.condition_id,
            "seed": spec.seed,
            "sample_unit": spec.sample_unit,
            "source_hash": source_digest,
            "runtime_commit": self.runtime_commit,
            "runtime_tree_hash": self.runtime_tree_hash,
            "offline_gate_hash": self.offline_gate_hash,
            "provider": self.settings.provider,
            "model": self.settings.model_name,
            "status": outcome,
            "v4_status": environment.status.value,
            "judge_state_hash": environment.state_hash(),
            "judge_state": environment.judge_state(),
            "metrics": environment.metrics(),
            "failure_classifications": failure_classifications,
            "decision_count": decision_count,
            "retry_used": retry_used,
            "usage": episode_usage,
            "provider_wall_seconds": episode_usage["provider_wall_seconds"],
            "finished_at": _utc_now(),
        }
        _write_json_atomic(judge_path, judge_data)
        _write_json_atomic(
            episode_dir / "episode_manifest.json",
            {
                "episode_id": episode_id,
                "experiment_id": self.ledger.experiment_id,
                "map_id": spec.map_id,
                "condition_id": spec.condition_id,
                "seed": spec.seed,
                "sample_unit": spec.sample_unit,
                "source_hash": source_digest,
                "runtime_commit": self.runtime_commit,
                "runtime_tree_hash": self.runtime_tree_hash,
                "offline_gate_hash": self.offline_gate_hash,
                "model": self.settings.model_name,
                "provider": self.settings.provider,
                "runtime_contract": "scenario_v4",
                "temperature": 0,
                "reasoning_effort": "none",
                "response_mode": "json_object",
                "max_input_tokens": MAX_INPUT_TOKENS_PER_REQUEST,
                "max_output_tokens": 1_024,
                "max_decisions_per_episode": self.decision_limit,
                "context_policy": _context_policy(spec),
                "prompt_sha256": _sha256(
                    system_prompt(spec.map_id, spec.condition_id).encode("utf-8")
                ),
                "status": outcome,
                "v4_status": environment.status.value,
                "decision_count": decision_count,
                "retry_used": retry_used,
                "usage": episode_usage,
                "failure_classifications": failure_classifications,
                "started_at": started_at,
                "finished_at": judge_data["finished_at"],
                "trace_sha256": _sha256(trace_path.read_bytes()),
                "judge_sha256": _sha256(_json_bytes(judge_data)),
            },
        )
        if not self.ledger.closed:
            self.ledger.record(
                "episode_completed",
                episode_id=episode_id,
                map_id=spec.map_id,
                condition_id=spec.condition_id,
                seed=spec.seed,
                outcome=outcome,
                v4_status=environment.status.value,
                decision_count=decision_count,
                judge_state_hash=environment.state_hash(),
                trace_sha256=_sha256(trace_path.read_bytes()),
            )
        self.progress(
            {
                "event": "episode_finished",
                "episode_id": episode_id,
                "outcome": outcome,
                "v4_status": environment.status.value,
                "decision_count": decision_count,
            }
        )
        return {
            "episode_id": episode_id,
            "map_id": spec.map_id,
            "condition_id": spec.condition_id,
            "seed": spec.seed,
            "outcome": outcome,
            "v4_status": environment.status.value,
            "decision_count": decision_count,
        }

    def _write_initial_trace(
        self,
        trace_path: Path,
        spec: V5EpisodeSpec,
        episode_id: str,
        source_digest: str,
        prefix_rows: list[dict[str, Any]],
    ) -> None:
        header = {
            "event": "trace_header",
            "episode_id": episode_id,
            "map_id": spec.map_id,
            "condition_id": spec.condition_id,
            "seed": spec.seed,
            "sample_unit": spec.sample_unit,
            "world_version": "V4",
            "action_contract_version": "scenario_v4",
            "source_hash": source_digest,
            "provider": self.settings.provider,
            "model": self.settings.model_name,
            "created_at": _utc_now(),
            "agent_visible_only": True,
        }
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [header, *prefix_rows]
        raw = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        )
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=trace_path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, trace_path)

    def _replay_decisions(self, environment: Any, decision_rows: list[dict[str, Any]]) -> None:
        for row in decision_rows:
            if row["invalid_output_reason"] is not None:
                result = environment.reject_invalid_action()
            else:
                result = environment.step(
                    ScenarioV4Action.model_validate(row["action"], strict=True)
                )
            if (
                result.result != row["result"]
                or environment.state_hash() != row.get("state_hash_after")
                or result.observation.model_dump(mode="json") != row["observation_after"]
            ):
                raise PilotBudgetClosed("Episode checkpoint cannot be replayed deterministically.")

    def _settle_uncheckpointed_response(
        self,
        environment: Any,
        spec: V5EpisodeSpec,
        episode_id: str,
        trace_path: Path,
        existing_rows: list[dict[str, Any]],
    ) -> None:
        decision_count = sum(row.get("event") == "decision" for row in existing_rows)
        events = self.ledger.read_events()
        recovered = [
            event
            for event in events
            if event["event"] == "request_settled"
            and event.get("episode_id") == episode_id
            and int(event.get("decision_index", 0)) > decision_count
        ]
        if len(recovered) > 1:
            self.ledger.close("MULTIPLE_UNCHECKPOINTED_RESPONSES", episode_id=episode_id)
            raise PilotBudgetClosed("Multiple uncheckpointed decisions make resume unsafe.")
        if recovered:
            event = recovered[0]
            if int(event["decision_index"]) != decision_count + 1:
                self.ledger.close("NONCONTIGUOUS_DECISION_CHECKPOINT", episode_id=episode_id)
                raise PilotBudgetClosed("V5 decision checkpoint sequence is not contiguous.")
            payload = event.get("decision_payload")
            if not isinstance(payload, dict):
                self.ledger.close("MISSING_DECISION_PAYLOAD", episode_id=episode_id)
                raise PilotBudgetClosed("Settled response has no safe action checkpoint.")
            row, _ = _append_decision(
                environment,
                trace_path,
                self.ledger,
                spec,
                episode_id,
                payload,
                str(event["request_id"]),
                input_tokens=event.get("input_tokens"),
                output_tokens=event.get("output_tokens"),
                cached_input_tokens=event.get("cached_input_tokens"),
                latency_ms=int(event.get("latency_ms", 0)),
            )
            _ = row

    def _history_from_trace(
        self,
        spec: V5EpisodeSpec,
        trace_rows: list[dict[str, Any]],
        prefix_history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if spec.map_id == "MAP-30":
            action_rows = [
                row
                for row in trace_rows
                if row.get("event") in {"prefix_action", "decision"}
            ]
            if spec.condition_id != "history_full":
                return [
                    {"action": row.get("action"), "result": row.get("result")}
                    for row in action_rows[-5:]
                ]
            full_history: list[dict[str, Any]] = []
            seen_event_ticks: set[int] = set()
            for row in action_rows:
                observation = row.get("observation_after", {})
                newly_visible_payloads: list[dict[str, Any]] = []
                for public_event in observation.get("recent_action_window", []):
                    event_tick = int(public_event["tick"])
                    if event_tick not in seen_event_ticks:
                        seen_event_ticks.add(event_tick)
                        payload = public_event.get("public_payload")
                        if isinstance(payload, dict) and "evidence" in payload:
                            newly_visible_payloads.append(
                                {
                                    "evidence": [
                                        {
                                            key: item[key]
                                            for key in (
                                                "evidence_id",
                                                "source_class",
                                                "fact",
                                                "rendered_text",
                                            )
                                            if key in item
                                        }
                                        for item in payload["evidence"]
                                    ]
                                }
                            )
                        if isinstance(payload, dict) and "npc_answer" in payload:
                            answer = payload["npc_answer"]
                            evidence_ids = {
                                item.get("evidence_id")
                                for item in payload.get("evidence", [])
                                if isinstance(item, dict)
                            }
                            answer_keys = (
                                ("npc_id", "answer_id", "evidence_ids")
                                if evidence_ids
                                and set(answer.get("evidence_ids", [])).issubset(evidence_ids)
                                else ("npc_id", "answer_id", "evidence_ids", "rendered_text")
                            )
                            newly_visible_payloads.append(
                                {
                                    "npc_answer": {
                                        key: answer[key]
                                        for key in answer_keys
                                        if key in answer
                                    }
                                }
                            )
                history_entry: dict[str, Any] = {
                    "action": row.get("action"),
                    "result": row.get("result"),
                }
                if newly_visible_payloads:
                    history_entry["public_payloads"] = newly_visible_payloads
                full_history.append(history_entry)
            return full_history

        history = list(prefix_history)
        decision_rows = [row for row in trace_rows if row.get("event") == "decision"]
        for row in decision_rows:
            history.append(
                {
                    "action": row["action"],
                    "result": row["result"],
                    "tick": row["observation_after"].get(
                        "tick", row["observation_after"].get("current_tick")
                    ),
                }
            )
        return history

    def _hypothesis_from_trace(
        self, spec: V5EpisodeSpec, decision_rows: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        if spec.condition_id != "hypothesis_table":
            return None
        for row in reversed(decision_rows):
            table = row.get("agent_hypothesis_table")
            if isinstance(table, dict):
                return table
        return initial_map08_hypothesis_table()

    def _episode_started_at(self, episode_id: str) -> str:
        for event in self.ledger.read_events():
            if event["event"] == "episode_started" and event.get("episode_id") == episode_id:
                return str(event["at"])
        raise PilotBudgetClosed("Episode start registration is missing.")

    def _pending_recovery_retry(self, episode_id: str) -> bool:
        events = self.ledger.read_events()
        last_reserved: dict[str, Any] | None = None
        for event in events:
            if event.get("episode_id") == episode_id and event["event"] == "request_reserved":
                last_reserved = event
        if last_reserved is None:
            return False
        last_failed = next(
            (
                event
                for event in reversed(events)
                if event.get("request_id") == last_reserved.get("request_id")
                and event["event"] == "request_failed"
            ),
            None,
        )
        return bool(last_failed and last_failed.get("retryable") and not last_reserved.get("retry"))

    def _previous_failed_hash_matches(
        self, episode_id: str, decision_index: int, request_hash: str
    ) -> bool:
        events = self.ledger.read_events()
        previous_failure = next(
            (
                event
                for event in reversed(events)
                if event["event"] == "request_failed"
                and event.get("episode_id") == episode_id
                and int(event.get("decision_index", 0)) == decision_index
            ),
            None,
        )
        return bool(previous_failure and previous_failure.get("request_hash") == request_hash)

    def _episode_retry_used(self, episode_id: str) -> bool:
        return any(
            event["event"] == "request_reserved"
            and event.get("episode_id") == episode_id
            and event.get("retry") is True
            for event in self.ledger.read_events()
        )

    @staticmethod
    def _request_hash(request: DecisionRequest) -> str:
        payload = {
            "system_prompt": request.system_prompt,
            "observation": request.observation.model_dump(mode="json")
            if hasattr(request.observation, "model_dump")
            else request.observation,
            "memory_data": request.memory_data,
            "recent_history": request.recent_history,
            "output_contract": request.output_contract,
            "action_contract_version": request.action_contract_version,
            "max_output_tokens": request.max_output_tokens,
        }
        return _sha256(_json_bytes(payload))

    @staticmethod
    def _feedback_instruction(condition_id: str, observation: Any) -> str:
        return json.dumps(
            {
                "registered_feedback_condition": condition_id,
                "public_current_feedback": observation.last_action_result,
                "feedback_visibility": "full"
                if condition_id == "recovery_full"
                else condition_id.removeprefix("recovery_"),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
