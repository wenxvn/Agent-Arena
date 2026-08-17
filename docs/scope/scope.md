# Agent Arena Scope

**Product:** 一个用于学习和比较 LLM Agent 行为的轻量实验环境。
**Build approach:** Skateboard，先交付一个从环境到结果完整可用的最小版本，再逐步增加 Agent 能力。
**Workflow:** Medium，开发后运行验证和测试，保证环境规则与实验指标可信。
**Source:** `研究总纲.md`（日常摘要），完整参考为 `总纲.md`

## At a glance

| # | Feature | Phase | Status |
|---|---|---|---|
| 1 | Python 项目骨架与命令入口 | Foundation | done |
| 2 | Spaceship Escape 环境 | Release 1 | in-progress |
| 3 | 环境规则测试 | Release 1 | planned |
| 4 | ReactAgent 与 Agent Loop | Release 1 | planned |
| 5 | Episode Trace 与终止控制 | Release 1 | planned |
| 6 | MemoryAgent | Release 2 | planned |
| 7 | Benchmark 与指标 | Release 2 | planned |
| 8 | Streamlit 实验界面 | Release 3 | planned |
| 9 | PlanningAgent 与 ReflectionAgent | Deferred | planned |

## Foundation

### 1. Python 项目骨架与命令入口 · done

建立清晰的模块边界和最小运行入口，让环境、Agent、实验执行彼此独立。

Done when: 可以安装依赖，运行一个命令，并从固定配置创建一个 episode。

- [x] Decide the stack (spec): [0001](../specs/0001-project-architecture/index.md)
- [x] Build it: `/develop scaffold Python 项目骨架与命令入口`
  - [x] 创建 `pyproject.toml`、`uv.lock` 和 `src/agent_arena`
  - [x] 创建 RuntimeSettings、CLI 和 Fake provider
  - [x] 配置 pytest、Ruff、mypy 和 GitHub Actions
- [x] Verify it: `/check verify Python 项目骨架与命令入口`
- [x] Test it: `/test Python 项目骨架与命令入口`
Spec 0001 · code in `src/agent_arena/`

## Release 1

### 2. Spaceship Escape 环境 · in-progress

实现六个房间、物品、能源修复和逃生授权组成的确定性部分可观测世界。Agent 只能通过工具获得观察结果。

Done when: 人可以只使用公开工具完成通关，环境不会暴露完整 WorldState。

- [x] Design it (spec): `/architect Spaceship Escape 环境`
- [ ] Build it: `/develop Spaceship Escape 环境`
  - [ ] 定义世界模型与 `spaceship_escape_v1` 配置，覆盖 AC-1、AC-2、AC-3、AC-9
  - [ ] 实现导航、观察、储物箱和拾取规则，覆盖 AC-3、AC-4、AC-5、AC-8
  - [ ] 实现诊断、反应堆修复、授权码和逃生状态，覆盖 AC-6、AC-7、AC-8
  - [ ] 固定环境规则测试和手动通关验证，覆盖 AC-1 至 AC-9
- [ ] Verify it: `/check verify Spaceship Escape 环境`
- [ ] Test it: `/test Spaceship Escape 环境`
Spec [0002](../specs/0002-spaceship-escape/index.md)

### 3. 环境规则测试 · planned

用测试固定世界规则，保证 benchmark 的结果来自 Agent 行为，而不是环境 bug。

Done when: 覆盖无电不能读终端、工具使用条件、修复反应堆恢复供电、逃生授权和非法动作。

- [ ] `/develop 环境规则测试`

### 4. ReactAgent 与 Agent Loop · planned

实现一个只依赖简短决策说明和结构化 Action 的基线 Agent，并驱动观察、决策、执行循环。

Done when: Agent 可以读取 observation，选择工具，处理工具反馈，并在限制步数内尝试完成任务。

- [ ] `/architect ReactAgent 与 Agent Loop`

### 5. Episode Trace 与终止控制 · planned

记录每一步的 observation、decision、action、result 和资源消耗，并处理成功、超步数、连续非法输出等终止条件。

Done when: 每次运行都生成可复盘的 JSON trace，并能明确区分成功、失败和系统错误。

- [ ] `/develop Episode Trace 与终止控制`

## Release 2

### 6. MemoryAgent · planned

在 ReactAgent 基础上加入规则驱动的结构化记忆，保存事实、访问位置、失败动作和未解决问题。

Done when: MemoryAgent 能在后续决策中使用记忆，并且可以与无记忆基线做公平对比。

- [ ] `/architect MemoryAgent`

### 7. Benchmark 与指标 · planned

重复运行固定世界和 Agent，统计成功率、平均步数、非法动作、重复动作和 token 使用量。

Done when: 一条命令可以运行多局实验，输出 JSON 或 CSV，并比较 ReactAgent 与 MemoryAgent。

- [ ] `/develop Benchmark 与指标`

## Release 3

### 8. Streamlit 实验界面 · planned

提供世界状态、执行 trace 和指标的可视化，让单局行为和 benchmark 结果容易检查。

Done when: 可以选择 Agent 和世界，运行 episode，并查看每一步的决策与结果。

- [ ] `/architect Streamlit 实验界面`

## Deferred

### 9. PlanningAgent 与 ReflectionAgent · planned

在基线和 MemoryAgent 可重复比较之后，再加入高层计划、重规划和反思机制。

Done when: 计划和反思都有明确触发条件，并能通过 benchmark 验证是否减少失败和循环。

- [ ] `/architect PlanningAgent 与 ReflectionAgent`

## First step

Foundation 已完成。下一步是运行 `/architect Spaceship Escape 环境`，固化六个房间、公开工具、非法动作和胜利条件。建议后续顺序是：

1. 用 `/develop Spaceship Escape 环境` 实现 `WorldState`、`Action`、`Observation` 和 `Environment.step`。
2. 用 `/develop 环境规则测试` 固定手动通关路径、供电、物品与逃生授权规则。
3. 用 `/architect ReactAgent 与 Agent Loop` 定义结构化决策、修正流程和受限步数循环。
4. 实现 Agent Loop、Episode Trace 和终止控制，完成 Release 1 的可重复闭环。

当前明确不开发 MemoryAgent、Benchmark、Streamlit、PlanningAgent 或 ReflectionAgent。它们要等 Release 1 闭环产生可重复 trace 后再排期。
