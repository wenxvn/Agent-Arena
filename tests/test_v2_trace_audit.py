from __future__ import annotations

import json
from pathlib import Path
from runpy import run_path

_audit = run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "audit_v2_traces.py"))
audit_trace = _audit["audit_trace"]
load_attempts = _audit["load_attempts"]
summarize = _audit["summarize"]
configuration_signature = _audit["_configuration_signature"]


def _trace(episode_id: str, created_at: str, outcome: str) -> dict[str, object]:
    return {
        "episode_id": episode_id,
        "created_at": created_at,
        "world_version": "synthetic-v1",
        "seed": 0,
        "agent": "memory",
        "provider": "fake",
        "prompt_version": "memory_v2",
        "outcome": outcome,
        "executed_action_count": 2,
        "latency_ms": 100,
        "provenance": {
            "world_definition_id": "synthetic",
            "world_definition_hash": "abc123",
            "model_name": "fake-model",
            "base_prompt_hash": "prompt-hash",
            "step_limit": 10,
            "recent_history_window": 5,
        },
        "steps": [],
    }


def test_audit_trace_counts_public_step_patterns() -> None:
    trace = _trace("episode-1", "2026-10-13T00:00:00Z", "success")
    trace["steps"] = [
        {
            "observation": {"current_room": "dock"},
            "action": {"tool": "read_terminal", "target": "escape_pod"},
            "result": {"status": "rejected", "reason": "wrong_target"},
            "progress": {"progress": False, "state_progress": False, "epistemic_progress": False},
        },
        {
            "observation": {"current_room": "dock"},
            "action": {"tool": "read_terminal", "target": "control_terminal"},
            "result": {"status": "success", "reason": "code_read"},
            "progress": {"progress": True, "state_progress": False, "epistemic_progress": True},
        },
        {
            "observation": {"current_room": "dock"},
            "action": {"tool": "read_terminal", "target": "control_terminal"},
            "result": {"status": "success", "reason": "code_read"},
            "progress": {"progress": False, "state_progress": False, "epistemic_progress": False},
        },
        {
            "observation": {"current_room": "dock"},
            "action": {"tool": "move", "destination": "hall"},
            "result": {"status": "success", "reason": "moved"},
            "progress": {"progress": False, "state_progress": False, "epistemic_progress": False},
        },
        {
            "observation": {"current_room": "hall"},
            "action": {"tool": "move", "destination": "dock"},
            "result": {"status": "success", "reason": "moved"},
            "progress": {"progress": True, "state_progress": True, "epistemic_progress": False},
        },
        {
            "observation": {"current_room": "dock"},
            "action": {"tool": "move", "destination": "hall"},
            "result": {"status": "success", "reason": "moved"},
            "progress": {"progress": False, "state_progress": False, "epistemic_progress": False},
        },
        {
            "observation": {"current_room": "dock"},
            "action": {"tool": "read_terminal", "target": "escape_pod"},
            "result": {"status": "rejected", "reason": "wrong_target"},
            "progress": {"progress": False, "state_progress": False, "epistemic_progress": False},
        },
    ]

    row = audit_trace(trace)

    assert row["wrong_terminal_target_reads"] == 2
    assert row["repeated_failed_action_attempts"] == 1
    assert row["repeated_code_reads"] == 1
    assert row["post_code_navigation_actions"] == 3
    assert row["navigation_two_cycle_count"] == 1
    assert row["no_progress_actions"] == 5
    assert row["epistemic_progress_actions"] == 1
    assert row["rejected_actions"] == 2
    assert row["rejection_reason_counts"] == {"wrong_target": 2}
    assert row["rejection_reason_by_tool_counts"] == {"read_terminal:wrong_target": 2}


def test_audit_trace_exports_memory_version_and_statistics_without_memory_text() -> None:
    trace = _trace("episode-memory", "2026-10-13T00:00:00Z", "success")
    trace["provenance"]["memory_schema_version"] = "v3"
    trace["provenance"]["memory_renderer_version"] = "v3_spatial_event"
    trace["steps"] = [
        {
            "action": {"tool": "look"},
            "result": {"status": "success", "reason": "looked"},
            "memory_statistics": {
                "insertions": 9,
                "updates": 2,
                "invalidations": 0,
                "compactions": 1,
                "rendered_chars": 800,
                "estimated_tokens": 200,
            },
        }
    ]
    row = audit_trace(trace)

    assert row["memory_schema_version"] == "v3"
    assert row["memory_renderer_version"] == "v3_spatial_event"
    assert row["memory_statistics_present"] is True
    assert row["memory_insertions"] == 9
    assert row["memory_compactions"] == 1
    assert row["memory_rendered_chars"] == 800
    assert row["memory_estimated_tokens"] == 200

    v2_trace = _trace("episode-memory-v2", "2026-10-13T00:00:00Z", "success")
    v2_trace["provenance"]["memory_schema_version"] = "memory_v1"
    v2_trace["provenance"]["memory_renderer_version"] = "memory_v1"
    assert configuration_signature(row) != configuration_signature(audit_trace(v2_trace))


def test_load_attempts_deduplicates_episode_copies_and_orders_attempts(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    results_dir = tmp_path / "results"
    run_group = runs_dir / "experiment-a"
    result_copy = results_dir / "experiment-a" / "traces"
    run_group.mkdir(parents=True)
    result_copy.mkdir(parents=True)
    first = _trace("episode-first", "2026-10-13T00:00:00Z", "step_limit")
    second = _trace("episode-second", "2026-10-13T00:01:00Z", "success")
    third = _trace("episode-third", "2026-10-13T00:02:00Z", "success")
    third["seed"] = 1
    (run_group / "episode_first.json").write_text(json.dumps(first), encoding="utf-8")
    (result_copy / "episode_first.json").write_text(json.dumps(first), encoding="utf-8")
    (run_group / "episode_second.json").write_text(json.dumps(second), encoding="utf-8")
    (run_group / "episode_third.json").write_text(json.dumps(third), encoding="utf-8")

    rows, counters = load_attempts(runs_dir, results_dir)
    summary = summarize(rows, counters)

    assert len(rows) == 3
    assert counters["duplicate_files"] == 1
    assert [row["recorded_attempt_index"] for row in rows] == [1, 2, 1]
    assert len({row["configuration_signature"] for row in rows}) == 1
    assert len({row["effective_instance_signature"] for row in rows}) == 1
    assert summary["outcomes_all_attempts"] == {"step_limit": 1, "success": 2}
    assert summary["earliest_recorded_per_condition_and_seed"] == {
        "step_limit": 1,
        "success": 1,
    }
    condition = summary["condition_groups"][0]
    assert condition["attempts"] == 3
    assert condition["offline_success_at_k_all_recorded_attempts"]["30"] == {
        "successes": 2,
        "eligible": 2,
        "rate": 1.0,
        "provider_error_censored": 0,
        "step_limit_censored_before_budget": 1,
    }
    assert summary["earliest_recorded_is_not_verified_first_attempt"] is True
