# Agent Arena 本地模型问题诊断与 V0.1 推进建议

> 建议文件位置：`docs/local-model-strategy.md`  
> 项目：Agent Arena  
> 更新日期：2026-08-18

### 最新实测（2026-08-18）

已完成 `qwen2.5:14b` 安装和连接验证。固定 `seed=0`、`MemoryAgent`、30 步的真实运行中，14B 在第 14 步恢复主电源后，仍连续重复读取诊断终端，最终为 `step_limit`；没有产生成功逃生 trace。结论是：14B 可用，但当前 Agent Loop 仍不能保证长程任务通关。

本轮实现的轻量化措施包括：`react_v9` 紧凑提示词、`MemoryAgent`、公开循环检测和运行时提醒、完成目标后隐藏部分观察对象，以及终端必须使用 `read_terminal`。这些措施改善了早期探索和信息边界，但没有消除模型循环。

## 1. 当前结论

Agent Arena 当前的主要问题已经不是基础设施是否可用，而是：

> **轻量本地模型在部分可观测、长程、多步骤任务中容易遗忘前置条件、重复失败动作并陷入循环。**

目前已经确认以下链路可以正常工作：

- Ollama 本地服务可以访问。
- Agent 可以调用本地模型。
- 模型输出可以通过 JSON Schema / Pydantic Action 校验。
- Episode 可以逐步执行。
- Trace 可以保存。
- Benchmark 结果可以写入结果目录。
- `ruff`、`mypy` 和测试均已通过。

当前没有通过的核心验收项是：

> **本地模型尚不能稳定完成 Spaceship Escape。**

已经测试的轻量模型包括：

- `qwen3:4b`
- `qwen3:8b`
- `qwen2.5:7b`
- `qwen2.5:14b`

典型失败行为包括：

- `no_power` 后仍反复返回 Control Room。
- 重复检查已经检查过的对象。
- 重复拾取已经拥有的物品。
- 在若干房间之间来回移动。
- Episode 达到 30 步上限仍未完成逃生。

因此，接下来不应继续把主要时间花在 Ollama 连接、Action JSON 或基础执行链路上。

---

## 2. 不建议继续做的事情

### 2.1 不要继续堆 Spaceship-specific Prompt Rules

当前 prompt 已经包含大量针对具体谜题的规则，例如：

- 进入 Storage Room 后优先检查 `storage_crate`。
- 拿到 screwdriver 和 replacement fuse 后立即离开。
- `no_power` 后暂时不要回 Control Room。
- 诊断终端提示手动修复后前往 Reactor Room。

这些规则短期可以提高成功率，但继续增加会逐渐把 Agent 变成：

> **按照人工攻略执行动作的模型。**

而不是：

> **根据 observation、history 和 environment feedback 自主解决任务的 Agent。**

这会削弱 Agent Arena 作为 benchmark 的价值。

从现在开始，ReactAgent 的 prompt 最好只保留通用规则：

- 只能操作当前可见对象。
- 只能移动到当前可达出口。
- 不得编造世界状态。
- 失败条件未发生变化时，不重复同一失败动作。
- 优先获取新信息或推进已知前置条件。
- 每一步只选择一个合法 Action。

不要再加入：

- 某个具体房间必须做什么。
- 某个谜题物品应该去哪里找。
- 某个任务阶段的正确路线。

---

## 3. 第一优先级：给 ReactAgent 合理的短期工作记忆

当前 ReactAgent 如果只拿到：

```text
Goal
Current Observation
Last Tool Result
```

对于一个十几到几十步的任务来说过于苛刻。

Spaceship Escape 天然需要跨步骤保留：

```text
control terminal currently has no power
storage crate has already been inspected
screwdriver has already been collected
replacement fuse has already been collected
diagnostic terminal says the reactor requires manual repair
```

如果这些信息没有出现在当前 observation 中，而 Agent 又没有 recent history，那么模型后续重复行为不一定完全说明它“不会规划”。

它也可能只是：

> **没有足够上下文恢复刚刚发生过的事实。**

### 建议改成

```text
System Prompt

Goal

Current Observation

Recent History
- Last 5 steps

Available Tools
```

Recent History 每一步只包含公开信息：

```text
Step N
Observation:
...

Action:
...

Result:
...
```

建议先使用：

```python
recent_history_size = 5
```

不要一开始使用完整历史。

### 为什么这仍然可以算 React baseline

