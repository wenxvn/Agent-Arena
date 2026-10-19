"""MAP-02 V10 基线：事件重排的 Oracle、公开启发式与消融（DCR-V10-29）。

Oracle 复用 V8 已验证的 9 动作方案（`nav_core_then_pod_success`），启发式是同一策略的
Observation 驱动版本；消融分别移除：关闸、救乘员、固定导航核心、及时反应。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.worlds.scenario_v8.models import V8Action

#: V8 手算通过的 9 动作方案（先救乘员、关闸隔离、再固定导航核心、最后进逃生舱）。
PLAN: tuple[dict[str, Any], ...] = (
    {"tool": "move", "edge_id": "C_L1"},
    {"tool": "move", "edge_id": "L1_L2"},
    {"tool": "pickup", "item_id": "crew"},
    {"tool": "move", "edge_id": "L1_L2"},
    {"tool": "move", "edge_id": "C_L1"},
    {"tool": "interact", "target": "center_gate", "choice": "isolate_L1"},
    {"tool": "move", "edge_id": "C_R1"},
    {"tool": "interact", "target": "nav_core", "choice": "brace_in_case"},
    {"tool": "move", "edge_id": "R1_R2"},
)


class ReplanPolicy:
    """按观察标志推进的状态机；只读 Observation。"""

    def __init__(
        self,
        *,
        name: str = "public_replan",
        close_gate: bool = True,
        rescue_crew: bool = True,
        secure_nav: bool = True,
        delay_ticks: int = 0,
    ) -> None:
        self.name = name
        self.close_gate = close_gate
        self.rescue_crew = rescue_crew
        self.secure_nav = secure_nav
        self.delay_ticks = delay_ticks
        self._waited = 0

    def reset(self) -> None:
        self._waited = 0

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        del history
        location = observation["location"]
        if self.delay_ticks and self._waited < self.delay_ticks:
            self._waited += 1
            return {"tool": "wait", "turns": 1}
        if self.rescue_crew and not observation["crew_in_escape_pod"]:
            if not observation["crew_escorted"]:
                if location == "C":
                    return {"tool": "move", "edge_id": "C_L1"}
                if location == "L1":
                    return {"tool": "move", "edge_id": "L1_L2"}
                return {"tool": "pickup", "item_id": "crew"}
            # 已护送：带乘员回 C
            if location == "L2":
                return {"tool": "move", "edge_id": "L1_L2"}
            if location == "L1":
                return {"tool": "move", "edge_id": "C_L1"}
        if self.close_gate and observation["center_gate"] != "closed" and location == "C":
            return {"tool": "interact", "target": "center_gate", "choice": "isolate_L1"}
        if self.secure_nav and not observation["nav_core_secured"]:
            if location == "C":
                return {"tool": "move", "edge_id": "C_R1"}
            if location == "R1":
                return {"tool": "interact", "target": "nav_core", "choice": "brace_in_case"}
        if observation["crew_escorted"] and not observation["crew_in_escape_pod"]:
            if location == "R1":
                return {"tool": "move", "edge_id": "R1_R2"}
        return {"tool": "wait", "turns": 1}


def HEURISTIC() -> ReplanPolicy:
    return ReplanPolicy()


def oracle_actions(seed: int) -> list[dict[str, Any]]:
    """固定 9 动作方案；在每个 seed 上回放验证成功，失败即视为实例不可行。"""

    environment = create_environment("MAP-02", environment_seed=seed)
    for payload in PLAN:
        if environment.is_terminal:
            break
        action = V8Action.model_validate(payload, strict=True)
        if not environment.accepts(action):
            raise AssertionError(f"MAP-02 方案含非法动作：{payload}")
        environment.step(action)
    if not environment.is_success:
        raise AssertionError(
            f"MAP-02 seed {seed} 方案不可行（{environment.status.value}）"
        )
    return [dict(item) for item in PLAN]


ABLATIONS = {
    "no_gate": lambda: ReplanPolicy(name="no_gate", close_gate=False),
    "nav_only": lambda: ReplanPolicy(name="nav_only", rescue_crew=False),
    "crew_only": lambda: ReplanPolicy(name="crew_only", secure_nav=False),
    "late_react": lambda: ReplanPolicy(name="late_react", delay_ticks=3),
}

__all__ = ["ABLATIONS", "HEURISTIC", "PLAN", "ReplanPolicy", "oracle_actions"]
