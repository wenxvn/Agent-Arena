"""V13 一键离线验收（``scripts/verify_v13.py`` 的实现）。

**不发任何 Provider 请求、不写真实账本**：全部在临时目录或只读历史文件上完成。
每一项都返回 ``{name, ok, seconds, detail}``，失败不吞异常。
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
    ProtocolManifest,
    SamplingProvenance,
)
from agent_arena.lab.experiment import ExperimentService
from agent_arena.lab.paths import LAB_RUNS, WEB_RUNS
from agent_arena.lab.runner import run_lab_episode
from agent_arena.lab.simulated import SimulatedDecisionProvider
from agent_arena.lab.v13.ablation import (
    ABLATION_TEMPLATES,
    build_ablation_specs,
    build_evidence_pack,
    classify_pair,
    template_table,
)
from agent_arena.lab.v13.capability import capability_profile
from agent_arena.lab.v13.comparability import (
    comparability_profile,
    compare_profiles,
    cross_experiment_pairs,
    single_switch_check,
)
from agent_arena.lab.v13.history import load_v12_history
from agent_arena.lab.v13.ledger import (
    NO_BILL,
    audit_ledger,
    reconcile_bill,
    write_bill_template,
)
from agent_arena.lab.v13.perf import synthesize_history
from agent_arena.lab.v13.report import build_report_v13, report_payload
from agent_arena.lab.v13.sdkcheck import run_sdk_checks
from agent_arena.lab.v13.stability import replicate_variability, write_variability
from agent_arena.lab.v13.taxonomy import check_fixtures, taxonomy_report
from agent_arena.lab.v13.validity import map30_ladder, six_map_audit
from agent_arena.v10.runtime.catalog import create_environment, metric_hash, rule_hash
from agent_arena.web.catalog import cards
from agent_arena.web.index import RunIndex
from agent_arena.web.safety import sanitize_text
from agent_arena.web.schemas import (
    SIMULATED_MODEL,
    SIMULATED_PROVIDER,
    RunConfig,
    RunMode,
)
from agent_arena.web.service import RunService

FORBIDDEN = (
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
    except Exception as exc:  # noqa: BLE001 - 报告失败而不是崩溃
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


def _config(map_id: str, agent: str, *, decisions: int = 8, seed: int = 0) -> RunConfig:
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


# ---------------------------------------------------------------------- checks
def check_contract_v13() -> dict[str, Any]:
    spec = ExperimentSpec(
        name="v13-selfcheck",
        maps=["MAP-22"],
        agent_arms=[AgentArm(agent_id="basic.v1")],
        environment_seeds=[0],
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        mode=ExperimentMode.SIMULATED,
        replicates=3,
        sampling=SamplingProvenance(seed_requested=1),
        protocol=ProtocolManifest(
            protocol_id="selfcheck", question="q", primary_metric="m"
        ),
    )
    cells = spec.matrix()
    assert len(cells) == 3
    assert len({cell.condition_key for cell in cells}) == 3
    assert cells[0].condition_key == "MAP-22|seed=0|basic.v1"
    assert spec.sampling.deterministic_claim != "deterministic"
    assert spec.fingerprint() == spec.fingerprint()
    # V12 旧规格（无 V13 字段）仍可解析。
    legacy = ExperimentSpec(
        name="legacy",
        maps=["MAP-22"],
        agent_arms=[AgentArm(agent_id="basic.v1")],
        environment_seeds=[0],
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        mode=ExperimentMode.SIMULATED,
    )
    assert legacy.replicates == 1 and legacy.protocol is None
    return {"cells": len(cells), "contract": spec.contract_version}


def check_v10_freeze() -> dict[str, Any]:
    from agent_arena.v10.freeze import verify

    report = verify(include_runs=False)
    drift = {
        root: item
        for root, item in report.items()
        if isinstance(item, dict) and item.get("state") != "unchanged"
    }
    assert not drift, f"冻结漂移：{sorted(drift)}"
    return {"roots": len(report)}


def check_thirty_maps() -> dict[str, Any]:
    items = cards()
    assert len(items) == 30
    hashes = {(rule_hash(item.map_id), metric_hash(item.map_id)) for item in items}
    assert len(hashes) == 30
    return {"maps": len(items)}


def check_history_reproduction() -> dict[str, Any]:
    two = load_v12_history(names=["main-54-runs.csv", "replicate-16-18-runs.csv"])
    three = load_v12_history(
        names=[
            "main-54-runs.csv",
            "replicate-16-18-runs.csv",
            "replicate-16-18-b-runs.csv",
        ]
    )
    report_two = replicate_variability(two, min_obs=2)
    report_three = replicate_variability(three, min_obs=2)
    assert report_two["flip_rate"] == 0.2222, report_two["flip_rate"]
    assert report_three["flip_rate"] == 0.25, report_three["flip_rate"]
    assert report_three["excluded_not_comparable"] == 6
    return {
        "two_obs_flip_rate": report_two["flip_rate"],
        "three_obs_flip_rate": report_three["flip_rate"],
        "three_obs_excluded": report_three["excluded_not_comparable"],
    }


def check_ledger_reproduction() -> dict[str, Any]:
    ledger = WEB_RUNS / "_ledger" / "web_ledger.jsonl"
    if not ledger.is_file():
        return {"skipped": "本机没有 V12 账本（离线环境）"}
    audit = audit_ledger(ledger_path=ledger, lab_dir=LAB_RUNS, web_dir=WEB_RUNS)
    assert audit.started == audit.settled, (audit.started, audit.settled)
    assert audit.duplicate_settlements == []
    assert audit.orphan_runs == []
    assert audit.cost_settled_cny == "5.43680012", audit.cost_settled_cny
    assert audit.requests == 5641, audit.requests
    return {
        "runs": audit.settled,
        "requests": audit.requests,
        "cost_cny": audit.cost_settled_cny,
        "unknown_spend": len(audit.unknown_spend_runs),
    }


def check_map30_ladder() -> dict[str, Any]:
    records = load_v12_history()
    ladder = map30_ladder(records)
    tiers = {tier["tier"]: tier for tier in ladder["tiers"]}
    assert "req=90|tok=200000" in tiers
    assert "req=180|tok=200000" in tiers
    assert "req=180|tok=600000" in tiers
    ext1 = tiers["req=180|tok=200000"]
    ext2 = tiers["req=180|tok=600000"]
    assert ext1["accusation_rejected"] == 4, ext1
    assert ext2["accusation_rejected"] == 2, ext2
    assert ext1["censored"] == 5, ext1
    assert ext2["censored"] == 7, ext2
    return {
        "tiers": len(tiers),
        "ext1_court": ext1["accusation_rejected"],
        "ext2_censored": ext2["censored"],
    }


def check_six_map_validity() -> dict[str, Any]:
    records = load_v12_history()
    audit = six_map_audit(records)
    labels = {row["map_id"]: row["composite"] for row in audit["maps"]}
    assert "CEILING" in labels["MAP-08"]
    assert "CEILING" in labels["MAP-26"]
    assert "CENSORED" in labels["MAP-30"]
    assert "SUITABLE" in labels["MAP-16"]
    return {"labels": labels}


def check_policies() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for map_id in ("MAP-22", "MAP-16"):
        environment = create_environment(map_id, environment_seed=0)
        for agent_id in ("memory.v2", "planning.v2", "reflection.v2"):
            provider = SimulatedDecisionProvider(map_id=map_id, shapes=environment.SHAPES)
            outcome = run_lab_episode(_config(map_id, agent_id, decisions=10), provider=provider)
            snapshot = outcome.result["provenance"]["policy"]
            results[f"{map_id}:{agent_id}"] = {
                key: snapshot.get(key)
                for key in (
                    "route_mode",
                    "route_length",
                    "planner_requests",
                    "triggered",
                    "exposure",
                )
                if key in snapshot
            }
            blob = json.dumps(outcome.result, ensure_ascii=False)
            for key in FORBIDDEN:
                assert key not in blob, f"{map_id}/{agent_id} 泄露 {key}"
    assert results["MAP-22:reflection.v2"]["triggered"] >= 1, results
    return results


def check_ablation_templates() -> dict[str, Any]:
    rows = template_table()
    assert rows and all(row["single_switch_ok"] for row in rows), rows
    for template in ABLATION_TEMPLATES.values():
        control, treatment = build_ablation_specs(
            template, maps=["MAP-22"], seeds=[0], replicates=3
        )
        assert len(control.matrix()) == 3
        assert len(treatment.matrix()) == 3
        assert control.fingerprint() != treatment.fingerprint()
    version = classify_pair(
        "memory.v1", {"enabled": True}, "memory.v2", {"enabled": True}
    )
    assert version == "VERSION_COMPARISON"
    multi = classify_pair(
        "memory.v2",
        {"enabled": True, "route_log": False},
        "memory.v2",
        {"enabled": False, "route_log": True},
    )
    assert multi == "MULTI_SWITCH_COMBINATION"
    return {"templates": len(rows), "version_compare": version, "multi": multi}


def check_comparability() -> dict[str, Any]:
    base = {
        "map_id": "MAP-22",
        "environment_seed": 0,
        "mode": "live",
        "provider_id": "openai_compatible",
        "model": "mimo",
        "rule_hash": "r",
        "metric_hash": "m",
        "metric_schema_hash": "s",
        "base_prompt_hash": "p",
        "request_cap": 90,
        "input_token_cap": 200_000,
    }
    left = comparability_profile({**base, "agent_config_hash": "a"})
    right = comparability_profile({**base, "agent_config_hash": "b"})
    assert compare_profiles(left, right)["verdict"] == "COMPARABLE"
    hard = comparability_profile({**base, "agent_config_hash": "b", "rule_hash": "r2"})
    assert compare_profiles(left, hard)["verdict"] == "INCOMPARABLE"
    check = single_switch_check(
        {"agent_id": "memory.v2", "config": {"enabled": True}},
        {"agent_id": "memory.v2", "config": {"enabled": False}},
    )
    assert check.ok and check.manipulated_variable == "enabled"
    pairs = cross_experiment_pairs(
        [
            {
                **base,
                "run_id": "L",
                "agent_id": "memory.v2",
                "agent_config_hash": "a",
                "success": True,
            }
        ],
        [
            {
                **base,
                "run_id": "R",
                "agent_id": "memory.v2",
                "agent_config_hash": "b",
                "success": False,
            }
        ],
        left_agent="memory.v2",
        right_agent="memory.v2",
        left_arm={"agent_id": "memory.v2", "config": {"enabled": True}},
        right_arm={"agent_id": "memory.v2", "config": {"enabled": False}},
    )
    assert len(pairs) == 1 and pairs[0].verdict == "COMPARABLE"
    return {"pairs": len(pairs), "verdict": pairs[0].verdict}


def check_taxonomy_and_capability() -> dict[str, Any]:
    fixtures = check_fixtures()
    assert fixtures["ok"], fixtures
    records = load_v12_history()
    taxonomy = taxonomy_report(records, findings=[])
    assert taxonomy["runs"] == len(records)
    profile = capability_profile(records)
    assert len(profile["dimensions"]) == 6
    assert all(
        item["success_rate"] is None or 0 <= item["success_rate"] <= 1
        for item in profile["dimensions"]
    )
    assert profile["label_status"] == "agent_reviewed"
    untested = [item for item in profile["dimensions"] if item["measurable_runs"] == 0]
    assert all(item["success_rate"] is None for item in untested), "缺失机制不得补 0"
    return {"fixtures": fixtures["checked"], "dimensions": len(profile["dimensions"])}


def check_report() -> dict[str, Any]:
    records = load_v12_history()
    pack = build_evidence_pack(
        "MAP-16", records, question="planning 在 MAP-16 是否有效？", source="HISTORICAL"
    )
    assert pack.conclusion_level() in {"SUPPORTED", "TENTATIVE", "INSUFFICIENT", "NOT_TESTED"}
    markdown = build_report_v13(
        experiment={"name": "selfcheck", "mode": "simulated", "replicates": 1},
        summary={
            "experiment_id": "lab-selfcheck",
            "state": "COMPLETED",
            "mode": "simulated",
            "model": SIMULATED_MODEL,
            "provider_id": SIMULATED_PROVIDER,
            "maps": ["MAP-16"],
            "seeds": [0],
            "total_cells": 3,
            "executed": 3,
            "categories": {"mechanism_failure": 3},
            "budget": {"cost_settled_cny": "0", "requests_used": 12},
        },
        comparison={
            "verdict": "DESCRIPTIVE_ONLY",
            "reasons": [],
            "arms": [
                {"agent_id": "basic.v1", "runs": 3, "valid_denominator": 3, "successes": 0,
                 "success_rate": 0.0, "mean_requests": 4, "mean_cost_cny": 0.0},
                {"agent_id": "planning.v2", "runs": 3, "valid_denominator": 3, "successes": 1,
                 "success_rate": 0.333, "mean_requests": 8, "mean_cost_cny": 0.0},
            ],
        },
        records=records[:3],
        validity=six_map_audit(records),
        capability=capability_profile(records),
        taxonomy={"primary_counts": {"POLICY_BEHAVIOUR": 2}},
        protocol=ProtocolManifest(protocol_id="p", question="q", primary_metric="m").as_dict(),
    )
    for key in ("结论摘要", "锚点", "负面结果", "统计与解释限制"):
        assert key in markdown, key
    assert any(
        level in markdown
        for level in ("SUPPORTED", "TENTATIVE", "INSUFFICIENT", "NOT_TESTED")
    ), "报告必须给出结论等级"
    payload = report_payload(
        experiment={"name": "x", "mode": "simulated"},
        summary={"experiment_id": "e", "mode": "simulated", "state": "COMPLETED"},
        comparison={"verdict": "COMPARABLE", "arms": []},
        records=records[:3],
    )
    assert payload["schema"] == "v13-report-1"
    for key in FORBIDDEN:
        assert key not in markdown.lower(), f"报告泄露 {key}"
    return {"markdown_chars": len(markdown), "evidence_level": pack.conclusion_level()}


def check_ledger_tooling() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agent-arena-v13-ledger-") as temporary:
        root = Path(temporary)
        ledger = root / "ledger.jsonl"
        rows: list[dict[str, Any]] = [
            {"event": "run_started", "run_id": "run-1", "reserved_cny": "0.5"},
            {"event": "run_settled", "run_id": "run-1", "requests": 10, "input_tokens": 1000,
             "output_tokens": 100, "cost_settled_cny": "0.0123", "cost_unknown": False},
            {"event": "run_started", "run_id": "run-2", "reserved_cny": "0.5"},
        ]
        ledger.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
        audit = audit_ledger(ledger_path=ledger)
        assert audit.settled == 1
        assert audit.orphan_runs == ["run-2"]
        assert audit.issues, "孤儿任务必须被报告"
        no_bill = reconcile_bill(audit, None)
        assert no_bill["status"] == NO_BILL
        bill = root / "bill.csv"
        write_bill_template(bill, [("run-1", "0.0123", "CNY")])
        reconciled = reconcile_bill(
            audit, bill, ledger_rows=rows
        )
        assert reconciled["status"] == "RECONCILED_WITH_EXTERNAL_BILL", reconciled
        bill.write_text("run_id,amount,currency\nrun-1,9.99,CNY\n", encoding="utf-8")
        mismatch = reconcile_bill(audit, bill, ledger_rows=rows)
        assert mismatch["status"] != "RECONCILED_WITH_EXTERNAL_BILL"
        assert mismatch["mismatches"]
    return {"orphans_detected": True, "reconciled": True, "mismatch_detected": True}


def check_sdk() -> dict[str, Any]:
    report = run_sdk_checks()
    assert report["ok"], report["checks"]
    return {"checks": len(report["checks"])}


def check_pagination() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agent-arena-v13-page-") as temporary:
        base = Path(temporary) / "web"
        synthesize_history(base, 120)
        index = RunIndex(base)
        first = index.page(offset=0, limit=10)
        assert first["total"] == 120 and len(first["rows"]) == 10 and first["has_more"]
        last = index.page(offset=115, limit=10)
        assert len(last["rows"]) == 5 and not last["has_more"]
        filtered = index.page(map_id="MAP-16", limit=5)
        assert all(row["map_id"] == "MAP-16" for row in filtered["rows"])
        aggregate = index.aggregate()
        assert aggregate["runs"] == 120
        # 压力数据只写在临时目录，不进入真实 runs/。
        assert "agent-arena-v13-page-" in str(base)
    return {"pages": 2, "total": first["total"]}


def check_replicate_experiment_flow() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agent-arena-v13-rep-") as temporary:
        runs = RunService(Path(temporary) / "web", recover=False)
        lab = ExperimentService(
            Path(temporary) / "lab", run_service=runs, recover=False
        )
        try:
            spec = ExperimentSpec(
                name="rep",
                maps=["MAP-22"],
                agent_arms=[AgentArm(agent_id="basic.v1")],
                environment_seeds=[0],
                provider_id=SIMULATED_PROVIDER,
                model=SIMULATED_MODEL,
                mode=ExperimentMode.SIMULATED,
                budget=ExperimentBudget(
                    per_run_request_cap=10,
                    per_run_decision_cap=3,
                    experiment_request_cap=200,
                    experiment_cost_cap_cny=Decimal("1"),
                ),
            )
            source = lab.create_experiment(spec)
            rep = lab.create_replicates(
                source, conditions=["MAP-22|seed=0|basic.v1"], repeats=3
            )
            rep_spec = lab.spec(rep)
            assert rep_spec.replicates == 3
            assert rep_spec.experiment_kind == "replicate"
            assert len(rep_spec.matrix()) == 3
            assert len({cell.condition_key for cell in rep_spec.matrix()}) == 3
            # 同一份规格重复提交命中同一实验（幂等），不会新建。
            assert (
                lab.create_replicates(
                    source, conditions=["MAP-22|seed=0|basic.v1"], repeats=3
                )
                == rep
            )
            lab.submit(rep)
            manifest = lab.wait(rep, timeout=300)
            assert manifest.state.value == "COMPLETED", manifest.message
            assert manifest.counts["done"] == 3
            assert len({child["run_id"] for child in manifest.children}) == 3
            return {"cells": 3, "done": manifest.counts["done"]}
        finally:
            runs.shutdown()


def check_simulated_isolation() -> dict[str, Any]:
    """SIMULATED 不得写付费账本：临时 RunService 跑完一局后账本目录仍为空。"""

    with tempfile.TemporaryDirectory(prefix="agent-arena-v13-iso-") as temporary:
        base = Path(temporary) / "web"
        runs = RunService(base, recover=False)
        try:
            run_id = runs.create_run(_config("MAP-22", "memory.v2", decisions=4))
            runs.wait(run_id, timeout=120)
            ledger = base / "_ledger" / "web_ledger.jsonl"
            assert not ledger.is_file() or ledger.read_text(encoding="utf-8").strip() == ""
            status = runs.get_run(run_id)
            assert status.config["mode"] == "simulated"
            return {"run": run_id, "ledger_entries": 0}
        finally:
            runs.shutdown()


def check_exports_recompute() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agent-arena-v13-export-") as temporary:
        root = Path(temporary)
        base = root / "web"
        synthesize_history(base, 60)
        index = RunIndex(base)
        rows = index.page(offset=0, limit=60)["rows"]
        buffer = io.StringIO(newline="")
        fields = ["run_id", "map_id", "state", "cost_settled_cny"]
        writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        text = buffer.getvalue()
        assert text.count("\n") == 61
        records = load_v12_history(names=["main-54-runs.csv"])
        report = replicate_variability(records, min_obs=1)
        written = write_variability(report, root / "exports")
        assert set(written) == {
            "repeat_variability.csv",
            "repeat_variability.json",
            "repeat_variability.md",
        }
        parsed = list(
            csv.DictReader(
                io.StringIO(written["repeat_variability.csv"].read_text(encoding="utf-8-sig"))
            )
        )
        assert len(parsed) == len(report["rows"])
    return {"csv_lines": 61, "variability_rows": len(parsed)}


def run_checks(*, report_path: Path | None = None) -> dict[str, Any]:
    checks = [
        _check("contract_v13", check_contract_v13),
        _check("v10_freeze", check_v10_freeze),
        _check("thirty_maps", check_thirty_maps),
        _check("history_reproduction", check_history_reproduction),
        _check("ledger_reproduction", check_ledger_reproduction),
        _check("map30_ladder", check_map30_ladder),
        _check("six_map_validity", check_six_map_validity),
        _check("policies_v13", check_policies),
        _check("ablation_templates", check_ablation_templates),
        _check("comparability", check_comparability),
        _check("taxonomy_capability", check_taxonomy_and_capability),
        _check("report", check_report),
        _check("ledger_tooling", check_ledger_tooling),
        _check("sdk", check_sdk),
        _check("pagination", check_pagination),
        _check("replicate_flow", check_replicate_experiment_flow),
        _check("simulated_isolation", check_simulated_isolation),
        _check("exports_recompute", check_exports_recompute),
    ]
    failed = [item for item in checks if not item["ok"]]
    report = {
        "schema": "v13-selfcheck-1",
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


__all__ = ["FORBIDDEN", "run_checks"]
