"""V10 Batch 7：多环境 seed 的难度定标（设计难度 vs 经验难度）。

对 23 张 V10 原生图，从已有的 ``runs/v10/baselines/MAP-XX.json`` 与图元数据汇总：

- **设计难度**：世界内的 简单/中等/困难 标签（来自 V8 catalog）；
- **必要操作下界**：Oracle 动作数（可解性下界，不代表可发现性）；
- **预算余量**：决策预算 − Oracle 动作数；
- **策略基线表现**：``legal_random`` 成功率（可发现性的粗代理）、公开启发式成功率；
- **消融成功率**：核心机制被移除后的成功率（越高说明机制越容易被绕过）；
- **种子覆盖**：环境 seed 数与 ``scenario_hash`` 去重数。

输出 ``docs/v10/difficulty-calibration.md`` 与 ``runs/v10/difficulty/calibration.json``。
只读既有基线产物，不重新跑昂贵实验。
"""

from __future__ import annotations

import json
from typing import Any

from agent_arena.v10.baselines.suite import decision_budget
from agent_arena.v10.paths import V10_DOCS, V10_RUNS
from agent_arena.v10.runtime.catalog import LEVEL_OF, V10_MAPS, WORLD_OF, v10_class

LEVEL_RANK = {"简单": 1, "中等": 2, "困难": 3}


def _baseline(map_id: str) -> dict[str, Any]:
    path = V10_RUNS / "baselines" / f"{map_id}.json"
    if not path.is_file():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _rate(rows: list[dict[str, Any]]) -> tuple[int, int]:
    return sum(1 for row in rows if row.get("success")), len(rows)


def summarize(map_id: str) -> dict[str, Any]:
    data = _baseline(map_id)
    oracle = data.get("oracle", [])
    heuristic = data.get("public_heuristic", [])
    random_runs = data.get("legal_random", [])
    ablations = data.get("ablations", {})
    oracle_success, oracle_total = _rate(oracle)
    heuristic_success, heuristic_total = _rate(heuristic)
    random_success, random_total = _rate(random_runs)
    ablation_rates = {
        name: _rate(rows) for name, rows in sorted(ablations.items())
    }
    worst_ablation = max(
        (success / total for success, total in ablation_rates.values() if total),
        default=0.0,
    )
    actions = len(v10_class(map_id).SEED_SPACE)
    oracle_file = V10_RUNS / "oracle" / f"{map_id}-seed0.json"
    oracle_actions: int | None = None
    if oracle_file.is_file():
        payload = json.loads(oracle_file.read_text(encoding="utf-8"))
        oracle_actions = len(payload.get("actions") or [])
    if oracle_actions is None:
        oracle_actions = max(
            (len(row.get("actions", [])) for row in oracle if row.get("actions")), default=None
        )
    budget = decision_budget(map_id)
    return {
        "map_id": map_id,
        "world": WORLD_OF[map_id],
        "design_level": LEVEL_OF[map_id],
        "design_rank": LEVEL_RANK[LEVEL_OF[map_id]],
        "environment_seeds": actions,
        "unique_scenarios": data.get("unique_scenario_hashes"),
        "oracle": f"{oracle_success}/{oracle_total}",
        "oracle_actions": oracle_actions,
        "decision_budget": budget,
        "budget_margin": (budget - oracle_actions) if oracle_actions else None,
        "public_heuristic": f"{heuristic_success}/{heuristic_total}",
        "legal_random": f"{random_success}/{random_total}",
        "legal_random_rate": round(random_success / random_total, 4) if random_total else None,
        "ablations": {
            name: f"{success}/{total}" for name, (success, total) in ablation_rates.items()
        },
        "worst_ablation_rate": round(worst_ablation, 4),
        "ablation_min_rate": round(
            min(
                (success / total for success, total in ablation_rates.values() if total),
                default=0.0,
            ),
            4,
        ),
        "primary": v10_class(map_id).PRIMARY_METRIC,
    }


