# V12 演示数据包（SIMULATED）

> 演示脚本：动作由人工按公开规则编写，不是模型输出，也不是 Oracle；结果只用于展示对照、诊断与可视化链路。

这些文件由 `uv run python scripts/build_v12_demo.py` 生成，
用于在没有 API Key、没有网络的情况下演示 Lab 的完整链路：

| 目录 | 内容 |
|---|---|
| `01-offline-basic-memory-planning/` | 三架构离线模拟对照：汇总、配对判定、可读报告 |
| `02-pairwise-diff/` | 同图同 seed 的一对轨迹对照：首次差异、指标增量、可验证假设 |
| `03-failure-evidence/` | 失败证据样例：类别、严重度、证据步 |

## 这些不是真实模型结果

- `mode=simulated`，Provider 是确定性脚本；
- 动作由人工按公开规则编写，不是 Oracle，也不代表任何模型能力；
- 报告中所有“成功率/费用”数字只说明链路可用，不能外推。

## 复现

```bash
uv run python scripts/build_v12_demo.py
uv run python scripts/demo_v12.py --out runs/v12/demo
```
