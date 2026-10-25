"""可访问性审计：主题对比度 + DOM 结构规则（纯函数，可离线单测）。

两层：

1. **主题层**（`audit_theme_tokens`）：用 WCAG 相对亮度公式核对设计系统里
   作为文字/图标使用的颜色在浅色与深色背景上的对比度；
2. **DOM 层**（`audit_dom`）：对浏览器采集的元素快照做规则检查
   （可交互元素必须有可访问名、页面必须有一级标题、图片必须有替代文本等）。

两层都不依赖 Streamlit；`scripts/a11y_v12.py` 负责采集快照并调用这里。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

#: WCAG 2.1 AA：正文 4.5:1，大字号（≥18.66px 粗体或 ≥24px）3:1。
AA_TEXT = 4.5
AA_LARGE = 3.0
#: 非文字对比（边框、图形）3:1。
AA_UI = 3.0

#: 设计系统里被当作**文字/图标**使用的前景色（与 ``ui/theme.py`` 的
#: ``--aa-*-text`` 一一对应；深色模式由 ``prefers-color-scheme`` 覆盖）。
TEXT_TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "accent": "#3b5bdb",
        "accent-2": "#6341d9",
        "success": "#0a7a3d",
        "warning": "#8a5200",
        "danger": "#c22a2f",
        "info": "#1a63c9",
        "neutral": "#5f6b7d",
    },
    "dark": {
        "accent": "#8ea2ff",
        "accent-2": "#b39cff",
        "success": "#3ddc97",
        "warning": "#f5b544",
        "danger": "#ff8b8f",
        "info": "#6aa9ff",
        "neutral": "#a9b3c6",
    },
}

#: 填充/边框色（只需 3:1）。
BASE_TOKENS: dict[str, str] = {
    "accent": "#4c6ef5",
    "accent-2": "#7c5cff",
    "success": "#12a150",
    "warning": "#d08218",
    "danger": "#e5484d",
    "info": "#2f80ed",
    "neutral": "#8b95a8",
}

#: Streamlit 的浅色/深色主背景与正文色（取渲染后的实际值）。
BACKGROUNDS: dict[str, tuple[str, str]] = {
    "light": ("#ffffff", "#31333f"),
    "dark": ("#0e1117", "#fafafa"),
}

INTERACTIVE_ROLES = frozenset(
    {"button", "link", "checkbox", "radio", "tab", "textbox", "combobox", "switch", "slider"}
)


def _srgb_to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _parse_hex(value: str) -> tuple[float, float, float]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    if len(text) != 6:
        raise ValueError(f"不是 6 位十六进制颜色：{value}")
    return tuple(int(text[index : index + 2], 16) / 255 for index in (0, 2, 4))  # type: ignore[return-value]


def relative_luminance(color: str) -> float:
    """WCAG 2.1 相对亮度。"""

    red, green, blue = _parse_hex(color)
    return (
        0.2126 * _srgb_to_linear(red)
        + 0.7152 * _srgb_to_linear(green)
        + 0.0722 * _srgb_to_linear(blue)
    )


def contrast_ratio(foreground: str, background: str) -> float:
    """两种颜色的对比度（1–21）。"""

    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return round((lighter + 0.05) / (darker + 0.05), 2)


@dataclass(frozen=True)
class A11yIssue:
    rule: str
    severity: str  # critical / serious / moderate / minor
    target: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "target": self.target,
            "detail": self.detail,
        }


def audit_theme_tokens() -> dict[str, Any]:
    """核对主题文字色与填充色的对比度。

    文字色（``--aa-*-text``）按 WCAG AA 正文 4.5:1 要求；填充/边框色只需 3:1。
    """

    rows: list[dict[str, Any]] = []
    for scheme, (background, body) in BACKGROUNDS.items():
        rows.append(
            {
                "scheme": scheme,
                "token": "body-text",
                "kind": "text",
                "foreground": body,
                "background": background,
                "ratio": contrast_ratio(body, background),
                "required": AA_TEXT,
                "pass": contrast_ratio(body, background) >= AA_TEXT,
            }
        )
        for name, color in TEXT_TOKENS[scheme].items():
            ratio = contrast_ratio(color, background)
            rows.append(
                {
                    "scheme": scheme,
                    "token": f"{name}-text",
                    "kind": "text",
                    "foreground": color,
                    "background": background,
                    "ratio": ratio,
                    "required": AA_TEXT,
                    "pass": ratio >= AA_TEXT,
                }
            )
        for name, color in BASE_TOKENS.items():
            ratio = contrast_ratio(color, background)
            rows.append(
                {
                    "scheme": scheme,
                    "token": name,
                    "kind": "ui",
                    "foreground": color,
                    "background": background,
                    "ratio": ratio,
                    "required": AA_UI,
                    "pass": ratio >= AA_UI,
                }
            )
    failures = [row for row in rows if not row["pass"]]
    text_failures = [row for row in failures if row["kind"] == "text"]
    ui_failures = [row for row in failures if row["kind"] == "ui"]
    return {
        "rows": rows,
        "failures": failures,
        "text_failures": text_failures,
        "ui_failures": ui_failures,
        "checked": len(rows),
        "ok": not text_failures,
        # 填充色只作装饰时 3:1 不足可接受，但仍单独暴露。
        "ui_ok": not ui_failures,
    }


def audit_dom(elements: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """DOM 快照规则检查。

    ``elements`` 每项形如::

        {"role": "button", "name": "打开 Lab", "visible": true,
         "tabindex": 0, "tag": "button", "src": null, "aria_hidden": false,
         "heading_level": null}
    """

    issues: list[A11yIssue] = []
    items = [dict(item) for item in elements]
    heading_levels: list[int] = []
    unnamed: list[str] = []

    for item in items:
        role = str(item.get("role") or "")
        tag = str(item.get("tag") or "")
        name = str(item.get("name") or "").strip()
        visible = bool(item.get("visible", True))
        aria_hidden = bool(item.get("aria_hidden"))
        if aria_hidden or not visible:
            continue
        level = item.get("heading_level")
        if isinstance(level, int) and level > 0:
            heading_levels.append(level)
        if role in INTERACTIVE_ROLES or tag in {"button", "input", "select", "textarea", "a"}:
            if not name:
                unnamed.append(f"{role or tag}#{item.get('index', '?')}")
        if tag == "img" and not item.get("alt") and not aria_hidden:
            issues.append(
                A11yIssue(
                    rule="image-alt",
                    severity="serious",
                    target=str(item.get("src") or "img"),
                    detail="图片缺少 alt 文本或 aria-hidden",
                )
            )

    if not heading_levels:
        issues.append(
            A11yIssue(
                rule="page-has-heading-one",
                severity="serious",
                target="document",
                detail="页面没有一级标题（h1）",
            )
        )
    elif 1 not in heading_levels:
        issues.append(
            A11yIssue(
                rule="page-has-heading-one",
                severity="moderate",
                target="document",
                detail=f"没有 h1；出现的标题级别为 {sorted(set(heading_levels))}",
            )
        )
    else:
        previous = 1
        for level in heading_levels:
            if level > previous + 1:
                issues.append(
                    A11yIssue(
                        rule="heading-order",
                        severity="moderate",
                        target="document",
                        detail=f"标题层级跳跃：h{previous} → h{level}",
                    )
                )
                break
            previous = level

    for target in unnamed:
        issues.append(
            A11yIssue(
                rule="control-has-name",
                severity="critical",
                target=target,
                detail="可交互元素没有可访问名称（屏幕阅读器无法朗读）",
            )
        )

    if not items:
        issues.append(
            A11yIssue(
                rule="document-not-empty",
                severity="critical",
                target="document",
                detail="采集到的 DOM 快照为空，审计结果不可用",
            )
        )

    return {
        "elements": len(items),
        "interactive": sum(
            1
            for item in items
            if str(item.get("role") or "") in INTERACTIVE_ROLES
            or str(item.get("tag") or "") in {"button", "input", "select", "textarea", "a"}
        ),
        "issues": [issue.as_dict() for issue in issues],
        "critical": sum(1 for issue in issues if issue.severity == "critical"),
        "serious": sum(1 for issue in issues if issue.severity == "serious"),
        "ok": not issues,
    }


def keyboard_report(focus_order: list[dict[str, Any]]) -> dict[str, Any]:
    """键盘可达性：焦点必须前进、必须可见、不能落到隐藏元素。

    ``body`` / ``html`` 表示"还没有进入可聚焦元素"，是正常的初始状态，
    不计为违规；只统计真正获得焦点的元素。
    """

    issues: list[A11yIssue] = []
    reachable = [
        item
        for item in focus_order
        if str(item.get("tag") or "") not in {"body", "html", ""}
    ]
    if not reachable:
        issues.append(
            A11yIssue(
                rule="keyboard-focusable",
                severity="critical",
                target="document",
                detail="按 Tab 后没有任何元素获得焦点",
            )
        )
    seen: set[str] = set()
    previous: str | None = None
    #: 网格/画布类控件（Streamlit dataframe 的 canvas）在方向键导航时会保持焦点，
    #: 这是表格的预期行为而不是键盘陷阱（Tab/Esc 仍可离开）。
    focus_holding_tags = {"canvas"}
    for item in reachable:
        # 用元素标识而不是"标签+文本"判断重复：同名锚点链接是不同元素。
        signature = str(item.get("id") or f"{item.get('tag')}:{item.get('name')}")
        tag = str(item.get("tag") or "")
        if signature == previous and tag not in focus_holding_tags:
            # 真正的键盘陷阱：焦点**连续**停在同一元素上（没有前进）。
            issues.append(
                A11yIssue(
                    rule="focus-not-trapped",
                    severity="moderate",
                    target=signature,
                    detail="焦点连续停在同一元素上，无法继续前进",
                )
            )
            break
        previous = signature
        seen.add(signature)
        if not item.get("visible", True):
            issues.append(
                A11yIssue(
                    rule="focus-visible",
                    severity="serious",
                    target=signature,
                    detail="焦点落在不可见元素上",
                )
            )
    return {
        "steps": len(reachable),
        "distinct": len(seen),
        "order": [
            {"tag": item.get("tag"), "name": item.get("name")} for item in reachable[:20]
        ],
        "issues": [issue.as_dict() for issue in issues],
        "ok": not issues,
    }


def _strip_css_comments(stylesheet: str) -> str:
    """去掉 CSS 注释，避免把说明文字当成样式声明。"""

    output: list[str] = []
    index = 0
    length = len(stylesheet)
    while index < length:
        start = stylesheet.find("/*", index)
        if start == -1:
            output.append(stylesheet[index:])
            break
        output.append(stylesheet[index:start])
        end = stylesheet.find("*/", start + 2)
        if end == -1:
            break
        index = end + 2
    return "".join(output)


def audit_focus_css(stylesheet: str) -> dict[str, Any]:
    """检查样式表是否保证键盘焦点可见（WCAG 2.4.7）。

    两条可复核规则：

    1. 不得出现 ``outline: none`` / ``outline: 0`` 这类无条件抑制；
    2. 必须至少有一条 ``:focus-visible`` 规则来加强焦点环。

    注意：这里只审计**我们自己的**样式表。Streamlit 组件的内部样式不在范围内，
    因此不把框架元素的计算样式当作违规（那会产生无法修复的误报）。
    """

    issues: list[A11yIssue] = []
    # 先去掉注释：注释里的文字不是样式声明，不应参与判定。
    text = _strip_css_comments(stylesheet)
    lowered = text.lower()
    suppressed = [
        match
        for match in ("outline:none", "outline: none", "outline:0", "outline: 0")
        if match in lowered
    ]
    if suppressed:
        issues.append(
            A11yIssue(
                rule="focus-not-suppressed",
                severity="serious",
                target="stylesheet",
                detail=f"样式表抑制了焦点轮廓：{', '.join(suppressed)}",
            )
        )
    if ":focus-visible" not in lowered:
        issues.append(
            A11yIssue(
                rule="focus-visible-style",
                severity="moderate",
                target="stylesheet",
                detail="样式表没有 :focus-visible 规则",
            )
        )
    return {
        "suppressed": suppressed,
        "has_focus_visible": ":focus-visible" in lowered,
        "issues": [issue.as_dict() for issue in issues],
        "ok": not issues,
    }


def summarize(*reports: dict[str, Any]) -> dict[str, Any]:
    """合并多份审计报告；任一硬失败即整体失败。"""

    issues: list[dict[str, Any]] = []
    for report in reports:
        issues.extend(report.get("issues") or [])
    critical = sum(1 for item in issues if item.get("severity") == "critical")
    serious = sum(1 for item in issues if item.get("severity") == "serious")
    moderate = sum(1 for item in issues if item.get("severity") == "moderate")
    return {
        "issues": issues,
        "critical": critical,
        "serious": serious,
        "moderate": moderate,
        "ok": critical == 0 and serious == 0,
    }


__all__ = [
    "AA_LARGE",
    "AA_TEXT",
    "AA_UI",
    "BACKGROUNDS",
    "BASE_TOKENS",
    "INTERACTIVE_ROLES",
    "TEXT_TOKENS",
    "A11yIssue",
    "audit_dom",
    "audit_focus_css",
    "audit_theme_tokens",
    "contrast_ratio",
    "keyboard_report",
    "relative_luminance",
    "summarize",
]
