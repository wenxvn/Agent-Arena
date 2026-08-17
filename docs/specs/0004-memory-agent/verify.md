# MemoryAgent 验证

在实现后执行。

1. 运行 `uv run ruff check .`。
2. 运行 `uv run mypy src`。
3. 运行 `uv run pytest`。
4. 运行 `uv run agent-arena run --agent memory --output-dir <temporary-directory>`，确认 trace 包含 `memory`、非敏感来源和终局结果。
5. 用 `--agent react` 运行相同 Fake 路线，确认两份 trace 的世界版本、seed、provider、基础 prompt 哈希和已执行动作数相同。
6. 在聚焦测试中检查 MemoryAgent provider 调用。确认 ReactAgent 基础指令是唯一 system prompt，`Agent Memory` 是单独的非指令数据消息，字段顺序稳定且没有密钥或 WorldState。
7. 测试每种终局结果，确认 MemoryAgent 在 `finish` 后清空状态。
8. 测试带 usage 的 Fake 响应和 provider 错误。确认 trace 只为已完成请求记录用量。
