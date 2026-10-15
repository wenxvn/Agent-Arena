from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import agent_arena.v5.runner as v5_runner
from agent_arena.config import RuntimeSettings
from agent_arena.llm.openai import OpenAIDecisionProvider
from agent_arena.llm.protocol import (
    DecisionRequest,
    ProviderResponse,
    decision_response_schema_strict,
)
from agent_arena.v5 import offline_gate
from agent_arena.v5.budget import (
    MAX_REQUESTS_GLOBAL,
    MAX_RESERVED_TOKENS_GLOBAL,
    PRICE_SHEETS,
    PilotBudgetClosed,
    V5BudgetLedger,
)
from agent_arena.v5.prompts import public_history, system_prompt
from agent_arena.v5.runner import (
    V5EpisodeSpec,
    V5PilotRunner,
    _clean_candidate,
    _context_policy,
    _failure_classifications,
    _prepare_prefix,
    _request_input_upper_bound_bytes,
    registered_matrix,
)
from agent_arena.worlds.scenario_v4 import ScenarioV4Action, create_environment
from agent_arena.worlds.scenario_v4.catalog import CONDITIONS, source_hash
from agent_arena.worlds.scenario_v4.map30 import CLAIMS, ENTRY_ORDER
from agent_arena.worlds.scenario_v4.models import V4JointOperation, V4MemoryFact
from scripts.run_v5_pilot import (
    _OfflineFakeProvider,
    _smoke_specs,
    _stage_gate_metadata,
    _verify_smoke,
    claim_pilot_registry,
    read_pilot_registry,
)


def test_registered_matrix_is_39_unique_episodes_with_three_seed_labels_per_map() -> None:
    matrix = registered_matrix()
    assert len(matrix) == 39
    assert len({item.episode_id for item in matrix}) == 39
    for map_id in ("MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30"):
        map_items = [item for item in matrix if item.map_id == map_id]
        assert len({item.seed for item in map_items}) == 3
    assert {
        item.condition_id for item in matrix if item.map_id == "MAP-30"
    } == {"history_full", "history5", "history5_casebook"}


def test_smoke_stage_gate_metadata_releases_all_33_remaining_registered_episodes() -> None:
    matrix = registered_matrix()
    smoke_ids = {spec.episode_id for spec in _smoke_specs()}
    metadata = _stage_gate_metadata(
        all_specs=matrix,
        smoke_ids=smoke_ids,
        smoke_report={"verified_at": "2026-10-15T00:00:00Z"},
    )

    assert metadata["remaining_episode_count"] == 33
    assert metadata["smoke_episode_ids"] == sorted(smoke_ids)
    assert len(smoke_ids) == 6


def test_all_registered_system_prompts_exclude_private_answer_and_source_material() -> None:
    private_markers = (
        "true_leak",
        "fault_part",
        "MARA_VENN",
        "Q4_CODE_INDEX",
        "oracle_trace",
        "future_events",
        "private_seed_reference",
    )
    for map_id, conditions in CONDITIONS.items():
        for condition_id in conditions:
            prompt = system_prompt(map_id, condition_id)
            assert not any(marker in prompt for marker in private_markers), (
                map_id,
                condition_id,
            )


def test_system_prompt_defines_complete_top_level_json_fields_without_placeholders() -> None:
    prompt = system_prompt("MAP-08", "no_hypothesis_table")

    assert '"decision_reason"' in prompt
    assert '"action"' in prompt
    assert '"agent_hypothesis_table"' in prompt
    assert "顶层只含这 3 个键" in prompt
    assert "不要输出 Markdown、代码围栏、占位符、省略号" in prompt
    assert "..." not in prompt

    hypothesis_prompt = system_prompt("MAP-08", "hypothesis_table")
    assert "belief_B/belief_D/belief_F" in hypothesis_prompt
    assert 'next_test（"X"/"Y"/"repair"）' in hypothesis_prompt


