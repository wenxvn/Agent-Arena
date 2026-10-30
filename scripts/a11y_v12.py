"""V12 可访问性审计：主题对比度（离线）+ 浏览器 DOM/键盘（Playwright）。

用法：
    uv run python scripts/a11y_v12.py                       # 只做主题审计（零依赖）
    uv run --with playwright --with streamlit python scripts/a11y_v12.py --browser
    uv run --with playwright --with streamlit python scripts/a11y_v12.py --browser --start

报告写入 ``runs/v12/a11y.json``；退出码 0 表示无 critical/serious 问题。
不发送任何 Provider 请求。
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
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.a11y import (  # noqa: E402
    audit_dom,
    audit_focus_css,
    audit_theme_tokens,
    keyboard_report,
    summarize,
)
from agent_arena.ui.theme import stylesheet  # noqa: E402

PAGES = [
    ("首页 / 地图大厅", "地图大厅"),
    ("挑战配置", "配置一局挑战"),
    ("历史与对照", "历史与对照"),
    ("Lab · 实验配置", "配置一组架构对照实验"),
    ("Lab · 结果与对照", "结果与对照"),
    ("Lab · 稳定性与效度", "稳定性与效度"),
    ("Lab · 报告与审计", "报告与审计"),
    ("设置与帮助", "设置与帮助"),
]

#: 采集 DOM 快照的脚本：只读属性，不修改页面。
#:
#: 可见性判定必须排除**折叠的** ``<details>``（Streamlit expander 的内容默认折叠，
#: 用户看不到也不应被审计），并优先用 ``checkVisibility``；名称回退到 ``textContent``
#: （``innerText`` 对隐藏子树返回空串，会产生"无名称按钮"的误报）。
SNAPSHOT_JS = """
() => {
  const items = [];
  const all = document.querySelectorAll(
    'button, a, input, select, textarea, h1, h2, h3, h4, h5, h6, img, [role]'
  );
  all.forEach((el, index) => {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    const collapsed = el.closest('details:not([open])') !== null;
    const cssVisible = typeof el.checkVisibility === 'function'
      ? el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
      : (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden');
    const label = el.getAttribute('aria-label')
      || el.getAttribute('title')
      || (el.labels && el.labels.length ? el.labels[0].innerText : '')
      || (el.innerText || '').trim()
      || (el.textContent || '').trim();
    const heading = /^H([1-6])$/.exec(el.tagName);
    items.push({
      index,
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      name: (label || '').slice(0, 80),
      alt: el.getAttribute('alt'),
      aria_hidden: el.getAttribute('aria-hidden') === 'true',
      visible: cssVisible && !collapsed,
      heading_level: heading ? parseInt(heading[1], 10) : null,
      outline_style: style.outlineStyle,
      box_shadow: style.boxShadow && style.boxShadow !== 'none',
      src: el.getAttribute('src'),
    });
  });
  return {
    lang: document.documentElement.getAttribute('lang') || '',
    items,
  };
}
"""


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


def _launch(playwright: Any) -> Any:
    try:
        return playwright.chromium.launch(channel="chrome", headless=True)
    except Exception:  # noqa: BLE001 - CI 无系统 Chrome
        return playwright.chromium.launch(headless=True)


def _browser_audit(url: str, *, color_scheme: str) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    pages: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        page = browser.new_page(
            viewport={"width": 1440, "height": 1200}, color_scheme=color_scheme
        )
        for view, marker in PAGES:
            # 显式 60s：Windows 冷启动实测单页 6–8s，默认 30s 会偶发超时（V14.1 记录）。
            page.goto(f"{url}/?view={quote(view)}", wait_until="networkidle", timeout=60_000)
            try:
                page.get_by_text(marker, exact=True).first.wait_for(timeout=20_000)
            except Exception:  # noqa: BLE001 - 标记文本可能因空状态不同
                pass
            page.wait_for_timeout(1_200)
            snapshot = page.evaluate(SNAPSHOT_JS)
            dom = audit_dom(snapshot["items"])
            order: list[dict[str, Any]] = []
            for _ in range(12):
                page.keyboard.press("Tab")
                page.wait_for_timeout(60)
                focused = page.evaluate(
                    """
                    () => {
                      const el = document.activeElement;
                      if (!el) return null;
                      const style = window.getComputedStyle(el);
                      const parentStyle = el.parentElement
                        ? window.getComputedStyle(el.parentElement) : null;
                      const grandStyle = el.parentElement && el.parentElement.parentElement
                        ? window.getComputedStyle(el.parentElement.parentElement) : null;
                      const rect = el.getBoundingClientRect();
                      const label = el.getAttribute('aria-label')
                        || (el.innerText || '').trim()
                        || (el.textContent || '').trim()
                        || el.getAttribute('type') || '';
                      const ringVisible =
                        style.outlineStyle !== 'none'
                        || (style.boxShadow && style.boxShadow !== 'none')
                        || (parentStyle && parentStyle.boxShadow
                            && parentStyle.boxShadow !== 'none')
                        || (grandStyle && grandStyle.boxShadow
                            && grandStyle.boxShadow !== 'none');
                      const all = Array.from(document.querySelectorAll('*'));
                      return {
                        id: all.indexOf(el),
                        tag: el.tagName.toLowerCase(),
                        name: (label || '').slice(0, 60),
                        visible: rect.width > 0 && rect.height > 0,
                        outline_style: ringVisible ? 'solid' : style.outlineStyle,
                        box_shadow: Boolean(ringVisible),
                      };
                    }
                    """
                )
                if focused:
                    order.append(focused)
            keyboard = keyboard_report(order)
            pages.append(
                {
                    "view": view,
                    "lang": snapshot["lang"],
                    "dom": dom,
                    "keyboard": keyboard,
                    "ok": dom["ok"] and keyboard["ok"],
                }
            )
        browser.close()
    merged = summarize(*[item["dom"] for item in pages], *[item["keyboard"] for item in pages])
    lang_issues = [
        {"view": item["view"], "lang": item["lang"]}
        for item in pages
        if item["lang"] not in {"zh-CN", "zh"}
    ]
    return {
        "color_scheme": color_scheme,
        "pages": pages,
        "summary": merged,
        "lang_issues": lang_issues,
        # 已知框架限制：`<html lang>` 由 Streamlit 前端固定为 en，应用层无法修改；
        # 中文内容因此需要屏幕阅读器手动切换语言。这里只记录，不计为失败。
        "framework_notes": [
            "Streamlit 将 <html lang> 固定为 en；应用层无法覆盖（已在文档披露）。",
        ],
        "ok": merged["ok"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="store_true", help="追加浏览器 DOM/键盘审计")
    parser.add_argument("--start", action="store_true", help="自动启动临时 Streamlit")
    parser.add_argument("--url", default="http://127.0.0.1:8514")
    parser.add_argument("--port", type=int, default=8514)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "runs" / "v12" / "a11y.json"
    )
    args = parser.parse_args()

    theme = audit_theme_tokens()
    focus_css = audit_focus_css(stylesheet())
    report: dict[str, Any] = {
        "schema": "v12-a11y-1",
        "theme": {
            "ok": theme["ok"],
            "ui_ok": theme["ui_ok"],
            "checked": theme["checked"],
            "text_failures": theme["text_failures"],
            "ui_failures": theme["ui_failures"],
        },
        "focus_css": focus_css,
    }
    ok = theme["ok"] and focus_css["ok"]

    if args.browser:
        process: subprocess.Popen[bytes] | None = None
        temporary: tempfile.TemporaryDirectory[str] | None = None
        try:
            url = args.url
            if args.start:
                temporary = tempfile.TemporaryDirectory(
                    prefix="agent-arena-a11y-", ignore_cleanup_errors=True
                )
                base = Path(temporary.name) / "runs"
                process = _start(args.port, base)
                url = f"http://127.0.0.1:{args.port}"
            light = _browser_audit(url, color_scheme="light")
            dark = _browser_audit(url, color_scheme="dark")
            report["browser"] = {"light": light, "dark": dark}
            ok = ok and light["ok"] and dark["ok"]
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
    else:
        report["browser"] = None

    report["ok"] = ok
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    summary = {
        "ok": ok,
        "theme_ok": theme["ok"],
        "theme_text_failures": len(theme["text_failures"]),
        "theme_ui_failures": len(theme["ui_failures"]),
        "focus_css_ok": focus_css["ok"],
        "report": str(args.report.relative_to(ROOT))
        if args.report.is_relative_to(ROOT)
        else str(args.report),
    }
    if report.get("browser"):
        for scheme in ("light", "dark"):
            item = report["browser"][scheme]
            summary[f"{scheme}_critical"] = item["summary"]["critical"]
            summary[f"{scheme}_serious"] = item["summary"]["serious"]
            summary[f"{scheme}_moderate"] = item["summary"]["moderate"]
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
