"""公开动作契约的类型渲染（Batch 8 接口修复，DCR-V10-24）。

问题：V10 MiMo runner 早期只把 ``SHAPES`` 的**字段名**写进 prompt（例如
``set_timetable: {operations,tick,tool}``），没有写字段**类型**。模型因此把
``operations``（应为 ``dict[str, dict]``）写成列表、把 ``claims``（应为 ``list[dict]``）
写成字典，导致结构合法的意图被 ``V8Action`` 判为 ``INVALID_ACTION_SCHEMA``——
这是接口假象，不是能力差异。

修复：从公开的 ``V8Action`` 模型注解渲染每个字段的类型形状（只暴露类型，不暴露
真值、最优动作或任何隐藏信息）。``SHAPES`` 仍是“哪些字段允许出现”的唯一来源。
"""

from __future__ import annotations

import types
from typing import Any, get_args, get_origin

from pydantic import BaseModel

from agent_arena.worlds.scenario_v8.models import V8Action

SCALARS = {str: "<str>", int: "<int>", bool: "<bool>", float: "<number>"}


def _scalar(annotation: Any) -> str | None:
    for python_type, label in SCALARS.items():
        if annotation is python_type:
            return label
    return None


def _model_shape(model: type[BaseModel], depth: int = 0) -> str:
    """把嵌套模型渲染成一行形状；只列公开字段名与类型，最多展开一层。"""

    if depth >= 1:
        return "{...}"
    parts = []
    for name, field in model.model_fields.items():
        parts.append(f'"{name}": {render_annotation(field.annotation, depth + 1)}')
    return "{" + ", ".join(parts) + "}"


def render_annotation(annotation: Any, depth: int = 0) -> str:
    """把一个公开字段注解渲染成紧凑的类型形状。"""

    if annotation is Any or annotation is None:
        return "<value>"
    scalar = _scalar(annotation)
    if scalar:
        return scalar
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (list, tuple):
        element = render_annotation(args[0] if args else Any, depth)
        return f"[{element}]"
    if origin is dict:
        key = render_annotation(args[0], depth) if args else "<key>"
        value = render_annotation(args[1], depth) if len(args) > 1 else "<value>"
        return "{" + f'"{_key_label(key)}": {value}' + "}"
    if origin is types.UnionType or str(origin) == "typing.Union":
        options = [item for item in args if item is not type(None)]
        rendered = " | ".join(render_annotation(item, depth) for item in options)
        return rendered or "<value>"
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _model_shape(annotation, depth)
    return "<value>"


def _key_label(rendered: str) -> str:
    """字典键的展示标签：标量键统一写成 ``<key>``，其余保留。"""

    return "<key>" if rendered in {"<str>", "<int>", "<number>", "<value>"} else rendered


def _bounds(field: Any) -> str:
    """把 pydantic 字段的 `ge`/`le` 约束渲染成区间（DCR-V10-28）。"""

    low = high = None
    for meta in getattr(field, "metadata", ()):  # Ge/Le/Gt/Lt 等约束对象
        if hasattr(meta, "ge"):
            low = meta.ge
        if hasattr(meta, "le"):
            high = meta.le
    if low is None and high is None:
        return ""
    return f"({'' if low is None else low}..{'' if high is None else high})"


def field_shape(name: str) -> str | None:
    field = V8Action.model_fields.get(name)
    if field is None:
        return None
    rendered = render_annotation(field.annotation)
    bounds = _bounds(field)
    return f"{rendered} {bounds}" if bounds else rendered


def action_contract(shapes: dict[str, set[frozenset[str]]]) -> str:
    """把 ``SHAPES`` 渲染成带类型的公开动作契约。"""

    lines = ["可用动作（严格 JSON；字段类型必须匹配；未列出的字段一律非法）："]
    for tool, variants in sorted(shapes.items()):
        rendered = []
        for shape in sorted(variants, key=sorted):
            parts = [f'"tool": "{tool}"']
            for name in sorted(shape - {"tool"}):
                parts.append(f'"{name}": {field_shape(name) or "<value>"}')
            rendered.append("{" + ", ".join(parts) + "}")
        lines.append(f"- {tool}: " + " | ".join(rendered))
    lines.append(
        "只输出一个 JSON 对象；对象/列表的形状必须与上面完全一致；不要输出解释。"
    )
    return "\n".join(lines)


def unknown_fields(shapes: dict[str, set[frozenset[str]]]) -> list[str]:
    """契约里出现但 ``V8Action`` 不认识的字段名（应为空；用于自检）。"""

    known = set(V8Action.model_fields)
    found: set[str] = set()
    for variants in shapes.values():
        for shape in variants:
            found |= {name for name in shape if name != "tool" and name not in known}
    return sorted(found)


__all__ = [
    "action_contract",
    "field_shape",
    "render_annotation",
    "unknown_fields",
]
