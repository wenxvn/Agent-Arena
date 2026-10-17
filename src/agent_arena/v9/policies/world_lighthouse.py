"""V9 lighthouse 世界（MAP-04 / MAP-05 / MAP-06）公开启发式策略。

运行时只读公开 Observation 与自己的 history，不导入 Environment、judge_state、
Oracle 或 Trace。编写策略时用到了一部分只存在于冻结规则代码里的事实（例如
``wait`` 的 turns/ticks 数值就是推进的 tick 数、``switch_power`` 只能在 C 执行、
MAP-06 的暴露边与风险增量）；这些事实**没有**出现在公开 prompt 中，逐条标注见
``docs/v9/maps/MAP-04-audit.md`` / ``MAP-05-audit.md`` / ``MAP-06-audit.md`` 第 3 节。

三个策略的目标是"在公开 Observation 上可复现"，不是复刻 Oracle：
MAP-04 用相位算术走潮汐门；MAP-05 用窗口表排程；MAP-06 用风险预算做保守加固。
"""

from __future__ import annotations

from typing import Any

Action = dict[str, Any]

#: 动作参数的上限来自 ``V8Action`` 的字段约束（turns/ticks ∈ [1, 8]）。
_MAX_WAIT = 8


def _move(edge_id: str) -> Action:
    return {"tool": "move", "edge_id": edge_id}


def _wait(ticks: int) -> Action:
    return {"tool": "wait", "ticks": max(1, min(_MAX_WAIT, ticks))}


def _wait_turns(turns: int) -> Action:
    """MAP-04 的 wait 字段名是 ``turns``，不是 ``ticks``。"""

    return {"tool": "wait", "turns": max(1, min(_MAX_WAIT, turns))}


def _interact(target_id: str, operation: str) -> Action:
    return {"tool": "interact", "target_id": target_id, "operation": operation}


# --------------------------------------------------------------------------- MAP-04
class Map04Heuristic:
    """潮汐密道：在相位空间里算"最短可行等待"，用涨潮门而不是绕行。

    公开依据：``tide_phase``、``tide_period``、``open_phases``、``visible_edges``、
    ``inventory``、``wick_location``、``lamp_wick_fitted``、``lamp_lit``。
    策略只读当前相位，不推测绝对 tick（MAP-04 不公开 tick）。
    """

    name = "public_heuristic"

    #: 绕行段到 T 的父节点表，仅用于意外落到绕行路时的自恢复。
    PARENT: dict[str, tuple[str, str]] = {
        "B1": ("T_B1", "T"),
        "B2": ("B1_B2", "B1"),
        "B3": ("B2_B3", "B2"),
        "B4": ("B3_B4", "B3"),
        "D": ("B4_D", "B4"),
        "S": ("T_S", "T"),
    }

    def reset(self) -> None:
        """无跨局状态：每个决策只由当前 Observation 决定。"""

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        phase = int(observation["tide_phase"])
        period = int(observation["tide_period"])
        safe = tuple(int(item) for item in observation["open_phases"])
        carrying = "wick" in list(observation["inventory"])
        fitted = bool(observation["lamp_wick_fitted"])
        lit = bool(observation["lamp_lit"])

        if location == "T":
            if carrying and not fitted:
                return {"tool": "interact", "target": "lamp", "choice": "fit_wick"}
            if fitted and not lit:
                return {"tool": "interact", "target": "lamp", "choice": "ignite"}
            return _move("T_S")
        if location == "S":
            if carrying:
                return _move("T_S")
            if phase in safe:
                return _move("S_G")
            return _wait_turns(self._wait_for_safe(phase, period, safe))
        if location == "G":
            if not carrying:
                return {"tool": "pickup", "item_id": "wick"}
            if phase in safe:
                return _move("S_G")
            return _wait_turns(self._wait_for_safe(phase, period, safe))
        edge, _parent = self.PARENT.get(location, ("T_S", "T"))
        return _move(edge)

    @staticmethod
    def _wait_for_safe(phase: int, period: int, safe: tuple[int, ...]) -> int:
        for turns in range(1, period + 1):
            if (phase + turns) % period in safe:
                return turns
        return 1


class Map04DetourShortcut:
    """消融：完全不进潮汐门，永远走六段绕行海岸路。

    用来验证"绕行本身也够快"这一旁路：绕行 15 步完成，而救援截止在 tick 18。
    """

    name = "detour_shortcut"

    TO_G = {"T": "T_B1", "B1": "B1_B2", "B2": "B2_B3", "B3": "B3_B4", "B4": "B4_D", "D": "G_D"}
    TO_T = {"D": "B4_D", "B4": "B3_B4", "B3": "B2_B3", "B2": "B1_B2", "B1": "T_B1"}

    def reset(self) -> None:
        """无跨局状态：每个决策只由当前 Observation 决定。"""

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        carrying = "wick" in list(observation["inventory"])
        fitted = bool(observation["lamp_wick_fitted"])
        lit = bool(observation["lamp_lit"])
        if location == "T":
            if carrying and not fitted:
                return {"tool": "interact", "target": "lamp", "choice": "fit_wick"}
            if fitted and not lit:
                return {"tool": "interact", "target": "lamp", "choice": "ignite"}
            return _move(self.TO_G["T"])
        if location == "G":
            if not carrying:
                return {"tool": "pickup", "item_id": "wick"}
            return _move("G_D")
        if carrying:
            return _move(self.TO_T.get(location, "G_D"))
        return _move(self.TO_G.get(location, "T_B1"))


