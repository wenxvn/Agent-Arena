#!/usr/bin/env bash
# V14 补充实验第二批（串行，零并发）：
# 2a) E1-a 预算扩展的 treatment 臂（MAP-22 route_log=on，150 请求）
# 2b) E3 换图重测暴露（MAP-19，reflection on/off，90 请求；已通过离线触发诊断）
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

run_phase suppl2-e1-budget-on --groups E1-a --replicates 3 \
    --request-cap 150 --decision-cap 150 --token-cap 400000 --per-run-cost 0.25 \
    --kind budget_extension || exit 1
run_phase suppl2-e3-map19 --groups E3 --map-override E3=MAP-19 --replicates 3 \
    --kind budget_extension || exit 1
echo "=== all supplements done ==="
