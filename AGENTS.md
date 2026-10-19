# Agent Arena 工程上下文

## 当前状态

- `0001-project-architecture` 架构 spec 已确认生效，状态为 `Accepted`。
- Release 2 的确定性 Spaceship Escape、ReactAgent、MemoryAgent、Agent Loop、Episode Trace、终止控制和 benchmark 对照已完成；PlanningAgent v1 的工程闭环及真实对照已完成（qwen 与 Muse 基线均为 0/5，见 spec 0006 与失败分析）。
- 十世界三十图（飞船/灯塔/深海站/极地/金字塔/地铁/火山/丛林/月球/古堡 × 简单 6 房/中等 8 房/困难 10 房，spec 0007–0011）已建成，规则零改动；最新完整测试记录见 `docs/engineering-log.md`。
- V3 世界设计提纲已完成十家族 30 个独立 Scenario 的离线实现、机制核对、设计评分、公开 Oracle 与 Legacy/Trace 兼容验收；细节见 spec 0017 与 `docs/world-design-v3/`。该结果不包含真实模型实验。
- Muse 自主组合（memory + history5 + recovery + phase，不限步）在 9 配置 × 5 seeds = 45/45 成功通关，均值步数三图全部随难度单调递增；终点 `read_terminal` 误用与读码后迷路是已确认的下一步消融靶子。
- 后续十世界三十图矩阵 150/150 成功；flex pilot 与 seeded 变体另有 30/30 和 15/15 成功，长尾分析与更广 seeded 覆盖仍待推进，详见 `docs/scope/scope.md`。
- Research V1 已提供只读 Streamlit MVP（单局回放、矩阵总览、错误热点、条件对照）；完整的实验配置与启动界面仍是 Release 3 计划项，运行命令见 README。
- `研究总纲.md` 是新对话和日常 workflow 的研究摘要；完整产品与研究参考保留在 `总纲.md`，需要追溯细节时再阅读。
- 当前模块结构见 `docs/architecture.md`，交付顺序和进度见 `docs/scope/scope.md`。
- 重要阶段、决策、验证和阻塞记录在 `docs/engineering-log.md`，它不替代 scope、spec 或 Git 历史。
- V6 能力测量效度：离线层已完成（审计 V5 失败并定位 MAP-22 接口契约缺陷；参数化 V4 引擎并建立 **29 个独立 V6 实例**、三个闭塞段、三个恢复失败前缀、纯召回变体、独立求解器与泄漏检查）。真实 API 复测已完成（MiMo，**47 局，CNY ¥0.29230284，17/47**）：MAP-22 的 V5 0/6 确认为接口假象；**MAP-22 L3 记忆消融与 MAP-30 纯召回出现条件差异**；MAP-08/L1-MAP-16/MAP-26-free 天花板、MAP-18/MAP-26-recovery/MAP-30 完整调查地板，维持 `HOLD`。详见 `docs/v6/pilot-report.md` 与 spec 0019。所有 V6 实例仍 `pending_human_review`。
- V7 30 图分层能力评测离线层已交付：`src/agent_arena/v7/metrics/` 为只读层，注册 **154 条 MetricSpec**（6 图 44 条 implemented + 24 图 110 条 design-only，全部带 `valid_range`），交付 30 张逐图指标卡、五态缺失规则、6 图 extractor、六图 36 条真实环境手算 fixture、结构自审与泄漏扫描、24 份 `pending-runtime/MAP-XX.md`、离线验收脚本与报告；29 个 V6 实例回放全部成功复算。24 图仍无运行时；30 卡已由用户于 2026-10-17 复核并记录为 `human_approved`。已有 V6 MiMo 47 局 trace 的 V7 post-hoc 复算；2026-10-17 六图 12 局 V7 pilot-001 启动 10 局、完整 9 局后因 `APIConnectionError` / `unknown_provider_spend` 按规则封账（CNY `0.05086048`），随后在独立新账本上完成 Pilot-001R **12/12 局**（CNY `0.08521648`，109 请求，0 中断）；两者均为单 seed、每条件 1 局的 E3-pilot，不构成 V7 主实验。详见 `docs/v7/validation-report.md`、`docs/v7/self-review.md`、`docs/v7/real-trace-rescore.md`、`docs/v7/pilot-001-report.md` 与 `docs/v7/pilot-001r-report.md`。
- V8 30 图定稿与 MiMo 三重复验收已完成：`src/agent_arena/worlds/scenario_v8/` 提供 24 张新运行时 + 6 张 V4/V6 适配图，`src/agent_arena/v8/` 提供五态指标投影、独立 append-only 账本、公开 prompt 与 runner；**154/154 指标**有运行时来源，离线门禁 **30/30**、858 pytest passed、`mypy src` 0 issues。正式 MiMo 完成 **90/90 局**（17 成功、39 机制失败、32 决策预算耗尽、2 截尾），正式行费用 **CNY ¥1.27464628**，全部账本 settled **¥1.39004496** + 未知消费预留 **¥0.04096**。运行期间因 4 次 provider `unknown_spend` 和 MAP-22/MAP-12 两处接口/预算修复，使用原账本 + 6 个隔离补充账本；旧局、预跑与失败尝试全部保留并标注，未静默覆盖。n=3 只作重复运行描述，不作显著性断言；Oracle 成功率不等于 MiMo 能力。详见 `docs/v8/final-acceptance.md`、`baseline-audit.md`、`mimo-90-results.md`、`failure-analysis.md` 与 `offline-validation.md`。
- V9 30 图难度定标与失败归因已完成：`src/agent_arena/v9/` 提供只读审计、120 条独立指标复算、30 个公开启发式/消融、独立 ¥10 账本与有界 runner；交付 30 份逐图审计、14 份 DCR、10 张图的公开信息补充、9 图指标叠加与状态矩阵。复算确认 V8 **17/90**、22 张 0/3；**11 张图存在构念旁路**（含 MAP-06 seed 0、MAP-15 goal 泄露、MAP-21 直达撤离），至少 13 张 0/3 首因是公开信息/接口而非能力。V9 起点状态 **7 张 VALIDATED、8 张 NEEDS_MORE_EVIDENCE、13 张 NEEDS_REDESIGN、2 张 BLOCKED**；V8 规则、账本与 90 局 Trace 未修改。验证：888 pytest passed、scoped Ruff/mypy 通过。MiMo V9 为预登记 E3-pilot（29 条记录、settled **¥0.34049884**、2 次 unknown spend）。详见 `docs/v9/` 下 `final-report.md`、`mimo-results.md`、`map-status-matrix.md`。
- V10 30 图核心机制重构、难度校准与多 Seed 有效性验证已完成 Batch 0–9：`src/agent_arena/v10/` 提供 23 张原生运行时（其余 7 张回退 V8）、v10 五态指标（154 旧 + 128 新）、25 份 DCR、多 seed 基线、独立 ¥10 共享账本、类型化公开动作契约、trace 级失败归因与 8 项验收 Gate；`docs/v10/` 交付 `final-report.md`、30 张逐图审计卡 `maps/MAP-XX.md`、状态矩阵、难度定标、构念效度、指标独立复核、失败归因、MiMo 结果与成本账本审计。离线：23 图 × 116 seed 实例 0 违规、回放确定 23/23、seed 互异 23/23；真实 MiMo：85 局记录（80 有效 + 5 中断保留）、成功 36/80、结算 CNY `1.77142820` + 未知预留 `0.11468800` = `1.88611620`。发现并修复两类系统性接口假象（动作契约只列字段名不列类型 DCR-V10-24；MAP-20 取值结构未公开 DCR-V10-25），合计把约 500 次非法动作从“能力结论”里剔除（MAP-18 非法 20/20→0、MAP-20 168/168→0、MAP-28 seed0 由从未提交变为成功）。当前 30 图状态 **30 VALIDATED**（23 张原生图 8 Gate 全过 + 7 张 V8 回退图沿用 V9 并记 3-seed 缺口），`NEEDS_REDESIGN`/`BLOCKED`/`BYPASS` 全为 0。全部结论 `agent_reviewed`，未发生 `human_approved`。详见 `docs/v10/README.md` 与 `docs/v10/final-report.md`。