class Map04NoPhaseWait:
    """消融：忽略 ``tide_phase``，看到 S_G 就直接过。"""

    name = "no_phase_wait"

    def reset(self) -> None:
        """无跨局状态：每个决策只由当前 Observation 决定。"""

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        carrying = "wick" in list(observation["inventory"])
        fitted = bool(observation["lamp_wick_fitted"])
        lit = bool(observation["lamp_lit"])
        if location == "T":
            if carrying and not fitted:
                return {"tool": "interact", "target": "lamp", "choice": "fit_wick"}
            if fitted and not lit:
                return {"tool": "interact", "target": "lamp", "choice": "ignite"}
            return _move("T_S")
        if location == "S":
            return _move("T_S") if carrying else _move("S_G")
        if location == "G":
            return {"tool": "pickup", "item_id": "wick"} if not carrying else _move("S_G")
        return _move(Map04Heuristic.PARENT.get(location, ("T_S", "T"))[0])


# --------------------------------------------------------------------------- MAP-05
class Map05Heuristic:
    """三束信号：按窗口结束时间排序，在 C 切电，只用一个空等段对齐首个窗口。

    公开依据：``location``、``tick``、``power_target``、``calibration``、
    ``transmitted``、``windows``、``visible_edges``。策略不读 schedule_chart
    （窗口本来就在 Observation 里），因此 ``idle_ticks`` 只在已校准站点等待时才
    增长，本策略把等待全部放在 C。
    """

    name = "public_heuristic"
    TRAVEL = {"R": 1, "B": 2, "W": 3}
    EDGE = {"R": "C_R", "B": "C_B", "W": "C_W"}

    def reset(self) -> None:
        """无跨局状态：每个决策只由当前 Observation 决定。"""

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        tick = int(observation["tick"])
        power = observation["power_target"]
        calibration = dict(observation["calibration"])
        transmitted = dict(observation["transmitted"])
        windows = {
            name: (int(span[0]), int(span[1]))
            for name, span in observation["windows"].items()
        }

        pending = [name for name in windows if not transmitted[name]]
        if not pending:
            return _wait(1)
        target = min(pending, key=lambda name: (windows[name][1], windows[name][0]))

        if location != "C":
            station = location
            if power != station:
                return _move(self.EDGE.get(station, "C_R"))
            done = int(calibration.get(station, 0))
            if done == 0:
                return _interact(station, "calibrate_align")
            if done == 1:
                return _interact(station, "calibrate_phase_lock")
            if not transmitted[station]:
                return _interact(station, "send_signal")
            return _move(self.EDGE.get(station, "C_R"))

        if power != target:
            return {"tool": "switch_power", "station": target}
        # 在 C 等：此时目标的 calibration 必为 0，等待不计 idle_ticks。
        travel = self.TRAVEL[target]
        completion = tick + travel + 3  # align + phase_lock + send
        start = windows[target][0]
        if completion < start:
            return _wait(start - completion)
        return _move(self.EDGE[target])


class Map05NoPowerSwitch:
    """消融：从不切电，直接去站点校准（复现 V8 R0 的 STATION_UNPOWERED 循环）。"""

    name = "no_power_switch"
    EDGE = {"R": "C_R", "B": "C_B", "W": "C_W"}

    def reset(self) -> None:
        """无跨局状态：每个决策只由当前 Observation 决定。"""

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        windows = dict(observation["windows"])
        transmitted = dict(observation["transmitted"])
        pending = [name for name in windows if not transmitted[name]]
        target = (
            min(pending, key=lambda name: (windows[name][1], windows[name][0]))
            if pending
            else "R"
        )
        if location == "C":
            return _move(self.EDGE[target])
        station = location
        if int(dict(observation["calibration"]).get(station, 0)) < 2:
            return _interact(station, "calibrate_align")
        if not transmitted[station]:
            return _interact(station, "send_signal")
        return _move(self.EDGE.get(station, "C_R"))


