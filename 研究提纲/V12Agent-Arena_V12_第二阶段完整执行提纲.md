# V12：Agent-Arena Lab 1.0 —— 第二阶段多架构 Agent 实验、批量对照与行为诊断完整执行提纲

> **交付给：DeepSeek V4.1 Flash（工程执行 Agent）**  
> **目标仓库：** https://github.com/wenxvn/Agent-Arena  
> **基准分支：** `main`，编写提纲时最近可核验 HEAD 为 `258eadc5039309859fc0385d61650e266e6ab488`（2026-10-22 北京时间）；**实际执行必须先重新检查 HEAD 和工作区**。  
> **阶段定义：** Phase 1（V11 本地网页交付）→ **Phase 2（V12 Agent Arena Lab 1.0）**  
> **总目标：** 让用户用**相同模型、相同地图、相同环境 seed 和明示的实验预算**，比较不同 Agent 架构的行为与结果，并得到可追溯的失败诊断、交互可视化与可导出的报告。  
> **工作原则：** 先离线、后真实；先契约、后界面；先事实、后解释；不修改冻结规则；所有阶段有明确 Gate；绝不以完成测试数量代替真实能力结论。

---

## 0. 给执行 Agent 的最高优先级指令

1. **这是一份可执行的完整第二阶段任务书，不是需求讨论。** 按 Batch 0→13 顺序实施；可在同一 Batch 内并行处理相互独立的任务。无需每做一项就向用户询问，但遇到下述阻塞情形应停在对应边界，记录真实状态。
2. **不要为了完成 V12 牺牲 V10/V11。** 保持现有 30 张地图规则、成功判据、Oracle、旧指标公式、V8/V9/V10 冻结 trace/账本原样不动；如新研究指标有必要改变，必须新增命名空间/版本，不得覆盖历史数据。
3. **除非用户另行明确批准付费实验预算，否则禁止发出真实付费模型请求。** 先用 Fake / scripted provider、录制的非敏感 fixture、公开启发式策略和离线测试完成可完成的工作。54 局矩阵是计划，不是默许消费。未获预算时标记 `LIVE_VALIDATION_PENDING_APPROVAL`，不可伪装为通过。
4. **允许修改 V12 自己新增的 schema、代码、页面和测试。** 默认不修改 V10 的冻结运行时；需要桥接旧 Agent 时，采用新的 Adapter，不直接移植旧世界的状态访问方式。
5. **不把 Oracle、启发式、人工规则保护或离线脚本当成真实模型自主能力。** 它们仅用于工程完整性、上限/基线或对照，页面、Trace 和报告必须醒目区分。
6. **真实模型的成功率不预设大小关系。** 不强制 Memory > Basic、Planning > Memory；即使三个 Agent 全部失败，也必须忠实保留结果并能完成分析。
7. **不要重建已存在的能力。** V11 已有 Streamlit UI、RunService、单实例锁、回放/导出/历史、单局费用门禁、30 图 catalog、截图和基本 E2E。优先扩展，避免平行实现第二套运行服务。
8. **工程质量优先于提交次数。** 一个功能至少配套契约测试、失败场景测试和适当的文档/截图；每个 Batch 完成后执行对应 Gate，记录实际输出；禁止凭空填充通过数。
9. **每次提交边界清晰。** Batch 结束形成可回退提交，并在 `docs/v12/progress.md` 登记已完成项、证据、风险和下一步。不要自行删除用户未提交的改动，不强推，不发布公网，不生成正式 Release/tag（需用户明确确认）。
10. **遇到冲突先判定事实。** 如当前仓库已有同类功能，以真实代码为准，做缺口分析，不重复造轮子；若新方案违背冻结约束，则退回架构层重新设计并在 ADR 记录取舍。

### 0.1 明确的非目标

- 不在 V12 建公网多租户、登录/权限管理、支付充值、云数据库、开放跨模型排行榜、分布式任务集群。
- 不在 V12 新增 30 张地图、不大规模重绘 30 张地图、不训练/微调模型，也不研究多 Agent 协作团队。
- 不自动修改 Prompt/Agent 策略并声称“训练提升”；Agent Gym 的自动优化循环属于未来阶段。
- 不对 3 seed 的小样本宣称统计显著性；不把 API 提供商故障计作模型认知失败。
- 不抓取或持久化模型完整思维链、原始带密钥请求/响应，不泄露隐藏真值。

---

## 1. 当前仓库与第二阶段切入点

### 1.1 执行前必须复核的事实

- `README.md`：Python 3.13 + uv；Streamlit 本地单机网页；10 世界 × 3 地图；本地离线演示和真实模型模式；回放与导出。
- `src/agent_arena/web/schemas.py`：V11 `RunConfig.agent` 默认 `v10_action_loop`；离线 `public_heuristic_policy`；运行状态和预算约束已有实现。
- `src/agent_arena/web/execution.py`：真实模式使用 V10 Observation/Action 契约、单个 DecisionProvider 循环、5 步历史窗口与独立预算；目前没有多架构可插拔统一运行能力。
- `src/agent_arena/agents/`、`src/agent_arena/planning/`：旧 React/Memory/Planning 架构和规划状态，但不能假定与 V10 原生地图契约直接兼容。
- `src/agent_arena/v10/` 与 `src/agent_arena/v10/runtime/`：30 张原生图与复算工具；历史冻结。
- `docs/v10/construct-validity.md`：工程 Gate 的 30/30 `VALIDATED` 与构念效度的 7 图 `VALIDATED`、23 图 `NEEDS_MORE_EVIDENCE` 是**不同口径**。
- `docs/v11/final-report.md`、`docs/v11/backlog.md`：V11 本地网页预览完成；macOS 实机、Ollama 实机、部分 Provider 错误实测和更完整的 a11y 测试尚有缺口。
- `docs/architecture.md`、`AGENTS.md`、`docs/scope/scope.md` 和 `研究总纲.md`：已有工程边界、研究习惯与历史决策。注意部分老文档可能滞后，以当前代码和 V11 最终报告优先。

### 1.2 第二阶段最终用户故事

