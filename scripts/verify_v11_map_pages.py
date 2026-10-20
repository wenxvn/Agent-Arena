"""V11 30 图网页映射验收：逐图打开配置页，确认公开目标/规则/契约可渲染。

用法（自动启动临时 Streamlit，不污染本机 runs/web）：

    uv run --with playwright --with streamlit python scripts/verify_v11_map_pages.py --start

或复用已启动服务：

    uv run --with playwright python scripts/verify_v11_map_pages.py --url http://127.0.0.1:8501
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.v10.runtime.catalog import MAP_IDS  # noqa: E402
from agent_arena.web.catalog import DISPLAY_TITLES  # noqa: E402


def _wait_port(port: int, timeout: float = 40.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Streamlit 未在端口 {port} 启动。")


def _start_server(port: int, runs_dir: Path) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    environment["AGENT_ARENA_WEB_RUNS_DIR"] = str(runs_dir)
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ROOT / "src" / "agent_arena" / "ui" / "app.py"),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--client.toolbarMode",
        "minimal",
    ]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_port(port)
    return process


def _check_map(page: Any, url: str, map_id: str) -> None:
    target = f"{url}/?view=%E6%8C%91%E6%88%98%E9%85%8D%E7%BD%AE&map={map_id}"
    page.goto(target, wait_until="networkidle")
    page.get_by_text("公开目标", exact=False).first.wait_for(timeout=30_000)
    body = page.locator("body").inner_text()
    assert map_id in body, f"{map_id} 未出现在页面"
    assert DISPLAY_TITLES[map_id] in body, f"{map_id} 标题未渲染"
    page.get_by_text("公开规则与动作契约", exact=True).first.click()
    page.get_by_text("动作契约（字段类型必须匹配）", exact=True).first.wait_for(timeout=15_000)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--port", type=int, default=8512)
    args = parser.parse_args()

    process: subprocess.Popen[bytes] | None = None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    url = args.url
    failures: list[dict[str, str]] = []
    try:
        if args.start:
            temporary = tempfile.TemporaryDirectory(
                prefix="agent-arena-map-pages-", ignore_cleanup_errors=True
            )
            runs_dir = Path(temporary.name) / "runs" / "web"
            process = _start_server(args.port, runs_dir)
            url = f"http://127.0.0.1:{args.port}"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 1000})
            for map_id in MAP_IDS:
                try:
                    _check_map(page, url, map_id)
                except Exception as exc:  # noqa: BLE001 - collect per-map failure
                    failures.append({"map_id": map_id, "error": type(exc).__name__})
            browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            time.sleep(0.5)
        if temporary is not None:
            temporary.cleanup()

    report = {
        "ok": not failures,
        "maps": len(MAP_IDS),
        "checked": len(MAP_IDS) - len(failures),
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
