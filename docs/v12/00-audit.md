# V12 Batch 0 审计报告

- **执行日期**：2026-10-25
- **起始 HEAD**：`258eadc5039309859fc0385d61650e266e6ab488`（`main`，与提纲给出的基准一致）
- **工作树状态**：仅 `研究提纲/V12Agent-Arena_V12_第二阶段完整执行提纲.md` 未跟踪；无其它未提交改动
- **Python / uv**：解释器 3.11.9（系统）→ 项目要求 `>=3.13,<3.14`，全部命令通过 `uv run` 使用 3.13 虚拟环境；`uv 0.13.3`
- **平台**：Windows 11（本次唯一实测平台）
- **基线测试**：`uv run pytest -q` → **1252 passed, 1 failed**（见 §5）

## 1. 可复用的现有能力（不重造）

| 层 | 现有实现 | V12 如何处理 |
|---|---|---|
| 单局状态机 / 单 worker / 取消 / 恢复 | `web/service.py` `RunService` | **复用**；新增 `SIMULATED` 分支与 Lab runner 注入 |
| 原子 manifest + append-only JSONL | `web/store.py` `RunStore`、`atomic_write_json`、`append_jsonl` | **复用**；父实验另建 `lab/experiment.py::ExperimentStore` 写 `runs/lab/` |
| 单局预算门禁 | `web/budget.py` `RunBudget`（请求/token/费用） | **复用**；Lab 通过 `lab/gateway.py` 复用同一对象 |
| 30 图 catalog / 展示元数据 | `web/catalog.py` | **复用**；Lab 只读 |
| V10 环境与公开契约 | `v10/runtime/catalog.py`、`v10/contract.py` | **只读复用**，不修改 |
| 公开提示组装 | `web/prompting.py` `system_prompt` | **复用**，`basic.v1` 与之逐字一致 |
| 指标五态与截尾口径 | `v10/metrics/schema.py`、`governance.py` | **只读复用**，不新增公式 |
| 失败归因 | `web/attribution.py`、`v10/attribution.py` | 复用机制动作集；新增证据级 `lab/diagnostics.py` |
| 导出 | `web/export.py` | 单局导出继续用；实验级导出新增 `lab/report.py` |
| 跨进程锁 | `web/lock.py` `SingleInstanceLock` | **复用**；Lab 服务共享同一 `RunService` |
| 网页框架与设计系统 | `ui/app.py`、`ui/theme.py` | **扩展**：新增三个 Lab 页面，不改既有六页 |
| Provider 抽象 | `llm/protocol.py` `DecisionProvider` | **复用**；Lab 网关包装它 |

## 2. 明确不能复用的部分

| 现有实现 | 为什么不能直接用 |
|---|---|
| `agents/`（React/Memory/Planning） | 面向 Legacy/V3 世界，Action 契约是 `legacy_v1`/`scenario_v3`，与 V10 `V8Action` 不兼容；直接移植会破坏"同一动作契约"的对照前提 |
| `planning/` `PlanState` | 同上；V12 的 Planner 输出走 `output_contract="planner"`，但执行侧必须是 V10 契约 |
| `evaluation/` EpisodeRunner | 驱动 V3/Legacy 环境；V10 单局已由 `web/execution.py` 承担 |
| V11 `execute_live` 的 agent 字段 | 只有一种执行器（`v10_action_loop`）；V12 需要按 `agent_id` 分派，因此新增 `lab/runner.py`，`v10_action_loop` 语义原样保留 |

## 3. 冻结基准与验证

| 命令 | 结果 |
|---|---|
| `uv run python -m agent_arena.v10.freeze verify` | 9/9 根目录 `unchanged`（`runs/` 本机存在，`docs/v8`、`docs/v9`、`src/agent_arena/v8`、`src/agent_arena/v9`、`worlds/scenario_v4`、`worlds/scenario_v8`、`worlds/v4`、`runs/v8`、`runs/v9`） |
| `uv run python -m agent_arena.v10.recompute --check` | 30/30 图、1093 次检查、0 不一致 |
| `uv run python -m agent_arena.v10.independent_check --check` | 0 违规、回放确定 30/30、seed 互异 30/30 |
| `uv run python scripts/verify_v11.py` | 7/7 通过 |

V12 结束时重新执行同样四项，结果见 `validation-report.md`。

## 4. Provider 请求路径清单（确认无未登记通道）

| 入口 | 位置 | 是否计费 | V12 是否新增 |
|---|---|---|---|
| 单局真实执行 | `web/execution.py::execute_live` | 是 | 否（保留） |
| 单局离线演示 | `web/execution.py::execute_offline` | 否 | 否（保留） |
| 连接检查 | `web/providers.py::probe_live_provider` | 可能少量 | 否（保留） |
| Lab 单局（真实/模拟） | `lab/runner.py::run_lab_episode` + `lab/gateway.py` | 是（模拟为 0） | **是** |
| CLI 历史实验 | `scripts/run_v5/v6/v7/v8/v9/v10_*.py` | 是（历史已封账） | 否 |

结论：Lab 的模型调用**只**经过 `DecisionGateway.ask`；`AgentPolicy` 拿不到 `DecisionProvider`。
`tests/test_v12_policies.py` 与 `lab/selfcheck.py` 都覆盖了"策略不得绕过网关"的边界。

## 5. 存储读写口径

| 目录 | 内容 | 谁写 | V12 是否改变 |
|---|---|---|---|
| `runs/web/<run_id>/` | `manifest.json`、`events.jsonl`、`result.json` | `RunService` | 只新增可选字段（`agent_config`、`experiment_id`、`matrix_index`、`agent_events`、`provenance`） |
| `runs/web/_ledger/web_ledger.jsonl` | V11 单局付费账本 | `RunService._ledger_*` | 不改变；**模拟模式不写** |
| `runs/lab/<experiment_id>/` | `experiment.json`、`manifest.json`、`events.jsonl`、`summary.json`、`comparison.json`、`children.json`、`report.md`、`exports/` | `ExperimentService` | **新增** |
| `runs/v8/`、`runs/v9/`、`runs/v10/` | 历史实验产物 | 历史脚本 | 只读，V12 不触碰 |

## 6. V11 遗留问题分类

| 遗留项 | V12 必修？ | 处理 |
|---|---|---|
| `test_home_shows_per_map_run_history` 在 HEAD 上偶发失败 | 是（阻断基线） | **已修**：`_prepare_runs` 依赖 `list_runs()[0]` 取"刚创建的第二局"，而 `created_at` 只精确到秒，同秒两局排序不稳定。改为直接使用第二个 `run_id`。 |
| macOS 实机未验证 | 否（不阻断） | 继续标 `NOT_VERIFIED` |
| Ollama 实机未跑 | 否 | 继续标未验证 |
| 浏览器 E2E 未进 CI | 是（P2） | 新增 `lab-e2e` job，`continue-on-error: true` |
| 移动端/可访问性未审计 | 部分 | 补 430px 截图；键盘/对比度仍为人工项 |
| Provider 账单对账未做 | 否 | 不在 V12 范围 |

## 7. 结论

- 现有 V11 服务层可以承载 V12 的父子实验，无需重写运行服务；
- V10 冻结资产完好，V12 全部新增代码在 `src/agent_arena/lab/`、`src/agent_arena/ui/lab.py`、`scripts/*_v12*.py`、`examples/`；
- 唯一基线缺陷是测试自身的排序假设，已修且不涉及运行时语义。
