"""V14 观测条件身份与公平性判定（P0-3）。

为什么需要这一层：

V12 的 ``condition_key = map|seed|agent`` 不含配置指纹，V13 的
``comparable_group_id`` 含预算但不含采样画像与契约版本。结果是：

- 两个**独立父实验**的 on/off 臂无法证明"只差一个开关"；
- 跨预算扩展（MAP-30 的 90→180 请求）会被当成同条件；
- 同条件重复被误当成新的环境样本。

本模块定义 **8 元组观测条件身份**，并显式区分三件事：

1. ``observation_condition_id``：完整条件身份（含预算与采样画像）。
2. ``replicate_index``：只是**同条件的观测序号**，不是新环境 seed。
3. ``seed``：只有 ``seed_space(map_id)`` 白名单里的值才算合法环境 seed。

口径原则（与 DCR-V14-01 一致）：历史 CSV 没有 ``contract_version`` /
``prompt_hash`` / ``sampling``，缺失一律 ``UNKNOWN``，**不得**当作"不一致"，
也不得当作"一致"——只能降级为 ``DESCRIPTIVE_ONLY`` 并写明原因。
"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.contracts import config_hash
from agent_arena.v10.runtime.catalog import MAP_IDS, seed_space

UNKNOWN = "UNKNOWN"

#: 判定结果。
VERDICT_COMPARABLE = "COMPARABLE"
VERDICT_DESCRIPTIVE = "DESCRIPTIVE_ONLY"
VERDICT_INCOMPARABLE = "INCOMPARABLE"

#: 硬不匹配原因代码。
MISMATCH_MAP = "MAP"
MISMATCH_SEED = "SEED"
MISMATCH_MODE = "MODE"
MISMATCH_MODEL = "MODEL"
MISMATCH_PROVIDER = "PROVIDER"
MISMATCH_RULE = "RULE"
MISMATCH_METRIC = "METRIC"
MISMATCH_CONTRACT = "CONTRACT"
MISMATCH_PROMPT = "PROMPT"
MISMATCH_BUDGET = "BUDGET"

#: 软不匹配（版本未登记等）：不拒绝，但结论降级为描述性。
SOFT_UNRECORDED = "UNRECORDED"
SOFT_SAMPLING = "SAMPLING"
SOFT_AGENT = "AGENT"
SOFT_RUNTIME = "RUNTIME"

#: 观测条件身份的 8 个字段（顺序即身份顺序，写进文档与报告）。
CONDITION_FIELDS: tuple[str, ...] = (
    "map_id",
    "environment_seed",
    "agent_id",
    "config_hash",
    "contract_version",
    "effective_prompt_version",
    "budget_profile",
    "sampling_profile",
)

# --------------------------------------------------------------- 画像派生
def budget_profile(record: dict[str, Any]) -> dict[str, Any]:
    """单局预算画像（请求 / token / 决策 / 费用四维）。

    未登记的一律 ``None``，指纹里写成 ``UNKNOWN``；这样"未登记"与
    "登记为 0"不会混在一起（0 请求上限在真实实验里没有意义，但仍是不同值）。
    """

    fields = {
        "request_cap": record.get("request_cap"),
        "input_token_cap": record.get("input_token_cap"),
        "decision_cap": record.get("decision_cap") or record.get("decision_budget"),
        "cost_cap_cny": record.get("cost_cap_cny") or record.get("per_run_cost_cap_cny"),
    }
    normalized: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None or value == "":
            normalized[key] = None
        elif key == "cost_cap_cny":
            normalized[key] = str(value)
        else:
            normalized[key] = int(value)
    fingerprint_payload = {
        key: (UNKNOWN if value is None else value) for key, value in normalized.items()
    }
    recorded = any(value is not None for value in normalized.values())
    return {
        **normalized,
        "fingerprint": config_hash(fingerprint_payload)[:12],
        "recorded": recorded,
        "display": "|".join(
            f"{key}={normalized[key] if normalized[key] is not None else 'UNKNOWN'}"
            for key in ("request_cap", "input_token_cap", "decision_cap", "cost_cap_cny")
        ),
    }

def sampling_profile(record: dict[str, Any]) -> dict[str, Any]:
    """模型采样画像。

    只有登记了 ``sampling``（``SamplingProvenance``）才算已知；历史 CSV 没有，
    因此 ``recorded=False`` 且 ``support=UNKNOWN``。**绝不**把未登记读成
    "temperature=0 / 可复现"。
    """

    raw = record.get("sampling")
    sampling: dict[str, Any] = raw if isinstance(raw, dict) else {}
    temperature = sampling.get("temperature")
    top_p = sampling.get("top_p")
    seed_requested = sampling.get("seed_requested")
    support = str(sampling.get("support") or UNKNOWN)
    recorded = bool(sampling)
    payload = {
        "temperature": UNKNOWN if temperature is None else temperature,
        "top_p": UNKNOWN if top_p is None else top_p,
        "seed_requested": UNKNOWN if seed_requested is None else seed_requested,
        "support": support,
    }
    return {
        **payload,
        "recorded": recorded,
        "deterministic_claim": (
            "SEED_ACCEPTED_BUT_OUTPUT_NOT_GUARANTEED"
            if support == "SUPPORTED" and seed_requested is not None
            else ("UNSUPPORTED" if support == "UNSUPPORTED" else UNKNOWN)
        ),
        "fingerprint": config_hash(payload)[:12],
        "display": (
            f"T={payload['temperature']}|top_p={payload['top_p']}|"
            f"seed={payload['seed_requested']}|support={support}"
        ),
    }

def _text(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value:
            return str(value)
    return UNKNOWN

def observation_condition(record: dict[str, Any]) -> dict[str, Any]:
    """8 元组观测条件身份（可序列化，含每维的来源与是否已登记）。"""

    budget = budget_profile(record)
    sampling = sampling_profile(record)
    values = {
        "map_id": str(record.get("map_id") or ""),
        "environment_seed": int(record.get("environment_seed") or 0),
        "agent_id": str(record.get("agent_id") or ""),
        "config_hash": _text(record, "agent_config_hash", "config_hash"),
        "contract_version": _text(
            record, "agent_contract_version", "action_contract_version", "contract_version"
        ),
        "effective_prompt_version": _text(
            record, "prompt_hash", "effective_prompt_hash", "prompt_version"
        ),
        "budget_profile": budget["fingerprint"],
        "sampling_profile": sampling["fingerprint"],
    }
    unrecorded = [
        key
        for key in (
            "config_hash",
            "contract_version",
            "effective_prompt_version",
        )
        if values[key] == UNKNOWN
    ]
    return {
        "condition_id": config_hash(values)[:16],
        "fields": values,
        "field_order": list(CONDITION_FIELDS),
        "budget": budget,
        "sampling": sampling,
        "replicate_index": int(record.get("replicate_index") or 0),
        "run_id": record.get("run_id"),
        "unrecorded_fields": unrecorded,
        "complete": not unrecorded,
        # 兼容 V12：``condition_key`` 只用于展示，不参与身份判定。
        "legacy_condition_key": (
            f"{values['map_id']}|seed={values['environment_seed']}|{values['agent_id']}"
        ),
    }

def observation_condition_id(record: dict[str, Any]) -> str:
    return str(observation_condition(record)["condition_id"])

# --------------------------------------------------------------- seed 白名单
def validate_seed(map_id: str, seed: int) -> dict[str, Any]:
    """环境 seed 必须在 ``seed_space(map_id)`` 里；绝不编造新 seed。"""

    if map_id not in MAP_IDS:
        return {
            "map_id": map_id,
            "seed": seed,
            "valid": False,
            "allowed": [],
            "reason": f"未注册的地图：{map_id}",
        }
    space = seed_space(map_id)
    valid = seed in space
    return {
        "map_id": map_id,
        "seed": seed,
        "valid": valid,
        "allowed": list(space),
        "reason": "" if valid else f"{map_id} 只登记了 seed：{list(space)}（收到 {seed}）",
    }

def seed_coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    """逐图统计"独立环境 seed"与"重复数"——两者不能相加。"""

    buckets: dict[str, dict[str, Any]] = {}
    illegal: list[dict[str, Any]] = []
    for record in records:
        map_id = str(record.get("map_id") or "")
        seed = int(record.get("environment_seed") or 0)
        check = validate_seed(map_id, seed)
        if not check["valid"]:
            illegal.append({"map_id": map_id, "seed": seed, "reason": check["reason"]})
        bucket = buckets.setdefault(
            map_id,
            {"map_id": map_id, "runs": 0, "seeds": set(), "replicates": {}, "conditions": set()},
        )
        bucket["runs"] += 1
        bucket["seeds"].add(seed)
        condition = observation_condition_id(record)
        bucket["conditions"].add(condition)
        bucket["replicates"].setdefault(condition, set()).add(
            int(record.get("replicate_index") or 0)
        )
    rows = []
    for bucket in sorted(buckets.values(), key=lambda item: item["map_id"]):
        replicates = [len(value) for value in bucket["replicates"].values()]
        rows.append(
            {
                "map_id": bucket["map_id"],
                "runs": bucket["runs"],
                "independent_seeds": sorted(bucket["seeds"]),
                "independent_seed_count": len(bucket["seeds"]),
                "condition_count": len(bucket["conditions"]),
                "max_replicates": max(replicates) if replicates else 0,
                "replicates_are_not_seeds": True,
            }
        )
    return {
        "maps": rows,
        "illegal_seeds": illegal,
        "note": (
            "``replicate_index`` 只是同一条件内的观测序号；"
            "独立环境样本数只能数 ``independent_seed_count``。"
        ),
    }

# ------------------------------------------------------------- 公平性判定
def _compare_dimension(
    name: str,
    left: Any,
    right: Any,
    *,
    hard_code: str,
) -> tuple[str, str] | None:
    """返回 ``(kind, message)``；``kind`` ∈ {``hard``, ``soft``}。"""

    if left == right:
        return None
    if left in (None, "", UNKNOWN) or right in (None, "", UNKNOWN):
        return (
            "soft",
            f"{name} 未登记（{left} vs {right}）：无法证明一致，结论降级为描述性。",
        )
    return ("hard", f"{name} 不一致（{left} vs {right}）。")


def condition_comparison(
    left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    """两条记录的观测条件比较：硬拒绝 / 描述性 / 可比。"""

    left_cond = observation_condition(left)
    right_cond = observation_condition(right)
    hard: list[dict[str, str]] = []
    soft: list[dict[str, str]] = []

    # 被测干预（允许不同，不得判为不可比）：
    #   - `agent_config_hash`：on/off 两臂的配置**本来**就不一样；
    #   - `prompt_hash`（effective）：记忆块/计划块会改变最终提示；
    #   - `base_prompt_hash` 才是"共享提示主体"，必须一致。
    # 这是 V14-02 的口径，与 V13 `comparability.MUST_MATCH_FIELDS` 一致。
    checks = (
        ("map_id", MISMATCH_MAP),
        ("environment_seed", MISMATCH_SEED),
        ("mode", MISMATCH_MODE),
        ("model", MISMATCH_MODEL),
        ("provider_id", MISMATCH_PROVIDER),
        ("rule_hash", MISMATCH_RULE),
        ("metric_hash", MISMATCH_METRIC),
        ("metric_schema_hash", MISMATCH_METRIC),
        ("agent_contract_version", MISMATCH_CONTRACT),
        ("base_prompt_hash", MISMATCH_PROMPT),
        ("request_cap", MISMATCH_BUDGET),
        ("input_token_cap", MISMATCH_BUDGET),
    )
    for key, code in checks:
        result = _compare_dimension(
            key, left.get(key), right.get(key), hard_code=code
        )
        if result is None:
            continue
        kind, message = result
        (hard if kind == "hard" else soft).append({"code": code, "detail": message})

    # 采样画像：只在两侧都登记时才能硬比较。
    left_sampling = left_cond["sampling"]
    right_sampling = right_cond["sampling"]
    if left_sampling["recorded"] and right_sampling["recorded"]:
        if left_sampling["fingerprint"] != right_sampling["fingerprint"]:
            hard.append(
                {
                    "code": SOFT_SAMPLING,
                    "detail": (
                        f"采样画像不同（{left_sampling['display']} vs "
                        f"{right_sampling['display']}）。"
                    ),
                }
            )
    else:
        soft.append(
            {
                "code": SOFT_SAMPLING,
                "detail": "采样参数未登记（历史 CSV 无 sampling 列）：不声称同采样。",
            }
        )

    # 单局预算：历史记录可能缺上限，缺就降级而不是当成相同。
    left_budget = left_cond["budget"]
    right_budget = right_cond["budget"]
    if left_budget["recorded"] and right_budget["recorded"]:
        if left_budget["fingerprint"] != right_budget["fingerprint"]:
            hard.append(
                {
                    "code": MISMATCH_BUDGET,
                    "detail": (
                        f"单局预算不同（{left_budget['display']} vs "
                        f"{right_budget['display']}）。"
                    ),
                }
            )
    else:
        soft.append(
            {
                "code": SOFT_UNRECORDED,
                "detail": "单局预算上限未登记：不能声称预算相同。",
            }
        )

    if left_cond["unrecorded_fields"] or right_cond["unrecorded_fields"]:
        soft.append(
            {
                "code": SOFT_UNRECORDED,
                "detail": "条件字段未登记："
                + str(
                    sorted(
                        set(left_cond["unrecorded_fields"])
                        | set(right_cond["unrecorded_fields"])
                    )
                )
                + "。",
            }
        )

    same_agent = left_cond["fields"]["agent_id"] == right_cond["fields"]["agent_id"]
    if not same_agent:
        soft.append(
            {
                "code": SOFT_AGENT,
                "detail": "策略不同：这是架构/版本比较，不是单开关消融。",
            }
        )
    elif (
        left.get("prompt_hash") != right.get("prompt_hash")
        and left.get("base_prompt_hash") == right.get("base_prompt_hash")
    ):
        # 共享提示主体相同、只有 effective prompt 不同：记忆/计划块带来的差异，
        # 属于被测干预的一部分，不是不可比。
        soft.append(
            {
                "code": "INTERVENTION",
                "detail": (
                    "effective prompt 不同但共享提示主体相同："
                    "这是被测机制（记忆/计划/反思文本）造成的差异。"
                ),
            }
        )
    elif left_cond["fields"]["config_hash"] != right_cond["fields"]["config_hash"]:
        # 同一策略、不同配置 = 被测干预（on/off 消融），不是不可比。
        soft.append(
            {
                "code": "INTERVENTION",
                "detail": (
                    "同一策略的实验臂配置不同（被操纵变量）："
                    f"{left_cond['fields']['config_hash'][:8]} vs "
                    f"{right_cond['fields']['config_hash'][:8]}；"
                    "效果可比较，但只能归因到该开关。"
                ),
            }
        )

    if hard:
        verdict = VERDICT_INCOMPARABLE
    elif soft:
        verdict = VERDICT_DESCRIPTIVE
    else:
        verdict = VERDICT_COMPARABLE
    return {
        "verdict": verdict,
        "hard_mismatches": hard,
        "soft_mismatches": soft,
        "left_condition_id": left_cond["condition_id"],
        "right_condition_id": right_cond["condition_id"],
        "same_condition": left_cond["condition_id"] == right_cond["condition_id"],
        "reason": (
            ""
            if verdict == VERDICT_COMPARABLE
            else "；".join(
                item["detail"] for item in (hard or soft)[:3]
            )
        ),
    }

def pair_key(record: dict[str, Any]) -> tuple[str, int, int]:
    """配对键：``(map, environment_seed, replicate_index)``。"""

    return (
        str(record.get("map_id") or ""),
        int(record.get("environment_seed") or 0),
        int(record.get("replicate_index") or 0),
    )

def build_pairs(
    left_records: list[dict[str, Any]],
    right_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按配对键配对，并逐对给出条件判定（不丢弃不可比的对）。"""

    index: dict[tuple[str, int, int], dict[str, Any]] = {}
    for record in left_records:
        index.setdefault(pair_key(record), record)
    right_index: dict[tuple[str, int, int], dict[str, Any]] = {}
    for record in right_records:
        right_index.setdefault(pair_key(record), record)
    pairs: list[dict[str, Any]] = []
    for key in sorted(set(index) & set(right_index)):
        left = index[key]
        right = right_index[key]
        comparison = condition_comparison(left, right)
        pairs.append(
            {
                "pair_key": f"{key[0]}|seed={key[1]}|rep={key[2]}",
                "map_id": key[0],
                "environment_seed": key[1],
                "replicate_index": key[2],
                "left_run_id": left.get("run_id"),
                "right_run_id": right.get("run_id"),
                "left_agent": left.get("agent_id"),
                "right_agent": right.get("agent_id"),
                "left_category": left.get("category"),
                "right_category": right.get("category"),
                "left_success": bool(left.get("success")),
                "right_success": bool(right.get("success")),
                "verdict": comparison["verdict"],
                "reason": comparison["reason"],
                "hard_mismatches": comparison["hard_mismatches"],
                "soft_mismatches": comparison["soft_mismatches"],
                "same_condition": comparison["same_condition"],
                "left_requests": left.get("requests"),
                "right_requests": right.get("requests"),
                "left_input_tokens": left.get("input_tokens"),
                "right_input_tokens": right.get("input_tokens"),
                "left_cost_cny": left.get("cost_cny"),
                "right_cost_cny": right.get("cost_cny"),
            }
        )
    return pairs

