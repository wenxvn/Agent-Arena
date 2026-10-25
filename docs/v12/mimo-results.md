# V12 真实 API 结果（MiMo）

- **授权**：用户明确指示"可以用 API"（2026-10-25）
- **模型 / Provider**：`mimo-v2.6-flash` / `openai_compatible`（本机 `.env`，密钥不回显）
- **价格口径**：项目登记价目（输入 ¥1/M 未缓存、¥0.02/M 缓存、输出 ¥2/M）
- **执行**：单 worker 串行；每局与实验级门禁；未知消费立即封账
- **未修改**：V10 规则、指标、Oracle、历史账本与 trace
- **样本口径**：每条件 1 局、3 seed；**只作描述性对照，不作显著性断言**

## 0. 三个实验一览

| 实验 | `experiment_id` | 局数 | 状态 | 请求 | 结算 CNY | 未知消费 |
|---|---|---:|---|---:|---:|---|
| Pilot | `lab-20261025T120139Z-f9b93d5a` | 6 | COMPLETED | 131 | **0.09949940** | 无 |
| 主矩阵 v1 | `lab-20261025T120807Z-3aaedd0f` | 54 | COMPLETED | 1 507 | **1.47181116** | 无 |
| MAP-22 契约修复复跑 | `lab-20261025T134724Z-fa696780` | 9 | COMPLETED | 424 | **0.21606796** | 无 |
| 补充（取消局） | `lab-20261025T134136Z-bfe16b0f` | 1 | COMPLETED | 41 | 0.03376040 | 无 |
| **合计** | — | 70 | — | 2 103 | **1.82113892** | **0** |

另外有一个早期探针实验 `lab-20261025T125039Z-28494088`（1 局，¥0.00026128），
用于验证 CLI 提交路径，不参与分析。全部记录合计 **CNY ¥1.82140020**，未超 ¥6.00 批准上限。

## 1. Pilot（6 局，决定主矩阵参数）

矩阵：MAP-22 / MAP-26 × 3 架构 × seed 0。

| 地图 | seed | 架构 | 终态 | 决策 | 请求 | 费用 | 非法 | 被拒 |
|---|---:|---|---|---:|---:|---:|---:|---:|
| MAP-22 | 0 | basic.v1 | BUDGET_REACHED | 40 | 40 | 0.021303 | 0 | 0 |
| MAP-22 | 0 | memory.v1 | BUDGET_REACHED | 40 | 40 | 0.034690 | 0 | 0 |
| MAP-22 | 0 | planning.v1 | BUDGET_REACHED | 38 | 40 | 0.033504 | 0 | 0 |
| MAP-26 | 0 | basic.v1 | SUCCEEDED | 3 | 3 | 0.001978 | 0 | 0 |
| MAP-26 | 0 | memory.v1 | SUCCEEDED | 3 | 3 | 0.003016 | 0 | 0 |
| MAP-26 | 0 | planning.v1 | SUCCEEDED | 4 | 5 | 0.005008 | 0 | 0 |

Pilot 结论：

1. 动作契约干净：128 决策 **0 非法、0 被拒**，说明 `V8Action` 与契约渲染对本模型可用；
2. 计划/记忆事件真实：`planning.v1` 产生 `plan_created` + `plan_replanned`，
   `purposes={'decision':38,'planner':2}`；`memory.v1` 每步 `memory_updated`；
3. **MAP-22 的 40 请求上限太紧**：三臂全部截尾 → 主矩阵把单局上限提到 90；
4. 单价极低：40 请求约 ¥0.021–0.035，90 请求预算 ¥0.50 足够。

## 2. 主矩阵 v1（54 局）

### 2.1 总体

| 项 | 值 |
|---|---|
| 状态 | `COMPLETED`（54/54） |
| 有效分母 | **53**（1 局取消不计入） |
| 完成且成功 | 24 |
| 机制失败 | 19 |
| 预算截尾 | 10 |
| 取消 | 1 |
| Provider 错误 | 0 |
| 未知消费 | 0 |
| 请求 | 1 507 |
| 结算 | **CNY ¥1.47181116** |
| 可比性判定 | `COMPARABLE`（同模型/Provider/模式/规则/指标 schema） |

### 2.2 实验臂汇总

| 实验臂 | 局数 | 有效分母 | 成功 | 成功率 | 机制失败 | 截尾 | 平均决策 | 平均请求 | 平均费用 | 被拒动作 | 非法动作 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `basic.v1` | 18 | 18 | 7 | 0.3889 | 7 | 4 | 30.2 | 30.2 | 0.020467 | 103 | 0 |
| `memory.v1` | 18 | 17 | 8 | 0.4706 | 5 | 4 | 27.4 | 27.4 | 0.033087 | 85 | 0 |
| `planning.v1` | 18 | 18 | 9 | 0.5000 | 7 | 2 | 24.7 | 26.1 | 0.028214 | 20 | 1 |

