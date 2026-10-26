"""V12 研究投影指标：在不覆盖 V10 冻结指标的前提下补齐口径。

为什么需要独立命名空间：

- `map22.v10.route_recall` **只能**读 ``key ∈ {bearing, path_state}``，而 MAP-22 的公开
  规则只要求 ``{key, value}`` 随意键值对（DCR-V12-02）。真实模型因此写出
  ``{"key": "path_to_here", "value": "pale_7->south->leaning_3"}``——语义正确、指标读不到。
- 直接改 V10 的指标会覆盖历史值、破坏 ``metric_hash`` 与跨版本可比性。

所以 V12 新增 ``v12.projection.route_recall``：

- **只读公开数据**：最终 Observation 的 ``agent_notes`` + trace 里**被接受**的 ``move`` 方位；
- **键名宽容**：接受 ``bearing`` / ``path_state``，也接受任何值里能解析出方位序列的条目；
- **口径显式**：结果带 ``rule_version``、``source_keys``、``note``，并在报告里与 V10 指标
  并列展示、明确标注"研究投影，不是 V10 官方值"；
- **不改**：V10 指标、环境、账本、历史 trace。

``route_recall`` 的定义（与 V10 语义一致）：写入的方位序列与真实走过的方位序列
逐位匹配的比例。分母是真实路线长度。
"""

from __future__ import annotations

from typing import Any

PROJECTION_NAMESPACE = "v12.projection"
PROJECTION_VERSION = "v12-projection-1"
ROUTE_RECALL_ID = f"{PROJECTION_NAMESPACE}.route_recall"

BEARINGS: tuple[str, ...] = ("north", "east", "south", "west")
_ALIASES: dict[str, str] = {
    "n": "north",
    "e": "east",
    "s": "south",
    "w": "west",
    "北": "north",
    "东": "east",
    "南": "south",
    "西": "west",
}
_KEY_HINTS: tuple[str, ...] = ("bearing", "path", "route", "visited", "trail", "返回", "路线")


def _tokens(value: str) -> list[str]:
    """把一段文本里的方位按出现顺序解析出来（容忍 ``->``、逗号、空格分隔）。"""

    found: list[str] = []
    buffer = ""
    for character in value:
        if character.isalpha() or "\u4e00" <= character <= "\u9fff":
            buffer += character.lower()
        else:
            if buffer:
                found.append(buffer)
                buffer = ""
    if buffer:
        found.append(buffer)
    bearings: list[str] = []
    for token in found:
        if token in BEARINGS:
            bearings.append(token)
        elif token in _ALIASES:
            bearings.append(_ALIASES[token])
    return bearings


def _candidate_sequences(notes: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    """从公开 notes 里收集候选方位序列（键名宽容，但只看公开字段）。

    两类候选都要保留：

    - **逐条值**：`path_state` 这类"每次写整段序列"的用法；
    - **按键拼接**：`bearing` 这类"一条一个方位"的用法（与 V10 口径一致）。
    """

    singles: list[tuple[str, list[str]]] = []
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        key = str(note.get("key") or "")
        value = note.get("value")
        if not isinstance(value, str):
            continue
        bearings = _tokens(value)
        if not bearings:
            continue
        key_lower = key.lower()
        if not (
            key in {"bearing", "path_state"}
            or any(hint in key_lower for hint in _KEY_HINTS)
        ):
            continue
        singles.append((key, bearings))
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].extend(bearings)
    candidates = list(singles)
    candidates.extend((key, grouped[key]) for key in order)
    return candidates


def project_route_recall(
    *, notes: list[dict[str, Any]], route: list[str]
) -> dict[str, Any]:
    """计算 V12 投影版 route_recall（只读公开 notes 与公开 move 方位）。"""

    if not route:
        return {
            "metric_id": ROUTE_RECALL_ID,
            "state": "NOT_APPLICABLE",
            "value": None,
            "numerator": None,
            "denominator": 0,
            "source_keys": [],
            "rule_version": PROJECTION_VERSION,
            "note": "本局没有成功的 move，无法构成真实路线。",
        }
    candidates = _candidate_sequences(notes)
    if not candidates:
        return {
            "metric_id": ROUTE_RECALL_ID,
            "state": "NOT_APPLICABLE",
            "value": None,
            "numerator": None,
            "denominator": len(route),
            "source_keys": [],
            "rule_version": PROJECTION_VERSION,
            "note": "公开记忆里没有可解析的方位序列（与 V10 口径一致：未记录 → N/A）。",
        }
    # 取与真实路线匹配位最多的那条候选，避免"最后写过一条无关记忆"把结果压低。
    best_key = ""
    best_matched = -1
    best_values: list[str] = []
    for key, bearings in candidates:
        matched = sum(
            1
            for index, bearing in enumerate(bearings)
            if index < len(route) and route[index] == bearing
        )
        if matched > best_matched:
            best_matched = matched
            best_key = key
            best_values = bearings
    ratio = round(best_matched / len(route), 6)
    return {
        "metric_id": ROUTE_RECALL_ID,
        "state": "VALID",
        "value": ratio,
        "numerator": best_matched,
        "denominator": len(route),
        "source_keys": sorted({key for key, _ in candidates}),
        "matched_key": best_key,
        "written_length": len(best_values),
        "rule_version": PROJECTION_VERSION,
        "note": (
            "V12 研究投影：键名宽容（不限于 bearing/path_state），"
            "分母为真实 move 数；不是 V10 官方值。"
        ),
    }


def project_metrics(
    map_id: str, *, notes: list[dict[str, Any]], route: list[str]
) -> dict[str, Any]:
    """当前只对 MAP-22 提供投影；其它图返回空字典。"""

    if map_id != "MAP-22":
        return {}
    return {ROUTE_RECALL_ID: project_route_recall(notes=notes, route=route)}


def summarize_projection(projections: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for metric_id, payload in sorted(projections.items()):
        out[metric_id] = {
            "state": payload.get("state"),
            "value": payload.get("value"),
            "numerator": payload.get("numerator"),
            "denominator": payload.get("denominator"),
            "rule_version": payload.get("rule_version"),
            "note": payload.get("note"),
        }
    return out


__all__ = [
    "BEARINGS",
    "PROJECTION_NAMESPACE",
    "PROJECTION_VERSION",
    "ROUTE_RECALL_ID",
    "project_metrics",
    "project_route_recall",
    "summarize_projection",
]
