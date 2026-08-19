# 本地模型通关现状与复现记录

更新时间：2026-08-18

## 结论

`qwen2.5:7b` 已经可以在本地 Ollama 中稳定完成 Spaceship Escape。当前成功模式是 `planner_assisted`，不是纯模型自由规划：模型真实返回每一步 Action，确定性规划器根据公开信息提供阶段和下一动作建议。

因此，下面的结果可以称为“真实本地模型的规划辅助通关”，不能称为“纯模型自主规划通关”。

## 两次本机复验

用户使用同一命令运行两次：

```bash
OLLAMA_MODEL=qwen2.5:7b uv run agent-arena run \
  --provider ollama \
  --agent planner_assisted \
  --seed 0 \
  --output-dir runs
```

两次结果都为：

| 项目 | 结果 |
|---|---|
| Provider | 本地 Ollama |
| Model | `qwen2.5:7b` |
| Agent | `planner_assisted_v2` |
| Outcome | `success` |
| 已执行 Action | 19 |
| 非法模型输出 | 0 |
| 环境拒绝 | 0 |
| trace | `runs/episode_20260818T082202Z_planner_assisted_seed-0_ad890530.json`、`runs/episode_20260818T082330Z_planner_assisted_seed-0_236c523b.json` |

两份 trace 都记录了 `action_validated`，最终 Action 是模型返回的：

```json
{"tool":"use","item":"ALPHA-731","target":"escape_pod"}
```

## 到底是不是规则写死

不是程序直接执行写死路线。执行链路是：

```text
公开 Observation
-> PlannerAssistedAgent 生成公开建议
-> Ollama qwen2.5:7b 返回 JSON Action
-> Action schema 校验
-> Environment.step(Action)
-> 下一条 Observation
```

代码中的 `PlannerAssistedAgent` 没有调用 `Environment.step`，也没有在模型失败后自动移动、拾取或使用物品。模型每一步仍然要返回 Action，Runner 才会执行它。

但路线也不是完全自由的。规划器包含公开房间路线和四个阶段：

```text
收集修理工具
-> 恢复主电源
-> 读取授权码
-> 启动逃生舱
```

规划器把“建议下一动作”放进当前请求的公开反馈中，模型通常会遵循。因此准确的说法是：**真实本地模型执行，确定性公开规划辅助**。

需要进一步说明：如果模型每次都照抄规划器给出的唯一建议，那么“路线选择”事实上已经被规划器写死了。此时模型仍然真实调用了 Ollama、生成了 JSON、通过了 Action 校验，但它证明的是端到端辅助系统能通关，不是模型具有自主规划能力。要研究模型判断力，必须只提供阶段和约束，或提供多个合法候选，让模型自行选择，并单独统计它是否拒绝不合理建议。

## 遇到的问题

1. 纯 `ReactAgent` 和 `MemoryAgent` 会重复移动、重复读取诊断终端，30 或 40 步后 `step_limit`。
2. 旧 prompt 要求所有 `use.item` 都必须在 `inventory`，但授权码来自控制终端结果，不在背包中；这与最终逃生规则冲突。
3. ReactAgent 没有跨步保存授权码的能力，离开控制室后无法仅靠当前 Observation 得到授权码。
4. 早期规划器在储物室先建议重复 `inspect`，没有优先拾取已经出现的物品，因此也会循环。
5. 当前 `PublicLoopDetector` 的公开状态键还没有包含 `available_exits` 和 `last_action_result`，可能把合法的回程动作误报为循环。这不影响本次 19 步通关，但仍是待修复问题。

## 解决过程

1. 检查环境规则、Runner、Agent、Ollama provider 和已有 trace，确认连接、JSON 校验和环境规则都正常，失败来自决策循环。
2. 做单状态模型实验，确认模型在获得明确阶段信息时可以选择正确动作。
3. 修正 prompt 契约，区分维修物品和公开读取的授权码，删除基础 prompt 中的真实谜底。
4. 将储物室逻辑改为“先拾取 visible_objects 中尚未拥有的物品，只有物品未出现时才 inspect 容器”。
5. 新增独立 `planner_assisted` Agent。它只读取公开 Observation、ToolResult 和 Memory，维护阶段标志，并把公开建议放入最新请求。
6. 在 trace 中单独记录 `planner_assisted_v2`，不把辅助结果混入纯 ReactAgent/MemoryAgent benchmark。
7. 用 Fake provider、48 项自动测试和真实 Ollama 多局运行验证。

