"""Run V6 leakage counter-example checks (offline, no provider)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v6.leakage import audit_all  # noqa: E402


def main() -> None:
    findings = audit_all()
    if findings:
        print("V6 leakage checks FAILED:")
        print(json.dumps(findings, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1)
    print("V6 leakage checks passed: no private truth, oracle route, or unlocked evidence leak.")


if __name__ == "__main__":
    main()
