"""V12 公开契约补丁：消歧那些"形状可见、内部字段名不可见"的动作字段。

背景（DCR-V12-01，真实 54 局发现）：

V10 的公开动作契约由 ``v10/contract.py`` 从 ``V8Action`` 注解渲染。对
``facts: list[dict[str, Any]]`` 这类嵌套字典，渲染结果是
``[{"<key>": <value>}]``——它说明了"一个字典"，但**没有说明字典里必须有哪些字段**。
真实 MiMo 因此在 MAP-22 写出 ``[{"at_sign": "leaning_3"}, {"came_from": "pale_7"}]``，
被环境以 ``INVALID_MEMORY_PAYLOAD`` 拒绝：182 次 ``write_memory`` 中 175 次被拒（96%）。

这是接口假象（与 V10 的 DCR-V10-24/25/28 同类），不是能力差异。

处理原则：

- **不改 V10/V11**：冻结运行时、指标、历史 trace 与账本一律不动；
- 只在 V12 的 Lab 运行链路里，把**已经存在于公开规则中的**要求写清楚
  （MAP-22 的公开规则本来就写了"1–3 条 {key,value}"）；
- 补丁版本与命中的字段写进 ``provenance.contract_augmentation``，``prompt_hash``
  因此变化——**跨版本的局不配对**，必须另开实验。
"""

from __future__ import annotations

from typing import Any

CONTRACT_AUGMENTATION_VERSION = "v12-contract-2"

#: 字段名 → 需要补充的公开说明。只补"环境确实要求、但契约渲染无法表达"的字段。
FIELD_HINTS: dict[str, str] = {
    "facts": (
        'facts 的每一项必须是恰好两个字符串字段的对象：'
        '{"key": "<str>", "value": "<str>"}。'
        "使用其它字段名（例如 {\"at_sign\": \"...\"}）会被环境拒绝为 INVALID_MEMORY_PAYLOAD。"
    ),
}

#: 地图 → 额外公开说明。只写"帮助记忆被指标/环境正确读取"的约定，
#: 不含任何真值、最优路线或隐藏信息。
MAP_HINTS: dict[str, tuple[str, ...]] = {
    "MAP-22": (
        "若要让自己写下的路线可被读取，建议用 key=bearing（单个方位，按走过顺序各写一条）"
        "或 key=path_state（逗号分隔的方位序列，如 north,east,north）；"
        "其它键名也会保留在 agent_notes 里，但不会被自动当作路线。",
    ),
}


def _used_fields(environment: Any) -> set[str]:
    shapes = getattr(environment, "SHAPES", None) or {}
    used: set[str] = set()
    for variants in shapes.values():
        for shape in variants:
            used |= {str(name) for name in shape}
    return used


def augmentation_for(environment: Any) -> tuple[str, ...]:
    """返回该图需要的公开契约补丁（字段补丁 + 地图补丁，顺序稳定）。"""

    used = _used_fields(environment)
    map_id = str(getattr(environment, "map_id", ""))
    hints = [text for field, text in FIELD_HINTS.items() if field in used]
    hints.extend(MAP_HINTS.get(map_id, ()))
    return tuple(hints)


def augment_prompt(system: str, environment: Any) -> tuple[str, tuple[str, ...]]:
    """把补丁追加到 system prompt；返回 ``(prompt, hints)``。"""

    hints = augmentation_for(environment)
    if not hints:
        return system, ()
    body = "\n".join(f"注意：{hint}" for hint in hints)
    return f"{system}\n{body}", hints


def provenance_block(hints: tuple[str, ...]) -> dict[str, Any]:
    """写进结果文件的补丁指纹；没有补丁时 ``applied=False``。"""

    return {
        "version": CONTRACT_AUGMENTATION_VERSION,
        "applied": bool(hints),
        "hints": list(hints),
    }


__all__ = [
    "CONTRACT_AUGMENTATION_VERSION",
    "FIELD_HINTS",
    "MAP_HINTS",
    "augment_prompt",
    "augmentation_for",
    "provenance_block",
]
