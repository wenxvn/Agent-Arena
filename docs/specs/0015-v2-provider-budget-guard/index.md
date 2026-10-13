# 0015. V2 Fail-Closed Provider Budget Guard

**日期**：2026-10-13
**状态**：Accepted（S2 M1 pilot 前置工程门禁）

## 摘要

为 V2 的受限真实模型 pilot 提供跨 episode、跨 CLI invocation 共享的 provider request/token 预算账本。每个决策 API 请求必须先持久化预留额度，再进入 provider adapter；不确定或超出登记边界时关闭账本并阻止后续请求。

## 决策

- `RuntimeSettings` 的预算配置要么全部缺省（旧行为不变），要么全部提供：请求上限、累计 token 上限、单请求输出 token cap、全局超时、experiment ID、expected provider/model、expected world-definition hash、expected base-prompt hash、ledger 路径。expected provider 必须与当前选择的 provider 相同。启用预算时要求 `retry_count=0` 且 `step_limit` 有限。
- `run` 与 `benchmark` 用同一个 `BudgetedDecisionProvider` 包装 provider adapter。benchmark 的多个 episode 和后续 CLI invocation 共用同一 ledger；OS 文件锁串行化账本事务，账本写入使用临时文件、`fsync` 与原子替换。整个 `run` episode 或 `benchmark` cell loop 持有 invocation lease，避免独立 CLI invocation 交错使用同一 experiment；每次 provider 请求还持有独立 OS request lease，从预留前直到记账完成，避免活跃 in-flight 请求被误回收为 abandoned。一个实验最多允许一个 provider 请求处于 in-flight。
- 请求发送前计算保守输入 token 上界（请求可见文本的 UTF-8 字节数、最大 response schema 字节数与固定 adapter overhead），预留输入上界和输出 cap。只有预留成功后，才把单请求输出 cap 传给 OpenAI-compatible、Bailian 或 Ollama adapter。
- 已完成请求按 provider 返回的整数 usage 计入实际 token。发起或完成请求时已超过全局 deadline 会关闭 ledger；跨过 deadline 才完成的请求按真实 usage 记账，当前 episode 中止。缺失 usage、provider error、进程遗留的 in-flight 请求、错误的 provider/model、usage 超过预留、ledger 不可读或配置不匹配，均 fail closed；未知支出按完整预留额计费，ledger 关闭且不再发起请求。账本验证必须确保 terminal request status 与 `closed_reason`、request/token counters 一致。provider 内重试和 SDK 自动重试关闭，格式修正请求仍会经过 wrapper 并单独占用 request/token 额度。
- 在创建 provider 前核对当前模型名；在 EpisodeRunner 发请求前分别核对实际环境 definition hash 与 Agent base prompt hash。Trace 保存实际模型、地图/prompt hash、硬预算与 experiment ID；ledger 只保存脱敏的 provider/model/context、额度、usage、状态和时间，不保存 prompt、密钥或 provider 响应。
- 预算拒绝、账本关闭、provider error、全局超时或未知支出的未完成 episode 不写成完整 Episode Trace。预算异常必须穿过 `EpisodeRunner` 到达 CLI；benchmark 保存已经完成 episode 的结果，明确打印提前停止及完成局数，并以非零状态终止预登记脚本。
- 不通过 `verify-model` 等未包装路径探测 pilot gateway。受限 gateway 探针使用预登记 pilot 的首个决策请求完成，并计入同一 request/token cap。

## 边界与风险

- 输入上界覆盖请求文本、公开 Observation、记忆/历史/反馈内容、response schema 和固定 adapter overhead。若真实 provider usage 高于预留，当前请求已经发生，系统会记录违规、关闭 ledger 并阻止下一次调用；因此该情况使 pilot 的预算有效性失效，必须单独报告，不能宣称费用绝对没有越界。
- provider 无法返回可校验 usage 时，系统按整笔预留计入并关闭实验，不尝试用估算替代真实 usage 继续运行。
- 仅通过 CLI 显式启用预算的 `run` / `benchmark` 受该 guard 保护。预算 pilot 不得调用其它真实模型入口。

## 验收

1. fake provider 覆盖成功计费、跨 invocation 共享上限、发请求前拒绝、输出 cap 传递、missing usage、provider error、异常 usage、abandoned request、活跃请求并发保护、invocation 防交错、provider/model identity mismatch、超时中请求完成、terminal status/closed reason 一致性与无效 ledger counter fail closed；runner 对预算异常不生成完成 Trace。
2. 所有 provider adapter 在预算模式下都接收 per-request output cap；默认无预算调用保持原参数行为。
3. Ruff、mypy、全量 pytest 与 `uv lock --check` 通过后，更新 V2 run registry 并固定代码 SHA、模型、地图/prompt hash、seed、并发、时间和预算上限。
4. 完成受限 pilot 或留下精确的 fail-closed 中断证据后，再判断 S2 Gate；单元测试和预算门禁本身不构成模型收益证据。