def test_map18_actual_provider_inputs_do_not_publish_future_fault_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_requests: list[dict[str, Any]] = []

    class FakeResponses:
        def create(self, **kwargs: Any) -> Any:
            captured_requests.append(kwargs)
            usage = SimpleNamespace(
                input_tokens=100,
                output_tokens=10,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
            )
            return SimpleNamespace(
                output_text=(
                    '{"decision_reason":"按当前公开信息","action":{"tool":"set_timetable",'
                    '"tick":0,"operations":{}},"agent_hypothesis_table":null}'
                ),
                usage=usage,
            )

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.responses = FakeResponses()

    monkeypatch.setattr("agent_arena.llm.openai.OpenAI", FakeOpenAI)
    provider = OpenAIDecisionProvider(_fake_v5_settings(tmp_path, provider="openai"))
    for condition_id in ("alert_off", "alert_on"):
        environment = create_environment("MAP-18", seed=0, condition_id=condition_id)
        for tick in range(5):
            request = DecisionRequest(
                observation=environment.observe(),
                system_prompt=system_prompt("MAP-18", condition_id),
                correction=False,
                action_contract_version="scenario_v4",
            )
            provider.decide(request)
            if tick == 0:
                initial_input = (
                    f"{captured_requests[-1]['instructions']}\n{captured_requests[-1]['input']}"
                )
                initial_segments = re.search(
                    r'"closed_segments":\s*(\[[^\]]*\])', initial_input
                )
                assert initial_segments is not None
                assert json.loads(initial_segments.group(1)) == []
            if tick == 4:
                tick4_input = (
                    f"{captured_requests[-1]['instructions']}\n{captured_requests[-1]['input']}"
                )
                tick4_segments = re.search(
                    r'"closed_segments":\s*(\[[^\]]*\])', tick4_input
                )
                assert tick4_segments is not None
                assert json.loads(tick4_segments.group(1)) == []
                if condition_id == "alert_on":
                    assert "unspecified" in tick4_input
            environment.step(
                ScenarioV4Action(tool="set_timetable", tick=tick, operations={})
            )
    assert len(captured_requests) == 10
    for request in captured_requests:
        model_input = f"{request['instructions']}\n{request['input']}"
        assert "R2-R3" not in model_input
        assert "tick 5 至 9" not in model_input
        assert "5–9" not in model_input
        assert "5-9" not in model_input


def test_map26_prompt_lists_public_operation_ids_without_seed_mapping() -> None:
    prompt = system_prompt("MAP-26", "free_diagnosis")
    for public_id in (
        "COMM_LOSS_LAST_TRANSMIT",
        "bus_load",
        "antenna_loopback",
        "software_checksum",
        "power_regulator",
        "antenna_coupler",
        "software_image",
        "T-D-A-B",
    ):
        assert public_id in prompt
    assert "FAULT_BY_SEED" not in prompt
    assert "seed 0" not in prompt
    assert "seed 1" not in prompt


def test_mimo_budget_prices_fit_registered_global_request_caps() -> None:
    assert MAX_REQUESTS_GLOBAL == 3_662
    assert MAX_RESERVED_TOKENS_GLOBAL == 33_748_992
    assert PRICE_SHEETS["CNY"].reserve_per_request() * MAX_REQUESTS_GLOBAL <= Decimal("37.50")
    assert PRICE_SHEETS["USD"].reserve_per_request() * MAX_REQUESTS_GLOBAL <= Decimal("5.25")


def test_frozen_offline_gate_validates_payload_and_live_source_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(offline_gate, "git_head", lambda: "commit-a")
    monkeypatch.setattr(offline_gate, "frozen_file_hashes", lambda: {"src/example.py": "sha-a"})
    monkeypatch.setattr(offline_gate, "map_source_hashes", lambda: {"MAP-08": "map-a"})
    source_hashes = {"src/example.py": "sha-a"}
    required_checks = (
        "scoped_ruff",
        "mypy",
        "pytest",
        "v4_oracle_replay",
        "independent_solvers",
        "fake_api_dry_run",
        "git_diff_check",
    )
    gate = {
        "status": "passed",
        "runtime_commit": "commit-a",
        "source_file_sha256": source_hashes,
        "runtime_tree_hash": offline_gate.runtime_tree_digest(source_hashes),
        "map_source_sha256": {"MAP-08": "map-a"},
        "checks": [{"name": name, "exit_code": 0} for name in required_checks],
        "dependency_lock_unchanged_from_head": True,
    }
    gate["frozen_gate_hash"] = offline_gate.gate_digest(gate)
    gate_path = tmp_path / "gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    assert offline_gate.load_and_validate_gate(gate_path) == gate

    gate["source_file_sha256"]["src/example.py"] = "sha-b"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    with pytest.raises(RuntimeError, match="content hash"):
        offline_gate.load_and_validate_gate(gate_path)


def test_paid_run_registry_prevents_a_second_ledger(tmp_path: Path) -> None:
    registry_path = tmp_path / "pilot_registry.json"
    registry = {
        "schema_version": "v5_pilot_registry_v1",
        "experiment_id": "experiment-1",
        "status": "running",
        "run_dir": "runs/v5/experiments/one",
        "ledger_path": "runs/v5/ledgers/one.jsonl",
        "offline_gate_hash": "gate-1",
    }
    claim_pilot_registry(registry_path, registry)

    assert read_pilot_registry(registry_path) == registry
    with pytest.raises(RuntimeError, match="already registered"):
        claim_pilot_registry(registry_path, registry)


