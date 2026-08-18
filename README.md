# Agent Arena

Agent Arena 是一个用于学习和比较 LLM Agent 行为的轻量实验环境。它让 Agent 在确定、部分可观测的飞船逃生世界中观察、调用工具、接收反馈，并记录每一步的运行结果。

当前已完成 Release 2：确定性 Spaceship Escape 世界、ReactAgent、MemoryAgent、受步数限制的执行循环、每局 JSON 运行记录，以及可重复的 benchmark 对照。

## 快速开始

安装依赖并运行默认的确定性演示：

```bash
uv sync
uv run agent-arena run
```

默认使用 Fake provider，不需要网络或 API Key。它会稳定完成逃生，并显示类似结果：

```text
本局结果：成功逃离飞船
已执行动作：20
无效模型输出：0
运行记录：runs/episode_20260817T090501Z_react_seed-0_a1b2c3d4.json
```

运行记录是 UTF-8 JSON 文件。文件名依次包含记录类型、UTC 时间、Agent、seed 和短 ID，因此可按时间浏览且不会重名。房间描述、决策说明和动作结果使用中文；`tool`、`outcome`、房间 id 等英文值是程序和后续统计使用的固定标识。

## 使用 Ollama 本地模型

项目的本地实验工作流使用 Ollama 的 `qwen2.5:7b`，不需要 API Key。先确保 Ollama 服务已启动且模型已下载：

```bash
ollama pull qwen2.5:7b
ollama list
uv run agent-arena verify-model --provider ollama
```

再运行一局，并在终端查看每步的短理由、动作和环境结果：

```bash
uv run agent-arena run --provider ollama --agent memory --output-dir runs
```

真实模型的完整思维链不会显示或保存；终端和 Trace 只保留不超过 280 个字符的 `decision_reason`，以及经过环境验证的 Action 和 ToolResult。每局完整步骤写入 `runs/episode_*.json`，benchmark 会在每局结束时打印该路径；`results/` 中的 benchmark JSON、CSV 只保存汇总和逐局指标。

可通过本机 `.env` 改写默认地址或模型名：

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b
```

## 使用百炼模型

真实模型调用必须显式指定，并且只在本机 `.env` 中保存密钥：

```bash
cp .env.example .env
```

在 `.env` 填入 `OPENAI_API_KEY` 或 `DASHSCOPE_API_KEY`。`OPENAI_BASE_URL` 和 `OPENAI_MODEL` 可保留示例值，或按你的百炼配置调整。密钥不能提交到 Git。

先验证模型连接：

```bash
bash scripts/verify_model.sh
```

再运行一局百炼实验：

```bash
uv run agent-arena run --provider bailian --output-dir runs
```

真实模型每次决策可能不同，因此结果可能是“成功逃离飞船”，也可能是“达到步数上限，未完成逃生”。后者表示 Agent 的探索策略尚不足，并不一定是配置或接口错误。

## 运行 benchmark

```bash
uv run agent-arena benchmark --provider ollama --episodes 3 --output-dir results
```

未指定 `--agent` 时，会依次运行 ReactAgent 和 MemoryAgent，因此上例共执行 6 局。终端会在开始、每局开始、每次真实模型决策请求前、每个已执行动作后和每局结束时显示进度。每局最多 30 步；一次模型请求在网络异常时最多等待 30 秒，并可能重试两次。

结果文件名称类似：

```text
benchmark_20260817T090501Z_react-memory_10-seeds_20-episodes_a1b2c3d4.json
benchmark_20260817T090501Z_react-memory_10-seeds_20-episodes_a1b2c3d4.csv
```

## 验收与检查

```bash
uv run ruff check .
uv run mypy src
uv run pytest
```

这三个工具的输出由第三方提供，仍是英文：

- `All checks passed!`：代码规范检查通过。
- `Success: no issues found`：类型检查通过。
- `N passed`：全部自动测试通过。

## 文档入口

- [研究总纲](研究总纲.md)：项目目标、研究边界与阶段路线。
- [开发进度](docs/scope/scope.md)：已完成工作和后续计划。
- [架构摘要](docs/architecture.md)：模块职责和数据流。
- [ReactAgent 与执行循环设计](docs/specs/0003-react-agent-loop/index.md)：Action、终止条件与 Trace 契约。

## 当前边界

首个版本不引入 LangChain、RAG、向量数据库、多 Agent 编排、数据库或复杂前端。环境规则、Agent 策略、模型调用和运行记录保持独立，确保实验结果可以追溯和比较。
