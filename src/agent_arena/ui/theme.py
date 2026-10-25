"""V11 网页平台的设计系统（纯展示层，不依赖 Streamlit）。

只做三件事：

- 提供一份统一 CSS（颜色、卡片、徽章、进度条、侧边栏导航、响应式）；
- 把状态/难度/五态翻译成一致的视觉语气（tone），避免每个页面各写一套颜色；
- 生成可复用的 HTML 片段（页头、统计块、地图卡、横幅、空状态）。

所有函数都接受 ``st`` 作为第一个参数但不 import Streamlit，方便用 stub 单测。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from html import escape
from typing import Any

TONES: tuple[str, ...] = ("neutral", "accent", "success", "warning", "danger", "info")

#: 运行状态 → 视觉语气。只影响颜色，不改变任何状态语义。
STATE_TONES: dict[str, str] = {
    "CREATED": "neutral",
    "QUEUED": "info",
    "RUNNING": "accent",
    "SUCCEEDED": "success",
    "FAILED": "danger",
    "BUDGET_REACHED": "warning",
    "CANCELLED": "neutral",
    "PROVIDER_ERROR": "danger",
    "INTERRUPTED": "warning",
}

#: 展示难度 → 视觉语气。
DIFFICULTY_TONES: dict[str, str] = {
    "简单": "success",
    "中等": "warning",
    "困难": "danger",
    "待校准": "neutral",
}

#: 指标五态 → 视觉语气。
METRIC_TONES: dict[str, str] = {
    "VALID": "success",
    "CENSORED": "warning",
    "NOT_APPLICABLE": "neutral",
    "MISSING": "danger",
    "INVALID": "danger",
}

_CSS = """
<style>
:root {
  --aa-accent: #4c6ef5;
  --aa-accent-2: #7c5cff;
  --aa-success: #12a150;
  --aa-warning: #d08218;
  --aa-danger: #e5484d;
  --aa-info: #2f80ed;
  --aa-line: rgba(120, 132, 155, .24);
  --aa-line-soft: rgba(120, 132, 155, .14);
  --aa-surface: rgba(120, 132, 155, .07);
  --aa-surface-2: rgba(120, 132, 155, .13);
  --aa-shadow: 0 1px 2px rgba(16, 24, 40, .04), 0 8px 24px rgba(16, 24, 40, .06);
  --aa-radius: 16px;
  --aa-mono: ui-monospace, SFMono-Regular, "Cascadia Mono", Consolas, monospace;
  /* 文字/图标专用色：与填充色分开，保证 WCAG AA 4.5:1（V12 可访问性审计）。
     填充与边框仍用上面的 --aa-*，它们只需 3:1。 */
  --aa-accent-text: #3b5bdb;
  --aa-accent-2-text: #6341d9;
  --aa-success-text: #0a7a3d;
  --aa-warning-text: #8a5200;
  --aa-danger-text: #c22a2f;
  --aa-info-text: #1a63c9;
  --aa-neutral-text: #5f6b7d;
}

@media (prefers-color-scheme: dark) {
  :root {
    --aa-accent-text: #8ea2ff;
    --aa-accent-2-text: #b39cff;
    --aa-success-text: #3ddc97;
    --aa-warning-text: #f5b544;
    --aa-danger-text: #ff8b8f;
    --aa-info-text: #6aa9ff;
    --aa-neutral-text: #a9b3c6;
  }
}

/* ---------------------------------------------------------------- 版式 */
.block-container {
  padding-top: 1.5rem;
  padding-bottom: 3.5rem;
  max-width: 1320px;
}
h1, h2, h3, h4 { letter-spacing: -.012em; }
h1 {
  font-size: 2.05rem !important;
  font-weight: 760;
  line-height: 1.22;
  margin: .1rem 0 .35rem !important;
}
/* 语义层级：h1 = 页面标题，h2 = 区块，h3 = 区块内小节。
   V12 可访问性审计要求标题层级不跳级（h1 → h2 → h3），因此视觉尺寸与语义级别
   解耦：h2 沿用原来的“左侧强调条”外观，h3 更小且无强调条。 */
h2 {
  font-size: 1.06rem !important;
  font-weight: 700;
  padding-left: .62rem;
  border-left: 3px solid var(--aa-accent);
  margin: 1.55rem 0 .7rem !important;
}
h3 {
  font-size: 1rem !important;
  font-weight: 680;
  margin: 1.1rem 0 .5rem !important;
}
[data-testid="stCaptionContainer"] p { opacity: .74; font-size: .85rem; }
[data-testid="stMarkdownContainer"] p { line-height: 1.62; }
hr { margin: 1.5rem 0 !important; opacity: .45; }
code { font-family: var(--aa-mono); font-size: .84em; }