1. 用户在网页选择 **MAP-22**、一个模型及 **Basic / Memory / Planning** 三种 Agent，选择固定 `seed=[0,1,2]` 与预算配置。
2. 系统在启动真实调用前展示 **实验矩阵、预计调用数、最大请求/token/费用门禁和风险说明**；用户可以离线预检。
3. 系统按队列执行，逐局记录运行状态、消耗、动作、公开观察和 Agent 架构事件；中断不会丢失已写入数据，也不会在刷新后重复计费。
4. 用户看到三种 Agent 的配对结果、成功/失败、成本、重复动作、关键机制指标，以及 **“差异发生在哪一步”** 的证据链。
5. 用户可回放单局、并排对照两个轨迹、阅读规则可证实的失败分析，导出**机器可读结果 + 可读实验报告**。
6. 第三方开发者可通过一个受控 Python Adapter 接入自己的 Agent，再利用同一运行、预算、指标和回放链路测试。

### 1.3 交付分级

| 等级 | 目标 | 是否为 V12 全量交付必要项 |
|---|---|---|
| **P0** | 统一 Agent Adapter；Basic/Memory/Planning；实验矩阵与批量队列；可比较的结果；预算安全；回归 | **必须** |
| **P1** | Reflection；轨迹差异与失败诊断；六图专属可视化；实验室网页流程；可读报告 | **必须** |
| **P2** | 第三方 Python Agent SDK/示例；可导入离线公开轨迹；体验优化、E2E/CI 加固与演示包 | **本提纲纳入执行**，不能静默省略；若客观阻塞须显式说明 |

**两道阶段门：** `LAB_CORE_READY` = 全 P0 通过；`LAB_1_0_READY` = P0 + P1 + P2 交付门通过。未获批准而未运行真实模型矩阵时，只能标注 `LAB_1_0_OFFLINE_READY` 或类似诚实状态，不得声称“真实三架构能力已验证”。

---

## 2. 总体设计：一条运行链路，三层清晰分离

```text
Streamlit UI / CLI / Python integration
      │
      ▼
ExperimentSpec + preflight + explicit live approval
      │
      ▼
ExperimentService (matrix / queue / progress / stop / ledger)
      │ creates child runs, reuses V11 RunService/RunStore safeguards
      ▼
AgentRunnerV12 ───> AgentPolicy Protocol (Basic / Memory / Planning / Reflection / External)
      │                            │
      │                  Public Observation + last public actions
      │                            │
      │                  DecisionProvider + one shared budget sink
      │                            │
      ▼                            ▼
V10 Environment ── public V8Action contract validation
      │
      ▼
V12 trace + version/provenance + V11-compatible result
      │
      ├──> per-map metric projection / five-state semantics
      ├──> evidence-based attribution + pairwise trace diff
      ├──> experiment aggregation / versioned exports
      └──> UI Lab panels / map-specific visualizations
```

### 2.1 核心模块建议（最终命名由代码审计决定）

```text
src/agent_arena/
  lab/
    contracts.py          # 版本化 Agent/Decision/Experiment 数据模型
    adapters.py           # 旧架构兼容与安全的公开上下文桥接
    policies/
      basic.py
      memory.py
      planning.py
      reflection.py
      external.py
    runner.py             # 复用 V10 environment + V11 expense/service 策略
    experiment.py         # 矩阵生成、预检、实验队列、状态汇总
    compare.py            # 同配置配对分析、不可比原因
    diagnostics.py        # trace 证据驱动的失败分析
    visualization.py      # 地图专属公开数据 view-model
    report.py             # 实验摘要 Markdown/JSON/CSV
    registry.py           # Agent/地图/可视化插件注册
  web/                   # 扩展现有 Store/Service/Budget/Export，不重造轮子
  ui/                    # 扩展现有 Streamlit 页面与 design tokens
scripts/
  verify_v12.py
  demo_v12.py
  [可选] run_v12_matrix.py
  [可选] e2e_lab.py

docs/v12/
  00-audit.md
  architecture-decision.md
  experiment-protocol.md
  metrics-and-attribution.md
  adapter-api.md
  progress.md
  validation-report.md
  release-checklist.md
  final-report.md
  screenshots/
  demo/
```

**禁止直接复制这份目录当成开发完成证据。** 以现有职责和 import 依赖为准，不应为“微服务式命名”人为增加循环依赖。新增模块不能反向让 `v10` 依赖 `lab` 或 UI。

### 2.2 不可破坏的数据契约

- Agent 可读取：本回合公开 `Observation`、公开动作契约、公开历史/失败反馈、明确允许的 episode-local Memory/Plan 状态。
- Agent 不可读取：私有 `WorldState`、`sealed_truth`、Oracle 解、judge 的未公开字段、用于指标复算的封存真值。
- Environment 是唯一事实来源，Agent **只提出 Action**；实际执行须通过当前图的 `V8Action` / `environment.accepts` / `environment.step`；不得由 Agent 直接修改环境。
- 所有架构复用同一模型调用抽象和预算汇总机制；Planner/Reflection 产生的 **额外 LLM 调用也要计入**请求数、token、费用和耗时。
- 每次运行保存：`map_id`、合法 `environment_seed`、`agent_id`、`agent_version`、`agent_config_hash`、`model`、`provider`、`prompt_hash`、`scenario_hash`、`rule_hash`、`metric_hash`、`metric_schema_hash`、预算、响应使用量与终态。缺字段要标成 unknown，不得猜。
- 实验执行与评分要隔离：分析器可读取已落盘 trace；需要使用隐藏真值进行离线审计的独立 evaluator，必须存储隔离并标注 source，绝不反向注入 Agent 输入。
- **V12 必须新增一个清晰隔离的模拟测试入口**（例如 `SIMULATED`/`FAKE_AGENT` 或仅供测试的受控 Provider 注入），以便不联网运行不同 Agent 的完整调用链；V11 原 `OFFLINE=public_heuristic_policy` 契约不可被悄悄改成“三种 Agent 的离线成绩”。模拟结果的 `mode`/`provider`/UI 标签、导出和分析分组必须显式注明 `SIMULATED`，绝不混入真实模型成绩。
- V11 旧 `manifest/events/result`、离线示例及历史查询保持可读取；**旧结果缺少 V12 agent provenance 时标记 legacy/unknown**，不能反向补写成新的架构。

---

## 3. V12 的统一 Agent Policy 契约（P0）

### 3.1 基本接口

定义可独立测试的 `AgentPolicy`（或等价 Protocol）：

```python
class AgentPolicy(Protocol):
    @property
    def identity(self) -> AgentIdentity: ...  # id, version, capabilities, config hash
    def reset(self, context: PublicEpisodeContext) -> None: ...
    def decide(self, observation: PublicObservation, context: AgentContext) -> AgentDecision: ...
    def observe_result(self, outcome: PublicActionResult) -> None: ...
    def close(self) -> None: ...
```

