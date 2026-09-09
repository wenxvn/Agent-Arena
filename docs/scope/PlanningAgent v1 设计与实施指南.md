# PlanningAgent v1 设计与实施指南

**Project:** Agent Arena  
**Feature:** PlanningAgent v1  
**Suggested Spec:** `docs/specs/0006-planning-agent-v1/index.md`  
**Status:** Proposed  
**Priority:** P0 / 下一阶段核心研究任务

---

# 1. 背景

Agent Arena 当前已经具备：

- 确定性、部分可观测环境；
- ReactAgent；
- MemoryAgent；
- Episode Runner；
- Episode Trace；
- Benchmark；
- `planner_assisted`；
- 最近轨迹、结构化里程碑、语义 Action Guard、循环恢复、候选动作和阶段上下文等实验变量。

当前实验已经表明：

- ReactAgent 在长程任务中容易陷入重复动作；
- MemoryAgent 可以保存更多事实，但无法稳定完成阶段转换；
- 最近历史可以改善局部探索，但无法稳定保持长程目标；
- Action Guard 可以减少明显非法动作，但无法判断“合法但无意义”的动作；
- Candidate Selection 可以解决部分参数生成问题，但仍可能发生目标绑定错误；
- 简单阶段标签不能稳定完成“阶段 → 子目标 → Action”的桥接；
- `planner_assisted` 可以稳定完成任务，但其路线主要由确定性规则规划器提供，因此不能作为模型自主规划能力。

因此，下一阶段不再继续增加零散自然语言提示，而是正式研究：

> **显式 Planning 是否能够提高 Agent 在部分可观测长程任务中的任务分解、阶段保持、目标绑定和失败恢复能力。**

---

# 2. PlanningAgent v1 的研究问题

PlanningAgent v1 只回答一个核心问题：

> 在相同模型、环境、Observation、Action Schema 和步数预算下，引入显式的“当前子目标计划状态”，是否能够显著改善 Agent 的长程任务表现？

重点研究以下问题：

1. Agent 是否能够维护稳定的当前子目标？
2. Agent 是否能够根据新 Observation 更新计划？
3. Agent 是否能够把资源绑定到正确目标？
4. Agent 是否能够在阶段完成后主动切换子目标？
5. Agent 是否能够避免重复执行已经完成或已经失败的动作？
6. Planning 带来的收益是否超过额外 token 和 latency 成本？

---

# 3. 核心设计原则

PlanningAgent v1 必须遵守以下原则。

## 3.1 Planner 不知道隐藏状态

Planner 只能看到：

- 当前公开 Observation；
- 公开 ToolResult；
- 允许暴露的结构化 Memory；
- 最近有限公开轨迹；
- 当前 PlanState。

Planner 不得访问：

- `WorldState`；
- 隐藏任务进度；
- 世界完整地图；
- 物品真实位置；
- 隐藏前置条件；
- 程序内部谜题答案；
- `planner_assisted` 的规则路线。

---

## 3.2 Planner 不直接执行 Action

PlanningAgent 必须保持：

```text
Observation
    ↓
Planner
    ↓
PlanState
    ↓
Executor
    ↓
Action
    ↓
Environment
```

Planner 决定：

> “现在应该完成什么子目标？”

Executor 决定：

> “为了完成这个子目标，现在应该执行哪个 Action？”

Environment 仍然是唯一事实来源。

---

## 3.3 不允许把 Spaceship Escape 攻略写入 Planner

禁止出现类似：

```python
if not has_screwdriver:
    go_to("storage_room")
```

或者：

```python
if power_off:
    next_goal = "find screwdriver and replacement fuse"
```

PlanningAgent 必须是通用机制。

同一套 PlanningAgent 未来应该能够直接用于第二个 World。

---

# 4. PlanningAgent v1 架构

建议采用三层结构：

```text
                ┌───────────────┐
                │  Observation  │
                └───────┬───────┘
                        ↓
                ┌───────────────┐
                │    Planner    │
                │   高层规划器   │
                └───────┬───────┘
                        ↓
                   PlanState
                        ↓
                ┌───────────────┐
                │   Executor    │
                │   动作执行器   │
                └───────┬───────┘
                        ↓
                     Action
                        ↓
                ┌───────────────┐
                │ Environment   │
                └───────┬───────┘
                        ↓
                  ToolResult
                        ↓
                ┌───────────────┐
                │ Plan Monitor  │
                │ 计划状态判断   │
                └───────────────┘
```

