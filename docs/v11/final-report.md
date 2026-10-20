# V11 最终报告：本地网页平台与阶段性交付

- **结论**：`WEB_PREVIEW_READY = true`（本地单机预览）。
- 执行日期：2026-10-20；起始 HEAD：`eb2f64a281677a0fce881769a6592cce1be6f7d9`。
- 本报告提交后的 HEAD：见 `git log -1`（报告自身不能写入自己的 hash）。
- 未推送正式 tag / GitHub Release；未修改 V8/V9/V10 冻结规则、账本与历史 trace。

## 1. 当前 HEAD、变更提交与运行入口

| 提交 | 内容 |
|---|---|
| `8c4b8cb` | Web 服务层、30 图 catalog、离线执行、预算、存储、导出、历史与测试 |
| `c0c5e0b` | 可操作 Streamlit 页面、`agent-arena web` CLI、UI/CLI 测试 |
| `a7e72ff` | 验收/截图/冒烟脚本、14 份交付文档、README、CI、截图 |
| `54c3951` | 导航 widget key、idempotency、单局历史成绩榜修复；Playwright E2E |
| `4d6a219` | CLI 测试平台差异修复，Ubuntu CI 转为 success |
| `65806ef` | 跨进程锁、失败归因、筛选/多局对照、Streamlit extra 锁定 |
| `e4fb40c` | shell 启动脚本可执行位 |
| `d51f472` | 文件锁 mypy 跨平台修正 |
| `33732ab` | 硬化文档：干净安装、Ubuntu CI、演示包与 0.2.0 |
| 本提交 | Streamlit 单例/深链导航修复、深色截图、E2E 清理 |

**推荐启动命令**：

```bash
uv run agent-arena web
```

打开 <http://127.0.0.1:8501>。辅助脚本：`scripts/launch_web.ps1`、`scripts/launch_web.sh`。原 CLI 入口保留。

## 2. 30 图是否都能选、启动、回放

**是，30/30。**

- 首页从 `MAP-01`～`MAP-30` 稳定 ID 生成，10 世界 × 3 图；筛选按世界/展示难度/关键词；
- 每张图详情包含公开目标、公开规则全文、带类型动作契约、公开观察字段、`scenario_descriptor`、成功/失败说明、版本 hash；
- 离线矩阵：30/30 成功启动并结束，合计 473 步，逐图 JSON 回放与 CSV 行数一致；
- `docs/v11/map-ux-checklist.md` 逐图留痕；6 张占位标题（08/16/18/22/26/30）只在展示层修复；
- 浏览器深链逐图打开配置页：**30/30，failures=[]**（`scripts/verify_v11_map_pages.py`）；
- MAP-19/20/28/29/30 有额外公开提醒，未修改规则。

## 3. 离线 / 真实模式各自完成了哪些端到端测试

### 离线（零 API）

- 30 图 × 1 seed，真实创建环境、执行公开启发式策略、写 manifest/events/result、读取回放、导出 JSON/CSV；
- 服务层：创建 → 排队 → 运行 → 终局；幂等；取消排队/运行；崩溃恢复；损坏日志容错；
- 预算：请求/token/费用上限；未知 usage fail-closed；
- 路径：遍历、非法 run_id、符号链接；
- 导出：字段、BOM、步数一致、敏感模式脱敏；
- 网页：stub 冒烟覆盖首页/配置/监控/结果/历史/设置；真实浏览器（Chrome）走通六页并截图。

### 真实（MiMo）

- 3 局完整闭环：创建 → 真实请求 → 动作落盘 → 终局 → 结果页 → 回放/导出；
- MAP-01：4 决策，`OXYGEN_SUPPLY_INTERRUPTION_LIMIT`；
- MAP-19：8 决策，`THERMAL_RUNAWAY`；
- MAP-30：46 决策，`decision_budget_exhausted`（`CENSORED` 指标）；
- 全部 0 非法动作、0 自动重试、0 成功；未改规则凑成功。