接口上面的类型名称仅是**设计示意**，不可绕开真实仓库现有协议。`AgentDecision` 至少包含**动作候选**、可选的有限长度公开决策摘要、可选的 `plan_event/memory_event/reflection_event`，以及真实 Provider 请求标识；不要提供完整 chain-of-thought。把 Provider 预算消费作为单一可注入能力，使 AgentPolicy 不得私自绕过预算直接调用 SDK。

### 3.2 四种策略的可验收定义

| ID | 架构 | 关键要求 | 是否需要新模型请求 |
|---|---|---|---|
| `basic.v1` | 基线行动循环 | 沿用 V10 的当前公开提示/动作契约/5 步历史语义，作为基线一致性锚点 | 每个决策通常一次 |
| `memory.v1` | 结构化记忆 | 基于公开 Observation/动作结果维护 episode-local 明确字段；reset/清理；记忆容量和窗口限额；可关闭记忆进行消融 | 最小版不额外增加 LLM 请求 |
| `planning.v1` | 高层计划 | 公共事实生成子目标、跟踪完成条件、事件触发重规划；Planner **只建议目标，不执行动作** | 可额外请求，全部计费 |
| `reflection.v1` | 条件反思（P1） | 由无进展/重复失败/被拒动作等**公开触发器**触发；输出改进建议/重规划事件；有限频率、成本可控、可关闭消融 | 可额外请求，全部计费 |

**反作弊边界：** A1/A2/A3 不得使用各地图 Oracle 的具体通关序列；不能为 MAP-22 硬编码路标答案，也不能给 MAP-30 加隐藏证据。允许通用的公开规则、通用记忆/规划/反思策略及用户可见参数。

### 3.3 研究对照的公平口径

- 研究比较基线是**同一模型、Provider、相同地图规则版本、相同 seed、相同公共任务提示基础、相同总预算门禁**。架构新增的记忆/计划上下文属于被比较的变量，须记录 prompt/agent config 的差异。
- 模型 API 温度、采样参数和模型版本尽量一致并记录；若 Provider 不支持固定随机种子，只能保证**环境 seed 配对**，不能宣称模型输出完全可重复。
- 同时报告 **质量**（成功、连续质量指标、约束违例）和 **代价**（请求、token、费用、时间、决策数）；规划的额外调用不能隐藏。
- 明确区分：可直接配对、仅描述性对比、不可比（版本不一致、缺失指标、环境实例不同、非法实验臂）。
- 早期有限样本报告范围/个体轨迹即可，不计算没有依据的 p 值或“性能提升具有显著性”。

---

## 4. 第二阶段实验方案与固定重点地图

### 4.1 第一条核心研究矩阵（默认方案）

- 地图：`MAP-08` / `MAP-16` / `MAP-18` / `MAP-22` / `MAP-26` / `MAP-30`。
- Agent：`basic.v1` / `memory.v1` / `planning.v1`（P0）；反思独立小矩阵作为 P1 拓展，**不混入前三架构 54 局的同口径对照**。
- Environment seed：每张图从 `seed_space(map_id)` 取**共同可用的 3 个合法 seed**（通常 0/1/2；先核验，禁止假设所有 map 都是 0/1/2）。
- 模型：固定同一个已获用户授权可用的模型。Provider 断链时保留错误局/事件并继续其他**安全合法**工作，不静默重跑计费。
- 总计：`6 × 3 × 3 = 54` 个计划单局；它是**待批准的付费矩阵**，不是第二阶段工程验证的先决条件。
- 实验预注册：先冻结矩阵、Agent 配置、预算、提示词版本与统计口径，再执行；中途任何策略变更都另开 `experiment_id`/版本。

### 4.2 六张图分别用什么回答问题

| 地图 | 主要能力假设 | 重点证据/指标（字段名以运行时 schema 为准） | 代表性 UI |
|---|---|---|---|
| MAP-08 漏点诊断 | 是否正确执行测试→缩小假设→诊断→修复 | `tests_used`、误判/重复测试、完成或失败阶段 | 候选原因收缩与诊断流程 |
| MAP-16 单线预约 | 是否遵守容量、预约、整帧调度约束 | 冲突/拒绝次数、合法调度、目标完成 | 节点/区段占用时间线 |
| MAP-18 故障传播 | 遇到变化能否重新规划与恢复 | `service_rate`、`recovery_delay_ticks`、非法调度 | 故障事件与列车调度 Gantt |
| MAP-22 无地图的丛林 | 记忆是否减少迷路与重复探索 | `route_recall`、`mission_success`、重复路径、返程 | 仅公开已发现区域的探索图 |
| MAP-26 失败的维修计划 | 诊断/回滚能否降低修错成本 | `spares_used`、`diagnosis_precision`、rollback 次数 | 测试→诊断→更换→回滚事件树 |
| MAP-30 午夜审判 | 是否形成有序、可引用的证据链 | `evidence_chain_coverage`、缺失证据、过期窗口、提交失败 | 证据卡片与法庭窗口时间线 |

表中字段属于**候选/已在 V10 文档出现的指标标识**，实际实现前逐项与最新 `MetricSpec` 核验；不得为了 UI 新造“已经实测”的指标数值。对于特殊轨迹，始终遵守只显示 agent-visible 信息的边界。

### 4.3 附加对照（P1 / 按顺序进行）

1. **Memory 关闭/开启**：同策略版本、同基线 prompt、相同历史窗口，明确新增记忆的唯一变量。
2. **Planning 关闭/开启**：保持执行器相同，比较规划本身是否带来净收益，并显示增加的 LLM 调用。
3. **Reflection 触发/关闭**：优先针对失败频繁地图/失败前缀，限制重规划调用次数；输出触发率、改进率、额外费用。
4. 如果出现天花板/地板效应（所有 Agent 都成功/都失败），报告**测量不敏感**，不通过改规则强行制造差异；可换重点 seed 或增加匹配的允许实例，但另列实验，不污染原矩阵。

---

## 5. 按依赖顺序执行：Batch 0–13

每一个 Batch 必须输出：`完成项 / 主要文件 / 测试命令及真实退出码 / 截图或 Trace 证据 / 剩余风险 / 下一批入口`。测试挂掉时优先修复，不得继续叠加大功能。

