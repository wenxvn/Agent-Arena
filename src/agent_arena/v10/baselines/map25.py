"""MAP-25 V10 基线：出舱依赖链的 Oracle、公开启发式与消融（DCR-V10-33）。

- Oracle：按实例起始位置展开的固定方案；
- 启发式：只读 Observation 的状态机（装备/气闸/阵列/诊断/维修）；
- 消融：不挂绳、不诊断、工具不全、不检查阵列。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.worlds.scenario_v8.maps.map25 import DIAGNOSIS
from agent_arena.worlds.scenario_v8.models import V8Action

REPAIR_TOOLS = ["diagnostic_unit", "wrench"]
TOOL_ORDER = ("eva_suit", "diagnostic_unit", "wrench")

BASE_PLAN: tuple[dict[str, Any], ...] = (
    {"tool": "equip", "item_id": "eva_suit"},
    {"tool": "equip", "item_id": "diagnostic_unit"},
    {"tool": "equip", "item_id": "wrench"},
    {"tool": "inspect", "target": "equipment"},
    {"tool": "move", "to": "A"},
    {"tool": "equip", "item_id": "safety_tether"},
    {"tool": "depressurize"},
    {"tool": "eva_exit"},
    {"tool": "inspect", "target": "array"},
    {"tool": "diagnose", "device_id": "diagnostic_unit"},
    {
        "tool": "repair",
        "target_id": "array_fuse_B",
        "tool_ids": list(REPAIR_TOOLS),
        "diagnosis_code": DIAGNOSIS,
    },
    {"tool": "return_to_A"},
    {"tool": "pressurize"},
    {"tool": "move", "to": "T"},
    {"tool": "move", "to": "H"},
)


def _plan(start: str) -> list[dict[str, Any]]:
    prefix = [{"tool": "move", "to": "T"}] if start != "T" else []
    return [*prefix, *[dict(item) for item in BASE_PLAN]]


class EvaPolicy:
    def __init__(
        self,
        *,
        name: str = "public_eva_chain",
        tether: bool = True,
        diagnose: bool = True,
        repair_tools: tuple[str, ...] = ("diagnostic_unit", "wrench"),
        inspect_array: bool = True,
    ) -> None:
        self.name = name
        self.tether = tether
        self.diagnose = diagnose
        self.repair_tools = repair_tools
        self.inspect_array = inspect_array
        self._equipment_inspected = False

    def reset(self) -> None:
        self._equipment_inspected = False

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
        del history
        location = observation["location"]
        tools = observation["carried_tools"]
        if not observation["suit_worn"]:
            if location == "T":
                return {"tool": "equip", "item_id": "eva_suit"}
            return {"tool": "move", "to": "T"}
        if not self._equipment_inspected:
            if location == "T":
                self._equipment_inspected = True
                return {"tool": "inspect", "target": "equipment"}
            return {"tool": "move", "to": "T"}
        for tool in TOOL_ORDER[1:]:
            if tool not in tools:
                if location == "T":
                    return {"tool": "equip", "item_id": tool}
                return {"tool": "move", "to": "T"}
        if self.tether and not observation["tether_attached"]:
            if location == "A":
                return {"tool": "equip", "item_id": "safety_tether"}
            return {"tool": "move", "to": "A"}
        if not observation["array_repaired"]:
            if observation["airlock_pressure"] != "VACUUM":
                if location == "A":
                    return {"tool": "depressurize"}
                return {"tool": "move", "to": "A"}
            if location != "S":
                if location == "A":
                    return {"tool": "eva_exit"}
                return {"tool": "move", "to": "A"}
            if self.inspect_array and observation["array_surface_symptom"] is None:
                return {"tool": "inspect", "target": "array"}
            if self.diagnose and observation["diagnosis_code_if_obtained"] is None:
                return {"tool": "diagnose", "device_id": "diagnostic_unit"}
            return {
                "tool": "repair",
                "target_id": "array_fuse_B",
                "tool_ids": list(self.repair_tools),
                "diagnosis_code": DIAGNOSIS if self.diagnose else None,
            }
        if location == "S":
            return {"tool": "return_to_A"}
        if location == "A":
            if observation["airlock_pressure"] != "PRESSURIZED":
                return {"tool": "pressurize"}
            return {"tool": "move", "to": "T"}
        if location == "T":
            return {"tool": "move", "to": "H"}
        return {"tool": "wait", "turns": 1}


def HEURISTIC() -> EvaPolicy:
    return EvaPolicy()


def oracle_actions(seed: int) -> list[dict[str, Any]]:
    environment = create_environment("MAP-25", environment_seed=seed)
    plan = _plan(str(environment.observe()["location"]))
    for payload in plan:
        if environment.is_terminal:
            break
        action = V8Action.model_validate(payload, strict=True)
        if not environment.accepts(action):
            raise AssertionError(f"MAP-25 方案含非法动作：{payload}")
        environment.step(action)
    if not environment.is_success:
        raise AssertionError(
            f"MAP-25 seed {seed} 方案不可行（{environment.status.value}）"
        )
    return plan


ABLATIONS = {
    "no_tether": lambda: EvaPolicy(name="no_tether", tether=False),
    "no_diagnosis": lambda: EvaPolicy(name="no_diagnosis", diagnose=False),
    "wrong_tools": lambda: EvaPolicy(name="wrong_tools", repair_tools=("wrench",)),
    "skip_array_inspection": lambda: EvaPolicy(name="skip_array_inspection", inspect_array=False),
}

__all__ = ["ABLATIONS", "BASE_PLAN", "EvaPolicy", "HEURISTIC", "oracle_actions"]