v1 暂时不单独加入 ReflectionAgent。

Plan Monitor 只负责判断：

- 当前子目标是否已经完成；
- 当前子目标是否明显失败；
- 是否需要重新调用 Planner。

---

# 5. PlanState 设计

PlanningAgent v1 不需要复杂 Plan Tree。

第一版只维护一个小型结构化状态。

建议：

```python
class PlanState(BaseModel):
    plan_version: str = "planning_v1"

    overall_goal: str

    current_subgoal: str

    success_criteria: tuple[str, ...]

    known_constraints: tuple[str, ...]

    relevant_resources: tuple[str, ...]

    completed_subgoals: tuple[str, ...]

    unresolved_questions: tuple[str, ...]

    replan_reason: str | None = None
```

---

# 6. 各字段解释

## overall_goal

任务总目标。

例如：

```text
完成当前环境要求的最终任务。
```

通常保持稳定，不频繁修改。

---

## current_subgoal

PlanningAgent v1 中最重要的字段。

它必须描述：

> 现在应该解决什么问题？

而不是描述：

> 当前处于什么阶段？

正确：

```text
获得完成当前维修所需要的资源
```

```text
找到恢复系统电力的方法
```

```text
利用已经获得的信息完成最终目标
```

不推荐：

```text
阶段 2
```

```text
已经获得授权码
```

```text
POWER_RESTORED
```

后者是状态，不是目标。

---

## success_criteria

Planner 必须说明：

> 什么公开证据出现后，可以认为当前 subgoal 已经完成？

例如：

```text
inventory 中出现所需资源
```

或者：

```text
ToolResult 明确返回系统恢复成功
```

不能使用隐藏 WorldState。

---

## known_constraints

保存当前已经确定的公开约束。

例如：

```text
某终端当前没有电力
```

```text
当前 Action 必须针对可见对象
```

```text
某个已经失败的动作在条件没有变化前不应重复
```

---

## relevant_resources

记录 Planner 当前认为与子目标相关的已知资源。

注意：

这里只允许记录已经公开观察到的信息。

不能预测隐藏物品。

---

## completed_subgoals

保存已经完成的高层任务。

例如：

```text
确认主系统当前没有电力
```

```text
获得维修资源
```

---

## unresolved_questions

Planner 当前无法回答，但可能影响后续规划的问题。

例如：

```text
尚不知道如何恢复系统电力
```

---

# 7. Planner 输入

Planner 每次不应该获得完整 Episode Trace。

建议输入：

```text
Overall Goal

Current Observation

Last ToolResult

Current Memory Summary

Current PlanState

Recent History（最多 3~5 步）

Reason for Replanning
```

严格限制长度。

---

# 8. Planner 输出 Schema

Planner 必须输出结构化数据。

建议：

```python
class PlannerDecision(BaseModel):
    decision_reason: str

    current_subgoal: str

    success_criteria: tuple[str, ...]

    known_constraints: tuple[str, ...]

    relevant_resources: tuple[str, ...]

    unresolved_questions: tuple[str, ...]
```

`decision_reason`：

- 最多 280 字；
- 只保存简短理由；
- 不要求完整 Chain-of-Thought；
- 不记录隐藏推理。

---

# 9. Planner Prompt 原则

Planner Prompt 必须保持通用。

核心要求：

```text
你负责决定“下一阶段应该解决什么问题”，而不是直接选择工具动作。

你只能使用公开 Observation、ToolResult、Memory 和最近轨迹。

不要假设未观察到的房间、对象、物品、规则或任务状态。

current_subgoal 应描述一个可以通过若干工具动作完成的中间目标。

success_criteria 必须能够通过未来公开 Observation 或 ToolResult 判断。

不要直接输出 move、inspect、pickup、use 等具体 Action。

如果当前计划仍然合理，不要无意义地改变 current_subgoal。
```

---

# 10. Executor

Executor 可以复用现有 ReactAgent 的大部分能力。

区别是 Executor 请求中额外加入：

```text
Current Subgoal
Success Criteria
Known Constraints
Relevant Resources
```

Executor 仍然只输出一个 Action。

建议：

```text
Observation
+
PlanState
+
Memory
+
Recent History
↓
Executor
↓
Action
```

---

# 11. Executor Prompt 的关键变化

原 React：

