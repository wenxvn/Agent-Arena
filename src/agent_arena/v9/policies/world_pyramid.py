"""V9 pyramid 世界（MAP-13/14/15）公开启发式与消融策略。

三条约束（与 ``v9/policies/base.py`` 一致）：

- 只读取公开 Observation 与自己的历史；不导入 Environment、judge_state、Oracle 或指标模块；
- 不输出值为 ``None`` 的字段（``V8Action`` 会拒绝）；
- 策略是“公开信息可执行”的，不是 Oracle 动作序列的复制：
  MAP-13 从碑文文本暴力枚举 24 种排列；MAP-14 用命题文本重建 9 态信念集合并做
  信息增益最大的提问；MAP-15 从 ``training_sample_log`` 学习互补对，再迁移到 T。
"""

from __future__ import annotations

from itertools import permutations
from typing import Any

# --------------------------------------------------------------------- MAP-13
MAP13_SLOTS = ("N", "E", "S", "W")
MAP13_SYMBOLS = ("日", "眼", "芦", "甲")
MAP13_CENTER_CLUE = "ORIENTATION_ORDER"


def _map13_edge(observation: dict[str, Any], destination: str) -> str:
    """Pick a public edge id that touches ``destination``."""

    for edge_id in observation.get("visible_edges") or []:
        if destination in str(edge_id).split("_"):
            return str(edge_id)
    return f"C_{destination}"


def _map13_holds(
    constraint: tuple[str, ...], position: dict[str, int]
) -> bool:
    kind = constraint[0]
    if kind == "not_ends":
        return position[constraint[1]] not in (1, len(MAP13_SLOTS))
    if kind == "right_of":
        return position[constraint[1]] > position[constraint[2]]
    if kind == "adjacent":
        return abs(position[constraint[1]] - position[constraint[2]]) == 1
    if kind == "not_first":
        return position[constraint[1]] != 1
    return True


def _map13_constraints(
    observed: dict[str, str],
) -> list[tuple[str, ...]]:
    """把公开碑文文本翻成槽位谓词；只依赖文本里的符号与方位词。"""

    constraints: list[tuple[str, ...]] = []
    for clue_id, text in observed.items():
        if clue_id == MAP13_CENTER_CLUE:
            continue
        symbols = [symbol for symbol in MAP13_SYMBOLS if symbol in text]
        if not symbols:
            continue
        if "两端" in text:
            constraints.append(("not_ends", symbols[0]))
        elif "右侧" in text and len(symbols) >= 2:
            constraints.append(("right_of", symbols[0], symbols[1]))
        elif "相邻" in text and len(symbols) >= 2:
            constraints.append(("adjacent", symbols[0], symbols[1]))
        elif "首槽" in text:
            constraints.append(("not_first", symbols[0]))
    return constraints


def _map13_solutions(observed: dict[str, str]) -> list[dict[str, str]]:
    order = list(MAP13_SLOTS)
    text = observed.get(MAP13_CENTER_CLUE, "")
    if text and "N→E→S→W" in text:
        order = ["N", "E", "S", "W"]
    constraints = _map13_constraints(observed)
    solutions: list[dict[str, str]] = []
    for perm in permutations(MAP13_SYMBOLS):
        layout = {slot: perm[index] for index, slot in enumerate(order)}
        position = {symbol: index + 1 for index, symbol in enumerate(perm)}
        if all(_map13_holds(item, position) for item in constraints):
            solutions.append(layout)
    return solutions


