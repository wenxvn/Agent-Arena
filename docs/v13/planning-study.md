# Planning 策略研究（P0-3）

- 数据来源：`HISTORICAL`（V12 真实局）+ `SIMULATED`（V13 机制验证）
- 本轮新增真实付费请求：**0**
- 结论强度：机制层面 `SUPPORTED`；真实收益 `WAITING_USER_APPROVAL`

## 1. 审计：`planning.v1` 的重规划逻辑

| 触发 | 规则 | 观察 |
|---|---|---|
| 初始 | `_plan is None` | 必调 1 次 Planner |
| 无进展 | 公开进度指纹连续 `replan_every=6` 次未变 | 长局会触发多次 |
| 连续被拒 | `reject_streak >= 2` | 与无进展可能同时成立 |
| 上限 | `max_plans=8` | 到上限后只提示一次 |

**问题**：

1. **没有节流**：两个触发条件可能在同一段连续被拒里反复触发（每 2 步一次）；
2. **没有预算感知**：剩余决策很少时仍然花钱规划；
3. **无法分离消融**：想测"重规划是否有用"，只能把 `replan_every` 调到很大——
   这同时改了"无进展阈值"，不是单因子；
4. **成本不可逐请求归因**：只知道 `purposes["planner"]` 总数，不知道哪次触发、
   对应哪个决策、花了多少 token/延迟。

## 2. `planning.v2` 的三个可分离因子

| 配置 | 取值 | 语义 |
|---|---|---|
| `enabled` | True/False | **规划开/关**（关 = 不请求 Planner、不注入计划） |
| `planner_mode` | `adaptive`（默认） | 只在公开触发条件成立时重规划 |
| | `initial_only` | 只规划一次 → **重规划关** |
| | `periodic` | 每 `min_steps_between_plans` 步强制重规划 → **低频/高频** |
| `min_steps_between_plans` | 4（默认） | TTL 下限：两次计划之间至少隔几步 |
| `stall_threshold` | 4 | 无进展触发阈值 |
| `reject_threshold` | 2 | 连续被拒触发阈值 |
| `max_plans` | 6 | 上限 |
| `budget_aware` | True | 剩余决策不足时跳过规划 |

这三个因子可以**分别**开关，因此 V13 的消融是真正的单因子：

```text
planning.on_off          : enabled True ↔ False
planning.replan_off      : planner_mode adaptive ↔ initial_only
planning.low_frequency   : min_steps_between_plans 4 ↔ 12
```

## 3. Planner 输出仍然是非执行性的

离线证据（`test_planning_v2_planner_output_is_non_executive`）：即使 Provider 在
Planner 响应里塞了 `"tool": "move"`，计划对象里也不会出现 `tool` 字段。

Planner 只能输出：`current_subgoal` / `success_criteria` / `known_constraints` /
`relevant_resources` / `unresolved_questions` / `decision_reason`。
动作永远由 Executor 在同一个动作契约下产生。

## 4. 减少不必要规划：触发 + TTL + 预算

| 机制 | 行为 | 证据 |
|---|---|---|
| 公开触发 | 只有 无进展 / 连续被拒 / 目标变化 / 进度变化且计划已旧 才重规划 | `test_planning_v2_adaptive_defers_trigger_with_ttl` |
| TTL 下限 | 触发被延迟 → 写 `planner_deferred_ttl` 事件 | 同上（`skipped_ttl >= 1`） |
| 预算感知 | 剩余决策 ≤ 25% 初始预算 → 写 `planner_skipped_budget`，不请求 | `test_planning_v2_budget_aware_skips_planner` |

**已知代价（不隐藏）**：TTL 会延迟响应。例如连续被拒在第 2 步就达到阈值，
但 TTL=8 会把它推迟到第 8 步之后——这段时间里 Agent 仍用旧计划。
这是"少花钱"换来的，报告里必须写明。

## 5. 逐请求成本归因

`snapshot()["plan_requests"]` 每条形如：

