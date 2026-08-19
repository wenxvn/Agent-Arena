# 自主逃生失败分析与复现实验设计

更新时间：2026-08-19

## 1. 目的与边界

本实验研究模型在确定性、部分可观测的 Spaceship Escape 世界中无法自主逃生的原因，并比较短期轨迹上下文与结构化里程碑记忆的作用。

本记录不把 `planner_assisted` 的成功描述为模型自主规划能力。规划辅助只作为可靠性上界和环境可解性对照。

所有 Agent 只能接收公开 `Observation`、公开 `ToolResult` 和由这些信息确定性生成的辅助数据，不得接收 `WorldState`、隐藏进度、完整 provider 响应或完整思维链。

## 2. 当前证据

基线为 Ollama `qwen2.5:7b`、`spaceship-escape-v2-zh`、30 步、seed 0 至 4、通用 `react_v12_autonomous` prompt：

| 条件 | 结果 | 说明 |
|---|---:|---|
| ReactAgent 纯自主 | 0/5 | 主要出现终端循环、重复 `look` 或无进展移动 |
| MemoryAgent 纯自主 | 0/5 | 有结构化记忆，但仍在控制室与走廊间循环 |
| `reasoning_effort=high` | 未改变循环 | 只增加执行步数，没有改变任务分解 |
| `guarded` | 未完成 | 能进入储藏室，但因 `missing_argument` 终止 |
| `planner_assisted` | 3/3 成功 | 固定 19 步完成，证明环境和 provider 链路可用 |

环境中曾存在错误终端动作导致终端永久消失的问题，已在 `c2eeca1` 修复。修复后仍然循环，因此该 bug 不再是当前主要原因。

## 3. 根因假设

按当前证据排序：

1. **长程任务分解不足**：目标包含收集工具、维修反应堆、恢复电源、读取授权码和启动逃生舱等因果依赖，单步模型没有稳定维护当前阶段。
2. **轨迹上下文不足**：`Observation` 只包含当前状态和最近一次结果；ReactAgent 没有最近动作历史和成功动作记录。
3. **部分可观测造成信用分配困难**：关键前置条件分布在多个房间，初始状态没有直接说明正确路线。
4. **失败反馈没有转化为可执行约束**：`no_power`、`not_visible` 等结果被作为文本暴露，但没有形成稳定的禁止动作或里程碑。
5. **MemoryAgent 的记忆不够可执行**：现有 `facts`、`failed_actions` 和 `open_questions` 能保存事实，却没有明确的阶段状态和已完成里程碑。
6. **结构化输出兼容性不足**：Hiyo relay 不接受当前 JSON Schema 模式；`json_object` 下仍可能产生缺少参数的 Action。该问题会造成提前终止，但不能解释 Ollama 纯自主基线的主要失败。
7. **模型规模或 reasoning 不是首要解释**：提高 reasoning 强度没有改变循环模式，14B 的历史运行也未稳定成功。

## 4. 实验变量

每次实验只增加一个变量，并记录在 Episode Trace 的 provenance 中。

### A0：纯自主基线

- ReactAgent 或 MemoryAgent
- 通用 `react_v12_autonomous` prompt
- 不启用最近历史
- 不启用公开动作候选
- 不启用 Runner 循环提醒

### A1：有限公开历史

在每次模型请求中增加最近 5 个已完成转移，每步只包含：

- 执行动作前的公开 Observation
- 已校验 Action
- 公开 ToolResult

不加入隐藏状态，不生成路线建议，不自动选择动作。A1 仍属于 ReactAgent 的短期工作上下文实验。

### A2：结构化里程碑记忆

在现有 MemoryAgent 记忆中增加确定性字段：

- 已访问地点
- 当前背包
- 已揭示物品
- `panel_open`
- `power_restored`
- `authorization_code_read`
- 已拒绝 Action 标识
- 未解决公开问题

这些字段只能由公开 Observation 和 ToolResult 更新。A2 不加入谜题专用路线提示。

### A3：语义动作校验（后续）

在 Environment 执行前，根据当前 Observation 检查出口、可见目标和背包前置条件。失败时要求模型纠正，不由系统代选动作。该变量主要衡量非法动作和环境拒绝，不直接等同于规划能力。

### A4：卡死恢复（后续）

检测相同公开状态下的重复 Action、重复失败结果和连续无进展 `look`，然后发送公开恢复提醒。启用后必须和 A0 分开统计。

