from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_arena.config import RuntimeSettings


def write_defaults(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "provider": "fake",
                "world": "test-world",
                "world_version": "test-world-v1",
                "agent": "react",
                "seed": 0,
                "runs_dir": "runs",
                "results_dir": "results",
                "step_limit": 30,
                "request_timeout_seconds": 30,
                "retry_count": 2,
                "retry_backoff_seconds": [1, 2],
                "enable_thinking": False,
                "model_name": "default-model",
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def isolated_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    defaults_file = tmp_path / "runtime.defaults.json"
    write_defaults(defaults_file)
    monkeypatch.setattr(RuntimeSettings, "defaults_file", defaults_file)
    return defaults_file


def test_runtime_settings_use_defaults_then_environment_then_cli(
    isolated_defaults: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "environment-model")
    monkeypatch.setenv("AGENT_ARENA_SEED", "5")

    settings = RuntimeSettings.load(env_file=None)
    cli_settings = RuntimeSettings.load({"model_name": "cli-model", "seed": 9}, env_file=None)

    assert settings.model_name == "environment-model"
    assert settings.seed == 5
    assert cli_settings.model_name == "cli-model"
    assert cli_settings.seed == 9


def test_fake_provider_does_not_require_bailian_credentials(isolated_defaults: Path) -> None:
    settings = RuntimeSettings.load(env_file=None)

    assert settings.provider == "fake"
    assert settings.memory_version == "v2"


def test_memory_v3_is_an_explicit_memory_agent_policy(isolated_defaults: Path) -> None:
    settings = RuntimeSettings.load(
        {"agent": "memory", "memory_version": "v3_spatial_event"}, env_file=None
    )

    assert settings.memory_version == "v3_spatial_event"
    with pytest.raises(ValueError, match="only valid with agent=memory"):
        RuntimeSettings.load({"memory_version": "v3_spatial_event"}, env_file=None)


def test_ollama_uses_its_own_default_endpoint_and_model(isolated_defaults: Path) -> None:
    settings = RuntimeSettings.load({"provider": "ollama"}, env_file=None)

    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.selected_model_name == "qwen2.5:7b"


def test_conflicting_bailian_keys_are_rejected_when_used(
    isolated_defaults: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "first-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "second-key")

    settings = RuntimeSettings.load({"provider": "bailian"}, env_file=None)

    with pytest.raises(ValueError, match="must match"):
        settings.require_bailian()


def test_openai_provider_uses_only_the_openai_api_key(
    isolated_defaults: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "different-bailian-key")

    settings = RuntimeSettings.load({"provider": "openai"}, env_file=None)

    base_url, api_key = settings.require_openai()
    assert base_url == "https://relay.example/v1"
    assert api_key.get_secret_value() == "openai-key"


def test_retry_delays_must_match_the_retry_count(isolated_defaults: Path) -> None:
    with pytest.raises(ValueError, match="one delay"):
        RuntimeSettings.load({"retry_count": 1}, env_file=None)


def test_provider_budget_requires_complete_caps_and_disables_retries(
    isolated_defaults: Path,
) -> None:
    with pytest.raises(ValueError, match="require all caps"):
        RuntimeSettings.load(
            {"max_provider_requests": 10},
            env_file=None,
        )

    with pytest.raises(ValueError, match="retry_count=0"):
        RuntimeSettings.load(
            {
                "max_provider_requests": 10,
                "max_provider_tokens": 10_000,
                "max_provider_output_tokens": 64,
                "provider_budget_timeout_seconds": 300,
                "provider_budget_experiment_id": "config-test",
                "provider_budget_expected_provider": "fake",
                "provider_budget_expected_model": "test-model",
                "provider_budget_expected_world_definition_hash": "world-hash",
                "provider_budget_expected_base_prompt_hash": "prompt-hash",
                "provider_budget_ledger": Path("results/budget-test.json"),
            },
            env_file=None,
        )

    settings = RuntimeSettings.load(
        {
            "retry_count": 0,
            "max_provider_requests": 10,
            "max_provider_tokens": 10_000,
            "max_provider_output_tokens": 64,
            "provider_budget_timeout_seconds": 300,
            "provider_budget_experiment_id": "config-test",
            "provider_budget_expected_provider": "fake",
            "provider_budget_expected_model": "test-model",
            "provider_budget_expected_world_definition_hash": "world-hash",
            "provider_budget_expected_base_prompt_hash": "prompt-hash",
            "provider_budget_ledger": Path("results/budget-test.json"),
        },
        env_file=None,
    )
    assert settings.retry_count == 0
    assert settings.retry_backoff_seconds == []


def test_provider_budget_rejects_selected_provider_mismatch(isolated_defaults: Path) -> None:
    with pytest.raises(ValueError, match="does not match the frozen provider"):
        RuntimeSettings.load(
            {
                "provider": "openai",
                "retry_count": 0,
                "max_provider_requests": 10,
                "max_provider_tokens": 10_000,
                "max_provider_output_tokens": 64,
                "provider_budget_timeout_seconds": 300,
                "provider_budget_experiment_id": "config-test",
                "provider_budget_expected_provider": "fake",
                "provider_budget_expected_model": "test-model",
                "provider_budget_expected_world_definition_hash": "world-hash",
                "provider_budget_expected_base_prompt_hash": "prompt-hash",
                "provider_budget_ledger": Path("results/budget-test.json"),
            },
            env_file=None,
        )