Recent history 是短期工作上下文，不等于 Structured Memory。

ReactAgent：

```text
current observation
+
last N raw interactions
```

MemoryAgent：

```text
current observation
+
last N raw interactions
+
compressed persistent structured memory
```

这样后续 React vs Memory 的变量仍然清楚。

---

## 4. 第二优先级：Loop Detection 属于 Runtime，不应该完全交给 Prompt

Agent Runtime 应该检测明显的无效行为模式。

这不是替 Agent 做决定，而是在系统层识别：

> 当前 trajectory 已经表现出循环迹象。

建议实现三个最简单的 detector。

### 4.1 Repeated Failed Action

例如：

```text
read_terminal(control_terminal)
→ no_power

...

read_terminal(control_terminal)
→ no_power
```

如果前置条件没有变化，又重复同一个失败动作：

```python
repeated_failed_action_count += 1
```

---

### 4.2 Exact / Near Repeat

检测最近若干动作：

```text
A
A
```

以及简单的：

```text
A
B
A
B
```

例如：

```text
move(control_room)
move(corridor)
move(control_room)
move(corridor)
```

MVP 不需要复杂的 sequence mining。

只识别：

```python
[A, A]
```

和：

```python
[A, B, A, B]
```

已经足够。

---

### 4.3 No-Progress Detection

不要用“位置变化”作为 progress。

Agent 在房间之间移动并不意味着任务在推进。

建议以 milestone 为准：

```python
MILESTONES = [
    "found_required_items",
    "opened_reactor_panel",
    "repaired_reactor",
    "restored_power",
    "obtained_authorization",
    "unlocked_escape_pod",
    "escaped",
]
```

如果：

```text
连续 5 步 milestone 没有变化
```

则：

```text
no_progress = True
```

---

## 5. Loop 被检测后不要直接替 Agent 选动作

Runtime 不应该：

```python
if loop_detected:
    action = move("maintenance_room")
```

这样会破坏：

> LLM decides. Environment determines reality.

更合理的是给 Agent 一个公开的纠偏信号。

例如：

```text
Progress warning:

You have made no milestone progress in the last 5 actions.

Recent repeated behavior:
- read_terminal(control_terminal) -> no_power
- move(control_room)
- move(corridor)
- move(control_room)

Reconsider your current approach.

Choose an action that:
- gathers new information,
- explores an unresolved path, or
- advances a known prerequisite.

Do not repeat an action whose failure condition has not changed.
```

然后仍然由模型输出 Action。

这个机制以后可以自然演化成 ReflectionAgent。

---

## 6. 不要把 Loop Detection 和 Reflection 混在一起

V0.1 可以只有：

```text
Runtime Loop Detector
```

它只是检测：

```text
repetition
no progress
same failed action
```

不调用第二次 LLM。

以后 V0.3 再做真正的 Reflection：

```text
Loop Detector
        ↓
Reflection Trigger
        ↓
LLM reviews recent trajectory
        ↓
short reflection
        ↓
future context
```

这样 feature 的演化路径清楚：

```text
V0.1
Detection only

V0.2 / V0.3
Detection + Reflection
```

---

## 7. MemoryAgent V1 应该比 ReactAgent 多什么

建议第一版 Structured Memory 保持简单、确定性、可解释。

```python
class StructuredMemory:
    visited_rooms: set[str]
    known_facts: list[str]
    failed_actions: list[str]
    inventory: list[str]
```

暂时不要加入复杂字段，例如：

```text
belief graph
long-term embeddings
vector retrieval
LLM-generated hypotheses
automatic planning tree
```

MemoryAgent 的目的不是“一次把 Agent 变聪明”。

V0.1 研究问题应该保持简单：

> **Structured memory 是否能减少遗忘和重复失败行为？**

---

## 8. Memory 不应该获得 Hidden State

Memory 只能来自 Agent 已经观察到的内容。

错误：

```python
memory.known_facts.append(
    env.hidden_state["correct_solution"]
)
```

正确：

```text
Observation / ActionResult
        ↓
public fact
        ↓
Structured Memory
```

如果 Environment 有结构化事件，可以让 ActionResult 附带公开 metadata：

```python
ActionResult(
    success=False,
    message="The control terminal has no power.",
    public_facts=[
        "control_terminal_no_power"
    ]
)
```

MemoryAgent 再保存：

```text
- The control terminal currently has no power.
```

