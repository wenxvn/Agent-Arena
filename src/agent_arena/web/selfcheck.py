"""V11 一键离线自检：catalog、服务层、离线运行、导出、预算、脱敏与路径。

不发送任何 Provider 请求；不依赖本机历史 runs。全量 pytest/ruff/mypy 仍是独立的
质量门禁，本模块只覆盖 P0 的核心可运行能力。
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
import tempfile
import time
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from agent_arena.web.budget import (
    MIMO_PRICE,
    BudgetExceeded,
    BudgetLimits,
    RunBudget,
    UnknownUsageError,
)
from agent_arena.web.catalog import cards, map_detail
from agent_arena.web.export import export_actions_csv, replay_document
from agent_arena.web.providers import provider_statuses
from agent_arena.web.safety import is_valid_run_id, safe_child, safe_run_dir, sanitize_text
from agent_arena.web.schemas import (
    OFFLINE_MODEL,
    OFFLINE_PROVIDER,
    TERMINAL_STATES,
    RunConfig,
    RunMode,
)
from agent_arena.web.service import RunService

ALLOWED_METRIC_STATES = {"VALID", "CENSORED", "NOT_APPLICABLE", "MISSING", "INVALID"}
FORBIDDEN_KEYS = (
    "sealed_truth",
    "judge_state",
    "oracle_trace",
    "OPENAI_API_KEY",
    "authorization",
    "system_prompt",
    "sk-",
)


def _head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - 自检不因缺 git 失败
        return "unknown"


def _check(name: str, function: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        detail = function()
    except Exception as exc:  # noqa: BLE001 - 自检需要报告失败而不是崩溃
        return {
            "name": name,
            "ok": False,
            "seconds": round(time.perf_counter() - started, 3),
            "detail": sanitize_text(f"{type(exc).__name__}: {exc}", limit=400),
        }
    return {
        "name": name,
        "ok": True,
        "seconds": round(time.perf_counter() - started, 3),
        "detail": detail,
    }


def check_catalog() -> dict[str, Any]:
    items = cards()
    assert len(items) == 30, "地图数不是 30"
    assert len({item.map_id for item in items}) == 30, "地图 ID 不唯一"
    assert [item.map_id for item in items] == [f"MAP-{index:02d}" for index in range(1, 31)]
    valid_difficulties = {"简单", "中等", "困难", "待校准"}
    worlds = {item.world for item in items}
    assert len(worlds) == 10, "世界数不是 10"
    for item in items:
        assert item.display_difficulty in valid_difficulties, item.map_id
        assert item.goal.strip(), f"{item.map_id} 缺公开目标"
        assert item.rule_count > 0, f"{item.map_id} 缺公开规则"
        assert item.tool_count > 0, f"{item.map_id} 缺动作契约"
        detail = map_detail(item.map_id, item.seeds[0])
        serialized = json.dumps(detail, ensure_ascii=False)
        for key in FORBIDDEN_KEYS:
            assert key not in serialized, f"{item.map_id} 详情泄露 {key}"
        assert detail["contract"], f"{item.map_id} 契约为空"
        assert detail["public_fields"], f"{item.map_id} 缺少公开观察字段"
    return {"maps": len(items), "worlds": len(worlds), "forbidden_hits": 0}


def check_offline_matrix() -> dict[str, Any]:
    outcomes: dict[str, str] = {}
    total_steps = 0
    with tempfile.TemporaryDirectory(prefix="agent-arena-v11-") as temporary:
        service = RunService(Path(temporary) / "runs" / "web", recover=False)
        try:
            for item in cards():
                config = _offline_config(item.map_id, item.seeds[0], item.decision_budget)
                run_id = service.create_run(
                    config, idempotency_key=f"selfcheck-{item.map_id}"
                )
                duplicate = service.create_run(
                    config, idempotency_key=f"selfcheck-{item.map_id}"
                )
                assert duplicate == run_id, f"{item.map_id} 幂等失效"
                status = service.wait(run_id, timeout=120)
                assert status.terminal, f"{item.map_id} 未在时限内结束"
                replay = service.load_replay(run_id)
                steps = replay["steps"]
                assert steps, f"{item.map_id} 没有动作记录"
                result = replay["result"] or {}
                assert result.get("state") in {state.value for state in TERMINAL_STATES}
                for key in ("scenario_hash", "rule_hash", "metric_hash", "prompt_hash"):
                    assert result.get(key), f"{item.map_id} 缺少 {key}"
                metrics = result.get("metrics") or {}
                for metric in metrics.values():
                    if isinstance(metric, dict):
                        assert metric.get("state") in ALLOWED_METRIC_STATES
                document = replay_document(replay["manifest"], result, steps)
                blob = json.dumps(document, ensure_ascii=False)
                assert "sealed_truth" not in blob, f"{item.map_id} 导出泄露 sealed_truth"
                assert "judge_state" not in blob, f"{item.map_id} 导出泄露 judge_state"
                exported = export_actions_csv(steps).decode("utf-8-sig")
                rows = list(csv.DictReader(io.StringIO(exported)))
                assert len(rows) == len(steps), f"{item.map_id} CSV 行数不一致"
                outcomes[item.map_id] = str(result.get("outcome"))
                total_steps += len(steps)
        finally:
            service.shutdown()
    succeeded = sum(1 for value in outcomes.values() if value == "success")
    return {
        "maps": len(outcomes),
        "successes": succeeded,
        "total_steps": total_steps,
        "outcomes": outcomes,
    }


def _offline_config(map_id: str, seed: int, budget: int) -> RunConfig:
    return RunConfig(
        map_id=map_id,
        environment_seed=seed,
        mode=RunMode.OFFLINE,
        provider_id=OFFLINE_PROVIDER,
        model=OFFLINE_MODEL,
        agent="public_heuristic_policy",
        max_decisions=budget,
        max_requests=1,
        max_input_tokens=200_000,
        max_output_tokens=8_000,
        max_cost_cny=Decimal("0.01"),
    )


def check_budget() -> dict[str, Any]:
    limits = BudgetLimits(
        max_requests=2,
        max_input_tokens=100_000,
        max_output_tokens=10_000,
        max_cost_cny=Decimal("0.05"),
        price=MIMO_PRICE,
    )
    budget = RunBudget(limits)
    budget.reserve(estimated_input_tokens=1_000, output_limit=100)
    budget.settle(input_tokens=900, output_tokens=80)
    budget.reserve(estimated_input_tokens=1_000, output_limit=100)
    budget.settle(input_tokens=900, output_tokens=80)
    try:
        budget.reserve(estimated_input_tokens=1_000, output_limit=100)
    except BudgetExceeded as exc:
        assert exc.reason == "request_limit_exceeded"
    else:
        raise AssertionError("请求上限未生效")

    unknown = RunBudget(limits)
    unknown.reserve(estimated_input_tokens=1_000, output_limit=100)
    try:
        unknown.settle(input_tokens=None, output_tokens=None)
    except UnknownUsageError:
        pass
    else:
        raise AssertionError("未知 usage 未 fail-closed")
    assert unknown.unknown_spend

    strict = BudgetLimits(
        max_requests=10,
        max_input_tokens=100_000,
        max_output_tokens=10_000,
        max_cost_cny=Decimal("0.03"),
        price=MIMO_PRICE,
    )
    cost = RunBudget(strict)
    cost.reserve(estimated_input_tokens=16_384, output_limit=1_024)
    try:
        cost.settle(input_tokens=16_384, output_tokens=1_024)
    except BudgetExceeded:
        pass
    # 单次 16k+1k 的 MiMo 估算约 ¥0.018，第二次即超过 ¥0.03。
    cost2 = RunBudget(strict)
    cost2.reserve(estimated_input_tokens=16_384, output_limit=1_024)
    cost2.settle(input_tokens=16_384, output_tokens=1_024)
    try:
        cost2.reserve(estimated_input_tokens=16_384, output_limit=1_024)
    except BudgetExceeded as exc:
        assert exc.reason == "cost_limit_exceeded"
    else:
        raise AssertionError("费用上限未生效")
    return {"request_cap": True, "unknown_usage": True, "cost_cap": True}


def check_redaction() -> dict[str, Any]:
    secret = "sk-selfcheck-0123456789abcdef"
    text = sanitize_text(f"Authorization: Bearer abcdefgh12345678 key={secret}")
    assert secret not in text and "abcdefgh12345678" not in text
    serialized = json.dumps(
        [status.to_dict() for status in provider_statuses()], ensure_ascii=False
    )
    assert "sk-" not in serialized, "Provider 状态回显了疑似密钥"
    return {"secret_echo": False, "provider_status": "safe"}


def check_paths() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agent-arena-paths-") as temporary:
        base = Path(temporary)
        (base / "ok").mkdir()
        assert safe_child(base, "ok") == (base / "ok").resolve()
        for bad in ("..", "a/b", "a\\b", ""):
            try:
                safe_child(base, bad)
            except ValueError:
                continue
            raise AssertionError(f"路径未被拒绝：{bad}")
        assert is_valid_run_id("web-20261020T000000Z-abcdef12")
        assert not is_valid_run_id("../etc/passwd")
        assert not is_valid_run_id("web-2026-abcdef12")
        try:
            safe_run_dir(base, "../escape")
        except ValueError:
            pass
        else:
            raise AssertionError("run 目录越界未被拒绝")
    return {"traversal": False, "run_id": "strict"}


def check_export_consistency() -> dict[str, Any]:
    """同一局的结果、JSON 导出与 CSV 字段一致，且 CENSORED 不被写成 0。"""

    with tempfile.TemporaryDirectory(prefix="agent-arena-export-") as temporary:
        service = RunService(Path(temporary) / "runs" / "web", recover=False)
        try:
            config = _offline_config("MAP-19", 0, 4)
            run_id = service.create_run(config)
            service.wait(run_id, timeout=120)
            replay = service.load_replay(run_id)
            result = replay["result"] or {}
            document = replay_document(replay["manifest"], result, replay["steps"])
            assert document["result"]["state"] == result["state"]
            assert document["run"]["run_id"] == run_id
            exported = export_actions_csv(replay["steps"]).decode("utf-8-sig")
            rows = list(csv.DictReader(io.StringIO(exported)))
            assert len(rows) == len(replay["steps"])
            assert set(rows[0]) == {
                "step",
                "tool",
                "action_json",
                "result",
                "status",
                "terminal",
                "input_tokens",
                "output_tokens",
                "latency_ms",
                "decision_reason",
                "observation_after_json",
            }
        finally:
            service.shutdown()
    return {"json": "ok", "csv": "ok", "rows": len(replay["steps"])}


def check_service_recovery() -> dict[str, Any]:
    """伪造一个上一个进程遗留的 RUNNING manifest，恢复后必须是 INTERRUPTED。"""

    with tempfile.TemporaryDirectory(prefix="agent-arena-recover-") as temporary:
        base = Path(temporary) / "runs" / "web"
        run_id = "web-20260101T000000Z-deadbeef"
        run_dir = base / run_id
        run_dir.mkdir(parents=True)
        manifest = {
            "schema_version": "v11-web-1",
            "run_id": run_id,
            "attempt_id": "att-deadbeef",
            "owner_id": "dead-owner",
            "owner_pid": 999_999,
            "state": "RUNNING",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "config": _offline_config("MAP-01", 0, 30).public_dict(),
            "map_id": "MAP-01",
            "world": "spaceship",
            "mode": "offline",
            "provider_id": OFFLINE_PROVIDER,
            "model": OFFLINE_MODEL,
            "environment_seed": 0,
            "decision_budget": 30,
            "decisions": 3,
        }
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        (run_dir / "events.jsonl").write_text(
            json.dumps({"event": "decision", "decision_index": 1}) + "\n", encoding="utf-8"
        )
        service = RunService(base, recover=True)
        try:
            status = service.get_run(run_id)
            assert status.state.value == "INTERRUPTED", status.state.value
            replay = service.load_replay(run_id)
            assert replay["result"] and replay["result"]["partial"] is True
            assert len(replay["steps"]) == 1
        finally:
            service.shutdown()
    return {"recovered": True}


def run_checks(*, report_path: Path | None = None) -> dict[str, Any]:
    checks = [
        _check("catalog", check_catalog),
        _check("offline_matrix", check_offline_matrix),
        _check("budget", check_budget),
        _check("redaction", check_redaction),
        _check("paths", check_paths),
        _check("export_consistency", check_export_consistency),
        _check("service_recovery", check_service_recovery),
    ]
    failed = [item for item in checks if not item["ok"]]
    report = {
        "schema": "v11-selfcheck-1",
        "head": _head(),
        "ok": not failed,
        "failed": len(failed),
        "checks": checks,
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    return report


__all__ = [
    "ALLOWED_METRIC_STATES",
    "check_budget",
    "check_catalog",
    "check_export_consistency",
    "check_offline_matrix",
    "check_paths",
    "check_redaction",
    "check_service_recovery",
    "run_checks",
]
