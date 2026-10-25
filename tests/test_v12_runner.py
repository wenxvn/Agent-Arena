"""V12 Runner 测试：30 图执行、V11 基线一致性、错误与预算路径、provenance。"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from v12_support import StubProvider, live_config, no_leak, simulated_config

from agent_arena.lab.policies.external import ExternalPolicyAdapter, register_external_plugin
from agent_arena.lab.registry import clear_external_agents
from agent_arena.lab.runner import run_lab_episode
from agent_arena.lab.simulated import SimulatedDecisionProvider
from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.web.execution import execute_live
from agent_arena.web.export import export_actions_csv, replay_document
from agent_arena.web.schemas import RunState
from agent_arena.web.service import RunService


def _run(map_id: str, agent: str = "basic.v1", **kwargs: object) -> object:
    environment = create_environment(map_id, environment_seed=0)
    provider = SimulatedDecisionProvider(
        map_id=map_id, shapes=environment.SHAPES, policy_seed=0
    )
    config = simulated_config(map_id, agent, **kwargs)  # type: ignore[arg-type]
    return run_lab_episode(config, provider=provider)


def test_all_thirty_maps_run_one_simulated_episode() -> None:
    from agent_arena.web.catalog import cards

    outcomes: dict[str, str] = {}
    for card in cards():
        outcome = _run(card.map_id, max_decisions=card.decision_budget, max_requests=200)
        outcomes[card.map_id] = outcome.state.value  # type: ignore[attr-defined]
        assert outcome.result["decision_count"] >= 1, card.map_id  # type: ignore[attr-defined]
        no_leak(outcome.result)  # type: ignore[attr-defined]
    assert len(outcomes) == 30
    assert all(state in {"SUCCEEDED", "FAILED", "BUDGET_REACHED"} for state in outcomes.values())


def test_basic_policy_matches_v11_action_loop_with_same_provider() -> None:
    """basic.v1 是基线锚点：同一 Provider 下动作序列与请求文本必须一致。"""

    map_id = "MAP-01"
    environment = create_environment(map_id, environment_seed=0)
    v11_provider = SimulatedDecisionProvider(map_id=map_id, shapes=environment.SHAPES)
    v11 = execute_live(
        live_config(map_id, max_decisions=6, max_requests=12),
        provider=v11_provider,
    )

    lab_provider = SimulatedDecisionProvider(map_id=map_id, shapes=environment.SHAPES)
    lab = run_lab_episode(
        live_config(map_id, max_decisions=6, max_requests=12), provider=lab_provider
    )
    assert lab.result["decision_count"] == v11.result["decision_count"]
    assert lab.result["outcome"] == v11.result["outcome"]
    assert lab.result["invalid_actions"] == v11.result["invalid_actions"]
    assert lab.result["rejected_actions"] == v11.result["rejected_actions"]
    assert len(lab_provider.calls) == len(v11_provider.calls)
    for left, right in zip(lab_provider.calls, v11_provider.calls, strict=True):
        assert left.system_prompt == right.system_prompt
        assert left.recent_history == right.recent_history
        assert left.correction == right.correction
        assert left.max_output_tokens == right.max_output_tokens
        assert left.output_contract == right.output_contract
        assert left.observation.model_dump() == right.observation.model_dump()


def test_basic_base_prompt_hash_matches_v11_prompt_hash() -> None:
    map_id = "MAP-18"
    environment = create_environment(map_id, environment_seed=0)
    provider = SimulatedDecisionProvider(map_id=map_id, shapes=environment.SHAPES)
    v11 = execute_live(live_config(map_id, max_decisions=2), provider=provider)
    lab = _run(map_id, max_decisions=2)
    assert lab.result["base_prompt_hash"] == v11.result["prompt_hash"]  # type: ignore[attr-defined]


def test_invalid_candidate_is_counted_and_run_terminates() -> None:
    config = simulated_config("MAP-22", max_decisions=4)
    provider = StubProvider([{"not_a_tool": 1}, {"tool": 3}, None, "oops"])
    outcome = run_lab_episode(config, provider=provider)
    assert outcome.result["invalid_actions"] == 4
    assert outcome.state in {RunState.FAILED, RunState.BUDGET_REACHED}
    assert outcome.result["decision_count"] == 4


def test_policy_exception_becomes_policy_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_external_agents()
    module = tmp_path / "broken_policy_plugin.py"
    module.write_text(
        "class Broken:\n"
        "    def decide(self, observation, context):\n"
        "        raise RuntimeError('boom')\n"
        "\n"
        "def make_policy(config):\n"
        "    return Broken()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    register_external_plugin(
        agent_id="broken.v1",
        module="broken_policy_plugin",
        attribute="make_policy",
        description="测试用异常策略",
    )
    try:
        config = simulated_config("MAP-22", "broken.v1", max_decisions=3)
        outcome = run_lab_episode(config, provider=StubProvider([]))
        assert outcome.state is RunState.FAILED
        assert outcome.outcome == "policy_error"
        assert "策略异常" in str(outcome.result.get("message"))
    finally:
        clear_external_agents()


def test_external_adapter_rejects_missing_plugin_interface() -> None:
    clear_external_agents()
    register_external_plugin(
        agent_id="noop.v1",
        module="agent_arena.lab.policies.external",
        attribute="ExternalPolicyAdapter",
        description="缺少工厂的插件",
    )
    try:
        adapter = ExternalPolicyAdapter("noop.v1", object())
        from agent_arena.lab.adapters import PublicObservation

        observation = PublicObservation.from_environment(
            {
                "map_id": "MAP-22",
                "terminal": False,
                "terminal_reason": None,
                "last_action_result": "READY",
            }
        )
        with pytest.raises(TypeError):
            adapter.decide(observation, None)
    finally:
        clear_external_agents()


def test_request_cap_stops_before_extra_request() -> None:
    config = simulated_config("MAP-22", max_decisions=50, max_requests=3)
    environment = create_environment("MAP-22")
    provider = SimulatedDecisionProvider(map_id="MAP-22", shapes=environment.SHAPES)
    outcome = run_lab_episode(config, provider=provider)
    assert outcome.state is RunState.BUDGET_REACHED
    assert outcome.result["termination"] == "request_limit_exceeded"
    assert len(provider.requests) if isinstance(provider.requests, list) else provider.requests == 3


def test_cost_cap_blocks_before_request() -> None:
    config = live_config("MAP-22", max_decisions=40, max_requests=40, max_cost_cny="0.01")
    environment = create_environment("MAP-22")
    provider = SimulatedDecisionProvider(map_id="MAP-22", shapes=environment.SHAPES)
    outcome = run_lab_episode(config, provider=provider)
    assert outcome.state is RunState.BUDGET_REACHED
    assert outcome.result["termination"] == "cost_limit_exceeded"
    assert provider.requests < 40


def test_unknown_usage_fails_closed() -> None:
    config = live_config("MAP-22", max_decisions=5)
    provider = StubProvider([{"tool": "observe_signpost"}], input_tokens=None, output_tokens=None)
    outcome = run_lab_episode(config, provider=provider)
    assert outcome.state is RunState.PROVIDER_ERROR
    assert outcome.outcome == "unknown_provider_spend"
    assert outcome.result["cost_unknown"] is True


def test_provider_exception_is_classified() -> None:
    from agent_arena.llm.bailian import DecisionProviderError

    config = live_config("MAP-22", max_decisions=5)
    provider = StubProvider(
        [],
        error=DecisionProviderError("x", error_category="APIConnectionError", unknown_spend=True),
        error_after=0,
    )
    outcome = run_lab_episode(config, provider=provider)
    assert outcome.state is RunState.PROVIDER_ERROR
    assert outcome.result["provider_error"] == "APIConnectionError"
    assert outcome.result["usage"]["cost_unknown"] is True


def test_provenance_fields_are_complete() -> None:
    outcome = _run("MAP-22", "planning.v1", max_decisions=8)
    result = outcome.result  # type: ignore[attr-defined]
    for key in (
        "agent_id",
        "agent_version",
        "agent_config_hash",
        "agent_contract_version",
        "base_prompt_hash",
        "prompt_hash",
    ):
        assert result["provenance"]["agent"][key], key
    for key in (
        "map_id",
        "environment_seed",
        "mode",
        "provider_id",
        "model",
        "scenario_hash",
        "rule_hash",
        "metric_hash",
        "metric_schema_hash",
    ):
        assert result["provenance"]["run"][key] is not None, key
    assert result["result_schema_version"] == "v12-lab-result-1"
    assert result["starting_observation"]["map_id"] == "MAP-22"
    no_leak(result)


def test_service_simulated_run_writes_replay_and_exports(tmp_path: Path) -> None:
    service = RunService(tmp_path / "web", recover=False)
    try:
        run_id = service.create_run(simulated_config("MAP-22", "memory.v1", max_decisions=6))
        status = service.wait(run_id, timeout=60)
        assert status.terminal
        replay = service.load_replay(run_id)
        assert replay["steps"], "没有决策事件"
        document = replay_document(replay["manifest"], replay["result"], replay["steps"])
        no_leak(document)
        csv_text = export_actions_csv(replay["steps"]).decode("utf-8-sig")
        assert len(csv_text.splitlines()) == len(replay["steps"]) + 1
        assert any(event.get("event") == "agent_event" for event in replay["events"])
        assert replay["result"]["mode"] == "simulated"
    finally:
        service.shutdown()


def test_simulated_mode_writes_no_global_ledger(tmp_path: Path) -> None:
    service = RunService(tmp_path / "web", recover=False)
    try:
        run_id = service.create_run(simulated_config("MAP-22", max_decisions=3))
        service.wait(run_id, timeout=60)
        ledger = tmp_path / "web" / "_ledger" / "web_ledger.jsonl"
        assert not ledger.is_file(), "模拟模式不得写付费账本"
    finally:
        service.shutdown()


def test_state_is_not_shared_between_runs(tmp_path: Path) -> None:
    service = RunService(tmp_path / "web", recover=False)
    try:
        first = service.create_run(simulated_config("MAP-22", "memory.v1", max_decisions=6))
        service.wait(first, timeout=60)
        second = service.create_run(
            simulated_config("MAP-22", "memory.v1", max_decisions=6, seed=1)
        )
        service.wait(second, timeout=60)
        first_result = service.load_replay(first)["result"] or {}
        second_result = service.load_replay(second)["result"] or {}
        assert first_result["run_id"] != second_result["run_id"]
        first_events = service.load_replay(first)["events"]
        second_events = service.load_replay(second)["events"]
        assert first_events != second_events
        assert first_result["starting_observation"]["current_sign"] == "camp"
        assert second_result["starting_observation"]["current_sign"] == "camp"
    finally:
        service.shutdown()


def test_cancel_simulated_run_is_cooperative(tmp_path: Path) -> None:
    service = RunService(tmp_path / "web", recover=False)
    try:
        run_id = service.create_run(
            simulated_config("MAP-22", max_decisions=80, max_requests=200)
        )
        service.cancel_run(run_id)
        status = service.wait(run_id, timeout=60)
        assert status.state in {RunState.CANCELLED, RunState.BUDGET_REACHED, RunState.FAILED}
        assert status.terminal
    finally:
        service.shutdown()


def test_budget_snapshot_records_limits() -> None:
    outcome = _run("MAP-22", max_decisions=4, max_requests=10)
    usage = outcome.result["usage"]  # type: ignore[attr-defined]
    assert usage["requests"] >= 1
    assert usage["limits"]["max_requests"] == 10
    assert json.dumps(usage, ensure_ascii=False)


def test_planning_extra_requests_are_counted() -> None:
    basic = _run("MAP-22", "basic.v1", max_decisions=12)
    planning = _run("MAP-22", "planning.v1", max_decisions=12)
    planning_requests = planning.result["usage"]["requests"]  # type: ignore[attr-defined]
    basic_requests = basic.result["usage"]["requests"]  # type: ignore[attr-defined]
    assert planning_requests > basic_requests
    assert planning.result["usage"]["purposes"]["planner"] >= 1  # type: ignore[attr-defined]


def test_offline_mode_still_uses_public_heuristic(tmp_path: Path) -> None:
    from v12_support import offline_config

    service = RunService(tmp_path / "web", recover=False)
    try:
        run_id = service.create_run(offline_config("MAP-01", max_decisions=30))
        status = service.wait(run_id, timeout=60)
        assert status.terminal
        result = service.load_replay(run_id)["result"] or {}
        assert result["mode"] == "offline"
        assert result["agent"] == "public_heuristic_policy"
        assert "provenance" not in result
    finally:
        service.shutdown()


def test_cost_is_zero_in_simulated_mode() -> None:
    outcome = _run("MAP-22", max_decisions=5)
    settled = Decimal(str(outcome.result["cost_settled_cny"]))  # type: ignore[attr-defined]
    assert settled == Decimal("0")
    assert outcome.result["cost_unknown"] is False  # type: ignore[attr-defined]


@pytest.mark.parametrize("agent", ["basic.v1", "memory.v1", "planning.v1", "reflection.v1"])
def test_each_agent_runs_on_core_map(agent: str) -> None:
    outcome = _run("MAP-22", agent, max_decisions=10, max_requests=40)
    assert outcome.result["decision_count"] >= 1  # type: ignore[attr-defined]
    assert outcome.result["agent"] == agent  # type: ignore[attr-defined]
