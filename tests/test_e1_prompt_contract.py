"""T4-E1：通用 tool 语义修正的诚实性契约（离线，不调用模型）。

E1 只允许讲工具-种类映射；出现任何授权码值、地图房间/对象 ID、
路线暗示，即视为“靠近答案式提示”，测试必须失败。
"""
from __future__ import annotations

from pathlib import Path

PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "react_v12_autonomous.txt"


def _text() -> str:
    return PROMPT.read_text(encoding="utf-8")


def test_e1_tool_kind_rule_present() -> None:
    text = _text()
    assert "绝不对载具用 read_terminal" in text
    assert "use(授权码,载具)" in text


def test_e1_contains_no_authorization_code_value() -> None:
    text = _text()
    for code in ("ALPHA-731", "BETA-512", "GAMMA-904", "TIDE-2049", "TIDE-3160",
                 "TIDE-5280", "ABYSS-102", "ABYSS-618", "ABYSS-909"):
        assert code not in text


def test_e1_contains_no_map_specific_ids() -> None:
    text = _text()
    for token in ("control_room", "corridor", "storage_room", "reactor_room",
                  "escape_pod", "harbor_skiff", "escape_capsule", "lamp_console",
                  "control_terminal", "diagnostic_terminal", "screwdriver",
                  "reactor_panel", "replacement_fuse"):
        assert token not in text


def test_e1_contains_no_route_hint() -> None:
    text = _text()
    for token in ("先去", "然后去", "路线", "顺序是", "第一步去"):
        assert token not in text
