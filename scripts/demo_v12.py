"""V12 无 API Key 的可复现演示。

一条命令跑完：

    实验配置 → 预检（零请求）→ 提交 → 父子状态 → 对照 → 诊断 → 六图视图 → 导出

用法：
    uv run python scripts/demo_v12.py
    uv run python scripts/demo_v12.py --maps MAP-22 MAP-18 MAP-26
    uv run python scripts/demo_v12.py --out runs/v12/demo

不会发送任何 Provider 请求；默认写到 ``runs/v12/demo``（``runs/`` 已在 .gitignore）。
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
    ExperimentBudget,
    ExperimentMode,
    ExperimentSpec,
)
from agent_arena.lab.demo import DEMO_NOTE, demo_provider_factory  # noqa: E402
from agent_arena.lab.experiment import ExperimentService, preflight  # noqa: E402
from agent_arena.web.schemas import SIMULATED_MODEL, SIMULATED_PROVIDER  # noqa: E402
from agent_arena.web.service import RunService  # noqa: E402


def _print(title: str) -> None:
    print()
    print(f"== {title} ==")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--maps", nargs="+", default=["MAP-10", "MAP-22", "MAP-26"])
    parser.add_argument("--agents", nargs="+", default=["basic.v1", "memory.v1", "planning.v1"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[0])
    parser.add_argument("--decisions", type=int, default=12)
    parser.add_argument("--out", type=Path, default=ROOT / "runs" / "v12" / "demo")
    args = parser.parse_args()

    from agent_arena.v10.runtime.catalog import MAP_IDS

    maps = [item for item in args.maps if item in MAP_IDS]
    if not maps:
        print("请至少选择一张已注册的地图（MAP-01～MAP-30）。")
        return 2

    print("Agent Arena Lab 1.0 · 离线演示")
    print("说明：" + DEMO_NOTE)
    print("本演示不联网、不产生费用；所有结果标注 mode=simulated。")

    spec = ExperimentSpec(
        name="demo-scripted-architectures",
        notes=DEMO_NOTE,
        maps=maps,
        agent_arms=[AgentArm(agent_id=agent) for agent in args.agents],
        environment_seeds=args.seeds,
        provider_id=SIMULATED_PROVIDER,
        model=SIMULATED_MODEL,
        mode=ExperimentMode.SIMULATED,
        budget=ExperimentBudget(
            per_run_request_cap=40,
            per_run_decision_cap=args.decisions,
            experiment_request_cap=2_000,
            experiment_cost_cap_cny=Decimal("10"),
        ),
    )
    _print("1. 预检（零请求）")
    result = preflight(spec)
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=1))
    if not result.ok:
        print("预检未通过，演示停止。")
        return 1

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    runs_dir = out / "web"
    lab_dir = out / "lab"
    runs = RunService(
        runs_dir, recover=False, simulated_provider_factory=demo_provider_factory
    )
    lab = ExperimentService(lab_dir, run_service=runs, recover=False)
    try:
        _print("2. 创建并提交")
        # 幂等键带规格指纹：同一规格复跑不会重复建实验，换规格则新建。
        key = f"demo-v12:{spec.fingerprint()[:12]}"
        experiment_id = lab.create_experiment(spec, idempotency_key=key)
        duplicate = lab.create_experiment(spec, idempotency_key=key)
        print(f"experiment_id = {experiment_id}")
        print(f"幂等复提交返回同一实验：{duplicate == experiment_id}")
        lab.submit(experiment_id)
        manifest = lab.wait(experiment_id, timeout=900)
        print(f"父实验状态：{manifest.state.value}；子局 {manifest.counts}")

        _print("3. 父/子状态一致性")
        for child in manifest.children:
            status = runs.get_run(child["run_id"])
            print(
                f"  #{child['matrix_index']:02d} {child['map_id']} "
                f"seed={child['environment_seed']} "
                f"{child['agent_id']:<12} {status.state.value:<14} {child['outcome']}"
            )

        _print("4. 汇总与配对比较")
        summary = lab.summary(experiment_id)
        comparison = lab.comparison(experiment_id)
        print(
            json.dumps(
                {
                    "executed": summary["executed"],
                    "valid_denominator": summary["valid_denominator"],
                    "categories": summary["categories"],
                    "verdict": comparison["verdict"],
                    "reasons": comparison["reasons"],
                    "notes": comparison["notes"],
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        for arm in comparison["arms"]:
            print(
                f"  {arm['agent_id']:<12} 局数 {arm['runs']} 有效 {arm['valid_denominator']} "
                f"成功 {arm['successes']} 平均请求 {arm['mean_requests']} "
                f"平均费用 {arm['mean_cost_cny']}"
            )

        _print("5. 失败诊断（每条都指向具体 decision 事件）")
        findings = lab.findings(experiment_id)
        for finding in findings[:10]:
            evidence = ", ".join(finding.evidence_event_ids) or "无单步证据"
            print(f"  [{finding.severity}] {finding.map_id} {finding.category}: {finding.summary}")
            print(f"      证据：{evidence}")

        _print("6. 两条轨迹对照（同图同 seed 的不同架构）")
        records = lab.records(experiment_id)
        pairs: list[dict[str, Any]] = []
        by_condition: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for record in records:
            by_condition.setdefault(
                (str(record["map_id"]), int(record["environment_seed"])), []
            ).append(record)
        for (map_id, seed), items in sorted(by_condition.items()):
            for left, right in zip(items, items[1:], strict=False):
                if left["agent_id"] == right["agent_id"]:
                    continue
                diff = lab.pairwise(
                    experiment_id, str(left["run_id"]), str(right["run_id"])
                )
                pairs.append(diff)
                print(
                    f"  {map_id} seed={seed}：{left['agent_id']} vs {right['agent_id']}"
                    f" → 首次差异第 {diff['diff']['first_divergence_step']} 步"
                )
                print(f"      {diff['diff']['first_divergence_summary']}")
                if len(pairs) >= 2:
                    break
            if len(pairs) >= 2:
                break

        _print("7. 六图可视化（view-model）")
        for record in records[:3]:
            model = lab.view_model(str(record["run_id"]))
            print(
                f"  {model['map_id']} · {model['kind']} · available={model['available']} · "
                f"步数={model['steps']}"
            )
            if model["kind"] == "exploration_graph":
                print(f"      已发现路标：{[node['sign'] for node in model['nodes']]}")
                edges = len(model["edges"])
                notes = len(model["agent_notes"])
                print(f"      走过边数：{edges}；记忆条数：{notes}")

        _print("8. 导出")
        files = lab.export(experiment_id)
        for name, path in sorted(files.items()):
            print(f"  {name:<24} {path}")
        report = Path(files["report.md"]).read_text(encoding="utf-8")
        print(f"  报告长度 {len(report)} 字符；包含不可比声明：{'不可比' in report}")

        demo_copy = out / "report.md"
        shutil.copyfile(files["report.md"], demo_copy)
        print(f"\n可读报告副本：{demo_copy}")
        print("完成：可用 `uv run agent-arena web` 在 Lab 页面查看同一目录。")
        return 0
    finally:
        runs.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