### Batch 0（P0）：仓库审计、冻结边界、风险表

**任务：**
- [ ] V12-00-01：记录当前 `HEAD`、工作树状态、Python/uv、系统环境、已有测试数、运行入口。
- [ ] V12-00-02：审计 V11 `web/`、`ui/`、`schemas.py`、`execution.py`、旧 `agents/planning` 的真实接口与依赖；列出可复用/不能复用的机制。
- [ ] V12-00-03：构建 V10 30 图规则哈希与指标哈希快照，运行 `freeze verify`、`recompute --check`、`independent_check --check`。
- [ ] V12-00-04：建立 `docs/v12/00-audit.md`、`progress.md`、`risk-register.md`；整理 V11 遗留问题并区分 V12 必修/非阻断。
- [ ] V12-00-05：列清单确认代码里没有其他未登记的 Provider 请求路径，梳理 `runs/web/`、账本和旧 trace 的存储读写口径。

**Gate 0：** 审计报告含可复用 API、迁移风险与冻结基准；Git 工作树无意外改写；V10 检查输出保留。若冻结现状异常，**先定位**，不能把既有问题直接算 V12 引入。

### Batch 1（P0）：架构 ADR、ExperimentSpec 和版本迁移

**任务：**
- [ ] V12-01-01：撰写 `docs/v12/architecture-decision.md`，确定扩展 `RunService` 还是在其上加 `ExperimentService`；优选**父 Experiment + 子 Run**，复用现有安全、恢复、锁、预算能力。
- [ ] V12-01-02：定义 `AgentIdentity` / `AgentPolicy` / `AgentDecision` / `AgentEvent` / `ExperimentSpec` / `ExperimentManifest` / `ComparisonResult` 的 Pydantic/Protocol 契约与版本号。
- [ ] V12-01-03：实验主键 `experiment_id`，子 `run_id` 稳定；矩阵 `matrix_index`、条件摘要、完整版本指纹、seed 取值和 preset 来源可审计。
- [ ] V12-01-04：新增版本化 schema 与旧 V11 读取迁移层；不原地重写已有 V11 manifest；非法配置在入队前拒绝。
- [ ] V12-01-05：设计 `dry_run/preflight` 输出：配置是否可比、缺少 Provider、潜在总调用数、最大费用门禁、无价目表时提示、活跃单局限制。
- [ ] V12-01-06：明确 `LIVE`（真实 Provider）、V11 `OFFLINE`（公开启发式）与 V12 `SIMULATED`（Fake/Scripted Agent）的数据隔离和 UI 标注；原 V11 离线模式不得偷换含义。

**Gate 1：** 通过 schema round-trip、schema 演进、旧 trace / result 向后读取、非法矩阵拒绝、版本不可比测试。ADR 记录替代方案和不选原因。

### Batch 2（P0）：V10 Agent Adapter 与统一 Runner

**任务：**
- [ ] V12-02-01：把 V10 公共 `V8Observation`、`V8Action`、类型化 Action contract 与新 `AgentPolicy` 对接；任何 Action 仍走 V10 校验。
- [ ] V12-02-02：定义仅包含公开字段的 `PublicEpisodeContext` 和 `AgentContext`；做对象图 / 可序列化字段检查，防止 private state/Oracle 穿透。
- [ ] V12-02-03：将 V11 `execute_live` 的模型调用、token/费用/时延统计抽到受控 `DecisionGateway` 或等价机制；策略不能直接绕过网关调用 SDK。
- [ ] V12-02-04：`AgentRunnerV12` 每局 reset、step、observe_result、close；对运行停止、拒绝、非法输出、模型异常、超时、预算耗尽使用 V11 已有规则。
- [ ] V12-02-05：新 runner 保存策略版本/配置哈希与 `agent_events`，与现有 `manifest/events/result` 可兼容导出；旧 `v10_action_loop` 不改历史语义。
- [ ] V12-02-06：使用受控 Fake/Scripted provider 的 `SIMULATED` 路径，在不请求外网的情况下将 30 图各跑至少一局**真实环境完整执行路径**；失败也要能正常终结、回放、导出；不能用 Oracle 自动通关替代 Agent 路径。

**Gate 2：** 30 图不出现 Adapter 字段不兼容；机密与隐藏真值扫描为零；取消/刷新/重复提交/失败继续遵守 V11 安全语义；新旧结果读取测试通过。

### Batch 3（P0）：三种核心 Agent 架构

**任务：**
- [ ] V12-03-01：实现 `basic.v1`；与旧 V10 动作循环做固定 Fake provider 回归，差异有解释，不允许伪装“完全相同”而实际更改 prompt/预算。
- [ ] V12-03-02：实现 `memory.v1`；公开事实记忆、更新、淘汰、容量/长度上限、同回合与跨回合状态隔离；可关闭进行消融。
- [ ] V12-03-03：实现 `planning.v1`；Planner 子目标、PlanMonitor 事件触发、无进展重规划、失败停止策略；Planner 不执行业务 Action。
- [ ] V12-03-04：每种策略提供 registry 元信息与配置 schema、描述、默认参数、契约版、适用地图；网页通过 registry 获取，不硬编码多个 if/else 分支。
- [ ] V12-03-05：测试跨不同地图、不同 seed、重复调用和错误终止时**没有 Agent 内部状态串局**；额外 Planner 请求不遗漏在账本和 Trace。
- [ ] V12-03-06：实现最小消融开关（memory off、planning off），开关变更必须改变 config/prompt 指纹。

**Gate 3：** 3 Agent × 6 核心图可在 Fake provider 下创建、执行、回放；至少证明 Memory 产生/更新真实公开记忆事件、Planning 可产生/监控/重规划事件；不能把有事件误当“模型能力提升”。

### Batch 4（P0）：矩阵实验、作业队列与安全预算