def calibrate() -> dict[str, Any]:
    rows = [summarize(map_id) for map_id in sorted(V10_MAPS)]
    by_world: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_world.setdefault(row["world"], []).append(row)
    for world_rows in by_world.values():
        world_rows.sort(key=lambda item: item["design_rank"])
    return {"maps": rows, "worlds": by_world}


def render(payload: dict[str, Any]) -> str:
    lines = [
        "# V10 多 seed 难度定标（设计难度 vs 经验难度）",
        "",
        "- 由 `python -m agent_arena.v10.difficulty` 从既有基线产物汇总，不重跑实验。",
        "- **设计难度** = V8 的 简单/中等/困难 标签；**经验难度**用 `legal_random` 成功率与"
        "“最容易被绕过的消融成功率”两个代理量描述。",
        "- `budget_margin` = 决策预算 − Oracle 动作数；负值表示预算偏紧。",
        "- `n=3` 之类的小样本只作描述，不作显著性断言。",
        "",
        "## 1. 十世界内的难度递进",
        "",
    ]
    for world in sorted(payload["worlds"]):
        rows = payload["worlds"][world]
        lines.append(f"### {world}")
        lines.append("")
        lines.append(
            "| 图 | 设计难度 | seed 数 | Oracle | Oracle 动作 | 预算余量 | 启发式 "
            "| legal_random | 最易绕过消融 | 主指标 |"
        )
        lines.append("|---|---|---:|---|---:|---:|---|---:|---:|---|")
        for row in rows:
            lines.append(
                "| {map_id} | {design_level} | {environment_seeds} | {oracle} | {acts} | {margin} "
                "| {heur} | {rand} | {worst} | `{primary}` |".format(
                    map_id=row["map_id"],
                    design_level=row["design_level"],
                    environment_seeds=row["environment_seeds"],
                    oracle=row["oracle"],
                    acts=row["oracle_actions"] if row["oracle_actions"] is not None else "—",
                    margin=row["budget_margin"] if row["budget_margin"] is not None else "—",
                    heur=row["public_heuristic"],
                    rand=f"{row['legal_random']} ({row['legal_random_rate']})",
                    worst=f"{row['ablation_min_rate']}–{row['worst_ablation_rate']}",
                    primary=row["primary"],
                )
            )
        lines.append("")
    reversals = []
    for world in sorted(payload["worlds"]):
        rows = sorted(payload["worlds"][world], key=lambda item: item["design_rank"])
        rates = [
            row["legal_random_rate"] if row["legal_random_rate"] is not None else 0.0
            for row in rows
        ]
        if any(rates[index] < rates[index + 1] for index in range(len(rates) - 1)):
            reversals.append(world)
    lines += [
        "## 2. 反转与解释",
        "",
        f"- `legal_random` 成功率随设计难度递进出现反转的世界：{'、'.join(reversals) or '无'}",
        "- 反转不等于设计错误：随机基线的成功率受“动作空间大小”和“是否容易误触成功终点”影响，",
        "  与认知负担不是同一维度；本表同时给出 `worst_ablation_rate`（机制被绕过的难易）供对照。",
        "- 设计难度与经验难度分开标注，不据单一模型成功率重排难度标签。",
        "",
        "## 3. 缺口",
        "",
        "- 6 张未进入 V10 原生运行时的图（01/02/05/16/17/25/27 中的一部分）不在本表；",
        "  它们的 3-seed 缺口见 `validated-regression.md`。",
        "- 每图只登记 3–10 个环境 seed，`n` 很小，禁止据此做跨模型排名。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    payload = calibrate()
    output = V10_RUNS / "difficulty"
    output.mkdir(parents=True, exist_ok=True)
    (output / "calibration.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    (V10_DOCS / "difficulty-calibration.md").write_text(render(payload), encoding="utf-8")
    print(json.dumps([row["map_id"] for row in payload["maps"]], ensure_ascii=False))


if __name__ == "__main__":
    main()
