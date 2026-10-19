"""V10 30 图目录：V10 新运行时优先，未改动的图回退到 V8 运行时。

- ``create_environment(map_id, environment_seed)``：V10 图要求 seed 在其预登记
  ``SEED_SPACE`` 中；V8 回退图沿用 V8 构造（其 seed 是否改变实例见 ``seed_effective``）。
- ``rule_hash``：V10 图 = V10 模块源码 sha256；V8 回退图 = ``v8:`` + V8 rule_hash。
- ``scenario_hash``：``(map_id, rule_hash, environment_seed, 公开实例描述, 密封真值封印)``。
- ``metric_hash``：V10 图 = V10 指标 spec hash；V8 回退图 = ``v8:`` + V8 schema hash。
"""

from __future__ import annotations

import importlib
from hashlib import sha256
from pathlib import Path
from typing import Any

from agent_arena.v10.metrics.schema import METRIC_SCHEMA_VERSION, specs_hash
from agent_arena.v10.runtime.base import V10Map, canonical_hash
from agent_arena.worlds.scenario_v8 import catalog as v8_catalog
from agent_arena.worlds.scenario_v8.base import MapEnvironment

MAP_IDS = v8_catalog.MAP_IDS
WORLD_OF = v8_catalog.WORLD_OF
LEVEL_OF = v8_catalog.LEVEL_OF

#: 已有 V10 运行时的地图 -> (模块, 类名)。后续 Batch 追加。
V10_MAPS: dict[str, tuple[str, str]] = {
    "MAP-04": ("agent_arena.v10.runtime.map04", "Map04V10Environment"),
    "MAP-05": ("agent_arena.v10.runtime.map05", "Map05V10Environment"),
    "MAP-01": ("agent_arena.v10.runtime.map01", "Map01V10Environment"),
    "MAP-02": ("agent_arena.v10.runtime.map02", "Map02V10Environment"),
    "MAP-27": ("agent_arena.v10.runtime.map27", "Map27V10Environment"),
    "MAP-07": ("agent_arena.v10.runtime.map07", "Map07V10Environment"),
    "MAP-03": ("agent_arena.v10.runtime.map03", "Map03V10Environment"),
    "MAP-06": ("agent_arena.v10.runtime.map06", "Map06V10Environment"),
    "MAP-08": ("agent_arena.v10.runtime.map08", "Map08V10Environment"),
    "MAP-09": ("agent_arena.v10.runtime.map09", "Map09V10Environment"),
    "MAP-10": ("agent_arena.v10.runtime.map10", "Map10V10Environment"),
    "MAP-11": ("agent_arena.v10.runtime.map11", "Map11V10Environment"),
    "MAP-12": ("agent_arena.v10.runtime.map12", "Map12V10Environment"),
    "MAP-13": ("agent_arena.v10.runtime.map13", "Map13V10Environment"),
    "MAP-14": ("agent_arena.v10.runtime.map14", "Map14V10Environment"),
    "MAP-15": ("agent_arena.v10.runtime.map15", "Map15V10Environment"),
    "MAP-21": ("agent_arena.v10.runtime.map21", "Map21V10Environment"),
    "MAP-22": ("agent_arena.v10.runtime.map22", "Map22V10Environment"),
    "MAP-23": ("agent_arena.v10.runtime.map23", "Map23V10Environment"),
    "MAP-26": ("agent_arena.v10.runtime.map26", "Map26V10Environment"),
    "MAP-24": ("agent_arena.v10.runtime.map24", "Map24V10Environment"),
    "MAP-18": ("agent_arena.v10.runtime.map18", "Map18V10Environment"),
    "MAP-19": ("agent_arena.v10.runtime.map19", "Map19V10Environment"),
    "MAP-20": ("agent_arena.v10.runtime.map20", "Map20V10Environment"),
    "MAP-28": ("agent_arena.v10.runtime.map28", "Map28V10Environment"),
    "MAP-29": ("agent_arena.v10.runtime.map29", "Map29V10Environment"),
    "MAP-30": ("agent_arena.v10.runtime.map30", "Map30V10Environment"),
}

_RUNTIME_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _RUNTIME_DIR.parents[3]


def is_v10(map_id: str) -> bool:
    return map_id in V10_MAPS


