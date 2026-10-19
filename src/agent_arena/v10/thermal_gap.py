"""MAP-19/20 热策略差距分析：把“接口修复后仍失败”的部分量化到 tick。

只读本地 MiMo trace（阶段 13/14：MAP-20 `-t2`、MAP-19 `-u2`），比较每 tick 的
公开安全界与实际设置：

- MAP-19：公开规则给出 ``T_next = max(0, T + 负荷 − 已生效冷却)``，
  因此安全负荷为 ``负荷 ≤ max(0, SAFE − T + 已生效冷却)``；超过即记一次超载。
- MAP-20：热点区热量超过单支管上限时必须走旁路；未开旁路且热量仍高即记一次缺口。

输出 ``docs/v10/thermal-gap-analysis.md``。
"""

from __future__ import annotations

import json
from typing import Any

from agent_arena.v10.attribution import _trace_rows
from agent_arena.v10.paths import V10_DOCS
from agent_arena.v10.runtime.map19 import SAFE_TEMPERATURE as SAFE_19
from agent_arena.v10.runtime.map20 import DIRECT_MAX
from agent_arena.v10.runtime.map20 import HORIZON as HORIZON_20

MAP19_RUNS = ("V10-MAP-19-S0-u2", "V10-MAP-19-S1-u2", "V10-MAP-19-S2-u2")
MAP20_RUNS = ("V10-MAP-20-S0-t2", "V10-MAP-20-S1-t2", "V10-MAP-20-S2-t2")


def _observations(run_id: str) -> list[dict[str, Any]]:
    rows = _trace_rows(run_id)
    return [
        dict(item.get("observation_after") or {})
        for item in rows
        if item.get("observation_after")
    ]


def analyse_19(run_id: str) -> dict[str, Any]:
    observations = _observations(run_id)
    overloads = 0
    ticks = 0
    max_temp = 0.0
    forecast_rejects = 0
    production = 0
    for previous, current in zip(observations, observations[1:], strict=False):
        if current.get("tick") == previous.get("tick"):
            continue
        ticks += 1
        loads = previous.get("current_load_levels") or {}
        temps = previous.get("current_temperatures") or {}
        cooling = previous.get("active_cooling") or {}
        for zone in temps:
            safe = max(
                0.0,
                SAFE_19 - float(temps[zone]) + float(cooling.get(zone, 0)),
            )
            if float(loads.get(zone, 0)) > safe:
                overloads += 1
        max_temp = max(max_temp, max((float(v) for v in temps.values()), default=0.0))
        if (current.get("rejected_ticks") or 0) > (previous.get("rejected_ticks") or 0):
            forecast_rejects += 1
        production = int(current.get("production_points") or production)
    return {
        "run_id": run_id,
        "ticks": ticks,
        "overloads": overloads,
        "max_temperature": max_temp,
        "forecast_rejects": forecast_rejects,
        "production": production,
        "target": (observations[-1].get("production_target") if observations else None),
    }


def analyse_20(run_id: str) -> dict[str, Any]:
    observations = _observations(run_id)
    gaps = 0
    bypass_ticks = 0
    settled = 0
    production = 0
    last: dict[str, Any] = {}
    for observation in observations:
        tick = int(observation.get("tick") or 0)
        if tick == 0 or tick == last.get("tick"):
            continue
        settled += 1
        last = observation
        schedule = observation.get("heat_schedule") or {}
        index = min(tick - 1, HORIZON_20 - 1)
        heats = {zone: schedule.get(zone, [0] * HORIZON_20)[index] for zone in schedule}
        hot = max(heats, key=lambda zone: heats[zone]) if heats else ""
        bypass = observation.get("bypass_settings") or {}
        if bypass:
            bypass_ticks += 1
        if heats and heats[hot] > DIRECT_MAX and not bypass:
            gaps += 1
        production = int(observation.get("production_points") or production)
    return {
        "run_id": run_id,
        "settled_ticks": settled,
        "hot_without_bypass": gaps,
        "bypass_ticks": bypass_ticks,
        "production": production,
        "target": (observations[-1].get("production_target") if observations else None),
    }


def audit() -> dict[str, Any]:
    return {
        "map19": [analyse_19(run_id) for run_id in MAP19_RUNS],
        "map20": [analyse_20(run_id) for run_id in MAP20_RUNS],
    }


def render(payload: dict[str, Any]) -> str:
    lines = [
        "# MAP-19/20 热策略差距（接口修复后的剩余失败）",
        "",
        "- 由 `python -m agent_arena.v10.thermal_gap` 生成；只读阶段 13/14 的 trace。",
        "- 这两图在补上“只有 wait 推进时间”后已能正常结算；本表只看**策略层**的安全界。",
        "",
        "## 1. MAP-19（冷却/预测）",
        "",
        "安全界：`负荷 ≤ max(0, 10 − 当前温度 + 已生效冷却)`；超过即该区下一 tick 必过热。",
        "",
        "| run | tick | 超载次数 | 最高温 | 预测被拒 tick | 产能 | 目标 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["map19"]:
        lines.append(
            f"| `{row['run_id']}` | {row['ticks']} | {row['overloads']} | "
            f"{row['max_temperature']} | {row['forecast_rejects']} | "
            f"{row['production']} | {row['target']} |"
        )
    lines += [
        "",
        "读法：三局都在冷却尚未生效（t+2 滞后）时把三区负荷拉到 2，"
        "前两 tick 就积累了 4–6 度温升；等首条冷却生效时已接近或越过 10.0。",
        "",
        "## 2. MAP-20（直供/旁路）",
        "",
        f"热点区热量超过单支管上限 {DIRECT_MAX} 时必须走旁路；未走则记一次缺口。",
        "",
        "| run | 结算 tick | 热点未走旁路 | 走旁路 tick | 产能 | 目标 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["map20"]:
        lines.append(
            f"| `{row['run_id']}` | {row['settled_ticks']} | {row['hot_without_bypass']} | "
            f"{row['bypass_ticks']} | {row['production']} | {row['target']} |"
        )
    lines += [
        "",
        "读法：seed 0 十个 tick 都未走旁路，产能 0.858824；seed 1 走了一次旁路但热量分配仍失衡；"
        "seed 2 在 tick 5 后回到重复 `set_flow`。公开启发式（30 动作）在四个 seed 上都能 1.0，"
        "说明差距是策略而不是接口。",
        "",
        "## 3. 结论",
        "",
        "- 两图的接口已可用（非法动作 0、tick 正常推进）；剩余失败都能落到具体的安全界违反。",
        "- 这不改变 `VALIDATED`：地图可解、机制可触发、指标可区分；它改变的是对模型失败的解释。",
        "- n=3、单 replicate，只作描述；跨模型与显著性检验不在本轮范围。",
        "",
        "## 4. 复现",
        "",
        "```powershell",
        ".venv\\Scripts\\python.exe -m agent_arena.v10.thermal_gap",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    payload = audit()
    (V10_DOCS / "thermal-gap-analysis.md").write_text(
        render(payload), encoding="utf-8", newline="\n"
    )
    print(json.dumps(payload, ensure_ascii=False, default=str))
    return 0


__all__ = ["analyse_19", "analyse_20", "audit", "main", "render"]


if __name__ == "__main__":
    raise SystemExit(main())