## 技术与模型配置

- **语言与运行时**：Python 3.13，使用 uv、`pyproject.toml` 和 `uv.lock` 管理项目。
- **核心依赖**：Pydantic v2、pydantic-settings、Typer、OpenAI Python SDK、pytest、Ruff 和 mypy。
- **LLM 平台**：默认使用本地 Ollama 原生 API；阿里云百炼保留为可选的远程 provider。
- **默认模型**：Ollama `qwen2.5:7b`；本机 OpenAI-compatible 研究网关当前使用 OpenCode Zen `muse-spark-1.3-contributor`，实际配置以本机 `.env` 为准。
- **本地配置**：`.env` 只保留在本机。新机器从 `.env.example` 创建它。密钥不得提交、打印、写入源码、日志、trace、文档、测试或 prompt。
- **环境变量**：Ollama 使用 `OLLAMA_BASE_URL` 和 `OLLAMA_MODEL`，默认地址为 `http://127.0.0.1:11434`。OpenAI-compatible relay 使用 `OPENAI_BASE_URL`、`OPENAI_API_KEY` 和 `OPENAI_MODEL`，并通过 `AGENT_ARENA_PROVIDER=openai` 选择。
- **验证命令**：本机远程模型运行 `bash scripts/verify_model.sh`；Ollama 运行 `uv run agent-arena verify-model --provider ollama`。

