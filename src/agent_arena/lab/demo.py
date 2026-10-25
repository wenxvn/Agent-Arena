"""演示专用脚本 Provider：让 SIMULATED 实验展示**行为差异**。

为什么需要它：``deterministic_cycle`` 对每个实验臂给出相同动作，只能验证调用链，
不能展示"架构差异"。本模块提供一组**人工编写、只使用公开信息**的动作脚本，
按 ``(地图, 策略)`` 选取，让三臂产生不同的失败模式、记忆事件与指标五态。

明确边界：

- 脚本**不是** Oracle：每一步的依据都是公开规则/公开 Observation
  （例如 MAP-10 的装载量由公开 fuel/burn 公式算出；MAP-26 的换件不依赖真值）；
- 脚本不保证通关，也不代表任何模型能力；
- 只用于演示/UI 测试，落盘结果仍然标注 ``mode=simulated``；
- 默认注册表不加载它，必须显式传入 ``demo_provider_factory``。
"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.simulated import (
    STRATEGY_SCRIPTED,
    SimulatedDecisionProvider,
    build_simulated_provider,
)

#: (map_id, agent_id) → 公开信息动作脚本。
DEMO_SCRIPTS: dict[tuple[str, str], list[dict[str, Any]]] = {
    # ---------------- MAP-10：公开算术题（fuel=6, burn=2+ceil(cargo/2)）--------
    # 装 10 → burn=7 > fuel=6 → OUT_OF_FUEL（算错代价）。
    ("MAP-10", "basic.v1"): [
        {"tool": "load", "quantity": 10},
        {"tool": "move", "to": "D"},
    ],
    # 装 6（= required_delivery）→ burn=5 ≤ 6 → 成功；同时把公开公式写进记忆。
    ("MAP-10", "memory.v1"): [
        {"tool": "load", "quantity": 6},
        {"tool": "move", "to": "D"},
    ],
    # 装 8 → burn=6 = fuel → 成功，但 Planner 会额外请求。
    ("MAP-10", "planning.v1"): [
        {"tool": "load", "quantity": 8},
        {"tool": "move", "to": "D"},
    ],
    # ---------------- MAP-22：无图导航，起点 bearings=["west"] ----------------
    ("MAP-22", "basic.v1"): [
        {"tool": "observe_signpost"},
        {"tool": "move", "bearing": "west"},
        {"tool": "move", "bearing": "west"},
        {"tool": "observe_signpost"},
        {"tool": "move", "bearing": "east"},
        {"tool": "move", "bearing": "east"},
    ],
    # memory 臂：先写方位再移动（公开 write_memory 契约），route_recall 因此可算。
    ("MAP-22", "memory.v1"): [
        {"tool": "observe_signpost"},
        {"tool": "write_memory", "facts": [{"key": "bearing", "value": "west"}]},
        {"tool": "move", "bearing": "west"},
        {"tool": "write_memory", "facts": [{"key": "bearing", "value": "west"}]},
        {"tool": "move", "bearing": "west"},
        {"tool": "check_goal"},
        {"tool": "return_to_camp"},
    ],
    # planning 臂：动作与 basic 相同，差异来自 Planner 请求与计划事件。
    ("MAP-22", "planning.v1"): [
        {"tool": "observe_signpost"},
        {"tool": "move", "bearing": "west"},
        {"tool": "move", "bearing": "west"},
        {"tool": "observe_signpost"},
        {"tool": "move", "bearing": "east"},
    ],
    # ---------------- MAP-26：备件映射 F1→P1/F2→P2/F3→P3 是公开信息 ----------
    # 不测试就连换三件 → 磨损到上限、备件耗尽（盲换）。
    ("MAP-26", "basic.v1"): [
        {"tool": "replace", "part_id": "P1"},
        {"tool": "replace", "part_id": "P2"},
        {"tool": "replace", "part_id": "P3"},
        {"tool": "restart"},
    ],
    # 先跑两个公开测试再换一件（不保证换对，但过程可复核）。
    ("MAP-26", "memory.v1"): [
        {"tool": "run_test", "test_id": "T1"},
        {"tool": "run_test", "test_id": "T2"},
        {"tool": "replace", "part_id": "P1"},
        {"tool": "restart"},
    ],
    ("MAP-26", "planning.v1"): [
        {"tool": "read_log", "log_id": "L1"},
        {"tool": "replace", "part_id": "P3"},
        {"tool": "restart"},
    ],
    # ---------------- MAP-18：公开发车窗口在 tick≥5 ---------------------------
    ("MAP-18", "basic.v1"): [
        {
            "tool": "set_timetable",
            "tick": 0,
            "operations": {"T_R1": {"op": "release", "to": "R2"}},
        },
        {
            "tool": "set_timetable",
            "tick": 0,
            "operations": {"T_B": {"op": "release", "to": "B2"}},
        },
    ],
    ("MAP-18", "memory.v1"): [
        {"tool": "set_timetable", "tick": 0, "operations": {}},
        {"tool": "set_timetable", "tick": 1, "operations": {}},
        {"tool": "set_timetable", "tick": 2, "operations": {}},
    ],
    ("MAP-18", "planning.v1"): [
        {
            "tool": "set_timetable",
            "tick": 0,
            "operations": {"T_G": {"op": "release", "to": "G2"}},
        },
        {"tool": "set_timetable", "tick": 1, "operations": {}},
    ],
    # ---------------- MAP-08：S1..S5 与 T1..T3 分区公开 -----------------------
    ("MAP-08", "basic.v1"): [
        {"tool": "run_test", "test_id": "T1"},
        {"tool": "run_test", "test_id": "T2"},
        {"tool": "seal_diagnosis", "diagnosis_code": "S1"},
        {"tool": "repair", "target_id": "S1"},
    ],
    ("MAP-08", "memory.v1"): [
        {"tool": "run_test", "test_id": "T1"},
        {"tool": "run_test", "test_id": "T2"},
        {"tool": "run_test", "test_id": "T3"},
        {"tool": "wait"},
    ],
    ("MAP-08", "planning.v1"): [
        {"tool": "run_test", "test_id": "T1"},
        {"tool": "seal_diagnosis", "diagnosis_code": "S1"},
        {"tool": "repair", "target_id": "S1"},
    ],
    # ---------------- MAP-16：登记下一跳后整帧提交（公开规则）-----------------
    ("MAP-16", "basic.v1"): [
        {"tool": "set_route", "train_id": "a", "next_node": "X"},
        {"tool": "move_train"},
        {"tool": "set_route", "train_id": "a", "next_node": "M"},
        {"tool": "move_train"},
    ],
    ("MAP-16", "memory.v1"): [
        {"tool": "inspect_network"},
        {"tool": "set_route", "train_id": "a", "next_node": "X"},
        {"tool": "move_train"},
        {"tool": "inspect_network"},
    ],
    ("MAP-16", "planning.v1"): [
        {"tool": "move_train"},
        {"tool": "set_route", "train_id": "b", "next_node": "Y"},
        {"tool": "move_train"},
    ],
    # ---------------- MAP-30：条目 ID 与地点公开，证据链需按顺序 -----------------
    ("MAP-30", "basic.v1"): [
        {"tool": "move", "to": "B"},
        {"tool": "inspect", "evidence_id": "B_KEY_STUB_2310"},
        {
            "tool": "record",
            "entry_id": "EVENT_1_HANDOFF",
            "evidence_ids": ["B_KEY_STUB_2310"],
        },
        {"tool": "move", "to": "J"},
        {
            "tool": "formal_accuse",
            "person_id": "BANQUET_CLERK",
            "event_claims": [],
            "cited_entry_ids": [],
        },
    ],
    ("MAP-30", "memory.v1"): [
        {"tool": "move", "to": "L"},
        {"tool": "move", "to": "K"},
        {"tool": "inspect", "evidence_id": "K_WAX_PLATE_2322"},
        {
            "tool": "record",
            "entry_id": "EVENT_2_WAX",
            "evidence_ids": ["K_WAX_PLATE_2322"],
        },
        {
            "tool": "interview",
            "npc_id": "KITCHEN_COOK",
            "topic_id": "EVENT_2_WAX",
            "shown_evidence_ids": ["K_WAX_PLATE_2322"],
            "shown_casebook_entry_ids": [],
        },
    ],
    ("MAP-30", "planning.v1"): [
        {"tool": "move", "to": "A"},
        {"tool": "inspect", "evidence_id": "Q4_ARCHIVE_DOCKET"},
        {
            "tool": "record",
            "entry_id": "Q4_CODEBOOK",
            "evidence_ids": ["Q4_ARCHIVE_DOCKET"],
        },
    ],
}

DEMO_NOTE = (
    "演示脚本：动作由人工按公开规则编写，不是模型输出，也不是 Oracle；"
    "结果只用于展示对照、诊断与可视化链路。"
)


def demo_provider_factory(config: Any) -> Any:
    """按 (map_id, agent) 选择演示脚本；没有脚本时退回确定性循环。"""

    script = DEMO_SCRIPTS.get((config.map_id, config.agent))
    if not script:
        return build_simulated_provider(config)
    from agent_arena.v10.runtime.catalog import create_environment

    environment = create_environment(
        config.map_id, environment_seed=config.environment_seed
    )
    return SimulatedDecisionProvider(
        map_id=config.map_id,
        shapes=environment.SHAPES,
        strategy=STRATEGY_SCRIPTED,
        script=script,
        policy_seed=config.policy_seed,
    )


def demo_pairs() -> list[tuple[str, str]]:
    return sorted(DEMO_SCRIPTS)


__all__ = ["DEMO_NOTE", "DEMO_SCRIPTS", "demo_pairs", "demo_provider_factory"]
