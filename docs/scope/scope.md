# Agent Arena Scope

**Product:** 一个用于学习和比较 LLM Agent 行为的轻量实验环境。
**Build approach:** Skateboard，先交付一个从环境到结果完整可用的最小版本，再逐步增加 Agent 能力。
**Workflow:** Medium，开发后运行验证和测试，保证环境规则与实验指标可信。
**Source:** `研究总纲.md`（日常摘要），完整参考为 `总纲.md`

## At a glance

按时间顺序；正文的 `### N.` 是历史条目编号，不再与下表一一对应。

| 内容 | 阶段 | 状态 |
|---|---|---|
| Python 项目骨架与命令入口 | Foundation | done |
| Spaceship Escape 环境 / 规则测试 / ReactAgent 与 Agent Loop / Episode Trace 与终止控制 | Release 1 | done |
| MemoryAgent / Benchmark 与指标 | Release 2 | done |
| 只读 Streamlit 研究回放（研究 V1） | Release 3 | done |
| 可操作本地网页平台 | Release 3 / V11 | done（`WEB_PREVIEW_READY`） |
| Lab 多架构实验层 | Release 4 / V12 | done（`LAB_1_0_READY`） |
| PlanningAgent v1 | Research Core | done（真实对照 0/5，未证明） |
| Planning v1 Failure Analysis & Evaluation v2 | Research Core | done |
| ReflectionAgent | Deferred → V12 | 已实现 `reflection.v1`；真实对照"触发器未激活" |
| 雾岛灯塔第二世界与迁移对照 | Research Core | done |
| 飞船扩建 v3 与不限步数 | Research Core | done |
| 三图难度对齐：灯塔 v2 与深海站 v1 | Research Core | done |
| 三档难度：简单/中等/困难 9 图 | Research Core | done |
| 七个新世界：十世界三十图 | Research Core | done |
| 任务结构 pilot：分支/并行/反转 + seeded（flex 引擎） | Research Core | done |
| 旧三世界重制图：去换皮，新 10×3 矩阵 | Research Core | done |
| V3 主题世界：10 家族 × 3 难度 × 30 手工关卡 | Research Core | done（离线） |
| V5 六图运行时与能力测量 | Research Core | **superseded**（由 V6–V10 覆盖） |
| V6 能力测量效度修复 | Research Core | done（`HOLD` 结论保留） |
| V7 30 图分层能力指标离线层 | Research Core | done（离线层） |
| V8 30 图定稿与 MiMo 三重复验收 | Research Core | done（17/90） |
| V9 30 图难度定标与失败归因 | Research Core | done（7 VALIDATED） |
| V10 30 图核心机制重构与多 Seed 验证 | Research Core | done（30 VALIDATED） |
| V13 Lab 1.1 深化：重复稳定性 / 可比性 / 消融 / 效度 / 归因 / 画像 / 报告 / 审计 | Release 4 / V13 | done（`LAB_1_1_ENGINEERING_READY`；LIVE `WAITING_USER_APPROVAL`） |

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

A 至 E 保留早期交付清单与当时待办；当前阶段以本文 V2 门禁总览、V3 状态及“当前下一步”为准，不据此直接启动旧实验建议。

下面的清单把“已经能通关”与“还没有证明”的问题分开。`planner_assisted` 的成功只能证明真实本地模型能在公开规划建议下执行一条合法路线，不能代表模型已经具备纯自主规划能力。

### 0. V6 能力测量效度（离线段已完成）

- [x] V5 六图失败审计（基于本机原始 trace）：定位 MAP-22 的接口契约缺陷（非记忆条件仍宣传 `write_memory`，173 次 `ACTION_NOT_AVAILABLE`；`return_to_camp` 只设目标）。
- [x] 参数化 V4 引擎（向后兼容，默认行为不变，DCR-002…006）并建立 24 个独立 V6 实例与三层难度。
- [x] 独立求解器 + Oracle 回放 40/40 成功；MAP-16/22 由 BFS 证明最优；泄漏检查 0 命中。
- [x] 可选真实 API 复测方案（`docs/v6/api-experiment-proposal.md`）与 24 图门槛（`docs/v6/next-24-gate.md`，结论 `HOLD`）。
- [x] 补齐任务书点名缺口：MAP-18 三闭塞段、MAP-26 三失败前缀、MAP-30 纯召回变体、每实例 3 条边界；实例 24 → 29。
- [x] 真实 API 复测 47 局（MiMo，CNY ¥0.29230284，17/47）：**MAP-22 L3 记忆消融与 MAP-30 召回出现条件差异**；另有多图天花板/地板，见 `docs/v6/pilot-report.md`。
- [ ] 人工审阅 V6 实例（`review_status` 待填）。
- [ ] 对已出现差异的配对增加重复次数；下一次付费矩阵需新预算登记。

细节见 `docs/specs/0019-v6-measurement-validity.md` 与 `docs/v6/`。

### 0.1 V7 30 图分层能力指标（离线层已完成）

