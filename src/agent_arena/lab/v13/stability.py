"""重复稳定性：同条件多次运行之间的结局一致性（P0-1 / V13-02-04）。

口径（必须逐条显式，否则数字会被误读）：

1. **分组键** = ``(map_id, environment_seed, agent_id)``。重复是"同一环境 seed 上的
   独立重采样"，**不是**新的环境 seed，因此不能把 3 次重复当成 3 个样本去谈地图泛化。
2. **可比性**：只有同 ``agent_config_hash``（同策略配置）、同 ``agent_version``、
   同单局预算、同 ``prompt_hash``（若有）的观测才计入翻转率；否则标
   ``跨版本`` / ``跨预算`` 并**排除**。这是 DCR-V12-06 的直接后果。
3. **翻转** = 同一分组内 ``category``（完成且成功 / 机制失败 / 预算截尾 / …）
   出现过两种及以上取值。
4. 观测数 < 3 一律 ``DESCRIPTIVE_ONLY``；二项置信区间只作描述，前提写在输出里。
5. 缺失、截尾、Provider 错误**不补零**：``censored`` 与 ``invalid`` 单独计数。
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_arena.lab.compare import (
    CATEGORY_LABELS,
    VALID_DENOMINATOR_CATEGORIES,
)

EVIDENCE_DESCRIPTIVE = "DESCRIPTIVE_ONLY"
EVIDENCE_STABLE = "REPEATED_CONSISTENT"
EVIDENCE_UNSTABLE = "REPEATED_FLIPPED"
EVIDENCE_SINGLE = "SINGLE_OBSERVATION"

MISMATCH_VERSION = "跨版本"
MISMATCH_BUDGET = "跨预算"
MISMATCH_MODEL = "跨模型"
MISMATCH_MODE = "跨模式"

#: 默认最小观测数：低于它只做描述。
DEFAULT_MIN_OBS = 3


@dataclass
class ConditionGroup:
    """一个 ``(map, seed, agent)`` 分组的全部观测。"""

    key: str
    map_id: str
    environment_seed: int
    agent_id: str
    observations: list[dict[str, Any]] = field(default_factory=list)

    # ---------------------------------------------------------------- derived
    @property
    def n(self) -> int:
        return len(self.observations)

    @property
    def categories(self) -> list[str]:
        return [str(item.get("category") or "") for item in self.observations]

    @property
    def successes(self) -> int:
        return sum(1 for item in self.observations if item.get("success"))

    @property
    def censored(self) -> int:
        return sum(
            1 for item in self.observations if item.get("category") == "budget_censored"
        )

    @property
    def invalid(self) -> int:
        return sum(
            1
            for item in self.observations
            if str(item.get("category") or "")
            in {"invalid_run", "provider_error", "cancelled", "interrupted"}
        )

    @property
    def valid_observations(self) -> int:
        return sum(
            1
            for item in self.observations
            if str(item.get("category") or "") in VALID_DENOMINATOR_CATEGORIES
        )

    @property
    def flips(self) -> bool:
        return len(set(self.categories)) > 1

    @property
    def mismatch_labels(self) -> list[str]:
        labels: list[str] = []
        if len({str(item.get("agent_config_hash") or "") for item in self.observations}) > 1:
            labels.append(MISMATCH_VERSION)
        elif len({str(item.get("agent_version") or "") for item in self.observations}) > 1:
            labels.append(MISMATCH_VERSION)
        prompts = {
            str(item.get("prompt_hash") or "")
            for item in self.observations
            if item.get("prompt_hash")
        }
        if len(prompts) > 1 and MISMATCH_VERSION not in labels:
            labels.append(MISMATCH_VERSION)
        budgets = {
            (
                int(item.get("request_cap") or 0),
                int(item.get("input_token_cap") or 0),
            )
            for item in self.observations
            if item.get("request_cap") is not None
        }
        if len(budgets) > 1:
            labels.append(MISMATCH_BUDGET)
        if len({str(item.get("model") or "") for item in self.observations}) > 1:
            labels.append(MISMATCH_MODEL)
        if len({str(item.get("mode") or "") for item in self.observations}) > 1:
            labels.append(MISMATCH_MODE)
        return labels

    @property
    def comparable(self) -> bool:
        return not self.mismatch_labels

    @property
    def evidence_label(self) -> str:
        if not self.comparable:
            return "NOT_COMPARABLE"
        if self.n <= 1:
            return EVIDENCE_SINGLE
        if self.flips:
            return EVIDENCE_UNSTABLE
        if self.n < DEFAULT_MIN_OBS:
            return EVIDENCE_DESCRIPTIVE
        return EVIDENCE_STABLE

    @property
    def cost_range(self) -> tuple[float | None, float | None]:
        values = [
            float(item["cost_cny"])
            for item in self.observations
            if item.get("cost_known") and item.get("cost_cny") is not None
        ]
        if not values:
            return None, None
        return min(values), max(values)

    @property
    def decision_range(self) -> tuple[int | None, int | None]:
        values = [
            int(item["decisions"])
            for item in self.observations
            if item.get("decisions") is not None
        ]
        if not values:
            return None, None
        return min(values), max(values)

    @property
    def cost_unknown(self) -> bool:
        return any(not item.get("cost_known") for item in self.observations)

    def as_dict(self) -> dict[str, Any]:
        low, high = self.cost_range
        dlow, dhigh = self.decision_range
        return {
            "group_key": self.key,
            "map_id": self.map_id,
            "environment_seed": self.environment_seed,
            "agent_id": self.agent_id,
            "observations": self.n,
            "valid_observations": self.valid_observations,
            "successes": self.successes,
            "censored": self.censored,
            "invalid": self.invalid,
            "categories": self.categories,
            "flipped": self.flips,
            "comparable": self.comparable,
            "mismatch": self.mismatch_labels,
            "evidence": self.evidence_label,
            "cost_min_cny": low,
            "cost_max_cny": high,
            "cost_unknown": self.cost_unknown,
            "decisions_min": dlow,
            "decisions_max": dhigh,
            "run_ids": [str(item.get("run_id")) for item in self.observations],
            "replicate_indexes": [
                int(item.get("replicate_index") or 0) for item in self.observations
            ],
        }


def group_records(records: list[dict[str, Any]]) -> dict[str, ConditionGroup]:
    """按 ``(map, seed, agent)`` 分组；组内保持观测顺序（按重复编号）。"""

    groups: dict[str, ConditionGroup] = {}
    for record in records:
        map_id = str(record.get("map_id") or "")
        seed = int(record.get("environment_seed") or 0)
        agent = str(record.get("agent_id") or "")
        key = f"{map_id}|seed={seed}|{agent}"
        group = groups.setdefault(
            key,
            ConditionGroup(
                key=key, map_id=map_id, environment_seed=seed, agent_id=agent
            ),
        )
        group.observations.append(record)
    for group in groups.values():
        group.observations.sort(
            key=lambda item: int(item.get("replicate_index") or 0)
        )
    return groups


def wilson_interval(successes: int, n: int, *, z: float = 1.96) -> tuple[float, float]:
    """Wilson 二项区间（**描述性**；不构成显著性检验）。"""

    if n <= 0:
        return (0.0, 1.0)
    phat = successes / n
    denominator = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denominator
    margin = (
        z
        * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
        / denominator
    )
    return (max(0.0, round(centre - margin, 4)), min(1.0, round(centre + margin, 4)))


def replicate_variability(
    records: list[dict[str, Any]],
    *,
    min_obs: int = 2,
    source: str = "HISTORICAL",
) -> dict[str, Any]:
    """整体重复稳定性报告（不含任何排名）。"""

    groups = group_records(records)
    rows = [group.as_dict() for group in groups.values()]
    comparable = [
        group
        for group in groups.values()
        if group.comparable and group.n >= min_obs
    ]
    flipped = [group for group in comparable if group.flips]
    flip_rate = round(len(flipped) / len(comparable), 4) if comparable else None
    excluded = [group for group in groups.values() if not group.comparable]

    # 只有同条件、同版本、同预算的组才进入翻转率；这是 DCR-V12-06 的硬要求。
    per_map: dict[str, dict[str, Any]] = {}
    for group in comparable:
        bucket = per_map.setdefault(
            group.map_id, {"comparable_groups": 0, "flipped_groups": 0, "observations": 0}
        )
        bucket["comparable_groups"] += 1
        bucket["flipped_groups"] += 1 if group.flips else 0
        bucket["observations"] += group.n
    for bucket in per_map.values():
        bucket["flip_rate"] = (
            round(bucket["flipped_groups"] / bucket["comparable_groups"], 4)
            if bucket["comparable_groups"]
            else None
        )

    stable_conditions = [
        group.key
        for group in comparable
        if not group.flips and group.n >= DEFAULT_MIN_OBS and group.successes == group.n
    ]
    return {
        "schema": "v13-repeat-variability-1",
        "source": source,
        "records": len(records),
        "groups": len(groups),
        "comparable_groups": len(comparable),
        "groups_with_flip": len(flipped),
        "flip_rate": flip_rate,
        "excluded_not_comparable": len(excluded),
        "excluded_keys": [group.key for group in excluded],
        "per_map": dict(sorted(per_map.items())),
        "always_success_conditions": stable_conditions,
        "observations_per_group": sorted({group.n for group in groups.values()}),
        "min_obs": min_obs,
        "rows": sorted(rows, key=lambda item: item["group_key"]),
        "units": {
            "group": "(map_id, environment_seed, agent_id)",
            "observation": "一次独立重采样（replicate_index 递增）",
            "warning": (
                "重复次数 ≠ 环境 seed 数：同一 seed 的 3 次重复只说明抽样波动，"
                "不能当作 3 张地图实例的泛化证据。"
            ),
        },
    }


def flip_interval(report: dict[str, Any]) -> dict[str, Any]:
    """翻转率的 Wilson 区间 + 使用前提（只作描述）。"""

    groups = report.get("comparable_groups") or 0
    flips = report.get("groups_with_flip") or 0
    low, high = wilson_interval(flips, groups)
    return {
        "n_groups": groups,
        "flips": flips,
        "point": report.get("flip_rate"),
        "wilson_95": [low, high],
        "premise": (
            "Wilson 区间假设每组「是否翻转」近似独立二项；组之间共享同一模型与提示，"
            "因此区间偏窄，仅作描述性参考，不作显著性断言。"
        ),
    }


def seed_blocks(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 ``(map, seed)`` 分块展示各实验臂：seed 是块，重复不是新块。"""

    blocks: dict[tuple[str, int], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("map_id")), int(record.get("environment_seed") or 0))
        block = blocks.setdefault(
            key,
            {
                "map_id": key[0],
                "environment_seed": key[1],
                "arms": {},
            },
        )
        agent = str(record.get("agent_id"))
        bucket = block["arms"].setdefault(
            agent,
            {"agent_id": agent, "observations": 0, "successes": 0, "categories": []},
        )
        bucket["observations"] += 1
        bucket["successes"] += 1 if record.get("success") else 0
        bucket["categories"].append(str(record.get("category") or ""))
    output: list[dict[str, Any]] = []
    for (map_id, seed), block in sorted(blocks.items()):
        output.append(
            {
                "map_id": map_id,
                "environment_seed": seed,
                "arms": [
                    {**bucket, "categories": list(bucket["categories"])}
                    for _, bucket in sorted(block["arms"].items())
                ],
            }
        )
    return output


