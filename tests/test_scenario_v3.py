from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_arena.agents import ReactAgent
from agent_arena.arena import ScenarioAction, ScenarioObservation, scenario_action_adapter
from agent_arena.config import RuntimeSettings
from agent_arena.evaluation import EpisodeOutcome, EpisodeRunner
from agent_arena.llm.protocol import DecisionRequest, ProviderResponse, decision_response_schema
from agent_arena.worlds import create_environment
from agent_arena.worlds.scenario.base import ScenarioEnvironment
from agent_arena.worlds.scenario.catalog import SCENARIO_REGISTRY
from agent_arena.worlds.scenario.oracle import public_oracle_action


class PublicOracleProvider:
    def __init__(self) -> None:
        self.contract_versions: list[str] = []

    def decide(self, request: DecisionRequest) -> ProviderResponse:
        self.contract_versions.append(request.action_contract_version)
        assert isinstance(request.observation, ScenarioObservation)
        action = public_oracle_action(request.observation)
        return ProviderResponse(
            candidate={
                "decision_reason": "根据当前公开状态执行参考策略。",
                "action": action.model_dump(mode="json"),
            }
        )


def v3_settings(environment: ScenarioEnvironment, step_limit: int = 100) -> RuntimeSettings:
    return RuntimeSettings.model_validate(
        {
            "provider": "fake",
            "world": environment.world,
            "world_version": environment.world_version,
            "agent": "react",
            "seed": 17,
            "runs_dir": "runs",
            "results_dir": "results",
            "step_limit": step_limit,
            "request_timeout_seconds": 30,
            "retry_count": 0,
            "retry_backoff_seconds": [],
            "enable_thinking": False,
            "model_name": "offline-oracle",
        }
    )


@pytest.mark.parametrize("selector", sorted(SCENARIO_REGISTRY))
def test_v3_public_oracle_completes_each_registered_scenario(selector: tuple[str, str]) -> None:
    world, version = selector
    environment = create_environment(world, version, seed=17)
    assert isinstance(environment, ScenarioEnvironment)
    observation = environment.reset(seed=17)

    for _ in range(100):
        action: ScenarioAction = public_oracle_action(observation)
        result, observation = environment.step(action)
        if environment.terminal_status.status.value != "running":
            break
        assert result.summary

    assert environment.terminal_status.status.value == "scenario_success", (
        environment.scenario_id,
        environment.terminal_status,
        observation.model_dump(mode="json"),
    )


def test_v3_trace_uses_scenario_contract_and_public_trace_fields() -> None:
    environment = create_environment("pyramid-escape", "pyramid-escape-world-v3-easy-zh", seed=17)
    assert isinstance(environment, ScenarioEnvironment)
    provider = PublicOracleProvider()
    prompt = Path(__file__).resolve().parents[1] / "prompts" / "react_scenario_v3.txt"
    trace = EpisodeRunner(
        environment,
        ReactAgent(provider, prompt_path=prompt),
        v3_settings(environment),
    ).run()

    assert trace.outcome is EpisodeOutcome.SCENARIO_SUCCESS
    assert trace.scenario_id == "PY-E"
    assert trace.trace_schema_version == 3
    assert trace.provenance.action_contract_version == "scenario_v3"
    assert provider.contract_versions
    assert set(provider.contract_versions) == {"scenario_v3"}
    assert all(step.observation is not None for step in trace.steps)
    serialized = trace.model_dump_json()
    assert "private_answer" not in serialized
    assert "oracle_plan" not in serialized


def test_v3_selector_hash_reset_and_observation_are_stable_and_allowlisted() -> None:
    env = create_environment("castle-escape", "castle-escape-world-v3-hard-zh", seed=4)
    assert isinstance(env, ScenarioEnvironment)
    first = env.reset(seed=4).model_dump(mode="json")
    first_hash = env.identity[-1]
    second = env.reset(seed=4).model_dump(mode="json")
    assert first == second
    assert first_hash == env.identity[-1]
    assert len(first_hash) == 64
    serialized = json.dumps(first, ensure_ascii=False).lower()
    assert "alden" not in serialized
    assert "private_culprit" not in serialized
    assert "facts" not in first


def test_v3_action_schema_is_strict_and_legacy_default_is_unchanged() -> None:
    with pytest.raises(ValidationError):
        scenario_action_adapter.validate_python({"tool": "wait", "turns": 2})
    with pytest.raises(ValidationError):
        scenario_action_adapter.validate_python(
            {"tool": "interact", "target": "valve", "choice": "close", "secret": True}
        )
    assert (
        DecisionRequest(observation={}, system_prompt="", correction=False).action_contract_version
        == "legacy_v1"
    )
    legacy_schema = decision_response_schema()
    assert len(legacy_schema["properties"]["action"]["$defs"]) >= 5


def test_v3_unknown_selector_does_not_fall_back_to_legacy_world() -> None:
    with pytest.raises(ValueError, match="未知的 V3 Scenario selector"):
        create_environment("spaceship-escape", "spaceship-escape-world-v3-nightmare-zh")


@pytest.mark.parametrize("selector", sorted(SCENARIO_REGISTRY))
def test_v3_all_selectors_have_stable_allowlisted_observations(
    selector: tuple[str, str],
) -> None:
    world, version = selector
    environment = create_environment(world, version, seed=23)
    assert isinstance(environment, ScenarioEnvironment)
    first = environment.reset(seed=23).model_dump(mode="json")
    identity = environment.identity
    assert environment.source_design_id == environment.scenario_id
    assert len(environment.definition_hash) == 64
    assert len(environment.ruleset_sha) == 64
    assert identity[:2] == (world, version)
    serialized = json.dumps(first, ensure_ascii=False).lower()
    for forbidden in ("private_truth", "private_answer", "oracle_plan", '"facts"'):
        assert forbidden not in serialized
    assert environment.reset(seed=23).model_dump(mode="json") == first
    assert environment.identity == identity


def test_v3_submit_answer_is_redacted_in_persisted_trace() -> None:
    class SubmitProvider:
        def decide(self, request: DecisionRequest) -> ProviderResponse:
            assert isinstance(request.observation, ScenarioObservation)
            return ProviderResponse(
                candidate={
                    "decision_reason": "提交结论以检查 Trace 脱敏。",
                    "action": {
                        "tool": "submit",
                        "target": "verdict_desk",
                        "answer": "MARIUS|KEY_LEDGER+SEAL_WAX",
                    },
                }
            )

    environment = create_environment("castle-escape", "castle-escape-world-v3-hard-zh", seed=9)
    assert isinstance(environment, ScenarioEnvironment)
    prompt = Path(__file__).resolve().parents[1] / "prompts" / "react_scenario_v3.txt"
    trace = EpisodeRunner(
        environment,
        ReactAgent(SubmitProvider(), prompt_path=prompt),
        v3_settings(environment, step_limit=1),
    ).run()

    assert trace.steps[0].action is not None
    assert trace.steps[0].action.model_dump(mode="json")["answer"] == "[redacted]"
    serialized = trace.model_dump_json()
    assert "MARIUS|KEY_LEDGER+SEAL_WAX" not in serialized
    assert trace.steps[0].scenario_event == "evidence_incomplete"