**任务：**
- [ ] V12-04-01：`ExperimentSpec` 支持多地图、多 Agent、seed 数组和单一模型/Provider，生成**确定的子局矩阵**；排除重复条件并支持 `dry-run`。
- [ ] V12-04-02：默认沿用 V11 单 worker 串行实际 Provider 调用；不能因 54 个子任务而并发 54 次付费请求。
- [ ] V12-04-03：实验级硬门禁 + 单局硬门禁：请求、token、费用、墙钟时限、未知 usage/异常；**总预算预留/结算**包含 Planner/Reflection 请求。
- [ ] V12-04-04：实现父实验 `CREATED/QUEUED/RUNNING/STOPPING/COMPLETED/PARTIAL/CANCELLED/FAILED`（具体命名按 ADR）；子局使用既有运行状态；中止只影响尚未开始的局及活跃局协作取消。
- [ ] V12-04-05：幂等启动（按钮重复点击、页面刷新、进程重启），同一请求不产生两个已收费 run；掉电只恢复已有记录状态，不擅自重发不确定费用请求。
- [ ] V12-04-06：断点续跑以**子局为单位**，只排尚未执行的子局；已完成/已中断/未知消费子局不自动重跑，必须有新的显式人工指令和新 run_id。
- [ ] V12-04-07：提供 CLI 或 Python API 提交同一实验，以支持 CI 只跑 Fake matrix；实验级 JSONL 账本 append-only。

**Gate 4：** 预检时**零请求**；配额用尽阻止下个调用；未知金额停止；中断后无双收费；局部成功、取消、失败形成准确父实验汇总；运行结果仅在有效对照规则下被归类。

### Batch 5（P0）：聚合、配对比较、版本门禁与导出

**任务：**
- [ ] V12-05-01：区分 `completed_success`、机制失败、预算截尾、取消、Provider 错误、异常；明确有效分母和缺失策略。
- [ ] V12-05-02：对于同地图、同 seed、同规则/指标 schema、同模型和预算配置的实验臂，提供配对统计：成功率、步骤、请求、token、费用、延迟、拒绝动作；低于样本要求时只给描述性统计。
- [ ] V12-05-03：添加同图主指标/图特定指标，保留 `VALID/CENSORED/NOT_APPLICABLE/MISSING/INVALID` 五态；不可合法聚合的数据不给均值，不补零。
- [ ] V12-05-04：逐对声明 `COMPARABLE / DESCRIPTIVE_ONLY / INCOMPARABLE` 及具体理由；禁止把不同地图绝对分值直接平均当总能力。
- [ ] V12-05-05：导出 `experiment.json`、`runs.csv`、`paired_comparison.csv`、`metrics.csv` 与版本元数据；旧 V11 单局 JSON/CSV 继续有效。
- [ ] V12-05-06：提供聚合单测：不等量 seed、缺失指标、成本 unknown、模型错误、不同版本、全失败、全成功、同 seed 不同策略、负例排序。

**Gate 5：** 聚合数据可从每个 run 原始记录独立复算，分母一致；错配实验不产生“公平排名”；导出后可只读重建主要汇总。

### Batch 6（P1）：ReflectionAgent 与结构化行为事件

**任务：**
- [ ] V12-06-01：实现 `reflection.v1`：公开触发器如连续无进展、重复被拒动作、关键阶段回退、循环警告；触发器必须是可解释的规则，而非 LLM 自判。
- [ ] V12-06-02：限定每局反思次数、冷却间隔、总请求/token/费用，避免反思自己反复反思。
- [ ] V12-06-03：只给 Reflection 公开历史/摘要；输出公开行动建议或计划修订，不提供隐藏进度或答案。
- [ ] V12-06-04：记录 `reflection_trigger`、触发证据、决策索引、反思后的下一步结果、额外费用；可离线 Fake 验证。
- [ ] V12-06-05：为 Reflection on/off 设计一个与前三策略主矩阵**独立**的小试验集，避免同组比较混淆架构变量。

**Gate 6：** 在有触发、无触发、连续失败及费用用尽场景均有测试；Reflection 可在 UI/结果显示，但不得声称必然提效。

### Batch 7（P1）：证据驱动的失败诊断和轨迹 Diff

**任务：**
- [ ] V12-07-01：复用 `web/attribution.py`、`v10` 失败码和关键机制证据；建立结构化 `Finding`：类别、严重度、触发步、证据事件 IDs、适用地图/规则版本、置信来源、可验证解释。
- [ ] V12-07-02：基本行为检测：重复动作/状态、无进展循环、被拒动作重复、遗漏公开前置条件、预算提前耗尽、窗口错失、错误因果顺序、计划频繁抖动。
- [ ] V12-07-03：给每图选择**明确可见的证据规则**，优先六图，避免统一关键字分析假装解决所有能力测量。
- [ ] V12-07-04：对两条配对轨迹做**事件序列对照**（步数不一致时使用阶段/公共状态变化或事件锚点，而不是武断按第 n 步相减）。
- [ ] V12-07-05：输出“首次有意义差异”“可能的失败链路”“已有证据/不足证据”“下一次可验证假设”；**不得断言模型内部心理原因**。
- [ ] V12-07-06：可选 LLM 生成报告解说必须默认关闭，且明确标成 `hypothesis/LLM-generated`、可禁用、费用另计；核心诊断必须在无 API 下可执行。
- [ ] V12-07-07：准备有正负标注的人工/确定性 fixture，覆盖误报、漏报与 `NOT_ENOUGH_EVIDENCE`；不要仅用“诊断输出不空”验收。

**Gate 7：** 每条核心诊断都能点到具体 trace 证据；对 Provider 错误/预算截尾不虚构策略失败；不会泄露密封真值；兼容旧 trace 缺字段情况。

### Batch 8（P1）：六图专属可视化 + 30 图通用回退

**任务：**
- [ ] V12-08-01：构建可复用 map-specific `view-model` 与 UI 的隔离层；可视化只接收已公开事件、指标，不在页面中重新执行环境。
- [ ] V12-08-02：MAP-08：诊断阶段/候选集合变化、测试次数与错误试探。
- [ ] V12-08-03：MAP-16：列车节点/区段预约与冲突时间线，缺数据时给合理空态。
- [ ] V12-08-04：MAP-18：故障/恢复事件与调度进展 Gantt/时间线。
- [ ] V12-08-05：MAP-22：根据 Agent 已**实际发现**的路标生成探索图和返程轨迹，不绘制隐藏地图全貌。
- [ ] V12-08-06：MAP-26：诊断→维修→回滚事件链及备件消耗。
- [ ] V12-08-07：MAP-30：证据引用关系、近期有效窗口与提交缺口；不提前揭示未发现物证。
- [ ] V12-08-08：其他 24 图展示通用资源/进度/动作图表；五态、缺失和无法绘图按原样展示。
- [ ] V12-08-09：为六图制作至少各一个成功/失败/截尾中的代表性公开 fixture（若某类数据不可得，使用明确说明的合成**UI 测试** fixture，不冒充真实模型）。

