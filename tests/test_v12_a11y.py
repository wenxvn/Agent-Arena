"""V12 可访问性测试：对比度公式、主题 token、DOM 规则与焦点规则。"""

from __future__ import annotations

from agent_arena.lab.a11y import (
    AA_TEXT,
    AA_UI,
    audit_dom,
    audit_focus_css,
    audit_theme_tokens,
    contrast_ratio,
    keyboard_report,
    relative_luminance,
    summarize,
)
from agent_arena.ui import theme


def test_contrast_ratio_extremes() -> None:
    assert contrast_ratio("#000000", "#ffffff") == 21.0
    assert contrast_ratio("#ffffff", "#ffffff") == 1.0


def test_relative_luminance_ordering() -> None:
    assert relative_luminance("#000000") == 0.0
    assert relative_luminance("#ffffff") == 1.0
    assert relative_luminance("#808080") < relative_luminance("#a0a0a0")


def test_short_hex_is_supported() -> None:
    assert contrast_ratio("#fff", "#000") == 21.0


def test_theme_text_tokens_pass_wcag_aa() -> None:
    """文字 token 必须达到 AA 4.5:1（这是 V12 修复的真实缺陷）。"""

    report = audit_theme_tokens()
    assert report["ok"] is True, report["text_failures"]
    assert report["text_failures"] == []


def test_theme_ui_tokens_pass_three_to_one() -> None:
    report = audit_theme_tokens()
    assert report["ui_ok"] is True, report["ui_failures"]
    for row in report["rows"]:
        if row["kind"] == "ui":
            assert row["ratio"] >= AA_UI, row


def test_theme_audit_detects_a_bad_token() -> None:
    """审计必须能抓到不合格颜色，而不是永远返回通过。"""

    from agent_arena.lab import a11y

    original = a11y.TEXT_TOKENS["light"]["warning"]
    a11y.TEXT_TOKENS["light"]["warning"] = "#f0e0b0"
    try:
        report = audit_theme_tokens()
    finally:
        a11y.TEXT_TOKENS["light"]["warning"] = original
    assert report["ok"] is False
    assert any(row["token"] == "warning-text" for row in report["text_failures"])


def test_stylesheet_defines_focus_visible() -> None:
    report = audit_focus_css(theme.stylesheet())
    assert report["has_focus_visible"] is True
    assert report["ok"] is True, report["issues"]


def test_stylesheet_does_not_suppress_outline() -> None:
    report = audit_focus_css(theme.stylesheet())
    assert report["suppressed"] == []


def test_audit_focus_css_ignores_comments() -> None:
    css = "/* 我们不在任何地方写 outline: none */ a:focus-visible { outline: 2px solid red; }"
    report = audit_focus_css(css)
    assert report["suppressed"] == []
    assert report["ok"] is True


def test_audit_focus_css_flags_real_suppression() -> None:
    report = audit_focus_css("a { outline: none; }")
    assert report["ok"] is False
    assert report["suppressed"]


def test_dom_flags_unnamed_control() -> None:
    report = audit_dom(
        [
            {"tag": "h1", "heading_level": 1, "visible": True},
            {"tag": "button", "role": "button", "name": "", "visible": True},
        ]
    )
    assert report["ok"] is False
    assert report["critical"] == 1
    assert report["issues"][0]["rule"] == "control-has-name"


def test_dom_ignores_hidden_and_collapsed_controls() -> None:
    """折叠 expander 里的控件用户看不到，不应报"无名称"。"""

    report = audit_dom(
        [
            {"tag": "h1", "heading_level": 1, "visible": True},
            {"tag": "button", "role": "button", "name": "", "visible": False},
            {
                "tag": "button",
                "role": "button",
                "name": "",
                "visible": True,
                "aria_hidden": True,
            },
        ]
    )
    assert report["ok"] is True


def test_dom_requires_h1() -> None:
    report = audit_dom([{"tag": "h3", "heading_level": 3, "visible": True}])
    assert any(item["rule"] == "page-has-heading-one" for item in report["issues"])