- [x] 30 张逐图指标卡：每图独立构念、≥1 核心连续指标、≥1 安全/约束指标、≥1 失败归因、≥1 成本指标，附手算样例、反例与边界。
- [x] 只读注册表 `src/agent_arena/v7/metrics/`：154 条 `MetricSpec`，6 图 44 条 implemented + 24 图 110 条 design-only；缺失五态，design-only 调用抛 `NotImplementedError`。
- [x] 六图 extractor 与 29 个 V6 实例离线回放：全部成功复算，无 `invalid_trace` / `unavailable`。
- [x] 六图 36 条真实环境手算轨迹（每图 6 条，覆盖成功/失败/边界/截尾/N/A）与 154 条 `MetricSpec.valid_range`。
- [x] 验收脚本、报告脚本、结构自审脚本、泄漏扫描脚本、90 项 V7 测试、难度向量、实验协议、人工复核清单与 DCR 登记。
- [x] 人工复核 30 卡：2026-10-17 用户确认，全部记录为 `human_approved`。
- [x] `V7-DCR-001 … 012` 已逐条复核登记；规则变更仍保留为对应地图运行时接入前的准入项，未私改 V4 规则。
- [ ] 24 图运行时接入（逐图阻塞项见 `docs/v7/pending-runtime/MAP-XX.md` 与总表 `README.md`）。
- [x] V7 六图 12 局 pilot-001：已预登记并执行；10 局启动、9 局完整、1 局因 `unknown_provider_spend` 中断，账本已关闭；见 `docs/v7/pilot-001-report.md`。
- [x] V7 Pilot-001R 完整重跑：同一 12 局矩阵在独立新账本上 12/12 完整结束，109 请求、CNY `0.08521648`、0 中断；见 `docs/v7/pilot-001r-report.md`。
- [ ] 真实模型 V7 主实验（30 图或六图多 seed 矩阵）：未运行；已有 V6 MiMo 47 局 trace 的 post-hoc 复算、9 局中断 pilot 和 12/12 完整重跑，但均为单 seed、每条件 1 局，不构成主实验。

细节见 `docs/v7/validation-report.md` 与 `docs/v7/maps/`。

### A. 原计划尚未完成

- [ ] **Streamlit 实验界面**：选择 provider、模型、Agent、world 和 seed，启动单局或 benchmark，并查看逐步 Observation、Action、ToolResult、trace 和聚合指标。
  - 验收：UI 明确显示 Agent 类型和辅助来源；不能把 `planner_assisted` 标成纯 ReactAgent/MemoryAgent；失败、超步数和非法输出都有可见状态。
- [x] **PlanningAgent v1**：实现高层子目标规划和事件触发阶段切换，规划本身不直接调用环境、不绕过 Action schema。
  - 工程验收：规划版本、阶段变化和实际 Action 可复盘；Fake provider 5 seeds smoke benchmark 已通过。
  - 研究对照已完成：qwen 与 Muse 基线均为 0/5；工程完成不代表研究有效，见 spec 0006 与 V1 失败分析。
- [ ] **ReflectionAgent**：只在明确触发条件下根据失败或循环进行反思和重规划。
  - 验收：反思触发次数、输入摘要和后续动作可追踪；证明它减少失败或重复动作，而不是只增加 token。
- [ ] **多世界、多模型对照**：至少加入第二个 world version 和第二种模型规模，避免结论只适用于单一地图和 `qwen2.5:7b`。
  - 验收：固定实验矩阵、统一指标和可重放 trace。

### B. 纯模型自主通关验收（2026-10-11 已通过，Muse 45/45）

这项任务必须证明模型在不依赖 Spaceship Escape 谜题攻略式提示、不使用 `planner_assisted` 或 `guarded` 引导的情况下，仅根据公开 Observation、历史和环境反馈完成任务。当前 ReactAgent、MemoryAgent 和 PlanningAgent 均有实现与 Fake provider 对照测试；真实 Ollama 对照已覆盖 React、Memory、Planning，当时未取得可重复的纯模型成功；后续 Muse 自主组合结果见本节后续记录及 §H、§I。

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
V3 30 个 Scenario 的离线实现与验收已完成，见第 19 项；真实模型对照仍须独立设计和登记。
V4 的 30 张地图已完成逐图设计与离线固定轨迹审计，当前均为 `DESIGN_COMPLETE_PENDING_RUNTIME`；运行时工作在第 20 项，不能从设计或Oracle推出模型能力结论。
V7 只读指标层已完成离线交付（6 图 44 条 + 24 图 110 条，六图各 6 条手算 fixture），30 卡已由用户复核记录为 `human_approved`；六图 12 局 pilot-001 因 `unknown_provider_spend` 在 9 局完整后停止，随后在独立新账本上完成 Pilot-001R 12/12 重跑（CNY `0.08521648`）。两者仍是单 seed、每条件 1 局的 E3-pilot，不能当作主实验。下一步是 24 图运行时接入与 DCR 规则决策，不能把设计态指标、求解器回放、V6 trace 的 post-hoc 复算或两次 pilot 当作新的 V7 模型能力结论。
当前研究缺口：seeded v3 的 90/30 布局全集和程序性 dev/test holdout 已冻结，两个运行时 selector 与 120 个实例 hash 全匹配；模型行为评估待 S2 matched-pilot Gate，通过前不能启动在线矩阵。

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

