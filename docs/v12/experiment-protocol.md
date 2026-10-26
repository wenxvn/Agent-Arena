# V12 实验协议（预登记）

- **状态**：矩阵与门禁已冻结；**真实执行已完成**（Pilot 6 局 + 主矩阵 54 局 + 版本复跑 9 局，结算 ¥1.82140020）
- **schema**：`v12-lab-1`
- **登记日期**：2026-10-25
- **对应代码**：`src/agent_arena/lab/contracts.py`（`ExperimentSpec`）、`lab/experiment.py`（`preflight`）

## 1. 研究问题

> 在同一张任务地图、同一环境 seed、同一模型、同一预算下，把 Agent 架构从
> `basic.v1` 换成 `memory.v1` 或 `planning.v1` 之后，**行为、成功率、成本与失败原因**
> 有哪些可验证的差异？

不含的假设：

- 不预设 Memory > Basic 或 Planning > Memory；
- 不宣称"架构更好"，只报告可复核的差异与代价；
- 3 seed 不是统计显著性检验。

## 2. 主矩阵（54 局，待批准）

| 维度 | 取值 |
|---|---|
| 地图 | `MAP-08`、`MAP-16`、`MAP-18`、`MAP-22`、`MAP-26`、`MAP-30` |
| 实验臂 | `basic.v1`、`memory.v1`、`planning.v1` |
| 环境 seed | 每图取 `seed_space(map_id)` 的共同前 3 个；六图共同可用为 `0/1/2`（运行时核验，不假设） |
| 模型 | 单一已授权模型（MiMo 有登记价目；其它模型不启用金额硬门禁） |
| 执行 | 单 worker 串行 |
| 子局数 | 6 × 3 × 3 = **54** |

**seed 核验结果**（`v10.runtime.catalog.seed_space`）：

| 地图 | seed 空间 | 前 3 |
|---|---|---|
| MAP-08 | 0,1,2,3 | 0,1,2 |
| MAP-16 | 0,1,2,3 | 0,1,2 |
| MAP-18 | 0,1,2,3,4 | 0,1,2 |
| MAP-22 | 0,1,2,3 | 0,1,2 |
| MAP-26 | 0,1,2,3 | 0,1,2 |
| MAP-30 | 0,1,2 | 0,1,2 |

## 3. 被操纵的变量（公平口径）

保持不变：

- 同一 `system_prompt`（`web/prompting.py::system_prompt`，与 V10/V11 冻结提示逐字一致）；
- 同一动作契约与 `V8Action` 校验；
- 同一 5 步历史窗口语义；
- 同一 `DecisionGateway`（唯一模型出口）与同一 `RunBudget` 上限；
- 同一地图规则版本、同一 seed、同一指标 schema。

**唯一变化**：策略额外注入的上下文与额外请求。

| 臂 | 注入的额外上下文 | 额外模型请求 |
|---|---|---|
| `basic.v1` | 无 | 0 |
| `memory.v1` | 结构化公开记忆（`memory_data`，≤1200 字符） | 0（默认） |
| `planning.v1` | 当前计划（`plan_data`） | Planner 调用，全部计费 |

`planning.v1` 的 Planner 使用 `output_contract="planner"`，只输出计划字段，不输出动作。

## 4. 预算与门禁

| 门禁 | 默认值 | 位置 |
|---|---|---|
| 单局请求上限 | 60 | `ExperimentBudget.per_run_request_cap` → `RunConfig.max_requests` |
| 单局决策上限 | 该图登记预算（`decision_budget`） | `per_run_decision_cap`（空则取登记值） |
| 单局输入 token | 200 000 | `per_run_input_token_cap` |
| 单局输出 token | 8 000 | `per_run_output_token_cap` |
| 单局费用 | ¥1.00 | `per_run_cost_cap_cny` |
| 实验请求上限 | 2 000 | `experiment_request_cap` |
| 实验费用上限 | ¥5.00 | `experiment_cost_cap_cny` |
| 墙钟 | 7 200 秒 | `wall_clock_cap_seconds` |
| 未知消费 | `stop`（立即封账，不重试） | `unknown_spend_policy` |

**未知消费规则**：任一子局 `cost_unknown=true` → 父实验立即停止后续子局，`manifest.budget.cost_unknown=true`，并在报告里单列。

## 5. 预检（零请求）

`preflight(spec)` 只做本地检查，**不创建实验、不发请求**：

