"""Agent Arena 本地网页平台（Streamlit）。

一条命令启动：

    uv run --extra web agent-arena web

页面只调用 ``agent_arena.web`` 服务层；不在 Streamlit 里创建环境或调用 Provider。
旧的只读研究视图（单局回放/矩阵总览/错误热点/条件对照）保留在同一入口。
"""

from __future__ import annotations

import csv
import io
import json
import os
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Any

from agent_arena import __version__
from agent_arena.lab.paths import LAB_RUNS
from agent_arena.ui import lab as lab_ui
from agent_arena.ui import theme
from agent_arena.ui.present import (
    aggregate_traces,
    autonomy_level,
    compare_conditions,
    error_hotspots,
    page_rows,
    success_at_k,
    summarize_trace,
    trace_overview,
)
from agent_arena.ui.runtime import get_lab_service as _get_shared_lab_service
from agent_arena.ui.runtime import get_service as _get_shared_service
from agent_arena.ui.runtime import reset_service as _reset_shared_service
from agent_arena.v10.baselines.suite import decision_budget
from agent_arena.web import catalog as web_catalog
from agent_arena.web.budget import BudgetLimits
from agent_arena.web.explain import (
    metric_state_label,
    mode_label,
    state_label,
)
from agent_arena.web.export import (
    export_actions_csv,
    export_filename,
    export_json_bytes,
    export_summary_bytes,
    export_trace_jsonl,
    replay_document,
)
from agent_arena.web.history import (
    compatibility_all,
    filter_runs,
    leaderboard,
    multi_comparison_rows,
)
from agent_arena.web.providers import (
    configuration_check,
    probe_live_provider,
    provider_statuses,
)
from agent_arena.web.safety import (
    DEFAULT_COST_CNY,
    MAX_COST_CNY,
    MAX_DECISIONS,
    MAX_INPUT_TOKENS,
    MAX_OUTPUT_TOKENS,
    MAX_REQUESTS,
    error_hint,
)
from agent_arena.web.schemas import (
    OFFLINE_MODEL,
    OFFLINE_PROVIDER,
    RunConfig,
    RunMode,
    RunState,
)
from agent_arena.web.service import (
    ConcurrentLiveRunError,
    RunService,
    RunServiceError,
)

ROOT = Path(__file__).resolve().parent.parent.parent.parent
RUNS_DIR = ROOT / "runs"
RESULTS_DIR = ROOT / "results"
WEB_RUNS_DIR = Path(os.environ.get("AGENT_ARENA_WEB_RUNS_DIR", str(RUNS_DIR / "web")))
LAB_RUNS_DIR = Path(
    os.environ.get("AGENT_ARENA_LAB_RUNS_DIR", str(LAB_RUNS))
)
MAX_SCAN_FILES = 400
PAGE_SIZE = 30
K_BUDGETS = [30, 60, 100, 150, 200]
HOME_PAGE_SIZE = 9

VIEW_HOME = "首页 / 地图大厅"
VIEW_CONFIG = "挑战配置"
VIEW_LIVE = "运行监控"
VIEW_RESULT = "结果与回放"
VIEW_HISTORY = "历史与对照"
VIEW_LAB_CONFIG = lab_ui.LAB_CONFIG
VIEW_LAB_MONITOR = lab_ui.LAB_MONITOR
VIEW_LAB_RESULT = lab_ui.LAB_RESULT
VIEW_RESEARCH = "研究回放（只读）"
VIEW_SETTINGS = "设置与帮助"
VIEWS = [
    VIEW_HOME,
    VIEW_CONFIG,
    VIEW_LIVE,
    VIEW_RESULT,
    VIEW_HISTORY,
    VIEW_LAB_CONFIG,
    VIEW_LAB_MONITOR,
    VIEW_LAB_RESULT,
    VIEW_RESEARCH,
    VIEW_SETTINGS,
]
LAB_VIEWS = set(lab_ui.LAB_VIEWS)
LEGACY_VIEWS = {"单局回放", "矩阵总览", "错误热点", "条件对照"}
RESEARCH_VIEWS = ["单局回放", "矩阵总览", "错误热点", "条件对照"]


def _load_streamlit() -> Any:
    try:
        from importlib import import_module
    except ImportError:  # pragma: no cover
        raise RuntimeError("需要先安装 streamlit 才能启动 UI。") from None
    try:
        module: Any = import_module("streamlit")
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("需要先安装 streamlit 才能启动 UI。") from exc
    return module


def get_service() -> RunService:
    return _get_shared_service(WEB_RUNS_DIR)


def get_lab_service() -> Any:
    return _get_shared_lab_service(WEB_RUNS_DIR, LAB_RUNS_DIR)


def reset_service() -> None:
    _reset_shared_service()


# --------------------------------------------------------------------- legacy
def _safe_dir(base: Path, name: str) -> Path | None:
    """只允许 base 下的一级子目录；其它一律拒绝。"""
    candidate = (base / name).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    if candidate == base.resolve() or not candidate.is_dir():
        return None
    return candidate


def _safe_trace_path(directory: Path, path: Path) -> Path | None:
    """只允许读取实验目录中的直接子文件，拒绝符号链接逃逸。"""
    try:
        candidate = path.resolve()
        relative = candidate.relative_to(directory.resolve())
    except (OSError, RuntimeError, ValueError):
        return None
    if len(relative.parts) != 1 or not candidate.is_file():
        return None
    return candidate