### S0–S6 阶段门禁总览

| 阶段 | 当前状态 | 证据与后续放行条件 |
|---|---|---|
| S0 质量门禁 | 完成 | 本机和 GitHub Actions 质量门禁通过；实现提交 `b301051` 的 Actions #93、文档同步提交 `59ab367` 的 #94、阶段总览提交 `fc490eb` 的 #95 均成功。 |
| S1 Trace 瓶颈审计 | 完成 | 518 个文件、474 个唯一 episode 的离线审计及逐家族案例复核已记录于 V2-02。 |
| S2 Memory v3 | 离线验收完成；研究 Gate 未通过 | spec 0014 离线验收已通过；BUDGET-01/02/03 分别以 unknown-spend、timeout、provider_error fail-closed，v2 为 0/2 完成、v3 未启动。登记表要求不创建 BUDGET-04、不再调用此矩阵；没有模型收益结论。 |
| S3 Action Grounding | 未启动，按序暂缓 | 当前没有完成的 S2 matched-pilot 结果；不得把离线 fixture 当作在线效果证据或据此启动 S3。 |
| S4 自主 Phase | 未启动，按序暂缓 | S3 尚未进入受控比较；保留 P0/P1/P2 的既有定义，不新增 Phase 实验。 |
| S5 跨任务/实例/模型验证 | 准备部分完成，行为验证暂缓 | S5.2 seeded v3 运行时和程序性 dev/test 拆分已冻结并通过身份回归；只对 S2/S3/S4 正向 Gate 候选开放行为评估或新任务。仓库可见的 test placements 不是盲测集。 |
| S6 研究收官 | 未启动 | 待 S2–S5 可报告的受控证据、失败/反例及跨条件审计齐备后再综合，不用离线实现完成替代研究收官。 |

阶段状态遵循 V2 探索提纲的 S0→S6 依赖顺序，并以 [S2 运行登记表](../research/v2/00-run-registry.md)、[Memory v3 报告](../research/v2/03-memory-v3.md) 和 spec 0014 为当前可追溯依据；停止边界优先于后续阶段排期。

