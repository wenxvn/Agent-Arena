# V11：Agent-Arena 网页平台与阶段性交付

> **执行对象**：DeepSeek V4.1 Flash（可以使用代码代理、测试工具）；**项目**：https://github.com/wenxvn/Agent-Arena  
> **基准 HEAD**：`eb2f64a281677a0fce881769a6592cce1be6f7d9`（2026-10-19 查询 main）；执行前必须重新核实 HEAD，不得覆盖他人新提交。  
> **版本定位**：产品化交付版本，不是 V10 研究复测、不做论文级实验、不做跨模型能力区分度。  
> **核心目标**：本地浏览器打开网页 → 选择十世界三十图 → 选择模型或离线演示 → 配置 seed/预算 → 启动挑战 → 实时看进度/动作 → 查看结果/回放 → 导出报告；新用户按 README 能独立运行。  
> **最高原则**：**复用 V10 运行时和既有只读 Streamlit UI；不重写 30 张地图、不动历史冻结文件、不拿 Oracle 伪装真实 Agent。**

---

## 0. 已核实的仓库事实与边界

在上述 HEAD 下：

- `src/agent_arena/ui/app.py` + `present.py` 已有**只读 Streamlit 研究回放界面**，通过 `uv run --with streamlit streamlit run src/agent_arena/ui/app.py` 启动；**尚不能在网页中配置/启动 episode 或 benchmark**。必须先审计代码并复用现有展示层，不要另造一套与现有 Trace 不兼容的 UI。
- `pyproject.toml` 是 Python 3.13 项目，依赖 `typer`、`openai`、`pydantic`、`pydantic-settings`；CLI 入口 `agent-arena = agent_arena.cli:app`。Streamlit 当前通过 `uv --with streamlit` 临时安装，不在核心依赖里。
- `src/agent_arena/v10/runtime/catalog.py` 提供 V10 地图目录；`src/agent_arena/v10/contract.py` 提供**类型化公开动作契约**；`src/agent_arena/v10/ledger.py` 提供独立费用账本；`scripts/run_v10_mimo.py` 是现有真实 MiMo 实验 runner。新网页必须通过可复用的**服务层/适配层**使用这些能力，而不是调用 Streamlit 按钮时拼 shell 命令或复制 runner 逻辑。
- V10 报告称 30/30 V10 原生地图通过 8 Gate；152 局有效 MiMo，57 局成功；历史 V8/V9 冻结。**Gate 通过 ≠ 模型必然通关**。
- V10 尚有 MAP-19/20 热控策略失败、古堡 MAP-28–30 路线/预算耗尽等模型能力现象；**本轮不得为了网页好看修改胜利条件或强行提高成功率**。
- README 已有 `uv sync`、CLI、Ollama、OpenAI-compatible `.env`、只读 Streamlit 入口，但文档重点仍是实验研发，尚非交付手册。

**执行前再检查** `README.md`、`docs/architecture.md`、`docs/scope/scope.md`、`docs/v10/final-report.md`、`src/agent_arena/ui/`、`src/agent_arena/v10/`、`scripts/run_v10_mimo.py`、`tests/test_ui_*`、`.github/workflows/ci.yml`、`.env.example`。记录最新 SHA、已有功能、待补功能。不得将本提纲中“缺口”机械认定为最新 HEAD 的事实。

## 1. 产品范围、优先级与完成定义

**目标用户**：一个拥有 Windows/macOS/Linux 电脑、可安装 Python/uv、可能拥有 MiMo/OpenAI-compatible API 的开发者或普通技术爱好者。默认**单机本地部署、单用户、浏览器访问 localhost**。不是互联网公开多租户 SaaS。

### P0：阶段性交付硬门槛（必须全部完成）

