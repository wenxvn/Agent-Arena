# agent_arena 模块上下文

- 运行入口是 `agent_arena.cli:app`，本地命令使用 `uv run agent-arena`。
- `config.py` 的 `RuntimeSettings` 是唯一公开配置模型。CLI 覆盖环境变量和本地 `.env`，环境变量再覆盖 `config/runtime.defaults.json`。
- `llm/` 只能处理 provider 调用。`arena/`、`agents/`、`worlds/` 和 `evaluation/` 不得直接导入 OpenAI SDK。
- `run` 通过 `ReactAgent`、`EpisodeRunner` 和 `write_episode_trace` 运行完整 episode。Spaceship Escape 环境位于 `arena/` 和 `worlds/`；benchmark 和 MemoryAgent 仍由后续 scope feature 实现。
- 运行质量检查：`uv run ruff check .`、`uv run mypy src`、`uv run pytest`。

_此文件由 /sync 根据引入改动生成，建议人工快速检查。_