- [x] S0 本地质量门禁：Python 3.13.16 / uv 0.13.0 临时环境下 `ruff check`、`mypy src`（48 个源文件）、`pytest -q`（303 passed）、`uv lock --check`（36 个 packages）和 `git diff --check` 通过；测试不再依赖本机 runs/ 与 results/。详见 [V2-01 CI 与基线](../research/v2/01-ci-and-baseline.md)。
- [x] S0 GitHub Actions Gate：d40f3e6 的 [run #56](https://github.com/wenxvn/Agent-Arena/actions/runs/38358490666) 与后续跨平台 `mypy` 修复提交 `4ec5bb1` 的 [run #67](https://github.com/wenxvn/Agent-Arena/actions/runs/38376965970) quality job 全部通过；Linux-only `msvcrt` typing 错误已修复。
- [x] S1 既有 Trace 离线瓶颈审计：扫描 518 个文件，去重后 474 个 episode_id；44 个副本、0 个 ID 冲突、0 个非法 Trace。脚本、Top 5 假设及分层结果见 [V2-02 离线瓶颈审计](../research/v2/02-bottleneck-audit.md) 与 [CSV](../research/v2/assets/trace-audit.csv)、[JSON](../research/v2/assets/trace-audit.json)。审计代码提交 a372dce 的 [run #57](https://github.com/wenxvn/Agent-Arena/actions/runs/38360270607) 全绿；无新增模型调用或 GPU 运行。
- [x] S1.3 可计算分布补充：按 experiment bucket、world version、configuration signature 汇总 92 个条件的成功动作数/token/延迟分位数、progress、失败计数与公开事件间隔；共 474 条记录、262 条成功。结合 spec 0011–0013 的路径参考和精确 map identity，再匹配 227 条成功 trace，产出 50 个条件的 `actions / spec_reference_min` 与超出动作数分布；其余 35 条成功 trace 因缺少精确参考 hash 不计算。旧 Trace 未记录环境规则代码 SHA，参考比值不作为历史规则实现的独立证明。数据与命令见 [V2-02](../research/v2/02-bottleneck-audit.md)、[条件分布](../research/v2/assets/condition-distributions.csv)及[最短路径匹配明细](../research/v2/assets/oracle-optimality-traces.csv)。仅离线复算，无 provider 调用或 GPU。
- [x] S1.4 逐世界家族 Trace 案例复核：从 10 个家族中索引最短已记录成功、长尾成功，以及行为非成功或 provider-error 删失样本，共 31 条；核对事件 step、公开 Observation/Action/ToolResult 与循环代理，并区分行为非成功和基础设施删失。该复核不把跨难度/版本样本作为对照，也不把成功长尾称为失败。474 条旧 Trace 均无 `memory_statistics`，且阶段开关不是模型阶段判断记录；事实遗忘和自主 Phase 根因仍不可由旧 Trace 证明。详见 [V2-02](../research/v2/02-bottleneck-audit.md) 与[案例索引](../research/v2/assets/trace-case-review.csv)。无新模型调用或 GPU 运行。
- [~] S5.2 seeded 长尾与实例泛化准备：10 条旧成功 Trace（lunar/pyramid 各 5 seed）布局逐局匹配；232/159 步长尾当前规则 BFS 最短为 22/16，移动动作差值 +122/+96，工具房回访 40/28，重复 look 41/32，阶段拒绝 1/0，重复失败重试 0/0。v2 seed 0–999 每图仅 2 种布局/hash（497/503），旧定义保留。spec 0016 的 v3 运行时包含 90/30 个唯一布局，当前规则下均可解；地图内 oracle simple/complex 阈值已预注册，冻结 split 为 lunar 60/30、pyramid 20/10。运行时 hash、placement、inactive-container 可见性和 seed 周期在 `PYTHONHASHSEED=1/42` 下与清单 120/120 匹配；回归测试锁定规范化清单 SHA、oracle 路线长度分布和每个难度桶的 split 数量，生成脚本拒绝覆盖冻结 CSV。全量 pytest 364 passed、Ruff 全仓和 mypy 49 个源文件通过；早期运行时回归提交 `b3010512023323609196412f2a4915fa738ded4a` 的 [Actions #93](https://github.com/wenxvn/Agent-Arena/actions/runs/38399647555) 及后续清单完整性回归提交 `f1d45ba87332172ac5737c8e1dfcddbae8a0d035` 的 [Actions #98](https://github.com/wenxvn/Agent-Arena/actions/runs/38402688442) 均通过。清单 placement 在仓库可见，属于程序性而非盲测 holdout；不得用 test 调 prompt 或机制。S5.2 模型行为评估仍待 S2 Gate。旧 Trace 缺环境规则 SHA，旧 v2 最短值只对应当前检出规则。详见 [V2-02 S5.2](../research/v2/02-bottleneck-audit.md)、[逐局 CSV](../research/v2/assets/seeded-overhead.csv)、[布局覆盖 CSV](../research/v2/assets/seeded-layout-coverage.csv) 与 [v3 冻结清单](../research/v2/assets/seeded-v3-layout-freeze.csv)。无 provider 调用或 GPU 运行。
- [x] V2 基线文档口径复核：README 与 Scope 的 45/45、46/51 尝试率、150/150 配置覆盖和 E1-ON 条件相符；Scope 明确保留火山困难均值低于中等的例外，README 未将其概括为七图全单调。README 中“预算门禁尚未实现”已依据 spec 0015 与运行登记表更正为门禁已实现、三次 pilot fail-closed、S2 Gate 未通过。未增加实验调用。
- [~] S2 Memory v3：M1 空间边、frontier、公开事件记忆的可选 v3 实现与离线验证已完成；默认 v2 保持。新增规范化 `memory_digest`，并对落盘后重新读取的完整 10 步公开 Trace 做双次回放，digest、frontier 和因果事件顺序一致。trace statistics 经两轮容量/字段复核，已覆盖 v3 房间、初始/新增事实、失败动作、问题、揭示物品、出口、成功边、事件，以及 current-room/inventory/里程碑/question/event 更新；v2 `visited_locations` 不重复计数。此前提交 a336bd6 时，Python 3.13.3 全量 pytest 350 passed、Ruff/mypy 通过；提交 `a336bd68768f32a35e5c6a906b60045571b63669` 的 [Actions run #74](https://github.com/wenxvn/Agent-Arena/actions/runs/38379921434) 通过。该环境没有 `uv` 命令，未执行 `uv lock --check`，依赖文件未改动。fail-closed provider budget guard 与 world identity 稳定性修复已验证；三次隔离尝试均在 v2 首个 episode 中因 provider error fail closed：BUDGET-01 为 2 次（1,509 usage + 22,577 reservation = 24,086 本地记账 tokens，unknown-spend），BUDGET-02 为 10 次（15,374 usage + 25,478 reservation = 40,852 本地记账 tokens，timeout），BUDGET-03 为 7 次（10,043 usage + 25,156 reservation = 35,199 本地记账 tokens，provider_error）。合计 19/500 requests、26,926 confirmed usage + 73,211 reservation = 100,137/4,000,000 本地记账 tokens；三笔 reservation 的 provider 实际扣费未知。三份 ledger 与 partial 输出保留，当前登记矩阵不再发送 API 请求，v2 为 0/2 完成且 v3 未启动。S2 Gate 未完成，不推进 S3。详见 [V2-03](../research/v2/03-memory-v3.md)、[运行登记表](../research/v2/00-run-registry.md)、spec [0014](../specs/0014-memory-v3-spatial-event/index.md) 与 [0015](../specs/0015-v2-provider-budget-guard/index.md)。
- [x] S2 末轮只读失败诊断：逐条核对三份 ledger 的计数、状态、错误分类与本地耗时；BUDGET-03 的 120 秒环境覆盖已通过配置前缀和 adapter 传参核实，失败事件约 10 秒且为无 HTTP status 的 `provider_error`。现有安全记录无法区分无输出响应与未分类 SDK/网关异常；BUDGET-01 约 30 秒但 schema 1 无类别，不能追溯定性。没有额外 provider 请求或 GPU 运行，不创建 BUDGET-04、不推进 S3。详见 [V2-03 末轮诊断](../research/v2/03-memory-v3.md) 与[运行登记表](../research/v2/00-run-registry.md)。
- [x] S2.4 离线负例与公开事实更正：新增非法 provider 候选/correction request、回程导航、单向出口、重复事件摘要、同房间 Observation 更正及 room-fact 压缩保留当前描述用例；普通 facts 压缩精确断言删 8/24、留 16/24，20 条失败动作仍保留；默认 v2 provider memory-data 有 golden fixture，legacy Trace 缺少 `memory_statistics` 时仍可读取。全量 pytest 357 passed、Ruff 和 mypy 49 个源文件通过，`git diff --check` 通过。此前实现/fixture 提交的 Actions #76/#78 均通过，本轮 fixture 提交 `29d6917c8f2825b175735f92443d1692b14e843d` 的 [Actions #81](https://github.com/wenxvn/Agent-Arena/actions/runs/38383303143) 通过。S2 Gate 仍未通过，不推进 S3；无 provider 请求。

## 19. V3 主题世界设计与实现 · done（2026-10-14）

V3 按 [spec 0017](../specs/0017-world-redesign-v3/index.md) 推进，内容来源为仓库根目录 `研究提纲/V3世界设计提纲.md`。新增独立 Scenario Action/Observation 与 selector，分十家族逐关实现，不改 Legacy 世界或冻结的 V2 seeded 定义。当前只做离线工程，不复用 V2 provider ledger、holdout 或真实模型预算。

- [x] Gate 0：固定基线 `main@e23fca0ac2b7cf339c6f16dc21872ea456d45a54` 与 V2 seeded 文件边界；完成 30 个 scenario ID、设计卡、地图/初值/路线与机制的静态核对。依赖文件未修改；当前环境无 `uv`，未执行 lock 专项命令。
- [x] Gate 1：Scenario 契约；PY-E/M/H、SU-E/M、AB-E/M 纵向原型完成，规则负例和公开 Oracle 纳入测试。
- [x] Gate 2：其余七家族 easy 关卡通过逐关 Oracle 与边界检查。
- [x] Gate 3：其余七家族 medium 关卡通过逐关 Oracle 与边界检查。
- [x] Gate 4：十个 hard 关卡通过公开状态驱动路线回放；每条路线限制 100 个动作，动态/谜题/资源/调度边界另有规则用例。路线见证不等于穷举搜索或最短解证明。
- [x] Gate 5：30/30 Oracle、六维评分、机制差异、Legacy 与 Trace 兼容、完整文档和基础质量门禁完成。详细 hash 与重播证据见 [`oracle-acceptance.md`](../world-design-v3/oracle-acceptance.md)。

最终验证：全量 pytest、Ruff、mypy 和 `git diff --check` 的准确结果追加在 `docs/engineering-log.md`。项目虚拟环境 Python 3.13 可用；当前 shell 没有 `uv`，`uv lock --check` 未运行且依赖文件未改。未进行真实 Provider 请求、GPU 训练或模型行为对照；离线 Oracle 不构成模型能力证据。
### 20. V5 六图运行时与能力测量 · superseded（由 V6–V10 覆盖）

先将MAP-08、16、18、22、26、30接入隔离的`scenario_v4`运行时，再根据结果说明其余24图的接入条件。
**Done when:** 六图逐关离线验收、V3/Legacy回归和成本受限的模型试验完成；环境、模型通关与能力效度分开报告。
- [x] 设计运行时契约与实施计划（spec）：[0018](../specs/0018-v5-six-map-measurement.md)
- [ ] Build it: `/develop V5 六图运行时与能力测量`
  - [x] 实现隔离的 V4 契约、六图运行时、公开视图与裁判状态，覆盖 AC-1 至 AC-5
  - [x] 实现 V5 episode、配对条件、Trace、指标、manifest 与恢复点，覆盖 AC-2、AC-7、AC-10
  - [x] 完成 Oracle 回放、失败机制、独立求解、泄漏和全项目回归，覆盖 AC-4 至 AC-6；此前实现和 39 局扩展矩阵均经第二模型只读复核为 Approve
  - [x] 实现 fail-closed MiMo pilot、预算账本与运行报告，覆盖 AC-7 至 AC-12
- [ ] Verify it: `/check verify V5 六图运行时与能力测量`
- [ ] Test it: `/test V5 六图运行时与能力测量`
Spec [0018](../specs/0018-v5-six-map-measurement.md)

真实模型阶段记录（2026-10-16）：冻结 offline gate 在 `e440cc1b599a5de4a57650f418d78b03c4746399` 通过。MiMo smoke 的 MAP-08 首局 70 次决策均为 `INVALID_ACTION_SCHEMA`，依研究提纲的系统接口失败停止；第 71 个请求 reservation 未结算，唯一 V5 ledger 因 unknown spend 关闭。0/39 episode 完成，六局 smoke gate 未通过，Stage C 未启动。停止后补全 prompt JSON 字段说明，加入连续 3 次 schema 拒绝即 fail-closed 的离线保护；封账后经用户授权的一次诊断显示 Action 缺少 `tool`、改用 `verb`。随后在 provider 边界加入同义动作键折叠（`verb` 等唯一同义键折叠为 `tool` 后再走严格校验，并在 trace 记录 `recovered_action_discriminator`），歧义/未知别名仍按非法处理；再按用户授权实时复测：3/3 首步请求 schema 合法，模型误读 `edge_id` 后补充 MAP-08 公开 Observation 编码说明，seed 0 单局 5 步通关（均为封账后诊断，不计入 39 局）。用户随后授权新建登记 pilot：归档旧 registry、在提交 `aae5088` 重新冻结 gate（`f0619e80…`），experiment `0d0685c8-…` 完成 **39/39 局**，15/39 成功，689 请求、0 unknown spend、报告费用 ¥0.24287288（逐图 3-seed：MAP-08 4/6、MAP-16 1/6、MAP-18 0/6、MAP-22 0/6、MAP-26 4/6、MAP-30 6/9）。全量 518 项测试与 scoped Ruff/mypy 通过。V5 仍为 in-progress：MAP-16/18/22 在当前条件下几乎无成功，须先修正测量设计；固定 scene 重复 seed 不构成模型排名或泛化结论。

### 21. V9 30 图难度定标、失败归因与能力区分度 · done（2026-10-17）

按根目录 `研究提纲/V9：30图难度定标、失败归因与能力区分度优化.md` 执行。V8 90 局、账本、冻结 hash 保持只读；V9 新增独立 `src/agent_arena/v9/`、`docs/v9/`、`runs/v9/` 与账本。

- [x] Batch 0：90/90 正式局可复算，header/runtime hash 30/30 一致，费用三口径（正式 ¥1.27464628 / 含补跑 ¥1.39004496 / 含作废预跑 ¥1.45502656）。
- [x] Batch 1–4：30/30 逐图审计、22 张 0/3 根因分类、3 张 3/3 旁路检查、10 世界三难度递进评估。
- [x] Batch 5：55/55 Oracle、600 次 `legal_random`（11 成功，仅 MAP-15/21）、30/30 公开启发式、120/120 独立指标复算。
- [x] Batch 6：10 张图的公开信息补充（05/07/08/09/10/11/12/16/25/26）与 9 图指标叠加；14 份 DCR，另有 MAP-25/26/27 专项候选；V8 规则零改动。
- [x] 状态矩阵：VALIDATED 7、NEEDS_MORE_EVIDENCE 8、NEEDS_REDESIGN 13、BLOCKED 2；未标记 `human_approved`。
- [x] 有界 MiMo V9：预登记 29 条记录，settled **¥0.34049884**，2 次 provider `InternalServerError` unknown spend；主账本与 supplement_001 按规则封账，剩余局在 supplement_002 完成。MAP-07/10/11/26 的前后对照改善（0→1 或 0/2→2/2），MAP-09 从 2 决策短路后移到 12 决策缺氧，MAP-12 `v9_fixed` 未完成。逐局与费用见 `docs/v9/mimo-results.md`，不构成主实验。
- [x] 验证：888 pytest passed、`ruff`/`mypy` scoped 通过、`git diff --check`；详见 `docs/v9/final-report.md`。

边界：V9 只证明“当前 30 图中 7 张可用于研究级测量”，其余 23 张仍是工程可运行或需要重构；0/3 不能直接解释为模型能力为零。真实 MiMo 是预登记的 E3-pilot，不用于排名或显著性断言。

### 22. V10 30 图核心机制重构、难度校准与多 Seed 有效性验证 · done（2026-10-19）

按根目录 `研究提纲/V10：30图核心机制重构、难度校准与多Seed有效性验证.md` 执行。V8/V9 文件、账本与 90 局 Trace 保持只读。

- [x] Batch 0–9：30/30 原生运行时（V8 回退 0）、154+172 指标、8 项 Gate、30 张逐图审计卡、状态矩阵与最终报告；全部结论 `agent_reviewed`。
- [x] 多 seed：30 图 × 144 seed 实例 0 违规、回放确定 30/30、seed 互异 30/30；公式级复算 30/30 图、1093 次检查 0 不一致。
- [x] MiMo：159 局记录（152 有效 + 7 中断保留）、成功 57/152；结算 `2.27994884` + 未知预留 `0.13312000` = `2.41306884`。
- [x] 重复运行：阶段 15 覆盖 MAP-01–12（36 对），成功率一致 32/36=0.8889、翻转 2 升/2 降；因全局请求上限停止，其余 18 图仍为单 replicate。
- [x] 公开信息缺陷：DCR-V10-24/25/28/38/39（动作类型、MAP-20 取值结构、整数区间、MAP-20/19 的 wait 语义）。
- [x] 验证：1157 pytest passed、`mypy src` 0 issues、`ruff check .` 通过、`freeze verify` 9/9 unchanged、CI 全绿。

边界：单模型、每图 3 seed、重复仅覆盖 12 图；不作跨模型排名或显著性断言。详见 `docs/v10/final-report.md`。

### 23. V11 网页平台与阶段性交付 · done（本地网页预览，2026-10-20）

按根目录 `研究提纲/V11：Agent-Arena 网页平台与阶段性交付.md` 执行。V10 规则、指标、Oracle、账本与历史 trace 保持只读。

- [x] Batch 0：HEAD `eb2f64a` 审计、UI/runner/catalog 盘点、基线 1157 pytest passed。
- [x] Batch 1–2：`web/RunService`、状态机、manifest/JSONL/result 持久化、取消、恢复、单局预算；30 图 catalog 与展示难度。
- [x] Batch 3：可操作 Streamlit 网页，离线 30/30 图可启动/回放/导出，473 步。
- [x] Batch 4：真实 MiMo 3 局（MAP-01/19/30），58 次已记录请求，结算 ¥0.04637556 + 未知预留 ¥0.073728 < ¥3。
- [x] Batch 5–6：指标五态/失败解释/JSON/CSV、README、quickstart、user-guide、configuration、一键自检、CI。
- [x] Batch 7：P1 全部落地；P2 可视化/成绩榜/启动脚本/截图完成，演示数据包 DEFERRED。
- [x] 验证：1240 pytest passed、mypy 0 issues、ruff clean、lock 0、freeze 9/9 unchanged、recompute 1093/1093、independent 0 violations。
- [x] 干净安装：Windows 无 `.env` 克隆 + `uv sync --extra web` + `web --check` 176.9s，7/7；Ubuntu CI success。
- [x] 结论：`WEB_PREVIEW_READY`（本地单机预览）；不是公网生产就绪。macOS 实机未验证。

详见 `docs/v11/final-report.md`、`docs/v11/release-checklist.md` 与 `docs/v11/safety-and-budget.md`。

### 24. V12 Agent Arena Lab 1.0（多架构实验、批量对照与行为诊断）· done（`LAB_1_0_READY`，2026-10-26）

按根目录 `研究提纲/V12Agent-Arena_V12_第二阶段完整执行提纲.md` 执行 Batch 0–13。V8/V9/V10 冻结规则、账本与历史 trace 保持只读；V11 单局服务层与网页保留。

- [x] Batch 0：HEAD `258eadc` 审计；发现并修复 V11 遗留的测试排序缺陷（`test_home_shows_per_map_run_history`）。
- [x] Batch 1–2：ADR（父 Experiment + 子 Run）、`v12-lab-1` 契约、`DecisionGateway`、`AgentRunnerV12`；30/30 图 SIMULATED 完整执行路径。
- [x] Batch 3：`basic.v1` / `memory.v1` / `planning.v1` + registry + 消融开关；`basic.v1` 与 V11 `execute_live` 在同一 Provider 下逐项一致。
- [x] Batch 4–5：矩阵/队列/父子状态/实验级预算/幂等/续跑；六类分母、配对比较、三种可比性判定、五种导出。
- [x] Batch 6–8：`reflection.v1`（公开触发器 + 限额）；18 类证据级诊断 + 轨迹 Diff；六图专属 view-model + 24 图通用回退。
- [x] Batch 9：三个 Lab 网页页面（配置/监控/结果），浏览器 E2E 走通配置→预检→离线提交→对照→导出。
- [x] Batch 10：`lab/sdk.py` + `examples/custom_agent/` + allowlist + 只读导入。
- [x] Batch 11：`scripts/verify_v12.py` 15/15；CI `lab-e2e`；8 张截图；三组 Demo 包；13 项稳健性测试。
- [x] Batch 12：真实 MiMo —— Pilot 6 局 + 主矩阵 54 局 + 四类衍生实验（补充 / 版本复跑 / 预算扩展 / 重复）+ 路线日志消融 + 三条开关消融，共 **20 个实验 / 159 局 / 5 641 请求 / ¥5.43680012**，未知消费 ¥0，未超 ¥6.00。
- [x] Batch 13：`docs/v12/` 完整文档、README/architecture/scope 更新。
- [x] 测量缺陷：DCR-V12-01（`facts` 契约）、02（`route_recall` 键名口径）、03（记忆序列过短）、04（长观测图的 token 瓶颈）、05（反思触发器未激活）。
- [x] 验证：1525 pytest passed、mypy 306 文件 0 issues、ruff clean、lock 0、freeze 9/9 unchanged、recompute 1093/1093、independent 0 violations、`verify_v11` 7/7、`verify_v12` 15/15。

边界：`LAB_1_0_READY` 指 P0+P1+P2 交付且真实矩阵已跑；**不表示任何架构更优**——同条件重复的结局翻转率为 22.2%（2 次观测 4/18）/ 25.0%（3 次观测 3/12）。未做项见 `docs/v12/gap-audit.md`；SIMULATED 成绩不代表模型能力；macOS/Ollama 未实测。详见 `docs/v12/final-report.md`、`docs/v12/mimo-results.md`、`docs/v12/ablations.md`。

### 25. V13 Agent Arena Lab 1.1（可信度、可比性与工程收尾）· done（`LAB_1_1_ENGINEERING_READY`，2026-10-26）

按根目录 `研究提纲/V13Agent-Arena_V13_第二阶段深化执行提纲.md` 执行 Batch 0–13。V8/V9/V10 冻结规则、账本与历史 trace 保持只读；V11 单局服务层与 V12 Lab 保留可用。**本轮没有新增真实付费请求**（0 局 / CNY 0）。

- [x] Batch 0：HEAD `32e2782` 审计；`pytest` 基线 **1525 passed**；V12 的 159 局 / 5 641 请求 / ¥5.43680012 / 翻转率 22.2% / 25.0% 逐项复现一致。
- [x] Batch 1：`v13-lab-1` 契约（只增字段）、`replicate_index`、`SamplingProvenance`、`ProtocolManifest`、14 维可比性画像、单变量检查、跨实验配对、跨版本硬拒绝。
- [x] Batch 2：`create_replicates`（同实验 N 次独立重复）、预检重复口径、`repeat_variability.csv/json/md`、按 seed 分块、UI 翻转率警示。
- [x] Batch 3–4：`memory.v2`（只累积被接受 move、`env_write`/`context_only`、三类瓶颈）、`planning.v2`（三模式 + TTL + 预算感知 + 逐请求成本）；v1 一字未改。
- [x] Batch 5：7 个单因子消融模板（全部 `single_switch_ok`）、MAP-16/18/22 三份证据包、版本比较与消融显式区分、负面结果保留。
- [x] Batch 6：`reflection.v2`（eligible/triggered/冷却/额度/误触发/恢复 + trigger-only）；SIMULATED 探针 `triggered=2`，零触发报 `NO_TREATMENT_EXPOSURE`。
- [x] Batch 7：MAP-30 三档预算阶梯（法庭被拒 1/4/2、截尾 8/5/7）+ 五类失败分型；六图构念效度标签（08/26 `CEILING`、16/18/22 `SUITABLE`、30 `CENSORED`）。
- [x] Batch 8：七层失败归因（接口/测量永不计入能力）+ 8 个正反例 fixture + 六维机制画像（缺失不补 0、`agent_reviewed`）。
- [x] Batch 9：Lab 扩到 5 页（新增「稳定性与效度」「报告与审计」）；`web/index.py` 懒加载 + 增量刷新 + 服务端分页。
- [x] Batch 10：零 LLM 模板报告（四级结论 + 逐数字锚点）、本地账本审计（159/159 配对、0 孤儿、0 重复结算）、脱敏账单对账接口。
- [x] Batch 11：SDK 8 项接入自检 + 异常隔离 + 旧 `act()` 签名兼容 + `docs/v13/sdk-guide.md`。
- [x] Batch 12：1 000 / 5 000 条合成历史压测（懒加载首页 18 ms / 31 ms；已建索引翻页 0.1 ms / 0.4 ms）；CI 加 `verify_v13` 步骤。
- [x] Batch 13：`docs/v13/` 全套（audit / protocol / progress / decisions / 三份 study / core-evidence / map-validity / map30 / taxonomy / capability / live-budget-proposal / data-and-cost-audit / performance / validation / gap / final / release-checklist / demo）。
- [x] 验证：**1638 pytest passed**、mypy 323 文件 0 issues、ruff clean、lock 0、freeze 9/9 unchanged、recompute 1093/1093、independent 0 violations、`verify_v11` 7/7、`verify_v12` 15/15、`verify_v13` 18/18、`e2e_lab` 通过、`e2e_web` 通过。

边界：`LAB_1_1_ENGINEERING_READY` 指 P0/P1/P2 工程交付完成；**真实模型效果仍是 `WAITING_USER_APPROVAL`**（V12 的 ¥6 已结束，余额不挪用）。CI 浏览器 E2E 仍非阻断（`NOT_VERIFIED`），Provider 后台账单对账为 `BLOCKED_EXTERNAL`。详见 `docs/v13/final-report.md` 与 `docs/v13/gap-audit.md`。
