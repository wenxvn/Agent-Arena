"""把 pytest JUnit XML 的失败用例转成 GitHub Actions 注解。

用法（CI 失败时）：
    python scripts/ci_failures.py pytest-report.xml

GitHub 会把 ``::error::`` 行渲染为 check-run annotation，便于在没有日志
下载权限时定位失败用例。本脚本只读 XML，不改变 pytest 的退出码。
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    path = Path(args[0] if args else "pytest-report.xml")
    if not path.is_file():
        print(f"::warning::找不到 {path}，无法汇总失败用例")
        return 0
    root = ET.parse(path).getroot()
    failed = 0
    total = 0
    for case in root.iter("testcase"):
        total += 1
        for tag in ("failure", "error"):
            node = case.find(tag)
            if node is None:
                continue
            failed += 1
            name = f"{case.get('classname', '?')}::{case.get('name', '?')}"
            raw = (node.get("message") or node.text or tag).strip()
            first = raw.splitlines()[0] if raw else tag
            print(f"::error title=pytest::{name}: {first[:600]}")
    print(f"::notice::pytest 用例 {total}，失败/错误 {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
