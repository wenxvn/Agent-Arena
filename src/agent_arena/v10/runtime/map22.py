"""MAP-22 V10｜无地图的丛林：遮蔽、分岔与跨阶段位置记忆（DCR-V10-12）。

V9 的根因：`write_memory` 完全可选——同一 DFS 导航 **0 次写记忆也 12 决策通关**；
公开信息里也没有“必须记住路线才能返程”的结构。V10 的修复：

- **遮蔽**：Agent 只知道当前节点的路标（sign）与可用方位（bearings），**看不到全图**，
  也看不到相邻节点是什么；`observe_signpost` 只补充当前路标的特征（用于自证记忆）；
- **分岔**：每个 seed 的迷宫是“主径 + 死胡同”，深度 5–7，营地与遗迹之间没有直达边；
  死胡同会消耗步数，探索不靠记忆就很容易超预算；
- **跨阶段位置记忆**：必须先到遗迹 `check_goal`，再返回营地 `return_to_camp`；
  runner 只给策略最近 5 条 history，深度 > 5 的返程无法只靠上下文完成，
  `write_memory` 是唯一跨阶段通道（写入内容原样出现在 `agent_notes`）；
- 4 个预登记迷宫：深度、分岔位置与方位指派的 seed 化，sign 名与节点 id 不重合。

主指标 `mission_success`（两阶段都完成）；`route_recall`（写入的方位序列与真实路线
逐项一致的比例）、`wasted_moves`（非最短路径上的移动数）作为次指标/护栏。
"""

from __future__ import annotations

import random
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

BEARINGS = ("north", "east", "south", "west")
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}
SIGN_WORDS = (
    "mossy",
    "split",
    "leaning",
    "hollow",
    "scorched",
    "pale",
    "hooked",
    "cracked",
    "twin",
    "silent",
)
MOVE_BUDGET = 44


class Maze22:
    """确定性种子迷宫：主径 0..depth，外加若干死胡同。"""

    def __init__(self, seed: int, depth: int, branches: tuple[int, ...]) -> None:
        rng = random.Random(f"map22-v10|{seed}")
        self.depth = depth
        # 主径
        path = list(range(depth + 1))
        edges: list[tuple[int, int]] = [(path[index], path[index + 1]) for index in range(depth)]
        next_id = depth + 1
        for anchor in branches:
            edges.append((anchor, next_id))
            next_id += 1
        self.node_count = next_id
        # 方位指派：每个节点内方位互不相同，且父子边不共用一个方位
        assignment: dict[int, dict[str, int]] = {node: {} for node in range(next_id)}
        used: dict[int, set[str]] = {node: set() for node in range(next_id)}
        for index, (a, b) in enumerate(edges):
            if index < depth:
                parent, child = a, b
                choices = [bearing for bearing in BEARINGS if bearing not in used[parent]]
                bearing = choices[rng.randrange(len(choices))]
                used[parent].add(bearing)
                assignment[parent][bearing] = child
                used[child].add(OPPOSITE[bearing])
                assignment[child][OPPOSITE[bearing]] = parent
            else:
                choices = [bearing for bearing in BEARINGS if bearing not in used[a]]
                bearing = choices[rng.randrange(len(choices))]
                used[a].add(bearing)
                assignment[a][bearing] = b
                used[b].add(OPPOSITE[bearing])
                assignment[b][OPPOSITE[bearing]] = a
        self.moves = assignment
        words = rng.sample(SIGN_WORDS, min(len(SIGN_WORDS), next_id))
        self.signs = {
            node: ("camp" if node == 0 else "ruin" if node == depth else f"{words[node]}_{node}")
            for node in range(next_id)
        }
        self.start = 0
        self.goal = depth
        self.shortest_moves = depth

    def bearings(self, node: int) -> list[str]:
        return sorted(self.moves[node])


VARIANTS: dict[int, Maze22] = {
    0: Maze22(0, 5, (2, 3)),
    1: Maze22(1, 6, (1, 4)),
    2: Maze22(2, 6, (2, 4, 5)),
    3: Maze22(3, 7, (3, 5)),
}


