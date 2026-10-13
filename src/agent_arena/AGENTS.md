# agent_arena 模块上下文

- 运行入口是 `agent_arena.cli:app`，本地命令使用 `uv run agent-arena`。
- `config.py` 的 `RuntimeSettings` 是唯一公开配置模型。CLI 覆盖环境变量和本地 `.env`，环境变量再覆盖 `config/runtime.defaults.json`。
- `llm/` 只能处理 provider 调用。`arena/`、`agents/`、`worlds/` 和 `evaluation/` 不得直接导入 OpenAI SDK。
- `run` 通过 `ReactAgent`、`MemoryAgent`、`PlanningAgent` 或明确标记的 `PlannerAssistedAgent`、`EpisodeRunner` 和 `write_episode_trace` 运行完整 episode。`benchmark` 使用持久化 trace 生成 JSON、CSV 对照指标；`llm/` 适配 Fake、百炼和本地 Ollama，且不得让任何 Agent 或 Environment 直接调用 SDK；Legacy Spaceship Escape 环境位于 `arena/` 与 `worlds/`。
- V3 场景规则位于 `worlds/scenario/`，由 allowlist selector 创建，并使用 `ScenarioAction` / `ScenarioObservation` 契约。Runner 根据显式 V3 world version 记录独立 Trace 字段；新机制不得改变 legacy Action JSON、旧 selector 或冻结 seeded 定义。公开 Oracle 只用于离线验收。
- `planning/` 只保存通用 `PlanState`、`PlannerDecision`、`PlanSignal` 和公开进度监控；不得放入 Spaceship Escape 特定路线或直接执行环境动作。Planning 的成本和生命周期字段由 `evaluation/trace.py` 与 `evaluation/benchmark.py` 记录。
- `ui/` 是只读 Streamlit 研究回放界面：仅消费 `runs/`、`results/` 中已有 trace/CSV，不读 `.env`、不调用 Provider、不启动新实验；运行命令见根目录 README。
- 运行质量检查：`uv run ruff check .`、`uv run mypy src`、`uv run pytest`。

_此文件由 /sync 根据引入改动生成，建议人工快速检查。_