```text
优先选择推进最终目标的动作
```

PlanningAgent Executor：

```text
你的首要任务不是直接完成最终目标，而是推进 Current Subgoal。

选择 Action 时优先考虑：

1. 是否能直接满足当前子目标；
2. 是否能获得完成当前子目标所缺失的信息；
3. 是否能消除当前计划中的公开约束；
4. 是否已经执行过相同且没有进展的动作。

不要自行改变 Current Subgoal。
如果发现当前子目标无法继续，通过 Action 获取必要信息。
真正的重新规划由 Planner 完成。
```

这样可以避免 Planner 和 Executor 职责混在一起。

---

# 12. 什么时候调用 Planner

绝对不要每一步都 Planner。

否则会：

- token 激增；
- latency 激增；
- 计划不断漂移；
- 实验难以解释。

建议 Planner 只在以下情况下调用。

## Trigger 1：Episode 开始

第一次 Observation 后生成初始 PlanState。

---

## Trigger 2：当前子目标完成

Plan Monitor 根据：

```text
success_criteria
+
Observation
+
ToolResult
```

判断当前子目标完成。

调用 Planner 生成下一子目标。

---

## Trigger 3：连续无进展

例如：

```text
3 个连续 Action 没有产生新的公开状态或有效进展
```

则：

```text
replan_reason = "no_progress"
```

---

## Trigger 4：公开事实证明计划不可行

例如：

```text
当前计划依赖某对象，
但新的公开 ToolResult 已证明该路径不可行
```

则：

```text
replan_reason = "constraint_violation"
```

---

## Trigger 5：重复失败

同一公开状态下：

```text
same Action
+
same failure reason
```

连续出现。

则触发：

```text
replan_reason = "repeated_failure"
```

---

# 13. v1 不应该触发 Planner 的情况

以下情况不要自动重新规划：

- 单次 Action 失败；
- 单次 move；
- 单次 inspect；
- Observation 文本变化但没有重要状态变化；
- Executor 与 Planner “意见不一致”；
- 模型理由看起来不够聪明。

避免 Planner 过度参与低层执行。

---

# 14. Progress 定义

PlanningAgent v1 最重要的基础设施之一是：

> 明确定义 progress。

推荐只使用公开数据。

Public Progress State 可以包含：

```python
class PublicProgressState(BaseModel):
    current_room: str
    visible_objects: tuple[str, ...]
    available_exits: tuple[str, ...]
    inventory: tuple[str, ...]
    last_result_status: str | None
    last_result_reason: str | None
```

未来可以加入公开 milestone，但不得读取 WorldState。

---

# 15. PlanningAgent 类结构建议

建议：

```text
src/agent_arena/agents/
├── react.py
├── memory.py
├── candidate.py
├── planner.py
└── planning.py
```

不要继续把新的逻辑堆到现有 `planner_assisted`。

建议新建：

```python
class PlanningAgent:
    name = "planning"
    prompt_version = "planning_v1"
```

内部持有：

```python
planner
executor
plan_state
```

---

# 16. 推荐的内部接口

```python
class PlanningAgent:

    def reset(self) -> None:
        ...

    def request(
        self,
        observation: Observation,
        *,
        last_result: ToolResult | None,
        recent_history: str | None,
        memory: str | None,
    ) -> AgentDecision:
        ...
```

内部流程：

```text
if no_plan:
    plan()

elif should_replan():
    plan()

action = executor.request(
    observation,
    plan_state,
    memory,
    history,
)

return action
```

---

# 17. Plan Monitor

建议单独实现：

```text
src/agent_arena/planning/monitor.py
```

例如：

```python
class PlanMonitor:

    def evaluate(
        self,
        plan: PlanState,
        before: Observation,
        action: Action,
        result: ToolResult,
        after: Observation,
    ) -> PlanSignal:
        ...
```

返回：

```python
class PlanSignal(BaseModel):
    status: Literal[
        "continue",
        "subgoal_completed",
        "no_progress",
        "repeated_failure",
        "plan_invalid",
    ]

    reason: str | None
```

---

# 18. Plan Monitor 不能做什么

Plan Monitor 不能：

```python
if current_room == "storage_room":
    goal = "pickup screwdriver"
```

Plan Monitor 只判断：

> 是否需要 Planner 再思考一次。

不决定新计划。

---

# 19. Trace 必须新增的信息

PlanningAgent 的主要研究价值来自可复盘。

