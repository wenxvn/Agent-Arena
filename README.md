# Agent Arena

Agent Arena 是一个用于学习和比较 LLM Agent 行为的轻量实验环境。

项目围绕一个确定性的 Spaceship Escape 世界，研究 Agent 如何在部分可观测环境中完成探索、工具调用、记忆和长程任务。完整设计见 [总纲.md](总纲.md)，开发顺序见 [docs/scope/scope.md](docs/scope/scope.md)。

## 第一阶段目标

1. 做出一个人可以只使用公开工具完成通关的环境。
2. 用规则测试固定环境行为。
3. 接入最小 ReactAgent 和 Agent Loop。
4. 记录每一局的 Episode Trace。
5. 加入 MemoryAgent，并用 benchmark 比较两种 Agent。

## 当前可运行入口

```bash
uv sync
uv run agent-arena run
```

`run` 默认使用 Fake provider，并在 `runs/` 写入一个不含密钥的 scaffold episode。它证明配置、CLI 与原子 JSON 持久化可用，尚不包含世界规则或 Agent Loop。

真实百炼配置验证需要本地 `.env`，并且必须显式调用：

```bash
bash scripts/verify_model.sh
```

## 下一步

先定义并测试环境契约：`WorldState`、`Action`、`Observation` 和 `Environment.step`。环境可以被手动控制并稳定通关后，再接入 LLM。这样后续的 Agent 实验才有可信的基线。

## 明确暂不做

第一版不做 Multi Agent、RAG、Vector DB、MCP、数据库、用户系统或复杂前端。先把一个完整、可重复的 Agent Loop 做通。