### 干净安装 / 跨 OS

- Windows 干净克隆 `b83755d`（无 `.env`）：`uv sync --extra web` + `web --check`，首次 **176.9 秒**、缓存复跑 **87–96.5 秒**，7/7；
- Ubuntu GitHub Actions：`b83755d` **success**（lock/ruff/mypy/pytest/freeze/recompute/independent/verify_v11）；
- macOS 未实机验证。

## 4. 取消、刷新、并发、Provider 错误、费用保护是否通过

| 项 | 结果 | 证据 |
|---|---|---|
| 取消排队 | 通过 | `test_cancel_queued_run` |
| 取消运行中 | 通过（协作式） | `test_cancel_running_run_is_cooperative` |
| 页面刷新不重复执行 | 通过 | 页面只读 manifest；UI 测试/浏览器刷新 |
| 重复提交 | 通过 | idempotency key；`test_idempotency_key_returns_existing_run` |
| 并发付费 | 拒绝第二局 | `ConcurrentLiveRunError`；`test_concurrent_live_run_is_rejected` |
| 进程中断 | 恢复为 `INTERRUPTED` | `test_recovery_marks_orphan_running_as_interrupted` |
| Provider 错误 | fail-closed | `test_provider_error_with_unknown_spend_fails_closed` |
| usage 缺失 | 未知消费、停止 | `test_missing_usage_is_unknown_spend` |
| 请求/token/费用上限 | 通过 | `test_web_budget.py`、`test_cost_cap_blocks_before_any_request` |
| 未知消费全局记录 | 通过 | `unknown_spend_adjustment`，本次 ¥0.073728 |
| 浏览器 E2E | 通过 | `scripts/e2e_web.py`：离线运行 15 步、下载 JSON 24,307 B、深链历史 |
| 30 图网页映射 | 通过 | `scripts/verify_v11_map_pages.py`：30/30 |
| 跨进程互斥 | 通过 | `SingleInstanceLock`；`test_single_instance_lock_per_run_directory` |
| 失败归因 | 通过 | `web/attribution.py`；结果页显示 label/detail |
| 原始公开 trace | 通过 | `trace.jsonl` 导出（header + decision） |

## 5. 数据/密钥泄露、版本 hash 与指标五态

- 30 图详情按**键名**扫描，无 `sealed_truth`、`judge_state`、`oracle`、`answer_key`、`truth_seal`；
- 导出回放扫描无 `sealed_truth`/`judge_state`；无 API Key、完整 prompt、Provider 响应头；
- Provider 状态只显示“已配置/未配置”，测试禁止 UI 读取密钥字段；
- 每局记录 `scenario_hash`、`rule_hash`、`metric_hash`、`metric_schema_hash`、`prompt_hash`；
- 指标五态 `VALID/CENSORED/NOT_APPLICABLE/MISSING/INVALID` 独立显示；`CENSORED`/缺失显示“—”，不写 0；
- 结果页显示单位、范围、公式（折叠）与主指标状态。

## 6. P0 / P1 / P2 状态、证据、未测试 OS

### P0（全部 DONE）

| 项 | 状态 | 证据 |
|---|---|---|
| 30 图体验检查 | DONE | `map-ux-checklist.md` 30/30 |
| 统一运行入口 | DONE | `agent-arena web`；README |
| 模型 API 配置 | DONE | `.env.example`、Provider 状态、离线演示、真实 3 局 |
| 结果输出 | DONE | manifest/events/result；JSON/CSV；实时进度 |
| 错误处理与安全 | DONE | 状态机、预算、取消、恢复、脱敏测试 |
| README 与安装教程 | DONE | `quickstart.md`、`user-guide.md`、`configuration.md` |
| 一键验收 | DONE | `scripts/verify_v11.py` 7/7 |

### P1（全部 DONE）