# --------------------------------------------------------------------- exports
VARIABILITY_FIELDS = (
    "group_key",
    "map_id",
    "environment_seed",
    "agent_id",
    "observations",
    "valid_observations",
    "successes",
    "censored",
    "invalid",
    "flipped",
    "comparable",
    "mismatch",
    "evidence",
    "cost_min_cny",
    "cost_max_cny",
    "cost_unknown",
    "decisions_min",
    "decisions_max",
    "run_ids",
)


def variability_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in report.get("rows") or []:
        item = dict(row)
        item["mismatch"] = "／".join(row.get("mismatch") or [])
        item["run_ids"] = ",".join(row.get("run_ids") or [])
        rows.append(item)
    return rows


def csv_bytes(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key) for key in fields})
    return buffer.getvalue().encode("utf-8-sig")


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def variability_markdown(
    report: dict[str, Any], *, title: str = "重复稳定性"
) -> str:
    """人可读的 Markdown：先口径，再数字，再限制。"""

    interval = flip_interval(report)
    lines = [
        f"# {title}",
        "",
        f"- 数据来源：`{report.get('source')}`（不是本次新跑的真实模型结果）",
        f"- 记录数：{report.get('records')}；条件分组：{report.get('groups')}",
        f"- 可比分组（观测 ≥ {report.get('min_obs')}）：{report.get('comparable_groups')}",
        f"- 出现结局翻转的分组：{report.get('groups_with_flip')}",
        f"- 翻转率：**{_fmt(report.get('flip_rate'))}**"
        f"（Wilson 95% 描述区间 {interval['wilson_95'][0]}–{interval['wilson_95'][1]}）",
        f"- 因版本/预算/模型/模式不一致被排除的分组："
        f"{report.get('excluded_not_comparable')}",
        "",
        "## 统计单位（先读这一节）",
        "",
        "- 分组 = `(map_id, environment_seed, agent_id)`；一次观测 = 一次独立重采样。",
        "- **重复不是新的环境 seed**：同一 seed 的 3 次重复只说明抽样波动，",
        "  不能当作 3 张地图实例，也不能据此声称地图泛化能力。",
        "- 只有同 `agent_config_hash` / 同 `agent_version` / 同预算的观测计入翻转率；",
        "  其余标 `跨版本` / `跨预算` 并排除（DCR-V12-06）。",
        "- 观测数 < 3 一律 `DESCRIPTIVE_ONLY`；翻转率不是显著性结论。",
        "",
        "## 逐条件明细",
        "",
        "| 条件 | 次数 | 有效 | 成功 | 截尾 | 结局序列 | 可比 | 证据 | 费用区间 CNY |",
        "|---|---:|---:|---:|---:|---|---|---|---|",
    ]
    for row in report.get("rows") or []:
        sequence = " → ".join(
            CATEGORY_LABELS.get(item, item) for item in row.get("categories") or []
        )
        mismatch = "／".join(row.get("mismatch") or []) or "是"
        cost = (
            "—"
            if row.get("cost_min_cny") is None
            else f"{row['cost_min_cny']:.6f}–{row['cost_max_cny']:.6f}"
        )
        if row.get("cost_unknown"):
            cost += "（含未知）"
        lines.append(
            f"| `{row['group_key']}` | {row['observations']} | {row['valid_observations']} | "
            f"{row['successes']} | {row['censored']} | {sequence} | {mismatch} | "
            f"`{row['evidence']}` | {cost} |"
        )
    lines += [
        "",
        "## 逐图翻转率",
        "",
        "| 地图 | 可比分组 | 翻转分组 | 翻转率 | 观测数 |",
        "|---|---:|---:|---:|---:|",
    ]
    for map_id, bucket in (report.get("per_map") or {}).items():
        lines.append(
            f"| {map_id} | {bucket['comparable_groups']} | {bucket['flipped_groups']} | "
            f"{_fmt(bucket.get('flip_rate'))} | {bucket['observations']} |"
        )
    if report.get("always_success_conditions"):
        lines += [
            "",
            "## 稳定成功条件（≥3 次全成功）",
            "",
            *[f"- `{key}`" for key in report["always_success_conditions"]],
        ]
    lines += [
        "",
        "## 限制",
        "",
        f"- {interval['premise']}",
        "- 历史观测来自 V12 的不同衍生实验；跨实验拼接只按同条件同版本进行。",
        "- 未观测到的翻转不代表不会发生；观测到的翻转也不等于机制差异。",
        "",
    ]
    return "\n".join(lines)