**读法（不做显著性断言）**：

- 成功率 7 / 8 / 9 局，三臂差异只有 1–2 局，**在 18 局样本下不足以支持"某架构更好"**；
- 但**代价结构**差异清楚：`memory.v1` 平均费用最高（0.0331 vs 0.0205），因为记忆注入
  让每次请求的输入 token 变多，而请求数并没有减少；
- `planning.v1` 的额外 Planner 请求可见（平均请求 26.1 > 决策 24.7），但**总费用反而低于
  memory**（0.0282 vs 0.0331）；
- `planning.v1` 的被拒动作最少（20 vs 103 / 85），`basic.v1` 最多。

### 2.3 逐图 × 实验臂

| 地图 | 臂 | 局 | 成功 | 机制失败 | 截尾 | 其他 | 请求 | 费用 CNY |
|---|---|---:|---:|---:|---:|---|---:|---:|
| MAP-08 | basic | 3 | 3 | 0 | 0 | — | 10 | 0.006115 |
| MAP-08 | memory | 3 | 3 | 0 | 0 | — | 11 | 0.008426 |
| MAP-08 | planning | 3 | 3 | 0 | 0 | — | 14 | 0.012728 |
| MAP-16 | basic | 3 | 0 | 3 | 0 | — | 23 | 0.011086 |
| MAP-16 | memory | 3 | 0 | 3 | 0 | — | 23 | 0.018418 |
| MAP-16 | planning | 3 | **2** | 1 | 0 | — | 73 | 0.063698 |
| MAP-18 | basic | 3 | 0 | 3 | 0 | — | 27 | 0.026088 |
| MAP-18 | memory | 3 | **2** | 1 | 0 | — | 35 | 0.058781 |
| MAP-18 | planning | 3 | 0 | 3 | 0 | — | 28 | 0.039285 |
| MAP-22 | basic | 3 | 1 | 1 | 1 | — | 205 | 0.078548 |
| MAP-22 | memory | 3 | 0 | 1 | 1 | 取消 1 | 146 | 0.134551 |
| MAP-22 | planning | 3 | 1 | 2 | 0 | — | 126 | 0.108019 |
| MAP-26 | basic | 3 | 3 | 0 | 0 | — | 9 | 0.003425 |
| MAP-26 | memory | 3 | 3 | 0 | 0 | — | 9 | 0.007545 |
| MAP-26 | planning | 3 | 3 | 0 | 0 | — | 12 | 0.007994 |
| MAP-30 | basic | 3 | 0 | 0 | 3 | — | 270 | 0.243140 |
| MAP-30 | memory | 3 | 0 | 0 | 3 | — | 270 | 0.367840 |
| MAP-30 | planning | 3 | 0 | 1 | 2 | — | 216 | 0.276125 |

### 2.4 逐图结论（含天花板/地板与接口问题）

| 地图 | 观察 | 判定 |
|---|---|---|
| **MAP-08** | 9/9 成功，三臂无差异；请求 10–14 | **天花板效应**：该图对本模型过易，测不出架构差异 |
| **MAP-16** | basic 0/3、memory 0/3、planning **2/3**；planning 请求 73 vs 23 | 有梯度，但 planning 的优势同时伴随 **3 倍请求**；需更多 seed 才能判断 |
| **MAP-18** | basic 0/3、memory **2/3**、planning 0/3 | 有梯度，但**只有 memory 成功**；方向与 MAP-16 相反，说明单图结论不能外推 |
| **MAP-22** | 2/9 成功；`write_memory` 96.2% 被拒 | **接口假象**（DCR-V12-01）；该图结论作废，见 §3 |
| **MAP-26** | 9/9 成功，三臂无差异；请求 9–12 | **天花板效应** |
| **MAP-30** | 0/9 成功，8 局截尾（1 局机制失败）；请求 216–270 | **地板/截尾效应**：90 请求内未走到法庭提交；需要更高预算或更长预算的独立实验 |

### 2.5 关键机制证据

- `MAP-18` 的 `service_rate` 是唯一连续可比的量：0.333 / 0.667 / 1.0 三档，
  `memory.v1` 在 seed 0 与 seed 2 达到 1.0（送达 ≥13/18 人），其余多为 0.667；
  失败码集中在 `STATION_CAPACITY_EXCEEDED`、`HEAD_ON_COLLISION`、`SEGMENT_CAPACITY`；
- `MAP-16` 的失败码以 `INVALID_ROUTE`（`set_route` 目标不在方向表内）与
  `NO_PENDING_ROUTE`（未登记就 `move_train`）为主——**整帧语义**仍是主要难点；