## 最终通关路线

真实 v11 路线为 19 步：

```text
1  move corridor
2  move storage_room
3  inspect storage_crate
4  pickup screwdriver
5  pickup replacement_fuse
6  move corridor
7  move maintenance_room
8  move reactor_room
9  use screwdriver -> reactor_panel
10 use replacement_fuse -> damaged_fuse
11 move maintenance_room
12 move corridor
13 move control_room
14 read_terminal control_terminal
15 move corridor
16 move maintenance_room
17 move reactor_room
18 move escape_pod
19 use 公开读取的授权码 -> escape_pod
```

## 可复现实验

单局：

```bash
OLLAMA_MODEL=qwen2.5:7b uv run agent-arena run \
  --provider ollama \
  --agent planner_assisted \
  --seed 0 \
  --output-dir runs
```

三局 benchmark：

```bash
OLLAMA_MODEL=qwen2.5:7b uv run agent-arena benchmark \
  --provider ollama \
  --agent planner_assisted \
  --episodes 3 \
  --output-dir results
```

已完成的三局真实 benchmark：seed 0/1/2 均成功，平均 19 步，0 次非法输出，0 次环境拒绝。结果文件位于 `/tmp/agent-arena-planner-v11-benchmark/`。

## 已完成的功能

- 确定性的六房间 Spaceship Escape 环境和公开工具。
- 严格 Action schema 和 Observation 边界，Agent 不读取 WorldState。
- ReactAgent、MemoryAgent、Ollama/Fake/Bailian provider。
- 有步数限制的 Episode Runner、终止状态和脱敏 JSON trace。
- benchmark 的 JSON/CSV 指标输出。
- `planner_assisted` 公开规划辅助模式和独立 trace 标记。
- 本地 `qwen2.5:7b` 规划辅助通关。

## 仍需完成的任务

- 修正 `PublicLoopDetector` 的状态键和误报测试，避免合法回程被当成重复动作。
- 单独实现并评估真正的公开规则保护模式 `guarded`，与规划辅助模式分开比较。
- **完成不依赖谜题攻略式提示的纯模型自主通关验收**：分别运行 ReactAgent 和 MemoryAgent，使用通用 prompt、相同 seed 和预算，公开成功与失败 trace。
- 继续测量纯 ReactAgent/MemoryAgent 的失败率，不把辅助结果当成纯模型能力。
- 完成 Release 3 的 Streamlit 实验界面。
- 后续再考虑独立的 PlanningAgent、ReflectionAgent、多世界和更多模型对照。

`qwen2.5:14b` 因当前 Mac M5 Air 的运行资源限制暂缓测试，不纳入本轮自主通关实验矩阵。

## 纯模型自主基线结果

2026-08-19 使用通用 `react_v12_autonomous` prompt 和关闭循环提醒的 `--autonomous` 模式，分别运行 ReactAgent 与 MemoryAgent，各 5 局，seed 0 至 4，模型为 Ollama `qwen2.5:7b`。

结果为：两种 Agent 都是 0/5 成功，平均 30 步，非法模型输出均为 0。ReactAgent 每局有 2 次环境拒绝，随后主要重复 `look`。MemoryAgent 每局有 15 次环境拒绝，主要在控制室和走廊之间反复读取不可见的控制终端。

因此，当前项目已经有一组真实、可重复的纯模型失败基线。`planner_assisted` 的 3/3 成功不能用于替代这项验收。

## 相关决策

- 规划辅助模式的边界和验收条件：`docs/specs/0005-planner-assisted-agent/index.md`
- 当前工程事件：`docs/engineering-log.md`
