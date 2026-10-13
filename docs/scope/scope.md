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
| 12 | 雾岛灯塔第二世界与迁移对照 | Research Core | done |
| 13 | 飞船扩建 v3 与不限步数 | Research Core | done |
| 14 | 三图难度对齐：灯塔 v2 与深海站 v1 | Research Core | done |
| 15 | 三档难度：简单/中等/困难 9 图 | Research Core | done |
| 16 | 七个新世界：十世界三十图 | Research Core | done |
| 17 | 任务结构 pilot：分支/并行/反转 + seeded（flex 引擎） | Research Core | done |
| 18 | 旧三世界重制图：去换皮，新 10×3 矩阵 | Research Core | done |

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

### B. 纯模型自主通关验收（2026-10-11 已通过，Muse 45/45）

这项任务必须证明模型在不依赖 Spaceship Escape 谜题攻略式提示、不使用 `planner_assisted` 或 `guarded` 引导的情况下，仅根据公开 Observation、历史和环境反馈完成任务。当前 ReactAgent、MemoryAgent 和 PlanningAgent 均有实现与 Fake provider 对照测试；真实 Ollama 对照已覆盖 React、Memory、Planning，但尚未取得可重复的纯模型成功。

- [x] ReactAgent + Ollama `qwen2.5:7b`，使用通用 prompt，不使用 planner feedback 或 `guarded` 公开规则保护。
- [x] MemoryAgent + Ollama `qwen2.5:7b`，保持与 ReactAgent 相同的模型、seed、预算和通用 prompt，只增加结构化记忆。
- [x] ReactAgent 和 MemoryAgent 均使用通用 prompt 完成 5 局真实 Ollama 对照，关闭 planner feedback 和循环提醒。
- [x] 每局记录并比较成功率、步数、重复或拒绝动作、非法输出、token 使用量和耗时。
- [x] PlanningAgent 使用相同 world、模型、seed、temperature 和 step limit 完成 5 局真实 Ollama 对照；结果为 0/5 成功，平均 30 步，子目标完成率 0%。
- [x] 纯模型、`guarded` 和 `planner_assisted` 结果保持独立标记。
- [x] Muse `muse-spark-1.3-contributor`（Zen 网关）完成 React/Memory/Planning 各 5 局同等条件对照：React 0/5（控制室/走廊循环），Memory 0/5（工具 3/5、电源 2/5、读码 1/5），Planning 0/5（4 step_limit + 1 网关瞬断，子目标完成率 12%、电源 1/5）；与 qwen 基线独立统计。
- [x] 公开失败 trace，并确认至少一组纯模型结果可以重复成功：2026-10-11 Muse Memory + history5 + stuck_recovery + phase_context + 60 步在 seeds 0–4 获 3/5（36/35/45 步）、全新 seeds 5–9 获 2/5（均 57 步），成功与失败 trace 均归档；消融确认 history/phase/recovery 互补（单变量均为 0/5）。

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

- [x] 纯模型至少有一组可重复的成功结果，并公开失败样本，不能只报告成功局：飞船 10 局 5 胜 + 灯塔 5 局 5 胜，成功与失败 trace 均归档。
- [ ] 辅助模式与纯模型模式有独立 trace、独立指标和独立结论。
- [ ] 关键技术债和未测试项关闭后，再将 Streamlit 和 Planning/Reflection 结果纳入下一版研究总结。

### F. 第二世界迁移对照（2026-10-11，done）

- [x] 雾岛灯塔世界：6 房链式拓扑、新名称新授权码（`TIDE-2049`）、15 步最优公开路径；规则测试与人可通关验证通过（spec 0007）。
- [x] 阶段上下文泛化为世界声明里程碑（`PublicMilestone`），飞船旧文本逐字保留（回归测试锁定）；Runner 不再内置飞船知识。
- [x] Muse 自主组合（memory + history5 + recovery + 通用 phase，无辅助）灯塔 5 seeds：**5/5 成功**（27/28/28/55/57 步），证明能力迁移到未见地图，而非背下飞船路线。

