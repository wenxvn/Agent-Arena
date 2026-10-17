"""V9 公开 prompt 层。

V8 的 prompt 模块保持冻结只读；V9 若需要补充公开规则，只在本模块追加
``V9_PUBLIC_ADDENDA``，并单独记录 prompt hash。这样：

- ``v8_compat`` 臂与 V8 正式 90 局使用完全相同的 system prompt；
- ``v9_fixed`` 臂只多出登记过的公开规则文本，便于同期前后对照。
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from agent_arena.v8.prompts import system_prompt as v8_system_prompt
from agent_arena.worlds.scenario_v8.base import MapEnvironment

#: 每项都是一条**公开规则补充**，不是隐藏真值、不是 Oracle 路径。
#: 只在 V9 的 ``v9_fixed`` 臂生效；``v8_compat`` 臂保持 V8 原文。
V9_PUBLIC_ADDENDA: dict[str, str] = {
    "MAP-05": (
        "switch_power 只能在 C（总电源）执行；在其他位置执行会被拒绝。"
        "send_signal 的结算 tick 必须落在对应窗口内，窗口外发射不会计入有效信号。"
    ),
    "MAP-07": (
        "阀门控制台的 target_id 是 control_panel（不是 console）；set_valve 使用 "
        "arguments={valve_id: v1|v2|v3|v4, open: true|false}；start_pump/stop_pump 在"
        "同一控制台执行。"
    ),
    "MAP-08": (
        "visible_edges 每项格式为 '边名:另一端'，move 只使用冒号前的边名；"
        "inspect 的 target_id 是 ordinary_sensor；压力测试使用 "
        "interact(target_id=X|Y, operation=pressure_test_X|pressure_test_Y)。"
    ),
    "MAP-09": (
        "E 舱与 P 舱之间的隔板开放时，每结算 1 tick 会把 1 单位水从 P 舱推入 E 舱"
        "（water_E +1）；water_E 超过 4 会立即短路失败。在 E 舱执行 "
        "interact(target_id=bulkhead_E_P, operation=isolate_compartment, "
        "arguments={mode: preserve|sacrifice}) 可关闭隔板并立即停止推进；"
        "关舱后 P 舱仍可抽水，但 sacrifice 会使 P 舱不可再进入。"
    ),
    "MAP-10": (
        "fuel_depot 只用于基地供暖；发电机与雪地车只消耗 carried_fuel。"
        "load_fuel 只能在 B 执行，随身容量 5；activate_generator 需要至少 3 单位"
        "随身燃料；雪地车通过 E–W 需要 2 单位。随身燃料不足时动作会立即失败并结束本局。"
    ),
    "MAP-11": (
        "每次 move 都消耗随身补给：短道 B_P_SHORT / P_S_SHORT 各 2，长道每段 1；"
        "携带不足会立即 SUPPLY_SHORTAGE 失败。resupply 只能在 B 执行，容量 8；"
        "救回队员后的负重返程需 loaded_return=true。"
    ),
    "MAP-12": (
        "transfer 的可用无向边为 H_E、E_G、G_S、S_L、H_S、G_L；from_node 与 to_node "
        "必须是该边两端。维修控制器需要 2 件 parts 送到 E。连续 3 天执行 research "
        "才获得 3 分；磨损日未维修会记一次计划违约。"
    ),
    "MAP-16": (
        "release_section 只撤销本车尚未提交的预约，不会释放已被占用的区段；"
        "occupy_siding 只能把与当前节点相邻的侧线 D 预约给指定列车；"
        "两车同时预约同一节点会在 move_train 结算时冲突。"
    ),
    "MAP-25": (
        "舱段邻接为 H–T–A–S（线性）；A 是气闸。舱外每移动一步消耗 1 单位氧气，"
        "维修额外消耗 1；氧气耗尽会立即失败。"
    ),
    "MAP-26": (
        "read_log 的 log_id 是 COMM_LOSS_LAST_TRANSMIT；test 的 test_id 是 bus_load、"
        "antenna_loopback、software_checksum；take_spare/replace 的 part_id 是 "
        "power_regulator、antenna_coupler、software_image。read_log 与 test 在 D，"
        "take_spare 在 B，replace/rollback/restart 在 A。"
    ),
}


def addenda(map_id: str) -> str:
    text = V9_PUBLIC_ADDENDA.get(map_id, "").strip()
    return f"补充公开规则：{text}\n" if text else ""


def system_prompt(
    environment: MapEnvironment,
    *,
    decision_budget: int,
    arm: str = "v9_fixed",
) -> str:
    base = v8_system_prompt(environment, decision_budget=decision_budget)
    if arm == "v8_compat":
        return base
    extra = addenda(environment.map_id)
    return base + extra if extra else base


def prompt_hashes(environment: MapEnvironment, *, decision_budget: int) -> dict[str, str]:
    base = v8_system_prompt(environment, decision_budget=decision_budget)
    fixed = system_prompt(environment, decision_budget=decision_budget, arm="v9_fixed")
    return {
        "v8_compat": sha256(base.encode("utf-8")).hexdigest(),
        "v9_fixed": sha256(fixed.encode("utf-8")).hexdigest(),
    }


def public_rules(map_id: str) -> dict[str, Any]:
    return {"map_id": map_id, "addendum": V9_PUBLIC_ADDENDA.get(map_id, "")}


__all__ = [
    "V9_PUBLIC_ADDENDA",
    "addenda",
    "prompt_hashes",
    "public_rules",
    "system_prompt",
]