class Map22V10Environment(V10Map):
    map_id = "MAP-22"
    title = "无地图的丛林"
    world = "jungle"
    level = "简单"
    RULE_VERSION = "v10.map22.1"
    SEED_SPACE = tuple(sorted(VARIANTS))
    SHAPES: dict[str, set[frozenset[str]]] = {
        "observe_signpost": {frozenset({"tool"})},
        "move": {frozenset({"tool", "bearing"})},
        "write_memory": {frozenset({"tool", "facts"})},
        "check_goal": {frozenset({"tool"})},
        "return_to_camp": {frozenset({"tool"})},
    }
    PUBLIC_FIELDS = frozenset(
        {
            "current_sign",
            "distinctive_feature",
            "bearings",
            "agent_notes",
            "ruin_recorded",
            "moves_used",
            "move_budget",
            "goal",
        }
    )
    PRIMARY_METRIC = "map22.v10.mission_success"
    METRIC_SPECS = (
        MetricSpec(
            "map22.v10.mission_success",
            "primary",
            "higher",
            "先 check_goal 再 return_to_camp",
            "1",
            censored_rule="截尾 → CENSORED",
        ),
        MetricSpec(
            "map22.v10.route_recall",
            "secondary",
            "higher",
            "写入的方位序列与真实路线的最长匹配比例",
            "写入过记忆的局（1）",
            zero_denominator="未写记忆 → NOT_APPLICABLE",
        ),
        MetricSpec(
            "map22.v10.wasted_moves",
            "guardrail",
            "lower",
            "实际移动数 − 该种子最短往返移动数",
            "—",
            unit="count",
            valid_range=(0.0, 60.0),
        ),
        MetricSpec(
            "map22.v10.memory_writes",
            "diagnostic",
            "none",
            "write_memory 调用次数",
            "—",
            unit="count",
            valid_range=(0.0, 60.0),
        ),
        MetricSpec(
            "map22.v10.goal_recorded",
            "secondary",
            "higher",
            "是否先完成遗迹打卡再返程",
            "1",
        ),
    )

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        super().__init__(seed=seed, step_limit=step_limit)

    # ------------------------------------------------------------------ instance
    def _reset_state(self, seed: int) -> None:
        self.maze = VARIANTS[seed]
        self.position = self.maze.start
        self.route: list[str] = []
        self.notes: list[dict[str, str]] = []
        self.observed = False
        self.ruin_recorded = False
        self.moves_used = 0
        self.memory_writes = 0
        self.wasted = 0
        self._cost = 1

    def scenario_descriptor(self) -> dict[str, Any]:
        return {
            "depth": self.maze.depth,
            "node_count": self.maze.node_count,
            "move_budget": MOVE_BUDGET,
            "bearings": list(BEARINGS),
        }

    def sealed_truth(self) -> dict[str, Any]:
        return {
            "depth": self.maze.depth,
            "goal_sign": self.maze.signs[self.maze.goal],
            "graph": {
                str(node): {bearing: other for bearing, other in sorted(links.items())}
                for node, links in sorted(self.maze.moves.items())
            },
        }

    def public_rules(self) -> tuple[str, ...]:
        return (
            "你在一片没有地图的丛林里，只能看到**当前**路标与可用方位（north/east/south/west）。",
            "move(bearing) 沿该方位走到相邻节点；方位不可用 → BEARING_NOT_AVAILABLE。",
            "observe_signpost 耗 1 tick，给出当前路标的特征（用于自证记忆），不改变位置。",
            "write_memory(facts) 把 1–3 条 {key,value} 写进 agent_notes；内容原样保留，"
            "是跨阶段唯一可靠通道。",
            "先在遗迹 check_goal，再回到营地 return_to_camp 才算完成。",
            f"移动次数上限 {MOVE_BUDGET}；相邻节点在你走过去之前不可见。",
        )

    # ------------------------------------------------------------------ public
    def _public(self) -> dict[str, Any]:
        sign = self.maze.signs[self.position]
        return {
            "current_sign": sign,
            "distinctive_feature": (
                f"{sign}: weathered marks" if self.observed else None
            ),
            "bearings": self.maze.bearings(self.position),
            "agent_notes": [dict(note) for note in self.notes],
            "ruin_recorded": self.ruin_recorded,
            "moves_used": self.moves_used,
            "move_budget": MOVE_BUDGET,
            "goal": "先到遗迹完成记录，再回到营地；路线只能靠自己记。",
        }

    # ------------------------------------------------------------------ rules
    def _apply(self, action: V8Action) -> str:
        self._cost = 1
        tool = action.tool
        if tool == "observe_signpost":
            self.observed = True
            return f"SIGN_OBSERVED:{self.maze.signs[self.position]}"
        if tool == "move":
            return self._move(action)
        if tool == "write_memory":
            return self._write_memory(action)
        if tool == "check_goal":
            if self.position != self.maze.goal:
                self._cost = 0
                return "NOT_AT_RUIN"
            self.ruin_recorded = True
            return "RUIN_RECORDED"
        if tool == "return_to_camp":
            if self.position != self.maze.start:
                self._cost = 0
                return "NOT_AT_CAMP"
            if not self.ruin_recorded:
                self._cost = 0
                return "RUIN_NOT_RECORDED"
            self._succeed("RETURNED_TO_CAMP_WITH_RUIN_RECORD")
            return "RETURNED_TO_CAMP_WITH_RUIN_RECORD"
        return "ACTION_NOT_ALLOWED"

    def _move(self, action: V8Action) -> str:
        bearing = action.bearing
        links = self.maze.moves[self.position]
        if bearing not in links:
            self._cost = 0
            return "BEARING_NOT_AVAILABLE"
        if self.moves_used + 1 > MOVE_BUDGET:
            self._fail("MOVE_BUDGET_EXHAUSTED")
            return "MOVE_BUDGET_EXHAUSTED"
        self.position = links[str(bearing)]
        self.moves_used += 1
        self.route.append(str(bearing))
        self.observed = False
        return f"MOVED_TO:{self.maze.signs[self.position]}"

    def _write_memory(self, action: V8Action) -> str:
        facts = action.facts or []
        if not facts:
            self._cost = 0
            return "INVALID_MEMORY_PAYLOAD"
        parsed: list[dict[str, str]] = []
        for item in facts:
            if not isinstance(item, dict):
                self._cost = 0
                return "INVALID_MEMORY_PAYLOAD"
            key = item.get("key")
            value = item.get("value")
            if not isinstance(key, str) or not isinstance(value, str):
                self._cost = 0
                return "INVALID_MEMORY_PAYLOAD"
            parsed.append({"key": key, "value": value})
        self.notes.extend(parsed)
        self.notes = self.notes[-12:]
        self.memory_writes += 1
        return "MEMORY_WRITTEN"

    def _action_cost(self, action: V8Action) -> int:
        del action
        return self._cost

    # ------------------------------------------------------------------ judge
    def judge_state(self) -> dict[str, Any]:
        return {
            "environment_seed": self.environment_seed,
            "node": self.position,
            "sign": self.maze.signs[self.position],
            "depth": self.maze.depth,
            "route": list(self.route),
            "notes": [dict(note) for note in self.notes],
            "ruin_recorded": self.ruin_recorded,
            "moves_used": self.moves_used,
            "memory_writes": self.memory_writes,
            "truth_seal": self.truth_seal(),
        }

    def _written_route(self) -> list[str]:
        route: list[str] = []
        for note in self.notes:
            if note["key"] == "bearing":
                route.append(note["value"])
            elif note["key"] == "path_state":
                route = [item for item in note["value"].split(",") if item]
        return route

    def v10_metrics(self) -> dict[str, MValue]:
        running = self.status.value == "step_limit_reached"
        if running:
            success: MValue = censored("截尾")
        else:
            success = valid(int(self.is_success))
        written = self._written_route()
        if not written:
            recall: MValue = not_applicable("未写记忆")
        else:
            matched = 0
            for index, bearing in enumerate(written):
                if index < len(self.route) and self.route[index] == bearing:
                    matched += 1
            recall = ratio(matched, len(self.route)) if self.route else valid(0)
        wasted = max(0, self.moves_used - 2 * self.maze.shortest_moves)
        return {
            "map22.v10.mission_success": success,
            "map22.v10.route_recall": recall,
            "map22.v10.wasted_moves": valid(wasted),
            "map22.v10.memory_writes": valid(self.memory_writes),
            "map22.v10.goal_recorded": valid(int(self.ruin_recorded)),
        }

    def mechanism_triggered(self) -> bool:
        """核心机制：写入过可返程的方位记忆。"""

        return any(note["key"] in ("bearing", "path_state") for note in self.notes)