### G. 飞船扩建 v3 与不限步数（2026-10-11，done）

- [x] v3 地图：8 房（货舱藏箱、观察甲板/船员舱/胶带三处诱饵）、新授权码 `BETA-512`、19 步最优公开路径；规则测试通过（spec 0008）。
- [x] `step_limit=0` 表示不限步数：非法输出上限与网关错误照常兜底；探索运行由实验者监督。
- [x] Muse 自主组合（同获胜配置，不限步）v3 5 seeds：**5/5 成功**（152/125/153/93/65 步）；诱饵被查看/拾取均未阻止通关。

### H. 三图难度对齐与自主通关对照（2026-10-11，done）

- [x] 灯塔 v2：8 房（工具箱搬进地窖、旧提灯/礁石/藤壶胶三处诱饵）、新授权码 `TIDE-3160`、16 步最优公开路径；规则测试与人可通关验证通过（spec 0009）。
- [x] 深海站 v1：8 房飞船形拓扑（货舱藏箱、瞭望穹顶/睡舱诱饵链、无电状态板）、新授权码 `ABYSS-618`、19 步最优公开路径；规则测试通过（spec 0009）。
- [x] 灯塔储物箱可见逻辑泛化为按容器房间判定（v1 行为不变）；`create_environment` 注册两对新 selector；全套 143 passed。
- [x] Muse 自主组合（memory + history5 + recovery + phase，不限步）首轮：深海站 seed 0 ✅ 41 步、灯塔 v2 seed 0 ✅ 56 步（终点对小艇 3 次用错 `read_terminal` 后纠正），trace 在 `runs/muse-3maps-*`。
- [x] 飞船 v3：seed 0 两次均在 73/76 步遇网关 `provider_error` 中断（0 非法输出，倾向偶发抖动：seed 1/2 同网关跑过 100+ 步无事）；seed 2 ✅ 113 步、seed 1 ✅ 180 步（重读授权码 20 次，不限步数立功，60 步预算下必挂）。三图均有自主通关样本，trace 在 `runs/muse-3maps-*`。

### I. 三档难度与 9 局全覆盖（2026-10-11，done；5 seeds 矩阵 45/45 done）

- [x] 简单=已有 6 房图零复用改动；困难=4 张新 10 房图（飞船 v4 `GAMMA-904`/21 步、灯塔 v3 `TIDE-5280`/20 步、深海简单 `ABYSS-102`/13 步、深海困难 `ABYSS-909`/21 步），规则零改动（spec 0010）。
- [x] 全套 159 passed（含 16 项新测试）。
- [x] Muse 自主组合（E1-ON，base prompt hash `44229085`）9 配置 × 5 seeds：每个配置均至少有一次成功，trace 在 `runs/muse-9maps-*`。原始 51 个 trace 包含 46 success + 5 `provider_error`，所有实际尝试成功率为 46/51（90.2%）；去重后 45 个配置为 45/45。均值步数：
  飞船 70.4/140.8/165.4、灯塔 39.8/49.4/105.8、深海 26.8/42.2/83.6——三图均值全部单调递增；
  中位数飞船 42/147/100（困难反低于中等，方差所致）。单局步数只反映迷路发作程度，不反映难度。

### J. 七个新世界与 30 局全覆盖（2026-10-11，done）

- [x] 新增极地科考站/沙漠金字塔/废弃地铁/火山观测站/丛林遗迹/月球基地/古堡
  7 个世界，各分简单 6 房/中等 8 房/困难 10 房，共 21 张新图（spec 0011）。
