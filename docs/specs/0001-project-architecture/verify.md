# 项目技术架构检查

这份检查用于在脚手架完成后确认实现遵守架构决策。它不是功能验收清单，具体世界规则由后续环境 spec 定义。

## Project shape

* [ ] Python 项目可以通过 `uv sync` 创建环境。
* [ ] `pyproject.toml` 和 `uv.lock` 存在并能在干净环境复现依赖。
* [ ] 应用代码位于 `src/agent_arena`，测试位于独立测试目录。
* [ ] CLI 暴露 `run`、`benchmark` 和 `verify-model` 命令。
* [ ] 配置只通过 `RuntimeSettings` 加载，优先级是 CLI、环境变量、`config/runtime.defaults.json`。
* [ ] `run` 和 `benchmark` 默认使用 Fake provider。真实百炼调用需要显式 `--provider bailian`。
* [ ] 两个 API key 环境变量同时存在且值不一致时，百炼启动失败。Fake 运行不要求 endpoint 或 API key。

## Boundary checks

* [ ] Agent 接口只接收 Observation，不接收 WorldState。
* [ ] Environment、Agent、LLM adapter、evaluation 和 prompts 位于独立边界。
* [ ] Action 是 Agent 到 Environment 的唯一命令载体。
* [ ] 所有外部模型输出在执行前通过 Pydantic 校验。
* [ ] Runner 通过 `DecisionProvider` 注入 Fake 或 Bailian provider，测试可断言 Fake 收到的 Observation 和 correction 标记。
* [ ] Fake 响应队列耗尽会明确失败，不会回退为真实模型调用。

## Reproducibility checks

* [ ] 世界配置包含版本，并且每局记录 seed。
* [ ] Fake LLM 可以驱动确定性 fixture 完成测试，不需要网络或 API key。
* [ ] 每局生成一个 JSON Trace，benchmark 可以输出 JSON 和 CSV。
* [ ] CI 不调用真实百炼 API。
* [ ] Benchmark JSON 和 CSV 具有约定的 episode 字段、聚合字段及 `episode_index` 稳定顺序。

## Reliability and safety checks

* [ ] 单局最多 30 步，单次请求超时为 30 秒。
* [ ] 网络错误、429 和 5xx 最多重试两次，并使用指数退避。
* [ ] OpenAI SDK 的内建重试已关闭，只有 provider adapter 负责重试。
* [ ] 非法 Action 允许一次修正，连续三次非法输出终止 episode。
* [ ] 状态机测试覆盖主响应非法、修正响应非法、三次连续非法、合法但被世界拒绝，以及 provider 失败。
* [ ] 日志和 Trace 不包含 API key、请求头、原始请求或响应、异常正文或完整 reasoning content。
* [ ] 脱敏测试验证注入决策说明和错误中的 secret like 字符串不会持久化。
* [ ] `enable_thinking` 默认关闭，Trace 只保留短 `decision_reason`。
* [ ] Trace 通过临时文件和原子重命名写入，episode id 不会碰撞。

## Quality checks

* [ ] GitHub Actions 在 push 和 pull request 执行依赖同步、Ruff、mypy 和 pytest。
* [ ] 真实 API smoke test 只能显式手动运行，不属于默认 CI。