_VALID = {"completed_success", "mechanism_failure", "budget_censored"}

def _delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    try:
        return round(float(right) - float(left), 8)
    except (TypeError, ValueError):
        return None

def _direction(left_success: bool, right_success: bool) -> str:
    if left_success and right_success:
        return "BOTH_SUCCESS"
    if left_success:
        return "LEFT_ONLY"
    if right_success:
        return "RIGHT_ONLY"
    return "NEITHER"

def summarize_pairing(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """配对摘要：局数、有效分母、成功/失败/截尾、可比对、方向、资源差值。

    关键约束：

    - ``comparable_pairs`` 只数 ``COMPARABLE`` 的对；
    - ``descriptive_pairs`` 单独计数，**不得**与可比对相加当作效果证据；
    - 资源差值只在两侧都有数值时计算，缺一侧就 ``None``（不补 0）；
    - 方向按 seed 分块，明确"同一 seed 的多次重复不是新环境样本"。
    """

    buckets: dict[tuple[str, int], dict[str, Any]] = {}
    for pair in pairs:
        bucket_key = (pair["map_id"], pair["environment_seed"])
        bucket = buckets.setdefault(
            bucket_key,
            {
                "map_id": pair["map_id"],
                "environment_seed": pair["environment_seed"],
                "pairs": 0,
                "comparable": 0,
                "descriptive": 0,
                "incomparable": 0,
                "left_successes": 0,
                "right_successes": 0,
                "directions": [],
                "resource_pairs": 0,
                "request_deltas": [],
                "token_deltas": [],
                "cost_deltas": [],
            },
        )
        bucket["pairs"] += 1
        verdict = pair["verdict"]
        bucket[
            {
                VERDICT_COMPARABLE: "comparable",
                VERDICT_DESCRIPTIVE: "descriptive",
                VERDICT_INCOMPARABLE: "incomparable",
            }[verdict]
        ] += 1
        if verdict == VERDICT_COMPARABLE:
            bucket["left_successes"] += 1 if pair["left_success"] else 0
            bucket["right_successes"] += 1 if pair["right_success"] else 0
            bucket["directions"].append(
                _direction(pair["left_success"], pair["right_success"])
            )
        if verdict != VERDICT_INCOMPARABLE:
            # 资源消耗是**事实测量**，不是效果主张：只要预算口径没被判为不可比，
            # 就可以逐对报告差值；方向统计仍只取 COMPARABLE。
            bucket["resource_pairs"] += 1
            for field, target in (
                ("requests", "request_deltas"),
                ("input_tokens", "token_deltas"),
                ("cost_cny", "cost_deltas"),
            ):
                delta = _delta(pair.get(f"left_{field}"), pair.get(f"right_{field}"))
                if delta is not None:
                    bucket[target].append(delta)

    rows = []
    for bucket in (item[1] for item in sorted(buckets.items())):
        directions = bucket.pop("directions")
        row = {
            **bucket,
            "n_comparable_pairs": bucket["comparable"],
            "right_only": directions.count("RIGHT_ONLY"),
            "left_only": directions.count("LEFT_ONLY"),
            "both_success": directions.count("BOTH_SUCCESS"),
            "neither": directions.count("NEITHER"),
            "paired_difference": (
                round(directions.count("RIGHT_ONLY") / len(directions), 4)
                if directions
                else None
            ),
            "resource_delta_pairs": bucket["resource_pairs"],
            "requests_delta_mean": _mean(bucket["request_deltas"]),
            "input_tokens_delta_mean": _mean(bucket["token_deltas"]),
            "cost_cny_delta_mean": _mean(bucket["cost_deltas"]),
            "cost_cny_delta_total": (
                round(sum(bucket["cost_deltas"]), 8) if bucket["cost_deltas"] else None
            ),
        }
        for drop in ("request_deltas", "token_deltas", "cost_deltas"):
            row.pop(drop)
        rows.append(row)

    comparable = sum(1 for pair in pairs if pair["verdict"] == VERDICT_COMPARABLE)
    descriptive = sum(1 for pair in pairs if pair["verdict"] == VERDICT_DESCRIPTIVE)
    incomparable = sum(1 for pair in pairs if pair["verdict"] == VERDICT_INCOMPARABLE)
    left_valid = sum(
        1
        for pair in pairs
        if pair["left_category"] in _VALID
    )
    right_valid = sum(1 for pair in pairs if pair["right_category"] in _VALID)
    return {
        "pairs": len(pairs),
        "comparable_pairs": comparable,
        "descriptive_pairs": descriptive,
        "incomparable_pairs": incomparable,
        "left_completed_runs": len(pairs),
        "left_valid_runs": left_valid,
        "right_valid_runs": right_valid,
        "left_successes": sum(1 for pair in pairs if pair["left_success"]),
        "right_successes": sum(1 for pair in pairs if pair["right_success"]),
        "left_censored": sum(
            1 for pair in pairs if pair["left_category"] == "budget_censored"
        ),
        "right_censored": sum(
            1 for pair in pairs if pair["right_category"] == "budget_censored"
        ),
        "left_mechanism_failures": sum(
            1 for pair in pairs if pair["left_category"] == "mechanism_failure"
        ),
        "right_mechanism_failures": sum(
            1 for pair in pairs if pair["right_category"] == "mechanism_failure"
        ),
        "by_seed": rows,
        "evidence_level": (
            VERDICT_DESCRIPTIVE
            if comparable < 3 or descriptive or incomparable
            else "PAIRED_SUMMARY"
        ),
        "note": (
            "只有 COMPARABLE 的对进入方向统计；DESCRIPTIVE_ONLY 与 INCOMPARABLE "
            "单独计数且不得当作效果证据。同一 seed 的重复观测不是新的环境样本，"
            "不能据此宣称跨环境泛化。"
        ),
    }

# ------------------------------------------------- V12 消融臂的配对复核
#: V12 单因子消融的 on/off 两臂（来源文件名 → 被测开关）。
#: 文件名的 ``on``/``off`` 是 V12 的**登记**，不是数据字段；V14 只读取、不改写。
ABLATION_PAIRS: tuple[dict[str, str], ...] = (
    {
        "label": "memory.v1 消融",
        "off": "ablation-memory-off-runs.csv",
        "on": "ablation-memory-on-runs.csv",
        "switch": "memory",
    },
    {
        "label": "planning.v1 消融",
        "off": "ablation-planning-off-runs.csv",
        "on": "ablation-planning-on-runs.csv",
        "switch": "planning",
    },
    {
        "label": "reflection.v1 消融",
        "off": "ablation-reflection-off-runs.csv",
        "on": "ablation-reflection-on-runs.csv",
        "switch": "reflection",
    },
)

def ablation_pairing_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """把 V12 三组消融臂按 8 维条件身份重新配对并审计。

    这是 P0-3 的核心证据：证明"两个独立父实验的 on/off 臂"能被正确配对，
    同时**不会**因为 ``replicate_index`` 或 config hash 丢配对，
    也不会把跨预算/跨契约的对当成可比。
    """

    by_file: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_file.setdefault(str(record.get("source_file") or ""), []).append(record)
    reports = []
    for spec in ABLATION_PAIRS:
        left = by_file.get(spec["off"], [])
        right = by_file.get(spec["on"], [])
        if not left or not right:
            reports.append(
                {
                    "label": spec["label"],
                    "switch": spec["switch"],
                    "available": False,
                    "reason": "缺少 on/off 臂的历史文件。",
                }
            )
            continue
        pairs = build_pairs(left, right)
        summary = summarize_pairing(pairs)
        preconditions = descriptive_only_preconditions(pairs)
        config_hashes = {
            "off": sorted({str(item.get("agent_config_hash") or UNKNOWN) for item in left}),
            "on": sorted({str(item.get("agent_config_hash") or UNKNOWN) for item in right}),
        }
        reports.append(
            {
                "label": spec["label"],
                "switch": spec["switch"],
                "available": True,
                "off_file": spec["off"],
                "on_file": spec["on"],
                "off_config_hashes": config_hashes["off"],
                "on_config_hashes": config_hashes["on"],
                "single_switch_by_config": (
                    len(config_hashes["off"]) == 1
                    and len(config_hashes["on"]) == 1
                    and config_hashes["off"] != config_hashes["on"]
                ),
                "pairs": summary["pairs"],
                "comparable_pairs": summary["comparable_pairs"],
                "descriptive_pairs": summary["descriptive_pairs"],
                "incomparable_pairs": summary["incomparable_pairs"],
                "by_seed": summary["by_seed"],
                "preconditions": preconditions,
                "note": summary["note"],
            }
        )
    return {
        "schema": "v14-ablation-pairing-1",
        "reports": reports,
        "note": (
            "on/off 的区分来自 V12 实验登记文件名；历史 CSV 没有 contract_version 与 "
            "prompt_hash，因此所有配对一律降级为 DESCRIPTIVE_ONLY（DCR-V14-01）。"
        ),
    }

def _dash(value: Any) -> str:
    return "—" if value is None else str(value)

def ablation_pairing_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# V14 消融臂配对复核（P0-3）",
        "",
        "> 数据来源：`docs/v12/real-runs/ablation-*.csv`（只读）。零外部请求。",
        "",
        "## 1. 逐组结果",
        "",
        "| 消融 | 配对 | 可比 | 描述性 | 不可比 | 单开关（按 config hash） |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in report.get("reports") or []:
        if not item.get("available"):
            lines.append(f"| {item['label']} | — | — | — | — | 缺失：{item['reason']} |")
            continue
        lines.append(
            f"| {item['label']} | {item['pairs']} | {item['comparable_pairs']} | "
            f"{item['descriptive_pairs']} | {item['incomparable_pairs']} | "
            f"{'是' if item['single_switch_by_config'] else '否'} |"
        )
    lines += ["", "## 2. 逐 seed 明细", ""]
    for item in report.get("reports") or []:
        if not item.get("available"):
            continue
        lines.append(f"### {item['label']}（`{item['switch']}`）")
        lines.append("")
        lines.append(
            f"- off `agent_config_hash`：{', '.join(item['off_config_hashes'])}"
        )
        lines.append(f"- on `agent_config_hash`：{', '.join(item['on_config_hashes'])}")
        lines.append("")
        lines.append(
            "| seed | 配对 | 可比 | 右胜 | 左胜 | 双成功 | 双失败 "
            "| 请求差值均值 | token 差值均值 | 费用差值均值 CNY |"
        )
        lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in item["by_seed"]:
            lines.append(
                f"| {row['environment_seed']} | {row['pairs']} | {row['comparable']} | "
                f"{row['right_only']} | {row['left_only']} | {row['both_success']} | "
                f"{row['neither']} | {_dash(row['requests_delta_mean'])} | "
                f"{_dash(row['input_tokens_delta_mean'])} | "
                f"{_dash(row['cost_cny_delta_mean'])} |"
            )
        reasons = item["preconditions"]["reasons"]
        lines.append("")
        lines.append(
            f"- 资源差值可比对：{item['by_seed'][0]['resource_delta_pairs']} 对"
            "（资源差值是事实测量，不构成效果证据）"
            if item["by_seed"]
            else "- 无逐 seed 行"
        )
        lines.append(
            "- 只能描述性的原因："
            + ("；".join(reasons) if reasons else "无（可比对与 seed 覆盖达标）")
        )
        lines.append("")
    lines += [f"> {report.get('note')}", ""]
    return "\n".join(lines)

def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)

