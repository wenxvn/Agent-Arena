"""V10 地图协议：在 V8 ``MapEnvironment`` 之上增加 seed 化实例、密封真值与 V10 指标。

V10 地图只在 ``agent_arena.v10.runtime`` 中实现；V8/V4 文件只读导入。每张 V10 图
必须声明：

- ``RULE_VERSION``：规则版本标签（写进 rule_hash 的来源文件即可追溯）；
- ``SEED_SPACE``：预登记的环境 seed 集合；
- ``scenario_descriptor()``：随 seed 改变的**公开**实例参数（不得含隐藏真值）；
- ``sealed_truth()``：随 seed 改变的隐藏真值，只进入 hash 与 judge，不进入 Observation；
- ``METRIC_SPECS`` 与 ``v10_metrics()``：五态 V10 指标；
- ``mechanism_triggered()``：本局核心机制是否被真实触发。
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, ClassVar

from agent_arena.v10.metrics.schema import MetricSpec, MValue
from agent_arena.worlds.scenario_v8.base import MapEnvironment


def stable_pick(label: str, seed: int, options: tuple[Any, ...]) -> Any:
    """按 ``sha256(label|seed)`` 从预登记选项中确定性选取，不依赖 PYTHONHASHSEED。"""

    digest = sha256(f"{label}|{seed}".encode()).digest()
    return options[int.from_bytes(digest[:8], "big") % len(options)]


def canonical_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(text.encode("utf-8")).hexdigest()


class V10Map(MapEnvironment):
    """V10 地图共同协议。"""

    RULE_VERSION: ClassVar[str] = ""
    SEED_SPACE: ClassVar[tuple[int, ...]] = (0, 1, 2)
    METRIC_SPECS: ClassVar[tuple[MetricSpec, ...]] = ()
    PRIMARY_METRIC: ClassVar[str] = ""

    def __init__(self, *, seed: int = 0, step_limit: int = 160) -> None:
        if seed not in self.SEED_SPACE:
            raise ValueError(f"{self.map_id} V10 未预登记环境 seed {seed}")
        self.environment_seed = seed
        super().__init__(seed=seed, step_limit=step_limit)

    def reset(self, seed: int) -> dict[str, Any]:
        if seed not in self.SEED_SPACE:
            raise ValueError(f"{self.map_id} V10 未预登记环境 seed {seed}")
        self.environment_seed = seed
        return super().reset(seed)

    # ------------------------------------------------------------------ contract
    def scenario_descriptor(self) -> dict[str, Any]:
        raise NotImplementedError

    def sealed_truth(self) -> dict[str, Any]:
        raise NotImplementedError

    def v10_metrics(self) -> dict[str, MValue]:
        raise NotImplementedError

    def mechanism_triggered(self) -> bool:
        raise NotImplementedError

    def public_rules(self) -> tuple[str, ...]:
        """写进 system prompt 的公开规则（接口透明，不含答案）。"""

        return ()

    # ------------------------------------------------------------------ helpers
    def truth_seal(self) -> str:
        return canonical_hash(self.sealed_truth())

    def metrics(self) -> dict[str, Any]:
        return {key: value.as_dict() for key, value in self.v10_metrics().items()}


__all__ = ["V10Map", "canonical_hash", "stable_pick"]
