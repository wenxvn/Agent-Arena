"""MAP-05 V10 基线：窗口排程的 Oracle、公开启发式与消融（DCR-V10-27）。

Oracle 由同一份**只读公开信息**的排程器离线展开成动作脚本；启发式是同一逻辑的在线版本。
消融分别移除：共享供电切换、按窗口发送、窗口顺序、校准前置。
"""

from __future__ import annotations

from typing import Any

from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.worlds.scenario_v8.models import V8Action

EDGE_OF = {"R": "C_R", "B": "C_B", "W": "C_W"}
MAX_WAIT = 8  # V8Action.turns/ticks 的公开上限


def _wait_action(ticks: int) -> dict[str, Any]:
    return {"tool": "wait", "ticks": max(1, min(MAX_WAIT, ticks))}


class WindowPolicy:
    """按窗口起点排序的排程策略，只读 Observation。"""

    def __init__(
        self,
        *,
        name: str = "public_window_scheduler",
        use_power: bool = True,
        send: bool = True,
        order: str = "earliest",
        calibrate: bool = True,
    ) -> None:
        self.name = name
        self.use_power = use_power
        self.send = send
        self.order = order
        self.calibrate = calibrate

    def reset(self) -> None:
        return None

    def _target(self, observation: dict[str, Any]) -> str | None:
        windows = observation["windows"]
        transmitted = observation["transmitted"]
        pending = [station for station in windows if not transmitted[station]]
        if not pending:
            return None
        key = (lambda station: windows[station][0]) if self.order == "earliest" else (
            lambda station: -windows[station][0]
        )
        return str(sorted(pending, key=key)[0])

    def act(
        self, observation: dict[str, Any], history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        del history
        windows = observation["windows"]
        transmitted = observation["transmitted"]
        location = observation["location"]
        station = self._target(observation)
        if station is None:
            return _wait_action(1)
        if location == "C":
            if not self.use_power:
                return _wait_action(1)
            if observation["power_target"] != station:
                return {"tool": "switch_power", "station": station}
            return {"tool": "move", "edge_id": EDGE_OF[station]}
        if transmitted.get(location):
            # 当前塔已完成：回 C 换电
            return {"tool": "move", "edge_id": EDGE_OF[location]}
        tick = int(observation["tick"])
        calibration = int(observation["calibration"][location])
        if self.calibrate and calibration == 0:
            return {"tool": "interact", "target_id": location, "operation": "calibrate_align"}
        if self.calibrate and calibration == 1:
            return {
                "tool": "interact",
                "target_id": location,
                "operation": "calibrate_phase_lock",
            }
        start, end = windows[location]
        if not self.send:
            # 错过窗口：一直等到窗口结束（用于 late_send 消融）
            return _wait_action(min(MAX_WAIT, max(1, end - tick + 1)))
        if tick + 1 < start:
            return _wait_action(start - tick - 1)
        if tick + 1 > end:
            return _wait_action(1)
        return {"tool": "interact", "target_id": location, "operation": "send_signal"}


def HEURISTIC() -> WindowPolicy:
    return WindowPolicy()


def _script(seed: int, policy: WindowPolicy, *, budget: int = 60) -> list[dict[str, Any]]:
    environment = create_environment("MAP-05", environment_seed=seed)
    actions: list[dict[str, Any]] = []
    while not environment.is_terminal and len(actions) < budget:
        observation = environment.observe()
        payload = policy.act(observation, [])
        action = V8Action.model_validate(payload, strict=True)
        if not environment.accepts(action):
            raise AssertionError(f"MAP-05 oracle 生成了非法动作：{payload}")
        environment.step(action)
        actions.append(payload)
    if not environment.is_success:
        raise AssertionError(
            f"MAP-05 seed {seed} 排程不可行（status={environment.status.value}）"
        )
    return actions


def oracle_actions(seed: int) -> list[dict[str, Any]]:
    return _script(seed, WindowPolicy(name="oracle"))


ABLATIONS = {
    "no_power_switch": lambda: WindowPolicy(name="no_power_switch", use_power=False),
    "late_send": lambda: WindowPolicy(name="late_send", send=False),
    "wrong_order": lambda: WindowPolicy(name="wrong_order", order="latest"),
    "no_calibration": lambda: WindowPolicy(name="no_calibration", calibrate=False),
}

__all__ = ["ABLATIONS", "EDGE_OF", "HEURISTIC", "WindowPolicy", "oracle_actions"]
