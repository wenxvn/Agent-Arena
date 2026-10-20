"""安装 V11 演示运行到本机 runs/web（不覆盖已有运行）。

用法：
    uv run python scripts/install_v11_demo.py
    uv run python scripts/install_v11_demo.py --force
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "v11" / "demo"
TARGET = ROOT / "runs" / "web"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="覆盖同名演示运行")
    args = parser.parse_args()
    runs = sorted(
        path for path in SOURCE.iterdir() if path.is_dir() and path.name.startswith("web-")
    )
    if not runs:
        print("没有找到演示运行。")
        return 1
    TARGET.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    for source in runs:
        target = TARGET / source.name
        if target.exists():
            if not args.force:
                print(f"跳过已存在：{source.name}")
                continue
            shutil.rmtree(target)
        shutil.copytree(source, target)
        installed.append(source.name)
    print(f"已安装 {len(installed)} 个演示运行：")
    for run_id in installed:
        print(f"- {run_id}")
    print(f"打开网页后到「历史与对照」或「结果与回放」查看：{TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
