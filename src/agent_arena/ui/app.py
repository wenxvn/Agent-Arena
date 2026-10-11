"""Agent Arena 研究可视化 MVP（只读 Streamlit 界面）。

运行（不改 pyproject/uv.lock，用 --with 临时提供 streamlit）：

    uv run --with streamlit streamlit run src/agent_arena/ui/app.py

能力：①单局 trace 步骤回放；②两份 benchmark CSV 对照；
③失败分布（failure_analysis.json，可选）。
只读 runs/ 与 results/ 下的用户自选文件；绝不读取 `.env`、
环境变量密钥，也不导入任何 llm provider 模块。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agent_arena.ui.present import autonomy_level, compare_conditions, summarize_trace


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


def _read_trace(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    st = _load_streamlit()
    st.title("Agent Arena 研究回放（只读）")
    st.caption("仅展示已有 trace/benchmark；不能运行新实验；不触碰密钥。")

    view = st.sidebar.radio("视图", ["单局回放", "条件对照"])
    if view == "单局回放":
        trace_path = st.sidebar.text_input("trace JSON 路径", "runs/")
        if trace_path.endswith(".json"):
            trace = _read_trace(Path(trace_path))
            header = {key: trace.get(key) for key in ("episode_id", "agent", "seed", "outcome")}
            st.write(header)
            st.write(autonomy_level(trace.get("provenance", {})))
            st.table(summarize_trace(trace))
        else:
            st.info("请输入一份已有 episode trace 的 .json 路径。")
    else:
        path_a = st.sidebar.text_input("对照 A benchmark CSV", "results/")
        path_b = st.sidebar.text_input("对照 B benchmark CSV", "results/")
        st.write("自主性图例：纯 observation 自主 / observation-derived / "
                 "world-declared phase guidance / planner_assisted（辅助上界，非自主）")
        for label, path in (("A", path_a), ("B", path_b)):
            if path.endswith(".csv"):
                rows = _read_csv_rows(Path(path))
                st.subheader(f"条件 {label}")
                st.write(compare_conditions(rows))
            else:
                st.info(f"请输入对照 {label} 的 benchmark .csv 路径。")


if __name__ == "__main__":
    main()