class Map05NoWindowWait:
    """消融：校准完立刻发射，不把发射完成 tick 对齐到窗口。"""

    name = "no_window_wait"
    TRAVEL = {"R": 1, "B": 2, "W": 3}
    EDGE = {"R": "C_R", "B": "C_B", "W": "C_W"}

    def reset(self) -> None:
        """无跨局状态：每个决策只由当前 Observation 决定。"""
        self._sent: set[str] = set()

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        power = observation["power_target"]
        calibration = dict(observation["calibration"])
        transmitted = dict(observation["transmitted"])
        windows = dict(observation["windows"])
        pending = [name for name in windows if not transmitted[name] and name not in self._sent]
        if not pending:
            return _wait(1)
        target = min(pending, key=lambda name: (windows[name][1], windows[name][0]))

        if location != "C":
            station = location
            if power != station:
                return _move(self.EDGE.get(station, "C_R"))
            done = int(calibration.get(station, 0))
            if done == 0:
                return _interact(station, "calibrate_align")
            if done == 1:
                return _interact(station, "calibrate_phase_lock")
            self._sent.add(station)
            return _interact(station, "send_signal")
        if power != target:
            return {"tool": "switch_power", "station": target}
        return _move(self.EDGE[target])


# --------------------------------------------------------------------------- MAP-06
class Map06Heuristic:
    """暴风眼：在公开风险预算下选择"先加固再修"的稳健路线。

    公开依据：``location``、``risk``、``risk_budget``、``deadline_tick``、
    ``storm_shield``、``forecast_accuracy``、``prior_short``/``prior_long``。
    判据（保守）：未加固修复落在长风暴下会耗尽 risk_budget=4，因此加固是唯一的
    稳健方案；该路线 5 个决策、tick 10 完成，留 4 tick 余量，不需要 forecast。

    注意：``forecast`` 只改变时间成本，不改变成功与否，所以本策略不读预报。
    """

    name = "public_heuristic"

    def reset(self) -> None:
        """无跨局状态：每个决策只由当前 Observation 决定。"""

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        shield = bool(observation["storm_shield"])
        restored = bool(observation["lamp_restored"])
        if restored:
            return _wait(1)
        if location == "Q":
            return _move("M_Q")
        if location == "M":
            return _move("M_G")
        if location == "G":
            return _move("G_P") if shield else _interact("G", "harden")
        if location == "P":
            return _interact("P", "repair_lighthouse")
        return _move("G_P")


class Map06Shortcut:
    """消融：只执行直达动作（Q→P 直达边 + 立即修复），不读预报、不加固。

    这是 V8 三局实际走成的路径：seed 0 的天气是 short，所以 2 个决策即成功；
    在 seed 5–9（long）同一路径必然 RESOURCE_EXHAUSTED。
    """

    name = "shortcut"

    def reset(self) -> None:
        """无跨局状态：每个决策只由当前 Observation 决定。"""

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        if location == "Q":
            return _move("Q_P")
        return _interact("P", "repair_lighthouse")


class Map06ForecastTrusting:
    """消融：读一次预报并按字面执行（80% 条件预报的朴素用法）。

    用于测量"信息价值"是否被兑现：seed 9 的真实天气是 long、预报是 short，
    这条策略在 seed 9 必然 RESOURCE_EXHAUSTED。
    """

    name = "forecast_trusting"

    def reset(self) -> None:
        """无跨局状态：每个决策只由当前 Observation 决定。"""

    def act(self, observation: dict[str, Any], history: list[dict[str, Any]]) -> Action:
        del history
        location = str(observation["location"])
        reading = observation["forecast_reading"]
        queries = int(observation["forecast_queries"])
        shield = bool(observation["storm_shield"])
        if reading is None and queries == 0 and location == "Q":
            return {"tool": "inspect", "target_id": "forecast"}
        if reading == "long":
            if location == "Q":
                return _move("M_Q")
            if location == "M":
                return _move("M_G")
            if location == "G":
                return _move("G_P") if shield else _interact("G", "harden")
            return _interact("P", "repair_lighthouse")
        if location == "Q":
            return _move("Q_P")
        return _interact("P", "repair_lighthouse")


HEURISTICS: dict[str, type[Map04Heuristic | Map05Heuristic | Map06Heuristic]] = {
    "MAP-04": Map04Heuristic,
    "MAP-05": Map05Heuristic,
    "MAP-06": Map06Heuristic,
}

ABLATIONS: dict[str, dict[str, type[Any]]] = {
    "MAP-04": {
        "detour_shortcut": Map04DetourShortcut,
        "no_phase_wait": Map04NoPhaseWait,
    },
    "MAP-05": {
        "no_power_switch": Map05NoPowerSwitch,
        "no_window_wait": Map05NoWindowWait,
    },
    "MAP-06": {
        "shortcut": Map06Shortcut,
        "forecast_trusting": Map06ForecastTrusting,
    },
}

__all__ = [
    "ABLATIONS",
    "HEURISTICS",
    "Map04DetourShortcut",
    "Map04Heuristic",
    "Map04NoPhaseWait",
    "Map05Heuristic",
    "Map05NoPowerSwitch",
    "Map05NoWindowWait",
    "Map06ForecastTrusting",
    "Map06Heuristic",
    "Map06Shortcut",
]
