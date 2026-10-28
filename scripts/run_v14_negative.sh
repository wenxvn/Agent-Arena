#!/usr/bin/env bash
# V14 负向对照（串行、零并发）：planning 在一个"天花板图"与一个"规划无关图"上是否无差异/无增益
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

run_phase neg-map26 --groups E2-a --map-override E2-a=MAP-26 --replicates 3 --kind matrix || exit 1
run_phase neg-map14 --groups E2-a --map-override E2-a=MAP-14 --replicates 3 --kind matrix || exit 1
echo "=== negative controls done ==="
