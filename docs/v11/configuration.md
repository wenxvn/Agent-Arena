# V11 配置说明

## 1. 配置文件

- 仓库内的 `config/runtime.defaults.json`：非敏感默认值，入库；
- 本机 `.env`：密钥与本地覆盖，**不入库**；
- 环境变量：优先级高于 `.env`；
- CLI 参数：优先级最高。

模板见 `.env.example`，只含假值。

## 2. 常用变量

| 变量 | 说明 | 默认/示例 |
|---|---|---|
| `AGENT_ARENA_PROVIDER` | `fake` / `openai` / `ollama` / `bailian` | `openai` |
| `OPENAI_API_KEY` | OpenAI-compatible 密钥 | `replace-with-your-api-key` |
| `OPENAI_BASE_URL` | Responses API 地址 | `https://example.com/v1` |
| `OPENAI_MODEL` | 模型名 | `gpt-5.6-terra`（示例） |
| `OPENAI_SESSION_ID` | 网关会话头 | `agent-arena` |
| `AGENT_ARENA_RESPONSE_FORMAT` | `json_object` / `json_schema` | 注释状态 |
| `OLLAMA_BASE_URL` | 本地 Ollama | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | 本地模型 | `qwen2.5:7b` |
| `AGENT_ARENA_WEB_RUNS_DIR` | 网页运行目录 | `runs/web` |
| `AGENT_ARENA_WEB_TOTAL_BUDGET_CNY` | 可选的跨局总额硬上限 | 不设置 |

`AGENT_ARENA_WEB_TOTAL_BUDGET_CNY` 只用于网页真实模式；设置后，`RunService` 在创建 live run 前把已结算 + 未结算预留 + 未知预留计入，超出即拒绝。V11 冒烟脚本使用 `3.00`。

## 3. Provider 选择

网页“设置与帮助”显示：

- **OpenAI-compatible / MiMo**：读取 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`；
- **本地 Ollama**：读取 `OLLAMA_BASE_URL`、`OLLAMA_MODEL`；
- **离线演示**：不需要任何配置。

网页不接受自定义 API URL；需要改地址时编辑本机 `.env` 并重启。

## 4. 密钥安全

- 页面只显示“已配置/未配置”，不显示长度、前后缀或哈希；
- 日志/结果/导出不写密钥；异常只记录类型；
- `.gitignore` 已忽略 `.env`、`.env.*`（保留 `.env.example`）、`runs/`、`results/`、`logs/`；
- 真实付费前页面要求勾选确认。

## 5. 预算

- 单局：请求数、输入 token、输出 token、费用（仅 MiMo 有登记价时）四道门禁；
- 全局：可选的 `AGENT_ARENA_WEB_TOTAL_BUDGET_CNY`；
- unknown usage：立即 `PROVIDER_ERROR`，保留预留上界并停止；
- 不自动重试、不自动补跑、不自动启动批量矩阵。

价格来源：MiMo 公开价（输入 ¥1/M、缓存输入 ¥0.02/M、输出 ¥2/M）。这是本地估算，不是 Provider 账单。

## 6. 连接检查

“设置与帮助 → 连接检查”会发送 **1 次最小请求**，可能产生极少量费用，且不进入单局预算账本。必须手动勾选确认。

零网络配置检查在每次“开始挑战”前自动执行，只验证 Key/URL/模型名是否存在。

## 7. 常见错误

| 类别 | 含义 | 处理 |
|---|---|---|
| `missing_api_key` | 未配置密钥 | 编辑 `.env` |
| `missing_base_url` | 未配置地址 | 编辑 `.env` |
| `AuthenticationError` | 密钥无效/过期 | 更换密钥 |
| `PermissionDeniedError` | 无模型权限 | 检查账户/模型 |
| `NotFoundError` | 模型或地址不存在 | 检查 `OPENAI_MODEL`/`OPENAI_BASE_URL` |
| `APIConnectionError` | 连接失败，结果未确认 | 已按未知消费停止；稍后手动重开 |
| `APITimeoutError` | 超时，结果未确认 | 同上 |
| `RateLimitError` | 限流 | 等待后手动重试 |
| `BudgetExceeded` | 请求/token/费用上限 | 调整预算或换更小任务 |
| `unknown` | 无法确认的结果 | 已 fail-closed，不自动重试 |

## 8. 日志位置

- `runs/web/<run_id>/manifest.json`：状态与配置；
- `runs/web/<run_id>/events.jsonl`：动作与状态事件；
- `runs/web/<run_id>/result.json`：终局、指标五态、hash、usage；
- `runs/web/_ledger/web_ledger.jsonl`：V11 跨局预算账本；
- `runs/v11/selfcheck.json`：一键自检报告；
- `runs/v11/smoke-summary.json`、`runs/v11/smoke-all.json`：真实冒烟记录。

删除 `runs/web/` 可重置网页历史；不要删除 `runs/v8`、`runs/v9`、`runs/v10`。