/* ------------------------------------------------------------ 焦点可见性 */
/* 键盘用户的焦点必须可见（WCAG 2.4.7）。这里只加强焦点环，
   不覆盖 Streamlit 自身的焦点样式，也不抑制任何轮廓。 */
:where(a, button, summary, [role="button"], [role="tab"], input, select, textarea):focus-visible {
  outline: 2px solid var(--aa-accent);
  outline-offset: 2px;
  border-radius: 6px;
}

/* ------------------------------------------------------------ 侧边栏 */
[data-testid="stSidebar"] { border-right: 1px solid var(--aa-line-soft); }
[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
.aa-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 4px 2px 14px;
}
.aa-brand-mark {
  width: 34px; height: 34px; border-radius: 11px; flex: 0 0 auto;
  display: grid; place-items: center; font-size: 17px; color: #fff;
  background: linear-gradient(140deg, var(--aa-accent), var(--aa-accent-2));
  box-shadow: 0 4px 14px rgba(76, 110, 245, .35);
}
.aa-brand-name {
  font-size: .82rem; font-weight: 760; letter-spacing: .14em;
  line-height: 1.2;
}
.aa-brand-sub { font-size: .72rem; opacity: .62; letter-spacing: .02em; }
.aa-nav-hint {
  font-size: .68rem; letter-spacing: .16em; text-transform: uppercase;
  opacity: .5; padding: 0 4px 6px;
}
[data-testid="stSidebar"] [role="radiogroup"] { gap: 2px !important; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] {
  padding: 7px 11px; border-radius: 10px; width: 100%;
  transition: background .12s ease, color .12s ease;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover { background: var(--aa-surface); }
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child { display: none; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] p {
  font-size: .88rem; font-weight: 500; margin: 0;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {
  background: linear-gradient(100deg, rgba(76, 110, 245, .16), rgba(124, 92, 255, .10));
  box-shadow: inset 0 0 0 1px rgba(76, 110, 245, .28);
}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p {
  font-weight: 680; color: var(--aa-accent-text);
}
.aa-side-card {
  border: 1px solid var(--aa-line-soft); border-radius: 12px;
  padding: 10px 12px; margin: 10px 0 6px; background: var(--aa-surface);
  font-size: .78rem; line-height: 1.5;
}
.aa-side-card .aa-side-label {
  font-size: .66rem; letter-spacing: .14em; text-transform: uppercase;
  opacity: .55; margin-bottom: 4px;
}
.aa-side-foot { font-size: .7rem; opacity: .45; padding-top: 8px; }

/* ------------------------------------------------------------ 页头 */
.aa-eyebrow {
  display: inline-flex; align-items: center; gap: 7px;
  font-size: .7rem; font-weight: 700; letter-spacing: .16em;
  text-transform: uppercase; color: var(--aa-accent-text);
  margin-bottom: 2px;
}
.aa-eyebrow::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: currentColor; box-shadow: 0 0 0 3px rgba(76, 110, 245, .18);
}
.aa-sub { font-size: .92rem; opacity: .74; max-width: 78ch; line-height: 1.6;
  margin-bottom: .85rem; }

/* ------------------------------------------------------------ 统计块 */
.aa-stat {
  position: relative; overflow: hidden;
  border: 1px solid var(--aa-line-soft); border-radius: var(--aa-radius);
  background: var(--aa-surface); padding: 13px 15px 12px; height: 100%;
  margin-bottom: 4px;
}
.aa-stat::after {
  content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
  background: var(--aa-tone, var(--aa-accent)); opacity: .85;
}
.aa-stat-label { font-size: .72rem; letter-spacing: .06em; opacity: .66; }
.aa-stat-value {
  font-size: 1.62rem; font-weight: 740; line-height: 1.24;
  margin-top: 2px; font-variant-numeric: tabular-nums;
}
.aa-stat-hint { font-size: .72rem; opacity: .58; margin-top: 1px; }
.aa-tone-neutral { --aa-tone: #8b95a8; }
.aa-tone-accent { --aa-tone: var(--aa-accent); }
.aa-tone-success { --aa-tone: var(--aa-success); }
.aa-tone-warning { --aa-tone: var(--aa-warning); }
.aa-tone-danger { --aa-tone: var(--aa-danger); }
.aa-tone-info { --aa-tone: var(--aa-info); }

/* ------------------------------------------------------------ 徽章 */
.aa-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 1px 9px; border-radius: 999px; font-size: .74rem;
  font-weight: 560; line-height: 1.7; white-space: nowrap;
  border: 1px solid var(--aa-line-soft);
  background: var(--aa-surface-2); color: inherit; opacity: .92;
}
.aa-chip-accent {
  color: var(--aa-accent-text); border-color: rgba(76, 110, 245, .32);
  background: rgba(76, 110, 245, .10);
}
.aa-chip-success {
  color: var(--aa-success-text); border-color: rgba(18, 161, 80, .3);
  background: rgba(18, 161, 80, .10);
}
.aa-chip-warning {
  color: var(--aa-warning-text); border-color: rgba(224, 140, 26, .32);
  background: rgba(224, 140, 26, .12);
}
.aa-chip-danger {
  color: var(--aa-danger-text); border-color: rgba(229, 72, 77, .3);
  background: rgba(229, 72, 77, .10);
}
.aa-chip-info {
  color: var(--aa-info-text); border-color: rgba(47, 128, 237, .3);
  background: rgba(47, 128, 237, .10);
}
.aa-chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }

