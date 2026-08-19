# Agent Arena 工程事件记录

这份记录只保存重要的工程事件，不替代 scope、spec 或 Git 历史。

记录范围包括：阶段开始或完成、架构决策确认或修改、重要验证结果、阻塞及解决、开发优先级调整。

每条记录使用以下结构：

```text
## 日期 事件名称

事件：发生了什么
原因：为什么做
改动：主要文件或范围
验证：运行了什么，结果如何
下一步：接下来做什么
关联提交：Git commit，若有
```

## 2026-08-19 研究状态文档同步

事件：同步日常研究摘要、scope 和当前问题记录，使其反映 Release 2 已完成以及纯模型自主通关基线已完成但未通过的事实。

原因：`研究总纲.md` 仍描述项目尚未创建源代码，scope 和问题记录的下一步也仍写为重新建立已完成的真实 Ollama 对照，容易使新对话从过期阶段开始工作。

改动：将当前阶段改为已完成 Foundation 至 Release 2；记录 `qwen2.5:7b` 下 ReactAgent 与 MemoryAgent 各 5 局、均未成功的通用 prompt 基线；将下一步收敛为不含谜题答案的通用运行时上下文或受控短期历史实验，并保留 Streamlit、PlanningAgent 和 ReflectionAgent 的后置条件。

验证：`uv run ruff check .`、`uv run mypy src` 和 `uv run pytest` 通过；pytest 共 49 项通过。

下一步：为通用运行时上下文或受控短期历史建立独立技术设计和公平实验对照，不能将结果并入纯模型基线。

关联提交：待提交。

## 2026-08-19 Hiyo Responses provider 与自主通关复验

事件：接入 Hiyo OpenAI-compatible relay 的原生 Responses API，并复验 `gpt-5.6-terra` 的辅助和纯自主逃生表现。

原因：CCSwitch 配置声明该中转站使用 `wire_api = responses`；此前 Chat Completions 兼容调用虽然可连接，但纯 Agent 在错误工具反馈后频繁输出非法 Action，不能排除协议适配差异。

改动：新增显式 `openai` provider，使用 `/v1/responses`、结构化 JSON 输出和 `store=false`；更新本机 `.env`、远程验证脚本及配置文档。保留 Fake 为仓库默认，避免无密钥 CI 误发真实请求。

验证：`gpt-5.6-terra` 模型验证通过；`planner_assisted` seed 0/1/2 共 3 局均在 19 步成功逃生、0 次非法输出；ReactAgent 和 MemoryAgent 的通用 `--autonomous` seed 0 均在第 2 步后达到 `invalid_action_limit`。Ruff、mypy 和 52 项 pytest 通过。

结论：该模型适合当前公开规划辅助演示，但尚不能作为纯自主通关模型。后续 benchmark 必须分开记录辅助与自主结果。

关联提交：待提交。

## 2026-08-19 调整自主通关优先级并暂缓 14B

事件：确认 ReactAgent 和 MemoryAgent 的代码实现、Fake provider 路线和公平对照测试已经完成，但真实 Ollama 的纯模型自主通关仍未完成。用户使用 Mac M5 Air，`qwen2.5:14b` 暂不继续测试。

原因：`planner_assisted` 的成功依赖确定性公开阶段和下一动作建议，不能证明模型在没有谜题攻略式提示时具备自主规划能力。继续堆 Spaceship 专用提示词会把实验变成人工攻略执行，削弱研究结论。

改动：将“不依赖谜题攻略式提示的纯 ReactAgent 与 MemoryAgent 自主通关验收”提升为当前首要未完成任务，要求使用通用 prompt、相同 seed 和预算，并独立保存成功与失败 trace。将 14B 标记为受 M5 Air 资源限制而暂缓，不纳入当前实验矩阵。

验证：复核 `docs/scope/scope.md`、`docs/current-issues.md`、`docs/model-passage-options.md`、ReactAgent 与 MemoryAgent spec 及历史记录，确认两者已完成实现级验证，但真实自主通关验收没有完成。

