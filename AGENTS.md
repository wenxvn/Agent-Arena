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
- V10 30 图核心机制重构、难度校准与多 Seed 有效性验证已完成 Batch 0–9：`src/agent_arena/v10/` 提供 **30 张原生运行时**（V8 回退 0）、v10 五态指标（154 旧 + 172 新）、39 份 DCR、多 seed 基线、独立 ¥10 共享账本、类型化公开动作契约、公式级指标复算、trace 级失败归因与 8 项验收 Gate；`docs/v10/` 交付 `final-report.md`、30 张逐图审计卡 `maps/MAP-XX.md`、状态矩阵、难度定标、构念效度、指标独立复核、公式级复算、失败归因、MiMo 结果与成本账本审计。离线：30 图 × 144 seed 实例 0 违规、回放确定 30/30、seed 互异 30/30、主指标第二套实现 30/30 图 1093 次检查全一致。真实 MiMo：159 局记录（152 有效 + 7 中断保留）、成功 57/152、结算 CNY `2.27994884` + 未知预留 `0.13312000` = `2.41306884`；重复运行覆盖 MAP-01–12（36 对，成功率一致 0.8889）。发现并修复五类系统性测量缺陷：动作契约只列字段名不列类型（DCR-V10-24）、MAP-20 取值结构未公开（DCR-V10-25）、整数字段区间未公开（DCR-V10-28）、被预算截断的局漏判 `CENSORED`（DCR-V10-26）、时间推进语义未公开（DCR-V10-38/39，MAP-20/19）；MAP-05 / MAP-02 / MAP-27 / MAP-01 / MAP-25 / MAP-17 / MAP-16 已按 DCR-V10-27/29/30/31/33/34/36 完成原生 seed 化，MAP-13/14/21 的公式级复算按 DCR-V10-35 补齐；MAP-20/19 的 wait 语义按 DCR-V10-38/39 补进公开规则。当前 30 图状态 **30 VALIDATED**（30 张原生图 8 Gate 全过），`NEEDS_MORE_EVIDENCE`/`NEEDS_REDESIGN`/`BLOCKED`/`BYPASS` 全为 0。全部结论 `agent_reviewed`，未发生 `human_approved`。详见 `docs/v10/README.md` 与 `docs/v10/final-report.md`。
- V11 本地网页平台已完成（`WEB_PREVIEW_READY`，单机预览）：新增 `src/agent_arena/web/` 服务层（RunService、manifest/JSONL/result、单局预算、取消、恢复、跨进程锁、catalog、导出、自检）与可操作 Streamlit 页面；`uv sync --extra web` 后 `uv run agent-arena web` 一条命令启动（Streamlit 已锁定在 `uv.lock`）。30/30 图离线可启动/回放/导出（473 步），浏览器逐图映射 30/30；真实 MiMo 冒烟 3 局（MAP-01/19/30，58 次已记录请求，结算 ¥0.04637556 + 未知预留 ¥0.073728 < ¥3，0 成功）。Windows 干净安装 176.9s 首次 / 87–96.5s 复跑（无 `.env`，自检 7/7）；Ubuntu CI success；1240 pytest passed、mypy 0 issues、ruff clean、freeze/recompute/independent 全绿。P1/P2 已补齐筛选、2–4 局对照、失败归因、trace JSONL、演示数据包、启动/桌面快捷方式与版本 0.2.0；macOS 实机仍未验证。详见 `docs/v11/final-report.md`。不修改 V8/V9/V10 冻结资产。
- V12 Agent Arena Lab 1.0 已完成并含真实模型验证（`LAB_1_0_READY`）。`src/agent_arena/lab/` 提供版本化契约（`v12-lab-1`）、策略注册表、受控 `DecisionGateway`、`AgentRunnerV12`、父 Experiment + 子 Run 队列（复用 V11 `RunService`）、配对比较、20 类证据级诊断与轨迹 Diff、六图 view-model、CSV/JSON/Markdown 导出与报告、第三方 SDK 与只读导入、可访问性审计、四类衍生实验（补充 / 版本复跑 / 预算扩展 / 重复）、运行时版本指纹、V12 研究投影指标与路线日志消融；`src/agent_arena/ui/lab.py` 新增 Lab 三页。三种执行通道严格隔离：`OFFLINE`（V11 语义不变）、`SIMULATED`（零费用、不写付费账本）、`LIVE`（需显式 `LiveApproval`）。`basic.v1` 与 V11 `execute_live` 在同一 Provider 下动作序列/请求文本/预算语义逐项一致；Planner/Reflection 额外请求全部计入。真实 MiMo：**159 局 / 20 个实验**（Pilot 6 + 主矩阵 54 + 主矩阵补充 1 + MAP-22 三版 27 + MAP-30 两档扩展 18 + 种子覆盖 10 + 重复 36 + 路线日志 3 + 三条开关消融 12 + 探针 1 + 早前补充 1），结算 **¥5.43680012**、未知消费 ¥0、未超 ¥6 批准上限；主矩阵 54/54、有效分母 53、成功 24（basic 7 / memory 8 / planning 9，描述性）。发现并修复 **DCR-V12-01**（`facts` 契约无法表达内部字段名，MAP-22 `write_memory` 96.2% 被拒 → 补丁后 0%）；**DCR-V12-02**（`route_recall` 键名口径未公开 → 新增 `v12-contract-2` 与 `v12.projection.*` 研究投影，9/9 N/A → 6/9 VALID）；**DCR-V12-03**（键名修好后模型只写 1–4 个方位 vs 路线 22–44 步 → 策略侧；`route_log` 消融把 `route_recall` 从 0 拉到 0.45–1.0，seed 2 通关）；**DCR-V12-04**（MAP-30 地板实为约束阶梯 90 请求 → 200k token → ¥0.20，抬到 180 请求后 4/9 走到法庭且 `ACCUSATION_REJECTED`）；**DCR-V12-05**（反思触发器在 MAP-16 从未激活——两臂 `reflection_triggered` 均为 0，该消融本轮不可回答）。**DCR-V12-06**（给 `memory.v1` 加默认关闭的 `route_log` 键后，默认配置表变化导致所有历史 `memory.v1` 的 `prompt_hash` 改变；6 组重复实验因此不可配对，翻转率口径收紧为 22.2%–25.0%）。同条件重复（18 格，2 次观测翻转率 **22.2%**、3 次观测 **25.0%**，6 组跨版本已排除）表明 1 次/条件不足以下架构结论；仅 `planning@MAP-16 seed 1` 为 3/3。验证：**1525 pytest passed**、mypy 306 文件 0 issues、ruff clean、freeze 9/9 unchanged、recompute 1093/1093、independent 0 violations、`verify_v11` 7/7、`verify_v12` 15/15、可访问性 0 critical/serious/moderate、V11/V12 浏览器 E2E 均通过。macOS 与 Ollama 按用户指示暂缓。详见 `docs/v12/final-report.md`、`docs/v12/mimo-results.md`、`docs/v12/ablations.md`、`docs/v12/gap-audit.md` 与 `docs/v12/dcr/`。

