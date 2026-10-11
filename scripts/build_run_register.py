"""从 runs/ 与 results/ 生成 V1 运行台账 CSV（离线，不调用模型）。

每条记录至少含 experiment_id、episode_id、world/version/hash、agent、
provider/model、prompt、条件开关、step_limit、seed、outcome、action_count、
input/output tokens（缺失记 N/A）；来源缺失记 unavailable。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
from pathlib import Path

TRACE_FIELDS = [
    "experiment_id",
    "episode_id",
    "source_path",
    "world",
    "world_version",
    "world_definition_id",
    "world_definition_hash",
    "agent",
    "provider",
    "model",
    "prompt",
    "base_prompt",
    "recent_history",
    "stuck_recovery",
    "phase_context",
    "step_limit",
    "seed",
    "outcome",
    "action_count",
    "input_tokens",
    "output_tokens",
    "error_type",
]


def _trace_row(path: Path, experiment_id: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {k: "unavailable" for k in TRACE_FIELDS} | {
            "experiment_id": experiment_id,
            "source_path": str(path),
            "error_type": "unreadable",
        }
    header = data if isinstance(data, dict) and "provenance" in data else {}
    prov = header.get("provenance", {}) if isinstance(header, dict) else {}
    steps = data.get("steps", []) if isinstance(data, dict) else []
    executed = sum(1 for s in steps if isinstance(s, dict) and s.get("action") is not None)
    outcome = data.get("outcome", "unavailable")
    error_type = ""
    if outcome == "provider_error":
        error_type = "provider_error"
    elif outcome not in ("success", "step_limit", "invalid_action_limit"):
        error_type = str(outcome)
    in_tok = sum(int(s.get("input_tokens") or 0) for s in steps if isinstance(s, dict))
    out_tok = sum(int(s.get("output_tokens") or 0) for s in steps if isinstance(s, dict))
    get = lambda *keys: next(
        (prov.get(k, header.get(k, "unavailable")) for k in keys
         if prov.get(k, header.get(k, None)) is not None),
        "unavailable",
    )
    return {
        "experiment_id": experiment_id,
        "episode_id": header.get("episode_id", path.stem),
        "source_path": str(path),
        "world": get("world"),
        "world_version": get("world_version"),
        "world_definition_id": get("world_definition_id"),
        "world_definition_hash": get("world_definition_hash"),
        "agent": header.get("agent", "unavailable"),
        "provider": header.get("provider", "unavailable"),
        "model": prov.get("model_name", header.get("model", "unavailable")),
        "prompt": header.get("prompt_version", "unavailable"),
        "base_prompt": prov.get("base_prompt_version", "unavailable"),
        "recent_history": prov.get("recent_history_window",
                                   prov.get("recent_history_enabled", "unavailable")),
        "stuck_recovery": prov.get("stuck_recovery_enabled", "unavailable"),
        "phase_context": prov.get("public_phase_context_enabled", "unavailable"),
        "step_limit": prov.get("step_limit", header.get("step_limit", "unavailable")),
        "seed": header.get("seed", "unavailable"),
        "outcome": outcome,
        "action_count": executed,
        "input_tokens": in_tok if steps else "N/A",
        "output_tokens": out_tok if steps else "N/A",
        "error_type": error_type,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 V1 运行台账 CSV")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output", default="docs/research/v1/assets/run_register.csv")
    args = parser.parse_args()

    rows: list[dict] = []
    for path in sorted(glob.glob(f"{args.runs_dir}/**/*.json", recursive=True)):
        p = Path(path)
        if p.name.startswith("benchmark_") or p.name.startswith("failure_analysis"):
            continue
        rows.append(_trace_row(p, experiment_id=p.parent.name))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TRACE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
