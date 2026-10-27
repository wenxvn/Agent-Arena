"""生成 V14 新增视图的截图（自动启动临时 Streamlit + 系统 Chrome）。

用法：
    uv run --with playwright --with streamlit python scripts/capture_v14_screenshots.py

截图写入 ``docs/v14/screenshots/``；数据来自临时目录的 SIMULATED 演示，
不含密钥、隐藏真值或本机历史。
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "v14" / "screenshots"
LAB_CONFIG = "Lab · 实验配置"
LAB_MONITOR = "Lab · 实验监控"
LAB_RESULT = "Lab · 结果与对照"
LAB_STABILITY = "Lab · 稳定性与效度"
LAB_AUDIT = "Lab · 报告与审计"


def _wait_port(port: int, timeout: float = 40.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Streamlit 未在端口 {port} 启动。")


def _start(port: int, base: Path) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    environment["AGENT_ARENA_WEB_RUNS_DIR"] = str(base / "web")
    environment["AGENT_ARENA_LAB_RUNS_DIR"] = str(base / "lab")
    process = subprocess.Popen(
        [
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
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_port(port)
    return process


def _shot(page: Page, name: str) -> str:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / name
    page.screenshot(path=str(path), full_page=False)
    return str(path.relative_to(ROOT))


def _goto(page: Page, url: str, view: str, *, settle: int = 2_500) -> None:
    page.goto(f"{url}/?view={quote(view)}", wait_until="networkidle")
    page.wait_for_timeout(settle)


def main() -> int:
    port = 8571
    shots: list[str] = []
    temporary = tempfile.TemporaryDirectory(
        prefix="agent-arena-v14-shots-", ignore_cleanup_errors=True
    )
    base = Path(temporary.name) / "runs"
    process = _start(port, base)
    url = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1200})

            # 先用"一键离线演示"造出数据，页面才有内容可看。
            _goto(page, url, LAB_CONFIG)
            page.get_by_text("配置一组架构对照实验", exact=True).first.wait_for(
                timeout=30_000
            )
            page.get_by_role("button", name=re.compile("一键离线演示")).first.click()
            page.get_by_text(re.compile("已入队")).first.wait_for(timeout=60_000)
            _goto(page, url, LAB_MONITOR)
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                if "COMPLETED" in page.locator("body").inner_text():
                    break
                refresh = page.get_by_role("button", name="刷新")
                if refresh.count():
                    refresh.first.click()
                page.wait_for_timeout(1_500)

            # 1. 结果页：V14 可比性门禁 + 配对明细（宽屏浅色）
            _goto(page, url, LAB_RESULT, settle=3_500)
            page.get_by_text("实验臂汇总", exact=True).first.wait_for(timeout=60_000)
            page.wait_for_timeout(1_200)
            shots.append(_shot(page, "01-lab-result-gate.png"))

            # 2. 可视化页：MAP-22 探索视图（被拒移动不画成路径）
            page.get_by_role("tab", name="可视化").first.click()
            page.wait_for_timeout(1_500)
            # 滚到 V14 的"被拒移动不画成路径"声明那一行再截图。
            statement = page.get_by_text("没有改变位置", exact=False)
            if statement.count():
                statement.first.scroll_into_view_if_needed()
                page.wait_for_timeout(600)
            shots.append(_shot(page, "02-lab-map22-exploration.png"))

            # 3. 证据与差异页：双轨迹首次分歧高亮
            page.get_by_role("tab", name="证据与差异").first.click()
            page.wait_for_timeout(800)
            pairwise = page.get_by_role("button", name=re.compile("生成对照"))
            if pairwise.count():
                pairwise.first.click()
                page.wait_for_timeout(1_800)
            shots.append(_shot(page, "03-lab-first-divergence.png"))

            # 4. 稳定性与效度：按 seed 分组 + 六图效度（切到 V12 历史）
            _goto(page, url, LAB_STABILITY, settle=4_000)
            history_radio = page.get_by_text("V12 历史（只读）", exact=False)
            if history_radio.count():
                history_radio.first.click()
                page.wait_for_timeout(3_000)
            shots.append(_shot(page, "04-lab-seed-groups.png"))

            # 5. 窄屏（430px）：同一页面的可用性
            mobile = browser.new_page(viewport={"width": 430, "height": 900})
            mobile.goto(f"{url}/?view={quote(LAB_STABILITY)}", wait_until="networkidle")
            mobile.wait_for_timeout(3_000)
            mobile_history = mobile.get_by_text("V12 历史（只读）", exact=False)
            if mobile_history.count():
                mobile_history.first.click()
                mobile.wait_for_timeout(3_000)
            shots.append(_shot(mobile, "05-lab-stability-mobile.png"))

            # 6. 深色模式（结果页）
            dark = browser.new_page(
                viewport={"width": 1440, "height": 1200}, color_scheme="dark"
            )
            dark.goto(f"{url}/?view={quote(LAB_RESULT)}", wait_until="networkidle")
            dark.wait_for_timeout(3_500)
            shots.append(_shot(dark, "06-lab-result-dark.png"))

            # 7. 报告与审计（保留 V13 报告生成流程）
            _goto(page, url, LAB_AUDIT, settle=3_000)
            page.get_by_role("button", name=re.compile("生成 V13 报告")).first.click()
            page.get_by_text(re.compile("下载 report_v13")).first.wait_for(timeout=60_000)
            page.wait_for_timeout(800)
            shots.append(_shot(page, "07-lab-audit.png"))

            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        time.sleep(0.5)
        temporary.cleanup()
    for path in shots:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
