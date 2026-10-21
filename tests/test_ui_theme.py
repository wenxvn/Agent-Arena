"""V11 展示层设计系统：色调映射、HTML 片段与转义。"""

from __future__ import annotations

from agent_arena.ui import theme


def test_state_tone_covers_every_run_state() -> None:
    from agent_arena.web.schemas import RunState

    for state in RunState:
        assert theme.state_tone(state.value) in theme.TONES
        assert state.value in theme.STATE_TONES


def test_difficulty_and_metric_tones() -> None:
    assert theme.difficulty_tone("简单") == "success"
    assert theme.difficulty_tone("困难") == "danger"
    assert theme.difficulty_tone("未登记的难度") == "neutral"
    for state in ("VALID", "CENSORED", "NOT_APPLICABLE", "MISSING", "INVALID"):
        assert theme.metric_tone(state) in theme.TONES
    assert theme.metric_tone("UNKNOWN") == "neutral"


def test_chip_escapes_user_text() -> None:
    html = theme.chip("<script>alert(1)</script>", "danger")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "aa-chip-danger" in html


def test_banner_and_progress_markup() -> None:
    html = theme.banner("失败", "水位超限", tone_name="danger", code="FLOODED")
    assert "aa-tone-danger" in html
    assert "FLOODED" in html
    assert "水位超限" in html

    assert "width:50.0%" in theme.progress(0.5, tone_name="success")
    # 越界比例被夹紧，不会画出负宽度或超过 100%。
    assert "width:0.0%" in theme.progress(-3)
    assert "width:100.0%" in theme.progress(7)


def test_map_card_html_contains_key_facts() -> None:
    html = theme.map_card_html(
        map_id="MAP-19",
        emoji="🌋",
        world_label="火山",
        title="温度临界点",
        display_difficulty="困难",
        design_difficulty="简单",
        goal="在 12 tick 内累计 49 点产能",
        mechanism="温度预测 · 冷却延迟",
        decision_budget=60,
        tool_count=5,
        seed_count=4,
        note="每 tick 必须 wait 一次",
        run_count=2,
        success_count=1,
    )
    assert "MAP-19" in html
    assert "aa-chip-danger" in html  # 展示难度「困难」
    assert "已跑 2 局 · 成功 1" in html
    assert "设计难度 简单" in html


def test_map_card_html_marks_never_run_maps() -> None:
    html = theme.map_card_html(
        map_id="MAP-30",
        emoji="🏰",
        world_label="古堡",
        title="午夜审判",
        display_difficulty="困难",
        design_difficulty="困难",
        goal="提交完整案卷",
        mechanism="案卷链 · 法庭指控",
        decision_budget=48,
        tool_count=6,
        seed_count=4,
        note="近期窗口只保留最近 5 条",
    )
    assert "未跑过" in html


def test_empty_state_and_kv_block_escape() -> None:
    empty = theme.empty_state("🔍", "没有结果", "换个筛选")
    assert "aa-empty-title" in empty
    assert "换个筛选" in empty

    block = theme.kv_block([("rule_hash", "a<b"), ("metric_hash", "c&d")])
    assert "a&lt;b" in block
    assert "c&amp;d" in block


def test_stylesheet_declares_core_tokens() -> None:
    css = theme.stylesheet()
    assert "<style>" in css
    assert "--aa-accent" in css
    assert "aa-tone-success" in css
    assert "@media (max-width: 900px)" in css