def test_failure_classifications_retain_behavior_evidence_and_avoid_false_safety_claims() -> None:
    unsupported = _failure_classifications(
        map_id="MAP-30",
        outcome="success",
        terminal_reason="ALL_THREE_EVENTS_ACCOUNTED_FOR_AND_MARA_VENN_PROVEN",
        metrics={"unsupported_formal_accusations": 1},
        decision_rows=[],
    )
    assert [item["code"] for item in unsupported] == ["UNSUPPORTED_CLAIM"]

    forgotten_q4 = _failure_classifications(
        map_id="MAP-30",
        outcome="failure",
        terminal_reason="ACCUSATION_LIMIT_EXCEEDED",
        metrics={
            "q4_gap_observed": True,
            "q4_recalled_after_gap": False,
            "unsupported_formal_accusations": 1,
        },
        decision_rows=[{"event": "prefix_action", "result": "EVIDENCE_FOUND:Q4_CODE_INDEX"}],
    )
    assert {item["code"] for item in forgotten_q4} == {
        "MEMORY_LOSS",
        "UNSUPPORTED_CLAIM",
    }

    ordinary_map18 = _failure_classifications(
        map_id="MAP-18",
        outcome="failure",
        terminal_reason="DEADLINE_SERVICE_BELOW_70",
        metrics={"failure_counts": {"INVALID_TURNBACK": 2}},
        decision_rows=[],
    )
    assert "SAFETY_VIOLATION" not in {item["code"] for item in ordinary_map18}
    assert "TIMEOUT" in {item["code"] for item in ordinary_map18}

    safety_map18 = _failure_classifications(
        map_id="MAP-18",
        outcome="failure",
        terminal_reason="HEAD_ON_COLLISION",
        metrics={"failure_counts": {"HEAD_ON_COLLISION": 1}},
        decision_rows=[],
    )
    assert "SAFETY_VIOLATION" in {item["code"] for item in safety_map18}


