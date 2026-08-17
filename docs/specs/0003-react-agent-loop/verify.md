# ReactAgent、Episode Runner 与 Trace 验证

## 自动验证

1. `uv run ruff check .`
2. `uv run mypy src`
3. `uv run pytest`

## 行为验证

1. 用完整 Fake 决策队列从 `control_room` 逃生，确认 trace outcome 为 `success`、20 个环境动作均已记录。
2. 先返回非法候选，再返回修正后的有效决策，确认同一 Observation 的 correction 为真且环境只执行有效 Action。
3. 返回三个连续非法候选，确认 outcome 为 `invalid_action_limit` 且没有环境动作。
4. 返回 schema 有效但环境拒绝的动作，确认它被记录且不增加非法输出计数。
5. 注入包含 API key 形式文本的决策说明和 provider 异常，确认 trace 不含秘密值。
6. 执行 `uv run agent-arena run --output-dir <temporary-directory>`，确认写出完整 terminal trace。