1. **30 图最终体验检查**：对每张地图核实公开目标、规则、动作契约、起点、成功/失败反馈和回放可读性；对 MAP-19/20 热控、MAP-28/29/30 古堡链条重点核查说明是否让普通用户理解。发现的是**说明/界面缺陷**就修复说明，不以 MiMo 失败为由修改世界规则。形成 `docs/v11/map-ux-checklist.md`，30/30 留痕。
2. **统一运行入口**：网页一条命令启动，首页可选择 10 世界 30 图；地图、环境 Seed、执行模式、Provider、Agent、决策上限与预算在一处配置。保留原 CLI，必要时新增 `agent-arena web`，但不能要求用户执行多个不明脚本。
3. **模型 API 配置**：`.env.example`、OpenAI-compatible/MiMo 接入、连接检查、无 Key 离线演示；服务端保管密钥、网页只显示脱敏配置。真实付费前显式确认。
4. **结果输出**：每局自动记录稳定 run_id、地图 ID、规则/指标版本、seed、模式、Agent、outcome、动作、公开观察、token/费用（可得时）、失败原因；支持实时进度、历史回放、JSON/CSV 导出。
5. **错误处理与运行安全**：API 超时/拒绝/额度不足、非法动作、模型输出格式错误、预算耗尽、用户取消、页面刷新、进程中断、重复提交、未知费用，均须可理解且 fail-closed；不得无限重试或重复计费。
6. **README 与安装教程**：Windows PowerShell 和 macOS/Linux 可按文档从零安装并启动；包含无 Key 演示、真实 API 配置、常见错误、日志位置和一键自检。
7. **一键验收**：至少提供一个明确的本地验收命令/脚本，自动检查 30 图 catalog、服务层、离线运行、结果导出、预算与脱敏等 P0 核心能力；全量 pytest/ruff/mypy/lock check 作为独立质量门禁。

### P1：网页产品体验完善（V11 应尽量完成；逐项验收）

1. **难度标签整理**：保留 MAP-01～30 稳定 ID 与原 `design_difficulty`；增加独立 `display_difficulty` 和简短 `difficulty_note`。基于动作链、规则复杂度和实际体验作人工可解释调整；不按 3 局 MiMo 胜率机械重排。展示难度可与设计难度不同，不修改运行时与历史 trace。
2. **可视化网页体验**：已有只读 Streamlit 作为基础，补齐地图卡片、任务配置、启动/停止、实时动作时间线、运行状态、回放、结果摘要；优化中文文案、布局、加载态、移动端基本响应式和错误提示。
3. **运行历史检索与对照**：按地图、结果、日期、Provider/模型、Seed 筛选；可对照同版本、同模型的两局或多局结果，版本不一致时警告或禁止直接比较。
4. **新手引导与体验细节**：首次运行引导、地图规则提示、费用提示、失败解释、空状态、无 Key 演示入口；不把内部审计字段直接丢给普通用户。

### P2：锦上添花（列入计划，但不得阻塞 P0 交付）

1. **更丰富的可视化**：十世界主题卡片、地图状态/公开资源的轻量示意、挑战过程进度图、能力指标图；优先用现有 Trace 数据，不能把不可观测的世界真值画给 Agent 看。
2. **本地成绩榜/排行榜**：仅在**同一模型、Agent、规则版本、地图和评分口径**内展示个人历史最好成绩或榜单；标明 seed 与决策预算，避免宣称跨模型公平排名。默认不做联网排行榜、用户系统、公开分数上传。
3. **交付体验增强**：可选桌面快捷启动脚本、演示数据包、网页截图/录屏、UI 主题与可访问性优化；评估工作量后择优实施。

**明确不做**：用户登录、云数据库、多人联机、付费充值、公开部署、跨模型研究比较、论文级统计、复杂 3D 游戏地图、30 图规则重构、历史数据迁移或清洗。**P2 的本地同模型成绩榜不等于跨模型排行榜。**

