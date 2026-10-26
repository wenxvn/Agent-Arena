"""DCR-V12-03 假设验证：路线日志开关（memory.v1 的策略变量）。"""

from __future__ import annotations

from decimal import Decimal

from agent_arena.lab.policies.memory import MemoryPolicy
from agent_arena.lab.registry import get_agent
from agent_arena.lab.runner import run_lab_episode
from agent_arena.lab.simulated import SimulatedDecisionProvider
from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.web.schemas import (
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
    RunConfig,
    RunMode,
)


def _config(agent_config: dict[str, object]) -> RunConfig:
    return RunConfig(
        map_id="MAP-22",
        environment_seed=0,
        mode=RunMode.SIMULATED,
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        agent="memory.v1",
        agent_config=dict(agent_config),
        max_decisions=40,
        max_requests=40,
        max_input_tokens=400_000,
        max_output_tokens=8_000,
        max_cost_cny=Decimal("1"),
    )


def test_route_log_is_off_by_default() -> None:
    registration = get_agent("memory.v1")
    assert registration.normalize_config({})["route_log"] is False
    policy = MemoryPolicy()
    assert policy.route_log is False


def test_route_log_changes_config_hash() -> None:
    registration = get_agent("memory.v1")
    off = registration.normalize_config({"route_log": False})
    on = registration.normalize_config({"route_log": True})
    assert off != on


def test_route_log_writes_path_state_without_model_requests() -> None:
    environment = create_environment("MAP-22")
    provider = SimulatedDecisionProvider(map_id="MAP-22", shapes=environment.SHAPES)
    outcome = run_lab_episode(
        _config({"route_log": True, "route_write_every": 1, "route_write_limit": 8}),
        provider=provider,
    )
    events = [e for e in outcome.result["agent_events"] if e["agent_event"] == "route_logged"]
    assert events, "开启路线日志后必须产生 route_logged 事件"
    assert all(item["requests"] == 0 for item in events), "日志动作不得调用模型"
    assert outcome.result["provenance"]["policy"]["route_log"] is True
    # 至少要有一条 path_state 写入被环境接受。
    assert outcome.result["provenance"]["policy"]["route_writes"] >= 1


def test_route_log_off_has_no_route_events() -> None:
    environment = create_environment("MAP-22")
    provider = SimulatedDecisionProvider(map_id="MAP-22", shapes=environment.SHAPES)
    outcome = run_lab_episode(_config({"route_log": False}), provider=provider)
    assert not [
        e for e in outcome.result["agent_events"] if e["agent_event"] == "route_logged"
    ]


def test_route_log_respects_write_limit() -> None:
    environment = create_environment("MAP-22")
    provider = SimulatedDecisionProvider(map_id="MAP-22", shapes=environment.SHAPES)
    outcome = run_lab_episode(
        _config({"route_log": True, "route_write_every": 1, "route_write_limit": 3}),
        provider=provider,
    )
    events = [e for e in outcome.result["agent_events"] if e["agent_event"] == "route_logged"]
    assert len(events) <= 3


def test_route_log_reset_clears_state() -> None:
    policy = MemoryPolicy({"route_log": True})
    from agent_arena.lab.adapters import PublicEpisodeContext

    def context() -> PublicEpisodeContext:
        return PublicEpisodeContext(
            run_id="r",
            experiment_id=None,
            map_id="MAP-22",
            environment_seed=0,
            agent_id="memory.v1",
            agent_version="1.0.0",
            agent_config={},
            decision_budget=10,
            max_requests=20,
            public_rules=(),
            action_contract="",
            system_prompt="",
            history_window=5,
            mode="simulated",
        )

    policy.reset(context())
    policy._route = ["west", "north"]
    policy.reset(context())
    assert policy.snapshot()["route_length"] == 0
    assert policy.snapshot()["route_writes"] == 0
