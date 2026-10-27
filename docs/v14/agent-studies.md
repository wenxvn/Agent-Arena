# V14 Agent 机制与 LIVE 状态

- 版本：`v14-agent-studies-1`（2026-10-27）
- 数据来源：`SIMULATED`（离线确定性 probe）+ `HISTORICAL`（V12 只读 CSV）
- V14 新增真实付费请求：**0**
- 三种证据严格分列：`SIMULATED` / `HISTORICAL` / `LIVE`

> 本文件不构成执行授权。所有真实模型效果一律 `LIVE_PENDING`：
> 未获用户对"模型 / 矩阵 / 总费用上限"的明确批准前，不得提交任何 LIVE 请求。

## 1. Memory（P0-4）

### 1.1 离线机制 probe（SIMULATED，零模型请求）

脚本：`north`（接受）→ `north`（被拒）→ `east`（接受）→ 缺 `bearing`（非法）→ `south`（接受）→ `west`（接受）→ 收尾 `wait` 一次以抓取最终记忆块。

| 臂 | 决策 | 请求 | 路线 | 被拒 | 非法 | 写入尝试 | 写入接受 | 渲染 | 瓶颈 |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| `context_only_on` | 7 | 7 | `north,east,south,west` | 1 | 1 | 0 | 0 | 7 | `RECORDED_AND_RENDERED` |
| `context_only_off` | 7 | 7 | `—` | 0 | 0 | 0 | 0 | 7 | `NO_RECORD` |
| `env_write_on` | 8 | 6 | `north,east,south,west` | 1 | 1 | 2 | 2 | 6 | `RECORDED_AND_RENDERED` |
| `disabled` | 7 | 7 | `—` | 0 | 0 | 0 | 0 | 0 | `DISABLED` |

> 瓶颈列是 **V14 投影**（`memory_bottleneck_v14`）：``env_write`` 按「已写入方位数」判定。
> ``memory.v2.bottleneck()`` 原口径把「写入次数」与路线长度比较，一次写入整段路线时会被误判为 `RECORDED_TOO_SHORT`（DCR-V14-03）。

三条 fixture（全部可在 `tests/test_v14_agent_studies.py` 复算）：

1. **被拒/非法移动不进路线**：`route_preview` 恒等于脚本里被接受的方位序列（`route_matches_expected`）；
2. **回到起点仍能引用完整方位**：`context_only` 的最终记忆块与`env_write` 的写入载荷都包含 `north,east,south,west`（`final_block_has_all_bearings`）；
3. **不写答案**：记忆块里没有隐藏真值关键词（`memory_block_leaks` 为空），路线只来自公开 `move` 结果。

### 1.2 写入机制的代价（不可互相冒充）

| 臂 | 决策 | 请求 | 说明 |
|---|---:|---:|---|
| `context_only_on` | 7 | 7 | 不发动作，路线只进 prompt |
| `env_write_on` | 8 | 6 | 每次写入占 1 次决策、0 次请求 |

- `env_write` 写入载荷：`north,east,south,west`；V14 投影 `route_recall = 1.0`（`VALID`）。
- `context_only` 不写环境，V10 官方 `route_recall` 在本臂为 `NOT_APPLICABLE`——必须与 V14 投影分列，不能混算。

### 1.3 单因子审计

| 组 | 对照 | 处理 | 唯一变化键 | 单开关 |
|---|---|---|---|---|
| E1-a | `E1-a-control` | `E1-a-treatment` | `route_log` | 是 |
| E1-b | `E1-b-control` | `E1-b-treatment` | `route_mode` | 是 |

- 全部单因子：是
- 每组只改一个配置键；``route_mode`` 在 E1-a 两组里被钉成 context_only，因此 E1-a 测的是 route_log 本身，不会混入写入机制的差异。

### 1.4 预检登记（`PLANNED_ONLY`，零请求）

| 项 | 值 |
|---|---|
| 地图 | MAP-22 |
| seed | [0, 1, 2] |
| 重复 | 3 |
| 组 | E1-a, E1-b |
| 子局 | 36 |
| 单局预算 | 90 请求 / 200000 token / ¥0.5 |
| 实验费用上限 | ¥5.0 |
| 状态 | `PLANNED_ONLY` / `LIVE_PENDING` |

- 比较口径：同一总预算、同一 memory.v2 版本、同一 prompt 主体、同一 seed；只允许被测开关不同（E1-a 改 route_log，E1-b 改 route_mode）。
- V14 未获用户对模型/矩阵/总额的批准，因此本计划不得执行；``scripts/run_v12_matrix.py --ablation`` 只允许在默认预检模式下运行。

## 2. Planning（P0-5）

### 2.1 离线触发链（SIMULATED，零模型请求）

脚本：1 步有进度 → 2 次被拒 → 5 步无进度 → 4 步恢复；共 12 次决策。