**执行要求**：DeepSeek 不得以“P0 完成”为由直接忽略 P1/P2；必须逐项评估并尽可能实现。若时间/依赖受限，先保证 P0，再实现 P1，P2 可以标 `DEFERRED` 并给出工作量与下一版入口。P0 未通过禁止宣称阶段性交付完成。

**成功定义**：陌生人从 README 开始，15 分钟内能启动本地网页，完成一局不付费离线演示；有 API 的用户可安全完成一局真实挑战并查看/导出完整记录。15 分钟为体验目标，需实际演练而非口头承诺。

## 2. 推荐技术路线与关键决策

**默认沿用 Streamlit + Python 后端**，不引入 React/Next.js、FastAPI、Redis、Celery、数据库，除非 Batch 0 证明 Streamlit 无法满足必要的执行/停止/状态隔离要求。理由：已有 Streamlit 只读 UI、Python 地图/指标/Provider/账本，单机单用户场景成本最低。

必须先完成技术小样（Spike）：

- 用独立 Python `RunService` 实现 `create_run(config) -> run_id`、`get_run(run_id)`、`cancel_run(run_id)`、`list_runs()`、`load_replay(run_id)`；UI 不直接创建环境或调 Provider。
- 后台任务采用**受控线程/进程**（根据现有 runner 同步/异步特点选型）；执行状态必须持久化到 `runs/web/`，页面 rerun/刷新不能重复调用模型。若进程终止，恢复后历史状态显示 `INTERRUPTED`，不可假装仍在运行。
- Streamlit 仅承担展示和操作，任务状态由服务层与持久化存储决定。服务层不 import Streamlit，可单元测试。
- 如现有 `scripts/run_v10_mimo.py` 难以复用，应提取公共执行核心并保持 CLI 兼容；**不要通过 subprocess 启动无界批量 runner**。离线演示与真实 Agent 共用结果 schema，但必须显式标记模式。
- 如确实必须改技术栈，提交简短 ADR，比较 Streamlit 复用成本、并发/取消、安全与部署复杂度；未经证据不默认前后端分离。

### 建议模块布局（可按现有结构调整）

```text
src/agent_arena/
  web/
    service.py          # RunService：提交/查询/取消/恢复
    schemas.py          # RunConfig/RunStatus/RunSummary/ReplayView
    execution.py        # V10 单局执行适配，事件回调
    store.py            # 原子化 manifest + append-only event log
    catalog.py          # 30 图公开元信息与展示难度
    safety.py           # 预算、密钥脱敏、路径限制
  ui/
    app.py              # 保留入口；升级为可操作网页
    present.py          # 复用现有 Trace 展示
    pages/              # 如有必要：主页、挑战、运行、历史、设置
    components/         # 状态、进度、结果、地图卡片
  ...
tests/test_web_*.py
docs/v11/
```

## 3. Batch 0：盘点与冻结（零 API）

**产出** `docs/v11/00-audit.md`：

- 最新 HEAD、工作树、现有 UI 页面/功能、运行入口、provider 配置方式、trace/指标格式、已有 CI。
- 30 图 V10 catalog 与 CLI 运行路径的对应表；验证不存在只在旧 V3/V8 可用的 UI selector 混用。
- 现有 `run_v10_mimo.py` 的预算、停止、事件输出、seed、prompt/metric/rule hash、恢复语义；明确哪些可直接复用、哪些需要适配。
- 列出 V11 最小实现任务和风险，按 P0/P1/P2 排序；不改任何地图规则。
- 执行基础测试并保存真实退出码；如测试依赖未安装或 `runs/v10` 本地缺失，注明，不虚构通过。

**Gate 0**：审计文档 + 可执行架构草图 + 明确单局真实运行适配方案；若无法确认预算防护，不得进入付费测试。

## 4. Batch 1：稳定服务层（零 API）

