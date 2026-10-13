"""Agent Arena 研究可视化（只读 Streamlit 界面）。

运行（不改 pyproject/uv.lock，用 --with 临时提供 streamlit）：

    uv run --with streamlit streamlit run src/agent_arena/ui/app.py

能力：①单局 trace 步骤回放（含错误热点）；②矩阵总览（runs/ 下多局聚合、
Success@K）；③错误热点（T4 三类计数）；④两份 benchmark CSV 对照。
只读 runs/ 与 results/ 下的用户自选文件；绝不读取 `.env`、
环境变量密钥，也不导入任何 llm provider 模块。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

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

ROOT = Path(__file__).resolve().parent.parent.parent.parent
RUNS_DIR = ROOT / "runs"
RESULTS_DIR = ROOT / "results"
MAX_SCAN_FILES = 400
PAGE_SIZE = 30
K_BUDGETS = [30, 60, 100, 150, 200]


def _load_streamlit() -> Any:
    try:
        from importlib import import_module
    except ImportError:  # pragma: no cover
        raise RuntimeError("需要先安装 streamlit 才能启动 UI。")
    try:
        module: Any = import_module("streamlit")
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("需要先安装 streamlit 才能启动 UI。") from exc
    return module


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
    steps = [
        trace.get("executed_action_count")
        for trace in traces
        if trace.get("outcome") == "success"
        and isinstance(trace.get("executed_action_count"), (int, float))
    ]
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
    st.write("自主性图例：纯 observation 自主 / observation-derived / "
             "world-declared phase guidance / planner_assisted（辅助上界，非自主）")
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


def main() -> None:
    st = _load_streamlit()
    st.title("Agent Arena 研究回放（只读）")
    st.caption("仅展示已有 trace/benchmark；不能运行新实验；不触碰密钥。")

    view = st.sidebar.radio("视图", ["单局回放", "矩阵总览", "错误热点", "条件对照"])
    if view == "单局回放":
        _replay_view(st)
    elif view == "矩阵总览":
        _matrix_view(st)
    elif view == "错误热点":
        _hotspot_view(st)
    else:
        _compare_view(st)


if __name__ == "__main__":
    main()
