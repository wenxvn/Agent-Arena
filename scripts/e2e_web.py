"""V11 浏览器端到端验收（Playwright + 系统 Chrome）。

覆盖：首页 → 离线演示 → 运行监控 → 结果 → 导出 JSON → 历史。

用法（会自动启动一个临时 Streamlit，不污染本机 runs/web）：

    uv run --with playwright --with streamlit python scripts/e2e_web.py --start

或复用已启动的服务：

    uv run --with playwright python scripts/e2e_web.py --url http://127.0.0.1:8501
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


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


def _run_flow(page: Page, url: str) -> dict[str, Any]:
    page.goto(url, wait_until="networkidle")
    page.get_by_text("地图大厅", exact=True).first.wait_for(timeout=30_000)
    page.get_by_role("button", name=re.compile("离线演示")).first.click()
    page.get_by_text("动作时间线", exact=True).first.wait_for(timeout=30_000)
    page.get_by_role("button", name="查看结果").first.wait_for(timeout=60_000)
    page.get_by_role("button", name="查看结果").first.click()
    page.get_by_text("逐步回放", exact=True).first.wait_for(timeout=30_000)
    page.get_by_text("导出", exact=True).first.wait_for(timeout=30_000)
    page.get_by_text("版本与安全", exact=True).first.wait_for(timeout=30_000)
    body = page.locator("body").inner_text()
    assert "指标（五态）" in body
    assert "导出" in body
    assert "版本与安全" in body

    with page.expect_download() as download_info:
        page.get_by_role("button", name="回放 JSON").first.click()
    download = download_info.value
    path = download.path()
    assert path is not None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    text = json.dumps(payload, ensure_ascii=False)
    assert payload["schema_version"] == "v11-web-replay-1"
    assert "sealed_truth" not in text
    assert "judge_state" not in text
    assert "sk-" not in text
    assert payload["result"]["state"] in {"SUCCEEDED", "FAILED", "BUDGET_REACHED"}

    page.wait_for_timeout(1_500)
    page.goto(
        f"{url}/?view=%E5%8E%86%E5%8F%B2%E4%B8%8E%E5%AF%B9%E7%85%A7",
        wait_until="networkidle",
    )
    page.get_by_text("本地同模型成绩榜（P2）", exact=True).first.wait_for(
        timeout=30_000
    )
    history = page.locator("body").inner_text()
    assert "历史与对照" in history
    assert "本地同模型成绩榜（P2）" in history
    return {
        "state": payload["result"]["state"],
        "run_id": payload["run"]["run_id"],
        "steps": len(payload["steps"]),
        "download_bytes": Path(path).stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true", help="自动启动临时 Streamlit")
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--port", type=int, default=8511)
    args = parser.parse_args()

    process: subprocess.Popen[bytes] | None = None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    url = args.url
    try:
        if args.start:
            temporary = tempfile.TemporaryDirectory(prefix="agent-arena-e2e-")
            runs_dir = Path(temporary.name) / "runs" / "web"
            process = _start_server(args.port, runs_dir)
            url = f"http://127.0.0.1:{args.port}"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            result = _run_flow(page, url)
            browser.close()
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