- 展示难度 30/30 + 说明：`difficulty-display.md`；ID/规则 hash 未变；
- 网页细化：卡片、配置、监控、时间线、结果、失败解释、空状态、移动端基本响应式；
- 历史筛选 + 2–4 局同版本对照 + 版本不一致阻止：`web/history.py`、页面；Provider/Seed 筛选、成绩榜决策预算列已补；
- 新手引导：首页快速开始、规则折叠、费用提示、无 Key 演示。
- 自动化浏览器 E2E：首页 → 离线运行 → 结果 → 下载 JSON → 深链历史；30 图配置页逐图 30/30。

### P2

| 项 | 状态 |
|---|---|
| 公开状态走势图 | DONE（基础版） |
| 本地同模型成绩榜 | DONE（含决策预算列） |
| 快捷启动脚本 | DONE（PowerShell/sh/command/桌面快捷方式/模板） |
| 截图 | DONE（`docs/v11/screenshots/` 8 张） |
| 演示数据包 | DONE（`docs/v11/demo/` + 安装脚本） |
| 桌面快捷方式 | DONE（模板；Linux 需改路径） |

### OS 覆盖

- **Windows 11**：已实测（干净安装 176.9s/87–96.5s、启动、离线 30 图、真实 3 局、浏览器六页、30 图映射、深色/移动端截图）；
- **Ubuntu**：GitHub Actions `b83755d` success（锁/ruff/mypy/pytest/freeze/recompute/independent/verify_v11）；
- **macOS**：未实机验证；`.command` 与文档已提供。

## 7. 真实 API 调用、请求、花费、未知消费

| 项 | 数值 |
|---|---:|
| 有效冒烟局 | 3（MAP-01/19/30） |
| 已记录请求 | 58 |
| 输入 token | 65,541 |
| 输出 token | 1,456 |
| 已结算 | **CNY ¥0.04637556** |
| 未知预留（修复前 4 次未落盘请求上界） | **CNY ¥0.073728** |
| 合计占用 | **CNY ¥0.12010356** |
| 预算上限 | CNY ¥3.00 |
| 成功 | 0/3（环境规则/预算终局） |

保留的修复前失败尝试：`web-20261020T024505Z-d221e453`（`FAILED / internal_error`，4 次请求未落盘）。修复与账本处理见 `safety-and-budget.md` §3。

## 8. 是否可以标记 `WEB_PREVIEW_READY`

**可以，限定为本地单机预览。**

成立的依据：

- P0 功能与主要 Gate 通过；P1 全部落地；P2 全部有实现或明确模板；
- **1240 pytest passed**、mypy 0 issues、ruff clean、lock 0、`git diff --check` 0；
- freeze 9/9 unchanged、recompute 1093/1093、independent 0 violations；
- 30/30 离线端到端 + 3/3 真实端到端 + 30/30 浏览器映射；
- Windows 干净安装 176.9s/87–96.5s、无 `.env` 自检 7/7；Ubuntu CI 已 success；
- 无密钥/隐藏真值泄露测试通过；
- 真实费用有硬门禁、未知消费封账；版本 `0.2.0`。

**不是**公网生产就绪，剩余缺口：

1. macOS 实机未验证；
2. 连接检查、Ollama 真实局、额度不足/限流/鉴权错误未真实触发；
3. 取消不能强制中断已发出的网络请求；真实 kill 进程恢复未演练；
4. 无自动化浏览器 E2E 进入 CI（本地脚本已通过）；
5. 移动端真机、深色模式、可访问性未审计；
6. Provider 账单对账未做；修复前 4 次请求只有预留上界；
7. V10 契约不返回 `decision_reason`，真实模式该列显示“—”。

最短修复路线：先在 macOS/Ubuntu 实机跑 `uv sync` + `verify_v11.py` + 网页 smoke，再补 Playwright CI；公网需求另立安全 ADR。未完成项均不阻塞本地预览。