class Map13Heuristic:
    """读全五条信息后按约束枚举唯一排列，再一次验证开门。

    若 ``read_orientation_nail`` 为 False（消融），跳过 C 的方向钉读取与记录，
    直接读四间外室并沿用默认阅读序 N→E→S→W。
    """

    name = "public_heuristic"
    read_orientation_nail = True

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.solution_index = 0

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        location = str(observation.get("location"))
        observed = {
            str(item["clue_id"]): str(item["text"])
            for item in observation.get("observed_clues") or []
        }
        recorded = {str(item) for item in observation.get("recorded_clue_ids") or []}

        if observation.get("gate_open") or observation.get("terminal"):
            return {"tool": "verify_layout"}

        if self.read_orientation_nail:
            if MAP13_CENTER_CLUE not in observed:
                if location == "C":
                    return {"tool": "read_inscription", "room": "C"}
                return {"tool": "move", "edge_id": _map13_edge(observation, "C")}
            if MAP13_CENTER_CLUE not in recorded:
                if location != "C":
                    return {"tool": "move", "edge_id": _map13_edge(observation, "C")}
                return {"tool": "record_constraint", "clue_id": MAP13_CENTER_CLUE}

        for room in MAP13_SLOTS:
            clue_id = next(
                (
                    key
                    for key in observed
                    if key != MAP13_CENTER_CLUE and key.startswith(f"{room}_")
                ),
                None,
            )
            if clue_id is None:
                if location != room:
                    return {"tool": "move", "edge_id": _map13_edge(observation, room)}
                return {"tool": "read_inscription", "room": room}
            if clue_id not in recorded:
                if location != "C":
                    return {"tool": "move", "edge_id": _map13_edge(observation, "C")}
                return {"tool": "record_constraint", "clue_id": clue_id}

        if observation.get("trial_layout") is None:
            solutions = _map13_solutions(observed)
            if not solutions:
                return {"tool": "verify_layout"}
            layout = solutions[min(self.solution_index, len(solutions) - 1)]
            return {"tool": "set_trial_layout", "layout_by_room": layout}
        return {"tool": "verify_layout"}


class Map13NoDirectionNail(Map13Heuristic):
    """消融：不读方向钉，只靠四条房间谓词 + 默认阅读序。"""

    name = "ablation_no_direction_nail"
    read_orientation_nail = False


# --------------------------------------------------------------------- MAP-14
MAP14_CONFIGS = ("A_sun_wheel", "B_crescent", "C_star_well")
MAP14_PRIESTS = ("A_priest", "B_priest", "C_priest")
MAP14_PRIEST_NAMES = {"A_priest": "甲", "B_priest": "乙", "C_priest": "丙"}
MAP14_LOCK_NAMES = {
    "日轮锁A": "A_sun_wheel",
    "月牙锁B": "B_crescent",
    "星井锁C": "C_star_well",
}
MAP14_GRAPH = {"P": ["A"], "A": ["P", "O"], "O": ["A", "J"], "J": ["O"]}


def _map14_predicate(text: str) -> tuple[str, bool] | None:
    """把公开命题文本翻成 ``(锁型, 是否取反)``。"""

    target = next((value for key, value in MAP14_LOCK_NAMES.items() if key in text), None)
    if target is None:
        return None
    return target, "不是" in text


def _map14_next_hop(observation: dict[str, Any], destination: str) -> str:
    """公开图上的最短下一跳；图边由 Observation 中露出的边 id 构造。"""

    node = str(observation.get("location"))
    adjacency: dict[str, list[str]] = {}
    for edge_id in observation.get("visible_edges") or []:
        parts = str(edge_id).split("_")
        if len(parts) == 2:
            adjacency.setdefault(parts[0], []).append(parts[1])
            adjacency.setdefault(parts[1], []).append(parts[0])
    for source, targets in MAP14_GRAPH.items():
        for target in targets:
            adjacency.setdefault(source, []).append(target)
            adjacency.setdefault(target, []).append(source)
    queue: list[tuple[str, list[str]]] = [(node, [])]
    seen = {node}
    while queue:
        current, path = queue.pop(0)
        if current == destination:
            return path[0] if path else node
        for neighbour in sorted(set(adjacency.get(current, []))):
            if neighbour in seen:
                continue
            seen.add(neighbour)
            queue.append((neighbour, [*path, neighbour]))
    return node