这里的关键是：

> Environment 可以帮助结构化“Agent 已经获得的信息”，但不能泄露尚未观察到的世界事实。

---

## 9. 建议的本地模型测试顺序

不要继续横向测试大量 4B / 7B / 8B 模型。

当前更有价值的是测试：

> **更大的模型能否显著改善 trajectory quality。**

推荐按以下顺序：

### A. 现有 Qwen3 8B

先不要换模型。

先测试新的 Agent architecture：

```text
qwen3:8b
+
recent history = 5
+
runtime loop detection
```

跑：

```text
5 episodes
```

目的是判断：

> 当前失败究竟有多少是 context / runtime architecture 导致的。

---

### B. 同家族更大模型（已实测 Qwen2.5 14B）

如果机器资源允许，这是最优先尝试的下一档。当前 `qwen2.5:14b` 已完成安装和连接验证，但单局 30 步仍失败。

原因不是要寻找“最好模型”，而是：

```text
同一个模型家族
8B → 14B
```

变量更容易解释。

保持：

```text
same world
same prompt
same history
same runtime
same temperature
same max steps
```

只改变模型规模。若机器在运行 14B 时明显卡顿，不建议把它设为默认开发模型；默认仍使用 `qwen2.5:7b`，14B 只用于对照实验。

---

### C. Gemma 3 12B

作为不同模型家族的交叉检查。

它的作用是回答：

> looping 是 Qwen 家族特有行为，还是当前规模本地模型普遍存在的问题？

---

### D. 更大的 20B+ 模型

只有机器资源允许时再测试。

不要为了本地推理把项目主要时间变成：

```text
模型下载
量化格式
显存调优
Ollama 缓存清理
推理速度调参
```

Agent Arena 的核心研究对象是 Agent architecture，而不是 Local LLM Ops。

---

## 10. Thinking Mode 应该做一次对照实验

当前使用：

```text
think: false
```

带来的优点：

- 输出速度更合理。
- Action JSON 更稳定。
- 不会长时间生成额外推理内容。

但现有现象也表明：

- 多步依赖跟踪可能下降。
- 模型更容易重新尝试已知失败路线。

因此建议做一个小型对照实验：

```text
qwen3:8b
think=false
5 episodes
```

对：

```text
qwen3:8b
think=true
3–5 episodes
```

只看：

```text
success
max progress
steps
repeated failed actions
loop count
```

这里暂时不把 latency 当第一判断标准。

如果：

```text
think=false
success ≈ 0

think=true
success clearly improves
```

可以说明：

> 当前任务对 inference-time reasoning 有实际需求。

这会帮助决定：

```text
继续忍受较慢本地推理
```

还是：

```text
切更强 API model
```

---

## 11. 建议增加的 Benchmark Metrics

V0.1 继续保留：

```text
Success Rate
Average Steps
Tool Calls
Invalid Actions
Repeated Actions
Token Usage
```

同时强烈建议新增：

```text
Maximum Progress
No-Progress Steps
Repeated Failed Actions
Loop Events
```

原因是：

如果所有轻量模型都是：

```text
0% success
```

Success Rate 无法区分它们。

但是：

```text
Model A:
max progress = 80%

Model B:
max progress = 30%
```

依然非常有信息。

---

## 12. 推荐的 Progress 定义

使用 milestone，而不是 world-state hash。

例如：

```python
MILESTONES = [
    "obtained_required_tool",
    "opened_reactor_panel",
    "repaired_reactor",
    "restored_power",
    "obtained_authorization",
    "unlocked_escape_pod",
    "escaped",
]
```

计算：

```python
progress = completed_milestones / total_milestones
```

这样即使 Episode 失败，也能分析：

```text
Agent 卡在哪里？
```

以后 failure taxonomy 也可以直接基于 milestone。

---

## 13. 推荐的实验矩阵

不要一上来跑大量 Episode。

### Phase 1 — Architecture sanity check

```text
Model: qwen3:8b

A:
React current
5 episodes

B:
React + recent history 5
5 episodes

C:
React + recent history 5 + loop detection
5 episodes
```

主要观察：

```text
Repeated Failed Actions
Loop Events
Maximum Progress
```

---

### Phase 2 — Local model scale

固定最佳 architecture：

```text
qwen2.5:7b
qwen2.5:14b
gemma3:12b
```

每个：

```text
5 episodes
```

如果差异明显，再扩大：