每一步建议增加：

```text
plan_version
plan_id
current_subgoal
planner_called
replan_reason
subgoal_completed
```

Planner 调用时额外记录：

```text
planner_latency_ms
planner_input_tokens
planner_output_tokens
```

不要保存：

- 完整 Planner CoT；
- 原始 Provider Response；
- Secret；
- 隐藏 WorldState。

---

# 20. Episode Provenance

建议增加：

```text
planning_enabled=true

planner_prompt_version=planning_v1

executor_prompt_version=react_v12_planning_executor

plan_monitor_version=plan_monitor_v1

planning_policy=event_triggered
```

确保结果可以复现。

---

# 21. Benchmark 新指标

PlanningAgent v1 不应该只看 success rate。

至少增加：

## 最终表现

```text
success_rate
mean_steps
```

## 规划质量

```text
planner_call_count
replan_count
completed_subgoal_count
mean_actions_per_subgoal
```

## 稳定性

```text
repeated_action_ratio
no_progress_action_count
unique_public_state_count
rejected_action_count
```

## 成本

```text
planner_tokens
executor_tokens
total_tokens
planner_latency
executor_latency
total_latency
```

---

# 22. 特别重要的指标：Subgoal Completion Rate

建议定义：

```text
subgoal_completion_rate
=
completed_subgoals
/
generated_subgoals
```

这样即使 PlanningAgent 最终没有通关，也可以判断规划是否有效。

---

# 23. 第一轮实验不要换模型

第一轮必须保持：

```text
相同 world
相同 model
相同 seed
相同 temperature
相同 step limit
相同 Action tools
```

只改变 Agent 架构。

建议：

| Condition | Agent |
|---|---|
| B0 | ReactAgent |
| B1 | MemoryAgent |
| B2 | PlanningAgent |
| B3 | planner_assisted |

其中：

`planner_assisted` 只是 reliability upper bound。

---

# 24. 第一轮实验矩阵

建议先跑：

```text
5 seeds × 4 conditions
```

即：

```text
React            5
Memory           5
Planning         5
Planner-assisted 5
```

共 20 局。

如果成本高：

先：

```text
seed 0
seed 1
```

做 smoke test。

确认设计正确后再完成五组固定 seed。

---

# 25. 第一阶段不要同时加入 Reflection

第一轮必须严格保持：

```text
Planning only
```

否则不能判断成功到底来自：

- Planning；
- Reflection；
- Loop Recovery；
- Memory；
- Candidate Selection。

PlanningAgent v1 应该成为独立变量。

---

# 26. 建议消融实验

PlanningAgent 成功运行后，再做：

## P-A0

```text
React
```

## P-A1

```text
React + Memory
```

## P-A2

```text
React + PlanState
```

## P-A3

```text
React + Memory + PlanState
```

回答：

> Planning 和 Memory 是否具有互补作用？

---

# 27. 第二组消融：Planner Trigger

比较：

```text
每步规划
```

vs

```text
事件触发规划
```

重点比较：

- success；
- token；
- latency；
- plan drift。

预计事件触发机制应该更加稳定。

---

# 28. 第三组消融：Plan 表示

未来可以比较：

### Simple

```text
current_subgoal
```

### Structured

```text
current_subgoal
success_criteria
constraints
resources
questions
```

用于判断：

> Planning 的收益来自“多调用一次 LLM”，还是结构化 PlanState 本身？

---

# 29. PlanningAgent v1 成功标准

不要要求：

```text
5/5 通关
```

才算成功。

最低验收标准应该分三层。

## 工程验收

- PlanningAgent 可以完整运行；
- Planner 与 Executor 分离；
- PlanState 正确 reset；
- Planner 不访问 WorldState；
- 所有 Action 仍经过统一 Action Schema；
- Trace 能完整复盘 Plan 生命周期。

---

## 行为验收

相对于 ReactAgent：

至少有两项显著改善：

```text
更高阶段完成率
更少重复动作
更高唯一公开状态数量
更少 no-progress
更少错误目标 Action
```

---

## 研究验收

如果 PlanningAgent：

```text
成功率提高
```

则说明显式 Planning 有帮助。

即使仍为 0%：

只要明显推进到更深阶段，也仍是重要结果。

---

# 30. PlanningAgent v1 失败时如何解释

如果：

```text
React = 0%
Memory = 0%
Planning = 0%
```

