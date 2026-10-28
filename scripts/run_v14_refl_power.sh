#!/usr/bin/env bash
# V14 reflection 功效补充：契约限制 replicates ≤ 10，因此分 3 个独立父实验对，
# 每个 10 次重复（每臂 10 局）。仅 MAP-22 seed 2（唯一可解实例）@150 请求。
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

APPROVED_BY="user: 继续执行（授权 MiMo 系列模型）"
for n in 1 2 3; do
  phase="refl-power2-${n}"
  echo "=== ${phase} ==="
  uv run python scripts/run_v14_live.py --groups E3 --seeds 2 --replicates 10 \
      --request-cap 150 --decision-cap 150 --token-cap 400000 --per-run-cost 0.25 \
      --e3-control trigger_only --kind budget_extension --phase "${phase}" \
      --i-have-budget-approval --approval-cap 4.00 --approved-by "${APPROVED_BY}" --submit
  status=$?
  summary="runs/v14/live/${phase}-summary.json"
  if [ -f "${summary}" ]; then
    stop=$(python -c "import json;print(json.load(open('${summary}'))['stop_reason'])")
    echo "  stop_reason=${stop:-none}"
    if [ -n "${stop}" ]; then
      echo "  停止规则触发，终止后续阶段。"
      exit 1
    fi
  fi
  [ ${status} -ne 0 ] && exit ${status}
done
echo "=== reflection power done ==="