- 设计不可变 `RunConfig`：`map_id`、`environment_seed`、`mode`、`provider_id`、`model`、`max_decisions`、`max_requests`、`max_input_tokens`、`max_output_tokens`、`max_cost_cny`（能计价时）、`created_at`、`schema_version`；提供字段范围验证，避免用户无限输入。
- 设计状态机 `CREATED -> QUEUED -> RUNNING -> {SUCCEEDED, FAILED, BUDGET_REACHED, CANCELLED, PROVIDER_ERROR, INTERRUPTED}`；另设 `CENSORED`/指标五态，不要混为一谈。记录 `run_id`、`attempt_id`、开始/结束时间、rule/prompt/metric schema hashes。
- 以**单局串行**为默认（全局仅一个付费任务），并发第二局明确拒绝或排队；防重复点击使用 idempotency key。绝不依赖 Streamlit session state 作为唯一任务事实来源。
- 持久化：每次状态转换原子写 manifest（临时文件 + rename），动作/事件追加 JSONL，结束写 `result.json`；中断保留可读部分记录。跨平台考虑 Windows 文件锁与原子替换。
- `cancel_run` 设置协作式停止标记：每次模型请求前、每个环境 step 前检查；不能保证立刻中止已发出的网络请求，UI 明示“停止将在当前请求结束后生效”；超时与异常必须封账。
- 路径固定在受控输出目录，run_id 使用受限字符集，禁止客户端传入任意本地路径；导出文件也只能来自白名单运行目录。

**Gate 1**：无需网络的假 Provider / 假运行时覆盖状态迁移、重复提交、取消、崩溃恢复、损坏日志容错、并发互斥、非法参数、越权路径。

## 5. Batch 2：30 图 catalog 与难度展示（零 API）

- 从 V10 catalog 生成十世界 × 三张地图的**稳定映射**，不得手填 30 份与源不一致的重复数据；显示世界名、地图名、机制摘要、原始 map_id、设计难度。
- **MAP-01…MAP-30 编号一律不改**；不交换 ID、不修改历史结果的 map_id，不重写世界顺序。
- 可新增 `display_difficulty`（简单/中等/困难/待校准）与 `difficulty_note`；依据 V10 `difficulty-calibration.md`、地图动作数、认知任务与玩家直觉给出初版，不机械用 MiMo 3 局成功率重排。
- 不强求一个世界三图展示难度各有一个；如希望三档齐全，仅允许在**展示层**人工调整并注明主观性，不影响 V10 规则/指标。
- 首页提供按世界、难度、机制筛选；地图详情明确“目标、公开操作规则、预计复杂度、成功条件、失败条件”，不能泄露封存真值/Oracle。

**Gate 2**：30/30 地图可从网页选中并映射到正确的 V10 运行时；公开数据无隐藏答案泄露；难度标签不污染原始数据。

## 6. Batch 3：离线可用的完整网页流程（零 API）

页面至少包括：

1. **首页/地图大厅**：十世界卡片、30 图目录、可筛选；清晰导航。
2. **挑战配置**：地图详情、seed、执行模式、模型选择、预算；默认“离线演示（不花钱）”。
3. **挑战进行中**：进度条、当前状态、动作时间线、公开 Observation、Agent 简短 `decision_reason`、模型请求数、token/费用估计、停止按钮。不得展示内部隐藏状态、完整思维链或密钥。
4. **结果页**：成功/失败/中断明确区分；关键指标、分数、动作数、失败原因、资源消耗、版本 hash；结果解释来自环境/指标，不编造自然语言结论。
5. **历史与回放**：列出本机 runs，按地图/时间/状态筛选；按步骤回放，兼容 V10 JSONL 和已有只读 UI 的 trace 读取方式；导出 JSON 和 CSV（CSV 需要清晰字段和 UTF-8 BOM 兼容 Excel 可选）。

**离线演示不能使用封存 Oracle 冒充自主 Agent**：若采用公开 Oracle/脚本路线，页面明确标注“规则脚本演示/Oracle 演示，非模型挑战”；更推荐 Fake Provider 或公开策略，且在结果元数据中留痕。

