# agent_arena 模块上下文

- 运行入口是 `agent_arena.cli:app`，本地命令使用 `uv run agent-arena`。
- `config.py` 的 `RuntimeSettings` 是唯一公开配置模型。CLI 覆盖环境变量和本地 `.env`，环境变量再覆盖 `config/runtime.defaults.json`。
- `llm/` 只能处理 provider 调用。`arena/`、`agents/`、`worlds/` 和 `evaluation/` 不得直接导入 OpenAI SDK。
- `run` 通过 `ReactAgent` 或 `MemoryAgent`、`EpisodeRunner` 和 `write_episode_trace` 运行完整 episode。`benchmark` 使用持久化 trace 生成 JSON、CSV 对照指标；`llm/` 适配 Fake、百炼和本地 Ollama，且不得让任何 Agent 或 Environment 直接调用 SDK；Spaceship Escape 环境位于 `arena/` 和 `worlds/`。
- 运行质量检查：`uv run ruff check .`、`uv run mypy src`、`uv run pytest`。

_此文件由 /sync 根据引入改动生成，建议人工快速检查。_