def _read_trace(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _scan_traces(directory: Path) -> tuple[list[dict[str, Any]], int]:
    """读目录下 episode trace；超 cap 截断并返回截断数。"""
    traces: list[dict[str, Any]] = []
    skipped = 0
    for path in sorted(directory.glob("episode_*.json")):
        if len(traces) >= MAX_SCAN_FILES:
            skipped += 1
            continue
        safe_path = _safe_trace_path(directory, path)
        if safe_path is None:
            continue
        trace = _read_trace(safe_path)
        if trace is not None:
            traces.append(trace)
    return traces, skipped


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _safe_csv_path(path: str) -> Path | None:
    """只允许读取 runs/、results/ 根目录或一级子目录中的 CSV。"""
    try:
        candidate = Path(path.strip()).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if candidate.suffix.lower() != ".csv" or not candidate.is_file():
        return None
    for base in (RUNS_DIR, RESULTS_DIR):
        try:
            relative = candidate.relative_to(base.resolve())
        except ValueError:
            continue
        if len(relative.parts) > 2:
            continue
        return candidate
    return None


def _run_dirs() -> list[str]:
    if not RUNS_DIR.is_dir():
        return []
    return sorted(path.name for path in RUNS_DIR.iterdir() if path.is_dir())


def _replay_view(st: Any) -> None:
    st.subheader("单局回放")
    options = _run_dirs()
    if not options:
        st.info("runs/ 下还没有实验目录。")
        return
    dirname = st.sidebar.selectbox("实验目录", options)
    directory = _safe_dir(RUNS_DIR, str(dirname))
    if directory is None:
        st.error("目录不合法。")
        return
    files = sorted(
        path.name
        for path in directory.glob("episode_*.json")
        if _safe_trace_path(directory, path) is not None
    )
    if not files:
        st.info("该目录下没有 episode trace。")
        return
    filename = st.sidebar.selectbox("trace 文件", files)
    trace_path = _safe_trace_path(directory, directory / str(filename))
    if trace_path is None:
        st.error("trace 文件路径不合法。")
        return
    trace = _read_trace(trace_path)
    if trace is None:
        st.error("trace 文件损坏。")
        return
    st.write(trace_overview(trace))
    st.write(autonomy_level(trace.get("provenance", {})))
    st.write({"error_hotspots": error_hotspots(trace)})
    rows = summarize_trace(trace)
    total_pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = st.sidebar.slider("页", 1, total_pages, 1) if total_pages > 1 else 1
    st.table(page_rows(rows, int(page), PAGE_SIZE))


def _matrix_view(st: Any) -> None:
    st.subheader("矩阵总览")
    options = _run_dirs()
    if not options:
        st.info("runs/ 下还没有实验目录。")
        return
    dirname = st.sidebar.selectbox("矩阵目录", options)
    directory = _safe_dir(RUNS_DIR, str(dirname))
    if directory is None:
        st.error("目录不合法。")
        return
    traces, skipped = _scan_traces(directory)
    if not traces:
        st.info("该目录下没有可读的 episode trace。")
        return
    if skipped:
        st.caption(f"文件过多，仅汇总前 {MAX_SCAN_FILES} 份，跳过 {skipped} 份。")
    st.table(aggregate_traces(traces))
    steps: list[int | float] = []
    for trace in traces:
        if trace.get("outcome") not in {"success", "scenario_success"}:
            continue
        value = trace.get("executed_action_count")
        if isinstance(value, (int, float)):
            steps.append(value)
    st.write({"success_at_k": success_at_k([int(value) for value in steps], K_BUDGETS)})


def _hotspot_view(st: Any) -> None:
    st.subheader("错误热点")
    st.caption("T4 三类：终点工具误用 / 重复读码 / 读码后游荡（只用公开字段）。")
    options = _run_dirs()
    if not options:
        st.info("runs/ 下还没有实验目录。")
        return
    dirname = st.sidebar.selectbox("实验目录", options)
    directory = _safe_dir(RUNS_DIR, str(dirname))
    if directory is None:
        st.error("目录不合法。")
        return
    traces, skipped = _scan_traces(directory)
    if not traces:
        st.info("该目录下没有可读的 episode trace。")
        return
    if skipped:
        st.caption(f"文件过多，仅汇总前 {MAX_SCAN_FILES} 份，跳过 {skipped} 份。")
    rows = []
    for trace in traces:
        hotspots = error_hotspots(trace)
        rows.append(
            {
                "seed": trace.get("seed"),
                "outcome": trace.get("outcome"),
                "wrong_tool": hotspots["wrong_tool_at_terminal"],
                "code_reads": hotspots["code_reads"],
                "post_code_moves": hotspots["post_code_moves"],
            }
        )
    st.table(rows)


def _compare_view(st: Any) -> None:
    st.subheader("条件对照")
    path_a = st.sidebar.text_input("对照 A benchmark CSV", "results/")
    path_b = st.sidebar.text_input("对照 B benchmark CSV", "results/")
    st.write(
        "自主性图例：纯 observation 自主 / observation-derived / "
        "world-declared phase guidance / planner_assisted（辅助上界，非自主）"
    )
    for label, path in (("A", path_a), ("B", path_b)):
        csv_path = _safe_csv_path(path)
        if csv_path is None:
            st.info(f"请输入 runs/ 或 results/ 下对照 {label} 的有效 benchmark .csv。")
            continue
        try:
            rows = _read_csv_rows(csv_path)
        except (OSError, UnicodeError, csv.Error):
            st.error(f"对照 {label} 的 CSV 无法读取。")
            continue
        st.write(label)
        st.write(compare_conditions(rows))


# ------------------------------------------------------------------ navigation
def _set_nav(st: Any, view: str) -> None:
    # radio 的 widget key 是 ``nav``；不能在组件实例化后直接改。这里只登记下一次
    # rerun 的目标，由 ``_apply_pending_nav`` 在组件创建前写入。
    st.session_state["pending_nav"] = view
    _set_query_param(st, "view", view)
    if hasattr(st, "rerun"):
        st.rerun()


def _apply_pending_nav(st: Any) -> None:
    state = getattr(st, "session_state", None)
    if state is None:
        return
    pending = state.get("pending_nav")
    if pending in VIEWS:
        state["nav"] = pending
        if hasattr(state, "pop"):
            state.pop("pending_nav", None)


def _set_query_param(st: Any, key: str, value: str) -> None:
    params = getattr(st, "query_params", None)
    if params is None:
        return
    try:
        params[key] = value
    except Exception:  # noqa: BLE001 - query params are a convenience only
        return


def _query_value(st: Any, key: str) -> str:
    params = getattr(st, "query_params", None)
    if params is None:
        return ""
    try:
        value = params.get(key)
    except Exception:  # noqa: BLE001
        return ""
    if isinstance(value, list):
        value = value[0] if value else ""
    return value if isinstance(value, str) else ""


def _apply_deep_link(st: Any) -> None:
    """支持 ``?view=结果与回放&run=<run_id>`` 深链；只在首次加载生效。

    ``_nav`` 会在用户导航后写回 ``view`` 参数；如果每次 rerun 都重新应用，就会把
    用户刚点的侧边栏选项覆盖掉。
    """

    state = getattr(st, "session_state", None)
    if state is not None and state.get("_deep_link_applied"):
        return
    view = _query_value(st, "view")
    run_id = _query_value(st, "run")
    map_id = _query_value(st, "map")
    if view in VIEWS:
        st.session_state["nav"] = view
    if run_id:
        st.session_state["active_run"] = run_id
    if map_id and any(item.map_id == map_id for item in web_catalog.cards()):
        st.session_state["selected_map"] = map_id
    if state is not None:
        state["_deep_link_applied"] = True


def _nav(st: Any) -> str:
    try:
        return str(
            st.sidebar.radio(
                "导航",
                VIEWS,
                key="nav",
                label_visibility="collapsed",
            )
        )
    except TypeError:  # 兼容旧测试的极简 stub
        return str(st.sidebar.radio("导航", VIEWS))


def _sidebar(st: Any) -> str:
    """品牌头 + 导航。旧只读视图的最小 stub 没有 markdown，因此全部守卫。"""

    if hasattr(st, "markdown"):
        st.sidebar.markdown(theme.brand_block(), unsafe_allow_html=True)
        st.sidebar.markdown("<div class='aa-nav-hint'>导航</div>", unsafe_allow_html=True)
    return _nav(st)


def _sidebar_footer(st: Any, service_getter: Any = get_service) -> None:
    """导航下方的当前运行摘要与版本脚注；只读，失败不影响主页面。"""

    if not hasattr(st, "markdown"):
        return
    try:
        service: RunService | None = service_getter()
    except Exception:  # noqa: BLE001 - 侧边栏摘要不得阻塞页面
        service = None
    st.sidebar.markdown("<div class='aa-hr'></div>", unsafe_allow_html=True)
    st.sidebar.markdown(
        theme.side_card("当前运行", _sidebar_run_html(st, service)),
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"<div class='aa-side-foot'>v{__version__} · 本地单机 · 密钥不离开本机</div>",
        unsafe_allow_html=True,
    )


def _sidebar_run_html(st: Any, service: RunService | None) -> str:
    run_id = str(st.session_state.get("active_run", "") or "")
    latest = False
    if not run_id and service is not None:
        # 用户还没在本次会话里选运行：退回到最近一局，避免侧边栏一片空白。
        try:
            rows = service.list_runs(limit=1)
        except Exception:  # noqa: BLE001
            rows = []
        if rows:
            run_id = rows[0].run_id
            latest = True
    if not run_id:
        return "<div class='aa-quiet'>还没有运行记录。先跑一局离线演示。</div>"
    if service is None:
        return f"<div class='aa-quiet'>{run_id}</div>"
    try:
        status = service.get_run(run_id)
    except Exception:  # noqa: BLE001 - 侧边栏不允许因缺文件崩溃
        return "<div class='aa-quiet'>选中运行的记录不可读。</div>"
    tone = theme.state_tone(status.state.value)
    map_id = str(status.config.get("map_id", ""))
    prefix = theme.chip("最近", "neutral") if latest else ""
    return (
        f"<div class='aa-chip-row' style='margin-bottom:6px'>{prefix}"
        f"{theme.chip(map_id or '未知地图', 'accent')}"
        f"{theme.chip(state_label(status.state.value), tone)}</div>"
        f"<div class='aa-quiet'>{status.decisions} / {status.decision_budget} 个动作</div>"
    )


def _world_options() -> dict[str, str]:
    return {"全部世界": ""} | {
        f"{web_catalog.WORLD_EMOJI[world]} {web_catalog.WORLD_LABELS[world]}": world
        for world in web_catalog.WORLD_ORDER
    }


# ------------------------------------------------------------------ formatting
def _format_cost(value: Any) -> str:
    if value in (None, "", "—"):
        return "—"
    try:
        return f"¥{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _format_tokens(value: Any) -> str:
    if value in (None, "", "—"):
        return "—"
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number / 1000:.1f}k" if number >= 1000 else str(number)