| 臂 | 决策 | 总请求 | Planner 请求 | Planner token(in) | 计划数 | TTL 跳过 | 预算跳过 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `adaptive` | 12 | 15 | 3 | 360 | 3 | 1 | 0 |
| `initial_only` | 12 | 13 | 1 | 120 | 1 | 0 | 0 |
| `periodic_4` | 12 | 15 | 3 | 360 | 3 | 0 | 0 |
| `periodic_12` | 12 | 13 | 1 | 120 | 1 | 0 | 0 |
| `disabled` | 12 | 12 | 0 | 0 | 0 | 0 | 0 |
| `budget_guard` | 12 | 15 | 3 | 360 | 3 | 4 | 2 |
| `max_plans` | 12 | 14 | 2 | 240 | 2 | 2 | 0 |

逐决策链（`adaptive`）：

| 步 | 触发 | 事件 | 被挡 | Planner 请求 | 子目标 | 公开结果 | 请求 |
|---:|---|---|---|---:|---|---|---:|
| 0 | `initial` | `plan_created` | `—` | 1 | 子目标 #1：沿公开线索推进 | `MOVED` | 2 |
| 1 | `—` | `—` | `—` | 0 | — | `BEARING_NOT_AVAILABLE` | 1 |
| 2 | `—` | `—` | `—` | 0 | — | `BEARING_NOT_AVAILABLE` | 1 |
| 3 | `repeated_rejection` | `planner_deferred_ttl` | `ttl` | 0 | — | `NO_EFFECT` | 1 |
| 4 | `no_progress` | `plan_replanned` | `—` | 1 | 子目标 #2：沿公开线索推进 | `NO_EFFECT` | 2 |
| 5 | `—` | `—` | `—` | 0 | — | `NO_EFFECT` | 1 |
| 6 | `—` | `—` | `—` | 0 | — | `NO_EFFECT` | 1 |
| 7 | `—` | `—` | `—` | 0 | — | `NO_EFFECT` | 1 |
| 8 | `public_progress` | `plan_replanned` | `—` | 1 | 子目标 #3：沿公开线索推进 | `MOVED` | 2 |
| 9 | `—` | `—` | `—` | 0 | — | `MOVED` | 1 |
| 10 | `—` | `—` | `—` | 0 | — | `MOVED` | 1 |
| 11 | `—` | `—` | `—` | 0 | — | `MOVED` | 1 |

> Planner 请求与动作请求同属一次决策的 ``requests``；成本按 requests + input/output token 分别记账，Planner 不免单。

被挡下的两条路径（`stall_threshold=2` + 12 步无进度）：

| 臂 | 决策数 | 计划数 | TTL 跳过 | 预算跳过 | Planner 请求 | 总请求 |
|---|---:|---:|---:|---:|---:|---:|
| `budget_guard` | 12 | 3 | 4 | 2 | 3 | 15 |
| `max_plans` | 12 | 2 | 2 | 0 | 2 | 14 |

### 2.2 三组独立单因子

| 组 | 对照 | 处理 | 唯一变化键 | 单开关 |
|---|---|---|---|---|
| E2-a | `E2-a-control` | `E2-a-treatment` | `enabled` | 是 |
| E2-b | `E2-b-control` | `E2-b-treatment` | `planner_mode` | 是 |
| E2-c | `E2-c-control` | `E2-c-treatment` | `min_steps_between_plans` | 是 |

- 全部单因子：是
- E2-a 改 ``enabled``；E2-b 改 ``planner_mode``（adaptive→initial_only）；E2-c 改 ``min_steps_between_plans``（4→12，两臂都钉 ``periodic``）。三组互不混用；MAP-18 只作负向对照。

### 2.3 预检登记（`PLANNED_ONLY`，零请求）

| 项 | 值 |
|---|---|
| 主测地图 | MAP-16 |
| 负向对照 | MAP-18 |
| 子局 | 72（主测 54 + 对照 18） |
| 状态 | `PLANNED_ONLY` / `LIVE_PENDING` |

- 比较口径：同一**总预算**下比较：Planner 请求不免费，必须计入同一 requests/token/费用上限；若节流省钱但成功率下降，如实保留，不为追涨点放松预算。
- 负向对照：MAP-18 在 V12/V13 从未显示 planning 正梯度，保留为负向对照；若该图也出现「规划更好」，先怀疑测量与噪声，不当作收益证据。
- V14 未获用户对模型/矩阵/总额的批准，本计划不得执行；``scripts/run_v12_matrix.py --ablation`` 只允许默认预检模式。

## 3. Reflection（P0-6）

### 3.1 六态计数（SIMULATED，零模型请求）