不能直接说：

> Planning 没用。

应该检查：

```text
阶段完成率
subgoal 完成率
最大推进阶段
重复动作
错误目标
token
```

例如：

```text
React:
控制室循环

Memory:
进入储藏室

Planning:
恢复电力并读取授权码
```

虽然都是 0%，实际能力已经完全不同。

---

# 31. 明确禁止的实现方式

PlanningAgent v1 禁止以下行为。

## 禁止 1

把 Spaceship 答案写入 system prompt。

## 禁止 2

Planner 根据隐藏 WorldState 规划。

## 禁止 3

Runner 自动替模型执行 Planner 推荐动作。

## 禁止 4

Planner 直接返回唯一 Action。

## 禁止 5

为了通关不断给 prompt 增加谜题规则。

## 禁止 6

Planning 成功后称其为“纯 React 自主能力”。

---

# 32. 开发顺序

严格建议按以下顺序开发。

## Step 0：先修实验契约

在 PlanningAgent 开发前完成：

- world/world_version 真正驱动 environment；
- 修复 PublicLoopDetector；
- benchmark 增加阶段/循环指标；
- 固定 trace provenance。

PlanningAgent 不应该建立在错误实验基础设施上。

---

## Step 1：定义 Planning 数据模型

实现：

```text
PlanState
PlannerDecision
PlanSignal
```

只写 schema 和测试。

---

## Step 2：实现 Planner Provider Adapter

输入：

```text
Observation
Memory
History
Plan
Replan reason
```

输出：

```text
PlannerDecision
```

---

## Step 3：实现 Planning Executor

优先复用 ReactAgent。

不要重新写一整套 Action Agent。

---

## Step 4：实现 PlanMonitor

只实现：

```text
continue
subgoal_completed
no_progress
repeated_failure
```

v1 不要追求复杂。

---

## Step 5：实现 PlanningAgent

把：

```text
Planner
Executor
PlanMonitor
```

组合起来。

---

## Step 6：接入 Episode Runner

Runner 仍然负责：

```text
Action Validation
Environment.step
Trace
Termination
```

PlanningAgent 不越权。

---

## Step 7：Trace

完成：

```text
plan_id
current_subgoal
planner_called
replan_reason
```

---

## Step 8：Fake Provider 自动测试

任何真实模型实验前：

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

全部通过。

---

## Step 9：seed 0 Smoke Test

只跑一局。

人工检查完整 Trace：

```text
Initial Observation
↓
Initial Plan
↓
Action
↓
Observation
↓
Plan 保持
↓
Subgoal Complete
↓
Replan
```

确认逻辑正确。

---

## Step 10：五 seed Benchmark

最后才运行正式实验。

---

# 33. CLI 建议

增加：

```bash
uv run agent-arena run \
  --provider ollama \
  --agent planning \
  --seed 0
```

以及：

```bash
uv run agent-arena benchmark \
  --provider ollama \
  --agent planning \
  --episodes 5 \
  --output-dir results/planning-v1
```

暂时不要增加大量 Planning 参数。

默认：

```text
planning = event triggered
history window = 5
no-progress threshold = 3
```

先固定实验协议。

---

# 34. 推荐目录结构

```text
src/agent_arena/
├── agents/
│   ├── react.py
│   ├── memory.py
│   ├── candidate.py
│   ├── planner.py
│   └── planning.py
│
├── planning/
│   ├── __init__.py
│   ├── models.py
│   └── monitor.py
│
├── evaluation/
│   ├── runner.py
│   ├── benchmark.py
│   ├── trace.py
│   └── loop.py
```

Prompt：

```text
prompts/
├── planning_v1.txt
└── planning_executor_v1.txt
```

---

# 35. 推荐测试

新增：

```text
tests/test_planning_models.py
tests/test_plan_monitor.py
tests/test_planning_agent.py
tests/test_planning_trace.py
```

必须覆盖：

### AC-1

Episode 开始时 Planner 被调用一次。

### AC-2

普通成功 Action 不导致无意义 replan。

### AC-3

满足 success criteria 后触发重新规划。

### AC-4

连续无 progress 后触发重新规划。

### AC-5

Planner 不接收 WorldState。

### AC-6

Executor 无权修改 PlanState。

### AC-7

所有 Action 仍通过原 Action schema。

### AC-8

reset 后 PlanState 清空。

### AC-9

不同 episode 不共享 Plan。