下一步：先完成通用 prompt 下的 ReactAgent 与 MemoryAgent 真实 Ollama 对照，再根据 trace 决定是否需要运行时循环检测或其他独立实验变量；之后才进入 Streamlit。

关联提交：待提交。

## 2026-08-19 通用 Prompt 纯模型自主基线未通过

事件：完成 ReactAgent 与 MemoryAgent 的纯模型自主对照，各运行 5 局真实 Ollama 实验。

原因：验证模型能否不依赖 Spaceship 专用攻略提示、规划辅助或运行时循环提醒，仅根据公开 Observation 和结构化 Memory 完成任务。

改动：新增 `react_v12_autonomous` 通用 prompt。ReactAgent 和 MemoryAgent 默认使用该 prompt。新增 CLI `--autonomous`，关闭 Runner 的循环提醒，并在 trace provenance 中记录 `runtime_feedback_enabled=false`。`planner_assisted` 继续使用独立的 `react_v11` 和辅助路径。

验证：`qwen2.5:7b`、seed 0 至 4、每局 30 步。ReactAgent 0/5 成功，平均 30 步，每局 2 次环境拒绝，非法输出 0。MemoryAgent 0/5 成功，平均 30 步，每局 15 次环境拒绝，非法输出 0。Ruff、mypy 和 49 项 pytest 全部通过。

结论：纯模型自主通关仍未完成，但失败基线已经真实且可重复。ReactAgent 在初始观察后连续重复 `look`，MemoryAgent 在控制室和走廊之间反复读取不可见终端。问题集中在公开 Observation 的行动选择和失败后的状态更新，不是连接或 JSON 格式问题。

下一步：先设计不含谜题答案的通用运行时上下文或受控短期历史实验，并将其与当前基线独立比较；不得直接恢复 Spaceship 专用路线提示。

关联提交：待提交。

## 2026-08-17 架构决策确认

事件：项目采用 Python 3.13、uv、本地分层单体、CLI 和本地 JSON 文件作为第一版基础架构。

原因：先建立一个可重复的本地 Agent 研究闭环，避免过早引入服务、数据库和复杂编排。

改动：接受 `docs/specs/0001-project-architecture/`，明确 Environment、Agent、LLM、Evaluation 和 UI 的边界。

验证：架构检查清单已建立，真实模型调用被明确为手动验证，不进入默认 CI。

下一步：完成 Foundation scaffold。

关联提交：`c630729`

## 2026-08-17 Foundation scaffold 完成

事件：项目已经可以安装、运行 CLI、生成 Fake episode，并执行自动质量检查。

原因：为确定性的 Spaceship Escape 环境提供稳定的代码和测试基础。

改动：新增 `pyproject.toml`、`uv.lock`、`src/agent_arena`、RuntimeSettings、Fake provider、CLI、测试和 GitHub Actions。

验证：`uv lock --check`、Ruff、mypy 和 10 项 pytest 全部通过。`uv run agent-arena run` 成功生成 JSON episode，百炼模型验证也成功返回确认文本。

下一步：运行 `/architect Spaceship Escape 环境`，定义房间、工具、物品、非法动作和胜利条件。

关联提交：`fe42515`

## 记录规则建立

事件：增加工程事件记录文件和对应 workflow 规则。

原因：scope 只保留当前状态，spec 只保留技术决策，Git 只保留代码差异，三者无法单独表达重要事件的原因、验证和下一步。

改动：新增本文件，并在根 `AGENTS.md` 中定义记录范围、模板和提交前流程。

验证：`git diff --check` 已通过，工作区只包含预期的 `AGENTS.md` 和本文件改动。

下一步：后续每个重要阶段完成时追加一条简短记录。

## 2026-08-17 Spaceship Escape 环境设计确认

事件：确认第一个确定性世界的地图、公开工具、信息边界、谜题状态和逃生条件。

原因：环境规则必须先稳定，后续 Agent Loop、trace 和 benchmark 才有可信对照。

改动：新增 `docs/specs/0002-spaceship-escape/`，并将 scope 中的 Spaceship Escape 环境改为设计完成和实现中。