```text
10 episodes
```

---

### Phase 3 — React vs Memory

选择一个：

```text
能够正常执行任务
但仍存在明显 failure 的模型
```

然后：

```text
ReactAgent
20–30 episodes

MemoryAgent
20–30 episodes
```

这是 V0.1 真正应该写进 README 的实验。

---

## 14. 什么时候停止折腾本地模型

建议给项目设一个明确 stopping rule。

完成下面三个条件：

### Test A

```text
Qwen3 8B
+
recent history
+
loop detection
```

### Test B

```text
Qwen2.5 14B
same architecture
```

### Test C

```text
另一个 12B–14B 左右模型
same architecture
```

如果这些模型依然普遍表现为：

```text
严重遗忘
重复失败动作
明显规划漂移
长期困在低 progress
```

则：

> **停止继续调本地模型，接入 API。**

这不是项目失败。

这是非常合理的工程边界。当前 14B 已经给出这一判断的证据：连接正常、动作合法，但在任务中段发生公开可见的重复循环。

不要继续花几天时间寻找：

```text
另一个量化版本
另一个 Modelfile
另一个 temperature
另一组几十条 prompt rule
```

如果核心问题已经明显是模型 capability ceiling，继续微调基础设施的机会成本会越来越高。

---

## 15. 如果切 API，仍然保留 Ollama

推荐 LLM 层保持：

```text
LLMClient
│
├── OllamaProvider
└── APIProvider
```

用途：

### 本地模型

```text
快速开发
schema 验证
environment smoke test
runner 调试
trace 检查
低成本 iteration
```

### API 模型

```text
正式 benchmark
高质量 trajectory
能力上限对照
最终 README 实验
```

这会让 Agent Arena 的实验结构更完整。

模型本来就应该是一个可替换变量。

---

## 16. API 不应该成为 Agent architecture 的一部分

Agent 代码不应该：

```python
from openai import ...
```

或者：

```python
ollama.chat(...)
```

Agent 只依赖：

```python
class LLMClient:
    def complete(...):
        ...
```

Provider 负责：

```text
transport
authentication
model request
structured output
usage
latency
```

Agent 负责：

```text
context building
memory
planning
decision
reflection
```

这样：

```text
ReactAgent + Ollama
ReactAgent + API
MemoryAgent + Ollama
MemoryAgent + API
```

都可以直接比较。

---

## 17. V0.1 不要追求“本地模型一定能逃生”

V0.1 更重要的成功标准应该是：

```text
Environment deterministic
Agent cannot access hidden state
Trace complete
Metrics reliable
Model providers replaceable
React baseline well-defined
Structured Memory well-defined
Repeated experiments reproducible
Behavior differences measurable
```

如果最终发现：

```text
8B local model:
low success

14B local model:
moderate success

API model:
high success
```

这本身就是一个合理结果。

Agent Arena 的目标不是证明本地小模型一定可以解决任务。

它的目标是：

> **在相同环境与 Agent architecture 下，可靠测量模型和架构差异如何影响长程行为。**

---

## 18. 当前 Prompt 建议

ReactAgent Prompt 应逐步从“Spaceship 攻略”退回成“通用行为约束”。

### 建议保留

```text
You are an autonomous agent operating in a partially observable environment.

You can only act using public tools.

Never invent locations, objects, inventory items, or hidden state.

Use only currently available exits and visible targets.

Treat failed tool results as facts.

Do not repeat the same failed action unless its relevant preconditions have changed.

Prefer actions that:
1. gather new information,
2. resolve an unknown prerequisite,
3. obtain a useful resource,
4. advance the goal.

Choose exactly one valid action.
```

### 建议移除

类似：

```text
When you enter storage_room, inspect storage_crate.
```

```text
After getting screwdriver and fuse, immediately go to corridor.
```

```text
After diagnostic terminal says X, go to reactor_room.
```

这些规则应该由 Agent 自己从环境反馈中推导，而不是写进 baseline prompt。

---

## 19. 推荐的开发顺序

从现在开始建议按以下顺序推进：

```text
1. ReactAgent 加 last-5-step recent history
        ↓
2. Runner 加 repeated-action detector
        ↓
3. Runner 加 no-progress detector
        ↓
4. 删除新增的 spaceship-specific prompt rules
        ↓
5. qwen3:8b × 5
        ↓
6. 分析 trace
        ↓
7. qwen2.5:14b × 5
        ↓
8. 第二模型家族 × 5
        ↓
9. 根据 stopping rule 决定本地 / API
        ↓
10. 实现 MemoryAgent
        ↓
11. React vs Memory 正式 benchmark
```