- [x] 规则零改动：同六工具、同谜题链、同 Action schema；旧 9 图一字节未动。
- [x] 非纯换皮：每张图独立拓扑（环形捷径/菱形双通道/干线侧线/起点工具/
  必经工具间/三角回路/狱后藏宝）、独立读码点与诱饵位置，最优公开路径
  11–22 步：极地 11/19/21、金字塔 11/15/17、地铁 13/15/21、火山 13/19/17、
  丛林 13/20/22、月球 12/14/16、古堡 13/19/21。
- [x] 7 个新测试文件共 56 项（房间数/双向出口/selector/精确步数通关/
  终端规则/诱饵/维修顺序）；全套 249 passed。
- [x] `create_environment` 新增 21 对 selector；真实模型新图 benchmark 另行安排。
- [x] 真实模型 benchmark（2026-10-11，Muse 自主组合 memory + history5 + recovery
  + world-declared phase + E1-ON（hash `44229085`），不限步）：21 配置 × 5 seeds = **105/105 配置均有成功 trace**，trace 在
  `runs/muse-21maps-*`（本地生成物）。均值步数：极地 20.4/38.2/41.8、
  金字塔 20.6/27.4/38.4、地铁 21.6/33.8/43.6、火山 21.2/35.4/31.4、
  丛林 24.8/35.6/49.8、月球 22.2/30.2/45.6、古堡 24.8/38.6/63.4——
  除火山困难图均值（31.4）低于中等图（35.4）外，其余六图均值随难度单调递增；保留实测数值，不为满足单调性改写数据。非法输出总共 1 次。
  首波 105 并发触发网关系统性限流（104 局开局中断），降到 21 并发池重跑后
  101/105，再补 4 局偶发中断后全通；全部尝试 trace 均保留。
- [x] 30 图 × 5 seeds 合并验证（2026-10-11，离线零新调用）：旧 9 图与新 21 图
  的 E1-ON（hash `44229085`）配置使用相同 memory + history5 + recovery +
  world-declared phase + 不限步 + `muse-spark` 和 seeds（0–4）；逐局 trace 核对后
  150 个配置均有成功 trace。该完成口径包含网关失败后的补跑，不代表首次尝试 150/150 成功。
  旧 9 图均值：飞船 70.4/140.8/165.4、灯塔 39.8/49.4/105.8、
  深海 26.8/42.2/83.6（见 §I）。

### K. 任务结构 pilot 与 flex 引擎（2026-10-11，done；真实对照 35/35）

- [x] 新参数化规则引擎 `worlds/flex.py`：维修点列表（分支二选一/单点多件），
  读码电源要求可配，深诱饵纯文本 fixture；旧 30 图零改动，全套回归通过。
- [x] 3 张 pilot 图（均为 8 房）：月球 v2 分支（`LUNAR-220`，短支 19）、
  古堡 v2 并行三件套（`CROWN-250`，22 步，中间件报 `CELL_STAGED`）、
  金字塔 v2 先读码（`SAND-260`，16 步）；各带 1 个深诱饵。
- [x] 3 张 seeded 版（工具双容器按 seed 分配，确定性/差异性/可解性测试通过）。
- [x] 共享加法：`ToolReason.CELL_STAGED`（旧 trace 可读，旧逻辑不受影响）；
  另修复 `_escape` 不查电源的旧假设 bug。
- [x] 22 项新测试，全套 271 passed；真实模型 pilot/seeded 结果沿用 E1-ON prompt hash `44229085`，按配置报告并保留重跑与长尾记录（spec 0012、V1-08）。

### L. 旧三世界重制图（2026-10-11，done；10×3 矩阵 150/150 配置完成）

- [x] 边集审计证实旧 9 图同拓扑家族换皮；旧图冻结保留，新 9 张版本进矩阵。
- [x] 飞船：纯长链（20 步）/双容器分置（22 步）/纵深双容器（24 步）；
  灯塔：死胡同电台+分叉（13 步）/塔顶读码（21 步）/长链双诱饵对（19 步）；
  深海：起点捷径（12 步）/起点旁逃生（16 步）/环路深码（17 步）。