```json
{"plan_index": 2, "trigger": "no_progress", "decision_index": 7,
 "requests": 1, "input_tokens": 3120, "output_tokens": 180,
 "latency_ms": 940, "accepted": true}
```

因此可以回答"第 7 步为什么多花了 3120 输入 token"，而不只是"这局 Planner 调了 3 次"。

## 6. MAP-16 / MAP-18 的分离消融设计（PLANNED_ONLY）

| 消融 | 地图 | seed | 对照 | 重复 | 关键指标 |
|---|---|---|---|---|---|
| 规划开/关 | MAP-16 | 0,1,2 | `enabled` | ≥3 | 成功、`planner_requests`、token、费用 |
| 重规划开/关 | MAP-16 | 1,2（有梯度） | `planner_mode` adaptive↔initial_only | ≥3 | `plan_count`、首次差异步 |
| 低频 Planner | MAP-16 | 1,2 | `min_steps_between_plans` 4↔12 | ≥3 | `planner_requests`、`skipped_ttl`、成功 |
| 规划开/关 | MAP-18 | 0,1,2 | `enabled` | ≥3 | 同上（MAP-18 的梯度在 memory 侧，预期 planning 无收益） |

**必须避免的做法**：把 `replan_every`、`max_plans`、`stall_threshold` 一起调，
然后说"规划变好了"——那是多开关组合，不是单因子效果。

## 7. 旧证据（V12 真实结果，只读）

| 条件 | 结果 | 读法 |
|---|---|---|
| MAP-16 `planning.v1` | 6/13（含 seed 3、重复） | 唯一稳定的正向梯度；3 次观测里 `seed=1` 是 **3/3** |
| MAP-16 `basic.v1` | 1/9 | 基线 |
| MAP-16 `memory.v1` | 0/9 | 记忆在这张图没有帮助 |
| MAP-18 `planning.v1` | 1/11 | 反向：MAP-18 的梯度在 memory 侧 |
| 代价 | `planning.v1` 平均请求 27.46 vs `basic.v1` 7.67 | **约 3.6 倍请求** |

**成功路径的可解释案例**：MAP-16 的整帧调度要求先 `set_route`/`occupy_siding`
登记下一跳，再 `move_train` 提交整帧。Planner 的子目标能把"先登记再提交"写进计划，
减少 `frame_mismatch`（V12 诊断里这是 MAP-16 的高频失败类）。

**失败路径**：MAP-16 seed 0 的失败在第 6 步 `DEADLOCK`，Planner 来不及介入——
这类失败不是"规划不够好"，而是**环境机制在早期就锁死**。

## 8. 哪些是证据、哪些是假设

| 陈述 | 类型 | 依据 |
|---|---|---|
| Planner 额外请求全部计入预算 | **证据** | `DecisionGateway` 唯一出口 + `purposes` 统计 |
| `initial_only` 只请求 1 次 | **证据** | 离线单测 `planner_requests == 1` |
| TTL 会延迟重规划 | **证据** | `planner_deferred_ttl` 事件 |
| 预算感知能省钱 | **证据**（机制） | `planner_skipped_budget` + 请求数不增 |
| Planning 在 MAP-16 提升成功率 | **假设（有描述性支持）** | 6/13 vs 1/9，但翻转率 22–25%，且只有单 seed 3/3 |
| 低频 Planner 不损失成功率 | **未验证** | 需要 LIVE 配对 |

## 9. 下一轮 LIVE 待批准矩阵（PLANNED_ONLY）

12 个条件 × 3 次重复 = 36 局；按 ¥0.50/局上界 = ¥18，预计实际 ¥1.5–2.5。
**未获授权前不执行**，详见 `docs/v13/live-budget-proposal.md` E2。

## 10. 不支持的主张

- ❌ "Planning 是最好的架构"——MAP-18 上它是 1/11；
- ❌ "规划提升能力 3 倍"——只有 MAP-16 单图、且请求数也涨了 3.6 倍；
- ❌ "低频规划不损失效果"——未测。