### A5：`planner_assisted` 对照

确定性程序根据公开事实生成阶段和下一步建议。该条件只用于可靠性上界，不计入模型自主成功率。

## 5. 固定实验协议

除实验变量外，以下配置必须保持一致：

- world：`spaceship-escape`
- world version：`spaceship-escape-v2-zh`
- model：同一 provider 和模型
- seed：0、1、2、3、4
- step limit：30
- temperature：0
- tool 集合：`look`、`move`、`inspect`、`pickup`、`use`、`read_terminal`
- prompt：A0、A1、A2 使用相同基础 prompt

每个条件至少运行 5 局。真实模型实验必须保存每局 JSON trace，不能只保存汇总表。

## 6. 指标

主要指标：

- `success_rate`
- 阶段完成率：收集工具、打开面板、恢复电源、读取授权码、成功逃生
- `executed_action_count`

诊断指标：

- `rejected_action_count`
- `invalid_output_count`
- `invalid_output_reason`
- 首次环境拒绝发生步数
- 重复 Action 比例
- 连续 `look` 次数
- 唯一公开状态数
- provider 延迟和 token 使用量

解释规则：

- A1 若降低循环但不提高成功率，说明上下文是必要条件，但任务分解仍不足。
- A2 若降低重复失败并提高阶段完成率，说明状态表示是主要瓶颈。
- A3 若只降低非法动作而不提高阶段完成率，说明输出约束不是主因。
- A5 成功不能替代 A0/A1/A2 的自主能力结论。

## 7. 预期实现边界

实验实现应新增版本化开关，而不是修改 A0 默认行为：

- `recent_history_enabled=false` 默认关闭
- `recent_history_window=5`
- A1/A2 的 provenance 独立记录
- provider 请求只接收脱敏、长度受限的公开数据
- 不写入原始请求、原始响应、密钥或完整 reasoning

## 8. 复现命令

先运行静态验证：

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

A0 基线：

```bash
uv run agent-arena benchmark \
  --provider ollama --agent react --episodes 5 \
  --autonomous --output-dir results/a0-react

uv run agent-arena benchmark \
  --provider ollama --agent memory --episodes 5 \
  --autonomous --output-dir results/a0-memory
```

A1/A2 使用新增的实验开关，命令格式和固定 seed 与 A0 相同；实际开关名称以实现后的 CLI help 和 trace provenance 为准。

## 10. 2026-08-19 实验结果

实现提交前的 A1/A2 复验使用 Ollama `qwen2.5:7b`、固定 seed 0 至 4、30 步预算、`--autonomous`。

| 条件 | 成功 | 平均步数 | 平均环境拒绝 | 非法输出 | 主要行为 |
|---|---:|---:|---:|---:|---|
| A1 React + 最近 5 步历史 | 0/5 | 30 | 9 | 0 | 能离开控制室并到达反应堆，但没有稳定拾取工具；随后在维修室和反应堆间循环 |
| A2 Memory + 结构化里程碑 | 0/5 | 30 | 5 | 0 | 在储藏室重复 `inspect(storage_crate)`，偶尔错误使用保险丝，未进入维修阶段 |

结果文件：

- A1：`results/a1-react-history5/benchmark_20260819T122121Z_react_5-seeds_5-episodes_fef36b3e.json`
- A2：`results/a2-memory-milestones/benchmark_20260819T123207Z_memory_5-seeds_5-episodes_7b1e6eef.json`

解释：A1 的短期历史改善了早期方向判断，但没有解决“发现物品”和“完成拾取”之间的状态保持；A2 增加里程碑字段后反而在储藏室出现更早、更稳定的重复检查。当前证据不支持仅增加上下文或增加字段即可完成自主逃生。

下一步应优先做 A3/A4 的**公开动作约束与卡死恢复**：把已知失败动作和当前公开前置条件转换成候选动作排除，而不是继续扩展自然语言记忆字段。A3/A4 仍需与 A0/A1/A2 独立统计，不能称为纯自主基线。

## 11. 2026-08-19 A3/A4 实验结果

| 条件 | 成功 | 平均步数 | 主要结果 |
|---|---:|---:|---|
| A3 React + 公开语义 guard（seed 0 探针） | 0/1 | 30 | `inspect/read_terminal(control_terminal)` 在公开参数上合法，因此 guard 没有拒绝；仍重复 `no_power` |
| A4 React + 卡死恢复（seed 0 至 4） | 0/5 | 30 | 全部离开控制室并进入储藏室，但之后重复 `inspect(storage_crate)` |

