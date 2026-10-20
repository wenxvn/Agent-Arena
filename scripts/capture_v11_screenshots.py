"""生成 V11 网页截图（需要本地 Streamlit 已启动）。

用法：
    uv run --with playwright python scripts/capture_v11_screenshots.py
    uv run --with playwright python scripts/capture_v11_screenshots.py --url http://127.0.0.1:8501

使用系统 Chrome（`channel="chrome"`），不额外下载浏览器。截图写入
``docs/v11/screenshots/``；页面数据来自本机 ``runs/web``，不包含密钥。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "v11" / "screenshots"
NAV = {
    "home": "首页 / 地图大厅",
    "config": "挑战配置",
    "live": "运行监控",
    "result": "结果与回放",
    "history": "历史与对照",
    "settings": "设置与帮助",
}


def _wait_text(page: Page, text: str, timeout: int = 20_000) -> None:
    page.get_by_text(text, exact=True).first.wait_for(timeout=timeout)


def _click_nav(page: Page, label: str) -> None:
    page.get_by_text(label, exact=True).first.click()
    page.wait_for_timeout(2_000)


def _shot(page: Page, name: str) -> str:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / name
    page.screenshot(path=str(path), full_page=False)
    return str(path.relative_to(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    args = parser.parse_args()
    shots: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
        page.goto(args.url, wait_until="networkidle")
        _wait_text(page, "地图大厅")
        shots.append(_shot(page, "01-home.png"))

        _click_nav(page, NAV["config"])
        _wait_text(page, "公开规则与动作契约")
        page.get_by_text("公开规则与动作契约", exact=True).first.click()
        page.wait_for_timeout(4_000)
        shots.append(_shot(page, "02-config-rules.png"))

        _click_nav(page, NAV["live"])
        _wait_text(page, "动作时间线")
        shots.append(_shot(page, "03-run-monitor.png"))

        _click_nav(page, NAV["result"])
        _wait_text(page, "逐步回放")
        shots.append(_shot(page, "04-result.png"))

        _click_nav(page, NAV["history"])
        _wait_text(page, "本地同模型成绩榜（P2）")
        shots.append(_shot(page, "05-history.png"))

        _click_nav(page, NAV["settings"])
        _wait_text(page, "Provider 配置（只读）")
        shots.append(_shot(page, "06-settings.png"))

        mobile = browser.new_page(viewport={"width": 430, "height": 900})
        mobile.goto(args.url, wait_until="networkidle")
        _wait_text(mobile, "地图大厅")
        mobile.wait_for_timeout(800)
        shots.append(_shot(mobile, "07-home-mobile.png"))
        browser.close()
    for path in shots:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
