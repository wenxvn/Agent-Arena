#!/usr/bin/env bash
# V14 第五轮（串行、零并发）：
# A) 留出 seed 检验：MAP-16 seed 3（未见过的 seed），mimo-v2.6-pro，planning on/off × 3 重复
# B) reflection 单因子：MAP-22 seed 2+0 @150 请求（可解实例 + 长失败前缀），trigger_only vs on
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

run_phase round5-holdout --groups E2-a --model mimo-v2.6-pro --seeds 3 --replicates 3 \
    --kind matrix || exit 1
run_phase round5-reflect-m22 --groups E3 --seeds 2 0 --replicates 3 \
    --request-cap 150 --decision-cap 150 --token-cap 400000 --per-run-cost 0.25 \
    --e3-control trigger_only --kind budget_extension || exit 1
echo "=== round 5 done ==="