视觉原则：中文优先、深浅色兼容、宽屏/笔记本适配、页面布局简洁、操作按钮可见、空状态/加载/失败状态完整；不要为了炫酷 3D 牺牲运行稳定性。避免 30 张地图全部铺满一屏。

**Gate 3**：无 API Key 的全新环境完成“打开网页 → 选图 → 离线运行 → 查看回放 → 导出”，至少在 Windows 和一种其他 OS 上测试；网页刷新不会重复执行。

## 7. Batch 4：真实模型挑战与费用保护（先假 Provider，再小额 API）

- Provider 选择只暴露已经实现且验证可用的模式；至少支持现有 OpenAI-compatible（MiMo 可通过该协议接入），本地 Ollama 如原架构可用则复用；不新增第二模型供应商的研究实验。
- `.env` 保存 API Key、base URL、model；**不在网页显示或回显完整密钥**，前端不允许提交任意自定义 API URL（避免 SSRF/本机网络滥用）。若要允许自定义地址，仅在本机配置文件/环境变量中设置并验证。
- 首次付费运行明确展示 Provider、模型、地图、seed、决策/请求上限、**费用上限与估算的不确定性**，用户主动确认后才发请求；离线默认不发请求。
- 每次请求前检查余额预留与硬限制；异常/超时/未知消费 fail-closed，不自动无界重试；记录 token 与可确认的费用，不支持精确计价时以请求/token 上限作为硬门禁，**禁止假称人民币费用可精确限制**。
- 只支持一局一次运行；不默认自动补跑、不自动启动 30 图全量测试；重试需要明确点击并生成新的 `attempt_id`。
- 记录 Provider error 分类，给出可操作提示（密钥未配、连接失败、限流、模型不可用、动作格式错误、超时、预算耗尽）；不能在网页日志中泄露响应头或密钥。
- 先用 Mock API 验证预算、取消、重试、账本一致性，再执行**至多 2–3 局**真实 MiMo 冒烟测试。**V11 自动测试 API 总预算上限 ¥3**（独立账本，包含未知预留）；不要把 V10 的剩余额度当作 V11 可用余额。若未能确认计价或密钥不可用，标记真实 API Gate 待验证，不得伪造成功。

**Gate 4**：真实模型启动/执行/结果完整闭环；无密钥时明确提示并仍可离线体验；成本可追溯，异常可恢复。

## 8. Batch 5：结果展示、解释和导出（零 API）

- 显示 V10 主指标、单位、范围、五态（VALID/CENSORED/NOT_APPLICABLE/MISSING/INVALID），不能将 CENSORED、N/A 和缺失渲染为 0。
- 区分 `run outcome` 与 `metric status`，对“模型已尝试机制动作但阈值没到”等情况使用已有 `failure-attribution` 的**可证实**信息，不要凭空猜测模型意图。
- 成绩比较只允许同一 `map_id + rule_hash + metric_schema_hash + 评测模式` 的运行，跨版本只做并排展示并提示不可直接比较。
- 支持导出：单局原始公开 Trace JSON、逐动作 CSV、摘要 JSON；默认排除密钥、隐藏世界真值、完整内部 prompt、未脱敏 Provider 响应。
- 复用已有 `ui/present.py` 的安全展示；旧 V8/V9/CLI trace 不保证全兼容，先探测格式，不支持时给出“旧格式不可回放”的明确提示，不得 silently misparse。

**Gate 5**：成功/失败/截尾/中断/费用未知各有 golden fixture；页面与导出数值一致；不泄露敏感数据。

## 9. Batch 6：质量、安装、文档与交付包（零 API）