验证：完成设计访谈与独立只读交叉检查。九项契约空白已补齐，`git diff --check` 通过。

下一步：运行 `/develop Spaceship Escape 环境`，实现配置、Environment 和规则测试。

关联提交：待提交。

## 2026-08-18 本地模型规划辅助通关验证

事件：在保留纯模型失败基线的前提下，完成 `qwen2.5:7b` 的 `planner_assisted` 公开规划辅助通关。

原因：纯 ReactAgent 和 MemoryAgent 在收集工具、恢复电源后会重复公开动作；同时旧 prompt 错误要求所有 `use.item` 必须在背包，和控制终端返回授权码后使用授权码的环境规则冲突。用户目标是让 agent 实际完成逃生，因此需要验证公开辅助是否能稳定解决循环，同时不能把辅助结果伪装成纯模型结果。

改动：新增 `react_v11` prompt，区分维修物品与公开读取的授权码；新增独立的 `PlannerAssistedAgent` 和 CLI `--agent planner_assisted`。规划器只使用公开 Observation、ToolResult 和结构化 Memory 生成阶段/下一动作建议，模型仍选择并返回每个 Action；授权码仅在收到公开 `CODE_READ` 结果后提取。储物室规划优先拾取已出现物品，阶段建议放入最新公开请求，并在 trace 中用独立 agent/prompt 版本标记。

验证：Ruff、mypy 和 48 项 pytest 通过。`qwen2.5:7b`、`planner_assisted_v2`、seed 0/1/2 的 Ollama benchmark 为 3/3 成功，平均 19 步、0 次非法输出、0 次环境拒绝；结果文件为 `/tmp/agent-arena-planner-v11-benchmark/benchmark_20260818T080152Z_planner_assisted_3-seeds_3-episodes_defcc08a.json`。纯模型 MemoryAgent 的失败结果仍保持为独立基线。

下一步：规划辅助结果只用于稳定通关和演示，继续与纯 React/Memory 对照分开统计；若研究需要纯模型成功率，应单独研究更强模型或公开循环保护，不得把规划建议视为模型自主规划。

关联提交：待提交。

## 2026-08-18 用户本机复验与通关记录补充

事件：用户使用 `OLLAMA_MODEL=qwen2.5:7b` 和 `--agent planner_assisted` 在本机连续运行两次，均以 19 步成功逃生。

原因：确认前一轮实验不是临时环境或 Fake provider 结果，并为后续复现明确区分真实模型执行与规划器辅助。

改动：将完整问题、排查步骤、最终路线、复现命令、已完成能力和待办写入 `docs/model-passage-options.md`。确认两份 trace 的模型为 `qwen2.5:7b`、Agent 为 `planner_assisted_v2`，每个执行 Action 都经过模型响应和环境校验；没有程序代替模型执行动作。

验证：两份用户 trace 均为 `success`、19 个 `action_validated`、0 次非法输出、0 次环境拒绝。复核发现 `PublicLoopDetector` 仍可能因状态键缺少 `available_exits` 和 `last_action_result` 而误报合法回程，该问题列入后续任务，不影响本次通关结果。

下一步：先修复循环检测状态键并增加回归测试，再独立实现 `guarded` 模式；继续将纯模型、规则保护和规划辅助结果分开统计。

关联提交：待提交。

## 2026-08-18 本地模型策略验收

事件：完成 Ollama 原生 `/api/chat`、关闭思考、JSON Schema、逐步终端回显和本地模型对照验收。

原因：用户明确只使用本地模型，并希望关闭思考以降低每步延迟；需要区分接口故障与模型策略能力不足。

改动：将 Ollama 默认模型更新为 `qwen2.5:7b`；新增原生请求回归测试；调整 Memory 消息顺序；提示词升级到 `react_v8`，明确公开环境中的关键前置条件和重复动作限制。