**Gate 8：** 六图均可打开可视化，时间/指标与原始 trace 可核对；无密封数据；窄屏可用、无数据可解释、无 JS/渲染崩溃。

### Batch 9（P1）：实验室网页闭环与可读报告

**任务：**
- [ ] V12-09-01：在现有 Streamlit 导航中增设 Lab 入口，保持 V11 地图大厅/单局演示路径不受影响。
- [ ] V12-09-02：实验配置页：地图、Agent 多选、模型、环境 seed、预算、主/次指标、实验备注；显示实验矩阵和**显式费用确认**。
- [ ] V12-09-03：实验监控页：父实验状态、每个子局状态、活动局实时动作/费用、已完成/取消/错误数量，停止按钮。
- [ ] V12-09-04：结果页：概览卡、可比性提示、配对图表、Agent 成本-质量权衡、逐局明细、五态指标、失败原因。
- [ ] V12-09-05：并排 trace 回放、差异锚点与证据卡片点击跳转；具备 JSON/CSV/Markdown 导出。
- [ ] V12-09-06：生成可读 Markdown 报告：问题、实验矩阵、不可比声明、数据口径、主要发现、代表性轨迹、局限、复现实验方式。**报告中所有数据必须来自真实结果或标注的离线演示数据**。
- [ ] V12-09-07：空状态和防误用提示：无 Key/无单局/指标缺失/全失败/版本冲突/取消/未批准预算/Provider 异常。
- [ ] V12-09-08：复用 V11 design tokens 和统一交互风格；本地化中文、长图表可滚动、清晰标注模型/规则版本。

**Gate 9：** 用户从首页可完成 `实验配置 → 预检 → 离线提交 → 运行 → 对照 → 回放 → 报告导出`；刷新不重复计费；V11 原有六页主要 E2E 不回归。

### Batch 10（P2）：第三方 Python Agent Adapter 与离线导入

**任务：**
- [ ] V12-10-01：定义 SDK 级 Python 插件入口（策略工厂、版本/能力声明、公开 context、Action 校验、错误分类）。第三方策略不能获得真实 Environment 对象或隐藏真值。
- [ ] V12-10-02：提供示例插件 `examples/custom_agent/`（只使用公开 Observation；可用 Fake Provider 或纯确定性例子）。
- [ ] V12-10-03：新增 registry allowlist，默认仅加载受信任的本机代码；**不得把任意上传 Python 代码当安全沙箱**。不从网页任意 `eval` 用户输入。
- [ ] V12-10-04：插件按 Agent 身份、实现版本和配置签名纳入实验可比性检测；缺少必需的事件字段时明确降级。
- [ ] V12-10-05：允许导入 V12 自身导出的**非敏感公开运行文件**进行只读分析，校验 schema/大小/hash 和路径；不从外部导入的 JSON 重建真实付费状态或覆盖本地账本。
- [ ] V12-10-06：补 `docs/v12/adapter-api.md`、接入示例、常见问题；第三方适配器和内置 Basic 在最简单测试中遵守相同 Action 边界。

**Gate 10：** 示例可单独安装/加载/执行/导出，错误插件不会绕过网关预算、修改 V10 或读取私有字段；SDK 能在文档指令下由另一位开发者复现。

### Batch 11（P2）：稳健性、质量门禁、跨平台与 E2E

**任务：**
- [ ] V12-11-01：一键自检 `scripts/verify_v12.py`：30 图 catalog + 旧 freeze + 新三架构/六图 Fake smoke + 预算 + 重复提交 + 父子状态 + schema + 脱敏 + 六图展示契约 + 导出复算。
- [ ] V12-11-02：添加 CI 的自动化浏览器 E2E（无 API Key，临时目录）：配置实验→离线预检→提交→结果→成对回放→导出；对浏览器依赖不可用时如实阻断/记录。
- [ ] V12-11-03：对 UI 430px/桌面/深色进行截图回归，并增加键盘导航、对比度和标签检查；能自动检测的自动检测，真机未测不得声称真机通过。
- [ ] V12-11-04：验证 Windows、Ubuntu CI、macOS（能拿到实机/runner 时）；未获得 macOS 实测须报告 `NOT_VERIFIED`，不可凭 `.command` 文件声称成功。
- [ ] V12-11-05：`mypy`、Ruff、pytest、uv lock、30 图 freeze/复算/独立检查全部绿色；跨版本结果读取和旧网页启动必须通过。
- [ ] V12-11-06：建立 Demo 包至少三组：纯离线 Basic/Memory/Planning、两轨迹对照、一个失败证据报告，明确标注非真实模型结果。
- [ ] V12-11-07：压力/故障测试：54 子局 dry-run、大量历史分页、CSV 导出大文件、损坏 JSONL 行、请求超时/未知消费、策略异常、取消中途进程退出。

**Gate 11：** 新功能 E2E 和 V11 回归均通过；所有未验证平台/场景明确披露；运行过程无历史文件变动、无密钥泄露。

### Batch 12（P0/P1 联合）：真实 API 验证（**需用户明确预算批准**）

**默认状态：`PENDING_APPROVAL`，不是偷偷执行。**

- [ ] V12-12-01：优先完成零成本 Fake/脚本验证后，给用户展示完整 `ExperimentSpec`、子局列表、模型、固定参数、单局与全实验预算上限、估算费用范围、未知费用策略；记录明确批准。
- [ ] V12-12-02：获批后先运行 **3–6 局小规模 Pilot**（至少覆盖 Basic/Memory/Planning，并覆盖至少两图）；检查动作契约、账单、运行终态、计划事件和指标。
- [ ] V12-12-03：Pilot 通过、费用未越界、没有未解释 Provider 错误时，运行预登记的 **54 局主矩阵**。如果用户只批准部分预算，按固定优先顺序运行可覆盖子集，记录矩阵不完整，不能报告“54/54 完成”。
- [ ] V12-12-04：将 Provider/环境/策略/预算失败分开编码；对中断局保留原始 run_id 与会计记录，**不隐式补跑**；确需补跑则新建补充实验并注明来源。
- [ ] V12-12-05：反思 P1 的独立少量补充试验需新的、明示的预算批准，不混进主实验。
- [ ] V12-12-06：核对 Provider usage 与本地费用估算，未知数额单独登记；生成带局限说明的实测总结。

