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
| 9 | PlanningAgent v1 | Research Core | done |
| 10 | ReflectionAgent | Deferred | planned |
| 11 | Planning v1 Failure Analysis & Evaluation v2 | Research Core | done |

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

补充实验：`planner_assisted` 作为独立的公开规划辅助模式完成本地 `qwen2.5:7b` 通关验证。它不替模型执行 Action，结果不并入纯 ReactAgent/MemoryAgent benchmark；技术决策见 [0005](../specs/0005-planner-assisted-agent/index.md)。

## 当前研究与交付清单

下面的清单把“已经能通关”与“还没有证明”的问题分开。`planner_assisted` 的成功只能证明真实本地模型能在公开规划建议下执行一条合法路线，不能代表模型已经具备纯自主规划能力。

### A. 原计划尚未完成

- [ ] **Streamlit 实验界面**：选择 provider、模型、Agent、world 和 seed，启动单局或 benchmark，并查看逐步 Observation、Action、ToolResult、trace 和聚合指标。
  - 验收：UI 明确显示 Agent 类型和辅助来源；不能把 `planner_assisted` 标成纯 ReactAgent/MemoryAgent；失败、超步数和非法输出都有可见状态。
- [x] **PlanningAgent v1**：实现高层子目标规划和事件触发阶段切换，规划本身不直接调用环境、不绕过 Action schema。
  - 工程验收：规划版本、阶段变化和实际 Action 可复盘；Fake provider 5 seeds smoke benchmark 已通过。
  - 研究验收待办：真实模型需与基线在相同 seed、预算和模型下进行对照。
- [ ] **ReflectionAgent**：只在明确触发条件下根据失败或循环进行反思和重规划。
  - 验收：反思触发次数、输入摘要和后续动作可追踪；证明它减少失败或重复动作，而不是只增加 token。
- [ ] **多世界、多模型对照**：至少加入第二个 world version 和第二种模型规模，避免结论只适用于单一地图和 `qwen2.5:7b`。
  - 验收：固定实验矩阵、统一指标和可重放 trace。

### B. 纯模型自主通关验收（当前首要未完成任务）

这项任务必须证明模型在不依赖 Spaceship Escape 谜题攻略式提示、不使用 `planner_assisted` 或 `guarded` 引导的情况下，仅根据公开 Observation、历史和环境反馈完成任务。当前 ReactAgent、MemoryAgent 和 PlanningAgent 均有实现与 Fake provider 对照测试；真实 Ollama 对照已覆盖 React、Memory、Planning，但尚未取得可重复的纯模型成功。

- [x] ReactAgent + Ollama `qwen2.5:7b`，使用通用 prompt，不使用 planner feedback 或 `guarded` 公开规则保护。
- [x] MemoryAgent + Ollama `qwen2.5:7b`，保持与 ReactAgent 相同的模型、seed、预算和通用 prompt，只增加结构化记忆。
- [x] ReactAgent 和 MemoryAgent 均使用通用 prompt 完成 5 局真实 Ollama 对照，关闭 planner feedback 和循环提醒。
- [x] 每局记录并比较成功率、步数、重复或拒绝动作、非法输出、token 使用量和耗时。
- [x] PlanningAgent 使用相同 world、模型、seed、temperature 和 step limit 完成 5 局真实 Ollama 对照；结果为 0/5 成功，平均 30 步，子目标完成率 0%。
- [x] 纯模型、`guarded` 和 `planner_assisted` 结果保持独立标记。
- [ ] 公开失败 trace，并确认至少一组纯模型结果可以重复成功；本轮 React、Memory、Planning 均未成功，自主通关验收仍未通过。

### C. 尚未测试的行为

- [x] `guarded` 公开规则保护模式：已通过 Fake contract test 验证它只提供公开规则反馈，不替模型选择或执行 Action；真实模型行为仍需对照。
- [ ] 规划建议被模型拒绝、偏离或返回非法 Action 时，Runner 是否正确继续、重试或终止。
- [x] planner 的阶段转换：Fake provider 已覆盖 `POWER_RESTORED`、`CODE_READ`、回到控制终端和最终 `finish`；真实模型路线仍需验证。
- [x] `reset`、`finish` 以及跨 episode 的 Memory、阶段和循环检测状态清理：已有 PlanningAgent lifecycle 回归测试。
- [ ] `qwen2.5:14b` 暂缓测试：当前 Mac M5 Air 运行资源不足，不纳入本轮实验矩阵，待更合适硬件再恢复。
- [ ] 不同 seed、world version 和模型温度下的路线稳定性；确认 19 步不是规则或测试桩写死的固定结果。
- [x] 完整回归：planner-assisted 路线只使用当前公开出口，且 contract test 验证公开反馈不泄漏 WorldState 或密钥。
- [x] 真实 world 选择：`RuntimeSettings.world` 与 `RuntimeSettings.world_version` 通过 `create_environment` 驱动加载，并拒绝未知组合。

### D. 建议新增或修改

