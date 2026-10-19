"""Batch 9 补强：公式级复算的覆盖与新增公式测试（不跑全量 audit，保持秒级）。"""

from __future__ import annotations

from agent_arena.v10 import recompute
from agent_arena.v10.runtime.catalog import V10_MAPS


def test_formulas_cover_all_native_maps() -> None:
    assert set(recompute.FORMULAS) <= set(V10_MAPS)
    assert len(recompute.FORMULAS) == len(V10_MAPS)
    assert recompute.SKIP_REASONS == {}


def test_map03_recall_formula() -> None:
    judge = {"route_tag_read": True, "submitted_answer": "K7", "route_code": "K7"}
    assert recompute._f03({}, judge, False) == ("VAL", 1)
    judge["submitted_answer"] = "K8"
    assert recompute._f03({}, judge, False) == ("VAL", 0)
    assert recompute._f03({}, {"route_tag_read": False}, True)[0] == "CENSORED"
    assert recompute._f03({}, {"route_tag_read": False}, False)[0] == "NOT_APPLICABLE"


def test_map24_replan_formula_precedence() -> None:
    base = {
        "observation_tick": 4,
        "bridge_used_before_collapse": True,
        "delivery_tick": 7,
        "collapsed_attempts_after": 0,
    }
    assert recompute._f24({}, base, False) == ("VAL", 1)
    assert recompute._f24({}, base, True)[0] == "CENSORED"
    assert recompute._f24({}, {**base, "bridge_used_before_collapse": False}, False)[0] == (
        "NOT_APPLICABLE"
    )


def test_map26_mission_formula_requires_true_fault() -> None:
    base = {
        "restarted": True,
        "true_fault": "F2",
        "parts": {"F1": "P1", "F2": "P2", "F3": "P3"},
        "installed": "P2",
    }
    assert recompute._f26({}, base, False) == ("VAL", 1)
    assert recompute._f26({}, {**base, "installed": "P1"}, False) == ("VAL", 0)
    assert recompute._f26({}, base, True)[0] == "CENSORED"


def test_map13_ratio_formula_counts_predicates_and_orientation() -> None:
    roles = {'sun': '日', 'eye': '眼', 'reed': '芦', 'armor': '甲'}
    # 日=N(1) 违例；眼=E(2) 不大于芦=W(4)；甲=S(3) 与日相距 2；芦非首槽 ✔；方向钉 ✔
    judge = {
        'last_attempted': {'N': '日', 'E': '眼', 'S': '甲', 'W': '芦'},
        'roles': roles,
        'observed': ['ORIENTATION_ORDER'],
    }
    assert recompute._f13({}, judge, False) == ('VAL', 0.4)
    # 日=2、眼=4>芦=3、甲=1 与日相邻、芦非首槽、方向钉 → 5/5
    judge['last_attempted'] = {'N': '甲', 'E': '日', 'S': '芦', 'W': '眼'}
    assert recompute._f13({}, judge, False) == ('VAL', 1.0)
    # 零分母优先于截尾
    assert recompute._f13({}, {'roles': roles}, True)[0] == 'NOT_APPLICABLE'
    assert recompute._f13({}, {**judge, 'last_attempted': judge['last_attempted']}, True)[0] == (
        'CENSORED'
    )


def test_map14_deduction_formula_rederives_consistency() -> None:
    judge = {
        'claims': {'0_1': {'speaker': 'P0', 'subset': ['LOCK_0']}},
        'answers': [{'claim_id': '0_1', 'answer': True}],
        'sealed': [
            {'configuration_candidate': 'LOCK_0', 'truthful_priest_candidate': 'P0'},
            {'configuration_candidate': 'LOCK_1', 'truthful_priest_candidate': 'P0'},
        ],
        'submissions': [{'configuration': 'LOCK_0'}],
        'gate_open': True,
        'configuration': 'LOCK_0',
        'minimum_queries_no_archive': 1,
        'minimum_queries_with_archive': 1,
    }
    assert recompute._f14({}, judge, False) == ('VAL', 1)
    # 第二条假设与答案矛盾 → 若封存里只剩它，则不算完成
    judge['sealed'] = [judge['sealed'][1]]
    assert recompute._f14({}, judge, False) == ('VAL', 0)
    # 问数超过“两种路线较小值” → 0
    judge['sealed'] = [{'configuration_candidate': 'LOCK_0', 'truthful_priest_candidate': 'P0'}]
    judge['minimum_queries_no_archive'] = 2
    judge['answers'].append({'claim_id': '0_1', 'answer': True})
    assert recompute._f14({}, judge, False) == ('VAL', 0)


def test_map21_utility_formula_reuses_rounded_completion() -> None:
    from agent_arena.v10.runtime.map21 import max_science

    judge = {
        'evacuated_tick': 7,
        'terminal_reason': 'EVACUATED',
        'sample_points': 10,
        'measurement': 'M1',
        'environment_seed': 0,
    }
    maximum = max_science(0)
    completion = round((10 + 5) / maximum, 6)
    assert recompute._f21({}, judge, False) == ('VAL', round(0.5 + 0.5 * completion, 6))
    assert recompute._f21({}, {**judge, 'terminal_reason': 'FATAL_ERUPTION'}, False) == (
        'VAL',
        0,
    )
    assert recompute._f21({}, judge, True)[0] == 'CENSORED'