### AC-10

Trace 保存 plan_id 和 current_subgoal。

---

# 36. 推荐的第一版 Planner 行为示例

下面只表示行为形式，不是固定答案。

初始：

```text
Goal:
完成当前环境任务

Observation:
当前位于起始区域，可见某终端和出口

Planner:

current_subgoal:
确定当前系统状态以及阻止完成任务的主要前置条件

success_criteria:
获得能够明确说明下一步需要解决的问题的公开信息
```

Executor：

```text
read_terminal(...)
```

返回：

```text
NO_POWER
```

Planner重新评估：

```text
current_subgoal:
寻找能够恢复系统功能的方法

known_constraints:
当前终端没有电力
```

注意：

Planner 没有说：

```text
去 storage_room 拿 screwdriver
```

这才是通用 Planning。

---

# 37. PlanningAgent v1 最重要的研究假设

建议将以下内容直接写进项目研究文档：

> ReactAgent 在部分可观测长程任务中的核心失败并不完全来自单步推理能力不足，而可能来自缺乏持久的可执行任务表示。

进一步：

> Memory 主要回答“我知道什么”，Planning 主要回答“我现在要完成什么”。

这是 Agent Arena 下一阶段最重要的区分。

可以表示为：

```text
Memory:
What do I know?

Planning:
What am I trying to achieve now?

Executor:
What should I do next?

Reflection:
Why did my previous strategy fail?
```

---

# 38. Agent Arena 后续完整研究路线

PlanningAgent v1 完成以后，推荐形成：

```text
A0 React
        ↓
A1 Memory
        ↓
A2 Planning
        ↓
A3 Planning + Reflection
```

研究能力逐层增加：

```text
React
单步决策

Memory
长期事实保持

Planning
长期目标保持

Reflection
失败后的策略修正
```

---

# 39. PlanningAgent v1 完成后再进入的任务

Planning v1 完成前暂缓：

- Streamlit；
- Multi-Agent；
- MCP；
- RAG；
- LangGraph；
- 自动世界生成；
- 复杂 Planning Tree；
- Reflection；
- 第二 Planner；
- 大规模模型排行榜。

PlanningAgent v1 首先应该回答：

> **显式子目标规划到底有没有用？**

---

# 40. 当前项目的建议里程碑

## Milestone P0 — Experimental Contract

完成：

```text
world selector
loop detector
diagnostic metrics
trace provenance
```

---

## Milestone P1 — Planning Core

完成：

```text
PlanState
Planner
PlanMonitor
Executor integration
```

---

## Milestone P2 — Planning Trace

完整记录：

```text
计划产生
计划保持
计划完成
重新规划
```

---

## Milestone P3 — Planning Benchmark

完成：

```text
React
Memory
Planning
Planner-assisted
```

公平对照。

---

## Milestone P4 — Failure Analysis

回答：

```text
Planning 解决了什么？
Planning 没解决什么？
```

---

# 41. 最终 Definition of Done

PlanningAgent v1 完成必须同时满足：

- [ ] Planner 和 Executor 职责明确分离；
- [ ] Planner 不读取隐藏 WorldState；
- [ ] Planner 不包含 Spaceship Escape 特定路线；
- [ ] PlanState 完全结构化；
- [ ] 支持事件触发重新规划；
- [ ] 子目标完成可以由公开证据判断；
- [ ] 每个 Episode reset PlanState；
- [ ] Trace 可以完整复盘 Plan 生命周期；
- [ ] Benchmark 增加 Planning 指标；
- [ ] React / Memory / Planning 使用相同实验条件；
- [ ] planner_assisted 与 PlanningAgent 明确分离；
- [ ] 至少完成固定 5 seeds 对照；
- [ ] 保存成功与失败 Trace；
- [ ] 分析 success 之外的阶段完成与循环指标；
- [ ] pytest、Ruff、mypy 全部通过。

---

# 42. 一句话版本

PlanningAgent v1 不应该是：

> “一个知道飞船逃生攻略的 Agent。”

而应该是：

> **一个能够根据公开环境反馈持续维护“当前应该完成什么子目标”，并让 Executor 围绕该子目标行动的通用长程 Agent。**

Agent Arena 下一阶段真正要验证的，不是模型能不能被提示到通关，而是：

> **显式 Planning 是否能够突破 ReAct 和 Memory 在长程、部分可观测任务中的 failure boundary。**