## 语言约定

- 面向使用者的 CLI 输出、世界描述、prompt、trace 摘要、scope、spec、工程记录和项目文档一律使用中文。
- 代码标识、文件路径、命令、第三方 API 字段和无准确中文替代的标准术语保留英文。

## 开发策略

Skateboard。先交付一个真正可运行的最小闭环：确定性环境、基线 Agent Loop、Episode Trace 和可重复结果。Memory、benchmark 分析和 UI 在该闭环稳定后再增加。

## 分层上下文加载

目标是用架构和状态文档恢复上下文，不在每次任务开始时扫描或读取全仓库。

### 新对话必读

1. `AGENTS.md`
2. `研究总纲.md`
3. `docs/architecture.md`
4. `docs/scope/scope.md`
5. 当前任务对应的 `docs/specs/` 文件，没有 spec 时只读取与任务直接相关的需求段落
6. `git status --short --branch`，以及当前改动的文件列表和 diff 摘要
7. `docs/engineering-log.md` 的最近记录，用于恢复重要历史和上次验证结果

### 按需读取代码

- `/develop`、`/test`、`/debug` 和 `/check` 只读取当前 spec 指向的目录、入口文件、直接依赖、相邻测试和当前 diff。
- 使用 `rg` 精确定位符号和调用点，先读小范围上下文，再按调用链向外扩展。
- 不因熟悉项目而读取全部源文件、全部测试、全部历史或 `总纲.md`。
- 只有以下情况可以进行全仓库扫描：`/audit`、跨模块架构重构、无法从架构文档判断责任边界，或用户明确要求。

### 文档权威顺序

1. `AGENTS.md`：工程工作流和持久约定。
2. `研究总纲.md`：日常研究摘要和阶段边界。
3. `总纲.md`：完整产品与研究蓝图，按需追溯。
4. `docs/scope/`：路线、里程碑和当前进度。
5. `docs/specs/`：已确认的技术决策和验收条件。
6. `docs/architecture.md`：稳定模块边界和数据流。
7. 代码和测试：实际运行行为。

## 工作流入口

操作流程与文件维护分工统一见 [docs/workflow.md](docs/workflow.md)，9 个项目 Skill 的入口见 [skills/README.md](skills/README.md)。按任务选用，不为文档或小修复机械执行全部阶段。

完成顺序：实现 → 适用验证 → `/sync` → 重要事件记录 → 提交并推送预期文件。验证失败时记录阻塞，不标记完成。只提交本次任务文件，保留用户已有修改。

真实模型实验必须另外满足研究登记、预算与停止条件。V2 S2 Gate 仍未通过；不得重试已关闭账本、创建 BUDGET-04 或推进后续模型评估。普通工程维护不构成实验启动授权。

## 项目约束

- Agent 只能接收 `Observation`，不得接收完整 `WorldState`。
- Environment、agents、模型客户端、evaluation 和 UI 必须保持独立边界。
- 环境必须确定且先有规则测试，随后 benchmark 才可信。
- 每个运行版本只使用一种 Action contract，所有 LLM 输出在执行前必须校验；Legacy 使用 `legacy_v1`，V3 使用 spec 0017 的 `scenario_v3`，不得混用。
- 每局运行保存一个 JSON Episode Trace，trace 中不能包含密钥或完整思维链。
- 首个 MVP 不引入 LangChain、向量数据库、多 Agent 编排、RAG、数据库存储或复杂 UI。
- `runs/` 和 `results/` 是本地生成物，默认不纳入 Git，除非未来 scope 明确改变该规则。

## 辅助工具建议

Foundation 稳定后按需引入 `pytest-cov`、Hypothesis、pre-commit 和 Rich；它们不是当前架构的必需依赖。当前不安装 MCP、LangChain、RAG、向量数据库或额外 Agent 编排工具。

_这是新 Agent 和新对话的持久入口。工程级事实改变时，用 `/audit` 或 `/sync` 更新本文件。_

## Context files

- [src/agent_arena/AGENTS.md](src/agent_arena/AGENTS.md)：应用包的局部模块边界、运行入口和质量检查。
- [worlds/v4/AGENTS.md](worlds/v4/AGENTS.md)：V4逐关设计约束、离线审计入口和运行时边界。