/* ------------------------------------------------------------ 地图卡 */
.aa-card-head {
  display: flex; align-items: baseline; gap: 8px;
  font-size: .74rem; opacity: .6; margin-bottom: 2px;
}
.aa-card-title { font-size: 1.02rem; font-weight: 700; line-height: 1.35; }
.aa-card-goal {
  font-size: .84rem; opacity: .8; line-height: 1.55;
  margin: 6px 0 10px; min-height: 2.6em;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden;
}
.aa-card-meta {
  display: flex; flex-wrap: wrap; gap: 4px 12px;
  font-size: .74rem; opacity: .62; margin-bottom: 4px;
}
.aa-card-meta b { font-weight: 620; opacity: .92; }
.aa-card-note {
  font-size: .74rem; opacity: .58; line-height: 1.5;
  border-top: 1px dashed var(--aa-line-soft); padding-top: 7px; margin-top: 7px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.aa-card-note b { font-weight: 620; opacity: .9; }

/* 让带 border 的容器更像卡片 */
[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: var(--aa-radius) !important;
  transition: box-shadow .16s ease, border-color .16s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
  border-color: rgba(76, 110, 245, .38) !important;
  box-shadow: var(--aa-shadow);
}

/* ------------------------------------------------------------ 横幅 */
.aa-banner {
  border: 1px solid var(--aa-line-soft); border-left: 3px solid var(--aa-tone, var(--aa-accent));
  border-radius: 12px; padding: 11px 14px; margin: 4px 0 12px;
  background: var(--aa-surface);
}
.aa-banner-title { font-weight: 700; font-size: .95rem; }
.aa-banner-code {
  font-family: var(--aa-mono); font-size: .7rem; font-weight: 500;
  opacity: .55; margin-left: 6px; letter-spacing: .04em;
}
.aa-banner-detail { font-size: .84rem; opacity: .78; margin-top: 2px; line-height: 1.55; }
.aa-banner-meta {
  font-size: .74rem; opacity: .6; margin-top: 5px;
  font-family: var(--aa-mono);
}

/* ------------------------------------------------------------ 进度条 */
.aa-progress {
  height: 8px; border-radius: 999px; overflow: hidden;
  background: var(--aa-surface-2); margin: 6px 0 4px;
}
.aa-progress-fill {
  height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--aa-accent), var(--aa-accent-2));
  transition: width .4s ease;
}
.aa-progress-fill.aa-tone-success { background: linear-gradient(90deg, #12a150, #34c47c); }
.aa-progress-fill.aa-tone-warning { background: linear-gradient(90deg, #e08c1a, #f0b545); }
.aa-progress-fill.aa-tone-danger { background: linear-gradient(90deg, #e5484d, #f2777a); }
.aa-progress-fill.aa-tone-neutral { background: linear-gradient(90deg, #8b95a8, #aeb6c4); }

/* ------------------------------------------------------------ 空状态 */
.aa-empty {
  border: 1px dashed var(--aa-line); border-radius: var(--aa-radius);
  padding: 26px 18px; text-align: center; background: var(--aa-surface);
}
.aa-empty-icon { font-size: 1.5rem; opacity: .7; }
.aa-empty-title { font-weight: 660; margin-top: 6px; }
.aa-empty-hint { font-size: .82rem; opacity: .64; margin-top: 3px; line-height: 1.55; }

/* ------------------------------------------------------------ 其他 */
.aa-kv { display: grid; gap: 3px; font-size: .8rem; }
.aa-kv div { display: flex; justify-content: space-between; gap: 12px; }
.aa-kv span:first-child { opacity: .6; }
.aa-kv span:last-child { font-family: var(--aa-mono); font-size: .76rem; text-align: right; }
.aa-hr { height: 1px; background: var(--aa-line-soft); margin: 14px 0; border: 0; }
.aa-quiet { font-size: .78rem; opacity: .6; }
.aa-inline-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px;
  font-size: .82rem; margin: .35rem 0 .2rem;
}
.aa-inline-meta span { opacity: .82; }
.aa-inline-meta b { font-weight: 660; font-family: var(--aa-mono); font-size: .78rem; }

/* 表格与控件微调 */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
[data-testid="stExpander"] details {
  border-radius: 12px !important; border-color: var(--aa-line-soft) !important;
}
[data-testid="stExpander"] summary { font-size: .86rem; font-weight: 560; }
.stButton > button, .stDownloadButton > button { border-radius: 10px; font-weight: 560; }
[data-testid="stBaseButton-primary"] {
  background: linear-gradient(100deg, var(--aa-accent), var(--aa-accent-2));
  border: 0; box-shadow: 0 4px 14px rgba(76, 110, 245, .28);
}
[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.05); }
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 4px; }
[data-testid="stTabs"] [data-baseweb="tab"] {
  border-radius: 9px; padding: 5px 12px; font-size: .86rem;
}

/* ------------------------------------------------------------ 响应式 */
@media (max-width: 900px) {
  .block-container { padding-left: .9rem; padding-right: .9rem; }
  h1 { font-size: 1.66rem !important; }
  .aa-stat-value { font-size: 1.36rem; }
  .aa-card-goal { min-height: 0; }
}
</style>
"""


def stylesheet() -> str:
    """整站 CSS；由 ``app.main`` 在页面顶部注入一次。"""

    return _CSS


def tone(value: str, mapping: dict[str, str], fallback: str = "neutral") -> str:
    return mapping.get(value, fallback)


def state_tone(state: str) -> str:
    return tone(state, STATE_TONES)


def difficulty_tone(display_difficulty: str) -> str:
    return tone(display_difficulty, DIFFICULTY_TONES)


def metric_tone(state: str) -> str:
    return tone(state, METRIC_TONES)


def chip(text: str, tone_name: str = "neutral") -> str:
    klass = "aa-chip" if tone_name == "neutral" else f"aa-chip aa-chip-{tone_name}"
    return f"<span class='{klass}'>{escape(str(text))}</span>"


def chip_row(items: Iterable[str]) -> str:
    body = "".join(items)
    return f"<div class='aa-chip-row'>{body}</div>" if body else ""


def page_head(
    st: Any,
    eyebrow: str,
    title: str,
    subtitle: str = "",
) -> None:
    """页头：小标签 + 标题（真实 ``h1``）+ 说明。"""

    st.markdown(
        f"<div class='aa-eyebrow'>{escape(eyebrow)}</div>",
        unsafe_allow_html=True,
    )
    st.title(title)
    if subtitle:
        st.markdown(
            f"<div class='aa-sub'>{subtitle}</div>",
            unsafe_allow_html=True,
        )


def stat_tiles(
    st: Any,
    tiles: Sequence[tuple[str, str, str, str]],
    *,
    columns: int | None = None,
) -> None:
    """一行统计块。``tiles`` 每项为 ``(标签, 值, 提示, tone)``。"""

    if not tiles:
        return
    count = columns or len(tiles)
    row = st.columns(min(count, len(tiles)))
    for index, column in enumerate(row):
        if index >= len(tiles):
            break
        label, value, hint, tone_name = tiles[index]
        html = (
            f"<div class='aa-stat aa-tone-{tone_name}'>"
            f"<div class='aa-stat-label'>{escape(label)}</div>"
            f"<div class='aa-stat-value'>{escape(str(value))}</div>"
            f"<div class='aa-stat-hint'>{escape(hint)}</div>"
            "</div>"
        )
        column.markdown(html, unsafe_allow_html=True)
    # 统计块后面紧跟筛选控件时容易被读成一整块，留一条固定间距。
    if hasattr(st, "markdown"):
        st.markdown("<div style='height:.55rem'></div>", unsafe_allow_html=True)


def banner(
    title: str,
    detail: str = "",
    *,
    tone_name: str = "accent",
    code: str = "",
    meta: str = "",
) -> str:
    code_html = f"<span class='aa-banner-code'>{escape(code)}</span>" if code else ""
    detail_html = f"<div class='aa-banner-detail'>{escape(detail)}</div>" if detail else ""
    meta_html = f"<div class='aa-banner-meta'>{escape(meta)}</div>" if meta else ""
    return (
        f"<div class='aa-banner aa-tone-{tone_name}'>"
        f"<div class='aa-banner-title'>{escape(title)}{code_html}</div>"
        f"{detail_html}{meta_html}</div>"
    )


def progress(ratio: float, *, tone_name: str = "accent") -> str:
    width = max(0.0, min(1.0, float(ratio))) * 100
    return (
        "<div class='aa-progress'>"
        f"<div class='aa-progress-fill aa-tone-{tone_name}' style='width:{width:.1f}%'></div>"
        "</div>"
    )


def empty_state(icon: str, title: str, hint: str = "") -> str:
    hint_html = f"<div class='aa-empty-hint'>{escape(hint)}</div>" if hint else ""
    return (
        "<div class='aa-empty'>"
        f"<div class='aa-empty-icon'>{escape(icon)}</div>"
        f"<div class='aa-empty-title'>{escape(title)}</div>"
        f"{hint_html}</div>"
    )


def kv_block(rows: Sequence[tuple[str, str]]) -> str:
    body = "".join(
        f"<div><span>{escape(label)}</span><span>{escape(str(value))}</span></div>"
        for label, value in rows
    )
    return f"<div class='aa-kv'>{body}</div>"


def brand_block() -> str:
    return (
        "<div class='aa-brand'>"
        "<div class='aa-brand-mark'>◈</div>"
        "<div><div class='aa-brand-name'>AGENT ARENA</div>"
        "<div class='aa-brand-sub'>十世界三十图 · 本地实验台</div></div>"
        "</div>"
    )


def side_card(label: str, body_html: str) -> str:
    return (
        "<div class='aa-side-card'>"
        f"<div class='aa-side-label'>{escape(label)}</div>{body_html}</div>"
    )


def map_card_html(
    *,
    map_id: str,
    emoji: str,
    world_label: str,
    title: str,
    display_difficulty: str,
    design_difficulty: str,
    goal: str,
    mechanism: str,
    decision_budget: int,
    tool_count: int,
    seed_count: int,
    note: str,
    run_count: int = 0,
    success_count: int = 0,
) -> str:
    """首页地图卡片的纯 HTML 部分（按钮由调用方另加）。"""

    chips = [
        chip(map_id, "accent"),
        chip(f"{emoji} {world_label}"),
        chip(display_difficulty, difficulty_tone(display_difficulty)),
    ]
    if run_count:
        chips.append(
            chip(f"已跑 {run_count} 局 · 成功 {success_count}", "info")
        )
    else:
        chips.append(chip("未跑过"))
    meta = (
        f"<span>机制 <b>{escape(mechanism)}</b></span>"
        f"<span>预算 <b>{decision_budget}</b></span>"
        f"<span>工具 <b>{tool_count}</b></span>"
        f"<span>seed <b>{seed_count}</b></span>"
    )
    return (
        f"{chip_row(chips)}"
        f"<div class='aa-card-title'>{escape(title)}</div>"
        f"<div class='aa-card-goal'>{escape(goal)}</div>"
        f"<div class='aa-card-meta'>{meta}</div>"
        f"<div class='aa-card-note'><b>设计难度 {escape(design_difficulty)}</b>"
        f" · {escape(note)}</div>"
    )


__all__ = [
    "DIFFICULTY_TONES",
    "METRIC_TONES",
    "STATE_TONES",
    "TONES",
    "banner",
    "brand_block",
    "chip",
    "chip_row",
    "difficulty_tone",
    "empty_state",
    "kv_block",
    "map_card_html",
    "metric_tone",
    "page_head",
    "progress",
    "side_card",
    "state_tone",
    "stat_tiles",
    "stylesheet",
    "tone",
]
