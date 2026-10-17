"""V9 volcano 世界的公开启发式策略（MAP-19 / MAP-20 / MAP-21）。

约束：策略只读取公开 Observation 与自己的历史记录；不 import 环境、
不访问 ``judge_state``、Oracle 动作或指标内部状态。

三个策略各自带一个显式消融，用于检验指标能否区分“机制正确”与“机制缺失”：

- MAP-19 ``no_lag_load_curtailment``：按最终冷却向量与稳态负荷立即运行，不做阀门
  延迟窗口内的降载；
- MAP-20 ``no_load_management``：保持初始 FULL 负荷、不改直供流量；
- MAP-21 ``shortcut_direct_evac``：只执行一次 ``move(O_E)``，不测量、不采样、
  不加固。
"""

from __future__ import annotations

from typing import Any

ZONES = ("A", "B", "C")

#: MAP-19 的最终稳定冷却向量：总量 4（运行时的总阀量上限；该上限与每区 0–2 的
#: 约束并未写进 prompt，属接口缺口），A/B/C 各以 2/1/1 负荷对应 2/1/1 冷却，
#: 净变化为 0。
MAP19_COOLING = [2, 1, 1]
#: 阀门延迟窗口（t+2）内的降载向量：只为把温升控制在安全线内，不追求产能。
MAP19_RAMP_LOADS = [1, 1, 1]
MAP19_STEADY_LOADS = [2, 1, 1]

#: MAP-20 已公开的直供上限内的一组稳定分配：三区各 2.0 单位，合计 6.0 单位，
#: 不消耗水源旁路、不产生 20% 损耗。
MAP20_DIRECT = [20, 20, 20]


def _vector(observation: dict[str, Any], field: str, default: int = 0) -> list[int]:
    raw = observation.get(field) or {}
    return [int(raw.get(zone, default)) for zone in ZONES]


class Map19Heuristic:
    """MAP-19：先排队冷却，再在 2 tick 延迟窗口内降载，最后回到稳态负荷。

    公开依据：``pending_cooling_commands`` 给出 ``effective_tick``，
    ``active_cooling`` 与 ``current_load_levels`` 逐 tick 可见；
    ``temperature_bands`` 足以确认三区未进入 ``NEAR_LIMIT``/``OVERHEAT``。
    策略不需要知道初始精确温度：延迟窗口用 1 档负荷，任何 ``WARM`` 上限（7）
    都只会升到 9，仍在公开的“不超过 10”之内。
    """

    name = "public_heuristic"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._stage = 0

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        active = _vector(observation, "active_cooling")
        loads = _vector(observation, "current_load_levels")
        tick = int(observation.get("tick") or 0)

        if self._stage == 0:
            self._stage = 1
            return {"tool": "set_cooling", "set_cooling": list(MAP19_COOLING)}
        if self._stage == 1:
            self._stage = 2
            return {"tool": "adjust_loads", "adjust_loads": list(MAP19_RAMP_LOADS)}
        if tick < 2:
            # 阀门尚未成熟：保持低负荷，避免把 2 tick 的温升叠进临界区。
            return {"tool": "wait"}
        if self._stage == 2 or (
            loads != MAP19_STEADY_LOADS and active == MAP19_COOLING
        ):
            self._stage = 3
            if loads != MAP19_STEADY_LOADS:
                return {"tool": "adjust_loads", "adjust_loads": list(MAP19_STEADY_LOADS)}
        return {"tool": "wait"}


class Map19NoLagLoadCurtailment(Map19Heuristic):
    """消融：按最终冷却向量与最终稳态负荷立即运行，完全忽略阀门延迟窗口。

    预期结果仍是成功（临界等号安全），但 ``temperature_exceedance_area``
    会从 0 升到 22，用于检验主指标是否区分“延迟感知”与“延迟无感”。
    """

    name = "no_key_mechanism"

    def reset(self) -> None:
        self._stage = 0

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        if self._stage == 0:
            self._stage = 1
            return {"tool": "set_cooling", "set_cooling": list(MAP19_COOLING)}
        if self._stage == 1:
            self._stage = 2
            return {"tool": "adjust_loads", "adjust_loads": list(MAP19_STEADY_LOADS)}
        return {"tool": "wait"}


