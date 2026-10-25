"""V12 一键离线验收：契约、30 图、父子实验、预算、可视化与导出复算。

不发送任何 Provider 请求；不读写本机历史 runs/账本；全部在临时目录完成。

用法：
    uv run python scripts/verify_v12.py
    uv run python scripts/verify_v12.py --report runs/v12/selfcheck.json
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

from agent_arena.lab.contracts import (
    AgentArm,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
)
from agent_arena.lab.experiment import ExperimentService, preflight
from agent_arena.lab.registry import agent_catalog, get_agent, registered_agent_ids
from agent_arena.lab.runner import run_lab_episode
from agent_arena.lab.simulated import SimulatedDecisionProvider
from agent_arena.lab.visualization import FOCUS_MAPS, KIND_BY_MAP, build_view_model
from agent_arena.v10.runtime.catalog import create_environment, metric_hash, rule_hash
from agent_arena.web.catalog import cards
from agent_arena.web.safety import sanitize_text
from agent_arena.web.schemas import (
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
    RunConfig,
    RunMode,
)
from agent_arena.web.service import RunService

FORBIDDEN_KEYS = (
    "sealed_truth",
    "truth_seal",
    "judge_state",
    "oracle_actions",
    "OPENAI_API_KEY",
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
    except Exception as exc:  # noqa: BLE001 - 自检报告失败而不是崩溃
        return {
            "name": name,
            "ok": False,
            "seconds": round(time.perf_counter() - started, 3),
            "detail": sanitize_text(f"{type(exc).__name__}: {exc}", limit=500),
        }
    return {
        "name": name,
        "ok": True,
        "seconds": round(time.perf_counter() - started, 3),
        "detail": detail,
    }


def _config(map_id: str, agent: str, *, decisions: int, seed: int = 0) -> RunConfig:
    return RunConfig(
        map_id=map_id,
        environment_seed=seed,
        mode=RunMode.SIMULATED,
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        agent=agent,
        max_decisions=decisions,
        max_requests=200,
        max_input_tokens=2_000_000,
        max_output_tokens=20_000,
        max_cost_cny=Decimal("1.00"),
    )


def check_catalog() -> dict[str, Any]:
    items = cards()
    assert len(items) == 30, "地图数不是 30"
    ids = [item.map_id for item in items]
    assert ids == [f"MAP-{index:02d}" for index in range(1, 31)]
    for map_id in FOCUS_MAPS:
        assert map_id in ids, map_id
    hashes = {(rule_hash(item.map_id), metric_hash(item.map_id)) for item in items}
    assert len(hashes) == 30, "规则/指标 hash 不唯一"
    return {"maps": len(items), "focus": len(FOCUS_MAPS), "unique_hashes": len(hashes)}


def check_v10_freeze() -> dict[str, Any]:
    from agent_arena.v10.freeze import verify

    report = verify(include_runs=False)
    drift = {
        root: item
        for root, item in report.items()
        if isinstance(item, dict) and item.get("state") != "unchanged"
    }
    assert not drift, f"冻结漂移：{sorted(drift)}"
    return {"roots": len(report), "drift": sorted(drift)}


def check_contracts() -> dict[str, Any]:
    spec = ExperimentSpec(
        name="selfcheck",
        maps=["MAP-22"],
        agent_arms=[AgentArm(agent_id="basic.v1"), AgentArm(agent_id="memory.v1")],
        environment_seeds=[0],
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        mode=ExperimentMode.SIMULATED,
    )
    payload = spec.public_dict()
    assert payload["fingerprint"]
    assert len(spec.matrix()) == 2
    assert spec.matrix()[0].matrix_index == 0
    # 非法矩阵：未注册策略。
    try:
        ExperimentSpec(
            name="bad",
            maps=["MAP-22"],
            agent_arms=[AgentArm(agent_id="nope.v1")],
            provider_id=SIMULATED_PROVIDER,
            model=SIMULATED_MODEL,
            mode=ExperimentMode.SIMULATED,
        )
    except Exception:  # noqa: BLE001 - 期望被拒绝
        pass
    else:
        raise AssertionError("非法实验臂未被拒绝")
    # 模拟模式不能冒充真实 Provider。
    try:
        ExperimentSpec(
            name="bad",
            maps=["MAP-22"],
            agent_arms=[AgentArm(agent_id="basic.v1")],
            provider_id="openai_compatible",
            model="mimo-v2.6-flash",
            mode=ExperimentMode.SIMULATED,
        )
    except Exception:  # noqa: BLE001
        pass
    else:
        raise AssertionError("模拟模式未拒绝真实 Provider")
    return {"matrix": len(spec.matrix()), "fingerprint": payload["fingerprint"][:12]}


def check_registry() -> dict[str, Any]:
    ids = registered_agent_ids()
    for agent_id in ("basic.v1", "memory.v1", "planning.v1", "reflection.v1"):
        assert agent_id in ids, agent_id
    rows = agent_catalog()
    assert len(rows) >= 4
    hashes = set()
    for agent_id in ("basic.v1", "memory.v1", "planning.v1", "reflection.v1"):
        registration = get_agent(agent_id)
        if "enabled" not in registration.allowed_config_keys:
            continue
        off = registration.normalize_config({"enabled": False})
        on = registration.normalize_config({"enabled": True})
        assert off != on, f"{agent_id} 消融开关未改变配置"
        hashes.add(json.dumps(off, sort_keys=True))
        hashes.add(json.dumps(on, sort_keys=True))
    assert len(hashes) >= 6, "消融配置未形成可区分指纹"
    return {"agents": len(ids), "catalog_rows": len(rows), "config_variants": len(hashes)}


def check_simulated_six_maps() -> dict[str, Any]:
    outcomes: dict[str, str] = {}
    events: dict[str, int] = {}
    for map_id in FOCUS_MAPS:
        environment = create_environment(map_id, environment_seed=0)
        for agent_id in ("basic.v1", "memory.v1", "planning.v1"):
            provider = SimulatedDecisionProvider(map_id=map_id, shapes=environment.SHAPES)
            outcome = run_lab_episode(
                _config(map_id, agent_id, decisions=8), provider=provider
            )
            assert outcome.state.value in {"SUCCEEDED", "FAILED", "BUDGET_REACHED"}
            assert outcome.result["decision_count"] >= 1
            outcomes[f"{map_id}:{agent_id}"] = outcome.state.value
            events[f"{map_id}:{agent_id}"] = len(outcome.result["agent_events"])
            blob = json.dumps(outcome.result, ensure_ascii=False)
            for key in FORBIDDEN_KEYS:
                assert key not in blob, f"{map_id}/{agent_id} 泄露 {key}"
    assert events["MAP-22:memory.v1"] >= 1, "记忆策略没有产生记忆事件"
    assert events["MAP-22:planning.v1"] >= 1, "规划策略没有产生计划事件"
    return {"runs": len(outcomes), "agent_events": sum(events.values())}


def check_simulated_all_maps() -> dict[str, Any]:
    states: dict[str, str] = {}
    for item in cards():
        provider = SimulatedDecisionProvider(
            map_id=item.map_id, shapes=create_environment(item.map_id).SHAPES
        )
        outcome = run_lab_episode(
            _config(item.map_id, "basic.v1", decisions=6), provider=provider
        )
        assert outcome.result["decision_count"] >= 1, item.map_id
        states[item.map_id] = outcome.state.value
    return {"maps": len(states)}


def _experiment_service(tmp: Path) -> tuple[RunService, ExperimentService]:
    runs = RunService(tmp / "web", recover=False)
    lab = ExperimentService(tmp / "lab", run_service=runs, recover=False)
    return runs, lab


def _matrix_spec(**overrides: Any) -> ExperimentSpec:
    payload: dict[str, Any] = {
        "name": "selfcheck-matrix",
        "maps": ["MAP-22", "MAP-18"],
        "agent_arms": [
            AgentArm(agent_id="basic.v1"),
            AgentArm(agent_id="memory.v1"),
            AgentArm(agent_id="planning.v1"),
        ],
        "environment_seeds": [0],
        "provider_id": SIMULATED_PROVIDER,
        "model": SIMULATED_MODEL,
        "mode": ExperimentMode.SIMULATED,
        "budget": ExperimentBudget(
            per_run_request_cap=40,
            per_run_decision_cap=4,
            experiment_request_cap=2_000,
            experiment_cost_cap_cny=Decimal("5"),
        ),
    }
    payload.update(overrides)
    return ExperimentSpec.model_validate(payload)


def check_parent_child() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agent-arena-v12-parent-") as temporary:
        runs, lab = _experiment_service(Path(temporary))
        try:
            spec = _matrix_spec()
            # 预检零请求：此时还没有任何子局。
            result = preflight(spec)
            assert result.ok and result.cells == 6
            assert runs.list_runs() == []
            experiment_id = lab.create_experiment(spec, idempotency_key="selfcheck")
            assert lab.create_experiment(spec, idempotency_key="selfcheck") == experiment_id
            lab.submit(experiment_id)
            manifest = lab.wait(experiment_id, timeout=600)
            assert manifest.state.value == "COMPLETED", manifest.message
            assert manifest.counts["done"] == 6
            for child in manifest.children:
                status = runs.get_run(child["run_id"])
                assert status.terminal
                assert status.state.value == child["state"]
                assert status.config["experiment_id"] == experiment_id
            before = len(runs.list_runs())
            lab.submit(experiment_id)
            time.sleep(0.2)
            assert len(runs.list_runs()) == before, "重复提交产生了新局"
            return {
                "cells": 6,
                "done": manifest.counts["done"],
                "children": len(manifest.children),
            }
        finally:
            runs.shutdown()


def check_budget() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agent-arena-v12-budget-") as temporary:
        runs, lab = _experiment_service(Path(temporary))
        try:
            spec = _matrix_spec(
                budget=ExperimentBudget(
                    per_run_request_cap=4,
                    per_run_decision_cap=4,
                    experiment_request_cap=4,
                    experiment_cost_cap_cny=Decimal("5"),
                )
            )
            experiment_id = lab.create_experiment(spec)
            lab.submit(experiment_id)
            manifest = lab.wait(experiment_id, timeout=600)
            assert manifest.state.value == "PARTIAL", manifest.state.value
            assert manifest.counts["done"] < manifest.counts["total"]
            assert "experiment_request_cap" in str(manifest.message)
            return {"state": manifest.state.value, "done": manifest.counts["done"]}
        finally:
            runs.shutdown()


def check_visualization() -> dict[str, Any]:
    kinds: dict[str, str] = {}
    for map_id in FOCUS_MAPS:
        provider = SimulatedDecisionProvider(
            map_id=map_id, shapes=create_environment(map_id).SHAPES
        )
        events: list[dict[str, Any]] = []
        outcome = run_lab_episode(
            _config(map_id, "basic.v1", decisions=8),
            provider=provider,
            on_event=events.append,
        )
        steps = [event for event in events if event.get("event") == "decision"]
        model = build_view_model(map_id, steps, outcome.result)
        assert model["available"] is True, map_id
        assert model["kind"] == KIND_BY_MAP[map_id], map_id
        blob = json.dumps(model, ensure_ascii=False)
        for key in ("sealed_truth", "judge_state", "truth_seal"):
            assert key not in blob, f"{map_id} 视图泄露 {key}"
        kinds[map_id] = model["kind"]
    return {"maps": len(kinds), "kinds": kinds}


def check_export_recompute() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agent-arena-v12-export-") as temporary:
        runs, lab = _experiment_service(Path(temporary))
        try:
            experiment_id = lab.create_experiment(_matrix_spec())
            lab.submit(experiment_id)
            lab.wait(experiment_id, timeout=600)
            files = lab.export(experiment_id)
            rows = list(
                csv.DictReader(
                    io.StringIO(Path(files["runs.csv"]).read_text(encoding="utf-8-sig"))
                )
            )
            summary = json.loads(Path(files["summary.json"]).read_text(encoding="utf-8"))
            assert len(rows) == summary["executed"], "runs.csv 与 summary 不一致"
            valid = sum(
                1
                for row in rows
                if row["category"]
                in {"completed_success", "mechanism_failure", "budget_censored"}
            )
            assert valid == summary["valid_denominator"], "有效分母不可复算"
            metrics_rows = list(
                csv.DictReader(
                    io.StringIO(Path(files["metrics.csv"]).read_text(encoding="utf-8-sig"))
                )
            )
            expected = sum(len(record["metrics"]) for record in lab.records(experiment_id))
            assert len(metrics_rows) == expected, "metrics.csv 行数不一致"
            for name in ("summary.json", "comparison.json", "experiment.json", "report.md"):
                text = Path(files[name]).read_text(encoding="utf-8").lower()
                for key in FORBIDDEN_KEYS:
                    assert key.lower() not in text, f"{name} 泄露 {key}"
            return {
                "runs": len(rows),
                "metrics": len(metrics_rows),
                "valid_denominator": valid,
            }
        finally:
            runs.shutdown()


def check_redaction() -> dict[str, Any]:
    secret = "sk-selfcheck-0123456789abcdef"
    text = sanitize_text(f"Authorization: Bearer abcdefgh12345678 key={secret}")
    assert secret not in text and "abcdefgh12345678" not in text
    with tempfile.TemporaryDirectory(prefix="agent-arena-v12-redact-") as temporary:
        runs, lab = _experiment_service(Path(temporary))
        try:
            experiment_id = lab.create_experiment(_matrix_spec())
            lab.submit(experiment_id)
            lab.wait(experiment_id, timeout=600)
            files = lab.export(experiment_id)
            for name, path in files.items():
                blob = Path(path).read_text(encoding="utf-8", errors="ignore")
                for key in FORBIDDEN_KEYS:
                    assert key.lower() not in blob.lower(), f"{name} 泄露 {key}"
            return {"files": len(files), "secret_echo": False}
        finally:
            runs.shutdown()


def check_a11y() -> dict[str, Any]:
    """可访问性：主题对比度 + 焦点样式（离线部分；浏览器部分见 scripts/a11y_v12.py）。"""

    from agent_arena.lab.a11y import (
        audit_focus_css,
        audit_theme_tokens,
    )
    from agent_arena.ui.theme import stylesheet

    theme_report = audit_theme_tokens()
    assert theme_report["ok"], theme_report["text_failures"]
    assert theme_report["ui_ok"], theme_report["ui_failures"]
    focus = audit_focus_css(stylesheet())
    assert focus["ok"], focus["issues"]
    return {
        "tokens_checked": theme_report["checked"],
        "text_failures": 0,
        "ui_failures": 0,
        "focus_visible": focus["has_focus_visible"],
    }


def check_theme_tokens_in_css() -> dict[str, Any]:
    """审计用的 token 名必须真的出现在样式表里（避免审计与实现脱节）。"""

    from agent_arena.ui.theme import stylesheet

    css = stylesheet()
    missing = [
        name
        for name in ("accent", "accent-2", "success", "warning", "danger", "info", "neutral")
        if f"--aa-{name}-text" not in css
    ]
    assert not missing, f"样式表缺少文字 token：{missing}"
    assert "--aa-warning-text" in css
    return {"tokens": 7, "missing": 0}


def run_checks(*, report_path: Path | None = None) -> dict[str, Any]:
    checks = [
        _check("catalog", check_catalog),
        _check("v10_freeze", check_v10_freeze),
        _check("contracts", check_contracts),
        _check("registry", check_registry),
        _check("simulated_six_maps", check_simulated_six_maps),
        _check("simulated_all_maps", check_simulated_all_maps),
        _check("parent_child", check_parent_child),
        _check("budget", check_budget),
        _check("visualization", check_visualization),
        _check("export_recompute", check_export_recompute),
        _check("redaction", check_redaction),
        _check("a11y", check_a11y),
        _check("theme_tokens_in_css", check_theme_tokens_in_css),
    ]
    failed = [item for item in checks if not item["ok"]]
    report = {
        "schema": "v12-selfcheck-1",
        "head": _head(),
        "ok": not failed,
        "failed": len(failed),
        "checks": checks,
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


__all__ = [
    "FORBIDDEN_KEYS",
    "check_budget",
    "check_catalog",
    "check_contracts",
    "check_export_recompute",
    "check_parent_child",
    "check_redaction",
    "check_registry",
    "check_simulated_all_maps",
    "check_simulated_six_maps",
    "check_v10_freeze",
    "check_visualization",
    "run_checks",
]