A3 只检查 `available_exits`、`visible_objects` 和 `inventory` 可直接证明的约束，不判断隐藏谜题前提。因此它能处理“不可见目标/不可达出口/不在背包的维修物品”，不能处理“动作参数合法但在当前阶段无进展”。

A4 能打破最初的控制室终端循环，说明公开循环提醒确实改变了探索轨迹；但它不能把“密封箱已检查”转化为“下一步必须拾取物品”，所以仍未提升成功率。

结果文件：

- A3 探针：`results/a3-semantic-guard-smoke/episode_20260819T124557Z_react_seed-0_86953f21.json`
- A4：`results/a4-react-stuck-recovery/benchmark_20260819T125452Z_react_5-seeds_5-episodes_c86a8aac.json`

结论：A3 主要降低公开非法动作风险，A4 能改善早期探索但不能完成阶段转换。下一步应研究“公开阶段状态 + 候选动作集合”或真正的 PlanningAgent；不能把 A4 的路径改善写成自主通关能力。

## 12. A5 公开具体候选动作

A5 只根据当前 `Observation` 枚举可构造的具体 Action，例如：

```text
look()
move(destination=corridor)
inspect(target=storage_crate)
pickup(item=screwdriver)
use(item=screwdriver,target=reactor_panel)
```

它不提供目标路线、任务阶段、谜题答案或隐藏前置条件。候选集合只说明参数如何填写，模型仍负责选择动作和解释 ToolResult。

A5 与 A3 的区别：A3 在执行前拒绝公开非法 Action；A5 在请求中公开当前可构造的具体候选，减少模型生成缺参或不可见目标的机会。两者应分别运行，也可以在后续组合实验中单独标记。

复现命令：

```bash
uv run agent-arena benchmark \
  --provider ollama --agent react --episodes 5 \
  --autonomous --candidate-actions \
  --output-dir results/a5-react-candidates
```

## 13. 2026-08-19 A5 实验结果

A5 已完成实现、Fake 回归和 Ollama seed 0/1 的真实探针。两局均为 `step_limit`、30 步、0 次非法输出；模型仍在控制室循环 `inspect/read_terminal(control_terminal)`，具体候选列表没有改变选择。

由于每局真实请求约 90 秒，继续运行剩余 seed 的收益有限；seed 0/1 已重复呈现相同失败模式，故本轮停止扩展 A5 的 5 局 benchmark。已保存 trace：

- `results/a5-react-candidates/episode_20260819T130608Z_react_seed-0_d5aa9a2f.json`
- `results/a5-react-candidates/episode_20260819T130746Z_react_seed-1_537082bc.json`

结论：具体 Action 候选主要解决参数填写问题，不能解决“公开参数合法但阶段无进展”的策略循环。A5 不足以替代阶段状态或 PlanningAgent。

## 14. A6 公开阶段状态

A6 使用已经公开的 Observation、Action 和 ToolResult，确定性压缩为当前阶段和未完成条件：

```text
当前公开阶段：收集修理工具。
已完成：无。
未完成：获得 screwdriver、replacement_fuse。
```

阶段只由公开背包和成功 ToolResult 更新。它不提供目标房间、路径、下一动作、物品位置或授权码值，因此低于 `planner_assisted` 的公开下一动作建议，但高于 A0 纯自主上下文。

复现命令：

```bash
uv run agent-arena benchmark \
  --provider ollama --agent react --episodes 5 \
  --autonomous --phase-context \
  --output-dir results/a6-react-phase-context
```

## 15. 2026-08-19 A6 实验结果

A6 seed 0 探针结果为 `step_limit`，30 步全部在控制室重复 `inspect/read_terminal(control_terminal)`，0 次非法输出，0 次阶段推进。阶段文字“收集修理工具”没有让模型离开控制室。

结论：公开阶段标签不能替代阶段到动作的桥接；继续增加类似自然语言上下文的收益很低。后续应暂停 A6 类提示变量，转向真正的规划策略或明确标记的公开辅助候选集合。

## 9. 成功标准

本轮不以“某一局成功”作为充分结论。最低交付是：

1. A1/A2 能独立运行并写入可区分的 trace。
2. A0、A1、A2 的测试、Ruff 和 mypy 全部通过。
3. 每个条件至少有 5 局固定 seed 的 JSON trace 和汇总结果。
4. 报告成功率、阶段完成率和循环/非法输出指标，不把辅助模式写成自主能力。

