# V11 安全与预算边界

## 1. 威胁模型

本地单机、单用户、浏览器访问 `127.0.0.1`。主要风险不是公网攻击，而是：

1. API Key 被页面、日志、导出文件或 Git 泄露；
2. 用户重复点击 / 刷新导致重复请求与重复计费；
3. 模型或 Provider 异常导致无界重试、无界费用；
4. 未知消费被当成 0，账本失真；
5. 任意路径读取 / 符号链接逃逸；
6. 前端提交任意 API URL，形成 SSRF 或本机网络滥用；
7. 把隐藏世界真值、完整 prompt 或 Provider 响应写进导出。

## 2. 已实施控制

### 2.1 密钥

- API Key 只从本机 `.env` / 环境变量读取；网页没有“输入自定义 Key”控件；
- 页面只显示 `已配置 / 未配置`，不回显长度、前后缀或哈希；
- 不允许网页提交自定义 `base_url`；地址只能在 `.env` 配置；
- Provider 异常只记录**异常类型**，不记录响应体、请求头或异常正文；
- 导出前统一经过 `sanitize_payload`，常见 `sk-…`、`Bearer …`、`api_key=…` 被替换为 `***`；
- `tests/test_ui_present.py::test_ui_touches_no_secrets` 继续扫描 UI，禁止直接读取密钥字段。

### 2.2 路径

- `run_id` 必须匹配 `^web-\d{8}T\d{6}Z-[0-9a-f]{8}$`；
- 只允许 `runs/web` 的直接子目录；拒绝 `..`、绝对路径、斜杠、符号链接；
- 导出只来自服务层已加载的 manifest/events/result，不接受客户端路径；
- 历史 CSV 导出只包含服务层 `RunSummary` 字段。

### 2.3 预算与费用

单局硬上限（页面与 API 都不可突破）：

| 项 | 上限 |
|---|---:|
| 决策数 | 200 |
| Provider 请求 | 200 |
| 输入 token | 2,000,000 |
| 输出 token | 200,000 |
| 单局费用 | ¥20 |

默认值：离线模式请求上限 1（实际 0 次）；真实模式 60 次请求、单局费用 ¥1.00。

请求前 `RunBudget.reserve()` 检查：

1. 请求数 +1 是否超过上限；
2. 累计输入 token + 本次保守估算是否超过上限；
3. 累计输出 token + 本次输出上限是否超过上限；
4. 若模型有登记价（当前仅 MiMo），累计成本 + 本次预留是否超过费用上限。

响应后 `settle()` 用真实 usage 替换预留；若 usage 缺失、为负或 cached > input，立即 `UnknownUsageError`，运行进入 `PROVIDER_ERROR`，**不自动重试**，未知消费保留预留上界。

**费用口径**：只有 MiMo 有本项目登记价（输入 ¥1/M、缓存输入 ¥0.02/M、输出 ¥2/M）；其它模型不启用金额硬门禁，页面显示“未知/不估算”，以请求/token 上限作为硬门禁。任何金额都不是 Provider 账单。

### 2.4 串行、幂等与取消

- 单 worker 队列；同一时刻最多一个付费任务（`ConcurrentLiveRunError` 明确拒绝第二个 live run）；
- `idempotency_key` 相同直接返回既有 `run_id`；页面在配置不变时复用 key，防双击；
- `cancel_run` 是协作式：设置 Event，执行循环在请求前/step 前检查；
- 已发出的请求不会被强制中断，UI 明示“当前请求或步骤结束后生效”；
- 取消后仍写 partial result，状态 `CANCELLED`。

### 2.5 恢复与损坏容错

- 每次状态转换原子写 manifest（临时文件 + `os.replace`，Windows 对 `PermissionError` 有限重试）；
- 动作事件 append-only JSONL（`flush` + `fsync`）；
- 启动时非终态遗留运行标为 `INTERRUPTED`，保留已写事件；
- manifest 读在 Windows 替换瞬间做 20 次短重试；
- JSONL 损坏行跳过并计数，页面提示但保留其余记录；
- 如果 result 已是终态而 manifest 落后，恢复时以 result 为准。

## 3. 运行安全事故与修复（2026-10-20）

第一次真实冒烟在 `web-20261020T024505Z-d221e453` 失败：

- 现象：`FAILED / internal_error`，0 条 decision 事件；
- 根因：`RunBudget.snapshot()["limits"]["max_cost_cny"]` 是 `Decimal`，写入 JSONL 时 `json.dumps` 抛 `TypeError`；第一次 decision 事件落盘失败，服务按内部错误停止；
- 影响：已向 Provider 发出 **4 次请求**，但 usage 未落盘；未产生可确认的结算记录；
- 修复：
  1. `snapshot()` 的 limits 改为 JSON 安全字符串；
  2. 存储层 `json.dumps(..., default=str)` 兜底；
  3. 新增单元测试 `test_snapshot_is_json_serializable`；
  4. 新增服务层集成测试，用真实 `execute_live` + fake provider 验证 budget 事件落盘；
  5. 按 fail-closed 记入全局账本 `unknown_spend_adjustment`，预留上界 **CNY 0.073728**（4 × 16,384 输入 + 4 × 1,024 输出的登记上限）。
- 后续 3 局均正常记录 usage，未见同类错误。

## 4. 残余风险

- `.env` 仍是明文文件；依赖操作系统账户权限，未做加密；
- 本机其他进程可读 `runs/web` 与 `.env`；
- Provider 账单可能与本地上报 usage 存在差异；
- 取消不能中断已发出的网络请求；
- 进程崩溃只能恢复到 `INTERRUPTED`，不能恢复环境内部状态；
- 未实现公网鉴权、速率限制、多用户隔离；默认拒绝非回环地址。
