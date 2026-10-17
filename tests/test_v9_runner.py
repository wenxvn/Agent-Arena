"""V9 Runner 的 FakeProvider 端到端测试（不调用真实 API）。"""

from __future__ import annotations

import json
from pathlib import Path

from agent_arena.config import RuntimeSettings
from agent_arena.llm.fake import FakeDecisionProvider
from agent_arena.llm.protocol import ProviderResponse
from agent_arena.v9.baseline_run import oracle_cases
from agent_arena.v9.budget import V9BudgetLedger
from agent_arena.v9.runner import V9EpisodeSpec, V9Runner
from agent_arena.worlds.scenario_v8.catalog import MAP_IDS, source_hash

SETTINGS = RuntimeSettings.model_construct(
    provider="openai",
    model_name="mimo-v2.6-flash",
    response_format="json_object",
)


def _ledger(root: Path) -> V9BudgetLedger:
    return V9BudgetLedger(
        root / "ledger.jsonl",
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={map_id: source_hash(map_id) for map_id in MAP_IDS},
    )


def _responses(actions: list[dict[str, object]]) -> list[ProviderResponse]:
    return [
        ProviderResponse(
            candidate={"decision_reason": "offline", "action": action},
            input_tokens=800,
            output_tokens=80,
        )
        for action in actions
    ]


def test_v9_runner_success_writes_artifacts(tmp_path: Path) -> None:
    case = oracle_cases("MAP-01")[0]
    actions = case["actions"]
    ledger = _ledger(tmp_path)
    runner = V9Runner(
        provider=FakeDecisionProvider(_responses(actions)),
        settings=SETTINGS,
        ledger=ledger,
        output_dir=tmp_path,
        commit="test-commit",
    )
    manifest = runner.run(V9EpisodeSpec("MAP-01", 0, len(actions), arm="v9_fixed"))
    assert manifest["success"] is True
    assert manifest["decision_count"] == len(actions)
    assert manifest["arm"] == "v9_fixed"
    trace = Path(manifest["agent_trace_path"])
    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["arm"] == "v9_fixed"
    assert rows[0]["agent_visible_only"] is True
    assert len([row for row in rows if row["event"] == "decision"]) == len(actions)
    assert Path(manifest["v9_metrics_path"]).is_file()
    assert ledger.snapshot()["settled_requests"] == len(actions)


def test_v9_runner_v8_compat_arm_uses_v8_prompt_hash(tmp_path: Path) -> None:
    from hashlib import sha256

    from agent_arena.v8.prompts import system_prompt as v8_prompt
    from agent_arena.worlds.scenario_v8.catalog import create_environment

    environment = create_environment("MAP-01")
    expected = sha256(
        v8_prompt(environment, decision_budget=18).encode("utf-8")
    ).hexdigest()
    case = oracle_cases("MAP-01")[0]
    runner = V9Runner(
        provider=FakeDecisionProvider(_responses(case["actions"])),
        settings=SETTINGS,
        ledger=_ledger(tmp_path),
        output_dir=tmp_path,
        commit="test-commit",
    )
    manifest = runner.run(V9EpisodeSpec("MAP-01", 0, 18, arm="v8_compat"))
    assert manifest["prompt_hash"] == expected


def test_v9_runner_budget_exhaustion_is_not_success(tmp_path: Path) -> None:
    runner = V9Runner(
        provider=FakeDecisionProvider(
            [
                ProviderResponse(
                    candidate={"action": {"tool": "wait", "turns": 1}},
                    input_tokens=100,
                    output_tokens=10,
                )
            ]
            * 3
        ),
        settings=SETTINGS,
        ledger=_ledger(tmp_path),
        output_dir=tmp_path,
        commit="test-commit",
    )
    manifest = runner.run(V9EpisodeSpec("MAP-04", 0, 3))
    assert manifest["status"] == "decision_budget_reached"
    assert manifest["success"] is False