def v10_class(map_id: str) -> type[V10Map]:
    module_name, class_name = V10_MAPS[map_id]
    module = importlib.import_module(module_name)
    factory: type[V10Map] = getattr(module, class_name)
    assert issubclass(factory, V10Map)
    return factory


def seed_space(map_id: str) -> tuple[int, ...]:
    if is_v10(map_id):
        return tuple(v10_class(map_id).SEED_SPACE)
    return (0, 1, 2)


def create_environment(
    map_id: str,
    *,
    environment_seed: int = 0,
    step_limit: int | None = None,
) -> MapEnvironment:
    if map_id not in MAP_IDS:
        raise ValueError(f"未注册的地图：{map_id}")
    if is_v10(map_id):
        factory = v10_class(map_id)
        if step_limit is None:
            environment: MapEnvironment = factory(seed=environment_seed)
        else:
            environment = factory(seed=environment_seed, step_limit=step_limit)
        environment.source_hash = rule_hash(map_id)
        environment.condition_id = "v10"
        return environment
    return v8_catalog.create_environment(
        map_id, seed=environment_seed, step_limit=step_limit or 160
    )


def rule_hash(map_id: str) -> str:
    if is_v10(map_id):
        module_name, _ = V10_MAPS[map_id]
        path = _RUNTIME_DIR / f"{module_name.rsplit('.', 1)[1]}.py"
        sources = v10_class(map_id).RULE_SOURCES
        if not sources:
            return sha256(path.read_bytes()).hexdigest()
        digest = sha256(path.read_bytes())
        for relative in sources:
            digest.update(b"\0" + relative.encode("utf-8") + b"\0")
            digest.update((_REPO_ROOT / relative).read_bytes())
        return digest.hexdigest()
    return "v8:" + v8_catalog.rule_hash(map_id)


def metric_hash(map_id: str) -> str:
    if is_v10(map_id):
        return specs_hash(tuple(v10_class(map_id).METRIC_SPECS))
    from agent_arena.v8.metrics import metric_schema_hash

    return "v8:" + metric_schema_hash(map_id)


def scenario_record(map_id: str, environment_seed: int) -> dict[str, Any]:
    """一个环境 seed 的实例身份：公开描述 + 真值封印，不含真值本身。"""

    environment = create_environment(map_id, environment_seed=environment_seed)
    if isinstance(environment, V10Map):
        descriptor = environment.scenario_descriptor()
        seal = environment.truth_seal()
        runtime = "v10"
    else:
        descriptor = {"v8_condition": environment.condition_id}
        seal = canonical_hash(environment.judge_state())
        runtime = "v8_fallback"
    payload = {
        "map_id": map_id,
        "runtime": runtime,
        "rule_hash": rule_hash(map_id),
        "environment_seed": environment_seed,
        "descriptor": descriptor,
        "truth_seal": seal,
    }
    payload["scenario_hash"] = canonical_hash(payload)
    return payload


def scenario_hash(map_id: str, environment_seed: int) -> str:
    return str(scenario_record(map_id, environment_seed)["scenario_hash"])


def seed_effective(map_id: str, seeds: tuple[int, ...] = (0, 1, 2)) -> bool:
    """不同环境 seed 是否真的产生不同实例（初始 Observation 或密封真值不同）。"""

    fingerprints = set()
    for seed in seeds:
        try:
            environment = create_environment(map_id, environment_seed=seed)
        except ValueError:
            return False
        if isinstance(environment, V10Map):
            fingerprints.add(
                canonical_hash({"obs": environment.observe(), "seal": environment.truth_seal()})
            )
        else:
            observation = dict(environment.observe())
            judge = dict(environment.judge_state())
            judge.pop("seed", None)
            fingerprints.add(canonical_hash({"obs": observation, "judge": judge}))
    return len(fingerprints) == len(seeds)


__all__ = [
    "LEVEL_OF",
    "MAP_IDS",
    "METRIC_SCHEMA_VERSION",
    "V10_MAPS",
    "WORLD_OF",
    "create_environment",
    "is_v10",
    "metric_hash",
    "rule_hash",
    "scenario_hash",
    "scenario_record",
    "seed_effective",
    "seed_space",
    "v10_class",
]
