"""V14 Agent 机制证据生成（零外部请求）。

用法：
    uv run python scripts/audit_v14_agents.py           # 打印摘要
    uv run python scripts/audit_v14_agents.py --write   # 写 docs/v14/agent-studies.md + .json

本脚本只驱动离线策略与只读历史数据：

- Memory：`memory.v2` 确定性 probe（被拒移动不写路线、回到起点可引用完整方位、不写答案）；
- 单因子臂与 `PLANNED_ONLY` 预检登记。

不联网、不写账本、不产生任何模型请求。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_arena.lab.v14.agent_studies import (  # noqa: E402
    memory_markdown,
    memory_study_report,
)

HEADER = """# V14 Agent 机制与 LIVE 状态

- 版本：`v14-agent-studies-1`（2026-10-27）
- 数据来源：`SIMULATED`（离线确定性 probe）+ `HISTORICAL`（V12 只读 CSV）
- V14 新增真实付费请求：**0**
- 三种证据严格分列：`SIMULATED` / `HISTORICAL` / `LIVE`

> 本文件不构成执行授权。所有真实模型效果一律 `LIVE_PENDING`：
> 未获用户对"模型 / 矩阵 / 总费用上限"的明确批准前，不得提交任何 LIVE 请求。
"""

FOOTER = """
## 4. 汇总状态

| 机制 | 离线机制证据 | 单因子臂 | 预检登记 | 真实收益 |
|---|---|---|---|---|
| Memory（`memory.v2`） | `SUPPORTED`（确定性 probe） | E1-a `route_log` / E1-b `route_mode` | `PLANNED_ONLY` | `LIVE_PENDING` |

## 5. 不支持的主张

- ❌ "Memory 提高成功率 X%"：离线 probe 不含模型，不能给出成功率；
- ❌ "route_log 一定更好"：机制成立 ≠ 收益成立，需要真实配对实验；
- ❌ "`env_write` 比 `context_only` 好"：前者多吃决策预算，长局可能因此截尾；
- ❌ "V10 `route_recall` 为 0 说明没记忆"：`context_only` 不写环境，该口径本就 `NOT_APPLICABLE`。
"""

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "v14")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    memory = memory_study_report()
    document = "\n".join([HEADER, memory_markdown(memory), FOOTER])

    if args.write:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "agent-studies.md").write_text(
            document, encoding="utf-8", newline="\n"
        )
        (args.out / "agent-studies.json").write_text(
            json.dumps(memory, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    summary = {
        "memory": {
            name: {
                "decisions": probe["decisions"],
                "requests": probe["requests"],
                "route_length": probe["route_length"],
                "rejected_moves": probe["rejected_moves"],
                "write_accepted": probe["write_accepted"],
                "bottleneck": probe["bottleneck"],
                "route_recall": probe["route_recall_v14"]["value"],
                "route_recall_state": probe["route_recall_v14"]["state"],
                "leaks": probe["memory_block_leaks"],
            }
            for name, probe in memory["probes"].items()
        },
        "all_single_factor": memory["arms"]["all_single_factor"],
        "plan_runs": memory["plan"]["runs"],
        "plan_status": memory["plan"]["status"],
        "written": str(args.out) if args.write else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