- [x] 规则零改动（复用三引擎与同名物件 id）；22 项新测试，全套 293 passed。
- [x] 新 10×3 矩阵 = 9 重制 × 5 seeds 新跑 + 21 图 105/105 沿用（spec 0013）。
- [x] 重制 9 图真实模型配置均有成功 trace（2026-10-11，Muse + E1-ON prompt hash `44229085`，不限步）：
  飞船 31.6/38.4/44.4、灯塔 24.2/41.2/51.2、深海 24.2/33.4/34.4，
  三图均值全部随难度单调递增，非法输出 0；trace 在 `runs/muse-redesign-*`。
  第一波 42/45，light-med s0/s2 与 abyss-med s2 网关中断，第二波补齐。
- [x] 新 10×3 合并 150/150：9 重制 45/45（新跑）+ 21 图 105/105（同条件沿用），
  旧 9 图 45/45 封存为历史基线。

## Release 3

### 8. Streamlit 实验界面 · planned

提供世界状态、执行 trace 和指标的可视化，让单局行为和 benchmark 结果容易检查。

Done when: 可以选择 Agent 和世界，运行 episode，并查看每一步的决策与结果。

已提供研究 V1 只读 MVP：单局回放、矩阵总览、错误热点、条件对照。运行方式为 `uv run --with streamlit streamlit run src/agent_arena/ui/app.py`；该版本不配置模型或启动实验，Release 3 的完整交互验收仍未完成。

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

十世界三十图矩阵及 9 张重制图已完成；flex pilot 与 seeded 共 45 局成功，详见 §K、§L 和 `docs/research/v1/08-cross-task-and-e1.md`。只读 Streamlit 研究回放 MVP 已提供，完整交互式实验界面仍属 Release 3。
当前研究缺口：扩大 seeded 实例覆盖并分析长尾步数；新在线实验仍需先登记预算与固定对照条件，避免重跑已有矩阵。

## V1 研究提纲执行状态（2026-10-11，S0–S1 完成，S2–S6 部分）

- S0/T1 partial：CI 红灯根因（`test_phase_tracker.py` 未使用导入）已修，本地 159→173 passed；51→45 去重台账与 provenance 审计见 `docs/research/v1/00-audit-and-run-register.md`、`01-ci-and-provenance.md`。CI 全绿待 push 后确认（本机无 uv/ruff/mypy）。
- S1/T2 done（离线）：9 配置统计复核通过，`Success@K` 离线裁剪（K=60:60%、K=100:80%）与 TOP3 瓶颈见 `docs/research/v1/02-offline-metrics.md` + `assets/success_at_k.csv`。0 次新 LLM 调用。
- S2–S6 在在线收官前的阶段快照：T3–T5 的设计与结果见 `03`–`05`；T6 的泛化与 seed 审计见 `06-generalization.md` 和后续补记 `08-cross-task-and-e1.md`；T7 Reflection deferred、UI 只读 MVP 见 `07-reflection-and-ui.md`；历史任务总表见 `SUMMARY.md`。
- 在线收官前曾有补测 blocked；后续完成状态以紧接的“V1 在线收官状态”和“08 跨任务与 E1 新世界验证”为准。

## V1 在线收官状态（2026-10-11 晚，用户批准在线后全部完成）

- T3 done：八格 8/8（C010/C011 新跑 0/5）；React-C111 0/4（seed4 censored）。
  结论：H 必要、M 增益（FORGOTTEN_FACT 双分离）、R 仅放大器。
- T4 done：E1 单变量 5/5（均值 30.6，零误用）vs C111 3/5（均值 47.2），配对全优，保留；
  E2/E3 隔离 deferred。
- T5 done：Planning 同上下文 0/4（seed4 censored），更差且 2 倍 token，不提议 v2。
- T6 partial：seeded-v5 生成器 + oracle + 真实 3/3 后，完成 flex 跨任务 pilot 30/30、seeded 变体 15/15；扩展实例覆盖与长尾分析仍待做，见 `08-cross-task-and-e1.md`。