def test_dom_flags_heading_skips() -> None:
    report = audit_dom(
        [
            {"tag": "h1", "heading_level": 1, "visible": True},
            {"tag": "h3", "heading_level": 3, "visible": True},
        ]
    )
    assert any(item["rule"] == "heading-order" for item in report["issues"])


def test_dom_accepts_sequential_headings() -> None:
    report = audit_dom(
        [
            {"tag": "h1", "heading_level": 1, "visible": True},
            {"tag": "h2", "heading_level": 2, "visible": True},
            {"tag": "h3", "heading_level": 3, "visible": True},
        ]
    )
    assert report["ok"] is True


def test_dom_flags_image_without_alt() -> None:
    report = audit_dom(
        [
            {"tag": "h1", "heading_level": 1, "visible": True},
            {"tag": "img", "src": "x.png", "alt": None, "visible": True},
        ]
    )
    assert any(item["rule"] == "image-alt" for item in report["issues"])


def test_dom_rejects_empty_snapshot() -> None:
    report = audit_dom([])
    assert report["ok"] is False


def test_keyboard_requires_focusable_elements() -> None:
    report = keyboard_report([{"tag": "body", "name": ""}])
    assert report["ok"] is False
    assert report["issues"][0]["rule"] == "keyboard-focusable"


def test_keyboard_accepts_forward_progress() -> None:
    report = keyboard_report(
        [
            {"id": 1, "tag": "a", "name": "Skip", "visible": True},
            {"id": 2, "tag": "input", "name": "radio", "visible": True},
            {"id": 3, "tag": "button", "name": "开始挑战", "visible": True},
        ]
    )
    assert report["ok"] is True
    assert report["distinct"] == 3


def test_keyboard_flags_consecutive_stuck_focus() -> None:
    report = keyboard_report(
        [
            {"id": 1, "tag": "a", "name": "Skip", "visible": True},
            {"id": 2, "tag": "button", "name": "x", "visible": True},
            {"id": 2, "tag": "button", "name": "x", "visible": True},
        ]
    )
    assert report["ok"] is False
    assert report["issues"][0]["rule"] == "focus-not-trapped"


def test_keyboard_allows_grid_canvas_focus_holding() -> None:
    report = keyboard_report(
        [
            {"id": 1, "tag": "a", "name": "Skip", "visible": True},
            {"id": 2, "tag": "canvas", "name": "grid", "visible": True},
            {"id": 2, "tag": "canvas", "name": "grid", "visible": True},
        ]
    )
    assert report["ok"] is True


def test_keyboard_flags_invisible_focus() -> None:
    report = keyboard_report(
        [{"id": 1, "tag": "button", "name": "hidden", "visible": False}]
    )
    assert report["ok"] is False
    assert report["issues"][0]["severity"] == "serious"


def test_keyboard_allows_wraparound_after_full_cycle() -> None:
    """焦点绕回第一个元素是浏览器正常行为，不算陷阱。"""

    order = [
        {"id": 1, "tag": "a", "name": "Skip", "visible": True},
        {"id": 2, "tag": "button", "name": "a", "visible": True},
        {"id": 3, "tag": "button", "name": "b", "visible": True},
        {"id": 1, "tag": "a", "name": "Skip", "visible": True},
    ]
    assert keyboard_report(order)["ok"] is True


def test_summarize_aggregates_severities() -> None:
    merged = summarize(
        {"issues": [{"rule": "a", "severity": "critical"}]},
        {"issues": [{"rule": "b", "severity": "moderate"}]},
    )
    assert merged["critical"] == 1
    assert merged["moderate"] == 1
    assert merged["ok"] is False


def test_theme_tokens_are_used_by_stylesheet() -> None:
    """审计的 token 名必须真的出现在样式表里，否则审计形同虚设。"""

    css = theme.stylesheet()
    for name in ("accent", "success", "warning", "danger", "info"):
        assert f"--aa-{name}-text" in css, name
    assert f"contrast >= {AA_TEXT}" not in css