---

## 20. 建议的最近几个 Commit

可以按小 commit 推进：

```text
feat(agent): add bounded recent history to react context
```

```text
feat(runner): detect repeated failed actions
```

```text
feat(runner): add milestone-based no-progress detection
```

```text
refactor(prompt): remove spaceship-specific react heuristics
```

```text
feat(metrics): record max progress and loop events
```

```text
test(agent): add deterministic loop-detection scenarios
```

最后再：

```text
feat(memory): add deterministic structured memory agent
```

不要一次把这些东西全部塞进一个 commit。

---

## 21. V0.1 的推荐验收标准

### Environment

- [ ] deterministic world rules
- [ ] Agent 无法读取 hidden state
- [ ] canonical solution 可以稳定通关
- [ ] 核心规则有 unit tests

### Runtime

- [ ] structured Action validation
- [ ] Episode termination reliable
- [ ] trace 完整保存
- [ ] invalid output 可记录
- [ ] repeated failed action 可检测
- [ ] no-progress 可检测

### ReactAgent

- [ ] 使用 bounded recent history
- [ ] 不包含 Structured Memory
- [ ] prompt 不包含谜题攻略
- [ ] 可以稳定产生合法 Action

### MemoryAgent

- [ ] memory 只来自公开 observation/result
- [ ] visited rooms 可持久保存
- [ ] known facts 可持久保存
- [ ] failed actions 可持久保存
- [ ] inventory 同步可靠

### Evaluation

- [ ] Success Rate
- [ ] Average Steps
- [ ] Invalid Actions
- [ ] Repeated Actions
- [ ] Repeated Failed Actions
- [ ] Maximum Progress
- [ ] Loop Events
- [ ] Token Usage

### Experiment

- [ ] same world
- [ ] same model
- [ ] same temperature
- [ ] same max steps
- [ ] same tools
- [ ] only agent architecture changes
- [ ] React 至少 20 episodes
- [ ] Memory 至少 20 episodes
- [ ] 保存原始 Episode traces

---

## 22. 当前最值得回答的研究问题

V0.1 不要把问题扩大成：

> Which model is the best agent model?

也不要扩大成：

> Can local LLMs solve autonomous agent tasks?

第一阶段只需要回答：

> **Does structured memory reduce forgetting and repetitive behavior in a long-horizon partially observable task?**

可以拆成三个可测量子问题：

### RQ1

MemoryAgent 是否提高 Success Rate？

### RQ2

MemoryAgent 是否减少 Repeated Failed Actions / Loop Events？

### RQ3

MemoryAgent 是否用更少步骤达到更高 Maximum Progress？

如果能用 trace 和数据回答这三个问题，V0.1 就已经成立。

---

## 23. 最重要的工程判断

现在遇到的循环不是需要被“藏起来”的失败。

它本身就是 Agent Arena 最有价值的数据之一。

例如：

```text
ReactAgent
Step 4  -> control terminal: no_power
Step 9  -> control terminal: no_power
Step 14 -> control terminal: no_power
```

然后 MemoryAgent：

```text
Memory:
- Control terminal has no power.
- Power has not yet been restored.

Decision:
Do not revisit the terminal yet.
Investigate the reactor dependency.
```

如果最终实验能稳定显示：

```text
Memory
    ↓
less forgetting
    ↓
fewer repeated failed actions
    ↓
higher progress
    ↓
higher task success
```

这比单纯展示“一次成功逃生”更有价值。

---

# 最终建议

短期内不要立刻购买 API，也不要继续堆 prompt。

先完成：

```text
Recent History
+
Runtime Loop Detection
+
Milestone Progress
```

然后重新验证现有 `qwen3:8b`。

接着测试一个更大的本地模型。

如果更大的本地模型和另一个模型家族在相同 Agent architecture 下仍然无法稳定推进，则按照 stopping rule 切 API。

无论最终使用本地模型还是 API，Agent Arena 都应该始终保持：

> **LLM provider 是可替换变量，Agent architecture 才是项目真正研究的对象。**

以及三个核心边界：

> **LLM decides. Environment determines reality.**

> **Agent only knows what it has observed.**

> **Every architectural feature must be measurable.**
