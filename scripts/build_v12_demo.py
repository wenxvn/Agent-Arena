"""生成 V12 可提交的演示数据包（脱敏、小体积、标注 SIMULATED）。

产物写入 ``docs/v12/demo/``：

- ``01-offline-basic-memory-planning/``：三架构离线模拟对照（summary/comparison/报告）；
- ``02-pairwise-diff/``：一对轨迹对照（diff + 假设）；
- ``03-failure-evidence/``：一条失败证据报告（findings 子集）；
- ``README.md``：说明这些文件不是真实模型结果。

用法：
    uv run python scripts/build_v12_demo.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.contracts import (  # noqa: E402
    AgentArm,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
)
from agent_arena.lab.demo import DEMO_NOTE, demo_provider_factory  # noqa: E402
from agent_arena.lab.experiment import ExperimentService  # noqa: E402
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER  # noqa: E402
from agent_arena.web.service import RunService  # noqa: E402

OUTPUT = ROOT / "docs" / "v12" / "demo"
MAX_STEP_FIELDS = ("decision_index", "action", "result", "status")


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8", newline="\n")
    else:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
            encoding="utf-8",
            newline="\n",
        )


def _spec() -> ExperimentSpec:
    return ExperimentSpec(
        name="demo-three-architectures",
        notes=DEMO_NOTE,
        maps=["MAP-10", "MAP-22", "MAP-26"],
        agent_arms=[
            AgentArm(agent_id="basic.v1"),
            AgentArm(agent_id="memory.v1"),
            AgentArm(agent_id="planning.v1"),
        ],
        environment_seeds=[0],
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        mode=ExperimentMode.SIMULATED,
        budget=ExperimentBudget(
            per_run_request_cap=40,
            per_run_decision_cap=12,
            experiment_request_cap=600,
            experiment_cost_cap_cny=Decimal("10"),
        ),
    )


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(
        prefix="agent-arena-v12-demo-", ignore_cleanup_errors=True
    )
    base = Path(temporary.name) / "runs"
    runs = RunService(
        base / "web", recover=False, simulated_provider_factory=demo_provider_factory
    )
    lab = ExperimentService(base / "lab", run_service=runs, recover=False)
    try:
        experiment_id = lab.create_experiment(_spec(), idempotency_key="demo-assets")
        lab.submit(experiment_id)
        manifest = lab.wait(experiment_id, timeout=900)
        summary = lab.summary(experiment_id)
        comparison = lab.comparison(experiment_id)
        records = lab.records(experiment_id)
        findings = lab.findings(experiment_id)

        # 01：三架构对照
        group = OUTPUT / "01-offline-basic-memory-planning"
        _write(
            group / "summary.json",
            {
                "note": DEMO_NOTE,
                "mode": summary["mode"],
                "experiment_id": experiment_id,
                "state": summary["state"],
                "executed": summary["executed"],
                "valid_denominator": summary["valid_denominator"],
                "categories": summary["categories"],
                "arms": [
                    {
                        "agent_id": arm["agent_id"],
                        "runs": arm["runs"],
                        "successes": arm["successes"],
                        "mean_requests": arm["mean_requests"],
                        "mean_cost_cny": arm["mean_cost_cny"],
                    }
                    for arm in comparison["arms"]
                ],
                "verdict": comparison["verdict"],
                "verdict_reasons": comparison["reasons"],
                "verdict_notes": comparison["notes"],
            },
        )
        _write(group / "comparison.json", comparison)
        report = lab.report(experiment_id)
        _write(group / "report.md", report)

        # 02：一对轨迹对照（同图同 seed 的不同架构）
        pairs: list[dict[str, Any]] = []
        by_condition: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for record in records:
            by_condition.setdefault(
                (str(record["map_id"]), int(record["environment_seed"])), []
            ).append(record)
        for (map_id, seed), items in sorted(by_condition.items()):
            if len(items) < 2:
                continue
            left, right = items[0], items[1]
            diff = lab.pairwise(
                experiment_id, str(left["run_id"]), str(right["run_id"])
            )
            steps_left, _ = lab._steps(str(left["run_id"]))
            steps_right, _ = lab._steps(str(right["run_id"]))
            pairs.append(
                {
                    "note": DEMO_NOTE,
                    "map_id": map_id,
                    "environment_seed": seed,
                    "left_agent": left["agent_id"],
                    "right_agent": right["agent_id"],
                    "diff": diff["diff"],
                    "hypotheses": diff["hypotheses"],
                    "left_steps": [
                        {key: step.get(key) for key in MAX_STEP_FIELDS}
                        for step in steps_left[:12]
                    ],
                    "right_steps": [
                        {key: step.get(key) for key in MAX_STEP_FIELDS}
                        for step in steps_right[:12]
                    ],
                }
            )
        _write(
            OUTPUT / "02-pairwise-diff" / "pairwise.json",
            {"note": DEMO_NOTE, "pairs": pairs[:3]},
        )

        # 03：失败证据报告
        critical = [item for item in findings if item.severity == "critical"]
        warnings = [item for item in findings if item.severity == "warning"]
        evidence = (critical + warnings)[:8]
        _write(
            OUTPUT / "03-failure-evidence" / "findings.json",
            {
                "note": DEMO_NOTE,
                "experiment_id": experiment_id,
                "total_findings": len(findings),
                "critical": len(critical),
                "warning": len(warnings),
                "samples": [item.as_dict() for item in evidence],
            },
        )
        lines = [
            "# 失败证据样例（SIMULATED）",
            "",
            f"> {DEMO_NOTE}",
            "",
            f"- 实验：`{experiment_id}`",
            f"- 诊断总数：{len(findings)}（critical {len(critical)} / warning {len(warnings)}）",
            "",
            "| 地图 | 类别 | 严重度 | 证据步 | 说明 |",
            "|---|---|---|---|---|",
        ]
        for item in evidence:
            steps = ", ".join(str(step) for step in item.evidence_steps) or "—"
            lines.append(
                f"| {item.map_id} | `{item.category}` | {item.severity} | {steps} | {item.summary} |"
            )
        lines += [
            "",
            "每条结论都能在 `runs/web/<run_id>/events.jsonl` 的 `decision` 事件里找到对应",
            "`decision_index`；不包含任何隐藏真值。",
            "",
        ]
        _write(OUTPUT / "03-failure-evidence" / "report.md", "\n".join(lines))

        _write(
            OUTPUT / "README.md",
            "\n".join(
                [
                    "# V12 演示数据包（SIMULATED）",
                    "",
                    f"> {DEMO_NOTE}",
                    "",
                    "这些文件由 `uv run python scripts/build_v12_demo.py` 生成，",
                    "用于在没有 API Key、没有网络的情况下演示 Lab 的完整链路：",
                    "",
                    "| 目录 | 内容 |",
                    "|---|---|",
                    "| `01-offline-basic-memory-planning/` | 三架构离线模拟对照：汇总、配对判定、可读报告 |",
                    "| `02-pairwise-diff/` | 同图同 seed 的一对轨迹对照：首次差异、指标增量、可验证假设 |",
                    "| `03-failure-evidence/` | 失败证据样例：类别、严重度、证据步 |",
                    "",
                    "## 这些不是真实模型结果",
                    "",
                    "- `mode=simulated`，Provider 是确定性脚本；",
                    "- 动作由人工按公开规则编写，不是 Oracle，也不代表任何模型能力；",
                    "- 报告中所有“成功率/费用”数字只说明链路可用，不能外推。",
                    "",
                    "## 复现",
                    "",
                    "```bash",
                    "uv run python scripts/build_v12_demo.py",
                    "uv run python scripts/demo_v12.py --out runs/v12/demo",
                    "```",
                    "",
                ]
            ),
        )
        print(f"demo assets written to {OUTPUT}")
        print(f"experiment {experiment_id} state={manifest.state.value} counts={manifest.counts}")
        return 0
    finally:
        runs.shutdown()
        temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
