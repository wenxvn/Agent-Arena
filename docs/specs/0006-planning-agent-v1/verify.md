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

本次 `uv run agent-arena verify-model --provider ollama` 未通过，未启动真实 Planning benchmark。

## 仍需真实环境验证

使用 Ollama 或 OpenAI-compatible provider 时，应在同一 world、model、temperature、step limit 和 seeds 下比较 React、Memory、Planning 与 `planner_assisted`。真实运行结果必须保存每局 trace，并单独报告 Planner 成本和子目标完成率。