def test_v5_ledger_reserves_before_use_tracks_reported_cost_and_refuses_reuse(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pilot.jsonl"
    ledger = V5BudgetLedger(
        path,
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={"MAP-08": "abc"},
    )
    ledger.start_episode("map08__test", map_id="MAP-08", seed=0, condition_id="no_hypothesis_table")
    request_id = ledger.reserve_request(
        "map08__test", decision_index=1, request_hash="req", retry=False
    )
    reservation = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    assert reservation["event"] == "request_reserved"
    assert reservation["max_input_tokens"] == 8_192
    assert reservation["max_output_tokens"] == 1_024
    ledger.settle_request(
        request_id,
        input_tokens=1_000,
        output_tokens=100,
        cached_input_tokens=200,
        latency_ms=123,
        decision_payload={"decision_index": 1, "action": {"tool": "wait"}},
    )
    snapshot = ledger.snapshot()
    assert snapshot["request_attempts"] == 1
    assert snapshot["reserved_tokens"] == 9_216
    assert snapshot["actual_cost_from_reported_usage"] == "0.001004"
    with pytest.raises(FileExistsError):
        V5BudgetLedger(
            path,
            currency="CNY",
            model="mimo-v2.6-flash",
            source_hashes={"MAP-08": "abc"},
        )


def test_unknown_usage_and_interrupted_requests_close_ledger(tmp_path: Path) -> None:
    path = tmp_path / "unknown-usage.jsonl"
    ledger = V5BudgetLedger(
        path,
        currency="USD",
        model="mimo-v2.6-flash",
        source_hashes={"MAP-08": "abc"},
    )
    ledger.start_episode("episode", map_id="MAP-08", seed=0, condition_id="hypothesis_table")
    request_id = ledger.reserve_request("episode", decision_index=1, request_hash="hash")
    with pytest.raises(PilotBudgetClosed):
        ledger.settle_request(
            request_id,
            input_tokens=None,
            output_tokens=None,
            cached_input_tokens=None,
            latency_ms=5,
            decision_payload={"invalid_action": True},
        )
    assert ledger.closed

    interrupted_path = tmp_path / "interrupted.jsonl"
    interrupted = V5BudgetLedger(
        interrupted_path,
        currency="USD",
        model="mimo-v2.6-flash",
        source_hashes={"MAP-08": "abc"},
    )
    interrupted.start_episode("episode", map_id="MAP-08", seed=0, condition_id="react")
    interrupted.reserve_request("episode", decision_index=1, request_hash="hash")
    with pytest.raises(PilotBudgetClosed, match="unknown spend"):
        V5BudgetLedger(
            interrupted_path,
            currency="USD",
            model="mimo-v2.6-flash",
            source_hashes={"MAP-08": "abc"},
            resume=True,
        )


def test_frozen_v4_json_schema_has_only_strict_closed_objects() -> None:
    schema = decision_response_schema_strict("scenario_v4")
    assert schema["required"] == ["decision_reason", "action", "agent_hypothesis_table"]

    def visit(value: object, path: str = "$") -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                properties = value.get("properties", {})
                assert value.get("additionalProperties") is False, path
                assert set(value.get("required", [])) == set(properties), path
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(schema)


def test_mimo_map18_null_train_slots_are_removed_before_strict_action_validation() -> None:
    candidate = {
        "decision_reason": "执行当前公开时刻表",
        "action": {
            "tool": "set_timetable",
            "tick": 0,
            "operations": {
                "T_R1": {"op": "temporary_stop"},
                "T_R2": None,
                "T_R3": None,
                "T_B": None,
                "T_G": None,
                "T_X": None,
            },
        },
        "agent_hypothesis_table": None,
    }
    action, hypothesis = _clean_candidate(candidate, map_id="MAP-18")
    assert action is not None
    assert action.operations is not None
    assert set(action.operations) == {"T_R1"}
    assert hypothesis is None


def test_v5_action_validation_rejects_null_required_fields_and_cross_map_shapes() -> None:
    invalid_candidates = (
        (
            "MAP-22",
            {"tool": "move", "bearing": None},
        ),
        (
            "MAP-18",
            {"tool": "set_timetable", "tick": 0, "operations": None},
        ),
        (
            "MAP-22",
            {"tool": "move", "to": "D"},
        ),
        (
            "MAP-08",
            {"tool": "set_timetable", "tick": 0, "operations": {}},
        ),
    )
    for map_id, action in invalid_candidates:
        candidate = {
            "decision_reason": "依当前观察选择动作",
            "action": action,
            "agent_hypothesis_table": None,
        }
        assert _clean_candidate(candidate, map_id=map_id) == (None, None)
        observation = create_environment(
            map_id, seed=0, condition_id=CONDITIONS[map_id][0]
        ).observe()
        payload = v5_runner._runtime_decision_payload(
            candidate,
            decision_index=1,
            observation=observation,
            condition_id=CONDITIONS[map_id][0],
        )
        assert payload["action"] is None
        assert payload["invalid_action"] is True

    with pytest.raises(ValueError, match="必填字段不得为空"):
        V4JointOperation.model_validate(
            {"op": "turnback", "reverse_toward": None, "duration_ticks": 1},
            strict=True,
        )
    with pytest.raises(ValueError, match="必填字段不得为空"):
        V4MemoryFact.model_validate(
            {"fact_type": "node_page", "sign_id": None, "exit_bearings": []}, strict=True
        )


def test_v5_provider_request_explicitly_disables_mimo_reasoning_and_uses_json_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    client_kwargs: dict[str, Any] = {}

    class FakeResponses:
        def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            usage = SimpleNamespace(
                input_tokens=123,
                output_tokens=22,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
            )
            return SimpleNamespace(
                output_text=(
                    '{"decision_reason":"状态明确","action":{"tool":"observe_signpost"},'
                    '"agent_hypothesis_table":null}'
                ),
                usage=usage,
            )

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            client_kwargs.update(kwargs)
            self.responses = FakeResponses()

    monkeypatch.setattr("agent_arena.llm.openai.OpenAI", FakeOpenAI)
    settings = RuntimeSettings(
        provider="openai",
        world="scenario_v4",
        world_version="V4",
        agent="react",
        seed=0,
        runs_dir=Path("runs"),
        results_dir=Path("results"),
        step_limit=100,
        request_timeout_seconds=30,
        retry_count=0,
        retry_backoff_seconds=[],
        enable_thinking=False,
        reasoning_effort="none",
        response_format="json_object",
        model_name="mimo-v2.6-flash",
        base_url="https://api.xiaomimimo.com/v1",
        openai_api_key="unit-test-key",
    )
    request = DecisionRequest(
        observation=create_environment("MAP-22", seed=0, condition_id="history5").observe(),
        system_prompt="只返回规定的 JSON 对象。",
        correction=False,
        action_contract_version="scenario_v4",
    )

    response = OpenAIDecisionProvider(settings).decide(request)

    assert isinstance(response.candidate, dict)
    assert captured["reasoning"] == {"effort": "none"}
    assert "store" not in captured
    assert captured["text"] == {"format": {"type": "json_object"}}
    assert captured["temperature"] == 0
    assert client_kwargs["default_headers"] == {}
    model_input = f"{captured['instructions']}\n{captured['input']}"
    assert not any(
        marker in model_input
        for marker in ("fault_part", "MARA_VENN", "Q4_CODE_INDEX", "oracle_trace")
    )


class _Map08FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        observation = request.observation
        if not hasattr(observation, "location"):
            raise AssertionError("Fake provider received a non-MAP-08 Observation.")
        if observation.location == "A" and not observation.test_results:
            action = {"tool": "move", "edge_id": "X_A"}
        elif observation.location == "X" and "X" not in observation.test_results:
            action = {
                "tool": "interact",
                "target_id": "X",
                "operation": "pressure_test_X",
            }
        elif observation.location == "X":
            action = {"tool": "move", "edge_id": "X_A"}
        elif observation.location == "A":
            action = {"tool": "move", "edge_id": "A_B"}
        else:
            action = {"tool": "interact", "target_id": "B", "operation": "repair_leak"}
        self.calls += 1
        return ProviderResponse(
            candidate={
                "decision_reason": "根据当前公开观察选择下一步。",
                "action": action,
                "agent_hypothesis_table": None,
            },
            input_tokens=200,
            output_tokens=30,
            cached_input_tokens=0,
        )


class _InvalidSchemaProvider:
    def __init__(self) -> None:
        self.calls = 0

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(candidate={"unexpected": "shape"}, input_tokens=10, output_tokens=5)


def test_v5_runner_closes_after_three_consecutive_invalid_action_schemas(
    tmp_path: Path,
) -> None:
    ledger = V5BudgetLedger(
        tmp_path / "invalid-schema-ledger.jsonl",
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={"MAP-08": source_hash("MAP-08")},
    )
    provider = _InvalidSchemaProvider()
    runner = V5PilotRunner(
        provider=provider,
        settings=_fake_v5_settings(tmp_path),
        ledger=ledger,
        output_dir=tmp_path / "invalid-schema-run",
        decision_limit=10,
    )

    result = runner.run(
        V5EpisodeSpec("MAP-08", "no_hypothesis_table", 0, "independent_seeded_instance")
    )

    events = ledger.read_events()
    close_event = next(event for event in events if event["event"] == "pilot_closed")
    assert result["outcome"] == "invalid_action_schema_limit"
    assert provider.calls == 3
    assert close_event["reason"] == "SYSTEMATIC_INVALID_ACTION_SCHEMA"
    assert close_event["consecutive_invalid_outputs"] == 3
    assert not any(event["event"] == "episode_completed" for event in events)


def _fake_v5_settings(tmp_path: Path, *, provider: str = "fake") -> RuntimeSettings:
    return RuntimeSettings(
        provider=provider,
        world="scenario_v4",
        world_version="V4",
        agent="react",
        seed=0,
        runs_dir=tmp_path / "runs",
        results_dir=tmp_path / "results",
        step_limit=100,
        request_timeout_seconds=30,
        retry_count=0,
        retry_backoff_seconds=[],
        enable_thinking=False,
        reasoning_effort="none",
        response_format="json_object",
        model_name="mimo-v2.6-flash",
        base_url="https://api.xiaomimimo.com/v1" if provider == "openai" else None,
        openai_api_key="unit-test-key" if provider == "openai" else None,
    )


def test_six_episode_smoke_evidence_gate_accepts_only_consistent_fake_ledger_artifacts(
    tmp_path: Path,
) -> None:
    gate = {
        "frozen_gate_hash": "gate-hash",
        "runtime_commit": "commit-hash",
        "runtime_tree_hash": "tree-hash",
    }
    source_hashes = {
        **{
            map_id: source_hash(map_id)
            for map_id in ("MAP-08", "MAP-16", "MAP-18", "MAP-22", "MAP-26", "MAP-30")
        },
        "__offline_gate__": gate["frozen_gate_hash"],
        "__runtime_tree__": gate["runtime_tree_hash"],
    }
    ledger = V5BudgetLedger(
        tmp_path / "smoke-ledger.jsonl",
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes=source_hashes,
    )
    runner = V5PilotRunner(
        provider=_OfflineFakeProvider(),
        settings=_fake_v5_settings(tmp_path, provider="openai"),
        ledger=ledger,
        output_dir=tmp_path / "smoke-run",
        offline_gate_hash=gate["frozen_gate_hash"],
        runtime_commit=gate["runtime_commit"],
        runtime_tree_hash=gate["runtime_tree_hash"],
        decision_limit=1,
    )
    for spec in _smoke_specs():
        runner.run(spec)

    report = _verify_smoke(ledger, tmp_path / "smoke-run", gate)

    assert report["episode_count"] == 6
    assert len(report["checks"]) == 6
    assert report["ledger_snapshot"]["request_attempts"] == 6


def test_v5_runner_resumes_from_settled_trace_without_duplicate_provider_calls(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "pilot.jsonl"
    ledger = V5BudgetLedger(
        ledger_path,
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={"MAP-08": source_hash("MAP-08")},
    )
    provider = _Map08FakeProvider()
    spec = V5EpisodeSpec("MAP-08", "no_hypothesis_table", 0, "independent_seeded_instance")

    def stop_after_two(payload: dict[str, Any]) -> None:
        if payload.get("event") == "decision_settled" and payload.get("decision_index") == 2:
            raise RuntimeError("test interruption after durable checkpoint")

    first_runner = V5PilotRunner(
        provider=provider,
        settings=_fake_v5_settings(tmp_path),
        ledger=ledger,
        output_dir=tmp_path / "experiment",
        progress=stop_after_two,
    )
    with pytest.raises(RuntimeError, match="test interruption"):
        first_runner.run(spec)
    assert provider.calls == 2

    resumed_ledger = V5BudgetLedger(
        ledger_path,
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={"MAP-08": source_hash("MAP-08")},
        resume=True,
    )
    resumed = V5PilotRunner(
        provider=provider,
        settings=_fake_v5_settings(tmp_path),
        ledger=resumed_ledger,
        output_dir=tmp_path / "experiment",
    ).run(spec, resume=True)

    assert resumed["outcome"] == "success"
    assert provider.calls == 5
    assert resumed_ledger.snapshot()["request_attempts"] == 5
    trace = (
        tmp_path / "experiment" / "episodes" / spec.episode_id / "agent_trace.jsonl"
    ).read_text(encoding="utf-8")
    assert trace.count('"event":"decision"') == 5
    assert "根据当前公开观察" not in trace
    assert '"true_leak"' not in trace


def test_v5_runner_recovers_first_settled_response_when_trace_has_only_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_path = tmp_path / "first-settled.jsonl"
    ledger = V5BudgetLedger(
        ledger_path,
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={"MAP-08": source_hash("MAP-08")},
    )
    provider = _Map08FakeProvider()
    spec = V5EpisodeSpec("MAP-08", "no_hypothesis_table", 0, "independent_seeded_instance")
    original_append = v5_runner._append_decision

    def interrupt_before_trace(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], Any]:
        raise RuntimeError("test interruption after settlement, before trace append")

    monkeypatch.setattr(v5_runner, "_append_decision", interrupt_before_trace)
    runner = V5PilotRunner(
        provider=provider,
        settings=_fake_v5_settings(tmp_path),
        ledger=ledger,
        output_dir=tmp_path / "first-settled-run",
        decision_limit=1,
    )
    with pytest.raises(RuntimeError, match="before trace append"):
        runner.run(spec)
    trace_path = (
        tmp_path
        / "first-settled-run"
        / "episodes"
        / spec.episode_id
        / "agent_trace.jsonl"
    )
    assert len(trace_path.read_text(encoding="utf-8").splitlines()) == 1
    assert sum(event["event"] == "request_settled" for event in ledger.read_events()) == 1
    assert provider.calls == 1

    monkeypatch.setattr(v5_runner, "_append_decision", original_append)
    resumed_ledger = V5BudgetLedger(
        ledger_path,
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={"MAP-08": source_hash("MAP-08")},
        resume=True,
    )
    resumed = V5PilotRunner(
        provider=provider,
        settings=_fake_v5_settings(tmp_path),
        ledger=resumed_ledger,
        output_dir=tmp_path / "first-settled-run",
        decision_limit=1,
    ).run(spec, resume=True)

    assert resumed["outcome"] == "decision_limit"
    assert provider.calls == 1
    assert resumed_ledger.snapshot()["request_attempts"] == 1
    assert len(trace_path.read_text(encoding="utf-8").splitlines()) == 2
    assert '"event":"decision"' in trace_path.read_text(encoding="utf-8")


def test_map22_paired_prefix_has_identical_movement_history_and_grounded_memory() -> None:
    baseline = create_environment("MAP-22", seed=0, condition_id="history5")
    memory = create_environment("MAP-22", seed=0, condition_id="history5_graph_memory")
    base_rows, base_history = _prepare_prefix(
        baseline, V5EpisodeSpec("MAP-22", "history5", 0, "fixed_scene_repeat")
    )
    memory_rows, memory_history = _prepare_prefix(
        memory,
        V5EpisodeSpec("MAP-22", "history5_graph_memory", 0, "fixed_scene_repeat"),
    )
    assert baseline.node == memory.node == "L"
    assert baseline.tick == memory.tick == 12
    assert base_history == memory_history
    assert baseline.observe().agent_authored_memory_journal == ()
    assert len(memory.observe().agent_authored_memory_journal) >= 20
    assert all(row["event"] == "prefix_action" for row in base_rows + memory_rows)


def test_map26_recovery_prefix_fixes_real_state_and_only_feedback_differs() -> None:
    observations = []
    private_states = []
    for condition in ("recovery_full", "recovery_hidden", "recovery_structured"):
        environment = create_environment("MAP-26", seed=0, condition_id=condition)
        rows, _ = _prepare_prefix(
            environment,
            V5EpisodeSpec("MAP-26", condition, 0, "same_seed_standardized_recovery_prefix"),
        )
        observations.append(environment.observe().model_dump(mode="json"))
        private_states.append(environment.judge_state())
        assert rows[-1]["result"] in {
            "POWER_SELF_TEST_OK_LINK_STILL_DOWN",
            "REPLACEMENT_FEEDBACK_HIDDEN",
            '{"communication":"still_down","event":"wrong_replacement_feedback","fault_component":"unknown","self_test":"passed","tested_part":"power_regulator"}',
        }
        assert environment.uninstalled_spares == 1
    assert private_states[0] == private_states[1] == private_states[2]
    assert len({item["last_action_result"] for item in observations}) == 3


def test_map30_casebook_pair_prefix_matches_public_last_five_events() -> None:
    hidden = create_environment("MAP-30", seed=0, condition_id="history5")
    visible = create_environment("MAP-30", seed=0, condition_id="history5_casebook")
    hidden_rows, _ = _prepare_prefix(
        hidden, V5EpisodeSpec("MAP-30", "history5", 0, "fixed_scene_repeat")
    )
    visible_rows, _ = _prepare_prefix(
        visible,
        V5EpisodeSpec("MAP-30", "history5_casebook", 0, "fixed_scene_repeat"),
    )
    assert hidden.node == visible.node == "J"
    assert hidden.tick == visible.tick
    assert hidden.observe().recent_action_window == visible.observe().recent_action_window
    assert hidden.observe().casebook == ()
    assert len(visible.observe().casebook) == 4
    assert len(hidden_rows) == len(visible_rows)
    visible_text = json.dumps(visible.observe().model_dump(mode="json"), ensure_ascii=False)
    hidden_text = json.dumps(hidden.observe().model_dump(mode="json"), ensure_ascii=False)
    assert "M-4对应档案员玛拉·维恩" in visible_text
    assert "MARA_VENN" in visible_text
    assert "MARA_VENN" not in hidden_text
    assert "M-4对应档案员玛拉·维恩" not in hidden_text


def test_map30_full_history_condition_retains_public_q4_evidence_within_context_cap(
    tmp_path: Path,
) -> None:
    full_spec = V5EpisodeSpec("MAP-30", "history_full", 0, "fixed_scene_repeat")
    recent_spec = V5EpisodeSpec("MAP-30", "history5", 0, "fixed_scene_repeat")
    full_environment = create_environment(
        "MAP-30", seed=0, condition_id="history_full"
    )
    recent_environment = create_environment("MAP-30", seed=0, condition_id="history5")
    full_rows, _ = _prepare_prefix(full_environment, full_spec)
    recent_rows, _ = _prepare_prefix(recent_environment, recent_spec)
    ledger = V5BudgetLedger(
        tmp_path / "history-full-ledger.jsonl",
        currency="CNY",
        model="offline-fake-v5",
        source_hashes={"MAP-30": source_hash("MAP-30")},
    )
    runner = V5PilotRunner(
        provider=_OfflineFakeProvider(),
        settings=_fake_v5_settings(tmp_path),
        ledger=ledger,
        output_dir=tmp_path / "history-full-run",
        decision_limit=1,
    )
    full_history = runner._history_from_trace(full_spec, full_rows, [])
    recent_history = runner._history_from_trace(recent_spec, recent_rows, [])
    interview_row = next(
        row
        for row in full_rows
        if any(
            event["result"] == "ANSWER_RECEIVED:ARCHIVE_Q4_INDEX_CONFIRMED"
            for event in row["observation_after"]["recent_action_window"]
        )
    )
    assert "MARA_VENN" in json.dumps(
        interview_row["observation_after"]["recent_action_window"], ensure_ascii=False
    )
    interview_position = full_rows.index(interview_row)
    assert all(
        "MARA_VENN" not in json.dumps(row["observation_after"], ensure_ascii=False)
        for row in full_rows[:interview_position]
    )

    assert len(full_history) == len(full_rows)
    assert len(recent_history) == 5
    assert "M-4对应档案员玛拉·维恩" in json.dumps(full_history, ensure_ascii=False)
    assert "MARA_VENN" in json.dumps(full_history, ensure_ascii=False)
    assert "M-4对应档案员玛拉·维恩" not in json.dumps(recent_history, ensure_ascii=False)
    assert "MARA_VENN" not in json.dumps(recent_history, ensure_ascii=False)
    one_more_decision_rows = [
        *full_rows,
        {
            "event": "decision",
            "action": {"tool": "inspect", "evidence_id": "E_TEST"},
            "result": {"ok": True, "message": "公开调查结果"},
            "observation_after": {},
        },
    ]
    one_more_decision_history = runner._history_from_trace(
        full_spec, one_more_decision_rows, []
    )
    full_request = DecisionRequest(
        observation=full_environment.observe(),
        system_prompt=system_prompt("MAP-30", "history_full"),
        correction=False,
        recent_history=public_history(full_history, limit=None),
        max_output_tokens=1_024,
        action_contract_version="scenario_v4",
    )
    assert _request_input_upper_bound_bytes(full_request) <= 8_192
    assert "完整公开轨迹" in full_request.recent_history
    assert "MARA_VENN" in full_request.recent_history
    next_request = DecisionRequest(
        observation=full_environment.observe(),
        system_prompt=system_prompt("MAP-30", "history_full"),
        correction=False,
        recent_history=public_history(one_more_decision_history, limit=None),
        max_output_tokens=1_024,
        action_contract_version="scenario_v4",
    )
    assert len(one_more_decision_history) == len(full_rows) + 1
    assert _request_input_upper_bound_bytes(next_request) <= 8_192

    summary = runner.run(full_spec)
    manifest_path = (
        tmp_path
        / "history-full-run"
        / "episodes"
        / full_spec.episode_id
        / "episode_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert summary["outcome"] == "decision_limit"
    assert manifest["context_policy"] == "current_public_observation_and_complete_public_history"
    assert _context_policy(recent_spec) == (
        "current_public_observation_and_last_five_public_actions"
    )
    assert _context_policy(
        V5EpisodeSpec("MAP-30", "history5_casebook", 0, "fixed_scene_repeat")
    ) == "current_public_observation_and_last_five_public_actions_and_recorded_casebook"


def test_map30_q4_recall_is_unmeasured_until_correct_post_gap_model_citation() -> None:
    def prepared_casebook() -> Any:
        environment = create_environment("MAP-30", seed=0, condition_id="history5_casebook")
        _prepare_prefix(
            environment,
            V5EpisodeSpec("MAP-30", "history5_casebook", 0, "fixed_scene_repeat"),
        )
        assert environment.metrics()["q4_gap_observed"] is True
        assert environment.metrics()["q4_recalled_after_gap"] is None
        return environment

    def accusation(person_id: str, cited_entry_ids: list[str]) -> dict[str, Any]:
        return {
            "tool": "formal_accuse",
            "person_id": person_id,
            "event_claims": [claim.model_dump(mode="json") for claim in CLAIMS],
            "cited_entry_ids": cited_entry_ids,
        }

    correct = prepared_casebook()
    correct.step(
        ScenarioV4Action.model_validate(
            accusation("MARA_VENN", list(ENTRY_ORDER)), strict=True
        )
    )
    assert correct.metrics()["q4_recalled_after_gap"] is True

    wrong_person = prepared_casebook()
    wrong_person.step(
        ScenarioV4Action.model_validate(accusation("OTHER_PERSON", list(ENTRY_ORDER)), strict=True)
    )
    assert wrong_person.metrics()["q4_recalled_after_gap"] is False

    omitted_citation = prepared_casebook()
    omitted_citation.step(
        ScenarioV4Action.model_validate(
            accusation("MARA_VENN", [entry for entry in ENTRY_ORDER if entry != "Q4_CODEBOOK"]),
            strict=True,
        )
    )
    assert omitted_citation.metrics()["q4_recalled_after_gap"] is False


def test_map08_candidate_set_sizes_shrink_by_observed_signature() -> None:
    amber = create_environment("MAP-08", seed=0, condition_id="no_hypothesis_table")
    amber.step(ScenarioV4Action(tool="move", edge_id="X_A"))
    amber.step(
        ScenarioV4Action(
            tool="interact", target_id="X", operation="pressure_test_X"
        )
    )
    assert amber.metrics()["candidate_set_sizes"] == [3, 1]

    slate_pair = create_environment("MAP-08", seed=8, condition_id="no_hypothesis_table")
    for edge_id in ("X_A",):
        slate_pair.step(ScenarioV4Action(tool="move", edge_id=edge_id))
    slate_pair.step(
        ScenarioV4Action(
            tool="interact", target_id="X", operation="pressure_test_X"
        )
    )
    for edge_id in ("X_C", "C_D", "Y_D"):
        slate_pair.step(ScenarioV4Action(tool="move", edge_id=edge_id))
    slate_pair.step(
        ScenarioV4Action(
            tool="interact", target_id="Y", operation="pressure_test_Y"
        )
    )
    assert slate_pair.metrics()["candidate_set_sizes"] == [3, 2, 1]