验证：`qwen3:8b` 与 `qwen2.5:7b` 的 `verify-model --provider ollama` 均通过，40 项 pytest、Ruff、mypy 通过。`qwen3:8b` 和 `qwen2.5:7b` 均能输出合法动作，但在关闭思考时单局 30 步都未完成逃生；7B 在 `react_v8` 下能走到存储室并发现物品，随后仍会重复移动。当时 14B 下载因长时间网络停滞中止；后续已完成安装，结果见 2026-08-18 的复验记录。

下一步：当前验收结论为本地链路和可观测性通过，自动逃生策略未通过；后续应优先改进 Agent Loop 的重复动作约束或采用已验证的更强本地模型，而不是把失败局写成成功。

关联提交：待提交。

## 2026-08-18 轻量化链路与 14B 复验

事件：完成紧凑提示词、公开循环检测、运行时提醒、MemoryAgent 请求接入和 Spaceship Escape 无效目标收敛；随后复验已安装的 `qwen2.5:14b`。

原因：用户希望降低 16G Mac 的运行压力，同时确认 14B 是否能解决 7B 的长程循环问题。

改动：新增 `react_v9`，默认 Ollama 输出上限调整为 256 token；`DecisionRequest`、Runner、两种 provider 和 trace 增加公开运行时提醒；Environment 在终端误用、目标完成和授权码前置条件不满足时减少无效观察目标；新增循环检测及回归测试。

验证：`uv run ruff check .`、`uv run mypy src` 和 45 项 pytest 全部通过；`qwen2.5:14b` 的 `verify-model` 通过。固定 seed=0、MemoryAgent、30 步真实运行执行 30 步、0 次非法模型输出，但在恢复主电源后重复读取诊断终端，结果为 `step_limit`，未完成逃生。

下一步：将当前结果作为诚实的失败基线；若产品必须保证通关，应另行设计确定性任务阶段/Action Guard，不能继续只堆提示词规则。默认开发模型保持 `qwen2.5:7b`，14B 仅作对照。

关联提交：待提交。

## 2026-08-17 Spaceship Escape 环境完成

事件：完成第一个可手动通关的确定性 Spaceship Escape 环境。

原因：为后续 Agent Loop、Episode Trace 和 benchmark 建立可重复的环境基线。

改动：新增严格 Action 与 Observation 契约、六房间 JSON 定义、环境状态转换和规则测试。

验证：`uv run ruff check .`、`uv run mypy src` 和 25 项 pytest 通过，公开工具路径在 20 步内完成逃生。

下一步：设计 ReactAgent 与 Agent Loop。

关联提交：待提交。

## 2026-08-17 Release 1 Agent Loop 完成

事件：Release 1 的 ReactAgent、受限 Episode Runner、JSON Episode Trace 和 CLI 运行闭环完成。

原因：在进入 Memory 与 benchmark 前，需要一个可重复、可复盘且不会将不可信模型原文写入 trace 的基线 Agent。

改动：新增 `0003-react-agent-loop` spec、`ReactAgent`、百炼结构化决策适配、20 步 Fake 通关路径、Runner 状态机、脱敏原子 trace 写入和端到端测试；CLI `run` 不再生成 scaffold episode。

验证：`uv run ruff check .`、`uv run mypy src` 和 30 项 pytest 通过；`uv run agent-arena run --output-dir <temporary-directory>` 生成 `success` trace，含 20 个已执行动作和 0 个非法输出。

下一步：设计规则驱动的 MemoryAgent，并在固定世界、模型、提示词与步数预算下建立 Release 2 对照。

关联提交：待提交。

## 2026-08-17 百炼 Action 格式修复

事件：真实百炼运行曾连续输出带 `args` 包装的动作，现已通过 `react_v3` prompt 改为直接在 `action` 内提供工具参数。

原因：严格 Action schema 正确拒绝了非约定格式，但旧 prompt 只给出无参数工具示例，模型稳定选择了通用包装格式。

改动：升级 prompt 版本并列出六种工具的完整扁平 JSON 示例，明确禁止 `args`、`arguments` 和 `parameters` 包装字段；增加 prompt 约束回归测试。

