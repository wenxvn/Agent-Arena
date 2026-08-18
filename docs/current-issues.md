# 当前问题记录

更新时间：2026-08-18

## 结论摘要

项目的本地运行链路已经可以工作，但“本地模型能否稳定完成飞船逃生”目前还没有验收通过。

简单说：程序能正常启动、调用 Ollama、校验模型输出、执行动作、在终端显示每一步并保存 trace；问题出在模型的多步决策能力，模型经常忘记已经得到的信息，重复走相同路线，最后达到 30 步上限。

## 已确认的问题

### 1. 轻量模型会陷入重复动作循环

已测试的本地模型：

- `qwen3:4b`
- `qwen3:8b`
- `qwen2.5:7b`

典型表现：

- 控制终端返回 `no_power` 后，模型仍反复回到控制室。
- 已经检查过密封箱后，模型仍重复 `inspect(storage_crate)`。
- 已经拾取物品后，模型仍重复 `pickup`。
- 模型在 `corridor`、`storage_room` 和 `control_room` 之间来回移动。
- 一局执行满 30 步，但没有完成逃生。

这不是 Ollama 连接失败，也不是 Action JSON 格式错误，而是模型在关闭思考模式后的多步规划能力不足。

### 2. 关闭思考后速度更合适，但推理能力下降

当前 Ollama 适配器使用原生 `/api/chat`，发送 `think: false`，并限制输出为 Action JSON Schema。

优点：

- 不再长时间生成隐藏思考内容。
- 每一步响应时间更容易接受。
- 输出格式稳定，能够被 Pydantic 正确校验。

缺点：

- 模型更容易忘记前置条件。
- 模型不能稳定规划“拿工具、修复反应堆、恢复电源、读取授权码、发射逃生舱”的完整链路。

### 3. 更严格的提示词只能部分改善问题

提示词已经加入以下约束：

- 只能移动到 `available_exits` 中的房间。
- 只能操作当前 `visible_objects` 中的目标。
- `no_power` 后不要立即回控制室。
- 进入存储室后先检查密封箱。
- 发现物品后先拾取。
- 已经拥有的物品不能重复拾取。

这些规则可以改善前几步行为，但不能完全阻止模型在后续步骤中循环。因此提示词不是根本解决方案。

### 4. 14B 模型尚未完成部署

曾尝试下载 `qwen2.5:14b`，文件约 9 GB。下载过程长时间停滞，终端显示的进度也出现回跳，最终停止下载。

当前已确认可用的模型是：

- `qwen2.5:7b`
- `qwen3:8b`
- `qwen3:4b`
- `qwen3:4b-no-think`

14B 没有注册为可用模型，因此不能算作已验收模型。Ollama 的 blob 缓存中可能仍有未完成下载留下的空间占用，当前约 20 GB；没有直接删除，避免误删其他模型共享文件。

## 已通过的部分

- Ollama 本地服务连接正常。
- `uv run agent-arena verify-model --provider ollama` 通过。
- 默认本地模型为 `qwen2.5:7b`。
- 模型输出可以被 JSON Schema 和 Pydantic Action 校验。
- 终端能够显示每一步的简短理由、动作和环境结果。
- 每局 trace 会写入 `runs/`，benchmark 汇总写入 `results/`。
- 不保存完整思维链、API Key 或原始模型响应。
- `uv run ruff check .` 通过。
- `uv run mypy src` 通过。
- `uv run pytest`：40 个测试全部通过。

## 当前验收状态

| 验收项目 | 状态 | 说明 |
|---|---|---|
| 本地 Ollama 服务 | 通过 | 服务和模型均可访问 |
| 模型连接验证 | 通过 | `verify-model` 返回成功 |
| JSON 动作格式 | 通过 | 输出可被严格校验 |
| 思考关闭 | 通过 | 使用 `think: false` |
| 终端逐步输出 | 通过 | 每一步显示理由、动作和结果 |
| Trace 保存 | 通过 | 步骤写入 `runs/` |
| 自动完成逃生 | 未通过 | 轻量模型会循环，达到 30 步上限 |

## 建议的下一步

1. 在 Agent Loop 增加重复动作和循环检测，而不是只依赖提示词提醒模型。
2. 对连续无进展动作触发一次专门的纠偏请求，要求模型选择尚未探索的出口或可见目标。
3. 为 MemoryAgent 增加更明确的“当前目标”和“下一步必要前置条件”字段。
4. 如果仍希望完全依赖模型规划，再尝试完成一个更强的本地模型部署，并重新进行同 seed 对照验收。
5. 在自动逃生成功率稳定前，不应把 benchmark 结果描述为项目功能已完成。

## 复验命令

```bash
uv run agent-arena verify-model --provider ollama
uv run agent-arena run --provider ollama --agent react --seed 0 --output-dir runs
uv run agent-arena benchmark --provider ollama --agent react --episodes 1 --output-dir results
uv run ruff check .
uv run mypy src
uv run pytest
```

真实逃生验收的最低标准是：终端最后显示“成功逃生”，并且对应 trace 的 `outcome` 为成功，而不是“达到步数上限，未完成逃生”。
