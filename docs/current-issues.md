# 当前问题记录

更新时间：2026-09-05

## 结论摘要

项目的本地运行链路已经可以工作，但“本地模型能否稳定完成飞船逃生”目前还没有验收通过。

简单说：程序能正常启动、调用 Ollama、校验模型输出、执行动作、在终端显示每一步并保存 trace；问题出在模型的多步决策能力，模型经常忘记已经得到的信息，重复走相同路线，最后达到 30 步上限。

## 已确认的问题

### 1. 本地模型会陷入重复动作循环

已测试的本地模型：

- `qwen3:4b`
- `qwen3:8b`
- `qwen2.5:7b`
- `qwen2.5:14b`

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

### 4. 14B 暂缓测试

此前曾验证 `qwen2.5:14b` 可以连接，但固定 seed=0、MemoryAgent、30 步的真实运行仍在恢复主电源后重复读取诊断终端，最终达到步数上限。当前用户使用 Mac M5 Air，运行 14B 的资源开销过高，因此暂不继续测试，也不将 14B 纳入当前实验矩阵。后续只有在更合适的硬件条件下才恢复该对照。

当前已确认可用的模型是：

- `qwen2.5:7b`
- `qwen3:8b`
- `qwen3:4b`
- `qwen3:4b-no-think`

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
- `uv run pytest`：68 个测试全部通过（2026-09-05 的问题盘点）。
- `qwen2.5:14b` 的 `verify-model` 通过，但完整逃生局结果为 `step_limit`。

## 当前验收状态

| 验收项目 | 状态 | 说明 |
|---|---|---|
| 本地 Ollama 服务 | 通过 | 服务和模型均可访问 |
| 模型连接验证 | 通过 | `qwen2.5:7b` 与 `qwen2.5:14b` 均返回成功 |
| JSON 动作格式 | 通过 | 输出可被严格校验 |
| 思考关闭 | 通过 | 使用 `think: false` |
| 终端逐步输出 | 通过 | 每一步显示理由、动作和结果 |
| Trace 保存 | 通过 | 步骤写入 `runs/` |
| 自动完成逃生 | 未通过 | 7B 出现重复动作并达到步数上限；14B 暂缓，不作为当前结论 |

## Hiyo Responses provider 复验（2026-08-19）

新增 `openai` provider，使用 `OPENAI_BASE_URL=https://codex.hiyo.top/v1` 的原生 `/v1/responses` 接口和 `gpt-5.6-terra`。模型连接验证通过，`planner_assisted` 在 seed 0/1/2 共 3 局全部于 19 步成功逃生，0 次非法输出。

相同 provider、模型、seed 和 30 步预算下，ReactAgent 与 MemoryAgent 使用通用 `--autonomous` prompt 均在第 2 步后的格式修正阶段达到 `invalid_action_limit`，没有自主逃生成功。因此当前结论是“远程模型可执行公开规划建议”，不是“远程模型已具备纯自主逃生能力”。

## 受控变量复验（2026-08-19）

- 修复环境拒绝副作用：错误使用终端工具或断电读取终端后，终端继续出现在公开 Observation 中，不再永久隐藏。修复后纯自主 React 能执行满 30 步，但仍在 `inspect(control_terminal)` 与 `read_terminal(control_terminal)` 间循环，结果为 `step_limit`。
- `reasoning_effort=high`：同一 seed 下执行 10 步、8 次非法输出后终止，仍是终端循环；没有证据表明增加推理预算能解决任务分解问题。
- `guarded` 公开动作候选：第一次请求遇到 relay 400，重试后能离开控制室、进入储藏室并检查密封箱，但在拾取阶段因缺少 Action 必填参数达到 `invalid_action_limit`，尚未通关。
- 非法输出分类显示本轮主要为 `missing_argument`。Responses relay 拒绝 `json_schema`（HTTP 400），因此默认继续使用 `json_object`，并将安全的缺参类别反馈给格式修正请求。

当前证据更支持“错误恢复与任务分解不足，叠加结构化输出约束不够”这一解释，而不是单一的模型过弱或思考太长。关卡可由人工和 `planner_assisted` 稳定通关，但断电终端反馈曾存在不可恢复的可见性副作用，已修复。

## 2026-08-19 纯模型自主基线结果

