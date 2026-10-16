"""Bounded V6 episode execution over the isolated V4 environments.

Reuses only map-agnostic Provider and validation helpers; V6 scenes, prompts,
conditions, ledger, and registry stay separate from V5.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from pydantic import ValidationError

from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import DecisionProviderError
from agent_arena.llm.protocol import DecisionProvider, DecisionRequest
from agent_arena.v5.runner import (
    _MAP_ACTION_SHAPES,
    _append_jsonl,
    _json_bytes,
    _normalize_action_discriminator,
    _request_input_upper_bound_bytes,
    _sha256,
    _write_json_atomic,
)
from agent_arena.v6.budget import (
    MAX_DECISIONS_PER_EPISODE,
    MAX_EPISODE_SECONDS,
    MAX_INPUT_TOKENS_PER_REQUEST,
    MAX_PROVIDER_SECONDS_GLOBAL,
    V6BudgetLedger,
)
from agent_arena.v6.catalog import build_environment, get_scene, scenario_hash
from agent_arena.v6.prompts import (
    v6_condition_memory,
    v6_public_history,
    v6_system_prompt,
)
from agent_arena.worlds.scenario_v4 import ScenarioV4Action
from agent_arena.worlds.scenario_v4.map30 import DEFAULT_CASE
from agent_arena.worlds.scenario_v4.models import V4HypothesisTable

REPOSITORY_ROOT: Any = None  # replaced by _repository_root(); kept for import symmetry
MAX_CONSECUTIVE_INVALID_ACTION_SCHEMAS = 3
_MAP22_MEMORY_CONDITIONS = frozenset({"history5_graph_memory"})
_PAIRED = {
    "map08_l1_two_candidate": ("no_hypothesis_table", "hypothesis_table"),
    "map08_l2_alt_coverage": ("no_hypothesis_table", "hypothesis_table"),
    "map08_l3_original": ("no_hypothesis_table", "hypothesis_table"),
    "map16_l1_single_train": ("react", "constraint_table"),
    "map16_l2_siding_variant_a": ("react", "constraint_table"),
    "map16_l3_original": ("react", "constraint_table"),
    "map18_l1_no_fault": ("alert_off", "alert_on"),
    "map18_l2_short_closure": ("alert_off", "alert_on"),
    "map18_l2_alt_segment_r2b2": ("alert_off", "alert_on"),
    "map18_l3_alt_segment_b3g2": ("alert_off", "alert_on"),
    "map18_l3_original": ("alert_off", "alert_on"),
    "map22_l1_short_return": ("history5", "history5_graph_memory"),
    "map22_l2_branch_loop": ("history5", "history5_graph_memory"),
    "map22_l3_original": ("history5", "history5_graph_memory"),
}
_MAP26_FREE = (
    "map26_l1_antenna_fault",
    "map26_l2_power_fault",
    "map26_l2_spare_rich",
    "map26_l3_software_fault",
)
_MAP26_RECOVERY = ("recovery_full", "recovery_structured", "recovery_hidden")
_MAP26_RECOVERY_INSTANCES = (
    "map26_recovery_antenna",
    "map26_recovery_power",
    "map26_recovery_software",
)
_MAP30_CASES = (
    "map30_l1_two_event_case",
    "map30_l2_three_event_alt",
    "map30_l3_original",
)
MAP30_RECALL_CONDITIONS = ("history_full", "history5", "history5_casebook")
SMOKE = (
    ("map08_l1_two_candidate", "no_hypothesis_table", 0),
    ("map16_l1_single_train", "react", 0),
    ("map18_l2_alt_segment_r2b2", "alert_off", 0),
    ("map22_l1_short_return", "history5", 0),
    ("map26_recovery_power", "recovery_full", 0),
    ("map30_recall_original", "history5_casebook", 0),
)


@dataclass(frozen=True)
class V6EpisodeSpec:
    instance_id: str
    condition_id: str
    seed: int

    @property
    def episode_id(self) -> str:
        return f"{self.instance_id}__{self.condition_id}__seed_{self.seed}"

    @property
    def map_id(self) -> str:
        return str(get_scene(self.instance_id).map_id)


def registered_v6_matrix() -> list[V6EpisodeSpec]:
    episodes: list[V6EpisodeSpec] = []
    for instance_id, conditions in _PAIRED.items():
        episodes.extend(V6EpisodeSpec(instance_id, condition, 0) for condition in conditions)
    episodes.extend(V6EpisodeSpec(instance_id, "free_diagnosis", 0) for instance_id in _MAP26_FREE)
    episodes.extend(
        V6EpisodeSpec(instance_id, condition, 0)
        for instance_id in _MAP26_RECOVERY_INSTANCES
        for condition in _MAP26_RECOVERY
    )
    episodes.extend(
        V6EpisodeSpec(instance_id, "history5_casebook", 0) for instance_id in _MAP30_CASES
    )
    episodes.extend(
        V6EpisodeSpec("map30_recall_original", condition, 0)
        for condition in MAP30_RECALL_CONDITIONS
    )
    if len(episodes) != len({item.episode_id for item in episodes}):
        raise AssertionError("The V6 matrix must contain unique episodes.")
    return episodes


def smoke_specs() -> list[V6EpisodeSpec]:
    return [V6EpisodeSpec(*item) for item in SMOKE]


def _public_repeat_reminder(recent_results: list[str]) -> str | None:
    """Public reminder when three consecutive decisions were refused.

    The text is derived only from the Agent's own public action results, so it
    adds no judge state. It breaks the "stuck on one invalid action" loop found
    in the V6 smoke runs.
    """
    if len(recent_results) < 3:
        return None
    last_three = recent_results[-3:]
    if len(set(last_three)) != 1:
        return None
    result = last_three[0]
    if not result.startswith(
        ("INVALID", "NO_", "TICK_MISMATCH", "CANCELED", "COMPLETED", "COURTROOM", "ALREADY")
    ):
        return None
    return (
        f"最近 3 次动作都返回 {result}，没有产生进展。"
        "请重新阅读动作契约与当前 Observation，改用字段合法且能改变状态的 action。"
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _observation_dict(environment: Any) -> dict[str, Any]:
    return cast(dict[str, Any], environment.observe().model_dump(mode="json"))


def _structural_for(scene: Any) -> dict[str, Any] | None:
    """Public structural labels a task needs; never private truth or evidence."""
    if scene.map_id == "MAP-30":
        order = scene.case.entry_order if scene.case is not None else DEFAULT_CASE.entry_order
        return {"entry_order": list(order)}
    return None


def _history_tick(observation_after: dict[str, Any]) -> Any:
    for key in ("movement_steps", "tick", "current_tick"):
        if key in observation_after:
            return observation_after[key]
    return None


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


def _map22_walk_to_target(scene: Any) -> list[str]:
    nodes = scene.nodes
    start, target = scene.start, scene.target
    parents: dict[str, tuple[str, str] | None] = {start: None}
    queue = [start]
    while queue:
        node = queue.pop(0)
        for bearing in sorted(nodes[node]["exits"]):
            neighbor = nodes[node]["exits"][bearing]
            if neighbor not in parents:
                parents[neighbor] = (node, bearing)
                if neighbor == target:
                    queue.clear()
                    break
                queue.append(neighbor)
    if target not in parents:
        raise ValueError("MAP-22 target is unreachable.")
    path: list[str] = []
    cursor = target
    while parents[cursor] is not None:
        previous, bearing = parents[cursor]  # type: ignore[misc]
        path.append(bearing)
        cursor = previous
    path.reverse()
    return path


def _prepare_prefix(environment: Any, spec: V6EpisodeSpec) -> list[dict[str, Any]]:
    scene = get_scene(spec.instance_id)
    if scene.map_id == "MAP-22":
        memory = spec.condition_id in _MAP22_MEMORY_CONDITIONS
        rows: list[dict[str, Any]] = []
        recorded_nodes: set[str] = set()
        recorded_edges: set[frozenset[str]] = set()
        sign_to_node = {payload["sign"]: node for node, payload in scene.nodes.items()}
        for bearing in _map22_walk_to_target(scene):
            rows.append(_apply_prefix_action(environment, {"tool": "observe_signpost"}))
            observation = environment.observe()
            detail = observation.inspected_current_sign_detail
            if detail is None:
                raise AssertionError("MAP-22 local sign observation is missing.")
            origin_sign = detail["sign_id"]
            origin_node = sign_to_node[origin_sign]
            if memory and origin_sign not in recorded_nodes:
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
            rows.append(_apply_prefix_action(environment, {"tool": "move", "bearing": bearing}))
            if environment.is_terminal:
                raise AssertionError("MAP-22 shared prefix reached the target as terminal.")
            rows.append(_apply_prefix_action(environment, {"tool": "observe_signpost"}))
            arrival = environment.observe()
            arrival_detail = arrival.inspected_current_sign_detail
            if arrival_detail is None:
                raise AssertionError("MAP-22 arrival sign observation is missing.")
            destination_sign = arrival_detail["sign_id"]
            destination_node = sign_to_node[destination_sign]
            facts: list[dict[str, Any]] = []
            if memory and destination_sign not in recorded_nodes:
                facts.append(
                    {
                        "fact_type": "node_page",
                        "sign_id": destination_sign,
                        "exit_bearings": list(arrival.visible_exit_bearings),
                    }
                )
                recorded_nodes.add(destination_sign)
            edge = frozenset((origin_sign, destination_sign))
            if memory and edge not in recorded_edges:
                arrival_reverse = next(
                    key
                    for key, value in scene.nodes[destination_node]["exits"].items()
                    if value == origin_node
                )
                facts.append(
                    {
                        "fact_type": "traversed_edge_page",
                        "from_sign_id": origin_sign,
                        "departure_bearing": bearing,
                        "to_sign_id": destination_sign,
                        "arrival_reverse_bearing": arrival_reverse,
                    }
                )
                recorded_edges.add(edge)
            if facts:
                rows.append(
                    _apply_prefix_action(environment, {"tool": "write_memory", "facts": facts})
                )
        if environment.node != scene.target:
            raise AssertionError("MAP-22 shared prefix must end at the target.")
        return rows
    if scene.map_id == "MAP-26" and spec.condition_id.startswith("recovery_"):
        from agent_arena.v6.solvers import map26_recovery_prefix

        return [
            _apply_prefix_action(environment, payload)
            for payload in map26_recovery_prefix(spec.instance_id)
        ]
    if scene.map_id == "MAP-30" and getattr(scene, "use_recall_prefix", False):
        from agent_arena.v6.solvers import map30_recall_actions

        return [
            _apply_prefix_action(environment, payload) for payload in map30_recall_actions()
        ]
    return []


def _repository_root() -> Any:
    from pathlib import Path

    return Path(__file__).resolve().parents[3]



def _v6_clean_candidate(
    candidate: object, *, map_id: str, condition_id: str
) -> tuple[ScenarioV4Action | None, dict[str, Any] | None, str | None]:
    """Validate the Action strictly while tolerating optional-field quirks.

    V6 keeps the executable Action contract strict but treats the optional,
    Agent-owned belief channel and the free-text ``decision_reason`` as
    non-executable: models sometimes exceed the 280-character reason or nest
    ``agent_hypothesis_table`` inside ``action``, and V4's helper rejected the
    whole decision in those cases. Only the Action's legality decides validity.
    """

    if not isinstance(candidate, dict) or not isinstance(candidate.get("action"), dict):
        return None, None, None
    raw_action = dict(candidate["action"])
    nested_table = raw_action.pop("agent_hypothesis_table", None)
    raw_table = candidate.get("agent_hypothesis_table", nested_table)
    payload, recovered = _normalize_action_discriminator(raw_action)
    if payload.get("tool") == "set_timetable" and isinstance(payload.get("operations"), dict):
        payload["operations"] = {
            train: operation
            for train, operation in payload["operations"].items()
            if operation is not None
        }
    try:
        action = ScenarioV4Action.model_validate(payload, strict=True)
    except (ValidationError, TypeError, ValueError):
        return None, None, None
    allowed_shapes = _MAP_ACTION_SHAPES.get(map_id, {}).get(action.tool, set())
    if frozenset(action.model_fields_set) not in allowed_shapes:
        return None, None, None
    table: dict[str, Any] | None = None
    if condition_id == "hypothesis_table" and isinstance(raw_table, dict):
        try:
            table = V4HypothesisTable.model_validate(raw_table, strict=True).model_dump(
                mode="json"
            )
        except (ValidationError, TypeError, ValueError):
            table = None
    return action, table, recovered


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
    candidate: object, *, decision_index: int, observation: Any, condition_id: str
) -> dict[str, Any]:
    action, raw_table, recovered = _v6_clean_candidate(
        candidate, map_id=observation.map_id, condition_id=condition_id
    )
    table, status = _validate_hypothesis_update(raw_table, observation, condition_id)
    return {
        "decision_index": decision_index,
        "action": action.model_dump(mode="json", exclude_none=True) if action else None,
        "invalid_action": action is None,
        "agent_hypothesis_table": table,
        "hypothesis_table_status": status,
        "recovered_action_discriminator": recovered,
    }


def _failure_codes(
    environment: Any, outcome: str, decision_rows: list[dict[str, Any]]
) -> list[str]:
    codes: list[str] = []
    if outcome in {"provider_error", "provider_error_limit", "unknown_provider_spend"}:
        codes.append("PROVIDER_ERROR")
    if outcome == "input_context_limit":
        codes.append("INPUT_BUDGET_EXCEEDED")
    if outcome in {"episode_timeout", "global_provider_timeout", "decision_limit", "censored"}:
        codes.append("TIMEOUT")
    if environment.terminal_reason in {
        "ACTION_LIMIT_REACHED",
        "STEP_LIMIT_REACHED",
        "DEADLINE_REACHED",
    }:
        codes.append("TIMEOUT")
    if any(
        row.get("invalid_output_reason") is not None
        or (isinstance(row.get("result"), str) and row["result"].startswith("INVALID_"))
        for row in decision_rows
    ):
        codes.append("INVALID_ACTION")
    if environment.terminal_reason in {"CORE_WATER_LIMIT_EXCEEDED", "SPARES_EXHAUSTED"}:
        codes.append("RESOURCE_EXHAUSTION")
    if environment.terminal_reason in {
        "NODE_CAPACITY_CONFLICT",
        "SIDING_CAPACITY_CONFLICT",
        "SECTION_RESERVATION_CONFLICT",
        "HEAD_ON_SWAP",
        "HEAD_ON_COLLISION",
        "SEGMENT_CAPACITY",
        "STATION_CAPACITY_EXCEEDED",
    }:
        codes.append("SAFETY_VIOLATION")
    if environment.terminal_reason == "DEADLOCK":
        codes.append("NO_REPLAN")
    if environment.terminal_reason == "SEALANT_MISUSED":
        codes.append("WRONG_HYPOTHESIS")
    if not codes and outcome == "success":
        return []
    return codes or ["UNCLASSIFIED_OUTCOME"]


class V6PilotRunner:
    def __init__(
        self,
        *,
        provider: DecisionProvider,
        settings: RuntimeSettings,
        ledger: V6BudgetLedger,
        output_dir: Any,
        progress: Callable[[dict[str, Any]], None] | None = None,
        offline_gate_hash: str | None = None,
        runtime_commit: str | None = None,
        runtime_tree_hash: str | None = None,
        decision_limit: int = MAX_DECISIONS_PER_EPISODE,
    ) -> None:
        if not 1 <= decision_limit <= MAX_DECISIONS_PER_EPISODE:
            raise ValueError("V6 decision_limit must be within 1..100.")
        self.provider = provider
        self.settings = settings
        self.ledger = ledger
        self.output_dir = output_dir
        self.progress = progress or (lambda _: None)
        self.offline_gate_hash = offline_gate_hash
        self.runtime_commit = runtime_commit
        self.runtime_tree_hash = runtime_tree_hash
        self.decision_limit = decision_limit

    def run(self, spec: V6EpisodeSpec) -> dict[str, Any]:
        episode_id = spec.episode_id
        if episode_id in self.ledger.completed_episode_ids():
            return {"episode_id": episode_id, "status": "already_completed"}
        scene = get_scene(spec.instance_id)
        self.ledger.start_episode(
            episode_id, map_id=scene.map_id, seed=spec.seed, condition_id=spec.condition_id
        )
        self.progress(
            {
                "event": "episode_started",
                "episode_id": episode_id,
                "instance_id": spec.instance_id,
                "condition_id": spec.condition_id,
            }
        )
        episode_dir = self.output_dir / "episodes" / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        trace_path = episode_dir / "agent_trace.jsonl"
        environment = build_environment(scene, spec.condition_id, seed=spec.seed, step_limit=100)
        prefix_rows = _prepare_prefix(environment, spec)
        hypothesis_table = (
            {"belief_B": 0.34, "belief_D": 0.33, "belief_F": 0.33,
             "test_X_result": None, "test_Y_result": None, "next_test": "X"}
            if spec.condition_id == "hypothesis_table"
            else None
        )
        trace_rows = list(prefix_rows)
        header = {
            "event": "trace_header",
            "episode_id": episode_id,
            "instance_id": spec.instance_id,
            "map_id": scene.map_id,
            "condition_id": spec.condition_id,
            "seed": spec.seed,
            "scenario_hash": scenario_hash(scene),
            "provider": self.settings.provider,
            "model": self.settings.model_name,
            "agent_visible_only": True,
        }
        with trace_path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(header, ensure_ascii=False, sort_keys=True) + "\n")
            for row in trace_rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
        history = [
            {
                "action": row["action"],
                "result": row["result"],
                "tick": _history_tick(row["observation_after"]),
            }
            for row in prefix_rows
        ]
        self._write_manifest(episode_dir, spec, scene, episode_id, "running", None)
        outcome = "running"
        decision_count = 0
        decision_rows: list[dict[str, Any]] = []
        recent_results: list[str] = []
        started_epoch = datetime.fromisoformat(_utc_now()).timestamp()
        started_monotonic = time.monotonic()
        invalid_streak = 0
        while (
            outcome == "running"
            and environment.status.value == "running"
            and decision_count < self.decision_limit
        ):
            elapsed = max(
                time.time() - started_epoch, time.monotonic() - started_monotonic
            )
            if elapsed >= MAX_EPISODE_SECONDS:
                outcome = "episode_timeout"
                break
            if self.ledger.provider_wall_seconds() >= MAX_PROVIDER_SECONDS_GLOBAL:
                self.ledger.close("GLOBAL_PROVIDER_WALL_LIMIT")
                outcome = "global_provider_timeout"
                break
            observation = environment.observe()
            memory_data = v6_condition_memory(
                scene.map_id, spec.condition_id, observation, hypothesis_table
            )
            request = DecisionRequest(
                observation=observation,
                system_prompt=v6_system_prompt(
                    scene.map_id, spec.condition_id, structural=_structural_for(scene)
                ),
                correction=False,
                memory_data=memory_data,
                runtime_feedback=_public_repeat_reminder(recent_results),
                recent_history=v6_public_history(history, limit=5),
                max_output_tokens=1_024,
                action_contract_version="scenario_v4",
            )
            request_hash = _sha256(
                _json_bytes({"p": request.system_prompt, "r": request.recent_history})
            )
            input_upper_bound = _request_input_upper_bound_bytes(request)
            if input_upper_bound > MAX_INPUT_TOKENS_PER_REQUEST:
                _append_jsonl(
                    trace_path,
                    {
                        "event": "request_context_rejected",
                        "episode_id": episode_id,
                        "decision_index": decision_count + 1,
                        "utf8_input_upper_bound_bytes": input_upper_bound,
                    },
                )
                self.ledger.close(
                    "REQUEST_CONTEXT_EXCEEDS_REGISTERED_INPUT_CAP",
                    episode_id=episode_id,
                    decision_index=decision_count + 1,
                )
                outcome = "input_context_limit"
                break
            request_id = self.ledger.reserve_request(
                episode_id,
                decision_index=decision_count + 1,
                request_hash=request_hash,
            )
            self.progress(
                {
                    "event": "request_started",
                    "episode_id": episode_id,
                    "decision_index": decision_count + 1,
                }
            )
            request_started = time.monotonic()
            try:
                response = self.provider.decide(request)
            except DecisionProviderError as exc:
                latency_ms = max(0, round((time.monotonic() - request_started) * 1_000))
                self.ledger.fail_request(
                    request_id,
                    error_category=exc.error_category[:80],
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
                outcome = "provider_error"
                break
            except Exception as exc:  # noqa: BLE001
                latency_ms = max(0, round((time.monotonic() - request_started) * 1_000))
                self.ledger.fail_request(
                    request_id,
                    error_category=type(exc).__name__[:80],
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
            row = self._append_decision(
                environment, trace_path, spec, episode_id, payload, request_id, response, latency_ms
            )
            decision_rows.append(row)
            decision_count += 1
            recent_results.append(str(row["result"]))
            history.append(
                {
                    "action": row["action"],
                    "result": row["result"],
                    "tick": _history_tick(row["observation_after"]),
                }
            )
            if payload["agent_hypothesis_table"] is not None:
                hypothesis_table = payload["agent_hypothesis_table"]
            invalid_streak = invalid_streak + 1 if row["invalid_output_reason"] else 0
            if row["invalid_output_reason"] and (
                invalid_streak >= MAX_CONSECUTIVE_INVALID_ACTION_SCHEMAS
                or environment.status.value != "running"
            ):
                self.ledger.close(
                    "SYSTEMATIC_INVALID_ACTION_SCHEMA",
                    episode_id=episode_id,
                    decision_index=decision_count,
                )
                outcome = "invalid_action_schema_limit"
                break
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
        usage = self._episode_usage(episode_id)
        failure_codes = _failure_codes(environment, outcome, decision_rows)
        judge = {
            "episode_id": episode_id,
            "instance_id": spec.instance_id,
            "map_id": scene.map_id,
            "condition_id": spec.condition_id,
            "seed": spec.seed,
            "scenario_hash": scenario_hash(scene),
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
            "failure_classifications": [{"code": code} for code in failure_codes],
            "decision_count": decision_count,
            "usage": usage,
            "finished_at": _utc_now(),
        }
        _write_json_atomic(episode_dir / "judge_metrics.json", judge)
        self._write_manifest(episode_dir, spec, scene, episode_id, outcome, judge)
        if not self.ledger.closed:
            self.ledger.record(
                "episode_completed",
                episode_id=episode_id,
                instance_id=spec.instance_id,
                condition_id=spec.condition_id,
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
                "decision_count": decision_count,
            }
        )
        return {
            "episode_id": episode_id,
            "instance_id": spec.instance_id,
            "condition_id": spec.condition_id,
            "outcome": outcome,
            "v4_status": environment.status.value,
            "decision_count": decision_count,
        }

    def _append_decision(
        self,
        environment: Any,
        trace_path: Any,
        spec: V6EpisodeSpec,
        episode_id: str,
        payload: dict[str, Any],
        request_id: str,
        response: Any,
        latency_ms: int,
    ) -> dict[str, Any]:
        before = _observation_dict(environment)
        if payload["invalid_action"]:
            result = environment.reject_invalid_action()
            action_payload = None
        else:
            action_payload = payload["action"]
            result = environment.step(ScenarioV4Action.model_validate(action_payload, strict=True))
        row = {
            "event": "decision",
            "episode_id": episode_id,
            "decision_index": payload["decision_index"],
            "request_id": request_id,
            "action": action_payload,
            "invalid_output_reason": "schema_error" if payload["invalid_action"] else None,
            "recovered_action_discriminator": payload.get("recovered_action_discriminator"),
            "result": result.result,
            "status": result.status.value,
            "observation_before": before,
            "observation_after": result.observation.model_dump(mode="json"),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cached_input_tokens": response.cached_input_tokens,
            "latency_ms": latency_ms,
            "agent_hypothesis_table": payload["agent_hypothesis_table"],
            "state_hash_after": environment.state_hash(),
        }
        _append_jsonl(trace_path, row)
        return row

    def _episode_usage(self, episode_id: str) -> dict[str, Any]:
        events = self.ledger.read_events()
        reserved = [
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
        settled_cost = sum(
            (Decimal(str(event["actual_cost"])) for event in settled), Decimal(0)
        )
        return {
            "request_attempts": len(reserved),
            "settled_requests": len(settled),
            "failed_requests": len(failed),
            "unknown_spend_failures": sum(bool(event.get("unknown_spend")) for event in failed),
            "input_tokens": sum(int(event["input_tokens"]) for event in settled),
            "output_tokens": sum(int(event["output_tokens"]) for event in settled),
            "reported_usage_cost": str(settled_cost),
            "currency": self.ledger.prices.currency,
            "provider_wall_seconds": round(
                sum(float(event.get("latency_ms", 0)) / 1_000 for event in [*settled, *failed]), 3
            ),
        }

    def _write_manifest(
        self,
        episode_dir: Any,
        spec: V6EpisodeSpec,
        scene: Any,
        episode_id: str,
        status: str,
        judge: dict[str, Any] | None,
    ) -> None:
        trace_path = episode_dir / "agent_trace.jsonl"
        payload = {
            "episode_id": episode_id,
            "experiment_id": self.ledger.experiment_id,
            "instance_id": spec.instance_id,
            "map_id": scene.map_id,
            "level": scene.level,
            "condition_id": spec.condition_id,
            "seed": spec.seed,
            "scenario_hash": scenario_hash(scene),
            "runtime_contract": "scenario_v4",
            "provider": self.settings.provider,
            "model": self.settings.model_name,
            "temperature": 0,
            "max_decisions_per_episode": self.decision_limit,
            "runtime_commit": self.runtime_commit,
            "runtime_tree_hash": self.runtime_tree_hash,
            "offline_gate_hash": self.offline_gate_hash,
            "prompt_sha256": _sha256(
                v6_system_prompt(
                    scene.map_id, spec.condition_id, structural=_structural_for(scene)
                ).encode()
            ),
            "status": status,
            "usage": judge["usage"] if judge else None,
            "trace_sha256": _sha256(trace_path.read_bytes()) if trace_path.is_file() else None,
        }
        _write_json_atomic(episode_dir / "episode_manifest.json", payload)


__all__ = [
    "SMOKE",
    "V6EpisodeSpec",
    "V6PilotRunner",
    "registered_v6_matrix",
    "smoke_specs",
]
