"""V8 Runner 的 FakeProvider 端到端行为与失败停机。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import DecisionProviderError
from agent_arena.llm.fake import FakeDecisionProvider
from agent_arena.llm.protocol import ProviderResponse
from agent_arena.v8.budget import V8BudgetLedger
from agent_arena.v8.runner import V8EpisodeSpec, V8Runner
from agent_arena.worlds.scenario_v8.catalog import MAP_IDS, source_hash
from agent_arena.worlds.scenario_v8.oracle import load_oracle_groups

SETTINGS = RuntimeSettings.model_construct(
    provider="openai",
    model_name="mimo-v2.6-flash",
    response_format="json_object",
)


def make_ledger(root: Path) -> V8BudgetLedger:
    return V8BudgetLedger(
        root / "ledger.jsonl",
        currency="CNY",
        model="mimo-v2.6-flash",
        source_hashes={map_id: source_hash(map_id) for map_id in MAP_IDS},
    )


def make_runner(
    root: Path,
    responses: list[Any],
    ledger: V8BudgetLedger | None = None,
) -> tuple[V8Runner, V8BudgetLedger]:
    active = ledger or make_ledger(root)
    return (
        V8Runner(
            provider=FakeDecisionProvider(responses),
            settings=SETTINGS,
            ledger=active,
            output_dir=root,
            commit="test-commit",
        ),
        active,
    )


def oracle_actions(map_id: str = "MAP-01") -> list[dict[str, Any]]:
    groups = load_oracle_groups(map_id)
    return [row["action"] for row in next(iter(groups.values()))]


def test_runner_success_writes_all_artifacts(tmp_path: Path) -> None:
    actions = oracle_actions()
    responses = [
        ProviderResponse(
            candidate={"decision_reason": "offline", "action": action},
            input_tokens=800,
            output_tokens=80,
        )
        for action in actions
    ]
    runner, ledger = make_runner(tmp_path, responses)
    manifest = runner.run(V8EpisodeSpec("MAP-01", 0, len(actions)))

    assert manifest["status"] == "success"
    assert manifest["success"] is True
    assert manifest["decision_count"] == len(actions)
    assert manifest["provider_error"] is None
    assert manifest["unknown_spend"] is False
    assert ledger.snapshot()["settled_requests"] == len(actions)

    trace_path = Path(manifest["agent_trace_path"])
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["event"] == "trace_header"
    assert len([row for row in rows if row["event"] == "decision"]) == len(actions)

    judge = json.loads(Path(manifest["judge_metrics_path"]).read_text(encoding="utf-8"))
    assert judge["status"] == "success"
    assert judge["success"] is True
    assert judge["metrics"]

    v8_metrics = json.loads(Path(manifest["v8_metrics_path"]).read_text(encoding="utf-8"))
    assert v8_metrics["status"] == "success"
    assert v8_metrics["status_counts"]["valid"] > 0


def test_runner_counts_invalid_schema(tmp_path: Path) -> None:
    runner, ledger = make_runner(
        tmp_path,
        [
            ProviderResponse(
                candidate={"action": {"tool": "not_a_tool"}},
                input_tokens=10,
                output_tokens=10,
            )
        ],
    )
    manifest = runner.run(V8EpisodeSpec("MAP-01", 0, 1))
    assert manifest["status"] == "decision_budget_reached"
    assert manifest["invalid_action_count"] == 1
    assert ledger.snapshot()["settled_requests"] == 1


def test_runner_unknown_spend_closes_everything(tmp_path: Path) -> None:
    runner, ledger = make_runner(
        tmp_path,
        [
            DecisionProviderError(
                "transport outcome unknown",
                error_category="APIConnectionError",
                retryable=False,
                unknown_spend=True,
            )
        ],
    )
    manifest = runner.run(V8EpisodeSpec("MAP-01", 0, 5))
    assert manifest["status"] == "unknown_provider_spend"
    assert manifest["unknown_spend"] is True
    assert ledger.closed
    assert ledger.snapshot()["failed_requests"] == 1


def test_three_consecutive_provider_errors_close_the_ledger(tmp_path: Path) -> None:
    root = tmp_path
    ledger = make_ledger(root)
    for index in range(3):
        runner, _ = make_runner(
            root,
            [
                DecisionProviderError(
                    "temporary gateway failure",
                    error_category="APITimeoutError",
                    retryable=True,
                    unknown_spend=False,
                )
            ],
            ledger,
        )
        manifest = runner.run(V8EpisodeSpec("MAP-02", 0, 5))
        if index < 2:
            assert manifest["status"] == "provider_error"
            assert not ledger.closed
        else:
            assert manifest["status"] == "provider_error_limit"
            assert ledger.closed


def test_runner_rejects_unregistered_spec(tmp_path: Path) -> None:
    runner, _ = make_runner(tmp_path, [])
    try:
        runner.run(V8EpisodeSpec("MAP-99", 0, 5))
    except ValueError as exc:
        assert "MAP-99" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unregistered map must be refused")
    try:
        runner.run(V8EpisodeSpec("MAP-01", 3, 5))
    except ValueError as exc:
        assert "replicate_id" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("replicate 3 must be refused")
