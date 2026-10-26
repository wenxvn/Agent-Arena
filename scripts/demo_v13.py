"""V13 零 Key 演示：三种 Agent + Reflection 真触发 + 重复比较 + 自动报告。

全部走 ``SIMULATED`` 通道（确定性脚本 Provider）：**不联网、不花钱、不写付费账本**。
输出目录默认 ``runs/v13/demo``（可被 ``--out`` 覆盖），并在每份产物里标注
``SIMULATED``。

用法：
    uv run python scripts/demo_v13.py
    uv run python scripts/demo_v13.py --out runs/v13/demo --repeats 3
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.contracts import (  # noqa: E402
    AgentArm,
    ComparisonPolicy,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
)
from agent_arena.lab.experiment import ExperimentService, preflight  # noqa: E402
from agent_arena.lab.v13.capability import (  # noqa: E402
    capability_markdown,
    capability_profile,
)
from agent_arena.lab.v13.report import build_report_v13, write_report  # noqa: E402
from agent_arena.lab.v13.stability import (  # noqa: E402
    replicate_variability,
    write_variability,
)
from agent_arena.lab.v13.taxonomy import taxonomy_report  # noqa: E402
from agent_arena.lab.v13.validity import (  # noqa: E402
    map30_ladder,
    map30_markdown,
    six_map_audit,
    validity_markdown,
)
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER  # noqa: E402
from agent_arena.web.service import RunService  # noqa: E402

DEMO_MAPS = ("MAP-22", "MAP-16")
DEMO_AGENTS = ("basic.v1", "memory.v2", "planning.v2", "reflection.v2")


def _spec(repeats: int) -> ExperimentSpec:
    return ExperimentSpec(
        name="v13-demo",
        notes=(
            "V13 零 Key 演示：SIMULATED 通道，用于验证重复身份、Reflection 触发、"
            "分层诊断与模板化报告；不代表任何真实模型能力。"
        ),
        maps=list(DEMO_MAPS),
        agent_arms=[AgentArm(agent_id=agent) for agent in DEMO_AGENTS],
        environment_seeds=[0],
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        mode=ExperimentMode.SIMULATED,
        replicates=repeats,
        experiment_kind="matrix",
        budget=ExperimentBudget(
            per_run_request_cap=60,
            per_run_decision_cap=16,
            per_run_cost_cap_cny=Decimal("1.00"),
            experiment_request_cap=4_000,
            experiment_cost_cap_cny=Decimal("10.00"),
        ),
        comparison=ComparisonPolicy(min_paired_samples=repeats),
    )


def _reflection_probe(out: Path) -> dict[str, Any]:
    """Reflection 真触发探针（Gate 6 的可复现证据）。

    用固定脚本动作（**不是 Oracle**，只是"连续做同一件事"）驱动一局，让公开触发器
    命中，并把事件写入 JSON。零请求以外的费用、SIMULATED 通道。
    """

    from agent_arena.lab.runner import run_lab_episode
    from agent_arena.lab.simulated import scripted_provider
    from agent_arena.web.schemas import RunConfig, RunMode

    script = [{"tool": "observe_signpost"}] * 10
    provider = scripted_provider("MAP-22", script)
    config = RunConfig(
        map_id="MAP-22",
        environment_seed=0,
        mode=RunMode.SIMULATED,
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        agent="reflection.v2",
        max_decisions=8,
        max_requests=40,
        max_input_tokens=400_000,
        max_output_tokens=8_000,
        max_cost_cny=Decimal("1.00"),
    )
    outcome = run_lab_episode(config, provider=provider)
    events = [
        event
        for event in outcome.result.get("agent_events") or []
        if event.get("kind") == "reflection"
    ]
    snapshot = outcome.result["provenance"]["policy"]
    payload = {
        "schema": "v13-reflection-probe-1",
        "mode": "simulated",
        "note": (
            "SIMULATED 探针：用固定脚本动作制造重复动作触发；"
            "不是 Oracle 解，也不代表真实模型会触发。"
        ),
        "state": outcome.state.value,
        "triggered": snapshot.get("triggered"),
        "eligible": snapshot.get("eligible"),
        "exposure": snapshot.get("exposure"),
        "events": events,
        "requests": (outcome.result.get("usage") or {}).get("requests"),
    }
    path = out / "reflection-trigger-probe.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {"path": str(path), "triggered": payload["triggered"], "exposure": payload["exposure"]}


def _main(out: Path, repeats: int) -> dict[str, Any]:
    if out.exists():
        # 只清理由本脚本自己生成的目录，避免误删用户数据。
        marker = out / "DEMO_SIMULATED.txt"
        if marker.is_file():
            shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "DEMO_SIMULATED.txt").write_text(
        "本目录是 V13 零 Key 演示产物：SIMULATED 通道，不联网、不产生费用。\n"
        "不得当作真实模型能力证据。\n",
        encoding="utf-8",
        newline="\n",
    )
    runs = RunService(out / "web", recover=False)
    lab = ExperimentService(out / "lab", run_service=runs, recover=False)
    try:
        spec = _spec(repeats)
        result = preflight(spec)
        assert result.ok, result.blockers
        experiment_id = lab.create_experiment(spec)
        lab.submit(experiment_id)
        manifest = lab.wait(experiment_id, timeout=1_800)
        records = lab.records(experiment_id)
        summary = lab.summary(experiment_id)
        comparison = lab.comparison(experiment_id)
        findings = lab.findings(experiment_id)
        stability = replicate_variability(records, min_obs=2, source="SIMULATED")
        validity = six_map_audit(records)
        capability = capability_profile(records)
        taxonomy = taxonomy_report(records, findings)

        written: dict[str, str] = {}
        for name, path in write_variability(stability, out).items():
            written[name] = str(path)
        for name, text in (
            ("map-validity.md", validity_markdown(validity)),
            ("capability-profile.md", capability_markdown(capability)),
            ("diagnosis-taxonomy.md", _taxonomy_markdown(taxonomy)),
        ):
            path = out / name
            path.write_text(text, encoding="utf-8", newline="\n")
            written[name] = str(path)
        if any(str(record.get("map_id")) == "MAP-30" for record in records):
            ladder = map30_ladder(records)
            path = out / "map30-ladder.md"
            path.write_text(map30_markdown(ladder), encoding="utf-8", newline="\n")
            written[path.name] = str(path)

        markdown = build_report_v13(
            experiment=lab.store.load_spec(experiment_id),
            summary=summary,
            comparison=comparison,
            records=records,
            findings=findings,
            stability=stability,
            validity=validity,
            capability=capability,
            taxonomy=taxonomy,
            protocol=None,
        )
        for name, path in write_report(
            out,
            markdown,
            {
                "schema": "v13-demo-1",
                "experiment_id": experiment_id,
                "mode": "simulated",
                "repeats": repeats,
            },
        ).items():
            written[name] = str(path)

        reflection = [
            record
            for record in records
            if str(record.get("agent_id")) == "reflection.v2"
        ]
        triggers = 0
        for record in reflection:
            replay = runs.load_replay(str(record["run_id"]))
            for event in replay.get("events") or []:
                if event.get("agent_event") == "reflection_triggered":
                    triggers += 1
        probe = _reflection_probe(out)
        return {
            "experiment_id": experiment_id,
            "state": manifest.state.value,
            "runs": len(records),
            "categories": summary.get("categories"),
            "valid_denominator": summary.get("valid_denominator"),
            "flip_rate": stability["flip_rate"],
            "reflection_triggers_in_matrix": triggers,
            "reflection_probe": probe,
            "written": written,
            "out": str(out),
            "note": "SIMULATED：只验证调用链/重复身份/报告链路，不代表模型能力。",
        }
    finally:
        runs.shutdown()


def _taxonomy_markdown(report: dict[str, Any]) -> str:
    from agent_arena.lab.v13.taxonomy import taxonomy_markdown

    return taxonomy_markdown(report)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "v13" / "demo")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    payload = _main(args.out, max(1, min(5, args.repeats)))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