def _format_range(value: Any) -> str:
    if value in (None, "", "—"):
        return "—"
    if isinstance(value, (list, tuple)):
        parts = [str(item) for item in value if item is not None]
        return " – ".join(parts) if parts else "—"
    return str(value)


def _format_seconds(start: Any, end: Any) -> str:
    from datetime import datetime

    try:
        begin = datetime.fromisoformat(str(start))
        finish = datetime.fromisoformat(str(end))
    except (TypeError, ValueError):
        return "—"
    seconds = (finish - begin).total_seconds()
    if seconds < 0:
        return "—"
    if seconds < 90:
        return f"{seconds:.0f} 秒"
    return f"{seconds / 60:.1f} 分钟"


# ------------------------------------------------------------------ home view
def _map_run_stats(service: RunService | None) -> dict[str, tuple[int, int]]:
    """每张图的本地运行数与该图成功数；只读历史，失败返回空表。"""

    if service is None:
        return {}
    try:
        rows = service.list_runs(limit=500)
    except Exception:  # noqa: BLE001 - 首页不允许因历史损坏而崩溃
        return {}
    stats: dict[str, tuple[int, int]] = {}
    for row in rows:
        runs, success = stats.get(row.map_id, (0, 0))
        stats[row.map_id] = (runs + 1, success + (1 if row.success else 0))
    return stats