- `MAP-30` 全部 9 局都记录到 3–4 个条目并 `chain_reconciled=True`（3 局），
  但没有一局在预算内到法庭提交（`formal_accuse` 只出现 1 次且被拒）。

## 3. MAP-22 契约修复复跑（DCR-V12-01）

修复前（主矩阵 v1）vs 修复后（`lab-20261025T134724Z-fa696780`）：

| 指标 | 修复前 | 修复后 |
|---|---:|---:|
| `write_memory` 调用 | 182 | 15 |
| 被拒 `INVALID_MEMORY_PAYLOAD` | **175（96.2%）** | **0（0%）** |
| 成功写入 | 7 | 15 |
| 成功局 | 2/9 | **4/9** |
| `route_recall` | 9/9 `NOT_APPLICABLE` | 9/9 `NOT_APPLICABLE` |
| 请求 | 477 | 424 |
| 费用 CNY | 0.321118 | 0.216068 |

**结论**：

1. 补丁有效：拒绝率从 96.2% 归零，说明 DCR-V12-01 的根因判断正确；
2. 成功率 2/9 → 4/9，但这**不能**归因为"记忆架构更好"——同一批条件在**不同 prompt 版本**下，
   且样本 9 局；只能说"接口修复后该图变得可测"；
3. `route_recall` 仍全是 `NOT_APPLICABLE`：记忆写入成功，但键名不在指标口径内
   （模型写 `at_sign` / `came_from` / `path_to_here`），这是 **DCR-V12-02**；
4. 因此 **MAP-22 的"记忆是否减少迷路"在本轮仍不可回答**。

`wasted_moves`（护栏指标）在修复后可读：0–34，`planning.v1` seed 0 为 0（最优返程），
`basic.v1` 与 `memory.v1` 多为 32–34（几乎走满非最短路）。

## 4. 失败归因汇总（139 条诊断）

| 类别 | 条数 | 说明 |
|---|---:|---|
| `repeated_action_loop` | 51 | 连续同动作，主要在 MAP-30 / MAP-22 |
| `NOT_ENOUGH_EVIDENCE` | 18 | 未命中规则（多为 MAP-08/26 的天花板局） |
| `no_progress_window` | 15 | 公开进度连续不变 |
| `key_action_used_no_trigger` | 10 | 机制动作被接受但阈值/时序未达 |
| `window_violation` | 10 | MAP-18 早于公开发车窗口 / 进入封闭区段 |
| `budget_censored` | 10 | 预算截尾（MAP-30 为主） |
| `repeated_rejected_action` | 7 | 重复被拒 |
| `memory_payload_rejected` | 6 | MAP-22 接口问题（DCR-V12-01） |
| `key_action_attempted_rejected` | 4 | 机制动作全被拒 |
| `memory_key_not_in_metric` | 3 | MAP-22 键名口径问题（DCR-V12-02） |
| `frame_mismatch` | 2 | MAP-16 整帧语义 |
| `unsupported_accusation` | 1 | MAP-30 指控被拒 |

严重度：critical 1（MAP-30 指控被拒）、warning 105、info 33。

## 5. 成本与账本

| 项 | 值 |
|---|---|
| 批准上限 | CNY ¥6.00 |
| 实际结算（5 个实验） | **CNY ¥1.82140020** |
| 未知消费 | **¥0.00** |
| 账本位置 | `runs/web/_ledger/web_ledger.jsonl`（append-only） |
| 每局一致性 | 每局 `result.json` 的 `usage.cost_settled_cny` 与账本 `run_settled` 一致 |

**未做**：Provider 后台账单对账（超出 V12 范围）。

## 6. 一次真实事故与修复（值得记录）

主矩阵第一次提交时，CLI 的默认等待是 1800 秒；54 局跑不完，进程退出，**进程内的
执行线程被杀**，留下 1 个孤儿 `QUEUED` 子局。父实验的 `children` 快照仍写着 `QUEUED`，
而真实 run 已被 `RunService` 收尾为 `CANCELLED`。

修复（`docs/v12/progress.md` 与 commit `d2ef08a`）：

- `_reconcile_children()`：以磁盘上的 run manifest 为准刷新父实验链接
  （状态、outcome、requests、cost、cost_unknown）；
- `supplement_candidates()` 也把 `CANCELLED` 与非终态子局列为候选；
- CLI `--timeout` 默认改为 0（一直等到终态），避免"调用方以为跑完了"；
- 新增 `--resume <experiment_id>` 与 `--rerun-of <experiment_id>`；
- 回归测试：`test_stale_child_link_is_reconciled_from_real_run_state`。

之后用 `--resume` 把剩余 19 局跑完，最终 54/54 `COMPLETED`，无重复计费。
