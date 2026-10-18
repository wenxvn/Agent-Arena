"""MAP-03 V10｜最后的百步：读码与远期调用分隔的长期记忆（DCR-V10-01）。

与 V8 的差异（规则变更，见 ``docs/v10/dcr/DCR-V10-01.md``）：

- 航线码、样本实验室位置、起点随环境 seed 变化（预登记手工变体表），航线码不再
  出现在 goal、词表或任何持续可见字段中；
- 航线码只在首次 ``read_tag`` 的结果与该步 Observation 中出现一次；样本稳定后清单
  封存（``MANIFEST_SEALED``），不存在后期回读通道；
- 读码与提交之间隔着不可跳过的 P3（EVA 天线）与 P4（遥测）阶段；
- 新增 agent-owned ``write_memory(facts)``：每次 1 tick，最多 3 条，写入的内容原样
  出现在 ``agent_notes``，环境不校验内容真伪；
- 天线面板码与遥测回执码与航线码同格式且持续可见，是合法干扰项；
- EVA 计费与设计文档对齐：进入 V 需 ``eva_supply==3``，进入、在 V 内的每个动作、
  返回 D3 各扣 1；在 V 内归零即失败。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.metrics.schema import (
    MetricSpec,
    MValue,
    censored,
    not_applicable,
    ratio,
    valid,
)
from agent_arena.v10.runtime.base import V10Map
from agent_arena.worlds.scenario_v8.models import V8Action

#: 预登记手工变体：seed -> (起点, 样本实验室, 航线码, 天线面板码, 遥测回执码)。
VARIANTS: dict[int, tuple[str, str, str, str, str]] = {
    0: ("U2", "U1", "K7", "R4", "M2"),
    1: ("XU", "D2", "T3", "K8", "W5"),
    2: ("D3", "U1", "H6", "T9", "K2"),
    3: ("U2", "D2", "M8", "H3", "R6"),
    4: ("XU", "U1", "N4", "M7", "T1"),
    5: ("D3", "D2", "R2", "W9", "H5"),
}
#: 航线码与干扰码不得与任何公开字符串（节点名、里程碑名）重合，否则泄漏扫描失效。
RESERVED_TOKENS = frozenset(
    {"D1", "D2", "D3", "U1", "U2", "U3", "XD", "XU", "P1", "P2", "P3", "P4", "P5"}
)
RETURN_SLACK = 8
NOTE_CAPACITY = 3
NOTE_VALUE_MAX = 24
EDGES = {
    "D1_D2": ("D1", "D2"),
    "D2_D3": ("D2", "D3"),
    "D3_XD": ("D3", "XD"),
    "XD_XU": ("XD", "XU"),
    "XU_U3": ("XU", "U3"),
    "U3_U2": ("U3", "U2"),
    "U2_U1": ("U2", "U1"),
    "D3_V": ("D3", "V"),
}


def shortest(start: str, goal: str) -> int:
    """九节点图上的 BFS 距离（公开拓扑）。"""

    frontier = [start]
    distance = {start: 0}
    while frontier:
        node = frontier.pop(0)
        if node == goal:
            return distance[node]
        for a, b in EDGES.values():
            if node not in (a, b):
                continue
            other = b if node == a else a
            if other not in distance:
                distance[other] = distance[node] + 1
                frontier.append(other)
    raise ValueError(f"不可达：{start}->{goal}")


def minimum_ticks(start: str, lab: str) -> int:
    """最短合法完成时长（含 1 次 write_memory），用于公开返航窗。"""

    ticks = shortest(start, "D1") + 1  # P1
    ticks += shortest("D1", lab) + 3  # read + write_memory + stabilize
    ticks += shortest(lab, "D3") + 3  # enter V + repair + exit
    ticks += shortest("D3", "U3") + 1  # transmit
    ticks += shortest("U3", "U2") + 1  # submit
    return ticks


class Map03V10Environment(V10Map):
    map_id = "MAP-03"
    title = "最后的百步"
    world = "spaceship"
    level = "困难"
    RULE_VERSION = "v10.map03.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    EDGES = EDGES
    SHAPES: dict[str, set[frozenset[str]]] = {
        "move": {frozenset({"tool", "edge_id"})},
        "inspect": {frozenset({"tool", "target"})},
        "interact": {frozenset({"tool", "target", "choice"})},
        "submit": {frozenset({"tool", "target", "answer"})},
        "wait": {frozenset({"tool", "turns"})},
        "write_memory": {frozenset({"tool", "facts"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "location",
            "visible_edges",
            "object_locations",
            "aux_power",
            "sample_cold",
            "manifest_state",
            "antenna",
            "antenna_panel_code",
            "telemetry",
            "telemetry_ack_code",
            "route_calibrated",
            "route_tag_read",
            "route_tag_value",
            "sample_thermal_ticks",
            "eva_supply",
            "eva_active",
            "milestones",
            "milestones_completed",
            "tick",
            "return_window_end_tick",
            "agent_notes",
            "note_capacity",
            "goal",
        }
    )
    MILESTONES = ("P1", "P2", "P3", "P4", "P5")
    PRIMARY_METRIC = "map03.v10.code_recall_correct"
    METRIC_SPECS = (
        MetricSpec(
            "map03.v10.code_recall_correct",
            "primary",
            "higher",
            "submitted_answer == sealed route_code",
            "读码且发生提交的局（1）",
            censored_rule=(
                "读码后预算截尾未提交 → CENSORED；未读码或提交前其他终局 → NOT_APPLICABLE"
            ),
            event_source="submit 事件 + 密封真值",
        ),
        MetricSpec(
            "map03.v10.phase_completion",
            "primary",
            "higher",
            "completed_milestones / 5",
            "5",
            censored_rule="部分进度在截尾时仍 VALID",
        ),
        MetricSpec(
            "map03.v10.memory_gap_actions",
            "secondary",
            "none",
            "submit_action_index - read_action_index",
            "—",
            censored_rule="未读码或未提交 → NOT_APPLICABLE / CENSORED",
            unit="actions",
            valid_range=(1.0, 200.0),
        ),
        MetricSpec(
            "map03.v10.tag_read_attempts",
            "diagnostic",
            "none",
            "count(interact sample_manifest/read_tag)",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map03.v10.memory_writes",
            "diagnostic",
            "none",
            "count(accepted write_memory)",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
        MetricSpec(
            "map03.v10.note_holds_code_at_submit",
            "secondary",
            "higher",
            "agent_notes 在提交时包含航线码",
            "发生提交的局（1）",
            event_source="submit 时刻 agent_notes 快照",
        ),
        MetricSpec(
            "map03.v10.distractor_submitted",
            "guardrail",
            "lower",
            "提交值 ∈ {天线面板码, 遥测回执码}",
            "发生提交的局（1）",
        ),
        MetricSpec(
            "map03.v10.eva_overspend",
            "guardrail",
            "lower",
            "EVA 实际消耗 - 3（成功单次出舱的最小消耗）",
            "—",
            unit="units",
            valid_range=(-3.0, 3.0),
        ),
        MetricSpec(
            "map03.v10.phase_order_violations",
            "guardrail",
            "lower",
            "count(PHASE_OUT_OF_ORDER)",
            "—",
            unit="count",
            valid_range=(0.0, 200.0),
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        start, lab, route_code, antenna_code, ack_code = VARIANTS[seed]
        self.start_node = start
        self.lab = lab
        self._route_code = route_code
        self.antenna_code = antenna_code
        self.ack_code = ack_code
        self.node = start
        self.aux_power = False
        self.sample_cold = False
        self.antenna = "damaged"
        self.telemetry = "not_sent"
        self.route_calibrated = False
        self.route_tag_read = False
        self.just_read_tag = False
        self.thermal_ticks: int | None = None
        self.eva_supply = 3
        self.eva_spent = 0
        self.milestones = {name: False for name in self.MILESTONES}
        self.min_ticks = minimum_ticks(start, lab)
        self.return_window_end_tick = self.min_ticks + RETURN_SLACK
        self.notes: list[dict[str, str]] = []
        self.action_index = 0
        self.read_action_index: int | None = None
        self.submit_action_index: int | None = None
        self.submitted_answer: str | None = None
        self.notes_at_submit: list[dict[str, str]] | None = None
        self.read_attempts = 0
        self.memory_writes = 0

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "start": self.start_node,
            "sample_lab": self.lab,
            "return_window_end_tick": self.return_window_end_tick,
            "antenna_panel_code": self.antenna_code,
            "telemetry_ack_code": self.ack_code,
            "min_ticks": self.min_ticks,
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {"route_code": self._route_code}

    def public_rules(self) -> tuple[str, ...]:
        return (
            "五阶段必须按 P1 供电(D1 aux_panel/restore_power) → P2 读清单并冷藏样本"
            "(实验室 sample_manifest/read_tag 后 cryo_case/stabilize_sample) → P3 EVA 修天线"
            "(V antenna/repair) → P4 发遥测(U3 telemetry/transmit) → P5 在 U2 "
            "submit route_console 航线码；跳步返回 PHASE_OUT_OF_ORDER。",
            "航线码格式为 1 个大写字母 + 1 个数字；只在首次 read_tag 的结果与紧随其后的一个"
            " Observation 中出现一次。稳定样本后清单封存，之后无法再读；只有 1 次提交机会。",
            "读码后样本开始升温：sample_thermal_ticks 从 4 递减，必须在第 4 个后续动作内完成冷藏。",
            'write_memory(facts)：facts 为 [{"key": str, "value": str}]，每次 1 tick，'
            "最多保留 3 条（同 key 覆盖），内容原样显示在 agent_notes；环境不校验真伪。"
            "这是你唯一能跨越很多步保存信息的通道。",
            "antenna_panel_code 与 telemetry_ack_code 与航线码同格式，但不是航线码。",
            "EVA：只有 eva_supply=3 时才能从 D3 进入 V；进入 V、在 V 内的每个动作、返回 D3 "
            "各消耗 1；在 V 内 eva_supply 归零立即失败。",
            "tick 达到 return_window_end_tick 仍未校准航线即失败；"
            "每个动作（含被拒动作）耗 1 tick。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        return {
            "location": self.node,
            "visible_edges": self.visible_edges(),
            "object_locations": {
                "aux_panel": "D1",
                "sample_manifest": self.lab,
                "cryo_case": self.lab,
                "route_console": "U2",
                "telemetry": "U3",
                "telemetry_panel": "U3",
                "antenna": "V",
            },
            "aux_power": self.aux_power,
            "sample_cold": self.sample_cold,
            "manifest_state": (
                "sealed" if self.sample_cold else "read" if self.route_tag_read else "unread"
            ),
            "antenna": self.antenna,
            "antenna_panel_code": self.antenna_code if self.antenna == "repaired" else None,
            "telemetry": self.telemetry,
            "telemetry_ack_code": self.ack_code if self.telemetry == "sent" else None,
            "route_calibrated": self.route_calibrated,
            "route_tag_read": self.route_tag_read,
            "route_tag_value": self._route_code if self.just_read_tag else None,
            "sample_thermal_ticks": self.thermal_ticks,
            "eva_supply": self.eva_supply,
            "eva_active": self.node == "V",
            "milestones": dict(self.milestones),
            "milestones_completed": sum(1 for done in self.milestones.values() if done),
            "tick": self.tick_count,
            "return_window_end_tick": self.return_window_end_tick,
            "agent_notes": [dict(item) for item in self.notes],
            "note_capacity": NOTE_CAPACITY,
            "goal": (
                "依次完成供电、读码并冷藏样本、EVA 修天线、发送遥测，"
                "最后在舰桥提交早前读到的航线码。"
            ),
        }

    # ------------------------------------------------------------------ rules
    def _spend_eva(self) -> None:
        self.eva_supply -= 1
        self.eva_spent += 1

    def _apply(self, action: V8Action) -> str:
        self.just_read_tag = False
        self.action_index += 1
        in_v = self.node == "V"
        result = self._dispatch(action)
        return self._eva_after(in_v, result)

    def _eva_after(self, in_v: bool, result: str) -> str:
        """在 V 内开始且结束的动作（含被拒动作）扣 1；离开 V 的移动已在 _move 计费。"""

        if self.status.value != "running":
            return result
        if in_v and self.node == "V":
            self._spend_eva()
        if self.node == "V" and self.eva_supply <= 0:
            self.eva_supply = 0
            self._fail("EVA_OXYGEN_EXHAUSTED")
            return "EVA_OXYGEN_EXHAUSTED"
        return result

    def _invalid_action(self) -> str:
        self.just_read_tag = False
        self.action_index += 1
        return self._eva_after(self.node == "V", "INVALID_ACTION_SCHEMA")

    def _dispatch(self, action: V8Action) -> str:
        tool = action.tool
        if tool == "move":
            return self._move(action)
        if tool == "inspect":
            if action.target == "telemetry_panel" and self.node == "U3":
                if self.antenna != "repaired":
                    return "TELEMETRY_REQUIRES_REPAIRED_ANTENNA"
                return "TELEMETRY_READY"
            return "TARGET_NOT_VISIBLE"
        if tool == "wait":
            return "WAITED"
        if tool == "submit":
            return self._submit(action)
        if tool == "interact":
            return self._interact(action)
        if tool == "write_memory":
            return self._write_memory(action)
        return "ACTION_NOT_ALLOWED"

    def _move(self, action: V8Action) -> str:
        assert action.edge_id is not None
        destination = self.edge_destination(action.edge_id)
        if destination is None:
            return "EDGE_NOT_ADJACENT"
        if destination == "V":
            if self.eva_supply < 3:
                return "EVA_SORTIE_REFUSED"
            self.node = "V"
            self._spend_eva()
            return "EVA_ENTERED"
        if self.node == "V":
            self.node = destination
            self._spend_eva()
            return f"EVA_EXITED:{destination}"
        self.node = destination
        return f"MOVED:{destination}"

    def _write_memory(self, action: V8Action) -> str:
        facts = action.facts or []
        if not facts:
            return "MEMORY_EMPTY"
        parsed: list[tuple[str, str]] = []
        for fact in facts:
            if set(fact) != {"key", "value"}:
                return "MEMORY_FACT_SCHEMA"
            key, value = fact["key"], fact["value"]
            if not isinstance(key, str) or not isinstance(value, str):
                return "MEMORY_FACT_SCHEMA"
            if not key.strip() or len(key) > NOTE_VALUE_MAX or len(value) > NOTE_VALUE_MAX:
                return "MEMORY_FACT_TOO_LONG"
            parsed.append((key, value))
        for key, value in parsed:
            self.notes = [item for item in self.notes if item["key"] != key]
            self.notes.append({"key": key, "value": value})
        dropped = max(0, len(self.notes) - NOTE_CAPACITY)
        if dropped:
            self.notes = self.notes[dropped:]
        self.memory_writes += 1
        return f"MEMORY_WRITTEN:{len(self.notes)}" + (f";DROPPED:{dropped}" if dropped else "")

    def _interact(self, action: V8Action) -> str:
        target, choice = action.target, action.choice
        if target == "aux_panel" and choice == "restore_power":
            if self.node != "D1":
                return "TARGET_NOT_VISIBLE"
            if self.aux_power:
                return "POWER_ALREADY_ON"
            self.aux_power = True
            self.milestones["P1"] = True
            return "AUX_POWER_ON"
        if target == "sample_manifest" and choice == "read_tag":
            if self.node != self.lab:
                return "TARGET_NOT_VISIBLE"
            self.read_attempts += 1
            if self.sample_cold:
                return "MANIFEST_SEALED"
            if not self.aux_power:
                self._violate("phase_order")
                return "PHASE_OUT_OF_ORDER"
            if self.route_tag_read:
                return "TAG_ALREADY_READ"
            self.route_tag_read = True
            self.just_read_tag = True
            self.thermal_ticks = 4
            self.read_action_index = self.action_index
            return f"TAG:{self._route_code}"
        if target == "cryo_case" and choice == "stabilize_sample":
            if self.node != self.lab:
                return "TARGET_NOT_VISIBLE"
            if not self.aux_power or not self.route_tag_read:
                self._violate("phase_order")
                return "PHASE_OUT_OF_ORDER"
            if self.sample_cold:
                return "SAMPLE_ALREADY_STABLE"
            self.sample_cold = True
            self.thermal_ticks = None
            self.milestones["P2"] = True
            return "SAMPLE_STABILIZED"
        if target == "antenna" and choice == "repair":
            if self.node != "V":
                return "TARGET_NOT_VISIBLE"
            if not (self.milestones["P1"] and self.milestones["P2"]):
                self._violate("phase_order")
                return "PHASE_OUT_OF_ORDER"
            if self.antenna == "repaired":
                return "ANTENNA_ALREADY_REPAIRED"
            self.antenna = "repaired"
            self.milestones["P3"] = True
            return "ANTENNA_REPAIRED"
        if target == "telemetry" and choice == "transmit":
            if self.node != "U3":
                return "TARGET_NOT_VISIBLE"
            if not self.milestones["P3"]:
                self._violate("phase_order")
                return "PHASE_OUT_OF_ORDER"
            if self.telemetry == "sent":
                return "TELEMETRY_ALREADY_SENT"
            self.telemetry = "sent"
            self.milestones["P4"] = True
            return "TELEMETRY_SENT"
        return "ACTION_NOT_ALLOWED"

    def _submit(self, action: V8Action) -> str:
        if action.target != "route_console" or self.node != "U2":
            return "TARGET_NOT_VISIBLE"
        if self.submitted_answer is not None:
            return "SUBMISSION_ALREADY_USED"
        if not all(self.milestones[name] for name in ("P1", "P2", "P3", "P4")):
            self._violate("phase_order")
            return "PHASE_OUT_OF_ORDER"
        self.submitted_answer = str(action.answer)
        self.submit_action_index = self.action_index
        self.notes_at_submit = [dict(item) for item in self.notes]
        if self.submitted_answer != self._route_code:
            self._fail("ROUTE_KEY_REJECTED")
            return "ROUTE_KEY_REJECTED"
        self.route_calibrated = True
        self.milestones["P5"] = True
        self._succeed("ROUTE_CALIBRATED")
        return "ROUTE_CALIBRATED"

    def _after_tick(self) -> None:
        if self.is_terminal:
            return
        if self.thermal_ticks is not None and not self.sample_cold and not self.just_read_tag:
            self.thermal_ticks -= 1
            if self.thermal_ticks <= 0:
                self.thermal_ticks = 0
                self._fail("SAMPLE_COLD_WINDOW_EXPIRED")
                return
        if self.tick_count >= self.return_window_end_tick and not self.route_calibrated:
            self._fail("RETURN_WINDOW_EXPIRED")

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "location": self.node,
            "aux_power": self.aux_power,
            "sample_cold": self.sample_cold,
            "antenna": self.antenna,
            "telemetry": self.telemetry,
            "route_calibrated": self.route_calibrated,
            "route_tag_read": self.route_tag_read,
            "eva_supply": self.eva_supply,
            "eva_spent": self.eva_spent,
            "milestones": dict(self.milestones),
            "thermal_ticks": self.thermal_ticks,
            "notes": [dict(item) for item in self.notes],
            "read_action_index": self.read_action_index,
            "submit_action_index": self.submit_action_index,
            "submitted_answer": self.submitted_answer,
            "violations": dict(self.violations),
            "truth_seal": self.truth_seal(),
        }

    def _note_has_code(self, notes: list[dict[str, str]] | None) -> bool:
        return any(self._route_code in item.get("value", "") for item in notes or [])

    def v10_metrics(self) -> dict[str, MValue]:
        submitted = self.submitted_answer is not None
        censored_run = self.status.value == "step_limit_reached" or not self.is_terminal
        if not self.route_tag_read:
            recall = not_applicable("从未读码")
            gap = not_applicable("从未读码")
        elif submitted:
            recall = valid(int(self.submitted_answer == self._route_code))
            assert self.submit_action_index is not None and self.read_action_index is not None
            gap = valid(self.submit_action_index - self.read_action_index)
        elif censored_run:
            recall = censored("读码后预算截尾，未提交")
            gap = censored("读码后预算截尾，未提交")
        else:
            recall = not_applicable(f"提交前终局：{self.terminal_reason}")
            gap = not_applicable(f"提交前终局：{self.terminal_reason}")
        completed = sum(1 for done in self.milestones.values() if done)
        if submitted:
            note_code = valid(int(self._note_has_code(self.notes_at_submit)))
            distractor = valid(int(self.submitted_answer in {self.antenna_code, self.ack_code}))
        else:
            note_code = not_applicable("未提交")
            distractor = not_applicable("未提交")
        overspend = valid(self.eva_spent - 3) if self.eva_spent else not_applicable("未出舱")
        return {
            "map03.v10.code_recall_correct": recall,
            "map03.v10.phase_completion": ratio(completed, len(self.MILESTONES)),
            "map03.v10.memory_gap_actions": gap,
            "map03.v10.tag_read_attempts": valid(self.read_attempts),
            "map03.v10.memory_writes": valid(self.memory_writes),
            "map03.v10.note_holds_code_at_submit": note_code,
            "map03.v10.distractor_submitted": distractor,
            "map03.v10.eva_overspend": overspend,
            "map03.v10.phase_order_violations": valid(self.violations.get("phase_order", 0)),
        }

    def mechanism_triggered(self) -> bool:
        """读码发生，且提交时距读码超过 5 条 history 窗口。"""

        if self.read_action_index is None or self.submit_action_index is None:
            return False
        return self.submit_action_index - self.read_action_index > 5


__all__ = ["Map03V10Environment", "VARIANTS", "minimum_ticks"]
