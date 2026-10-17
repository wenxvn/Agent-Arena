"""从 30 份逐图审计中提取标签与状态，生成草稿矩阵（供人工复核）。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "docs" / "v9" / "maps"
LABELS = (
    "MEASUREMENT_VALID",
    "INTERFACE_BLOCKED",
    "BUDGET_BLOCKED",
    "RULE_DEFECT",
    "CONSTRUCT_BYPASS",
    "METRIC_DEFECT",
    "INCONCLUSIVE",
)
STATUSES = ("VALIDATED", "NEEDS_REDESIGN", "NEEDS_MORE_EVIDENCE", "BLOCKED")


def _section(text: str, start: str, end: str | None) -> str:
    begin = text.find(start)
    if begin < 0:
        return ""
    if end is None:
        return text[begin:]
    finish = text.find(end, begin + len(start))
    return text[begin : finish if finish > 0 else len(text)]


def main() -> None:
    rows: list[str] = []
    rows.append("| map | 标签 | V9 状态 | 优先级 |")
    rows.append("|---|---|---|---|")
    for index in range(1, 31):
        map_id = f"MAP-{index:02d}"
        path = AUDITS / f"{map_id}-audit.md"
        if not path.is_file():
            rows.append(f"| {map_id} | MISSING | MISSING | - |")
            continue
        text = path.read_text(encoding="utf-8")
        section9 = _section(text, "## 9", "## 10")
        labels: list[str] = []
        for line in section9.splitlines():
            if any(negation in line for negation in ("不标", "不选", "未标", "不判", "不算")):
                continue
            for label in LABELS:
                if f"`{label}`" in line and label not in labels:
                    labels.append(label)
        tail = _section(text, "## 12", None) or text[-800:]
        status = next((item for item in STATUSES if item in tail), "UNKNOWN")
        priority = "-"
        match = re.search(r"P[012]", tail)
        if match:
            priority = match.group(0)
        rows.append(f"| {map_id} | {', '.join(labels) or '-'} | {status} | {priority} |")
    output = ROOT / "runs" / "v9" / "reports" / "status-matrix-draft.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(output)
    print("\n".join(rows))


if __name__ == "__main__":
    main()
