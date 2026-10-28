#!/usr/bin/env bash
# V14 第四轮（串行、零并发）：
# A) route_log 的 seed 3 复核（MAP-22，150 请求，每臂 5 次重复）
# B) reflection 单因子（MAP-16：trigger_only vs reflection_on，3 seed × 3 重复）
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

APPROVED_BY="user: 继续执行（授权 MiMo 系列模型）"

run_phase() {
  local phase=$1; shift
  echo "=== ${phase} ==="
  uv run python scripts/run_v14_live.py "$@" \
      --phase "${phase}" --i-have-budget-approval --approval-cap 3.00 \
      --approved-by "${APPROVED_BY}" --submit
  local status=$?
  local summary="runs/v14/live/${phase}-summary.json"
  if [ -f "${summary}" ]; then
    local stop
    stop=$(python -c "import json;print(json.load(open('${summary}'))['stop_reason'])")
    echo "  stop_reason=${stop:-none}"
    if [ -n "${stop}" ]; then
      echo "  停止规则触发，终止后续阶段。"
      return 1
    fi
  fi
  return ${status}
}

run_phase round4-seed3 --groups E1-a --seeds 3 --replicates 5 \
    --request-cap 150 --decision-cap 150 --token-cap 400000 --per-run-cost 0.25 \
    --kind budget_extension || exit 1
run_phase round4-reflect-m16 --groups E3 --map-override E3=MAP-16 \
    --e3-control trigger_only --replicates 3 --kind ablation || exit 1
echo "=== round 4 done ==="
