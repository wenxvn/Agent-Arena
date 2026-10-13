from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from agent_arena.cli import _default_fake_responses, app
from agent_arena.config import RuntimeSettings
from agent_arena.llm import (
    FakeDecisionProvider,
    ProviderBudgetController,
    ProviderBudgetExceeded,
    ProviderBudgetLimits,
    ProviderResponse,
)
from agent_arena.llm.bailian import ModelVerificationError

runner = CliRunner()


def test_cli_exposes_foundation_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "run" in result.output
    assert "benchmark" in result.output
    assert "verify-model" in result.output


def test_run_writes_a_terminal_allowlisted_episode(monkeypatch, tmp_path: Path) -> None:
    defaults_file = tmp_path / "runtime.defaults.json"
    defaults_file.write_text(
        json.dumps(
            {
                "provider": "fake",
                "world": "spaceship-escape",
                "world_version": "spaceship-escape-v2-zh",
                "agent": "react",
                "seed": 0,
                "runs_dir": str(tmp_path / "runs"),
                "results_dir": "results",
                "step_limit": 30,
                "request_timeout_seconds": 30,
                "retry_count": 2,
                "retry_backoff_seconds": [1, 2],
                "enable_thinking": False,
                "model_name": "qwen3.7-plus",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(RuntimeSettings, "defaults_file", defaults_file)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    trace_paths = list((tmp_path / "runs").glob("*.json"))
    assert len(trace_paths) == 1
    assert trace_paths[0].name.startswith("episode_")
    assert "_react_seed-0_" in trace_paths[0].name
    trace = json.loads(trace_paths[0].read_text(encoding="utf-8"))
    assert trace["outcome"] == "success"
    assert trace["executed_action_count"] == 20
    assert len(trace["steps"]) == 20
    assert "本局结果：成功逃离飞船" in result.output
    assert "第 1 步 | 理由：根据当前可见信息推进逃生路线。" in result.output
    assert "OPENAI_API_KEY" not in trace_paths[0].read_text(encoding="utf-8")


def test_run_can_select_ollama_without_bailian_credentials(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agent_arena.cli.OllamaDecisionProvider",
        lambda settings: FakeDecisionProvider([]),
    )

    result = runner.invoke(
        app,
        ["run", "--provider", "ollama", "--output-dir", str(tmp_path / "runs")],
    )

    assert result.exit_code == 0
    assert "真实模型实验开始" in result.output
    assert "模型服务请求失败" in result.output


def test_benchmark_budget_interrupt_preserves_partial_status_and_returns_failure(
    monkeypatch, tmp_path: Path
) -> None:
    settings = RuntimeSettings.model_validate(
        {
            "provider": "fake",
            "world": "spaceship-escape",
            "world_version": "spaceship-escape-v2-zh",
            "agent": "react",
            "seed": 0,
            "runs_dir": tmp_path / "runs",
            "results_dir": tmp_path / "results",
            "step_limit": 5,
            "request_timeout_seconds": 30,
            "retry_count": 0,
            "retry_backoff_seconds": [],
            "enable_thinking": False,
            "model_name": "test-model",
            "max_provider_requests": 5,
            "max_provider_tokens": 4_000,
            "max_provider_output_tokens": 64,
            "provider_budget_timeout_seconds": 300,
            "provider_budget_experiment_id": "cli-budget-test",
            "provider_budget_expected_provider": "fake",
            "provider_budget_expected_model": "test-model",
            "provider_budget_expected_world_definition_hash": "world-hash",
            "provider_budget_expected_base_prompt_hash": "prompt-hash",
            "provider_budget_ledger": tmp_path / "budget.json",
        }
    )
    budget_controller = ProviderBudgetController(
        ProviderBudgetLimits(
            experiment_id="cli-budget-test",
            expected_provider="fake",
            expected_model="test-model",
            expected_world_definition_hash="world-hash",
            expected_base_prompt_hash="prompt-hash",
            max_requests=5,
            max_tokens=4_000,
            max_output_tokens_per_request=64,
            timeout_seconds=300,
        ),
        tmp_path / "budget.json",
    )
    written_rows = []
    monkeypatch.setattr("agent_arena.cli._load_settings", lambda **kwargs: settings)
    monkeypatch.setattr(
        "agent_arena.cli._create_provider_budget_controller",
        lambda current_settings: budget_controller,
    )
    monkeypatch.setattr(
        "agent_arena.cli._create_decision_provider",
        lambda current_settings, **kwargs: FakeDecisionProvider(
            [ProviderBudgetExceeded("active request overlap")]
        ),
    )
    monkeypatch.setattr("agent_arena.cli._validate_budget_world_identity", lambda *_: None)
    monkeypatch.setattr("agent_arena.cli._validate_budget_prompt_identity", lambda *_: None)
    monkeypatch.setattr(
        "agent_arena.cli.write_benchmark",
        lambda rows, output_dir: (
            written_rows.extend(rows) or tmp_path / "benchmark.json",
            tmp_path / "benchmark.csv",
        ),
    )

    result = runner.invoke(app, ["benchmark", "--episodes", "2", "--agent", "react"])

    assert result.exit_code == 2
    assert "基准测试提前停止" in result.output
    assert "（0/2 局完成）" in result.output
    assert written_rows == []
    assert not list((tmp_path / "runs").glob("*.json"))


def test_benchmark_identity_mismatch_preserves_prior_episode_summary(
    monkeypatch, tmp_path: Path
) -> None:
    settings = RuntimeSettings.model_validate(
        {
            "provider": "fake",
            "world": "spaceship-escape",
            "world_version": "spaceship-escape-v2-zh",
            "agent": "react",
            "seed": 0,
            "runs_dir": tmp_path / "runs",
            "results_dir": tmp_path / "results",
            "step_limit": 5,
            "request_timeout_seconds": 30,
            "retry_count": 0,
            "retry_backoff_seconds": [],
            "enable_thinking": False,
            "model_name": "test-model",
            "max_provider_requests": 100,
            "max_provider_tokens": 1_000_000,
            "max_provider_output_tokens": 64,
            "provider_budget_timeout_seconds": 300,
            "provider_budget_experiment_id": "cli-identity-budget-test",
            "provider_budget_expected_provider": "fake",
            "provider_budget_expected_model": "test-model",
            "provider_budget_expected_world_definition_hash": "world-hash",
            "provider_budget_expected_base_prompt_hash": "prompt-hash",
            "provider_budget_ledger": tmp_path / "identity-budget.json",
        }
    )
    budget_controller = ProviderBudgetController(
        ProviderBudgetLimits(
            experiment_id="cli-identity-budget-test",
            expected_provider="fake",
            expected_model="test-model",
            expected_world_definition_hash="world-hash",
            expected_base_prompt_hash="prompt-hash",
            max_requests=100,
            max_tokens=1_000_000,
            max_output_tokens_per_request=64,
            timeout_seconds=300,
        ),
        tmp_path / "identity-budget.json",
    )
    prompt_checks = 0

    def validate_prompt_identity(*_args) -> None:
        nonlocal prompt_checks
        prompt_checks += 1
        if prompt_checks == 2:
            raise ProviderBudgetExceeded("prompt identity mismatch")

    def create_provider(*_args, **_kwargs) -> FakeDecisionProvider:
        responses = [
            ProviderResponse(candidate=response, input_tokens=1, output_tokens=1)
            for response in _default_fake_responses("react")
        ]
        return FakeDecisionProvider(responses)

    monkeypatch.setattr("agent_arena.cli._load_settings", lambda **kwargs: settings)
    monkeypatch.setattr(
        "agent_arena.cli._create_provider_budget_controller",
        lambda current_settings: budget_controller,
    )
    monkeypatch.setattr("agent_arena.cli._create_decision_provider", create_provider)
    monkeypatch.setattr("agent_arena.cli._validate_budget_world_identity", lambda *_: None)
    monkeypatch.setattr(
        "agent_arena.cli._validate_budget_prompt_identity", validate_prompt_identity
    )

    result = runner.invoke(app, ["benchmark", "--episodes", "2", "--agent", "react"])

    benchmark_files = list((tmp_path / "results").glob("benchmark_*.json"))
    assert result.exit_code == 2
    assert "基准测试提前停止" in result.output
    assert "（1/2 局完成）" in result.output
    assert len(benchmark_files) == 1
    benchmark = json.loads(benchmark_files[0].read_text(encoding="utf-8"))
    assert len(benchmark["rows"]) == 1
    assert len(list((tmp_path / "runs").glob("*.json"))) == 1


def test_verify_model_does_not_echo_provider_exception_content(monkeypatch) -> None:
    class FailingVerifier:
        def __init__(self, settings: RuntimeSettings) -> None:
            del settings

        def verify(self) -> None:
            raise ModelVerificationError("secret-like-response-body")

    monkeypatch.setattr("agent_arena.cli.BailianModelVerifier", FailingVerifier)

    result = runner.invoke(app, ["verify-model"])

    assert result.exit_code == 1
    assert "模型验证失败" in result.output
    assert "secret-like-response-body" not in result.output