def descriptive_only_preconditions(
    pairs: list[dict[str, Any]], *, min_pairs: int = 3
) -> dict[str, Any]:
    """说明"为什么只能描述性"以及区间的前提条件。"""

    reasons: list[str] = []
    summary = summarize_pairing(pairs)
    if summary["comparable_pairs"] < min_pairs:
        reasons.append(
            f"可比对仅 {summary['comparable_pairs']} 对（< {min_pairs}）：样本不足以谈稳定性。"
        )
    if summary["descriptive_pairs"]:
        reasons.append(
            f"{summary['descriptive_pairs']} 对因版本/采样/预算未登记而降级为描述性。"
        )
    if summary["incomparable_pairs"]:
        reasons.append(
            f"{summary['incomparable_pairs']} 对硬不匹配（不可比），已从效果统计中排除。"
        )
    seeds = {(pair["map_id"], pair["environment_seed"]) for pair in pairs}
    if len(seeds) < 3:
        reasons.append(
            f"独立环境 seed 只有 {len(seeds)} 个：任何区间只描述这些 seed，"
            "不代表地图整体或其它 seed。"
        )
    return {
        "descriptive_only": bool(reasons),
        "reasons": reasons,
        "sampling_unit": "environment_seed（同 seed 的重复观测不是独立样本）",
        "interval_precondition": (
            "若要给区间，必须说明：抽样单位是环境 seed，区间只覆盖已观测 seed；"
            "重复次数只反映模型采样波动，不扩大 seed 覆盖。"
        ),
        "independent_seed_count": len(seeds),
    }

__all__ = [
    "ABLATION_PAIRS",
    "CONDITION_FIELDS",
    "MISMATCH_BUDGET",
    "MISMATCH_CONTRACT",
    "MISMATCH_PROMPT",
    "SOFT_SAMPLING",
    "SOFT_UNRECORDED",
    "UNKNOWN",
    "VERDICT_COMPARABLE",
    "VERDICT_DESCRIPTIVE",
    "VERDICT_INCOMPARABLE",
    "ablation_pairing_markdown",
    "ablation_pairing_report",
    "budget_profile",
    "build_pairs",
    "condition_comparison",
    "descriptive_only_preconditions",
    "observation_condition",
    "observation_condition_id",
    "pair_key",
    "sampling_profile",
    "seed_coverage",
    "summarize_pairing",
    "validate_seed",
]