- 提供单一推荐启动命令，例如 `uv run --with streamlit streamlit run src/agent_arena/ui/app.py`，若增加可选依赖则记录原因；保留 CLI 原有入口不破坏。
- 编写 `docs/v11/quickstart.md`（Windows PowerShell + macOS/Linux）、`user-guide.md`（选图/运行/停止/回放/导出）、`configuration.md`（.env、Provider、预算、常见错误）、`architecture.md`（数据流和安全边界）、`release-checklist.md`。
- README 首页改为“快速启动网页 + CLI 可选 + 研究资料入口”，保留既有研究事实但不让新用户先读几十页历史实验。
- `.env.example` 只保留假值，`.gitignore` 检查 `runs/web/`、账本、API 密钥、缓存；确保 `git status` 不出现凭据或真实付费 Trace。历史研究 `runs/v8/v9/v10` 不要清理。
- 单元/集成测试：catalog 30 图、运行状态机、取消、幂等、持久化、预算门禁、脱敏、指标五态、导出、UI smoke；尽量通过 mock 完成，不消耗真实 API。
- 运行 `uv run ruff check .`、`uv run mypy src`、`uv run pytest -q`、`uv run uv lock --check`、`git diff --check`；记录实际退出码；CI 加入 web smoke 和 V10 `recompute --check`（如 CI 无历史 runs，则采用可提交的小型 fixture 或有条件的验证路径，不能依赖未入库大文件）。
- Windows/Ubuntu/macOS 至少进行两个系统的启动检查；若执行环境无法覆盖，明确列为未验证，不虚报。
- 可选：生成 `v0.2.0-web-preview` 候选标签，但**未经用户确认不要推送正式 release/tag**。

**Gate 6**：全新安装演练 + 全 P0 流程通过 + 质量检查可复现 + 文档与代码一致。

## 9A. Batch 7：P1/P2 产品体验冲刺（P0 通过后执行）

- **P1-1 难度展示**：完成 30 图的 `design_difficulty` / `display_difficulty` / `difficulty_note`，在地图大厅显示标签解释；原 ID、规则 hash 和历史文件保持不变。
- **P1-2 网页细化**：地图卡片、运行进度、动作时间线、终局摘要、失败解释、响应式布局、空状态和首次引导。优先复用 `ui/present.py`。
- **P1-3 历史筛选与对照**：支持按地图/时间/结果/模型筛选；仅对同规则/指标版本的数据做直接对照，混合版本时清楚标注。
- **P2-1 可视化增强**：若 P0/P1 稳定，增加公开状态资源图、进度图、世界主题视觉，但不引入复杂 3D 引擎。
- **P2-2 本地同模型成绩榜**：若有充足时间，提供同模型/同地图/同版本范围内的历史榜单，明确 seed/预算差异；不接入跨模型排行。
- **P2-3 快捷启动与演示素材**：Windows/macOS/Linux 启动辅助脚本、演示截图、可选示例 Trace。

**Gate 7**：P1 每项都有可见网页效果及测试/截图证据；P2 每项明确 `DONE` / `DEFERRED` / `BLOCKED`，未完成原因与下一步写入 `docs/v11/backlog.md`。**P2 不作为 `WEB_PREVIEW_READY` 硬门槛。**

## 10. 执行节奏与交付物

每 Batch 都要：先说明变更范围 → 实现 → 运行测试 → 记录结果 → 小提交 → 更新 `docs/v11/progress.md`。尽量每个 Batch 单独 commit，避免一次性重构。

必须生成：

```text
docs/v11/
  00-audit.md
  architecture-decision.md
  progress.md
  difficulty-display.md
  ui-pages.md
  safety-and-budget.md
  quickstart.md
  user-guide.md
  configuration.md
  test-report.md
  release-checklist.md
  final-report.md
  map-ux-checklist.md
  backlog.md
```

`final-report.md` 必须回答：

