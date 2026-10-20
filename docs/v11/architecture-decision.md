# V11 架构决策（ADR）

**状态**：Accepted（2026-10-20，执行 Agent 记录，待用户复核）
**范围**：本地网页平台、单机单用户、localhost。不是公网多租户服务。

## 1. 决策

沿用 **Streamlit + Python 服务层**，不引入 React/Next.js、FastAPI、Redis、Celery 或数据库。

新增 `src/agent_arena/web/`：

| 模块 | 职责 |
|---|---|
| `schemas.py` | 不可变 `RunConfig`、状态机、`RunStatus`/`RunSummary` |
| `store.py` | `runs/web/<run_id>/` 的 manifest 原子写、JSONL 事件、result、全局账本 |
| `service.py` | `create_run/get_run/cancel_run/list_runs/load_replay/recover`，单 worker 串行 |
| `execution.py` | 单局 V10 适配：离线公开策略 + 真实模型循环，事件回调 |
| `budget.py` | 请求 / token / 费用硬门禁，未知 usage fail-closed |
| `catalog.py` | 30 图公开元信息、展示难度、地图详情 |
| `providers.py` | Provider 状态、构造、零网络配置检查、显式连接检查 |
| `prompting.py` | 与 V10 冻结 runner 逐字一致的 system prompt |
| `export.py` | 回放 JSON、摘要 JSON、逐动作 CSV |
| `history.py` | 历史筛选、版本对照、本地同模型成绩榜 |
| `safety.py` | 路径限制、脱敏、错误分类 |
| `explain.py` | 状态/终止码/指标五态的中文解释 |
| `selfcheck.py` | 一键离线验收 |

`ui/app.py` 只做展示与操作；执行状态由服务层与磁盘 manifest 决定，**不以 `st.session_state` 作为任务事实来源**。

## 2. 数据流

```text
浏览器
  → Streamlit 页面
    → RunService.create_run(RunConfig)
      → runs/web/<run_id>/manifest.json (QUEUED)
      → 单 worker 线程
        → execution.execute_offline / execute_live
          → V10 create_environment + 公开 Observation
          → (live) DecisionProvider.decide + RunBudget
          → events.jsonl（逐动作，公开数据）
          → result.json（指标五态 + 版本 hash）
    → 页面按 run_id 读取 manifest/events/result
```

取消：`cancel_run` 设置协作式 `threading.Event`；执行循环在**每次模型请求前、每个环境 step 前**检查。已发出的网络请求不会被强制中断，页面明确提示“停止将在当前请求或步骤结束后生效”。

恢复：`RunService` 启动时扫描非终态 manifest，若不属于当前活跃进程，则标为 `INTERRUPTED` 并写 partial result；日志损坏行跳过但保留其余记录。

## 3. 备选方案与取舍

| 备选 | 结论 | 理由 |
|---|---|---|
| 仅用 `st.session_state` 管状态 | 拒绝 | 刷新/进程退出即丢；无法取消、恢复、导出 |
| 页面按钮拼 shell 调 `run_v10_mimo.py` | 拒绝 | 无界批量、无法逐局预算/取消、重复计费风险 |
| FastAPI + React | 拒绝 | 单机单用户成本高；已有 Streamlit 展示层可复用 |
| 数据库 | 拒绝 | 单机文件足够；manifest + JSONL 可审计、可删除 |
| 后台进程池 | 拒绝 | 单局串行更安全；付费任务不允许并发 |
| 直接把 V10 全局 ¥10 账本给网页 | 拒绝 | 研究账本已封账/有历史；V11 必须独立预算 |
| 每局独立 `V10BudgetLedger` | 部分复用 | 价格语义复用，但 V11 需要可配置上限与未知消费状态 |

## 4. 预算实现说明

V11 没有复用 `V10BudgetLedger` 的**固定 ¥10 / 60 局**全局语义，因为网页需要：

- 每局独立的请求/token/费用上限；
- 用户取消后仍能封账；
- 未知 usage 立即进入 `PROVIDER_ERROR`，并可跨局记录全局未知预留。

因此 `web/budget.py` 复用 `v10.ledger.PRICE_SHEETS` 的 MiMo 单价与成本公式，但门禁与快照独立。全局 `runs/web/_ledger/web_ledger.jsonl` 只记录 V11 的 `run_started` / `run_settled` / `run_aborted` / `unknown_spend_adjustment`，不读写 V10 账本。

## 5. 兼容性

- V10 地图规则、动作契约、指标、Oracle、账本、历史 trace **零修改**；
- 新增 `v10/contract_hints.py` 只提取既有公开字符串，测试保证与冻结 runner 一致；
- CLI 原入口保留；新增 `agent-arena web`；
- 旧 Streamlit 四个研究视图保留，旧测试继续通过。

## 6. 后果与限制

- 单进程单 worker；多用户同时访问同一 localhost 实例会共享队列，不适合多人；
- 进程崩溃后只能恢复到 `INTERRUPTED`，不能续跑未完成环境；
- 无法强制中断已经发出的 HTTP 请求；
- Windows 文件替换存在瞬时共享冲突，已加入读重试与原子替换重试；
- 真实费用以 Provider 账单为准；本地只记录可确认 usage 的估算/结算值。

## 7. 何时需要重新选型

出现以下任一情况时，应先写新 ADR：

- 需要公网访问或多用户隔离；
- 需要并发执行多局付费任务；
- 需要断点续跑完整环境状态；
- Streamlit 无法满足取消/状态隔离（当前实测满足）。