**Gate 12：** 真实试验只有在授权后才能标绿；没有授权则保持 `LIVE_VALIDATION_PENDING_APPROVAL`，整体可标 `LAB_1_0_OFFLINE_READY`。不允许因缺预算将伪造/离线数据冒充真实模型数据。

### Batch 13（P0/P1/P2）：阶段验收、文档、演示和交付

**任务：**
- [ ] V12-13-01：完善 `README.md` 的 Lab 使用入口、`docs/architecture.md`、`docs/scope/scope.md`、`研究总纲.md`；不把未完成项改成已完成。
- [ ] V12-13-02：完成 `docs/v12/validation-report.md`（命令、真实测试输出、与 V11 的回归、内存/费用/兼容边界），`release-checklist.md`（P0/P1/P2 状态）。
- [ ] V12-13-03：完成 `docs/v12/final-report.md`：WHAT/WHY/RESULT/KNOWN ISSUES/NEXT，含截图、命令、报告示例和准确的实际 HEAD。
- [ ] V12-13-04：提供**可复现演示脚本**：无 API Key 从空环境启动、选择实验、跑离线 3 Agent、看对照、打开 MAP-22 探索图、导出报告。
- [ ] V12-13-05：完成最终 `git diff` 审核、安全/隐私检查、冻结 hash 对比、测试 Gate、清理临时文件；只提交源码、文档、脱敏演示资产。
- [ ] V12-13-06：按完成事实标记 `LAB_CORE_READY` / `LAB_1_0_OFFLINE_READY` / `LAB_1_0_READY`；生成下一阶段 backlog，但**不提前实现 V13**。

**Gate 13：** 一个新用户可根据 README 完整体验 Lab；文档足以审计；失败路径可复现；无阻断项才可称对应 Gate ready。

---

## 6. 质量门禁与硬约束（全部适用）

### 6.1 每批最少执行的命令（执行前按实际 CLI 核验）

```bash
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run uv lock --check
git diff --check
uv run python -m agent_arena.v10.freeze verify
uv run python -m agent_arena.v10.recompute --check
uv run python -m agent_arena.v10.independent_check --check
uv run python scripts/verify_v11.py
# V12 新建后：
uv run python scripts/verify_v12.py
```

注：`scripts/verify_v12.py` 是 V12 待实现命令，不是现有文件；任何无法执行的命令须报告真实原因。脚本不能主动发真实付费 API 请求。

### 6.2 必须具备的自动化测试类别

| 类别 | 最低覆盖 |
|---|---|
| 契约 | schema round-trip、错误输入、旧结果兼容、Agent metadata、版本门禁 |
| 架构 | 3/4 Agent 生命周期、状态隔离、公开事实限制、记忆/规划/反思事件 |
| 30 图 | 30/30 创建和可执行检查；六图优先覆盖真实执行适配的完整失败/成功通路 |
| Batch | matrix dry-run、父子状态、幂等、取消、部分执行、恢复、重复调用拒绝 |
| 安全预算 | 单局+全局 token/请求/金额上限、Planner 额外请求计费、未知 usage fail-closed |
| 评测 | 配对/不可比、五态、Provider 错误和截尾分母、导出独立复算 |
| 诊断 | 每条 finding 可定位证据、否定 fixture、缺失信息降级、不泄露答案 |
| 六图 UI | 公共字段可视化、没有记录时空态、版本不一致、窄屏显示 |
| E2E | 无 Key 离线入口及 V11 原单局流程回归 |

### 6.3 P0 不可通过的情形（NO-GO）

- 改动了任一 V8/V9/V10 冻结规则/账本/原始 trace，或未给出哈希对照证明未修改。
- 新 Agent 能读取隐藏世界状态、Oracle 答案或完整私有评分对象。
- Planner/Reflection 请求未纳入实际总请求/token/费用统计；未知费用被忽略。
- 实验对照自动跨不同 `rule_hash`/指标 schema 混算，或将缺失/截尾当作 0。
- 网页刷新/重复点击导致重复执行或支付；失败后自动无限重试。
- 用 Fake、Oracle、录制 fixture 冒充 MiMo 等真实模型成绩。
- 仅靠截图或日志文字宣布完成，缺少可执行测试与文件证据。

### 6.4 可合理延期但必须披露的项

- 用户没有授权 API 消费；只能停在离线准备状态。
- 某平台缺乏实际运行环境；可通过 CI 或文档说明，但不能填“实测通过”。
- 第三方任意代码**安全隔离**：本地受信任插件可以交付，公网安全沙箱明确不在范围。
- 模型输出含完整思维链问题：只能截取可公开的有限摘要/动作，不需要也不允许采集完整 CoT。

---

## 7. 数据格式与可审计输出（建议）

### 7.1 `ExperimentSpec` 最小实例（示意，字段名按最终 schema 决定）

```yaml
schema_version: v12-lab-1
experiment_id: auto-generated
name: six-maps-three-agents
maps: [MAP-08, MAP-16, MAP-18, MAP-22, MAP-26, MAP-30]
agent_arms:
  - {id: basic.v1, config: {}}
  - {id: memory.v1, config: {enabled: true}}
  - {id: planning.v1, config: {enabled: true}}
environment_seeds: auto-validated-three-common-seeds
provider: configured-single-provider
model: user-approved-fixed-model
execution: sequential
mode: live
preflight_only: true
budget:
  per_run_request_cap: recorded-from-run-config
  per_run_token_caps: recorded-from-run-config
  per_experiment_request_cap: explicit
  per_experiment_cost_cap_cny: explicit-or-blocked
  unknown_spend: stop-and-mark-unknown
comparison:
  paired_by: [map_id, environment_seed]
  require_same_versions: true
  descriptive_only_for_small_samples: true
```

**重要：** YAML 示例中 `auto-validated-three-common-seeds` 不是可直接传给最终类型系统的值；执行者需查询 `seed_space` 后生成真实列表。`preflight_only=true` 的演示不可实际收费。

### 7.2 可读诊断 `Finding` 示例（不能凭空当作实测）

```json
{
  "category": "repeated_no_progress",
  "severity": "warning",
  "map_id": "MAP-22",
  "evidence_event_ids": ["event-17", "event-23"],
  "summary": "在相同已公开路标之间重复移动，期间无新公开探索进展",
  "source": "deterministic_trace_rule",
  "confidence_scope": "behavior_observed_not_internal_cause",
  "suggested_check": "对照启用记忆策略后重复路径是否减少"
}
```

### 7.3 输出文件与命名空间

