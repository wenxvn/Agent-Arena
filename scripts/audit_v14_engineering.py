"""V14 工程边界审计（临时目录 + 零外部请求）。

用法：
    uv run python scripts/audit_v14_engineering.py            # 打印摘要
    uv run python scripts/audit_v14_engineering.py --write     # 写文档

覆盖：冷启动/预热、损坏 manifest、并发读写、TTL 刷新、长历史导出、
导出格式一致性、SDK 加固、账本复算。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.contracts import (  # noqa: E402
    AgentArm,
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
)
from agent_arena.lab.demo import demo_provider_factory  # noqa: E402
from agent_arena.lab.experiment import ExperimentService  # noqa: E402
from agent_arena.lab.v14.engineering import (  # noqa: E402
    engineering_markdown,
    engineering_report,
    export_consistency,
)
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER  # noqa: E402
from agent_arena.web.service import RunService  # noqa: E402


def _export_consistency_sample() -> dict:
    """在临时目录跑一个小型 SIMULATED 实验并检查导出口径。"""

    temporary = Path(tempfile.mkdtemp(prefix="agent-arena-v14-export-"))
    try:
        runs = RunService(
            temporary / "web", recover=False, simulated_provider_factory=demo_provider_factory
        )
        lab = ExperimentService(temporary / "lab", run_service=runs, recover=False)
        spec = ExperimentSpec(
            name="v14-export-consistency",
            notes="V14 导出一致性检查（SIMULATED，零费用）。",
            maps=["MAP-22", "MAP-26"],
            agent_arms=[AgentArm(agent_id="basic.v1"), AgentArm(agent_id="memory.v1")],
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
        experiment_id = lab.create_experiment(spec)
        lab.submit(experiment_id)
        lab.wait(experiment_id, timeout=600)
        files = lab.export(experiment_id)
        csv_texts = {
            name: Path(path).read_text(encoding="utf-8")
            for name, path in files.items()
            if name.endswith(".csv")
        }
        report_text = Path(files["report.md"]).read_text(encoding="utf-8")
        metrics = json.loads(Path(files["metrics.json"]).read_text(encoding="utf-8")) \
            if "metrics.json" in files else {}
        result = export_consistency(
            csv_texts,
            metrics=metrics,
            report_text=report_text,
            expected_mode="simulated",
        )
        result["files_present"] = sorted(files)
        return result
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v14")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    report = engineering_report()
    report["export_consistency"] = _export_consistency_sample()
    document = engineering_markdown(report)
    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "engineering-boundaries.md").write_text(
            document, encoding="utf-8", newline="\n"
        )
        (args.out / "engineering-boundaries.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    print(
        json.dumps(
            {
                "cold_ms": {
                    item["label"]: item["milliseconds"]
                    for item in report["cold_start"]["measurements"]
                },
                "corrupted_ok": not report["corrupted_manifest"]["bad_run_indexed"],
                "concurrent_ok": report["concurrent"]["ok"],
                "ttl_ok": report["ttl_refresh"]["ok"],
                "long_export_rows": report["long_export"]["rows_exported"],
                "export_consistency_ok": report["export_consistency"]["ok"],
                "sdk_ok": report["sdk"]["ok"],
                "ledger_status": report["ledger"]["status"],
                "ledger_matches": report["ledger"]["matches_v13_record"],
                "written": str(args.out / "engineering-boundaries.md") if args.write else None,
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