- V14 Agent Arena Lab 1.2（Stage II Final Evidence & Delivery）离线/工程部分已完成（`ENGINEERING_VERIFIED` / `LIVE_PARTIAL`；用户授权后真实 MiMo（flash + pro）执行 **265 局 / 8 177 请求 / ¥4.77211952**（方案 A + 五轮补充，3 次 `unknown_spend` 各自停批且未重试，0 重复 0 孤儿）：**E2-a planning.v2 跨模型与留出 seed 复现** —— MAP-16 flash off **0/25** vs on **14/15 有效局**，MAP-16 **pro** off **2/12** vs on **12/12**（留出 seed 3 `0/3 → 3/3`，off 臂 2–3 决策即 DEADLOCK），MAP-18 flash `2/9 → 4/9`，负向对照 **MAP-26 天花板 9/9→9/9（无损害）**、**MAP-14 地板 0/9→0/9（无效）**；**E1-a route_log** 仅在 MAP-22 seed 2 且 ≥150 请求有效（`2/9 → 8/8`），seed 0/1/3 两臂全 0，每成功局 ¥0.283→¥0.059，公开轨迹归因显示写入全部成立而仅 seed 2 折返下降 → 瓶颈是「记录未被使用」（DCR-V14-06/07/08），且 `route_write_every=1` 的修复尝试为负向（recall 0.977 仍不降折返，DCR-V14-09）；**E3 reflection.v2** 暴露已稳定且出现方向性正向（MAP-22@150 seed 2 每臂 13 局：`trigger_only` **3/13** vs `on` **7/13**，Fisher p=0.226、Wilson 区间重叠 → `TENTATIVE`，未达显著）；**仍不是** `STAGE_II_FINAL_READY`）。`src/agent_arena/lab/v14/` 提供只读分析层：8 元组观测条件身份与三档可比性判定、未知/零分离的效度口径、协议隔离、MAP-30 三维预算阶梯与保守区间、诊断锚点三态与正反 fixture、六维能力画像缺口、结论强度三字段、Lab 视图（首次分歧高亮 / seed 分组 / MAP-22 不画被拒移动 / MAP-30 阶梯 / 可比性门禁）、冷启动与异常负载实测、导出一致性与 SDK 加固、账本复算（159/159、5641 请求、¥5.43680012、0 重复 0 孤儿）、LIVE 方案 A 预注册（54 局 / ¥2.11 预估 / ¥5.00 上限，`PLANNED_ONLY`）。修掉 5 个实质测量缺陷：`validity_markdown` 把未知机制触发渲染成 `0/N`、V13 预算表算术（逐行 221 写 229）、`DCR-V14-01`（历史 CSV 缺 `contract_version`/`prompt_hash`）、`DCR-V14-03`（`memory.v2` 在 `env_write` 下的分母口径）、配对只用 `(map, seed, agent)`。`lab-e2e` 已改为**阻断**门禁（切换前连续 7 次成功；切换后第一红灯 `40477841302` 保留并修复，随后连续 5 次成功）。验证：**1790 pytest passed**、mypy 334 文件 0 issues、ruff clean、freeze/recompute/independent 绿、`verify_v11` 7/7、`verify_v12` 15/15、`verify_v13` 18/18、**`verify_v14` 14/14**、`e2e_lab` 与 `a11y_v12 --browser` 通过（0 critical/serious/moderate）。详见 `docs/v14/`。
- V13 Agent Arena Lab 1.1 深化已完成（`LAB_1_1_ENGINEERING_READY`；**本轮 0 局真实付费请求、CNY 0**，真实模型效果 `WAITING_USER_APPROVAL`）。`src/agent_arena/lab/v13/` 新增只读分析层：可比性画像与单变量检查、重复稳定性（翻转率 + Wilson 描述区间 + 按 seed 分块）、单因子消融模板与证据包、六图构念效度与 MAP-30 预算阶梯、七层失败归因、六维机制画像、零 LLM 模板报告、本地账本审计与脱敏账单对账、SDK 8 项自检、1k/5k 压力测试；`src/agent_arena/web/index.py` 提供懒加载 + mtime 增量刷新 + 服务端分页；`ui/lab.py` 扩到五页（新增「稳定性与效度」「报告与审计」）。契约只增字段（`v13-lab-1`，`schema_version` 仍为 `v12-lab-1`）：`replicates` / `replicate_index` / `SamplingProvenance` / `ProtocolManifest` / `experiment_kind`；`replicate_index=0` 时 `condition_key` 与 V12 逐字一致。新增 `memory.v2`（路线只累积被接受 move、`env_write`/`context_only` 显式区分、三类瓶颈）、`planning.v2`（adaptive/initial_only/periodic + TTL + 预算感知 + 逐请求成本）、`reflection.v2`（eligible/triggered/冷却/额度/误触发/恢复 + trigger-only）；v1 一字未改。复算 V12：2 次观测翻转率 **22.22%**、3 次观测 **25.00%**（排除 6 组跨版本）、159 局 / 5 641 请求 / **¥5.43680012** / 0 孤儿 / 0 重复结算，全部一致。六图构念效度：MAP-08/26 `CEILING`、MAP-16/18/22 `SUITABLE`、MAP-30 `CENSORED`。验证：**1639 pytest passed**（V13 新增 114 项）、mypy 323 文件 0 issues、ruff clean、freeze 9/9 unchanged、recompute 1093/1093、independent 0 violations、`verify_v11` 7/7、`verify_v12` 15/15、`verify_v13` 18/18、`e2e_web` 与 `e2e_lab`（含两个新页面 + SDK 自检）通过、可访问性 0 critical/serious/moderate。CI 浏览器 E2E 仍 `continue-on-error`（`NOT_VERIFIED`）；Provider 后台账单对账 `BLOCKED_EXTERNAL`。macOS 与 Ollama 按用户指示暂缓。详见 `docs/v13/final-report.md`、`docs/v13/gap-audit.md`、`docs/v13/validation-report.md` 与 `docs/v13/decisions.md`。

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
