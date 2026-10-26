# agent_arena 模块上下文

- 运行入口是 `agent_arena.cli:app`，本地命令使用 `uv run agent-arena`。
- `config.py` 的 `RuntimeSettings` 是唯一公开配置模型。CLI 覆盖环境变量和本地 `.env`，环境变量再覆盖 `config/runtime.defaults.json`。
- `llm/` 只能处理 provider 调用。`arena/`、`agents/`、`worlds/` 和 `evaluation/` 不得直接导入 OpenAI SDK。
- `run` 通过 `ReactAgent`、`MemoryAgent`、`PlanningAgent` 或明确标记的 `PlannerAssistedAgent`、`EpisodeRunner` 和 `write_episode_trace` 运行完整 episode。`benchmark` 使用持久化 trace 生成 JSON、CSV 对照指标；`llm/` 适配 Fake、百炼和本地 Ollama，且不得让任何 Agent 或 Environment 直接调用 SDK；Legacy Spaceship Escape 环境位于 `arena/` 与 `worlds/`。
- V3 场景规则位于 `worlds/scenario/`，由 allowlist selector 创建，并使用 `ScenarioAction` / `ScenarioObservation` 契约。Runner 根据显式 V3 world version 记录独立 Trace 字段；新机制不得改变 legacy Action JSON、旧 selector 或冻结 seeded 定义。公开 Oracle 只用于离线验收。
- `planning/` 只保存通用 `PlanState`、`PlannerDecision`、`PlanSignal` 和公开进度监控；不得放入 Spaceship Escape 特定路线或直接执行环境动作。Planning 的成本和生命周期字段由 `evaluation/trace.py` 与 `evaluation/benchmark.py` 记录。
- `ui/` 是本地网页平台：地图大厅、挑战配置、运行监控、结果回放、历史对照，并保留旧只读研究视图。页面只调用 `agent_arena.web` 服务层；不直接创建环境、不在 Streamlit 中执行 Agent Loop，也不以 `st.session_state` 作为任务事实来源。运行命令：`uv sync --extra web` 后 `uv run agent-arena web`。
- `ui/lab.py` 是 V12 Lab 三页（配置/监控/结果）：只调用 `agent_arena.lab` 与 `agent_arena.web` 服务层；预检零请求、真实付费需显式批准；可视化只渲染 `lab.visualization` 的 view-model，不在页面重跑环境。
- `web/` 是 V11 服务层：`service.py` 管状态机/单 worker/取消/恢复，`store.py` 管 `runs/web/<run_id>/` 原子 manifest 与 JSONL，`budget.py` 管单局请求/token/费用门禁，`catalog.py` 提供 30 图公开元信息与展示难度，`execution.py` 适配 V10 单局。服务层不 import Streamlit；不读写 V8/V9/V10 账本；离线演示必须标记 `public_heuristic_policy`。
- `lab/` 是 V12 实验层：`contracts.py` 版本化契约，`registry.py` 策略注册表，`gateway.py` 唯一模型出口，`runner.py` 单局执行，`experiment.py` 父实验与队列，`compare.py` 配对比较，`diagnostics.py` 证据级诊断与 Diff，`visualization.py` 六图 view-model，`report.py` 导出与报告，`sdk.py` 第三方接入，`demo.py` 演示脚本 Provider。`lab` 不得 import `ui`，不得修改 `v10`，不得直接调用 Provider SDK（只能经 `DecisionGateway`）；父实验必须复用同一个 `RunService`。
- `lab/v13/` 是 V13 深化层（**只读**）：`comparability.py` 可比性画像/单变量检查/跨实验配对，`stability.py` 重复稳定性与翻转率，`ablation.py` 单因子消融模板与证据包，`validity.py` 六图构念效度与 MAP-30 阶梯，`taxonomy.py` 七层失败归因，`capability.py` 六维机制画像，`report.py` 零 LLM 模板报告，`ledger.py` 本地账本审计与账单对账，`sdkcheck.py` SDK 自检，`perf.py` 压力测试，`history.py` 只读历史装载。它不创建环境、不发请求、不写历史文件或账本。
- `web/index.py` 是 V13 只读历史索引：懒加载首页、mtime 增量刷新、服务端分页与聚合；不读事件/回放，不写 manifest。`web/service.py` 的 `page_runs` / `aggregate_runs` / `invalidate_index` 是它的入口。
- `v7/` 是只读指标层：只消费 Episode Trace 与离线 judge artefact，不修改 V4/V5/V6 环境、Action、Trace 写出器或账本；24 张 design-only 图调用 `compute_metrics` 必须抛 `NotImplementedError`，不得伪造分数。每条 `MetricSpec` 带 `valid_range`；六图有 36 条真实环境手算 fixture；新增 extractor 前先跑 `scripts/check_v7_leakage.py` 与 `scripts/audit_v7_cards.py`。
- `v8/` 是隔离的 30 图实验层：`worlds/scenario_v8/` 保存 24 张新运行时与 6 张 V4 适配图，`v8/` 保存五态指标投影、¥10 append-only 账本、公开 prompt 与 90 局 runner。不得修改 V3–V7 契约或历史账本；正式运行前必须通过 `scripts/validate_v8_offline.py` 并用 `scripts/freeze_v8.py` 冻结 30 图 hash。`runs/v8/` 为唯一输出目录。
- 运行质量检查：`uv run ruff check .`、`uv run mypy src`、`uv run pytest`。

_此文件由 /sync 根据引入改动生成，建议人工快速检查。_