def oracle_actions(environment_seed: int) -> list[dict[str, Any]]:
    """真值感知：沿主径走到遗迹，逐步写方位，再原路反向返回。"""

    maze = VARIANTS[environment_seed]
    # 主径：0 → depth（贪心找最短路径）
    adjacency = {
        node: {bearing: other for bearing, other in links.items()}
        for node, links in maze.moves.items()
    }
    parent: dict[int, tuple[int, str]] = {}
    seen = {maze.start}
    frontier = [maze.start]
    while frontier:
        current = frontier.pop(0)
        if current == maze.goal:
            break
        for bearing, other in sorted(adjacency[current].items()):
            if other in seen:
                continue
            seen.add(other)
            parent[other] = (current, bearing)
            frontier.append(other)
    forward: list[str] = []
    cursor = maze.goal
    while cursor != maze.start:
        previous, bearing = parent[cursor]
        forward.append(bearing)
        cursor = previous
    forward.reverse()

    actions: list[dict[str, Any]] = [{"tool": "observe_signpost"}]
    for bearing in forward:
        actions.append(
            {
                "tool": "write_memory",
                "facts": [{"key": "bearing", "value": bearing}],
            }
        )
        actions.append({"tool": "move", "bearing": bearing})
    actions.append({"tool": "check_goal"})
    for bearing in reversed(forward):
        actions.append({"tool": "move", "bearing": OPPOSITE[bearing]})
    actions.append({"tool": "return_to_camp"})
    return actions


__all__ = [
    "BEARINGS",
    "MOVE_BUDGET",
    "Map22V10Environment",
    "Maze22",
    "OPPOSITE",
    "VARIANTS",
    "oracle_actions",
]