使用 `qwen2.5:7b`、`spaceship-escape-v2-zh`、seed 0 至 4、每局 30 步、关闭思考、通用 `react_v12_autonomous` prompt，并关闭 Runner 循环提醒，分别运行 ReactAgent 和 MemoryAgent。

| Agent | 局数 | 成功 | 成功率 | 平均步数 | 平均环境拒绝 | 非法输出 |
|---|---:|---:|---:|---:|---:|---:|
| ReactAgent | 5 | 0 | 0% | 30 | 2 | 0 |
| MemoryAgent | 5 | 0 | 0% | 30 | 15 | 0 |

ReactAgent 的典型行为是第 1 步误用 `inspect(control_terminal)`，第 2 步尝试不可见目标，之后连续 28 次 `look`，直到达到步数上限。MemoryAgent 能走出控制室并返回走廊，但随后在控制室和走廊之间循环，反复对不可见的 `control_terminal` 调用 `read_terminal`。

这组结果证明：移除谜题攻略式提示后，当前 `qwen2.5:7b` 还不能依靠公开 Observation 和结构化 Memory 自主完成任务。它不是连接、格式校验或非法 JSON 问题，所有 10 局的模型输出都通过格式校验。

## 建议的下一步

1. 在当前已完成的纯模型失败基线上，设计不含谜题答案的通用运行时上下文或受控短期历史实验，并与基线使用相同模型、seed 和步数预算。
2. 在保持通用 prompt 的前提下，分析最近历史、结构化记忆、重复动作检测各自对结果的影响。
3. 对连续无进展动作触发运行时纠偏时，必须单独标记该实验变量，不能把它当成纯模型结果。
4. `planner_assisted` 只作为辅助通关和演示模式，不能替代自主通关验收。
5. 在自动逃生成功率稳定前，不应把 benchmark 结果描述为模型自主规划已完成。

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

## 2026-09-05 问题盘点补充

以下条目区分已确认的缺口、尚未验证的行为和外部运行阻塞；未测试项不应被描述为现有缺陷。

### P0：研究验收未完成

1. 纯 ReactAgent 与 MemoryAgent 在 Ollama `qwen2.5:7b` 的固定五个 seed 对照中均为 0/5 成功，尚无可重复的纯模型成功样本。
2. `planner_assisted` 的稳定成功只代表带公开规划建议的可靠性上界，不能与纯模型 trace、指标或结论混合。
3. 尚未公开一组同时包含成功与失败的纯模型 trace；在取得可重复成功前，不能宣称自主规划验收通过。

### P1：实现与实验契约缺口

1. `RuntimeSettings.world` 和 `RuntimeSettings.world_version` 当前不驱动环境加载：即使传入不同值，`SpaceshipEscapeEnvironment` 仍加载 `spaceship_escape_v1 / v2-zh`。在实现真实 world selector 前，CLI/UI 不得暗示该配置已生效。
2. `PublicLoopDetector` 的状态键缺少部分公开进展信息。已知授权码读取后的合法回程可能误报为循环；需要补充回归测试并决定使用 `available_exits`、最近公开结果或阶段 epoch 的最小修复。
3. benchmark 尚未汇总阶段完成率、重复 Action 比例、连续 `look`、唯一公开状态数和 guidance 偏离率，无法完整执行既定实验解释规则。
4. 每步 planner feedback 仍缺少受长度限制的 trace 摘要或 hash，导致无法在不保存完整 reasoning 的前提下复盘建议与实际动作的偏离。

### P1：尚未完成验证

1. `guarded` 模式是否只提供公开规则反馈、而不替模型选取或执行 Action。
2. 规划建议被拒绝、偏离或产生非法 Action 时，Runner 的继续、纠正和终止行为。
3. planner 的完整阶段转换，以及 `reset`、`finish`、跨 episode 的 Memory、阶段和循环检测状态清理。
4. 所有 planner 路线表项都与当前公开 Observation 一致，且公开反馈不泄漏 WorldState 或密钥。

### P2：范围与外部条件

1. Streamlit、PlanningAgent、ReflectionAgent、第二 world version 和第二种模型的对照仍未交付；应在上述自主基线和变量边界稳定后推进。
2. `qwen2.5:14b` 受本机资源限制暂缓，不纳入当前实验矩阵。
3. 本次 Hiyo Responses 链路曾返回 `401 INVALID_API_KEY`；这是本地凭据或服务端配置的外部阻塞，不记录或输出密钥。更新有效本地配置后才可继续该 provider 的复验。
