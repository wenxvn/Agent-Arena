"""V7 offline, trace-derived capability measurement layer.

V7 does not change any V4/V5/V6 environment, Action contract, prompt, trace
writer, ledger, or registry. It only reads already-produced episode traces (or
deterministic replays) and computes separately registered per-map metrics.
"""

from __future__ import annotations

from agent_arena.v7.metrics.registry import (
    all_specs,
    compute_metrics,
    implemented_map_ids,
    spec_for,
)

__all__ = ["all_specs", "compute_metrics", "implemented_map_ids", "spec_for"]
