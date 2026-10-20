#!/bin/bash
# macOS 双击启动（首次可能需要 chmod +x scripts/launch_web.command）
set -eu
repo="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo"
exec uv run --extra web agent-arena web
