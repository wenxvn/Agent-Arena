"""V6 instance catalog: builds environments and content-addressed manifests."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from pydantic import BaseModel

from agent_arena.v6.scenes import REVIEW_STATUS, RULE_VERSION, all_scenes
from agent_arena.worlds.scenario_v4.base import ScenarioV4Environment
from agent_arena.worlds.scenario_v4.catalog import source_hash
from agent_arena.worlds.scenario_v4.map08 import Map08Environment
from agent_arena.worlds.scenario_v4.map16 import Map16Environment
from agent_arena.worlds.scenario_v4.map18 import Map18Environment
from agent_arena.worlds.scenario_v4.map22 import Map22Environment
from agent_arena.worlds.scenario_v4.map26 import Map26Environment
from agent_arena.worlds.scenario_v4.map30 import Map30Environment

_MEMORY_CONDITIONS = {"history5": False, "history5_graph_memory": True}
_ALERT_CONDITIONS = {"alert_off": False, "alert_on": True}
_FEEDBACK_CONDITIONS = {
    "free_diagnosis": "full",
    "recovery_full": "full",
    "recovery_structured": "structured",
    "recovery_hidden": "hidden",
}
_CASEBOOK_CONDITIONS = {"history_full": False, "history5": False, "history5_casebook": True}


def _plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _plain(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256(payload).hexdigest()


def scenes() -> dict[str, Any]:
    return all_scenes()


def get_scene(instance_id: str) -> Any:
    registry = all_scenes()
    if instance_id not in registry:
        raise KeyError(f"Unknown V6 instance: {instance_id}")
    return registry[instance_id]


def build_environment(
    scene: Any, condition_id: str, *, seed: int = 0, step_limit: int = 100
) -> ScenarioV4Environment:
    map_id = scene.map_id
    environment: ScenarioV4Environment
    if map_id == "MAP-08":
        environment = Map08Environment(step_limit=step_limit, **scene.env_kwargs())
    elif map_id == "MAP-16":
        environment = Map16Environment(step_limit=step_limit, **scene.env_kwargs())
    elif map_id == "MAP-18":
        if condition_id not in _ALERT_CONDITIONS:
            raise ValueError(f"Unknown MAP-18 condition: {condition_id}")
        environment = Map18Environment(
            alert_enabled=_ALERT_CONDITIONS[condition_id],
            step_limit=step_limit,
            **scene.env_kwargs(),
        )
    elif map_id == "MAP-22":
        if condition_id not in _MEMORY_CONDITIONS:
            raise ValueError(f"Unknown MAP-22 condition: {condition_id}")
        environment = Map22Environment(
            memory_enabled=_MEMORY_CONDITIONS[condition_id],
            step_limit=step_limit,
            disabled_memory_result="MEMORY_DISABLED",
            **scene.env_kwargs(),
        )
    elif map_id == "MAP-26":
        if condition_id not in _FEEDBACK_CONDITIONS:
            raise ValueError(f"Unknown MAP-26 condition: {condition_id}")
        environment = Map26Environment(
            feedback_mode=_FEEDBACK_CONDITIONS[condition_id],
            step_limit=step_limit,
            **scene.env_kwargs(),
        )
    elif map_id == "MAP-30":
        if condition_id not in _CASEBOOK_CONDITIONS:
            raise ValueError(f"Unknown MAP-30 condition: {condition_id}")
        environment = Map30Environment(
            casebook_visible=_CASEBOOK_CONDITIONS[condition_id],
            step_limit=step_limit,
            **scene.env_kwargs(),
        )
    else:  # pragma: no cover - guarded by the scene registry
        raise ValueError(f"Unregistered V6 map: {map_id}")
    environment.condition_id = condition_id
    environment.source_hash = scenario_hash(scene)
    environment.reset(seed)
    return environment


def scenario_hash(scene: Any) -> str:
    return _hash(
        {
            "map_id": scene.map_id,
            "instance_id": scene.instance_id,
            "rule_version": RULE_VERSION,
            "kwargs": _plain(scene.env_kwargs()),
        }
    )


def _private_truth(scene: Any, seed: int, environment: ScenarioV4Environment) -> dict[str, Any]:
    judge = environment.judge_state()
    if scene.map_id == "MAP-08":
        return {"true_leak": judge["true_leak"]}
    if scene.map_id == "MAP-16":
        return {"goals": _plain(scene.goals), "sidings": sorted(scene.sidings)}
    if scene.map_id == "MAP-18":
        return {
            "fault_edge": sorted(scene.fault_edge),
            "fault_window": list(scene.fault_window),
            "fault_enabled": scene.fault_enabled,
        }
    if scene.map_id == "MAP-22":
        return {"target": scene.target}
    if scene.map_id == "MAP-26":
        return {"fault_part": judge["fault_part"]}
    culprit = scene.case.culprit if scene.case is not None else "MARA_VENN"
    return {"culprit": culprit}


def public_initial_state_hash(scene: Any, condition_id: str, seed: int) -> str:
    environment = build_environment(scene, condition_id, seed=seed)
    return _hash(environment.observe().model_dump(mode="json"))


def instance_manifest(scene: Any, *, seed: int = 0) -> dict[str, Any]:
    condition = scene.paired_conditions[0]
    environment = build_environment(scene, condition, seed=seed)
    return {
        "instance_id": scene.instance_id,
        "map_id": scene.map_id,
        "rule_version": RULE_VERSION,
        "source_design": f"worlds/v4/{scene.map_id}",
        "level": scene.level,
        "capability": scene.capability,
        "scenario_hash": scenario_hash(scene),
        "public_initial_state_hash": _hash(environment.observe().model_dump(mode="json")),
        "private_truth_hash": _hash(_private_truth(scene, seed, environment)),
        "oracle_trace": f"runs/v6/instances/{scene.instance_id}/oracle_trace.json",
        "solver_result": f"runs/v6/instances/{scene.instance_id}/solver_result.json",
        "paired_conditions": list(scene.paired_conditions),
        "review_status": REVIEW_STATUS,
        "note": scene.note,
    }


@dataclass(frozen=True)
class V6InstanceSummary:
    instance_id: str
    map_id: str
    level: str
    capability: str
    paired_conditions: tuple[str, ...]


def instance_summaries() -> list[V6InstanceSummary]:
    return [
        V6InstanceSummary(
            instance_id=scene.instance_id,
            map_id=scene.map_id,
            level=scene.level,
            capability=scene.capability,
            paired_conditions=scene.paired_conditions,
        )
        for scene in sorted(all_scenes().values(), key=lambda item: item.instance_id)
    ]


__all__ = [
    "build_environment",
    "get_scene",
    "instance_manifest",
    "instance_summaries",
    "public_initial_state_hash",
    "scenario_hash",
    "scenes",
    "source_hash",
]