def _home(st: Any, service_getter: Any = get_service) -> None:
    service: RunService | None
    try:
        service = service_getter()
    except Exception:  # noqa: BLE001
        service = None

    all_cards = web_catalog.cards()
    stats = _map_run_stats(service)
    total_runs = sum(runs for runs, _ in stats.values())
    total_success = sum(success for _, success in stats.values())

    theme.page_head(
        st,
        "地图大厅",
        "Agent Arena · 十世界三十图",
        "选一张图、定 seed 与预算、启动挑战，实时查看公开动作，结束后回放并导出。"
        "默认离线演示：不花钱、不联网、不发任何请求。",
    )
    theme.stat_tiles(
        st,
        [
            ("地图", str(len(all_cards)), "十世界 · 简单/中等/困难", "accent"),
            ("世界", str(len(web_catalog.WORLD_ORDER)), "每世界 3 张", "info"),
            (
                "本地运行",
                str(total_runs),
                f"成功 {total_success} 局" if total_runs else "还没有运行记录",
                "success" if total_runs else "neutral",
            ),
            ("离线演示", "0 元", "公开规则策略，非模型挑战", "warning"),
        ],
    )

    st.subheader("快速开始")
    quick = st.columns(4)
    with quick[0]:
        with st.container(border=True):
            st.markdown(
                theme.chip_row([theme.chip("推荐", "success"), theme.chip("零 API")])
                + "<div class='aa-card-title'>离线演示</div>"
                "<div class='aa-card-goal'>用公开规则策略跑一局 MAP-01（seed 0，"
                "30 个动作）。用来熟悉界面，结果不代表模型能力。</div>",
                unsafe_allow_html=True,
            )
            if st.button("离线演示：MAP-01（seed 0）", type="primary", width="stretch"):
                _quickstart_offline(st, service_getter)
    with quick[1]:
        with st.container(border=True):
            st.markdown(
                theme.chip_row([theme.chip("需要 API Key", "warning")])
                + "<div class='aa-card-title'>真实模型挑战</div>"
                "<div class='aa-card-goal'>选择地图、模型与请求/token/费用上限，"
                "真实请求会记入单局预算账本。</div>",
                unsafe_allow_html=True,
            )
            if st.button("配置真实挑战", width="stretch"):
                _set_nav(st, VIEW_CONFIG)
    with quick[2]:
        with st.container(border=True):
            st.markdown(
                theme.chip_row([theme.chip("只读", "neutral")])
                + "<div class='aa-card-title'>历史与对照</div>"
                "<div class='aa-card-goal'>筛选本地运行、并排对照 2–4 局、"
                "查看同模型成绩榜与导出 CSV。</div>",
                unsafe_allow_html=True,
            )
            if st.button("打开历史", width="stretch"):
                _set_nav(st, VIEW_HISTORY)
    with quick[3]:
        with st.container(border=True):
            st.markdown(
                theme.chip_row([theme.chip("V12", "accent"), theme.chip("多架构", "info")])
                + "<div class='aa-card-title'>Lab 架构对照</div>"
                "<div class='aa-card-goal'>同一模型、同一地图、同一 seed，"
                "比较 Basic / Memory / Planning 的行为、成本与失败原因。</div>",
                unsafe_allow_html=True,
            )
            if st.button("打开 Lab", width="stretch"):
                _set_nav(st, VIEW_LAB_CONFIG)

    st.subheader("地图大厅")
    filters = st.columns([1.2, 1, 2])
    world_label = filters[0].selectbox("世界", list(_world_options()), index=0)
    difficulty = filters[1].selectbox(
        "展示难度", ["全部难度", "简单", "中等", "困难"], index=0
    )
    query = filters[2].text_input("搜索地图 / 机制 / 目标", "")
    selected = web_catalog.filter_cards(
        world=_world_options()[world_label],
        difficulty="" if difficulty == "全部难度" else difficulty,
        query=query,
    )

    signature = (world_label, difficulty, query)
    if st.session_state.get("home_filter_sig") != signature:
        st.session_state["home_filter_sig"] = signature
        st.session_state["home_page"] = 1

    st.caption(
        f"共 {len(selected)} 张。展示难度是人工可解释标签，保留原设计难度；"
        "不按单模型少量胜率重排。"
    )
    if not selected:
        st.markdown(
            theme.empty_state("🔍", "没有符合筛选条件的地图", "换一个世界或清空搜索词再试。"),
            unsafe_allow_html=True,
        )
        return

    total_pages = max(1, (len(selected) + HOME_PAGE_SIZE - 1) // HOME_PAGE_SIZE)
    page = int(st.session_state.get("home_page", 1) or 1)
    page = max(1, min(total_pages, page))
    st.session_state["home_page"] = page
    start = (page - 1) * HOME_PAGE_SIZE
    visible = selected[start : start + HOME_PAGE_SIZE]

    for offset in range(0, len(visible), 3):
        columns = st.columns(3)
        for column, item in zip(columns, visible[offset : offset + 3], strict=False):
            with column:
                _map_card(st, item, stats.get(item.map_id, (0, 0)))

    if total_pages > 1:
        pager = st.columns([1, 2, 1])
        if pager[0].button("← 上一页", disabled=page <= 1, width="stretch"):
            st.session_state["home_page"] = page - 1
            st.rerun()
        pager[1].markdown(
            f"<div class='aa-quiet' style='text-align:center;padding-top:.45rem'>"
            f"第 {page} / {total_pages} 页 · 共 {len(selected)} 张</div>",
            unsafe_allow_html=True,
        )
        if pager[2].button("下一页 →", disabled=page >= total_pages, width="stretch"):
            st.session_state["home_page"] = page + 1
            st.rerun()


def _quickstart_offline(st: Any, service_getter: Any) -> None:
    config = _default_config("MAP-01", 0, RunMode.OFFLINE, max_decisions=30)
    nonce = str(st.session_state.get("quickstart_nonce", "0"))
    try:
        run_id = service_getter().create_run(
            config,
            idempotency_key=(
                f"quickstart-offline-{config.map_id}-"
                f"{config.environment_seed}-{nonce}"
            ),
        )
    except (RunServiceError, ValueError) as exc:
        st.error(f"无法启动离线演示：{exc}")
    else:
        st.session_state["quickstart_nonce"] = str(int(nonce) + 1)
        st.session_state["active_run"] = run_id
        _set_nav(st, VIEW_LIVE)


def _map_card(
    st: Any,
    item: web_catalog.MapCard,
    stats: tuple[int, int] = (0, 0),
) -> None:
    with st.container(border=True):
        st.markdown(
            theme.map_card_html(
                map_id=item.map_id,
                emoji=item.world_emoji,
                world_label=item.world_label,
                title=item.title,
                display_difficulty=item.display_difficulty,
                design_difficulty=item.design_difficulty,
                goal=item.goal,
                mechanism=item.mechanism,
                decision_budget=item.decision_budget,
                tool_count=item.tool_count,
                seed_count=len(item.seeds),
                note=item.difficulty_note,
                run_count=stats[0],
                success_count=stats[1],
            ),
            unsafe_allow_html=True,
        )
        if st.button("选择这张图", key=f"pick-{item.map_id}", width="stretch"):
            st.session_state["selected_map"] = item.map_id
            _set_nav(st, VIEW_CONFIG)


def _default_config(
    map_id: str,
    seed: int,
    mode: RunMode,
    *,
    max_decisions: int | None = None,
    provider_id: str = OFFLINE_PROVIDER,
    model: str = OFFLINE_MODEL,
    max_requests: int = 60,
    max_input_tokens: int = 200_000,
    max_output_tokens: int = 8_000,
    max_cost_cny: float = DEFAULT_COST_CNY,
) -> RunConfig:
    return RunConfig(
        map_id=map_id,
        environment_seed=seed,
        mode=mode,
        provider_id=provider_id,
        model=model,
        agent="public_heuristic_policy" if mode is RunMode.OFFLINE else "v10_action_loop",
        max_decisions=max_decisions or decision_budget(map_id),
        max_requests=max_requests if mode is RunMode.LIVE else 1,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        max_cost_cny=Decimal(str(max_cost_cny)),
    )


# ---------------------------------------------------------------- config view
def _config_view(st: Any, service_getter: Any = get_service) -> None:
    cards = web_catalog.cards()
    labels = {
        f"{item.map_id} · {item.title}"
        f"（{item.world_label} / {item.design_difficulty}）": item
        for item in cards
    }
    default_map = str(st.session_state.get("selected_map", "MAP-01"))
    default_label = next(
        (label for label, item in labels.items() if item.map_id == default_map),
        next(iter(labels)),
    )
    theme.page_head(
        st,
        "挑战配置",
        "配置一局挑战",
        "先读公开规则与动作契约，再决定 seed、执行模式与预算。"
        "页面不会回显密钥，也不会替你选模型。",
    )
    choice = st.selectbox("地图", list(labels), index=list(labels).index(default_label))
    item = labels[choice]
    st.session_state["selected_map"] = item.map_id

    left, right = st.columns([1.6, 1], gap="large")
    with left:
        st.markdown(
            theme.chip_row(
                [
                    theme.chip(item.map_id, "accent"),
                    theme.chip(f"{item.world_emoji} {item.world_label}"),
                    theme.chip(
                        f"展示难度 {item.display_difficulty}",
                        theme.difficulty_tone(item.display_difficulty),
                    ),
                    theme.chip(f"设计难度 {item.design_difficulty}"),
                    theme.chip(f"运行时 {item.runtime}"),
                ]
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='aa-card-title' style='font-size:1.3rem'>"
            f"{item.world_emoji} {item.title}</div>"
            f"<div class='aa-card-goal' style='min-height:0;font-size:.9rem'>"
            f"{item.goal}</div>",
            unsafe_allow_html=True,
        )
        theme.stat_tiles(
            st,
            [
                ("决策预算", str(item.decision_budget), "动作数上限", "accent"),
                ("可用 seed", str(len(item.seeds)), "环境实例", "info"),
                ("工具", str(item.tool_count), "动作契约条目", "neutral"),
                ("公开规则", str(item.rule_count), "条", "neutral"),
            ],
        )
        st.markdown(
            f"<div class='aa-card-note'><b>难度说明</b> · {item.difficulty_note}</div>",
            unsafe_allow_html=True,
        )

    with right:
        seed = st.selectbox("环境 seed", list(item.seeds), index=0)
        detail = web_catalog.map_detail(item.map_id, int(seed))
        if detail["watch_out"]:
            st.warning(detail["watch_out"])

    detail = web_catalog.map_detail(item.map_id, int(seed))
    st.subheader("公开信息")
    rule_tab, contract_tab, field_tab, version_tab = st.tabs(
        ["公开规则", "动作契约", "观察字段", "版本与 hash"]
    )
    with rule_tab:
        st.markdown("**公开规则**")
        for index, rule in enumerate(detail["rules"], start=1):
            st.markdown(f"{index}. {rule}")
        st.markdown(f"**成功**：{detail['success_text']}")
        st.markdown(f"**失败 / 截尾**：{detail['failure_text']}")
    with contract_tab:
        st.markdown("**动作契约（字段类型必须匹配）**")
        st.code("\n".join(detail["contract"]), language="text")
        if detail["contract_hints"]:
            st.markdown("**本图接口提醒**")
            for hint in detail["contract_hints"]:
                st.markdown(f"- {hint}")
    with field_tab:
        st.markdown("**公开观察字段**")
        st.markdown("、".join(f"`{field}`" for field in detail["public_fields"]))
        st.markdown("**实例参数（scenario_descriptor）**")
        st.json(detail["scenario_descriptor"])
    with version_tab:
        st.markdown(
            theme.kv_block(
                [
                    ("rule_hash", item.rule_hash),
                    ("metric_hash", item.metric_hash),
                    ("runtime", item.runtime),
                    ("primary_metric", item.primary_metric),
                ]
            ),
            unsafe_allow_html=True,
        )
        st.caption("hash 用于判断两局是否可直接对照；页面不会修改它们。")

    st.subheader("运行参数")
    mode_column, budget_column = st.columns([1, 1.5], gap="large")
    with mode_column:
        mode_label_choice = st.radio(
            "执行模式",
            ["离线演示（不花钱）", "真实模型挑战"],
            horizontal=False,
            help="离线演示使用公开规则策略，不是模型挑战；真实模式会向 Provider 发送请求。",
        )
        live = mode_label_choice.startswith("真实")
        mode = RunMode.LIVE if live else RunMode.OFFLINE
        statuses = {status.provider_id: status for status in provider_statuses()}
        provider_id = OFFLINE_PROVIDER
        model = OFFLINE_MODEL
        if live:
            provider_labels = {
                "[OI]-compatible / MiMo": "openai_compatible",
                "本地 Ollama": "ollama",
            }
            provider_choice = st.selectbox("Provider", list(provider_labels), index=0)
            provider_id = provider_labels[provider_choice]
            status = statuses[provider_id]
            model = st.text_input("模型", value=status.model)
            st.markdown(
                theme.kv_block(
                    [
                        ("配置来源", "本机 .env"),
                        ("密钥", status.key_state),
                        ("地址", status.base_url_host or "未配置"),
                    ]
                ),
                unsafe_allow_html=True,
            )
            if provider_id == "openai_compatible" and not status.configured:
                st.error("未配置 API Key / Base URL；请先编辑本机 .env，或改用离线演示。")
        else:
            st.markdown(
                theme.banner(
                    "离线演示",
                    "公开启发式规则策略，不发送网络请求，不产生费用；"
                    "结果不能用于模型能力结论。",
                    tone_name="success",
                    code="OFFLINE",
                ),
                unsafe_allow_html=True,
            )

    with budget_column:
        budget_first, budget_second = st.columns(2)
        max_decisions = budget_first.slider(
            "决策上限",
            1,
            MAX_DECISIONS,
            int(min(item.decision_budget, MAX_DECISIONS)),
            help="本局最多执行多少个动作。",
        )
        max_requests = budget_second.number_input(
            "请求上限",
            min_value=1,
            max_value=MAX_REQUESTS,
            value=60 if live else 1,
            step=1,
        )
        token_first, token_second = st.columns(2)
        max_input_tokens = token_first.number_input(
            "输入 token 上限",
            min_value=1_000,
            max_value=MAX_INPUT_TOKENS,
            value=200_000,
            step=10_000,
        )
        max_output_tokens = token_second.number_input(
            "输出 token 上限",
            min_value=64,
            max_value=MAX_OUTPUT_TOKENS,
            value=8_000,
            step=500,
        )
        max_cost = st.number_input(
            "费用上限（CNY）",
            min_value=0.01,
            max_value=float(MAX_COST_CNY),
            value=float(DEFAULT_COST_CNY),
            step=0.1,
            help="只有登记了价格的模型才能作为金额硬门禁；其它模型以请求/token 上限为准。",
        )
        st.markdown(
            theme.kv_block(
                [
                    ("动作 / 预算", f"{int(max_decisions)} / {item.decision_budget}"),
                    ("请求上限", str(int(max_requests))),
                    ("token 上限", f"{_format_tokens(max_input_tokens)} 入 / "
                     f"{_format_tokens(max_output_tokens)} 出"),
                    ("费用上限", _format_cost(max_cost)),
                ]
            ),
            unsafe_allow_html=True,
        )
        st.caption("费用不是供应商账单；未知 usage 会立即封账，不自动重试。")

    confirmed = True
    if live:
        st.warning(
            "真实模式会向 Provider 发送请求，可能产生费用。请确认地图、seed、"
            "模型、请求/token/费用上限后再继续。"
        )
        confirmed = st.checkbox(
            "我确认发送真实请求并接受可能产生的费用",
            value=False,
        )

    if st.button("开始挑战", type="primary", disabled=not confirmed, width="stretch"):
        try:
            config = RunConfig(
                map_id=item.map_id,
                environment_seed=int(seed),
                mode=mode,
                provider_id=provider_id,
                model=model,
                agent="public_heuristic_policy" if not live else "v10_action_loop",
                max_decisions=int(max_decisions),
                max_requests=int(max_requests),
                max_input_tokens=int(max_input_tokens),
                max_output_tokens=int(max_output_tokens),
                max_cost_cny=Decimal(str(max_cost)),
            )
        except (ValueError, InvalidOperation) as exc:
            st.error(f"参数不合法：{exc}")
            return
        nonce = str(st.session_state.get("submit_nonce", "0"))
        payload = json.dumps(config.public_dict(), ensure_ascii=False, sort_keys=True)
        key = sha256(f"{payload}|{nonce}".encode()).hexdigest()
        check = configuration_check(config)
        if not check["ok"]:
            st.error(str(check["detail"]))
            return
        try:
            run_id = service_getter().create_run(config, idempotency_key=key)
        except ConcurrentLiveRunError as exc:
            st.error(str(exc))
        except RunServiceError as exc:
            st.error(f"无法启动：{exc}")
        except ValueError as exc:
            st.error(f"配置被拒绝：{exc}")
        else:
            st.session_state["active_run"] = run_id
            st.session_state["submit_nonce"] = str(int(nonce) + 1)
            st.success(f"已创建运行 {run_id}")
            _set_nav(st, VIEW_LIVE)


# ------------------------------------------------------------------ live view
def _status_badge(st: Any, state: str) -> None:
    text = f"{state_label(state)}（{state}）"
    if state == RunState.SUCCEEDED.value:
        st.success(text)
    elif state in {RunState.FAILED.value, RunState.PROVIDER_ERROR.value}:
        st.error(text)
    elif state == RunState.BUDGET_REACHED.value:
        st.warning(text)
    else:
        st.info(text)


def _live_panel(st: Any, service: RunService, run_id: str) -> None:
    try:
        status = service.get_run(run_id)
    except Exception as exc:  # noqa: BLE001 - missing/corrupt run
        st.error(f"无法读取运行 {run_id}：{exc}")
        return
    st.subheader(f"运行 {run_id}")
    st.markdown(
        theme.chip_row(
            [
                theme.chip(str(status.config.get("map_id", "")), "accent"),
                theme.chip(mode_label(str(status.config.get("mode", "")))),
                theme.chip(f"模型 {status.config.get('model', '')}"),
                theme.chip(f"seed {status.config.get('environment_seed', '')}"),
            ]
        ),
        unsafe_allow_html=True,
    )
    tone = theme.state_tone(status.state.value)
    st.markdown(
        theme.banner(
            state_label(status.state.value),
            status.message or "",
            tone_name=tone,
            code=status.state.value,
        ),
        unsafe_allow_html=True,
    )
    ratio = status.progress
    st.markdown(theme.progress(ratio, tone_name=tone), unsafe_allow_html=True)
    st.caption(
        f"进度 {status.decisions} / {status.decision_budget} 个动作"
        f"（{ratio * 100:.0f}%）。页面刷新只读 manifest，不会重复执行。"
    )

    budget = status.budget or {}
    theme.stat_tiles(
        st,
        [
            ("动作数", str(status.decisions), f"预算 {status.decision_budget}", "accent"),
            ("请求数", str(budget.get("requests", "—")), "Provider 调用", "info"),
            (
                "输入 / 输出 token",
                f"{_format_tokens(budget.get('input_tokens'))} / "
                f"{_format_tokens(budget.get('output_tokens'))}",
                "本局累计",
                "neutral",
            ),
            (
                "费用 CNY",
                "未知"
                if budget.get("cost_unknown")
                else _format_cost(budget.get("cost_settled_cny")),
                "本地门禁，不是账单",
                "warning" if budget.get("cost_unknown") else "neutral",
            ),
        ],
    )

    if not status.terminal:
        if st.button("停止运行", key=f"stop-{run_id}"):
            service.cancel_run(run_id)
            st.warning("停止请求已收到；将在当前请求或步骤结束后生效。")
    else:
        if st.button("查看结果", type="primary", key=f"result-{run_id}"):
            st.session_state["active_run"] = run_id
            _set_nav(st, VIEW_RESULT)

    replay = service.load_replay(run_id)
    steps = replay["steps"]
    if replay["events_skipped"]:
        st.warning(f"日志中有 {replay['events_skipped']} 行损坏，已跳过但保留其余记录。")
    st.subheader("动作时间线")
    if not steps:
        st.markdown(
            theme.empty_state("⏳", "还没有动作", "运行在队列中或刚刚开始；自动刷新会持续更新。"),
            unsafe_allow_html=True,
        )
        return
    show_all = st.checkbox("显示全部动作", value=False, key=f"all-{run_id}")
    limit = len(steps) if show_all else 20
    if not show_all and len(steps) > limit:
        st.caption(f"只显示最近 {limit} 条；共 {len(steps)} 条。")
    st.dataframe(_timeline_rows(steps, limit), width="stretch", hide_index=True)


def _timeline_rows(steps: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    reasons = [step.get("decision_reason") for step in steps]
    present = [str(item) for item in reasons if item]
    # 离线演示时每步理由都是同一句，逐行重复只会把表格撑宽。
    uniform = bool(present) and len(set(present)) == 1 and len(present) == len(steps)
    for position, step in enumerate(steps[-limit:]):
        action = step.get("action") or {}
        row: dict[str, Any] = {
            "步": step.get("decision_index"),
            "动作": action.get("tool") if isinstance(action, dict) else "",
            "目标": _action_target(action),
            "结果": step.get("result"),
            "状态": step.get("status"),
            "tokens": f"{step.get('input_tokens', 0)}/{step.get('output_tokens', 0)}",
        }
        if present:
            reason = step.get("decision_reason") or "—"
            if uniform and position > 0:
                reason = "同上"
            row["理由"] = reason
        rows.append(row)
    return rows


def _action_target(action: Any) -> str:
    if not isinstance(action, dict):
        return ""
    for key in (
        "to",
        "target",
        "target_id",
        "next_node",
        "area",
        "room",
        "claim_id",
        "entry_id",
        "item",
        "bearing",
        "edge_id",
    ):
        value = action.get(key)
        if value not in (None, ""):
            return str(value)
    fields = sorted(key for key in action if key != "tool")
    return ",".join(fields[:4])


def _live_view(st: Any, service_getter: Any = get_service) -> None:
    service = service_getter()
    theme.page_head(
        st,
        "运行监控",
        "运行监控",
        "状态、预算与动作全部来自本地 manifest 与 JSONL；刷新页面不会重新执行模型。",
    )
    run_id = str(st.session_state.get("active_run", ""))
    rows = service.list_runs(limit=30)
    if not rows:
        st.markdown(
            theme.empty_state(
                "🛰️",
                "还没有运行记录",
                "先到「挑战配置」启动一局，或用首页的离线演示快速体验。",
            ),
            unsafe_allow_html=True,
        )
        return
    labels = {f"{row.run_id} · {row.map_id} · {state_label(row.state)}": row.run_id for row in rows}
    if run_id not in labels.values():
        run_id = next(iter(labels.values()))
    choice = st.selectbox(
        "运行",
        list(labels),
        index=list(labels.values()).index(run_id),
    )
    run_id = labels[choice]
    st.session_state["active_run"] = run_id
    auto = st.checkbox("自动刷新（1.5 秒）", value=True)
    if auto and hasattr(st, "fragment"):
        st.fragment(run_every="1.5s")(_live_panel)(st, service, run_id)
    else:
        _live_panel(st, service, run_id)
        if st.button("刷新", key=f"refresh-{run_id}"):
            st.rerun()


# ---------------------------------------------------------------- result view
def _result_view(st: Any, service_getter: Any = get_service) -> None:
    service = service_getter()
    theme.page_head(
        st,
        "结果与回放",
        "结果与回放",
        "结局只由环境终止码与指标五态解释；逐步回放只展示公开 Observation 与动作。",
    )
    rows = service.list_runs(limit=60)
    if not rows:
        st.markdown(
            theme.empty_state("📄", "还没有可查看的结果", "完成一局之后这里会出现回放与导出。"),
            unsafe_allow_html=True,
        )
        return
    labels = {
        f"{row.run_id} · {row.map_id} · {state_label(row.state)}": row.run_id for row in rows
    }
    active = str(st.session_state.get("active_run", ""))
    if active not in labels.values():
        active = next(iter(labels.values()))
    choice = st.selectbox("运行", list(labels), index=list(labels.values()).index(active))
    run_id = labels[choice]
    st.session_state["active_run"] = run_id
    replay = service.load_replay(run_id)
    result = replay["result"] or {}
    status = replay["status"]
    manifest = replay["manifest"]

    title = str(result.get("title") or manifest.get("title") or "")
    state_value = str(result.get("state") or status.state.value)
    succeeded = state_value == RunState.SUCCEEDED.value or bool(result.get("success"))
    st.subheader(f"{result.get('map_id') or manifest.get('map_id')} · {title}")
    st.markdown(
        theme.chip_row(
            [
                theme.chip(mode_label(str(manifest.get("mode", "")))),
                theme.chip(f"模型 {manifest.get('model', '')}"),
                theme.chip(f"seed {manifest.get('environment_seed', '')}"),
                theme.chip(
                    "用时 "
                    + _format_seconds(
                        manifest.get("started_at"), manifest.get("finished_at")
                    )
                ),
            ]
        ),
        unsafe_allow_html=True,
    )

    raw_failure = result.get("failure")
    failure: dict[str, Any] = raw_failure if isinstance(raw_failure, dict) else {}
    tone = theme.state_tone(state_value)
    headline = str(failure.get("headline") or state_label(state_value))
    detail = str(failure.get("detail") or result.get("message") or "")
    st.markdown(
        theme.banner(
            headline,
            detail,
            tone_name=tone,
            code=state_value,
        ),
        unsafe_allow_html=True,
    )
    attribution = result.get("attribution")
    if isinstance(attribution, dict) and attribution.get("label"):
        label = f"{attribution.get('label_zh')}（{attribution.get('label')}）"
        detail_text = str(attribution.get("detail") or "")
        if succeeded:
            # 成功局没有“失败归因”；这里只做机制复核说明，避免把成功读成失败。
            st.caption(f"机制复核：{label} — {detail_text}")
        else:
            st.info(f"失败归因：{label} — {detail_text}")

    usage_raw = result.get("usage")
    usage: dict[str, Any] = usage_raw if isinstance(usage_raw, dict) else {}
    theme.stat_tiles(
        st,
        [
            (
                "动作数",
                str(result.get("decision_count", status.decisions)),
                f"预算 {status.decision_budget}",
                "accent",
            ),
            ("非法动作", str(result.get("invalid_actions", "—")), "契约校验失败", "danger"
             if result.get("invalid_actions") else "success"),
            ("被拒动作", str(result.get("rejected_actions", "—")), "环境前置条件", "warning"
             if result.get("rejected_actions") else "success"),
            (
                "费用 CNY",
                "未知"
                if usage.get("cost_unknown")
                else _format_cost(usage.get("cost_settled_cny")),
                "本地门禁，不是账单",
                "warning" if usage.get("cost_unknown") else "neutral",
            ),
        ],
    )

    primary = result.get("primary_metric")
    if primary:
        primary_state = str(result.get("primary_metric_state", ""))
        st.markdown(
            f"<div class='aa-inline-meta'>"
            f"<span>主指标 <b>{primary}</b></span>"
            f"{theme.chip(metric_state_label(primary_state), theme.metric_tone(primary_state))}"
            f"<span>值 <b>{result.get('primary_metric_value')}</b>"
            f" {result.get('primary_metric_unit') or ''}</span></div>",
            unsafe_allow_html=True,
        )

    _metrics_table(st, result)
    _observation_chart(st, replay["steps"])

    st.subheader("逐步回放")
    steps = replay["steps"]
    if not steps:
        st.markdown(
            theme.empty_state("🎬", "该运行没有动作记录", "检查 events.jsonl 是否完整。"),
            unsafe_allow_html=True,
        )
    else:
        index = st.slider("步骤", 1, len(steps), len(steps)) - 1
        step = steps[index]
        st.caption(f"第 {index + 1} / {len(steps)} 步 · 动作与公开 Observation")
        action_column, observation_column = st.columns(2, gap="large")
        with action_column:
            st.markdown("**动作**")
            st.json(step.get("action") or {})
        with observation_column:
            st.markdown("**公开 Observation**")
            st.json(step.get("observation_after") or {})
        with st.expander("完整动作时间线", expanded=False):
            st.dataframe(_timeline_rows(steps, len(steps)), width="stretch", hide_index=True)

    _downloads(st, manifest, result, steps)

    st.subheader("版本与安全")
    hashes = [
        ("scenario_hash", str(result.get("scenario_hash") or "—")),
        ("rule_hash", str(result.get("rule_hash") or "—")),
        ("metric_hash", str(result.get("metric_hash") or "—")),
        ("metric_schema_hash", str(result.get("metric_schema_hash") or "—")),
        ("prompt_hash", str(result.get("prompt_hash") or "—")),
    ]
    st.markdown(
        theme.kv_block(
            [
                (label, f"{value[:16]}…" if len(value) > 16 else value)
                for label, value in hashes
            ]
        ),
        unsafe_allow_html=True,
    )
    with st.expander("完整 hash"):
        st.markdown(theme.kv_block(hashes), unsafe_allow_html=True)
    st.caption(
        "导出只包含公开 Observation、动作与指标；不含 API Key、隐藏真值、"
        "完整内部 prompt 或未脱敏 Provider 响应。"
    )
    if st.button("用相同地图与 seed 再跑一局", key=f"rerun-{run_id}"):
        st.session_state["selected_map"] = str(manifest.get("map_id", "MAP-01"))
        nonce = int(str(st.session_state.get("submit_nonce", "0")))
        st.session_state["submit_nonce"] = str(nonce + 1)
        _set_nav(st, VIEW_CONFIG)


def _metrics_table(st: Any, result: dict[str, Any]) -> None:
    specs = result.get("metric_specs") or []
    metrics = result.get("metrics") or {}
    if not specs or not isinstance(metrics, dict):
        return
    compact = {
        "VALID": "有效",
        "CENSORED": "截尾",
        "NOT_APPLICABLE": "不适用",
        "MISSING": "缺失",
        "INVALID": "非法",
    }
    rows: list[dict[str, Any]] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        metric_id = str(spec.get("metric_id", ""))
        value = metrics.get(metric_id, {})
        if not isinstance(value, dict):
            value = {}
        raw_state = str(value.get("state", ""))
        raw_value = value.get("value")
        rows.append(
            {
                "指标": metric_id,
                "五态": compact.get(raw_state, metric_state_label(raw_state)),
                "值": "—" if raw_value is None else str(raw_value),
                "单位": spec.get("unit") or "",
                "范围": _format_range(spec.get("valid_range")),
            }
        )
    if not rows:
        return
    st.subheader("指标（五态）")
    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption("CENSORED / N/A / 缺失不会被渲染成 0。")
    with st.expander("指标公式"):
        for spec in specs:
            if isinstance(spec, dict):
                st.markdown(f"- `{spec.get('metric_id', '')}`：{spec.get('formula') or '—'}")


def _observation_chart(st: Any, steps: list[dict[str, Any]]) -> None:
    if len(steps) < 2:
        return
    sample = steps[-1].get("observation_after")
    if not isinstance(sample, dict):
        return
    numeric = [
        key
        for key, value in sample.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if not numeric:
        return
    series: dict[str, list[float]] = {}
    for key in sorted(numeric):
        values: list[float] = []
        for step in steps:
            observation = step.get("observation_after") or {}
            value = observation.get(key) if isinstance(observation, dict) else None
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
        if len(values) == len(steps) and len(set(values)) > 1:
            series[key] = values
    if not series:
        return
    st.subheader("公开状态走势")
    st.caption("只画公开 Observation 中每步都出现的数值字段，不做插值。")
    key = st.selectbox("字段", sorted(series))
    _line_chart(st, key, series[key])


def _line_chart(st: Any, key: str, values: list[float]) -> None:
    """优先用 Altair 让纵轴从数据范围开始；不可用时退回内置折线图。"""

    try:
        import altair as alt
    except ImportError:  # pragma: no cover - streamlit 自带 altair，这里只做兜底
        st.line_chart({key: values})
        return
    records = [
        {"步": index + 1, key: value} for index, value in enumerate(values)
    ]
    try:
        chart = (
            # altair 未随包提供类型信息，Data/Gradient 在 mypy 里是未标注调用。
            alt.Chart(alt.Data(values=records))  # type: ignore[no-untyped-call]
            .mark_area(
                line={"color": "#4c6ef5", "strokeWidth": 2},
                color=alt.Gradient(  # type: ignore[no-untyped-call]
                    gradient="linear",
                    stops=[
                        alt.GradientStop(color="rgba(76,110,245,0.02)", offset=0),
                        alt.GradientStop(color="rgba(76,110,245,0.28)", offset=1),
                    ],
                    x1=1,
                    x2=1,
                    y1=1,
                    y2=0,
                ),
            )
            .encode(
                x=alt.X("步:Q", title="步", axis=alt.Axis(format="d", tickMinStep=1)),
                y=alt.Y(f"{key}:Q", title=key, scale=alt.Scale(zero=False)),
                tooltip=["步:Q", f"{key}:Q"],
            )
            .properties(height=200)
        )
        st.altair_chart(chart, width="stretch")
    except Exception:  # noqa: BLE001 - 图表只是辅助，任何异常都退回内置图
        st.line_chart({key: values})


def _downloads(
    st: Any,
    manifest: dict[str, Any],
    result: dict[str, Any],
    steps: list[dict[str, Any]],
) -> None:
    st.subheader("导出")
    run_id = str(manifest.get("run_id", "run"))
    document = replay_document(manifest, result, steps)
    with st.container(border=True):
        st.caption("四种格式内容一致；CSV 带 UTF-8 BOM，可直接用 Excel 打开。")
        first, second, third, fourth = st.columns(4)
        first.download_button(
            "回放 JSON",
            data=export_json_bytes(document),
            file_name=export_filename(run_id, "json"),
            mime="application/json",
            width="stretch",
        )
        second.download_button(
            "摘要 JSON",
            data=export_summary_bytes(result),
            file_name=export_filename(run_id, "summary"),
            mime="application/json",
            width="stretch",
        )
        third.download_button(
            "逐动作 CSV",
            data=export_actions_csv(steps),
            file_name=export_filename(run_id, "csv"),
            mime="text/csv",
            width="stretch",
        )
        fourth.download_button(
            "公开 Trace JSONL",
            data=export_trace_jsonl(steps),
            file_name=export_filename(run_id, "trace"),
            mime="application/x-ndjson",
            width="stretch",
        )


# --------------------------------------------------------------- history view
def _history_view(st: Any, service_getter: Any = get_service) -> None:
    service = service_getter()
    theme.page_head(
        st,
        "历史与对照",
        "历史与对照",
        "本地运行的全部记录。只有同地图、同规则/指标版本、同模式的两局才允许直接对照。",
    )
    all_rows = service.list_runs(limit=500)
    diagnostics = service.diagnostics()
    if diagnostics["broken"]:
        st.warning(f"有 {len(diagnostics['broken'])} 个损坏的运行目录，已跳过。")
    if not all_rows:
        st.markdown(
            theme.empty_state("🗂️", "还没有历史运行", "跑完一局后这里会累积记录与成绩榜。"),
            unsafe_allow_html=True,
        )
        return

    finished = [row for row in all_rows if row.finished_at]
    success_total = sum(1 for row in finished if row.success)
    cost_total = sum(row.cost_settled_cny or 0.0 for row in all_rows)
    theme.stat_tiles(
        st,
        [
            ("本地运行", str(len(all_rows)), "含未终局", "accent"),
            ("已完成", str(len(finished)), "进入终态", "info"),
            (
                "成功率",
                f"{success_total / len(finished) * 100:.0f}%" if finished else "—",
                f"{success_total} / {len(finished)} 局",
                "success" if success_total else "neutral",
            ),
            ("累计费用", _format_cost(cost_total), "本地结算合计", "warning"),
        ],
    )

    maps = sorted({row.map_id for row in all_rows})
    providers = sorted({row.provider_id for row in all_rows})
    seeds = sorted({row.environment_seed for row in all_rows})
    first, second, third, fourth = st.columns(4)
    map_choice = first.selectbox("地图", ["全部地图"] + maps)
    states = sorted({row.state for row in all_rows})
    state_choice = second.selectbox("状态", ["全部状态"] + states)
    modes = sorted({row.mode for row in all_rows})
    mode_choice = third.selectbox("模式", ["全部模式"] + modes)
    provider_choice = fourth.selectbox("Provider", ["全部 Provider"] + providers)
    fifth, sixth, seventh = st.columns([1, 1.4, 1])
    seed_choice = fifth.selectbox("seed", ["全部 seed"] + [str(seed) for seed in seeds])
    query = sixth.text_input("搜索 run_id / 模型 / 标题", "")
    since = seventh.text_input("起始日期（YYYY-MM-DD）", "")
    filtered = filter_runs(
        all_rows,
        map_id="" if map_choice == "全部地图" else map_choice,
        state="" if state_choice == "全部状态" else state_choice,
        mode="" if mode_choice == "全部模式" else mode_choice,
        provider_id="" if provider_choice == "全部 Provider" else provider_choice,
        environment_seed=None if seed_choice == "全部 seed" else int(seed_choice),
        query=query,
        since=since,
    )
    st.caption(f"{len(filtered)} / {len(all_rows)} 局")
    table = [
        {
            "run_id": row.run_id,
            "地图": row.map_id,
            "标题": row.display_title,
            "模型": row.model,
            "seed": row.environment_seed,
            "状态": state_label(row.state),
            "结局": row.outcome or "—",
            "动作 / 预算": f"{row.decisions} / {row.decision_budget}",
            "费用": "—" if row.cost_settled_cny is None else row.cost_settled_cny,
        }
        for row in filtered
    ]
    st.dataframe(table, width="stretch", hide_index=True)
    if filtered:
        open_column, export_column = st.columns([1.6, 1])
        options = {
            f"{row.run_id} · {row.map_id} · {state_label(row.state)}": row.run_id
            for row in filtered
        }
        choice = open_column.selectbox("打开某局的回放", list(options), index=0)
        if open_column.button("打开结果", type="primary"):
            st.session_state["active_run"] = options[choice]
            _set_nav(st, VIEW_RESULT)
        _history_export(st, filtered, export_column)

    st.subheader("多局对照（2–4 局）")
    if len(filtered) < 2:
        st.info("至少需要两局同条件运行才能对照。")
    else:
        labels = {
            f"{row.run_id} · {row.map_id} · {state_label(row.state)}": row
            for row in filtered
        }
        names = list(labels)
        selected_names = st.multiselect(
            "对照运行（2–4 局）",
            names,
            default=names[: min(2, len(names))],
            max_selections=4,
        )
        if len(selected_names) < 2:
            st.info("请选择至少两局。")
        else:
            chosen = [labels[name] for name in selected_names]
            verdict = compatibility_all(chosen)
            if not verdict["compatible"]:
                st.error(
                    "不可直接比较：" + "、".join(verdict["mismatches"])
                    + "。请只并排查看，不要当作同一条件对照。"
                )
            elif verdict["warnings"]:
                st.warning("；".join(verdict["warnings"]))
            else:
                st.success("同地图、同规则/指标版本、同模式，可直接对照。")
            st.dataframe(
                multi_comparison_rows(chosen),
                width="stretch",
                hide_index=True,
            )

    st.subheader("本地同模型成绩榜")
    rows = leaderboard(filtered)
    if not rows:
        st.info("暂无可排行的终局运行。")
    else:
        st.dataframe(rows, width="stretch", hide_index=True)
        st.caption(
            "只比较同地图、同模型、同模式、同规则/指标版本；seed 与预算差异见列。"
            "不是跨模型公平排名。"
        )


def _history_export(st: Any, rows: list[Any], target: Any | None = None) -> None:
    buffer = io.StringIO(newline="")
    fields = [
        "run_id",
        "map_id",
        "world",
        "mode",
        "provider_id",
        "model",
        "environment_seed",
        "state",
        "outcome",
        "success",
        "decisions",
        "created_at",
        "finished_at",
        "cost_settled_cny",
        "cost_unknown",
        "rule_hash",
        "metric_hash",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row.to_dict())
    host = target if target is not None else st
    host.download_button(
        "导出筛选结果 CSV",
        data=buffer.getvalue().encode("utf-8-sig"),
        file_name="agent-arena-runs.csv",
        mime="text/csv",
        width="stretch",
    )


# -------------------------------------------------------------- settings view
def _settings_view(st: Any) -> None:
    theme.page_head(
        st,
        "设置与帮助",
        "设置与帮助",
        "Provider 状态只读；密钥只从本机 .env 或环境变量读取，页面不会显示、回显或提交密钥。",
    )
    st.subheader("Provider 配置")
    statuses = provider_statuses()
    st.dataframe(
        [
            {
                "Provider": status.label,
                "状态": "已配置" if status.configured else "未配置",
                "模型": status.model,
                "地址": status.base_url_host or "—",
                "密钥": status.key_state,
            }
            for status in statuses
        ],
        width="stretch",
        hide_index=True,
    )

    with st.expander("连接检查（会发送 1 次最小请求）"):
        st.warning("该检查可能产生极少量费用，且不进入挑战预算账本。")
        confirmed = st.checkbox("我确认发送一次最小连接检查", value=False)
        model = st.text_input("检查用模型", value=statuses[0].model)
        if st.button("执行连接检查", disabled=not confirmed):
            config = _default_config(
                "MAP-01",
                0,
                RunMode.LIVE,
                provider_id="openai_compatible",
                model=model,
            )
            with st.spinner("正在检查…"):
                probe = probe_live_provider(config)
            if probe["ok"]:
                st.success(str(probe["detail"]))
            else:
                st.error(str(probe["detail"]))

    with st.expander("费用与预算边界"):
        limits = BudgetLimits(
            max_requests=MAX_REQUESTS,
            max_input_tokens=MAX_INPUT_TOKENS,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            max_cost_cny=Decimal(str(MAX_COST_CNY)),
        )
        st.write("平台硬上限（页面与 API 均不可突破）：")
        st.json(limits.public_dict())
        st.write(
            "请求前先检查请求数、token 预算与（可得时）费用上限；Provider 未返回 usage "
            "时立即按未知消费停止，不自动重试。"
        )
        st.caption("RunBudget 只做本地门禁，不等于 Provider 账单。")

    with st.expander("常见错误"):
        for category in (
            "missing_api_key",
            "APIConnectionError",
            "APITimeoutError",
            "RateLimitError",
            "NotFoundError",
            "BudgetExceeded",
            "unknown",
        ):
            st.markdown(f"- **{category}**：{error_hint(category)}")

    with st.expander("日志与数据位置"):
        st.code(str(WEB_RUNS_DIR), language="text")
        st.write("每局一个目录：manifest.json、events.jsonl、result.json；可整体删除。")
        try:
            diagnostics = get_service().diagnostics()
            st.write(f"当前运行数：{diagnostics.get('runs', '—')}")
        except Exception:  # noqa: BLE001 - settings page must not crash
            st.write("当前运行数：—")


# --------------------------------------------------------------- research view
def _research_view(st: Any, view: str) -> None:
    st.title("Agent Arena 研究回放（只读）")
    st.caption("仅展示已有 trace/benchmark；不启动新实验；不触碰密钥。")
    if view == "单局回放":
        _replay_view(st)
    elif view == "矩阵总览":
        _matrix_view(st)
    elif view == "错误热点":
        _hotspot_view(st)
    else:
        _compare_view(st)


def _research_hub(st: Any) -> None:
    theme.page_head(
        st,
        "研究回放",
        "研究回放（只读）",
        "读取 runs/ 与 results/ 中已有的研究 trace 与 benchmark CSV；"
        "与网页挑战运行互不影响。",
    )
    view = st.radio("视图", RESEARCH_VIEWS, horizontal=True)
    if view == "单局回放":
        _replay_view(st)
    elif view == "矩阵总览":
        _matrix_view(st)
    elif view == "错误热点":
        _hotspot_view(st)
    else:
        _compare_view(st)


def main() -> None:
    st = _load_streamlit()
    if hasattr(st, "set_page_config"):
        st.set_page_config(
            page_title="Agent Arena · 十世界三十图",
            page_icon="◈",
            layout="wide",
            # "auto" 让窄屏（手机）默认收起侧边栏，宽屏保持展开。
            initial_sidebar_state="auto",
        )
    if hasattr(st, "markdown"):
        st.markdown(theme.stylesheet(), unsafe_allow_html=True)
    _apply_deep_link(st)
    _apply_pending_nav(st)
    nav = _sidebar(st)
    if nav in LEGACY_VIEWS:
        _research_view(st, nav)
        _sidebar_footer(st)
        return
    if nav == VIEW_HOME:
        _home(st)
    elif nav == VIEW_CONFIG:
        _config_view(st)
    elif nav == VIEW_LIVE:
        _live_view(st)
    elif nav == VIEW_RESULT:
        _result_view(st)
    elif nav == VIEW_HISTORY:
        _history_view(st)
    elif nav in LAB_VIEWS:
        lab_ui.render(st, get_lab_service, nav)
    elif nav == VIEW_SETTINGS:
        _settings_view(st)
    elif nav == VIEW_RESEARCH:
        _research_hub(st)
    else:
        _home(st)
    # 侧边栏摘要放在视图之后渲染，才能反映本页刚选中的运行。
    _sidebar_footer(st)


if __name__ == "__main__":
    main()
