"""V12 第三方 SDK 与只读导入测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from v12_support import StubProvider, simulated_config

from agent_arena.lab.contracts import AgentArm, ExperimentMode, ExperimentSpec
from agent_arena.lab.registry import clear_external_agents, get_agent, registered_agent_ids
from agent_arena.lab.runner import run_lab_episode
from agent_arena.lab.sdk import (
    PLUGIN_ALLOWLIST_ENV,
    ImportRejected,
    PluginLoadError,
    install_plugin,
    load_plugin,
    plugin_allowlist,
    read_public_run_file,
    replay_steps,
)
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER


def test_example_plugin_imports_and_runs() -> None:
    clear_external_agents()
    try:
        install_plugin(
            agent_id="test_first.v1",
            module="examples.custom_agent.policy",
            attribute="make_policy",
            version="0.1.0",
            display_name="TestFirst",
            description="示例策略",
            default_config={"use_model": False},
            allowed_config_keys=("use_model",),
        )
        assert "test_first.v1" in registered_agent_ids()
        outcome = run_lab_episode(
            simulated_config("MAP-08", "test_first.v1", max_decisions=8, max_requests=20),
            provider=StubProvider([]),
        )
        assert outcome.result["agent"] == "test_first.v1"
        assert outcome.result["decision_count"] >= 1
        assert outcome.result["state"] in {"SUCCEEDED", "FAILED", "BUDGET_REACHED"}
    finally:
        clear_external_agents()


def test_example_plugin_uses_public_tests_first() -> None:
    clear_external_agents()
    try:
        install_plugin(
            agent_id="test_first.v1",
            module="examples.custom_agent.policy",
            attribute="make_policy",
            default_config={"use_model": False},
            allowed_config_keys=("use_model",),
        )
        events: list[dict[str, Any]] = []
        run_lab_episode(
            simulated_config("MAP-08", "test_first.v1", max_decisions=6, max_requests=20),
            provider=StubProvider([]),
            on_event=events.append,
        )
        decisions = [event for event in events if event.get("event") == "decision"]
        assert (decisions[0].get("action") or {}).get("tool") == "run_test"
    finally:
        clear_external_agents()


def test_plugin_allowlist_blocks_unknown_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PLUGIN_ALLOWLIST_ENV, raising=False)
    assert plugin_allowlist() == ()
    with pytest.raises(PluginLoadError):
        load_plugin("agent_arena.lab.policies.basic")


def test_plugin_allowlist_accepts_registered_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PLUGIN_ALLOWLIST_ENV, "agent_arena.lab.policies.basic")
    assert plugin_allowlist() == ("agent_arena.lab.policies.basic",)
    # 模块可加载（这里只校验 allowlist 生效，不注册成策略）。
    with pytest.raises(PluginLoadError):
        # BasicPolicy 模块没有 make_policy 工厂。
        load_plugin("agent_arena.lab.policies.basic")


def test_plugin_rejects_illegal_module_name() -> None:
    with pytest.raises(PluginLoadError):
        load_plugin("../etc/passwd")


def test_example_agent_is_registered_in_spec_and_comparable() -> None:
    clear_external_agents()
    try:
        install_plugin(
            agent_id="test_first.v1",
            module="examples.custom_agent.policy",
            attribute="make_policy",
            default_config={"use_model": False},
            allowed_config_keys=("use_model",),
        )
        spec = ExperimentSpec(
            name="sdk",
            maps=["MAP-08"],
            agent_arms=[
                AgentArm(agent_id="test_first.v1"),
                AgentArm(agent_id="basic.v1"),
            ],
            environment_seeds=[0],
            provider_id=SIMULATED_PROVIDER,
            model=SIMULATED_MODEL,
            mode=ExperimentMode.SIMULATED,
        )
        assert len(spec.matrix()) == 2
        assert spec.agent_arms[0].config == {"use_model": False}
    finally:
        clear_external_agents()


def test_plugin_missing_from_registry_after_uninstall() -> None:
    clear_external_agents()
    with pytest.raises(KeyError):
        get_agent("test_first.v1")


def _replay_document() -> dict[str, Any]:
    return {
        "schema_version": "v11-web-replay-1",
        "run": {"run_id": "web-20260101T000000Z-abcdef12", "map_id": "MAP-22"},
        "result": {"state": "FAILED", "success": False},
        "steps": [
            {
                "event": "decision",
                "decision_index": 1,
                "action": {"tool": "observe_signpost"},
                "result": "SIGN_OBSERVED:camp",
            }
        ],
    }


def test_read_public_run_file_accepts_public_document(tmp_path: Path) -> None:
    path = tmp_path / "replay.json"
    path.write_text(json.dumps(_replay_document(), ensure_ascii=False), encoding="utf-8")
    imported = read_public_run_file(path)
    assert imported["read_only"] is True
    assert imported["schema_version"] == "v11-web-replay-1"
    assert imported["sha256"]
    assert len(replay_steps(imported["document"])) == 1


def test_read_public_run_file_rejects_hidden_truth(tmp_path: Path) -> None:
    payload = _replay_document()
    payload["result"]["sealed_truth"] = {"graph": {}}
    path = tmp_path / "leak.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ImportRejected):
        read_public_run_file(path)


def test_read_public_run_file_rejects_unknown_schema(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "nope"}), encoding="utf-8")
    with pytest.raises(ImportRejected):
        read_public_run_file(path)


def test_read_public_run_file_rejects_non_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.txt"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ImportRejected):
        read_public_run_file(path)


def test_read_public_run_file_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ImportRejected):
        read_public_run_file(tmp_path / "missing.json")


def test_import_does_not_touch_ledger(tmp_path: Path) -> None:
    path = tmp_path / "replay.json"
    path.write_text(json.dumps(_replay_document(), ensure_ascii=False), encoding="utf-8")
    read_public_run_file(path)
    assert not (tmp_path / "_ledger").exists()
    assert not (tmp_path / "web_ledger.jsonl").exists()