def _map14_edge(observation: dict[str, Any], destination: str) -> str:
    node = str(observation.get("location"))
    for edge_id in observation.get("visible_edges") or []:
        parts = str(edge_id).split("_")
        if node in parts and destination in parts:
            return str(edge_id)
    return f"{node}_{destination}"


class Map14Heuristic:
    """档案排除 C → 用最小区分命题组提问 → 在 O 封存一致假设 → 在 J 提交。

    ``compare_before_submit`` 为 False 时（消融）跳过 ``compare_evidence``，
    仍按同一信念提交，用来检验主指标是否只依赖这一记账动作。

    **公开性边界**：本策略使用的“恰一名祭司如实、其余两人逐命题反报”这条规则
    只写在 map14 的模块 docstring 与 ``worlds/v4/MAP-14/map_spec.yaml``，
    V8/V9 的 system prompt 未公开它（见 ``docs/v9/maps/MAP-14-audit.md`` §3）。
    因此它是“设计者已知规则”的参照实现，不是严格意义上的公开信息策略。
    """

    name = "public_heuristic"
    compare_before_submit = True

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.cards: dict[str, str] = {}
        self.speakers: dict[str, str] = {}
        self.excluded: set[str] = set()
        self.asked: set[str] = set()
        self.rejected: set[str] = set()
        self.last_wrong = 0
        self.last_submitted: str | None = None

    # ---------------------------------------------------------------- helpers
    def _speaker(self, claim_id: str) -> str | None:
        return self.speakers.get(claim_id)

    def _belief(self, observation: dict[str, Any]) -> list[tuple[str, str]]:
        answers = observation.get("question_answers") or []
        belief: list[tuple[str, str]] = []
        for config in MAP14_CONFIGS:
            if config in self.excluded:
                continue
            for priest in MAP14_PRIESTS:
                consistent = True
                for row in answers:
                    claim_id = str(row.get("claim_id"))
                    text = self.cards.get(claim_id)
                    if text is None:
                        consistent = False
                        break
                    predicate = _map14_predicate(text)
                    if predicate is None:
                        consistent = False
                        break
                    target, negated = predicate
                    truth = (config == target) != negated
                    truthful = MAP14_PRIEST_NAMES[priest] == row.get("speaker")
                    spoken = truth if truthful else not truth
                    if ("yes" if spoken else "no") != row.get("answer"):
                        consistent = False
                        break
                if consistent:
                    belief.append((config, priest))
        return belief

    def _configs(self, belief: list[tuple[str, str]]) -> list[str]:
        ordered: list[str] = []
        for config, _priest in belief:
            if config not in ordered:
                ordered.append(config)
        return [config for config in ordered if config not in self.rejected]

    def _best_claim(self, belief: list[tuple[str, str]]) -> str | None:
        best: tuple[int, str] | None = None
        for claim_id in sorted(self.cards):
            if claim_id in self.asked:
                continue
            text = self.cards[claim_id]
            predicate = _map14_predicate(text)
            speaker = self._speaker(claim_id)
            if predicate is None or speaker is None:
                continue
            target, negated = predicate
            yes = 0
            for config, priest in belief:
                truth = (config == target) != negated
                spoken = truth if MAP14_PRIEST_NAMES[priest] == speaker else not truth
                yes += 1 if spoken else 0
            no = len(belief) - yes
            balance = min(yes, no)
            if balance == 0:
                continue
            if best is None or balance > best[0]:
                best = (balance, claim_id)
        return best[1] if best else None

    def _support(self, observation: dict[str, Any]) -> list[str]:
        ids: list[str] = []
        archive = observation.get("archive_record_if_read") or {}
        if archive.get("evidence_id"):
            ids.append(str(archive["evidence_id"]))
        for row in observation.get("question_answers") or []:
            if row.get("evidence_id"):
                ids.append(str(row["evidence_id"]))
        return ids

    # ------------------------------------------------------------------- act
    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        cards = observation.get("public_statement_cards") or {}
        if cards:
            self.cards = {str(key): str(value.get("text")) for key, value in cards.items()}
            self.speakers = {
                str(key): str(value.get("speaker")) for key, value in cards.items()
            }

        archive = observation.get("archive_record_if_read")
        if archive and not self.excluded:
            text = str(archive.get("text", ""))
            for name, config in MAP14_LOCK_NAMES.items():
                if name in text:
                    self.excluded.add(config)

        wrong = int(observation.get("wrong_submissions") or 0)
        if wrong > self.last_wrong:
            if self.last_submitted is not None:
                self.rejected.add(self.last_submitted)
            self.last_wrong = wrong

        location = str(observation.get("location"))
        belief = self._belief(observation)

        if not self.excluded:
            if location == "A":
                return {"tool": "read_archive"}
            return {
                "tool": "move",
                "edge_id": _map14_edge(observation, _map14_next_hop(observation, "A")),
            }

        remaining = int(observation.get("questions_remaining") or 0)
        if remaining > 0 and len(self._configs(belief)) > 1:
            claim_id = self._best_claim(belief)
            if claim_id is not None:
                if location != "P":
                    return {
                        "tool": "move",
                        "edge_id": _map14_edge(
                            observation, _map14_next_hop(observation, "P")
                        ),
                    }
                self.asked.add(claim_id)
                return {"tool": "ask", "claim_id": claim_id}

        configs = self._configs(belief) or [
            config for config in MAP14_CONFIGS if config not in self.excluded
        ]
        choice = configs[0] if configs else MAP14_CONFIGS[0]
        pair = next(
            ((config, priest) for config, priest in belief if config == choice),
            (choice, "A_priest"),
        )

        if self.compare_before_submit and observation.get("comparison_record") is None:
            if location != "O":
                return {
                    "tool": "move",
                    "edge_id": _map14_edge(observation, _map14_next_hop(observation, "O")),
                }
            return {
                "tool": "compare_evidence",
                "choice": pair[0],
                "person_id": pair[1],
                "support_evidence_ids": self._support(observation),
            }

        if location != "J":
            return {
                "tool": "move",
                "edge_id": _map14_edge(observation, _map14_next_hop(observation, "J")),
            }
        self.last_submitted = choice
        return {"tool": "submit_configuration", "choice": choice}


