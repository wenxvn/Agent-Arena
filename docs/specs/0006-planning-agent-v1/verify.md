# PlanningAgent v1 验证记录

## 自动验证

执行：

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

结果：96 项 pytest 通过，Ruff 通过，mypy 通过。

## Fake smoke test

执行：

```bash
uv run agent-arena run --provider fake --agent planning --seed 0 --output-dir <temporary-directory>
uv run agent-arena benchmark --provider fake --agent planning --episodes 5 --output-dir <temporary-directory>
```

结果：单局 20 个 Executor Action、4 个 Planner 计划和 4 个子目标完成；5 seeds 均成功，输出 Planning provenance、计划生命周期字段和 benchmark v3 JSON/CSV。该结果只验证工程闭环，不作为真实模型自主能力结论。

本次 `uv run agent-arena verify-model --provider ollama` 已通过。随后以
`qwen2.5:7b`、`spaceship-escape-v2-zh`、temperature 0、30 步上限、seed 0 至 4
和 `--autonomous` 运行真实 Planning benchmark。

结果：5 局均为 `step_limit`，成功率 0%；平均 30 步、重复动作比例 93.3%、平均连续
`look` 26 次、唯一公开状态 1 个、平均 28 次 Planner 调用、子目标完成率 0%，总 token
141,445。该结果确认 PlanningAgent 的真实研究验收仍未通过；主要失败行为是模型持续执行
合法但无进展的 `look`，而不是非法 Action 或 provider 连接错误。

Benchmark JSON：
`/tmp/agent-arena-planning-real-5/benchmark_20260910T004317Z_planning_5-seeds_5-episodes_16921bb2.json`

对应的 5 局 trace 已写入本地 `runs/`，文件名以
`episode_20260910T001900Z_planning_seed-0` 至
`episode_20260910T003823Z_planning_seed-4` 开头。

## 仍需真实环境验证

PlanningAgent 的真实 5 seeds 已完成，但尚未满足研究验收。下一步应在同一 world、model、temperature、step limit 和 seeds 下整理 React、Memory、Planning 与 `planner_assisted` 的可比结果，公开成功与失败 trace，并单独报告 Planner 成本和子目标完成率；在取得可重复纯模型成功前，不得把本次 0/5 结果解释为 Planning 已证实有效。
