# Agent Arena Scope

**Product:** 一个用于学习和比较 LLM Agent 行为的轻量实验环境。
**Build approach:** Skateboard，先交付一个从环境到结果完整可用的最小版本，再逐步增加 Agent 能力。
**Workflow:** Medium，开发后运行验证和测试，保证环境规则与实验指标可信。
**Source:** `研究总纲.md`（日常摘要），完整参考为 `总纲.md`

## At a glance

| # | Feature | Phase | Status |
|---|---|---|---|
| 1 | Python 项目骨架与命令入口 | Foundation | done |
| 2 | Spaceship Escape 环境 | Release 1 | done |
| 3 | 环境规则测试 | Release 1 | done |
| 4 | ReactAgent 与 Agent Loop | Release 1 | done |
| 5 | Episode Trace 与终止控制 | Release 1 | done |
| 6 | MemoryAgent | Release 2 | done |
| 7 | Benchmark 与指标 | Release 2 | done |
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

### 2. Spaceship Escape 环境 · done

实现六个房间、物品、能源修复和逃生授权组成的确定性部分可观测世界。Agent 只能通过工具获得观察结果。

Done when: 人可以只使用公开工具完成通关，环境不会暴露完整 WorldState。

- [x] Design it (spec): `/architect Spaceship Escape 环境`
- [x] Build it: `/develop Spaceship Escape 环境`
  - [x] 定义世界模型与 `spaceship_escape_v1` 配置，覆盖 AC-1、AC-2、AC-3、AC-9
  - [x] 实现导航、观察、储物箱和拾取规则，覆盖 AC-3、AC-4、AC-5、AC-8
  - [x] 实现诊断、反应堆修复、授权码和逃生状态，覆盖 AC-6、AC-7、AC-8
  - [x] 固定环境规则测试和手动通关验证，覆盖 AC-1 至 AC-9
- [x] Verify it: `/check verify Spaceship Escape 环境`
- [x] Test it: `/test Spaceship Escape 环境`
Spec [0002](../specs/0002-spaceship-escape/index.md)
Code in `src/agent_arena/arena/`, `src/agent_arena/worlds/`, and `tests/test_spaceship_escape.py`

### 3. 环境规则测试 · done

用测试固定世界规则，保证 benchmark 的结果来自 Agent 行为，而不是环境 bug。

Done when: 覆盖无电不能读终端、工具使用条件、修复反应堆恢复供电、逃生授权和非法动作。

- [x] `/develop 环境规则测试`

### 4. ReactAgent 与 Agent Loop · done

实现一个只依赖简短决策说明和结构化 Action 的基线 Agent，并驱动观察、决策、执行循环。

Done when: Agent 可以读取 observation，选择工具，处理工具反馈，并在限制步数内尝试完成任务。

- [x] Design it (spec): [0003](../specs/0003-react-agent-loop/index.md)
- [x] Build it: `/develop ReactAgent 与 Agent Loop`
- [x] Verify it: `/check verify ReactAgent 与 Agent Loop`
- [x] Test it: `/test ReactAgent 与 Agent Loop`

### 5. Episode Trace 与终止控制 · done

记录每一步的 observation、decision、action、result 和资源消耗，并处理成功、超步数、连续非法输出等终止条件。

Done when: 每次运行都生成可复盘的 JSON trace，并能明确区分成功、失败和系统错误。

- [x] Design it (spec): [0003](../specs/0003-react-agent-loop/index.md)
- [x] Build it: `/develop Episode Trace 与终止控制`
- [x] Verify it: `/check verify Episode Trace 与终止控制`
- [x] Test it: `/test Episode Trace 与终止控制`

## Release 2

### 6. MemoryAgent · done

在 ReactAgent 基础上加入规则驱动的结构化记忆，保存事实、访问位置、失败动作和未解决问题。

Done when: MemoryAgent 能在后续决策中使用记忆，并且可以与无记忆基线做公平对比。

- [x] Design it (spec): [0004](../specs/0004-memory-agent/index.md)
- [x] Build it: `/develop MemoryAgent`
  - [x] 实现结构化记忆、脱敏、Action 标识和问题映射，覆盖 AC 1、AC 2、AC 5、AC 6
  - [x] 实现 provider 请求、Agent 生命周期、MemoryAgent 和 Runner 更新，覆盖 AC 3、AC 4、AC 9、AC 11
  - [x] 实现 trace 来源、CLI Agent 选择和公平对照测试，覆盖 AC 7、AC 8、AC 10
- [x] Verify it: `/check verify MemoryAgent`
- [x] Test it: `/test MemoryAgent`
Spec [0004](../specs/0004-memory-agent/index.md) · code in `src/agent_arena/agents/`, `src/agent_arena/llm/`, `src/agent_arena/evaluation/`, and `src/agent_arena/safety.py`

### 7. Benchmark 与指标 · done

重复运行固定世界和 Agent，统计成功率、平均步数、非法动作、重复动作和 token 使用量。

Done when: 一条命令可以运行多局实验，输出 JSON 和 CSV，并比较 ReactAgent 与 MemoryAgent。

- [x] `/develop Benchmark 与指标`
  - [x] 从持久化 Episode Trace 生成每局指标、JSON manifest 和 CSV 行
  - [x] 支持 `--episodes`、`--provider`、`--agent react|memory|both` 和输出目录
  - [x] 默认运行 ReactAgent 与 MemoryAgent 的同 seed 对照，并保持 `episode_index` 稳定
- [x] `/check verify Benchmark 与指标`
- [x] `/test Benchmark 与指标`

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

Release 2 已完成：ReactAgent、MemoryAgent 与同世界同 seed 的 benchmark 对照均可运行。下一步是在有稳定 benchmark 结果后设计 Release 3 的 Streamlit 实验界面。

当前不开发 PlanningAgent 或 ReflectionAgent。Streamlit 需要先完成 `/architect Streamlit 实验界面`；Planning 与 Reflection 要等 benchmark 结果稳定后再排期。
