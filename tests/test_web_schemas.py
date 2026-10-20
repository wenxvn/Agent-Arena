"""V11 RunConfig / 状态机数据契约测试。"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from agent_arena.web.schemas import (
    OFFLINE_MODEL,
    OFFLINE_PROVIDER,
    RunConfig,
    RunMode,
    RunState,
    RunStatus,
)


def _config(**overrides: object) -> RunConfig:
    payload: dict[str, object] = {
        "map_id": "MAP-01",
        "environment_seed": 0,
        "mode": RunMode.OFFLINE,
        "provider_id": OFFLINE_PROVIDER,
        "model": OFFLINE_MODEL,
        "agent": "public_heuristic_policy",
        "max_decisions": 30,
        "max_requests": 1,
        "max_input_tokens": 10_000,
        "max_output_tokens": 1_000,
        "max_cost_cny": Decimal("0.01"),
    }
    payload.update(overrides)
    return RunConfig.model_validate(payload)


def test_offline_config_is_immutable_and_serializable() -> None:
    config = _config()
    assert config.mode is RunMode.OFFLINE
    with pytest.raises(ValidationError):
        config.map_id = "MAP-02"  # type: ignore[misc]
    payload = config.public_dict()
    assert payload["map_id"] == "MAP-01"
    assert "api_key" not in payload


def test_unknown_map_and_seed_are_rejected() -> None:
    with pytest.raises(ValidationError):
        _config(map_id="MAP-99")
    with pytest.raises(ValidationError):
        _config(environment_seed=99)


def test_offline_cannot_masquerade_as_model() -> None:
    with pytest.raises(ValidationError):
        _config(model="gpt-5.6-terra")
    with pytest.raises(ValidationError):
        _config(agent="v10_action_loop")


def test_live_requires_supported_provider() -> None:
    live = _config(
        mode=RunMode.LIVE,
        provider_id="openai_compatible",
        model="mimo-v2.6-flash",
        agent="v10_action_loop",
    )
    assert live.mode is RunMode.LIVE
    with pytest.raises(ValidationError):
        _config(
            mode=RunMode.LIVE,
            provider_id="custom_url",
            model="mimo-v2.6-flash",
            agent="v10_action_loop",
        )


def test_model_name_rejects_url_and_whitespace() -> None:
    for bad in ("https://evil.example/v1", "gpt 5", "   "):
        with pytest.raises(ValidationError):
            _config(
                mode=RunMode.LIVE,
                provider_id="openai_compatible",
                model=bad,
                agent="v10_action_loop",
            )


def test_bounds_are_enforced() -> None:
    for factory in (
        lambda: _config(max_decisions=0),
        lambda: _config(max_decisions=201),
        lambda: _config(max_requests=0),
        lambda: _config(max_cost_cny=Decimal("0")),
        lambda: _config(max_cost_cny=Decimal("21")),
        lambda: _config(max_output_tokens=50),
    ):
        with pytest.raises(ValidationError):
            factory()


def test_run_status_from_manifest_tolerates_missing_fields() -> None:
    status = RunStatus.from_manifest({"run_id": "web-x", "state": "RUNNING"})
    assert status.state is RunState.RUNNING
    assert status.config == {}
    assert status.decisions == 0
    assert not status.terminal