- T7 partial：Reflection deferred；只读 UI 已扩为 4 视图并通过真实数据冒烟，完整交互式实验界面仍待 Release 3。
- 中断总账：C011-seed1 provider_error→重跑失败；React-seed4 2×provider_error→censored；
  Pctx-seed4 2×基础设施中断 + 首步 provider_error→censored。全部单列，未并入分母。
- 另：并行会话新增 7 世界 21 图（spec 0011），兼容共存（249 passed）；本轮结论范围仍为原三世界。

## V2 探索进度（2026-10-13）

- [x] S0 本地质量门禁：Python 3.13.16 / uv 0.13.0 临时环境下 `ruff check`、`mypy src`（48 个源文件）、`pytest -q`（303 passed）、`uv lock --check`（36 个 packages）和 `git diff --check` 通过；测试不再依赖本机 runs/ 与 results/。详见 [V2-01 CI 与基线](../research/v2/01-ci-and-baseline.md)。
- [x] S0 GitHub Actions Gate：d40f3e6 的 [run #56](https://github.com/wenxvn/Agent-Arena/actions/runs/38358490666) 与后续跨平台 `mypy` 修复提交 `4ec5bb1` 的 [run #67](https://github.com/wenxvn/Agent-Arena/actions/runs/38376965970) quality job 全部通过；Linux-only `msvcrt` typing 错误已修复。
- [x] S1 既有 Trace 离线瓶颈审计：扫描 518 个文件，去重后 474 个 episode_id；44 个副本、0 个 ID 冲突、0 个非法 Trace。脚本、Top 5 假设及分层结果见 [V2-02 离线瓶颈审计](../research/v2/02-bottleneck-audit.md) 与 [CSV](../research/v2/assets/trace-audit.csv)、[JSON](../research/v2/assets/trace-audit.json)。审计代码提交 a372dce 的 [run #57](https://github.com/wenxvn/Agent-Arena/actions/runs/38360270607) 全绿；无新增模型调用或 GPU 运行。
- [~] S2 Memory v3：M1 空间边、frontier、公开事件记忆的可选 v3 实现与离线验证已完成；默认 v2 保持。新增规范化 `memory_digest`，并对落盘后重新读取的完整 10 步公开 Trace 做双次回放，digest、frontier 和因果事件顺序一致。trace statistics 经两轮容量/字段复核，已覆盖 v3 房间、初始/新增事实、失败动作、问题、揭示物品、出口、成功边、事件，以及 current-room/inventory/里程碑/question/event 更新；v2 `visited_locations` 不重复计数。当前 Python 3.13.3 全量 pytest 350 passed、Ruff/mypy 通过；提交 `a336bd68768f32a35e5c6a906b60045571b63669` 的 [Actions run #74](https://github.com/wenxvn/Agent-Arena/actions/runs/38379921434) 通过。该环境没有 `uv` 命令，未执行 `uv lock --check`，依赖文件未改动。fail-closed provider budget guard 与 world identity 稳定性修复已验证；三次隔离尝试均在 v2 首个 episode 中因 provider error fail closed：BUDGET-01 2 次/24,086 tokens unknown-spend，BUDGET-02 10 次/40,852 tokens timeout，BUDGET-03 7 次/35,199 tokens generic provider_error。合计 19/500 requests、100,137/4,000,000 本地记账 tokens；三笔不确定 reservation 不代表 provider 实际 usage。三份 ledger 与 partial 输出保留，当前登记矩阵不再发送 API 请求，v2 为 0/2 完成且 v3 未启动。S2 Gate 未完成，不推进 S3。详见 [V2-03](../research/v2/03-memory-v3.md)、[运行登记表](../research/v2/00-run-registry.md)、spec [0014](../specs/0014-memory-v3-spatial-event/index.md) 与 [0015](../specs/0015-v2-provider-budget-guard/index.md)。