class Map14NoCompare(Map14Heuristic):
    """消融：跳过 ``compare_evidence``，直接提交同一信念。"""

    name = "ablation_no_compare"
    compare_before_submit = False


class Map14BlindTwoSubmissions:
    """旁路证据：不读档案、不问、不比对，直接到 J 依次盲交 A、B。

    3 种锁型 + 1 次容错 ⇒ 盲交两种锁型在 6/9 个隐藏状态上直接开门。它不是
    公开启发式，只用于证明“成功判据不要求任何证词推理”。
    """

    name = "ablation_blind_two_submissions"
    ORDER = ("A_sun_wheel", "B_crescent")

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.submitted = 0

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        location = str(observation.get("location"))
        if location != "J":
            return {
                "tool": "move",
                "edge_id": _map14_edge(observation, _map14_next_hop(observation, "J")),
            }
        choice = self.ORDER[min(self.submitted, len(self.ORDER) - 1)]
        self.submitted += 1
        return {"tool": "submit_configuration", "choice": choice}


# --------------------------------------------------------------------- MAP-15
MAP15_COLORS = ("red", "blue", "gold", "green")
MAP15_STATIC_COMPLEMENT = {"red": "blue", "blue": "red", "gold": "green", "green": "gold"}


class Map15Heuristic:
    """每区先 inspect（0 tick），按“偶数同色 / 奇数互补”算目标色再选门。

    互补对优先从公开 ``training_sample_log`` 的奇数相位成功样例学习；遇到训练区
    没出现过的墙色时，用“剩下未配对的两种颜色必须互为补色”推出，再迁移到 T。
    """

    name = "public_heuristic"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.predicted = False
        self.recorded = False

    def _learned_complement(
        self, observation: dict[str, Any], wall: str
    ) -> str:
        learned: dict[str, str] = {}
        for sample in observation.get("training_sample_log") or []:
            if sample.get("parity_before_choice") == "odd" and sample.get("result") == "passed":
                learned[str(sample.get("wall_color"))] = str(sample.get("chosen_door_color"))
        if wall in learned:
            return learned[wall]
        used = set(learned) | set(learned.values())
        remaining = [color for color in MAP15_COLORS if color not in used and color != wall]
        if len(remaining) == 1:
            return remaining[0]
        return MAP15_STATIC_COMPLEMENT[wall]

    def _target(self, observation: dict[str, Any], wall: str) -> str:
        if observation.get("current_tick_parity") == "even":
            return wall
        return self._learned_complement(observation, wall)

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        area = str(observation.get("area"))
        if observation.get("gate_open") or area == "EXIT":
            return {"tool": "choose_door", "slot_index": 1}
        if not observation.get("inspected_current_area"):
            return {"tool": "inspect_symbols", "area": area}

        wall = str(observation.get("current_wall_symbol_color_if_inspected"))
        doors = [
            str(color)
            for color in (
                observation.get("current_door_colors_in_ephemeral_slot_order_if_inspected")
                or []
            )
        ]
        target = self._target(observation, wall)
        slot = doors.index(target) + 1 if target in doors else 1

        if area == "T" and not self.predicted:
            self.predicted = True
            return {"tool": "predict_transition", "answer": target}
        if area == "T" and not self.recorded:
            self.recorded = True
            samples = [
                str(sample.get("sample_id"))
                for sample in observation.get("training_sample_log") or []
                if sample.get("result") == "passed"
            ]
            return {
                "tool": "record_rule",
                "rule_id": "R_EVEN_SAME_ODD_COMPLEMENT",
                "supporting_sample_ids": samples,
            }
        return {"tool": "choose_door", "slot_index": slot}


