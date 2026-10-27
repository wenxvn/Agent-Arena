#!/usr/bin/env bash
# V14 补充实验（三阶段串行，零并发）。
# 1) E2-a 补到每 seed 5 次重复（同 90 请求预算，可与原批配对）
# 2) E1-a 预算扩展 150 请求（MAP-22 route_log on/off）
# 3) E3 长程重测（MAP-22 reflection on/off，150 请求；只测暴露，不评效果）
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

APPROVED_BY="user: 授权 MiMo，按推荐补充实验"
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

run_phase suppl-e2 --groups E2-a --replicates 5 --kind supplement || exit 1
run_phase suppl-e1-budget --groups E1-a --replicates 3 \
    --request-cap 150 --decision-cap 150 --token-cap 400000 --per-run-cost 0.25 \
    --kind budget_extension || exit 1
run_phase suppl-e3-long --groups E3 --replicates 3 \
    --request-cap 150 --decision-cap 150 --token-cap 400000 --per-run-cost 0.25 \
    --kind budget_extension || exit 1
echo "=== all supplements done ==="