验证：Ruff、mypy 和 31 项 pytest 通过。真实百炼运行从 3 次非法输出、0 个执行动作变为 0 次非法输出、30 个有效动作；该局因反复探索无电控制终端达到步数上限，说明格式问题已修复，而基线策略仍是后续 MemoryAgent 的研究对象。

下一步：设计 MemoryAgent，用结构化记忆降低重复观察和重复失败动作。

关联提交：待提交。

## 2026-08-17 Release 2 MemoryAgent 完成

事件：完成规则驱动的结构化 MemoryAgent，并建立与 ReactAgent 的可复现单局对照。

原因：在 benchmark 前先固定唯一实验变量，避免完整历史、隐藏状态或第二次模型调用影响结果。

改动：增加公开记忆 reducer、脱敏、失败动作与问题映射、Agent 生命周期、结构化 provider 请求与响应、token 用量、trace 实验来源和 CLI `--agent` 选择。

验证：Ruff、mypy 和 33 项 pytest 全部通过。ReactAgent 与 MemoryAgent 的 Fake CLI 均在 20 步成功逃生，Memory trace 包含版本化来源字段。

下一步：实现 benchmark 命令，使用持久化 trace 输出 ReactAgent 和 MemoryAgent 的 JSON、CSV 指标对照。

关联提交：待提交。

## 2026-08-17 Release 2 Benchmark 与指标完成

事件：完成多局 benchmark 命令，以及基于持久化 trace 的 JSON、CSV 指标输出。

原因：MemoryAgent 需要与 ReactAgent 在相同世界、seed 和预算下进行可复现对照，才能解释后续实验结果。

改动：新增 benchmark 行和聚合计算、原子 JSON/CSV 写入、trace 重读校验；CLI 支持单 Agent 或默认双 Agent 对照。

验证：Ruff、mypy 和 36 项 pytest 通过。`agent-arena benchmark --episodes 1` 使用 Fake provider 生成两份 trace，CSV 按 React、Memory 顺序输出，JSON 聚合成功率为 1.0。

下一步：在 benchmark 结果稳定后设计 Streamlit 实验界面。

关联提交：待提交。

## 2026-08-17 Benchmark 反馈与文件命名改进

事件：为 episode trace 和 benchmark 结果加入可读文件名，并让 benchmark 实时显示运行进度。

原因：原始 UUID 文件名难以按实验辨认；真实百炼 benchmark 默认运行 React 与 Memory 两组，原 CLI 在所有局完成前没有任何输出，容易被误判为卡住。

改动：输出名称包含 UTC 时间、Agent、seed 或局数和短 ID；真实模型会在每次决策请求前输出当前步数，benchmark 还会输出开始、每局开始和每局结束状态。

验证：Fake provider 端到端运行确认新名称和进度输出。`uv run ruff check .`、`uv run mypy src` 和 37 项 pytest 全部通过。

下一步：以小局数真实 benchmark 观察新进度信息和实际响应时长，再在结果稳定后设计 Streamlit 实验界面。

关联提交：待提交。

## 2026-08-17 本地 Ollama 与逐步复盘支持

事件：将真实实验工作流扩展为本地 Ollama `qwen3:4b`，并在终端逐步显示简短理由、动作、环境结果和对应 trace 路径。

原因：百炼的 3 seed React、Memory 对照均达到步数上限。Trace 显示 React 重复读取无电终端，Memory 虽减少拒绝动作但在维修室和反应堆室之间循环；原 benchmark 终端未展示已记录的步骤，难以直接诊断。

改动：新增 `ollama` provider、无密钥本地验证、独立 Ollama 配置、`react_v4` 探索规则和逐步终端回显。完整步骤继续存入 `runs/`，`results/` 保持指标职责。

验证：Ollama 服务可访问但模型列表为空，因此真实本地模型验证明确失败，未伪造通过结果。Ruff、mypy 和 39 项 pytest 全部通过；Fake benchmark 验证逐步输出和 trace 路径。

下一步：在本机下载 `qwen3:4b` 后运行 `verify-model --provider ollama`，再以单局和同 seed 对照检验 `react_v4` 的真实模型表现。

关联提交：待提交。
