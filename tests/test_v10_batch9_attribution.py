"""Batch 9 补充：trace 级失败归因的单元测试（合成 trace，不依赖 runs/）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent_arena.v10 import attribution


def _row(**overrides: Any) -> dict[str, Any]:
    base = {
        "run_id": "V10-MAP-TEST-S0-x",
        "map_id": "MAP-08",
        "environment_seed": 0,
        "mechanism_triggered": False,
        "decision_count": 4,
        "invalid_actions": 0,
        "outcome": "failure",
        "termination": "SOMETHING",
        "primary_metric_value": 0.0,
    }
    base.update(overrides)
    return base


@pytest.fixture()
def episodes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(attribution, "EPISODES", tmp_path)
    return tmp_path


def _write_trace(root: Path, run_id: str, decisions: list[tuple[dict[str, Any], str]]) -> None:
    path = root / run_id / "agent_trace.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": "trace_header"}, ensure_ascii=False) + "\n")
        for action, result in decisions:
            stream.write(
                json.dumps(
                    {"event": "decision", "action": action, "result": result},
                    ensure_ascii=False,
                )
                + "\n"
            )


def test_triggered_label(episodes: Path) -> None:
    row = _row(mechanism_triggered=True)
    assert attribution.attribute(row).label == "TRIGGERED"


def test_contract_artifact_by_invalid_ratio(episodes: Path) -> None:
    row = _row(decision_count=10, invalid_actions=9)
    assert attribution.attribute(row).label == "CONTRACT_ARTIFACT"


def test_key_action_never_attempted(episodes: Path) -> None:
    _write_trace(episodes, "V10-MAP-TEST-S0-x", [({"tool": "wait"}, "WAITED")])
    assert attribution.attribute(_row()).label == "KEY_ACTION_NEVER_ATTEMPTED"


def test_key_action_attempted_but_rejected(episodes: Path) -> None:
    _write_trace(
        episodes,
        "V10-MAP-TEST-S0-x",
        [({"tool": "run_test"}, "UNKNOWN_TEST"), ({"tool": "seal_diagnosis"}, "INVALID_DIAGNOSIS")],
    )
    gate = attribution.attribute(_row())
    assert gate.label == "KEY_ACTION_ATTEMPTED_REJECTED"
    assert gate.key_tool_rejected["run_test"] == 1


def test_key_action_used_without_trigger(episodes: Path) -> None:
    _write_trace(episodes, "V10-MAP-TEST-S0-x", [({"tool": "run_test"}, "TEST_RUN")])
    assert attribution.attribute(_row()).label == "KEY_ACTION_USED_NO_TRIGGER"


def test_legacy_flat_episode_file_is_read(episodes: Path) -> None:
    legacy = episodes / "V10-MAP-TEST-S0-legacy.json"
    legacy.write_text(
        json.dumps(
            {
                "run_id": "V10-MAP-TEST-S0-legacy",
                "history": [{"action": {"tool": "run_test"}, "result": "TEST_RUN"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    gate = attribution.attribute(_row(run_id="V10-MAP-TEST-S0-legacy"))
    assert gate.key_tool_attempts["run_test"] == 1
    assert gate.label == "KEY_ACTION_USED_NO_TRIGGER"


def test_interrupted_run_is_marked_invalid(episodes: Path) -> None:
    _write_trace(episodes, "V10-MAP-TEST-S0-x", [({"tool": "wait"}, "WAITED")])
    gate = attribution.attribute(_row(outcome="unknown_provider_spend"))
    assert gate.valid is False


def test_mechanism_tools_cover_native_maps() -> None:
    from agent_arena.v10.runtime.catalog import MAP_IDS, V10_MAPS

    for map_id in V10_MAPS:
        assert map_id in attribution.MECHANISM_TOOLS, map_id
    # 机制动作必须是该图真实存在的工具
    from agent_arena.v10.runtime.catalog import create_environment

    for map_id in V10_MAPS:
        tools = set(create_environment(map_id).SHAPES)
        assert set(attribution.MECHANISM_TOOLS[map_id]) <= tools, map_id
    assert len(MAP_IDS) == 30