class Map20Heuristic:
    """MAP-20：直供 2.0/2.0/2.0，三区统一 REDUCED，热点出现再落 IDLE。

    公开依据：``flow_rules`` 给出水源、支管、区阀与旁路损耗；``
    previous_tick_flow_ledger`` 每 tick 回显 ``delivered_tenths``；
    ``temperature_bands`` 与单区精确读数提供闭环反馈。流程本身不依赖
    隐藏的负荷热系数：只要某区进入 ``HOT`` 就锁存为 IDLE，温度只降不升。
    """

    name = "public_heuristic"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._read_done = False
        self._flow_set = False
        self._idle: set[str] = set()

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        if not self._read_done:
            self._read_done = True
            return {"tool": "read_temperature", "station": "A"}
        if not self._flow_set:
            self._flow_set = True
            return {"tool": "set_flow", "set_flow_tenths": list(MAP20_DIRECT)}

        bands = observation.get("temperature_bands") or {}
        for zone in ZONES:
            if bands.get(zone) in {"HOT", "OVERHEAT"}:
                self._idle.add(zone)
        target = ["IDLE" if zone in self._idle else "REDUCED" for zone in ZONES]
        current = observation.get("current_load_modes") or {}
        if [current.get(zone) for zone in ZONES] != target:
            return {"tool": "adjust_loads", "adjust_loads": target}
        return {"tool": "wait"}


class Map20NoLoadManagement(Map20Heuristic):
    """消融：不改负荷（保持初始 FULL），只把直供设成 2.0/2.0/2.0。

    预期在 tick 2 触发 ``THERMAL_OVERHEAT``（A 区 70→90→110），
    用于检验 ``max_node_exceedance`` / ``key_node_runaway`` 的判别力。
    """

    name = "no_key_mechanism"

    def reset(self) -> None:
        self._read_done = False
        self._flow_set = False

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        if not self._read_done:
            self._read_done = True
            return {"tool": "read_temperature", "station": "A"}
        if not self._flow_set:
            self._flow_set = True
            return {"tool": "set_flow", "set_flow_tenths": list(MAP20_DIRECT)}
        return {"tool": "wait"}


class Map21Heuristic:
    """MAP-21：先在 O 做一次 2 tick 测量，再从 O 直达 E（6 tick）。

    公开依据：``available_edges`` 明确给出 ``O_E`` 的 6 tick；初始
    ``posterior_over_eruption_ticks`` 已经公开了喷发时刻只可能是
    12/16/20。因此 2+6=8 < 12，测量后的最坏到达仍早于最早喷发。
    策略保留测量只是为了不丢弃公开后验，它并不改变撤离动作。
    """

    name = "public_heuristic"

    #: 由远及近的回撤顺序；主运行只会用到 ``O_E``。
    EDGE_ORDER = ("O_E", "S_E", "W_S", "R_W", "O_R")

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._measured = False

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        edges = observation.get("available_edges") or {}
        if observation.get("location") == "E":
            return self._fallback(edges)
        if observation.get("measurement_available") and not self._measured:
            self._measured = True
            return {"tool": "measure"}
        return self._fallback(edges)

    def _fallback(self, edges: dict[str, Any]) -> dict[str, Any]:
        for edge in self.EDGE_ORDER:
            if edge in edges:
                return {"tool": "move", "edge_id": edge}
        if edges:
            return {"tool": "move", "edge_id": sorted(edges)[0]}
        return {"tool": "reinforce_sample_case"}


class Map21ShortcutDirectEvac(Map21Heuristic):
    """消融（shortcut baseline）：只执行 ``move(O_E)``，一次决策到 E。

    这条基线不使用测量、样品与加固；只要它同样成功，就说明隐藏喷发时刻
    的风险决策机制没有被成功条件实际要求。
    """

    name = "shortcut_direct_evac"

    def reset(self) -> None:
        self._measured = True

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        edges = observation.get("available_edges") or {}
        return self._fallback(edges)


HEURISTICS: dict[str, type] = {
    "MAP-19": Map19Heuristic,
    "MAP-20": Map20Heuristic,
    "MAP-21": Map21Heuristic,
}

ABLATIONS: dict[str, dict[str, type]] = {
    "MAP-19": {"no_lag_load_curtailment": Map19NoLagLoadCurtailment},
    "MAP-20": {"no_load_management": Map20NoLoadManagement},
    "MAP-21": {"shortcut_direct_evac": Map21ShortcutDirectEvac},
}

__all__ = [
    "ABLATIONS",
    "HEURISTICS",
    "Map19Heuristic",
    "Map19NoLagLoadCurtailment",
    "Map20Heuristic",
    "Map20NoLoadManagement",
    "Map21Heuristic",
    "Map21ShortcutDirectEvac",
]