1. 当前 HEAD、变更提交列表、运行入口；
2. 30 图是否都能选、能否启动、能否回放；
3. 离线/真实模式各自完成了哪些端到端测试；
4. 取消、刷新、并发、Provider 错误、费用保护是否通过；
5. 数据/密钥泄露测试、版本哈希与指标五态是否正确；
6. P0/P1/P2 各项的 DONE / DEFERRED / BLOCKED 状态、证据、哪些 OS 未测试；
7. 真实 API 调用了几局、多少请求、花费多少、未知消费多少；
8. 是否可以标记 `WEB_PREVIEW_READY`，若不行具体阻塞是什么。

## 11. 明确停止规则和验收口径

- **绝不**为 UI 开发修改 V10 30 图规则、成功条件、Oracle、指标公式或历史冻结账本。
- **绝不**为了展示漂亮把失败局改成成功、把脚本演示当真实模型、把 0/3 改成难度标签的唯一依据。
- **绝不**自动进行跨模型评测、90 局批量 MiMo、重复 seed 统计、论文实验。
- **绝不**允许无限预算、无限重试、后台无感付费、前端暴露 API Key。
- **绝不**默认向公网暴露网页；默认只监听 `127.0.0.1`，远程访问须另做安全设计。
- 发现现有 Streamlit 架构不支持安全取消/状态恢复，先提交可复现问题与 ADR，再选更合适的最小架构；不能悄悄引入大堆依赖。
- 如果 API 无法调用，继续完成全部离线功能，将 `REAL_API_SMOKE` 标为 `BLOCKED`；不得假称 V11 已完成全部 P0。

**最终验收标准**（P0 为硬门槛，P1 应尽量完成，P2 可延期）：

| 验收项 | 必须满足 |
|---|---|
| MAP catalog + 体验检查（P0） | 30/30 可选择、稳定 ID、公开信息正确；30 张逐图 UX 清单 |
| 离线挑战 | 新用户零密钥可运行、可回放、可导出 |
| 真实挑战 | 有 API 时单局闭环；未配置时安全拒绝 |
| 任务控制 | 不重复提交、可停止、异常可恢复、串行付费 |
| 费用 | 请求/token/金额（可计价时）有硬门禁，未知消费封账 |
| 结果 | outcome/metric 五态准确，版本 hash 完整 |
| 安全 | 无密钥/隐藏真值泄露，无任意路径读取 |
| 质量 | 新旧测试通过，CI 有最小 UI/服务 smoke |
| 文档 + 一键自检（P0） | Windows + macOS/Linux 启动说明、故障排查及统一自检命令 |
| 难度/历史/体验（P1） | 逐项说明完成状态，展示难度不改 MAP ID/规则 |
| 可视化/本地同模型榜（P2） | 尽力完成；未完成登记 backlog，不阻塞 P0 交付 |
| 版本 | 不修改 V8/V9/V10 冻结数据和规则 |

**通过后输出 `WEB_PREVIEW_READY`（本地网页预览版）**，而非“公网生产环境就绪”；未通过列出具体阻塞和最短修复路线。不要为了凑 100% 而虚报。

---

## 12. 给 DeepSeek 的直接执行指令

> 请以当前 GitHub main 的最新提交为准，先审计而后开发。V10 的 30 张地图、规则、指标和测试是现成资产，V11 只负责把它们做成可在本地浏览器使用的交互式平台。优先复用现有 Streamlit 只读 UI、V10 catalog/contract/runner/ledger，不要重写地图或造第二套评测系统。按 Batch 0–7 分批执行，自动完成零成本任务和测试；只有在预算保护与 Mock 测试通过后，才允许在 ¥3 独立总预算内做至多 2–3 局 MiMo 冒烟。保留真实运行记录、每批提交和可复核验收证据。**必须覆盖本提纲 P0/P1/P2 全部任务**：P0 全部验收，P1 尽力落地，P2 尽力实现或在 backlog 中明确延期。最后给出本地启动命令、截图路径、P0/P1/P2 状态表、最终报告及 `WEB_PREVIEW_READY` 是否成立。若发现提纲与最新代码冲突，以事实为准并在 ADR 解释，不要照抄错误假设。
