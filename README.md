# Agent Arena

Agent Arena 是一个用于学习和比较 LLM Agent 行为的轻量实验环境。它让 Agent 在确定、部分可观测的世界中观察、调用工具、接收反馈，并记录每一步的运行结果。

当前已完成 Release 2、PlanningAgent v1 工程闭环和十世界三十图（飞船/灯塔/深海站/极地/金字塔/地铁/火山/丛林/月球/古堡 × 简单/中等/困难，见 `docs/specs/0007-*`～`0011-*`）：确定性世界、ReactAgent、MemoryAgent、PlanningAgent、不限步数执行循环、每局 JSON 运行记录，以及可重复的 benchmark 对照。

另外提供独立的 `planner_assisted` 实验模式：规划器只根据公开信息给出阶段和下一动作建议，模型仍需返回并执行合法的 JSON Action。它用于研究“公开辅助能否提高通关可靠性”，不能当作纯模型自主规划结果。

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

## Agent 模式

| 模式 | 用途 | 是否自主规划 |
|---|---|---|
| `react` | 基线 Agent，只根据当前公开观察和反馈决策 | 是，尚未证明稳定通关 |
| `memory` | 在 ReactAgent 上加入结构化公开记忆，配 history/recovery/phase 公开上下文 | 是，Muse 在 9 配置 × 5 seeds 获 45/45 成功（见开发进度） |
| `planning` | 事件触发的 Planner、PlanState、Executor 和 PlanMonitor | 是，真实 5 seeds 为 0/5，尚未证明有效 |
| `planner_assisted` | 公开阶段状态和下一动作建议，模型仍返回 Action | 否，路线选择主要由确定性规划器辅助 |

运行时可以显式指定 Agent，未指定时默认仍是 `react`：

```bash
uv run agent-arena run --provider ollama --agent react --seed 0 --output-dir runs
uv run agent-arena run --provider ollama --agent memory --seed 0 --output-dir runs
uv run agent-arena run --provider ollama --agent planner_assisted --seed 0 --output-dir runs
```

`MemoryAgent` 默认使用 `memory_version=v2`。研究中的 `v3_spatial_event` 可通过 `--memory-version v3_spatial_event` 显式选择，目前仅完成离线验证。全局 API/token 硬预算门禁已实现；三次隔离 pilot 均未完成 episode，并在 provider error 后 fail-closed，v2 为 0/2、v3 未启动，S2 matched-pilot Gate 尚未通过。不要把 v3 离线验证视为行为收益证据，预算、删失与停止规则见 [`docs/research/v2/03-memory-v3.md`](docs/research/v2/03-memory-v3.md) 和 [`docs/research/v2/00-run-registry.md`](docs/research/v2/00-run-registry.md)。

目前已真实验证的是 `qwen2.5:7b + planner_assisted`：固定 seed 0、1、2 共 3 局全部成功，平均 19 步，0 次非法输出，0 次环境拒绝。这个结果证明端到端辅助流程可用；纯 `react`/`memory` 的自主规划成功率仍需单独实验。

 PlanningAgent v1 已完成工程验证，并以相同模型、world、seed 和 30 步预算运行真实 5 seeds：首轮 0/5 成功，平均 28 次 Planner 调用、子目标完成率 0%；Evaluation v2 独立重跑仍为 0/5，平均 25.6 次 Planner 调用、调用比例 85.3%、State Progress 0。这说明当前主要问题仍是高层子目标到有效动作的桥接，不能把 Fake 或辅助模式结果当作自主规划能力。

2026-10-11 起真实实验切到 OpenCode Zen 网关的 `muse-spark-1.3-contributor`：Memory + history5 + recovery + world-declared phase + E1（prompt hash `44229085`）+ 不限步的自主组合，在 9 配置（飞船/灯塔/深海站 × 简单/中等/困难）× 5 seeds 中每个配置至少有一次成功；原始 51 个 trace 含 46 次成功和 5 次 `provider_error`，按所有实际尝试计为 46/51（90.2%），去重后的 45 个配置才是 45/45。0 非法输出；均值步数飞船 70.4/140.8/165.4、灯塔 39.8/49.4/105.8、深海 26.8/42.2/83.6，三图全部随难度单调递增。旧 qwen 基线保留独立统计。

后续十世界三十图矩阵 150/150 均有成功 trace，使用 E1-ON 基线；其中固定图存在网关失败后的重跑补齐，不能解读为首次尝试 150/150 稳定成功。flex pilot 与 seeded v2 变体分别记录为 30/30、15/15，且 seeded 长尾分析发现 v2 每图仅两种布局。新的 seeded v3 已离线冻结 lunar 90 / pyramid 30 个实例及 dev/test hash split，运行时与冻结清单 120/120 匹配；尚无 v3 模型行为评估，且 S2 matched-pilot Gate 未通过。具体实例、尝试分母与条件见 [开发进度](docs/scope/scope.md) 和 [V2-02 seeded 审计](docs/research/v2/02-bottleneck-audit.md)。

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

