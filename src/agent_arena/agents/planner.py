"""Public, explicitly labelled planning assistance for the spaceship world."""

from __future__ import annotations

import re
from pathlib import Path

from agent_arena.agents.memory import MemoryAgent
from agent_arena.arena import Action, Observation, ToolReason, ToolResult, ToolStatus
from agent_arena.llm import DecisionProvider
from agent_arena.llm.protocol import DecisionRequest, ProviderResponse


class PlannerAssistedAgent(MemoryAgent):
    """Use public facts to suggest the next phase without executing actions.

    This is intentionally a separate agent name. The model still selects every
    Action, while the deterministic planner supplies a public route suggestion.
    """

    name = "planner_assisted"
    prompt_version = "planner_assisted_v2"
    base_prompt_version = "react_v11"

    _ROOM_ROUTES: dict[str, dict[str, str]] = {
        "storage_room": {
            "control_room": "corridor",
            "maintenance_room": "corridor",
            "reactor_room": "corridor",
            "escape_pod": "corridor",
        },
        "reactor_room": {
            "control_room": "maintenance_room",
            "storage_room": "maintenance_room",
            "escape_pod": "escape_pod",
        },
        "control_room": {
            "storage_room": "corridor",
            "maintenance_room": "corridor",
            "reactor_room": "corridor",
            "escape_pod": "corridor",
        },
        "corridor": {
            "storage_room": "storage_room",
            "maintenance_room": "maintenance_room",
            "control_room": "control_room",
            "reactor_room": "maintenance_room",
            "escape_pod": "maintenance_room",
        },
        "maintenance_room": {
            "storage_room": "corridor",
            "control_room": "corridor",
            "reactor_room": "reactor_room",
            "escape_pod": "reactor_room",
        },
        "escape_pod": {
            "control_room": "reactor_room",
            "storage_room": "reactor_room",
            "maintenance_room": "reactor_room",
        },
    }

    def __init__(self, provider: DecisionProvider, prompt_path: Path | None = None) -> None:
        super().__init__(provider, prompt_path or self._planner_prompt_path())
        self._power_restored = False
        self._authorization_code: str | None = None

    def _default_prompt_path(self) -> Path:
        return self._planner_prompt_path()

    def reset(self, observation: Observation) -> None:
        super().reset(observation)
        self._power_restored = False
        self._authorization_code = None

    def observe(self, action: Action, result: object, observation: Observation) -> None:
        super().observe(action, result, observation)
        if not isinstance(result, ToolResult):
            return
        if result.reason is ToolReason.POWER_RESTORED and result.status is ToolStatus.SUCCESS:
            self._power_restored = True
        if result.reason is ToolReason.CODE_READ and result.status is ToolStatus.SUCCESS:
            self._authorization_code = _authorization_code(result.summary)

    def finish(self, outcome: object) -> None:
        super().finish(outcome)
        self._power_restored = False
        self._authorization_code = None

    def request(
        self,
        observation: Observation,
        *,
        correction: bool,
        runtime_feedback: str | None = None,
    ) -> ProviderResponse:
        guidance = self._guidance(observation)
        planner_feedback = (
            "公开规划建议（由确定性程序根据公开 Observation 和 ToolResult 生成；"
            "不是隐藏状态，也不代替你执行动作）：\n"
            f"{guidance}"
        )
        combined_feedback = (
            f"{runtime_feedback}\n{planner_feedback}" if runtime_feedback else planner_feedback
        )
        return self._provider.decide(
            DecisionRequest(
                observation=observation,
                system_prompt=self._prompt,
                correction=correction,
                runtime_feedback=combined_feedback,
                memory_data=self._render_memory_data(),
            )
        )

    def _guidance(self, observation: Observation) -> str:
        inventory = set(observation.inventory)
        if "screwdriver" not in inventory or "replacement_fuse" not in inventory:
            if observation.current_room == "storage_room":
                for item in ("screwdriver", "replacement_fuse"):
                    if item not in inventory and item in observation.visible_objects:
                        return (
                            "阶段=收集修理工具。建议下一动作："
                            f"pickup(item={item})，不要离开储物室。"
                        )
                if "storage_crate" in observation.visible_objects:
                    return (
                        "阶段=收集修理工具。当前在储物室且物品尚未出现；"
                        "建议下一动作：inspect(target=storage_crate)。"
                    )
            return self._route_guidance(observation, "storage_room", "收集修理工具")

        if not self._power_restored:
            if observation.current_room == "reactor_room":
                if "reactor_panel" in observation.visible_objects:
                    return (
                        "阶段=恢复主电源。建议下一动作："
                        "use(item=screwdriver,target=reactor_panel)。"
                    )
                if "damaged_fuse" in observation.visible_objects:
                    return (
                        "阶段=恢复主电源。面板已打开；建议下一动作："
                        "use(item=replacement_fuse,target=damaged_fuse)。"
                    )
            return self._route_guidance(observation, "reactor_room", "恢复主电源")

        if self._authorization_code is None:
            if observation.current_room == "control_room":
                if "control_terminal" in observation.visible_objects:
                    return (
                        "阶段=读取授权码。建议下一动作："
                        "read_terminal(target=control_terminal)。"
                    )
            return self._route_guidance(observation, "control_room", "读取授权码")

        if observation.current_room == "escape_pod":
            return (
                "阶段=启动逃生舱。授权码是此前公开终端结果中的 "
                f"{self._authorization_code}；建议下一动作："
                f"use(item={self._authorization_code},target=escape_pod)。"
            )
        return self._route_guidance(observation, "escape_pod", "启动逃生舱")

    def _route_guidance(self, observation: Observation, target: str, phase: str) -> str:
        destination = self._ROOM_ROUTES.get(observation.current_room, {}).get(target)
        if destination and destination in observation.available_exits:
            return f"阶段={phase}。建议下一动作：move(destination={destination})。"
        if destination:
            return (
                f"阶段={phase}。沿当前 Observation 的 available_exits 向 {target} 推进；"
                f"优先选择 {destination}（若可达）。"
            )
        return f"阶段={phase}。当前已到达目标房间，优先处理 visible_objects 中的新目标。"

    @staticmethod
    def _planner_prompt_path() -> Path:
        return Path(__file__).resolve().parents[3] / "prompts" / "react_v11.txt"


def _authorization_code(summary: str) -> str | None:
    match = re.search(r"授权码\s*[：:]\s*([A-Za-z0-9-]+)", summary)
    return match.group(1) if match else None