## 16. 2026-08-19 Hiyo 复验与重新根因分析

### Hiyo 纯自主复验

模型配置验证成功：OpenAI-compatible Hiyo relay，模型 `gpt-5.6-terra`。

| 条件 | 结果 | 诊断 |
|---|---:|---|
| React A0，seed 0 | `invalid_action_limit`，执行 3 步，非法输出 5 次 | 第 1 步正确生成 `read_terminal`，收到 `no_power` 后仍尝试终端；`json_object` 仍产生 `missing_argument` |
| Memory + 结构化里程碑 + 最近 5 步，seed 0 | `invalid_action_limit`，执行 2 步，非法输出 3 次 | 记忆内容未能改变“无电终端”策略，协议错误更早终止 |
| `planner_assisted`，seed 0 | 19 步成功，0 次非法输出 | 同一模型、环境和执行链路可通关；确定性阶段规划是关键差异 |

结果文件：

- `results/hiyo-a0-react/episode_20260819T133646Z_react_seed-0_b298d9e8.json`
- `results/hiyo-a2-memory/episode_20260819T134140Z_memory_seed-0_a4bfb964.json`
- `results/hiyo-planner-assisted/episode_20260819T134237Z_planner_assisted_seed-0_250e92d3.json`

### A7：公开候选选择

A7 新增 `candidate_select` Agent。确定性 Runner 只根据当前公开 Observation 和之前公开结果枚举完整 Action，并在相同公开状态下排除已经拒绝或无状态变化的动作；模型只返回 `candidate_id`，不直接生成 Action 参数。候选列表不含路线、阶段、世界地图或谜题答案，因此 A7 不能计为纯自主能力。

复现命令：

```bash
uv run agent-arena run --provider openai --agent candidate_select --seed 0 \
  --reasoning-effort high --output-dir results/hiyo-a7-candidate-select-v2
uv run agent-arena run --provider openai --agent candidate_select --seed 0 \
  --reasoning-effort high --phase-context --output-dir results/hiyo-a7-candidate-phase
```

结果：

| 条件 | 结果 | 最高阶段 | 主要失败 |
|---|---:|---|---|
| 候选选择，无阶段上下文 | 0/1，30 步 | 恢复主电源 | 在维修室/反应堆间探索，未完成授权码阶段 |
| 候选选择 + 公开阶段上下文 | 0/1，30 步 | 读取授权码并成功读取 | 将授权码用于控制终端而非逃生舱，之后继续尝试语义错误的 `use` |

结果文件：

- `results/hiyo-a7-candidate-select-v2/episode_20260819T143015Z_candidate_select_seed-0_d97ffb40.json`
- `results/hiyo-a7-candidate-phase/episode_20260819T143515Z_candidate_select_seed-0_498d1842.json`

### 结论更新

目前证据不支持“模型太弱”或“提示词不够长”是首要根因。失败来自三个相互独立的决策层：

1. **输出协议层**：Hiyo relay 的 `json_object` 仍会生成缺少参数的 Action；这会在策略尚未展开前终止 episode。
2. **状态转移层**：模型能理解单次 `no_power`、`diagnostic_read` 等事实，却不能稳定维护“当前阶段的目标对象和下一阶段入口”。
3. **动作语义层**：即使候选参数完整、阶段标签存在，`use(code, control_terminal)` 这类动作仍然公开合法但语义错误；通用公开候选无法自行推断目标绑定。

因此，自主逃生不是“再给模型一条提示”即可解决的问题。真正需要的是可执行的状态机/计划表示、对语义前置条件的显式验证，以及协议层的单独修正重试。`planner_assisted` 的 19 步成功证明这些机制有效，但不证明模型自主规划。

### 后续实验优先级

1. 单独 benchmark Hiyo 的结构化输出修正，避免把协议失败与策略失败混在一起。
2. 将公开阶段表示从布尔里程碑升级为“当前子目标 + 可接受目标类型”，并把它作为显式辅助变量单独统计。
3. 增加公开语义 Action guard：只拒绝能由已公开阶段和 ToolResult 证明错误的 `use` 目标，不代替模型选动作。
4. 使用 5 个固定 seed 重复 A7 组合变量；若仍不能稳定通关，应停止把它称为自主改进，转向独立 PlanningAgent 研究。
