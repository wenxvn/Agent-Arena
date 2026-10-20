"""生成 V11 网页截图（需要本地 Streamlit 已启动）。

用法：
    uv run --with playwright python scripts/capture_v11_screenshots.py
    uv run --with playwright python scripts/capture_v11_screenshots.py --url http://127.0.0.1:8501

使用系统 Chrome（`channel="chrome"`），不额外下载浏览器。截图写入
``docs/v11/screenshots/``；页面数据来自本机 ``runs/web``，不包含密钥。
"""

from __future__ import annotations

import argparse
import os
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
    page.locator('[data-testid="stSidebar"] label').filter(has_text=label).first.click()
    page.wait_for_timeout(2_000)


def _shot(page: Page, name: str) -> str:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / name
    page.screenshot(path=str(path), full_page=False)
    return str(path.relative_to(ROOT))


def _latest_run(runs_dir: Path) -> str:
    candidates = sorted(
        (path for path in runs_dir.glob("web-*") if (path / "result.json").is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0].name if candidates else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--runs-dir", type=Path, default=None)
    args = parser.parse_args()
    runs_dir = args.runs_dir or Path(
        os.environ.get("AGENT_ARENA_WEB_RUNS_DIR", str(ROOT / "runs" / "web"))
    )
    run_id = args.run_id or _latest_run(runs_dir)
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

        if run_id:
            page.goto(
                f"{args.url}/?view=%E8%BF%90%E8%A1%8C%E7%9B%91%E6%8E%A7&run={run_id}",
                wait_until="networkidle",
            )
        else:
            _click_nav(page, NAV["live"])
        _wait_text(page, "动作时间线")
        shots.append(_shot(page, "03-run-monitor.png"))

        if run_id:
            page.goto(
                f"{args.url}/?view=%E7%BB%93%E6%9E%9C%E4%B8%8E%E5%9B%9E%E6%94%BE&run={run_id}",
                wait_until="networkidle",
            )
        else:
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

        dark = browser.new_page(
            viewport={"width": 1440, "height": 1200},
            color_scheme="dark",
        )
        dark.goto(args.url, wait_until="networkidle")
        _wait_text(dark, "地图大厅")
        dark.wait_for_timeout(800)
        shots.append(_shot(dark, "08-home-dark.png"))
        browser.close()
    for path in shots:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