| 臂 | 决策 | 总请求 | 反思请求 | eligible | triggered | 冷却挡 | 额度挡 | 误触发 | 恢复 | 暴露 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `disabled` | 12 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | `DISABLED` |
| `trigger_only` | 12 | 12 | 0 | 9 | 9 | 0 | 0 | 0 | 0 | `TREATMENT_TRIGGERED` |
| `reflection_on` | 12 | 15 | 3 | 3 | 3 | 6 | 0 | 0 | 2 | `TREATMENT_TRIGGERED` |
| `long_failure_on` | 12 | 15 | 3 | 3 | 3 | 6 | 1 | 0 | 3 | `TREATMENT_TRIGGERED` |
| `no_trigger_on` | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | `NO_TREATMENT_EXPOSURE` |

> `eligible` 只是候选；`triggered` 才是真的发生了干预。`trigger_only` 臂计入暴露但 `requests` 不增加。

### 3.2 暴露门禁

| 臂 | 状态 | 允许的结论 |
|---|---|---|
| `disabled` | `DISABLED_ARM` | 该臂不构成干预对照，只能作为无反思基线。 |
| `trigger_only` | `TREATMENT_TRIGGERED` | 干预确实发生；效果只能在「全部已分配局」与「触发子集」两组同时报告。 |
| `reflection_on` | `TREATMENT_TRIGGERED` | 干预确实发生；效果只能在「全部已分配局」与「触发子集」两组同时报告。 |
| `long_failure_on` | `TREATMENT_TRIGGERED` | 干预确实发生；效果只能在「全部已分配局」与「触发子集」两组同时报告。 |
| `no_trigger_on` | `NO_TREATMENT_EXPOSURE` | NO_TREATMENT_EXPOSURE：干预从未发生，不得报告「反思无效」；先改选有更长失败前缀的地图（改阈值必须另立版本）。 |

### 3.3 三臂单因子

| 比较 | 唯一变化键 | 单开关 | 预期 | 说明 |
|---|---|---|---|---|
| `E3-control` → `E3-treatment` | `enabled` | 是 | 单因子 | enabled（无反思 → 完整反思） |
| `E3-trigger-only` → `E3-treatment` | `trigger_only` | 是 | 单因子 | trigger_only（只判定 → 真请求） |
| `E3-control` → `E3-trigger-only` | `enabled、trigger_only` | **否** | 组合 | enabled + trigger_only |

- ``disabled→reflection_on`` 是组合对照（含触发判定 + 请求 + 注入），只能作为机制比较；单因子结论必须用 ``trigger_only→reflection_on``。

### 3.4 选择偏倚防护

效果评估必须同时给出两组口径（`evaluate_without_selection_bias`）：

| 口径 | 局数 | 有效 | 成功 | 成功率 |
|---|---:|---:|---:|---:|
| 全部已分配局 | 全部分母 | 同左 | 含未触发局 | 真实可用 |
| 触发子集 | 仅触发的局 | 更小 | 偏高 | **只作机制证据** |

> 只报触发子集等于把「没触发就失败」的局从分母删掉，会系统性高估效果。

### 3.5 预检登记（`PLANNED_ONLY`，零请求）

| 项 | 值 |
|---|---|
| 地图 | MAP-22 |
| 臂 | E3-control, E3-trigger-only, E3-treatment |
| 子局 | 27（两臂子集 18） |
| 状态 | `PLANNED_ONLY` / `LIVE_PENDING` |
| 激活门禁 | ``reflection_on`` 臂必须至少出现一次真实反思请求（``triggered > 0``）；否则记录 NO_TREATMENT_EXPOSURE 并改选地图，不得按「反思无效」报告。 |

- 候选地图（需先做离线公开诊断）：MAP-22（PRIMARY）；MAP-19（CANDIDATE）；MAP-20（CANDIDATE）；MAP-29（CANDIDATE）
- V14 未获用户对模型/矩阵/总额的批准，本计划不得执行；所有真实效果保持 LIVE_PENDING。


## 4. 汇总状态

| 机制 | 离线机制证据 | 单因子臂 | 预检登记 | 真实收益 |
|---|---|---|---|---|
| Memory（`memory.v2`） | `SUPPORTED` | E1-a / E1-b | `PLANNED_ONLY` | `LIVE_PENDING` |
| Planning（`planning.v2`） | `SUPPORTED` | E2-a / E2-b / E2-c | `PLANNED_ONLY` | `LIVE_PENDING` |
| Reflection（`reflection.v2`） | `SUPPORTED` | E3 三臂 | `PLANNED_ONLY` | `LIVE_PENDING` |

## 5. 不支持的主张

- ❌ "Memory 提高成功率 X%"：离线 probe 不含模型，不能给出成功率；
- ❌ "route_log 一定更好"：机制成立 ≠ 收益成立，需要真实配对实验；
- ❌ "`env_write` 比 `context_only` 好"：前者多吃决策预算，长局可能因此截尾；
- ❌ "V10 `route_recall` 为 0 说明没记忆"：`context_only` 不写环境，该口径本就 `NOT_APPLICABLE`；
- ❌ "Planner 请求不计成本"：Planner 与动作请求同属 `requests`，token 单独累加；
- ❌ "低频 Planner 一定更好"：省请求是事实，成功率代价必须同时报告。
