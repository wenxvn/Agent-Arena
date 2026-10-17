"""从逐图基线 JSON 生成 `docs/v9/baselines.md`（避免 summary.json 被单批覆盖）。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "runs" / "v9" / "baselines"
OUTPUT = ROOT / "docs" / "v9" / "baselines.md"

WORLDS = {
    "spaceship": range(1, 4),
    "lighthouse": range(4, 7),
    "abyss": range(7, 10),
    "polar": range(10, 13),
    "pyramid": range(13, 16),
    "subway": range(16, 19),
    "volcano": range(19, 22),
    "jungle": range(22, 25),
    "lunar": range(25, 28),
    "castle": range(28, 31),
}


def load(map_id: str) -> dict | None:
    path = BASELINES / f"{map_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _short(value: object, limit: int = 60) -> str:
    if value is None:
        return "null"
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> None:
    lines = [
        "# V9 基线与消融结果（自动生成）",
        "",
        "来源：`runs/v9/baselines/MAP-XX.json`。每图包含 Oracle 回放、20 个策略种子的",
        "`legal_random`、一个 `public_heuristic` 与（若有）显式消融。",
        "Oracle 只证明存在合法路径，不代表模型能力；`legal_random` 语义非法由环境裁决。",
        "",
        "> 环境 seed 固定为注册实例（默认 0）；`legal_random` 只改变策略 RNG 种子。",
        "",
        "## 1. 总览",
        "",
        "| map | world | 难度 | Oracle | random 成功 | heuristic | 决策 | 终局 "
        "| 消融（成功=旁路证据） |",
        "|---|---|---|---:|---:|---|---:|---|---|",
    ]
    totals = {"oracle": 0, "oracle_ok": 0, "random_success": 0, "heuristic": 0, "maps": 0}
    for world, indexes in WORLDS.items():
        for index in indexes:
            map_id = f"MAP-{index:02d}"
            data = load(map_id)
            if data is None:
                lines.append(f"| {map_id} | {world} | - | - | - | - | - | - | 未运行 |")
                continue
            totals["maps"] += 1
            oracle = data.get("oracle") or []
            oracle_ok = sum(1 for item in oracle if item.get("ok"))
            totals["oracle"] += len(oracle)
            totals["oracle_ok"] += oracle_ok
            random = data.get("legal_random") or []
            random_success = sum(1 for item in random if item.get("success"))
            totals["random_success"] += random_success
            heuristic = data.get("public_heuristic") or {}
            if heuristic.get("success"):
                totals["heuristic"] += 1
            ablations = data.get("ablations") or {}
            ablation_text = ", ".join(
                f"{name}={'✓' if record.get('success') else '✗'}"
                for name, record in ablations.items()
            ) or "-"
            lines.append(
                (
                    "| {map} | {world} | {level} | {ok}/{total} | {rand}/20 | {heur} "
                    "| {dec} | {term} | {abl} |"
                ).format(
                    map=map_id,
                    world=data["world"],
                    level=data["difficulty"],
                    ok=oracle_ok,
                    total=len(oracle),
                    rand=random_success,
                    heur="✓" if heuristic.get("success") else ("✗" if heuristic else "-"),
                    dec=heuristic.get("decisions", "-"),
                    term=_short(heuristic.get("terminal_reason") or heuristic.get("status")),
                    abl=ablation_text,
                )
            )
    lines.extend(
        [
            "",
            f"- Oracle：{totals['oracle_ok']}/{totals['oracle']} 个用例真实回放成功。",
            f"- `legal_random`：{totals['random_success']}/600 次运行成功（30 图 × 20 seed）。",
            f"- `public_heuristic`：{totals['heuristic']}/{totals['maps']} 图成功。",
            "",
            "## 2. 关键读法",
            "",
            "- **random 成功率高**（MAP-15、MAP-21）说明地图的通过条件可被低成本猜中，"
            "是 `LOW_DISCRIMINATION` / `CONSTRUCT_BYPASS` 的直接证据。",
            "- **消融成功**表示“被移除的机制不是通关必需”，但这不等于地图无效："
            "有些机制是效率/安全护栏，不是成功前置。逐图审计 §2/§9 区分了这两种情况。",
            "- **heuristic 成功不等于模型可发现**：策略作者可以使用设计稿常量；"
            "审计 §3 标注了哪些常量未公开。早期 MAP-22/26 的策略失败已分别修正为 "
            "24/11 决策成功，原因记录在对应审计 §4。",
            "",
            "## 3. 复现",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -m agent_arena.v9.baseline_run",
            "```",
            "",
            "单图：`. \\.venv\\Scripts\\python.exe -m agent_arena.v9.baseline_run MAP-09`；",
            "调试策略：`. \\.venv\\Scripts\\python.exe scripts/v9_try_policy.py MAP-09`。",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT)
    print(json.dumps(totals, ensure_ascii=False))


if __name__ == "__main__":
    main()