```text
runs/lab/<experiment_id>/
  experiment.json               # 固定矩阵、指纹、版本、预算、审批状态
  manifest.json                 # 父实验状态
  events.jsonl                  # 父实验 append-only 事件
  summary.json                  # 汇总与有效分母
  comparison.json               # 版本门禁与配对差异
  report.md                     # 可读报告
  exports/
    runs.csv
    metrics.csv
    paired_comparison.csv
  children/                     # 仅链接子 run_id，避免复制旧 RunStore 数据

runs/web/<run_id>/              # 保持 V11 子局既有可读结构，必要时只增 V12 可选字段
```

具体布局可调整，但必须优先复用 V11 已有 RunStore，不要复制、双写、篡改旧账本。把 `runs/` 保持在 `.gitignore` 范围，提交演示资产时须先**脱敏、压缩、版本注明**。

---

## 8. 阶段性演示脚本（必须实现）

**场景 A：无 API Key 的工程演示**

1. `uv sync --extra web`，`uv run agent-arena web`。
2. 打开 Lab 页，选 `MAP-22` 和 `MAP-18`，选择 3 种内置 Agent、合法 seed，点击预检；显示 0 个真实请求已发送。
3. 启用 V12 `SIMULATED` / Fake/Scripted 演示 Provider（明确写“离线模拟，不是模型”，不占用 V11 `OFFLINE` 的旧标识），批量提交小矩阵。
4. 查看实验级队列、三个 Agent 的完成/失败/截尾状态，点击某局查看公开轨迹。
5. 打开 MAP-22 探索图、MAP-18 时间线和至少一条失败证据卡；进行 pairwise 对照。
6. 导出 Markdown/CSV/JSON，独立脚本校验汇总与单局原始数据一致。

**场景 B：经授权的真实 API 验证**

1. 用户明确批准预算后才解除 `preflight_only`。
2. 先 Pilot 3–6 局；确认单局费用、额外 Planner 调用、异常行为与 prompt provenance。
3. 满足 Gate 后按同一已冻结 ExperimentSpec 执行 54 局（或按实际授权上限执行的透明子集）。
4. 只用真实 trace 生成报告，声明样本量、失败类型、Seed 口径、局限与不可比原因。

**场景 C：第三方 Agent 示例**

1. 安装/加载受信任本地自定义策略。
2. 对 MAP-08 做无付费 dry-run 和简短 Fake 完整局。
3. 结果含明确 `agent_id/version/config_hash`；与内置策略的比较按版本约束生效；卸载不会破坏其他策略。

---

## 9. 任务优先级和停止条件

### P0——必须先打通的研究产品骨架

- Batch 0 审计 / Batch 1 契约 / Batch 2 运行桥接 / Batch 3 Basic-Memory-Planning / Batch 4 实验矩阵 / Batch 5 对照与导出。
- 这六批全部完成且 V11 回归保持通过，才可标 `LAB_CORE_READY`。

### P1——从“能运行”变成“能解释”的产品价值

- Batch 6 Reflection / Batch 7 失败诊断与 Diff / Batch 8 六图可视化 / Batch 9 Lab UI 和报告。
- 如工期紧张，**优先保 Batch 7/9 的诊断与报告**，不要为视觉效果破坏指标可信度；但任务状态必须诚实标注未完成，不算完整 V12。

### P2——扩大可用性和交付质量

- Batch 10 SDK/导入 / Batch 11 E2E/CI/跨平台/演示 / Batch 13 文档与发布准备。
- 不做云部署、登录、跨模型竞赛；它们是未来路线而不是 V12 延期任务。

### 有效的停止条件

- 发生密钥/封存信息泄漏、费用账本不可信、原有冻结检查回归时立即停止相关改动，先恢复安全性与一致性。
- 真实 API 没有授权、预算耗尽、Provider 费用未知时暂停所有真实请求，不影响离线工程继续推进。
- 某功能无法在现有架构下安全完成，停止该支线，提交最小可用状态与书面设计分歧；不要在没有验收的情况下重构整个仓库。

---

## 10. 最终提交清单和向用户汇报格式

**必须交付：**

- [ ] A. 一套能独立运行的 `Agent Arena Lab 1.0` 本地网页实验流程。
- [ ] B. Basic/Memory/Planning 三架构 + Reflection 能力（可关闭/触发事件明确）。
- [ ] C. ExperimentSpec、批量队列、父子 run、全局预算/幂等与版本化存储。
- [ ] D. 六图实验方案、统一配对分析、五态指标与自动导出。
- [ ] E. 行为诊断/两轨迹 Diff、可点开证据及六图专属可视化。
- [ ] F. 第三方 Python Agent 接入示例、只读导入与 API 文档。
- [ ] G. 一键离线验收、CI/E2E、V11 兼容回归、最新截图、无 Key 演示包。
- [ ] H. `docs/v12/` 中完整审计、ADR、实验协议、进度、验证、Checklist 与 Final Report。
- [ ] I. 如用户批准：真实 Pilot + 54 局矩阵或透明的授权子集；若未批准，明确标 `PENDING_APPROVAL`。

**给用户的最后汇报必须使用以下结构：**

```text
【当前仓库 HEAD 与分支】
【V12 总状态】LAB_CORE_READY / LAB_1_0_OFFLINE_READY / LAB_1_0_READY / NOT_READY
【P0 已完成 / 未完成】按 V12 任务编号列出
【P1 已完成 / 未完成】按 V12 任务编号列出
【P2 已完成 / 未完成】按 V12 任务编号列出
【核心功能演示】启动、预检、批量、对照、证据、导出
【质量证据】pytest/ruff/mypy/lock/V10 冻结/V11 自检/V12 自检/E2E 实际结果
【真实 API】是否获授权、实际局数、请求/费用/未知预留、失败与补跑说明
【数据可信性】有效分母、可比性限制、离线 vs 真实模型标识
【遗留风险及原因】明确 NOT_VERIFIED/PENDING/FAILED
【下一步】只列最优先的 3–5 项，不发散提前做 V13
```

**完成判据只有一个：** 用户不需要理解内部代码，也能在本地网页中回答——

> **“在同一张任务地图上，我更换 Agent 架构以后，它的行为、成功率、成本与失败原因究竟有哪些可验证的差异？”**

如果系统只能让三种 Agent 点击运行，却无法可靠地记录它们的差异、解释失败、限制费用与复现对照，那么 V12 还不能算交付。