class Map15NoProbe(Map15Heuristic):
    """消融 / 旁路证据：完全不 inspect、不 predict，走固定槽位序列 1→2→2→3。

    这个序列不是从公开 Observation 推出来的（盲猜命中率 1/108），它的用途是
    证明“存在一条不需要更新世界模型的固定路径直接通关”。
    """

    name = "ablation_no_probe"
    SEQUENCE = (1, 2, 2, 3)

    def reset(self) -> None:
        super().reset()
        self.step = 0

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del observation, history
        index = min(self.step, len(self.SEQUENCE) - 1)
        self.step += 1
        return {"tool": "choose_door", "slot_index": self.SEQUENCE[index]}


class Map15NoRuleTransfer(Map15Heuristic):
    """消融：只“偶数同色 / 奇数也选墙色”，完全没有互补对与相位模型。"""

    name = "ablation_no_rule_transfer"

    def _target(self, observation: dict[str, Any], wall: str) -> str:
        return wall


HEURISTICS: dict[str, type[Any]] = {
    "MAP-13": Map13Heuristic,
    "MAP-14": Map14Heuristic,
    "MAP-15": Map15Heuristic,
}

ABLATIONS: dict[str, dict[str, type[Any]]] = {
    "MAP-13": {"no_direction_nail": Map13NoDirectionNail},
    "MAP-14": {
        "no_compare": Map14NoCompare,
        "blind_two_submissions": Map14BlindTwoSubmissions,
    },
    "MAP-15": {
        "no_probe": Map15NoProbe,
        "no_rule_transfer": Map15NoRuleTransfer,
    },
}

__all__ = [
    "ABLATIONS",
    "HEURISTICS",
    "Map13Heuristic",
    "Map13NoDirectionNail",
    "Map14BlindTwoSubmissions",
    "Map14Heuristic",
    "Map14NoCompare",
    "Map15Heuristic",
    "Map15NoProbe",
    "Map15NoRuleTransfer",
]
