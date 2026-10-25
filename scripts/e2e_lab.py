"""V12 Lab 浏览器端到端验收（Playwright + 系统 Chrome）。

覆盖：首页 → Lab 配置 → 一键离线演示入队 → 监控（父子状态）→ 结果（对照/可视化）
→ 导出报告。

用法（自动启动临时 Streamlit，不污染本机 runs）：

    uv run --with playwright --with streamlit python scripts/e2e_lab.py --start

或复用已启动服务：

    uv run --with playwright python scripts/e2e_lab.py --url http://127.0.0.1:8501
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
from urllib.parse import quote

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LAB_CONFIG = "Lab · 实验配置"
LAB_MONITOR = "Lab · 实验监控"
LAB_RESULT = "Lab · 结果与对照"


def _wait_port(port: int, timeout: float = 40.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Streamlit 未在端口 {port} 启动。")


def _start_server(port: int, web_dir: Path, lab_dir: Path) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    environment["AGENT_ARENA_WEB_RUNS_DIR"] = str(web_dir)
    environment["AGENT_ARENA_LAB_RUNS_DIR"] = str(lab_dir)
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


def _goto_view(page: Page, url: str, view: str) -> None:
    page.goto(f"{url}/?view={quote(view)}", wait_until="networkidle")
    page.wait_for_timeout(1_200)


def _run_flow(page: Page, url: str) -> dict[str, Any]:
    page.goto(url, wait_until="networkidle")
    page.get_by_text("地图大厅", exact=True).first.wait_for(timeout=30_000)

    # 1. 从首页进入 Lab 配置。
    page.get_by_role("button", name=re.compile("打开 Lab")).first.click()
    page.get_by_text("配置一组架构对照实验", exact=True).first.wait_for(timeout=30_000)

    # 2. 一键离线演示入队。
    page.get_by_role("button", name=re.compile("一键离线演示")).first.click()
    page.get_by_text(re.compile("已入队")).first.wait_for(timeout=60_000)

    # 3. 监控页：等到父实验 COMPLETED。
    _goto_view(page, url, LAB_MONITOR)
    deadline = time.monotonic() + 180
    completed = False
    while time.monotonic() < deadline:
        body = page.locator("body").inner_text()
        if "COMPLETED" in body:
            completed = True
            break
        refresh = page.get_by_role("button", name="刷新")
        if refresh.count():
            refresh.first.click()
            page.wait_for_timeout(1_500)
        else:
            page.wait_for_timeout(1_000)
    assert completed, "父实验未在 180 秒内完成"
    monitor_body = page.locator("body").inner_text()
    assert "进度" in monitor_body
    assert "basic.v1" in monitor_body

    # 4. 结果页：对照、五态与可视化。
    _goto_view(page, url, LAB_RESULT)
    page.get_by_text("实验臂汇总", exact=True).first.wait_for(timeout=60_000)
    result_body = page.locator("body").inner_text()
    assert "有效分母" in result_body
    assert "SIMULATED" in result_body
    assert "COMPARABLE" in result_body or "DESCRIPTIVE_ONLY" in result_body

    # 5. 导出报告并校验内容。
    page.get_by_role("tab", name="导出").first.click()
    page.wait_for_timeout(800)
    page.get_by_role("button", name=re.compile("生成导出文件")).first.click()
    page.get_by_text(re.compile("已写出")).first.wait_for(timeout=60_000)
    with page.expect_download() as download_info:
        page.get_by_role("button", name=re.compile("下载实验报告")).first.click()
    download = download_info.value
    path = download.path()
    assert path is not None
    report = Path(path).read_text(encoding="utf-8")
    assert "SIMULATED" in report
    assert "不代表任何真实模型能力" in report
    assert "sealed_truth" not in report.lower()
    assert "judge_state" not in report.lower()
    assert "sk-" not in report.lower()

    return {
        "monitor_state": "COMPLETED",
        "report_bytes": Path(path).stat().st_size,
        "report_lines": len(report.splitlines()),
    }


def _launch(playwright: Any) -> Any:
    """优先用系统 Chrome（本地）；CI 没有时回退到 Playwright 自带 chromium。"""

    try:
        return playwright.chromium.launch(channel="chrome", headless=True)
    except Exception:  # noqa: BLE001 - CI 环境通常没有系统 Chrome
        return playwright.chromium.launch(headless=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true", help="自动启动临时 Streamlit")
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--port", type=int, default=8512)
    args = parser.parse_args()

    process: subprocess.Popen[bytes] | None = None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    url = args.url
    try:
        if args.start:
            temporary = tempfile.TemporaryDirectory(
                prefix="agent-arena-lab-e2e-", ignore_cleanup_errors=True
            )
            base = Path(temporary.name) / "runs"
            process = _start_server(args.port, base / "web", base / "lab")
            url = f"http://127.0.0.1:{args.port}"
        with sync_playwright() as playwright:
            browser = _launch(playwright)
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
                process.wait(timeout=10)
            time.sleep(0.5)
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