- 矩阵规模与 seed 合法性（逐图核验 `seed_space`）；
- Provider 配置是否齐全（读 `.env`，不联网）；
- 请求/费用上界与实验级上限比较；
- 真实付费是否已批准（未批准即 blocker）；
- `preflight_only=true` 时即使批准也不提交。

## 6. 执行顺序与停止条件

1. 预检通过 → `create_experiment`（写 `experiment.json` + `manifest.json`）；
2. `submit` → 单 worker 串行，按 `matrix_index` 顺序；
3. 每个子局：`RunService.create_run` → 等待终态 → 读 `result.json` → 更新父 manifest；
4. 停止条件（任一满足即停）：
   - 用户 `stop()`；
   - 实验请求上限用尽；
   - 实验费用上限将被突破；
   - 任一子局未知消费；
   - 墙钟超时；
   - 父实验内部异常（`internal_error:*`）。

停止后父实验为 `PARTIAL`（有已完成子局）或 `CANCELLED`（一局未完成）。

## 7. 断点续跑

- 以**子局**为单位：`submit(resume=True)` 只排尚未执行的 `matrix_index`；
- 已完成 / 已中断 / 未知消费的子局**不自动重跑**；
- 确需补跑必须新建补充实验，并在 `notes` 注明来源。

## 8. 统计口径

| 类别 | 是否进入有效分母 |
|---|---|
| `completed_success` | 是 |
| `mechanism_failure`（`scenario_failure`） | 是 |
| `budget_censored`（`BUDGET_REACHED`） | 是 |
| `provider_error` | **否** |
| `cancelled` | **否** |
| `interrupted` | **否** |
| `invalid_run`（`policy_error` 等） | **否** |
| `pending`（未执行） | **否** |

配对键：`(map_id, environment_seed)`。判定：

- `COMPARABLE`：同模型/Provider/模式，同图同 seed，规则与指标 schema 一致；
- `DESCRIPTIVE_ONLY`：可配对但样本不足 `min_paired_samples=3`；
- `INCOMPARABLE`：模型/Provider/模式/规则/指标 schema 不一致，或费用一方未知，或没有可配对条件。

**不做**：跨图绝对分平均、p 值、显著性断言、"提升 X%"。

## 9. 输出

```text
runs/lab/<experiment_id>/
  experiment.json     # 冻结规格 + 矩阵 + 指纹
  manifest.json       # 父状态、children、预算汇总
  events.jsonl        # append-only 父事件
  children.json       # 子局链接（只存 run_id，不复制数据）
  summary.json        # 汇总与有效分母
  comparison.json     # 版本门禁与配对
  report.md           # 可读报告
  exports/{runs,metrics,paired_comparison,findings}.csv + *.json
runs/web/<run_id>/    # V11 子局结构（新增可选 provenance 字段）
```

## 10. 真实执行（已授权并完成）

- [x] 用户书面批准费用上限（`LiveApproval.approved=true` + `approved_by` + `max_cost_cny=6.00`）；
- [x] 先跑 6 局 Pilot，覆盖 Basic/Memory/Planning 与两图；
- [x] Pilot 通过后跑 54 局主矩阵（6 图 × 3 seed × 3 架构）；
- [x] 发现 DCR-V12-01 后，用**版本复跑**重测 MAP-22 九局（不与旧版本配对）；
- [x] 未超预算：结算 ¥1.82140020 / 批准 ¥6.00；未知消费 ¥0。

状态：**已完成**。明细见 `mimo-results.md` 与 `dcr/DCR-V12-01.md`、`dcr/DCR-V12-02.md`。

## 11. 版本与复跑口径

| 场景 | 入口 | 改变什么 | 是否重跑已完成局 | 是否与原矩阵配对 |
|---|---|---|---|---|
| 续跑（进程中断/未执行） | `--resume <id>` | 无 | 否 | 是（同版本） |
| 补充实验（失败/未执行/取消） | `--supplement-of <id>` | 无（只挑条件） | 否 | 是（同版本） |
| 版本复跑（契约/提示变更后重测） | `--rerun-of <id> --conditions ...` | 运行时版本 | **是** | **否**（`prompt_hash` 已变） |
| 预算扩展（解除截尾） | `--budget-ext-of <id> --ext-requests N` | 预算 | **是** | **否**（预算不同） |
| 重复（测量波动） | `--replicate-of <id> --conditions ...` | 什么都不改 | **是** | **否**（独立实验，同条件） |

五条路径都新建独立实验、都不修改源实验的 manifest/账本/run 记录。
实验身份包含 `runtime_version`（`v12-lab-1+agent_policy_v1+v12-contract-N`），
因此"改完代码复跑"不会静默命中旧实验。
