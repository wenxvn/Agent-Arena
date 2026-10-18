"""Batch 9：逐图审计卡与状态矩阵的一致性测试（离线、无网络）。"""

from __future__ import annotations

import json

from agent_arena.v10.evidence_state import DECISIONS
from agent_arena.v10.map_cards import render_card, render_index
from agent_arena.v10.paths import V10_DOCS
from agent_arena.v10.runtime.catalog import MAP_IDS, V10_MAPS

REQUIRED_SECTIONS = (
    "## 1. 目标构念与最小可观察行为",
    "## 2. 公开信息边界",
    "## 3. 合法动作契约",
    "## 4. 环境 seed 与实例差异性",
    "## 6. 反事实消融",
    "## 8. 结论、剩余风险与下一步",
    "## 9. 证据索引",
)


def test_every_map_has_a_card_with_required_sections() -> None:
    for map_id in MAP_IDS:
        text = render_card(map_id, {})
        assert text.startswith(f"# {map_id}｜"), map_id
        for section in REQUIRED_SECTIONS:
            assert section in text, (map_id, section)


def test_v10_cards_declare_public_boundary_and_sealed_keys() -> None:
    for map_id in sorted(V10_MAPS):
        text = render_card(map_id, {})
        assert "### 密封真值（只列键名，真值只在 judge 与 hash 中）" in text
        assert "`rule_hash`：" in text


def test_index_lists_thirty_maps() -> None:
    index = render_index({})
    for map_id in MAP_IDS:
        assert f"[{map_id}]({map_id}.md)" in index
    assert "30 张" in index


def test_committed_cards_match_mimo_results() -> None:
    """卡片里的 MiMo 行必须与 ``runs/v10/mimo/results.json`` 一致（无产物则跳过）。

    不比对逐字节全文：卡片还包含会随时间变化的基线证据，字节级同步由
    ``python -m agent_arena.v10.map_cards`` 负责，这里只保证模型证据不漂移。
    """

    from agent_arena.v10.map_cards import _mimo_rows
    from agent_arena.v10.paths import V10_RUNS

    if not (V10_RUNS / "mimo" / "results.json").is_file():
        return
    mimo = _mimo_rows()
    for map_id in MAP_IDS:
        path = V10_DOCS / "maps" / f"{map_id}.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for row in mimo.get(map_id, []):
            assert f"`{row['run_id']}`" in text, (map_id, row["run_id"])


def test_status_matrix_covers_all_maps_and_states() -> None:
    path = V10_DOCS / "map-status-matrix.json"
    if not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == set(MAP_IDS)
    for map_id, row in payload.items():
        assert row["validity_status"] in {
            "VALIDATED",
            "NEEDS_MORE_EVIDENCE",
            "NEEDS_REDESIGN",
            "BLOCKED",
        }, map_id
        assert row["construct_status"] in {"FORCED", "OPTIONAL", "BYPASS", "BLOCKED"}


def test_decisions_cover_all_maps() -> None:
    assert set(DECISIONS) == set(MAP_IDS)
