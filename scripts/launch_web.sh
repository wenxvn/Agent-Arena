#!/usr/bin/env sh
# 启动 Agent Arena 本地网页（macOS / Linux）。只监听 127.0.0.1。
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo"
port="${1:-8501}"
exec uv run --with streamlit agent-arena web --port "$port"
