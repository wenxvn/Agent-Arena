"""独立复算注册表。"""

from __future__ import annotations

from agent_arena.v9.metric_checks import part_a, part_b
from agent_arena.v9.metric_checks.base import Check


def registry() -> dict[str, list[Check]]:
    merged = {**part_a.CHECKS, **part_b.CHECKS}
    for module_name in ("part_c", "part_d"):
        try:
            module = __import__(
                f"agent_arena.v9.metric_checks.{module_name}", fromlist=["CHECKS"]
            )
        except ModuleNotFoundError:
            continue
        merged.update(getattr(module, "CHECKS", {}))
    return merged


__all__ = ["registry"]