def write_variability(
    report: dict[str, Any], directory: Path, *, stem: str = "repeat_variability"
) -> dict[str, Path]:
    """写出 ``repeat_variability.csv/json/md``（不覆盖历史文件）。"""

    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    csv_path = directory / f"{stem}.csv"
    csv_path.write_bytes(csv_bytes(variability_rows(report), VARIABILITY_FIELDS))
    written[csv_path.name] = csv_path
    import json

    json_path = directory / f"{stem}.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    written[json_path.name] = json_path
    md_path = directory / f"{stem}.md"
    md_path.write_text(
        variability_markdown(report), encoding="utf-8", newline="\n"
    )
    written[md_path.name] = md_path
    return written


__all__ = [
    "DEFAULT_MIN_OBS",
    "EVIDENCE_DESCRIPTIVE",
    "EVIDENCE_SINGLE",
    "EVIDENCE_STABLE",
    "EVIDENCE_UNSTABLE",
    "MISMATCH_BUDGET",
    "MISMATCH_MODE",
    "MISMATCH_MODEL",
    "MISMATCH_VERSION",
    "VARIABILITY_FIELDS",
    "ConditionGroup",
    "csv_bytes",
    "flip_interval",
    "group_records",
    "replicate_variability",
    "seed_blocks",
    "variability_markdown",
    "variability_rows",
    "wilson_interval",
    "write_variability",
]
