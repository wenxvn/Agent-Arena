"""可比较性画像与配对判定（P0-5 / V13-01-01 … 01-07）。

三件事必须分开：

1. **画像**（``comparability_profile``）：把一局的可比性维度摊平成固定字段，
   写入 provenance 摘要。缺字段一律 ``UNKNOWN``，不假装已知。
2. **单变量检查**（``single_switch_check``）：两个实验臂的配置差异必须恰好是
   一个开关；多开关同时变化时**拒绝**做因果比较（可以并列展示，不能说"因为 X"）。
3. **配对判定**（``pairability``）：硬不匹配（地图/规则/指标/模型/模式/契约）
   → ``INCOMPARABLE``；只有版本不同 → ``DESCRIPTIVE_ONLY``；只有被测干预不同
   → ``COMPARABLE``。

关键设计：**不要求**被测干预的 ``prompt_hash`` 相同——记忆/计划文本本身是被测变量，
要求它们相同等于禁止实验。但共享提示主体（``base_prompt_hash``）、动作契约、
预算、历史窗口、地图与 seed 必须一致。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from agent_arena.lab.contracts import ComparisonPolicy, config_hash

UNKNOWN = "UNKNOWN"

VERDICT_COMPARABLE = "COMPARABLE"
VERDICT_DESCRIPTIVE = "DESCRIPTIVE_ONLY"
VERDICT_INCOMPARABLE = "INCOMPARABLE"
VERDICT_NO_TREATMENT = "NO_TREATMENT_EXPOSURE"

#: 必须逐项一致的字段（环境与测量口径）。
MUST_MATCH_FIELDS: tuple[str, ...] = (
    "map_id",
    "environment_seed",
    "mode",
    "provider_id",
    "model",
    "rule_hash",
    "metric_hash",
    "metric_schema_hash",
    "action_contract_version",
    "base_prompt_hash",
    "history_window",
    "decision_cap",
    "request_cap",
    "input_token_cap",
)

#: 允许不同、但会让结论降级为描述性的字段。
SOFT_FIELDS: tuple[str, ...] = (
    "agent_id",
    "agent_version",
    "agent_config_hash",
    "runtime_version",
    "sampling_support",
)

#: 属于"被测干预"的字段：允许不同，且不构成不可比。
INTERVENTION_FIELDS: tuple[str, ...] = (
    "effective_prompt_hash",
    "agent_config_hash",
)


def _hash(value: Any) -> str:
    return config_hash(value) if not isinstance(value, str) else value


def comparability_profile(record: dict[str, Any]) -> dict[str, Any]:
    """从一条 run record 提取可比性画像（只读、可序列化）。"""

    sampling_raw = record.get("sampling")
    sampling: dict[str, Any] = sampling_raw if isinstance(sampling_raw, dict) else {}
    profile = {
        "map_id": str(record.get("map_id") or ""),
        "environment_seed": int(record.get("environment_seed") or 0),
        "mode": str(record.get("mode") or ""),
        "provider_id": str(record.get("provider_id") or ""),
        "model": str(record.get("model") or ""),
        "model_revision": str(record.get("model_revision") or UNKNOWN),
        "rule_hash": str(record.get("rule_hash") or ""),
        "metric_hash": str(record.get("metric_hash") or ""),
        "metric_schema_hash": str(record.get("metric_schema_hash") or ""),
        "scenario_hash": str(record.get("scenario_hash") or UNKNOWN),
        "action_contract_version": str(
            record.get("agent_contract_version")
            or record.get("action_contract_version")
            or UNKNOWN
        ),
        "base_prompt_hash": str(
            record.get("base_prompt_hash") or record.get("prompt_hash") or ""
        ),
        "effective_prompt_hash": str(record.get("prompt_hash") or ""),
        "history_window": int(record.get("history_window") or 0) or UNKNOWN,
        "decision_cap": int(record.get("decision_cap") or record.get("decision_budget") or 0),
        "request_cap": int(record.get("request_cap") or 0),
        "input_token_cap": int(record.get("input_token_cap") or 0),
        "agent_id": str(record.get("agent_id") or ""),
        "agent_version": str(record.get("agent_version") or ""),
        "agent_config_hash": str(record.get("agent_config_hash") or ""),
        "runtime_version": str(record.get("runtime_version") or UNKNOWN),
        "sampling_support": str(sampling.get("support") or UNKNOWN),
        "replicate_index": int(record.get("replicate_index") or 0),
    }
    return profile


def comparable_group_id(profile: dict[str, Any]) -> str:
    """同条件组 ID：只取"必须一致"的维度，不含被测干预。

    用途：把跨实验、跨版本的历史观测归到同一个 ``comparable_group_id``，
    报告里可以显式声明"这些观测属于同一条件组 / 不属于"。
    """

    payload = {
        key: profile.get(key)
        for key in (
            "map_id",
            "environment_seed",
            "mode",
            "provider_id",
            "model",
            "rule_hash",
            "metric_hash",
            "metric_schema_hash",
            "action_contract_version",
            "base_prompt_hash",
            "history_window",
            "decision_cap",
            "request_cap",
            "input_token_cap",
        )
    }
    return _hash(payload)[:16]


def compare_profiles(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    policy: ComparisonPolicy | None = None,
) -> dict[str, Any]:
    """逐维比较两个画像，给出判定、原因与被操纵变量。"""

    policy = policy or ComparisonPolicy()
    hard: list[str] = []
    soft: list[str] = []
    manipulated: list[str] = []
    for name in MUST_MATCH_FIELDS:
        a, b = left.get(name), right.get(name)
        if a == b:
            continue
        # 0 / UNKNOWN 视为"未登记"，不算硬不匹配，但降级为描述性。
        if a in (0, "", None, UNKNOWN) or b in (0, "", None, UNKNOWN):
            soft.append(f"{name} 未登记或缺失（{a} vs {b}）")
        else:
            hard.append(f"{name} 不一致（{a} vs {b}）")
    for name in SOFT_FIELDS:
        a, b = left.get(name), right.get(name)
        if a != b:
            if name in {"agent_id", "agent_config_hash"}:
                manipulated.append(name)
            else:
                soft.append(f"{name} 不同（{a} vs {b}）")

    if hard:
        verdict = VERDICT_INCOMPARABLE
    elif soft:
        verdict = VERDICT_DESCRIPTIVE
    else:
        verdict = VERDICT_COMPARABLE
    if policy.require_same_versions is False and verdict == VERDICT_COMPARABLE:
        verdict = VERDICT_DESCRIPTIVE
        soft.append("比较策略要求宽松版本匹配：只作描述性对照")
    return {
        "verdict": verdict,
        "reasons": [*hard, *soft],
        "hard_mismatches": hard,
        "soft_mismatches": soft,
        "manipulated_variables": manipulated,
        "comparable_group_left": comparable_group_id(left),
        "comparable_group_right": comparable_group_id(right),
        "same_condition_group": comparable_group_id(left) == comparable_group_id(right),
    }


# ------------------------------------------------------------ single variable
@dataclass(frozen=True)
class SwitchCheck:
    """两个实验臂之间"是否只改了一个开关"。"""

    ok: bool
    manipulated_variable: str = ""
    changed_keys: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    kind: str = "single_switch"

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "manipulated_variable": self.manipulated_variable,
            "changed_keys": list(self.changed_keys),
            "reasons": list(self.reasons),
            "kind": self.kind,
        }


def single_switch_check(
    left: dict[str, Any], right: dict[str, Any]
) -> SwitchCheck:
    """检查两个 ``AgentArm`` 配置是否只差一个开关。

    - 同一 ``agent_id`` + 恰好一个配置键不同 → 单因子消融，可比；
    - 同一 ``agent_id`` + 多个配置键不同 → 拒绝（不能归因到单个开关）；
    - 不同 ``agent_id`` → **版本/架构比较**，不是消融（``kind="version_compare"``）。
    """

    left_agent = str(left.get("agent_id") or "")
    right_agent = str(right.get("agent_id") or "")
    left_config = dict(left.get("config") or {})
    right_config = dict(right.get("config") or {})
    keys = sorted(set(left_config) | set(right_config))
    changed = tuple(key for key in keys if left_config.get(key) != right_config.get(key))
    if left_agent != right_agent:
        return SwitchCheck(
            ok=False,
            changed_keys=changed,
            reasons=(
                f"agent_id 不同（{left_agent} vs {right_agent}）：这是版本/架构比较，"
                "不是单开关消融，不能宣称某个开关的因果效果。",
            ),
            kind="version_compare",
        )
    if not changed:
        return SwitchCheck(
            ok=False,
            changed_keys=(),
            reasons=("两个实验臂配置完全相同：没有可识别的干预变量。",),
            kind="no_intervention",
        )
    if len(changed) > 1:
        return SwitchCheck(
            ok=False,
            changed_keys=changed,
            reasons=(
                "同时改了 " + "、".join(changed) + " 多个开关；"
                "这不能归因到单个机制，只能作为「组合方案」描述。",
            ),
            kind="multi_switch",
        )
    return SwitchCheck(
        ok=True, manipulated_variable=changed[0], changed_keys=changed
    )


# ------------------------------------------------------- cross-experiment pairs
@dataclass
class CrossPair:
    pairing_key: str
    map_id: str
    environment_seed: int
    replicate_index: int
    left: dict[str, Any]
    right: dict[str, Any]
    verdict: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    switch: SwitchCheck | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "pairing_key": self.pairing_key,
            "map_id": self.map_id,
            "environment_seed": self.environment_seed,
            "replicate_index": self.replicate_index,
            "left_run_id": self.left.get("run_id"),
            "right_run_id": self.right.get("run_id"),
            "left_agent": self.left.get("agent_id"),
            "right_agent": self.right.get("agent_id"),
            "left_experiment": self.left.get("experiment_id"),
            "right_experiment": self.right.get("experiment_id"),
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "left_success": bool(self.left.get("success")),
            "right_success": bool(self.right.get("success")),
            "left_category": self.left.get("category"),
            "right_category": self.right.get("category"),
            "left_decisions": self.left.get("decisions"),
            "right_decisions": self.right.get("decisions"),
            "left_cost_cny": self.left.get("cost_cny"),
            "right_cost_cny": self.right.get("cost_cny"),
            "switch": None if self.switch is None else self.switch.as_dict(),
        }
        return payload


def _index(
    records: Iterable[dict[str, Any]], agent_id: str
) -> dict[tuple[str, int, int], dict[str, Any]]:
    index: dict[tuple[str, int, int], dict[str, Any]] = {}
    for record in records:
        if str(record.get("agent_id")) != agent_id:
            continue
        key = (
            str(record.get("map_id")),
            int(record.get("environment_seed") or 0),
            int(record.get("replicate_index") or 0),
        )
        index.setdefault(key, record)
    return index


def cross_experiment_pairs(
    left_records: Iterable[dict[str, Any]],
    right_records: Iterable[dict[str, Any]],
    *,
    left_agent: str,
    right_agent: str,
    left_arm: dict[str, Any] | None = None,
    right_arm: dict[str, Any] | None = None,
    policy: ComparisonPolicy | None = None,
    allow_replicate_mismatch: bool = False,
) -> list[CrossPair]:
    """在两个**独立父实验**之间按 ``(map, seed, replicate_index)`` 配对。

    与 V12 ``pair_records`` 的差别：

    - 允许 ``agent_id`` 相同、``config`` 不同的 on/off 对照（V12 的
      ``condition_key = map|seed|agent`` 不含 config hash，做不到）；
    - 重复编号必须对齐（第 0 次对第 0 次），否则配对只标描述性；
    - 任何硬不匹配一律 ``INCOMPARABLE``，并保留原因供 UI 显示。
    """

    policy = policy or ComparisonPolicy()
    left_index = _index(left_records, left_agent)
    right_index = _index(right_records, right_agent)
    switch = (
        single_switch_check(left_arm, right_arm)
        if left_arm is not None and right_arm is not None
        else None
    )
    pairs: list[CrossPair] = []
    for key in sorted(set(left_index) & set(right_index)):
        left = left_index[key]
        right = right_index[key]
        verdict = compare_profiles(
            comparability_profile(left), comparability_profile(right), policy=policy
        )
        reasons = list(verdict["reasons"])
        if verdict["hard_mismatches"]:
            state = VERDICT_INCOMPARABLE
        elif switch is not None and not switch.ok and switch.kind == "multi_switch":
            state = VERDICT_INCOMPARABLE
            reasons.append("；".join(switch.reasons))
        elif verdict["soft_mismatches"]:
            state = VERDICT_DESCRIPTIVE
        else:
            state = VERDICT_COMPARABLE
        pairs.append(
            CrossPair(
                pairing_key=f"{key[0]}|seed={key[1]}|rep={key[2]}",
                map_id=key[0],
                environment_seed=key[1],
                replicate_index=key[2],
                left=left,
                right=right,
                verdict=state,
                reasons=tuple(reasons),
                switch=switch,
            )
        )
    del allow_replicate_mismatch
    return pairs


def summarize_pairs(pairs: list[CrossPair]) -> dict[str, Any]:
    """配对摘要：逐 seed 明细 + 只按 seed 分块的配对差值。"""

    by_seed: dict[tuple[str, int], dict[str, Any]] = {}
    for pair in pairs:
        key = (pair.map_id, pair.environment_seed)
        bucket = by_seed.setdefault(
            key,
            {
                "map_id": pair.map_id,
                "environment_seed": pair.environment_seed,
                "pairs": 0,
                "comparable": 0,
                "left_successes": 0,
                "right_successes": 0,
                "replicate_deltas": [],
            },
        )
        bucket["pairs"] += 1
        if pair.verdict == VERDICT_COMPARABLE:
            bucket["comparable"] += 1
            bucket["left_successes"] += 1 if pair.left.get("success") else 0
            bucket["right_successes"] += 1 if pair.right.get("success") else 0
            bucket["replicate_deltas"].append(
                int(bool(pair.right.get("success"))) - int(bool(pair.left.get("success")))
            )
    rows = []
    for bucket in (item[1] for item in sorted(by_seed.items())):
        deltas = bucket["replicate_deltas"]
        rows.append(
            {
                **{key: value for key, value in bucket.items() if key != "replicate_deltas"},
                "paired_difference": (
                    round(sum(deltas) / len(deltas), 4) if deltas else None
                ),
                "n_comparable_pairs": len(deltas),
            }
        )
    return {
        "pairs": len(pairs),
        "comparable": sum(1 for pair in pairs if pair.verdict == VERDICT_COMPARABLE),
        "descriptive": sum(1 for pair in pairs if pair.verdict == VERDICT_DESCRIPTIVE),
        "incomparable": sum(1 for pair in pairs if pair.verdict == VERDICT_INCOMPARABLE),
        "by_seed": rows,
        "note": (
            "配对以 (map, seed) 为块、replicate_index 对齐；配对差值只是描述性，"
            "同一 seed 的多次重复不构成新的环境样本。"
        ),
    }


def refusal_message(verdict: dict[str, Any]) -> str:
    """给用户看的不可比原因（UI 与报告共用同一措辞）。"""

    if verdict.get("verdict") != VERDICT_INCOMPARABLE:
        return ""
    reasons = verdict.get("hard_mismatches") or verdict.get("reasons") or []
    return "不可做因果比较：" + "；".join(str(item) for item in reasons[:4])


__all__ = [
    "INTERVENTION_FIELDS",
    "MUST_MATCH_FIELDS",
    "SOFT_FIELDS",
    "UNKNOWN",
    "VERDICT_COMPARABLE",
    "VERDICT_DESCRIPTIVE",
    "VERDICT_INCOMPARABLE",
    "VERDICT_NO_TREATMENT",
    "CrossPair",
    "SwitchCheck",
    "comparable_group_id",
    "comparability_profile",
    "compare_profiles",
    "cross_experiment_pairs",
    "refusal_message",
    "single_switch_check",
    "summarize_pairs",
]