## 使用 OpenAI-compatible 远程模型

真实模型调用必须显式指定，并且只在本机 `.env` 中保存密钥：

```bash
cp .env.example .env
```

在 `.env` 填入 OpenAI-compatible relay 的 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `OPENAI_MODEL`，并设置 `AGENT_ARENA_PROVIDER=openai`。密钥不能提交到 Git。

先验证模型连接：

```bash
bash scripts/verify_model.sh
```

再运行一局远程实验：

```bash
uv run agent-arena run --provider openai --agent planner_assisted --output-dir runs
```

真实模型每次决策可能不同，因此结果可能是“成功逃离飞船”，也可能是“达到步数上限，未完成逃生”。后者表示 Agent 的探索策略尚不足，并不一定是配置或接口错误。

不要把 `planner_assisted` 的成功与纯模型结果混在一起。规划建议会出现在模型当前请求的公开反馈中；如果模型每次都遵循唯一建议，实际路线选择就主要由规划器决定。

## 运行 benchmark

```bash
uv run agent-arena benchmark --provider ollama --episodes 3 --output-dir results
```

未指定 `--agent` 时，会依次运行 ReactAgent 和 MemoryAgent，因此上例共执行 6 局。要单独运行规划辅助模式：

```bash
uv run agent-arena benchmark \
  --provider ollama \
  --agent planner_assisted \
  --episodes 3 \
  --output-dir results/planner-assisted
```

终端会在开始、每局开始、每次真实模型决策请求前、每个已执行动作后和每局结束时显示进度。每局最多 30 步；一次模型请求在网络异常时最多等待 30 秒，并可能重试两次。benchmark 输出 JSON 汇总、CSV 指标和每局 episode trace。

结果文件名称类似：

```text
benchmark_20260817T090501Z_react-memory_10-seeds_20-episodes_a1b2c3d4.json
benchmark_20260817T090501Z_react-memory_10-seeds_20-episodes_a1b2c3d4.csv
```

## 只读研究回放界面

项目提供只读 Streamlit 页面，用于浏览已有 trace 和 benchmark：单局回放、矩阵总览、错误热点和条件对照。启动命令：

```bash
uv run --with streamlit streamlit run src/agent_arena/ui/app.py
```

`streamlit` 通过 `--with` 临时提供，不写入 `pyproject.toml` 或 `uv.lock`。页面只读取本地 `runs/`、`results/` 文件，不调用模型，也不能启动新实验。支持配置并运行 episode/benchmark 的完整交互式实验界面仍在开发计划中，见 [开发进度](docs/scope/scope.md)。

## 验收与检查

```bash
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run uv lock --check
git diff --check
```

这些检查工具的输出由第三方提供，仍是英文：

- `All checks passed!`：代码规范检查通过。
- `Success: no issues found`：类型检查通过。
- `N passed`：全部自动测试通过。

## 文档入口

- [研究总纲](研究总纲.md)：项目目标、研究边界与阶段路线。
- [开发进度](docs/scope/scope.md)：已完成工作和后续计划。
- [架构摘要](docs/architecture.md)：模块职责和数据流。
- [ReactAgent 与执行循环设计](docs/specs/0003-react-agent-loop/index.md)：Action、终止条件与 Trace 契约。
- [规划辅助 Agent 设计](docs/specs/0005-planner-assisted-agent/index.md)：公开规划建议、边界和验收条件。
- [PlanningAgent v1 设计](docs/specs/0006-planning-agent-v1/index.md)：事件触发计划、Executor、PlanMonitor 和真实对照状态。
- [本地模型通关复现记录](docs/model-passage-options.md)：真实 Ollama 运行结果、排查过程和后续任务。
- [工程记录](docs/engineering-log.md)：重要验证、决策和阻塞记录。

## 当前边界

首个版本不引入 LangChain、RAG、向量数据库、多 Agent 编排、数据库或复杂前端。环境规则、Agent 策略、模型调用和运行记录保持独立，确保实验结果可以追溯和比较。

当前尚未完成：PlanningAgent 的自主规划稳定通关、真实 `guarded` 行为对照、规划建议偏离后的真实模型验证、终点 `read_terminal` 误用与读码后迷路的提示消融、可配置并启动实验的完整交互式 Streamlit 界面、ReflectionAgent，以及多模型对照。只读研究回放界面已提供。纯模型自主通关已由 Muse + Memory + 公开上下文组合在 9 配置 × 5 seeds 证明（45/45），qwen 与 Planning 基线仍未通过。详细清单见 [开发进度](docs/scope/scope.md)。
