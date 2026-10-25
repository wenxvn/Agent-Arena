# ADR-V12-01：父 Experiment + 子 Run，复用 V11 运行服务

- **状态**：Accepted（`agent_reviewed`，未 `human_approved`）
- **日期**：2026-10-25
- **决策者**：执行 Agent（工程执行）
- **相关**：`docs/v12/00-audit.md`、`src/agent_arena/lab/experiment.py`

## 背景

第二阶段需要"同一模型、同一地图、同一 seed、同一预算下比较多种 Agent 架构"。V11 已经有
成熟的单局运行服务（状态机、单 worker、取消、崩溃恢复、幂等、跨进程锁、单局预算、原子
存储、导出）。问题是：**多局实验应该怎么叠在它上面？**

三个候选：

1. 改造 `RunService` 让一个 run 表示整组实验；
2. 在 `RunService` 之上加一层父实验，子局仍是普通 run；
3. 新写一套独立的批量执行器，不复用 V11。

## 决策

采用 **方案 2**：`ExperimentService` 是父，子局是 V11 的普通 `run`。

```text
ExperimentService (runs/lab/<experiment_id>/)
        │  create_run(config with experiment_id + matrix_index)
        ▼
RunService (runs/web/<run_id>/)  ← 未改动其状态机、锁、预算、存储
        │
        ▼
lab/runner.py (AgentPolicy + DecisionGateway) 或 web/execution.py (v10_action_loop)
```

### 关键实现约束

- `ExperimentService` **不**自己执行环境，只调用注入的 `RunService`；
- 子局 `RunConfig` 新增 `experiment_id`、`matrix_index`、`agent_config`（都可空，旧 manifest 仍可读）；
- 父实验幂等键落在子局上（`f"{experiment_id}:{matrix_index}"`），因此"重复提交父实验"不会产生第二个已收费 run；
- 父实验状态机独立：`CREATED → QUEUED → RUNNING → {COMPLETED, PARTIAL, CANCELLED, FAILED}`，`STOPPING` 为协作式中间态；
- 父实验预算只做**聚合与门禁**，真正的单局硬门禁仍由 `RunBudget` 执行。

## 为什么不选方案 1

- `RunService` 的状态机、恢复、锁、账本都假设"一个 run = 一局"；把整组塞进 run 会让
  `manifest.state` 同时表示父与子，恢复逻辑无法区分"父未开始"与"子跑到一半"；
- V11 的 `ConcurrentLiveRunError`、`_guard_live_start`、`_ledger_*` 都以 run 为粒度，
  改造会破坏既有语义与测试，违背"不牺牲 V11"的硬约束。

## 为什么不选方案 3

- 会立刻复制出第二套状态机、第二套锁、第二套恢复逻辑，两套账本口径迟早漂移；
- 提纲明确要求"优先扩展，避免平行实现第二套运行服务"。

## 后果

**收益**

- 子局天然获得 V11 全部安全属性（取消、刷新不重复计费、进程重启恢复、单 worker 串行）；
- `runs/web/<run_id>/` 结构不变，V11 页面、导出、历史查询继续可用；
- 父实验只新增 `runs/lab/`，与旧数据完全隔离。

**代价**

- 父实验的"实验级"语义要自己维护（矩阵、汇总、配对、门禁）；
- 子局被删除/损坏时父实验只能降级（`records()` 跳过并记录），不能凭空重建；
- 父实验与子局之间没有数据库事务，靠 append-only 事件 + 幂等键保证最终一致。

**已知边界**

- 同一时刻只允许一个父实验运行（`ExperimentBusy`）；这是刻意的，避免并发付费；
- `stop()` 只保证"不再开始新子局"，已发出的网络请求不会被强制中断（与 V11 一致）；
- 子局中断后**不自动重跑**：必须显式 `submit(resume=True)`，且已 `INTERRUPTED`/未知消费的子局会被跳过。

## 替代方案记录

| 方案 | 结论 | 原因 |
|---|---|---|
| 在 Streamlit 里直接循环创建 run | 拒绝 | UI 会成为任务事实来源，刷新即丢失 |
| 用线程池并发跑 54 局 | 拒绝 | 并发付费请求、Provider 限流、账本竞态 |
| 用 SQLite 存实验状态 | 拒绝 | 引入新依赖与新事务语义；append-only JSONL 已够用且可审计 |
| 子局写入父实验目录 | 拒绝 | 会复制 RunStore 数据，破坏 V11 单一事实来源 |