- [x] 修正 `PublicLoopDetector`：公开状态已包含 `available_exits` 等进展信息，并有合法回程回归测试。
- [x] 将每步 planner feedback 以长度受限文本或 hash 写入 trace，支持复盘且不记录完整思维链或密钥。
- [x] 增加 guidance 偏离率指标：benchmark 已比较 planner 建议与模型实际 Action，并统计偏离后的成功率。
- [ ] 做提示消融：仅公开阶段提示、阶段提示加多个候选动作、阶段提示加唯一下一动作建议，分别 benchmark。
- [x] 将公开规则保护与规划器辅助拆成独立实验变量；trace provenance 和 benchmark 已分开记录“模型自主性”和“通关可靠性”。
- [ ] 补充真实模型回归测试和最小可重复实验脚本，固定模型标签、prompt 版本、world 版本、seed 和输出目录格式。
- [x] 补齐 benchmark 实验指标：已覆盖阶段完成率、重复 Action 比例、连续 `look`、唯一公开状态数、planner guidance 偏离率和偏离后的成功率。
- [x] 为 planner feedback 写入长度受限摘要或 hash，以支持建议与实际 Action 的安全复盘。

### E. 完成判定

- [ ] 纯模型至少有一组可重复的成功结果，并公开失败样本，不能只报告成功局。
- [ ] 辅助模式与纯模型模式有独立 trace、独立指标和独立结论。
- [ ] 关键技术债和未测试项关闭后，再将 Streamlit 和 Planning/Reflection 结果纳入下一版研究总结。

## Release 3

### 8. Streamlit 实验界面 · planned

提供世界状态、执行 trace 和指标的可视化，让单局行为和 benchmark 结果容易检查。

Done when: 可以选择 Agent 和世界，运行 episode，并查看每一步的决策与结果。

- [ ] `/architect Streamlit 实验界面`

## Research Core

### 9. PlanningAgent v1 · done

在保持 Environment、Observation、统一 Action schema 和 Runner 边界不变的前提下，加入事件触发的 Planner、PlanState、Executor integration、PlanMonitor、Planning Trace 和 Benchmark 指标。

Done when: Planner 不读取 WorldState、不直接执行 Action；子目标完成、连续无进展和重复失败都能触发可复盘的重规划；Fake provider 和自动质量检查通过。

- [x] Design it (spec): [0006](../specs/0006-planning-agent-v1/index.md)
- [x] Build it: PlanningAgent、PlanMonitor、Planner provider contract、Trace、Benchmark 和 CLI
- [x] Verify it: 96 项 pytest、Ruff、mypy 通过；Fake provider 5 seeds smoke benchmark 通过
- [x] Test it: planning models、monitor、agent lifecycle、trace 和 benchmark 回归

真实 PlanningAgent 5 seeds 对照已使用本地模型服务完成，但 0/5 成功，Fake 结果不代表自主规划研究结论；Evaluation v2 已完成独立重跑和失败分析，仍需取得可重复成功样本。

### 11. Planning v1 Failure Analysis & Evaluation v2 · done

冻结 PlanningAgent v1 的 Planner→Executor 核心，增加公开事实、State/Epistemic Progress 分离、结构化 SuccessCriterion、Trace schema v2、规则失败分类和 `analyze-trace(s)` CLI。旧 trace 与 v1 字符串条件保持可读取；缺失字段的旧指标显式标记不可用。

- [x] 对原始 Planning v1 5 局 trace 完成离线失败分析。
- [x] 在 Evaluation v2 后以相同 `qwen2.5:7b`、固定 seeds、30 步、autonomous 配置独立重跑 5 局。
- [x] 对 5 局各自前 10 个执行动作及重规划边界完成 Grounding Failure 人工抽样检查。
- [x] 形成 [Planning v1 Failure Analysis](../experiments/planning-v1-failure-analysis.md)，回答 RQ1–RQ6 并完成 Gate 判断。
- [x] 生成 `results/planning-v1-eval-v2/failure_analysis.json` 和 `.csv`；结果目录为本地生成物。

结论：重跑仍为 0/5；主要证据指向 Action grounding 与 exploration/recovery 空转，而非单纯 Criteria 误判。暂不实现 PlanningAgent v2，后续先做带人工抽样标注的单变量验证。

## Deferred

### 10. ReflectionAgent · planned

在 PlanningAgent v1 的真实模型对照稳定后，再加入明确触发条件的失败反思与重规划。

Done when: 反思触发次数、输入摘要和后续动作可追踪，并能证明它减少失败或重复动作，而不是只增加 token。

- [ ] `/architect ReflectionAgent`

## 当前下一步

Release 2 的确定性环境、ReactAgent、MemoryAgent、Agent Loop、Episode Trace、终止控制和 benchmark 已完成。PlanningAgent v1 的工程闭环和 Evaluation v2 失败分析也已完成；它与 `planner_assisted` 保持独立。**B. 纯模型自主通关验收** 仍是失败基线：通用 prompt 下 ReactAgent、MemoryAgent 和 PlanningAgent 在 `qwen2.5:7b` 固定 5 seeds 中均未成功。Evaluation v2 重跑显示平均 Planner call ratio 85.3%、State Progress 0、每局 29 次无进展动作、唯一公开房间 1 个和同子目标重复 Action 26 次，当前主要证据指向 Action grounding 与 exploration/recovery 空转。Fake smoke benchmark 只证明工程闭环，不代表模型自主能力。下一步是完成失败步骤的人工抽样和单变量消融，再决定 PlanningAgent v2、ReflectionAgent 和 Streamlit 的顺序。
