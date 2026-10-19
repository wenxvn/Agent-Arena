"""V10 Batch 5/9：V9 已 VALIDATED 图的防回归审计（含 V10 已原生化的图）。

对 MAP-01/02/05/16/17/25/27 逐图记录：

- 运行时来源（V10 原生 / V8 回退）；
- 环境 seed 0/1/2 是否真的产生不同实例（``seed_effective``）与三个 ``scenario_hash``；
- V9 存档的 Oracle / 消融结果（只读引用，作为防回归基线）；
- 用当前运行时在 seed 0 复跑 V9 Oracle 用例，确认行为未漂移。

输出 ``docs/v10/validated-regression.md`` 与 ``runs/v10/regression/validated_regression.json``。
"""

from __future__ import annotations

import json
from typing import Any

from agent_arena.v10.paths import V9_RUNS, V10_DOCS, V10_RUNS
from agent_arena.v10.runtime.catalog import (
    create_environment,
    is_v10,
    scenario_hash,
    seed_effective,
)
from agent_arena.worlds.scenario_v8.models import V8Action

VALIDATED = ("MAP-16",)
SEEDS = (0, 1, 2)


def _v9_baseline(map_id: str) -> dict[str, Any]:
    path = V9_RUNS / "baselines" / f"{map_id}.json"
    if not path.is_file():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _oracle_cases(map_id: str) -> list[dict[str, Any]]:
    """V8 运行时模块里的 ORACLE_CASES（V10 原生另走 runtime 的 oracle_actions）。"""

    module_name = f"agent_arena.worlds.scenario_v8.maps.map{map_id[-2:]}"
    try:
        module = __import__(module_name, fromlist=["ORACLE_CASES"])
    except ModuleNotFoundError:
        return []
    return [dict(case) for case in getattr(module, "ORACLE_CASES", ())]


def _replay(map_id: str, seed: int, actions: list[dict[str, Any]]) -> dict[str, Any]:
    environment = create_environment(map_id, environment_seed=seed)
    executed = 0
    for payload in actions:
        if environment.is_terminal:
            break
        try:
            action = V8Action.model_validate(payload, strict=True)
        except Exception:  # noqa: BLE001 - 回放旧用例时形状可能不同
            break
        if not environment.accepts(action):
            break
        environment.step(action)
        executed += 1
    return {
        "executed": executed,
        "status": environment.status.value,
        "success": environment.is_success,
        "terminal_reason": environment.terminal_reason,
    }


def audit() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for map_id in VALIDATED:
        baseline = _v9_baseline(map_id)
        native = is_v10(map_id)
        effective = seed_effective(map_id, SEEDS)
        hashes = [scenario_hash(map_id, seed)[:16] for seed in SEEDS]
        replays: list[dict[str, Any]] = []
        if native:
            from agent_arena.v10.baselines import runner as v10_runner

            module = __import__(
                f"agent_arena.v10.baselines.map{map_id[-2:]}", fromlist=["oracle_actions"]
            )
            for seed in SEEDS:
                run = v10_runner.run_actions(
                    map_id, module.oracle_actions(seed), environment_seed=seed
                )
                replays.append(
                    {
                        "seed": seed,
                        "success": run.success,
                        "status": run.status,
                        "actions": len(module.oracle_actions(seed)),
                    }
                )
        else:
            for case in _oracle_cases(map_id):
                seed = int(case.get("seed", 0))
                result = _replay(map_id, seed, list(case.get("actions") or []))
                result["seed"] = seed
                result["expect_success"] = bool(case.get("expect_success"))
                replays.append(result)
        oracle_ok = sum(
            1
            for item in baseline.get("oracle", [])
            if item.get("ok") or item.get("success")
        )
        rows.append(
            {
                "map_id": map_id,
                "runtime": "v10" if native else "v8_fallback",
                "seed_effective": effective,
                "scenario_hashes": hashes,
                "v9_oracle": f"{oracle_ok}/{len(baseline.get('oracle', []))}"
                if baseline
                else "missing",
                "v9_ablations": {
                    name: bool(record.get("success"))
                    for name, record in (baseline.get("ablations") or {}).items()
                },
                "replay": replays,
                "regression_ok": all(item.get("success") for item in replays if "success" in item),
                "three_seed_met": bool(effective) and len(set(hashes)) == len(SEEDS),
            }
        )
    return {
        "maps": rows,
        "three_seed_met": [row["map_id"] for row in rows if row["three_seed_met"]],
        "three_seed_missing": [row["map_id"] for row in rows if not row["three_seed_met"]],
        "regression_failed": [row["map_id"] for row in rows if not row["regression_ok"]],
    }


def render(payload: dict[str, Any]) -> str:
    lines = [
        "# V9 已 VALIDATED 图的防回归审计（含 V10 已原生化的图）",
        "",
        "- 由 `python -m agent_arena.v10.regression` 生成；V8/V9 只读。",
        "- `runtime=v8_fallback` 的图在 V10 尚无原生运行时；已原生化的图（如 MAP-05）",
        "  按 V10 实例判定。",
        "- `seed_effective` 用初始 Observation + 密封真值指纹比较 seed 0/1/2；三者全不同才算通过。",
        "",
        "| 图 | 运行时 | 3 seed 实例不同 | scenario_hash | V9 Oracle | 防回归复跑 | 结论 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in payload["maps"]:
        lines.append(
            "| {map_id} | {runtime} | {effective} | {hashes} | {oracle} | {replay} | "
            "{verdict} |".format(
                map_id=row["map_id"],
                runtime=row["runtime"],
                effective="是" if row["seed_effective"] else "**否**",
                hashes=" / ".join(row["scenario_hashes"]),
                oracle=row["v9_oracle"],
                replay="通过" if row["regression_ok"] else "**失败**",
                verdict="VALIDATED 维持"
                if row["three_seed_met"] and row["regression_ok"]
                else "**3-seed 未达标（保留 VALIDATED 但记缺口）**"
                if row["regression_ok"]
                else "**防回归失败，需复核**",
            )
        )
    lines += [
        "",
        "## 汇总",
        "",
        f"- 3 seed 实例确实不同：{'、'.join(payload['three_seed_met']) or '无'}",
        f"- 3 seed 未达标：{'、'.join(payload['three_seed_missing']) or '无'}",
        f"- 防回归失败：{'、'.join(payload['regression_failed']) or '无'}",
        "",
        "3 seed 未达标的图**不撤销** V9 的 VALIDATED（它们的构念证据仍然成立），",
        "但必须在最终报告中列为“多 seed 覆盖缺口”，不能声称已完成 30/30 的 3-seed 验证。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = audit()
    V10_DOCS.mkdir(parents=True, exist_ok=True)
    output = V10_RUNS / "regression"
    output.mkdir(parents=True, exist_ok=True)
    (output / "validated_regression.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    , newline="\n")
    (V10_DOCS / "validated-regression.md").write_text(
        render(payload), encoding="utf-8", newline="\n"
    )
    print(json.dumps({k: v for k, v in payload.items() if k != "maps"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
