# V13 实验报告：v13-demo

- `experiment_id`：`lab-20261026T123446Z-cf687cd5`
- 数据来源：`SIMULATED` — **SIMULATED**：确定性脚本 Provider，只验证调用链/预算/诊断，不代表任何真实模型能力。
- 状态：`COMPLETED`；执行通道：`simulated`
- 模型 / Provider：`simulated-agent-policy` / `simulated_scripted`
- 地图：MAP-22, MAP-16
- 环境 seed：[0]；重复次数：2
- 实验臂：basic.v1, memory.v2, planning.v2, reflection.v2
- 运行时版本：`v12-lab-1+agent_policy_v1+v12-contract-2`

## 0. 结论摘要（分级 + 锚点）

- `INSUFFICIENT`（范围：截尾比例 1.0） 有效分母 16 局，成功 0 局；可比性判定 `COMPARABLE`。  
  锚点：`experiment:lab-20261026T123446Z-cf687cd5`
- `TENTATIVE`（范围：重复不是新的环境 seed） 同条件重复的结局翻转率为 0.0（0/8 组）；单次观测不足以下架构结论。  
  锚点：`experiment:lab-20261026T123446Z-cf687cd5`
- `TENTATIVE` 3 个实验臂出现反向、零提升或成本升高，已如实保留。  
  锚点：`experiment:lab-20261026T123446Z-cf687cd5`

## 1. 研究问题与预注册

- **未预注册协议**：本报告属于 `ad_hoc` 分析，结论强度上限为 `TENTATIVE`。

## 2. 设置与可比较性

- 配对判定：`COMPARABLE`
- 采样参数登记：support=`UNKNOWN`，对外口径 `UNKNOWN`（环境 seed 固定 ≠ 模型输出可复现）
- 有效分母只含：完成且成功 / 机制失败 / 预算截尾；Provider 错误、取消、中断、策略异常**不计入**。

## 3. 分母与结果

| 口径 | 值 |
|---|---:|
| all_attempted | 16 |
| evaluable | 16 |
| uncensored_finished | 0 |
| censored | 16 |
| invalid | 0 |
| censored_ratio | 1.0 |

| 实验臂 | 版本 | 局数 | 有效 | 成功 | 成功率 | 平均请求 | 平均费用 CNY |
|---|---|---:|---:|---:|---:|---:|---:|
| `basic.v1` | 1.0.0 | 4 | 4 | 0 | 0.0 | 16.0 | 0.0 |
| `memory.v2` | 2.0.0 | 4 | 4 | 0 | 0.0 | 15.5 | 0.0 |
| `planning.v2` | 2.0.0 | 4 | 4 | 0 | 0.0 | 19.0 | 0.0 |
| `reflection.v2` | 2.0.0 | 4 | 4 | 0 | 0.0 | 19.0 | 0.0 |

### 单局类别分布

| 类别 | 局数 |
|---|---:|
| 预算截尾（`budget_censored`） | 16 |

### 逐局锚点（每个数字都可回到原始 run）

| run_id | 地图 | seed | 实验臂 | 类别 | 锚点 |
|---|---|---:|---|---|---|
| `web-20261026T123446Z-b2e7342b` | MAP-22 | 0 | `basic.v1` | `budget_censored` | `run:web-20261026T123446Z-b2e7342b` |
| `web-20261026T123446Z-e7978af1` | MAP-22 | 0 | `memory.v2` | `budget_censored` | `run:web-20261026T123446Z-e7978af1` |
| `web-20261026T123446Z-5982b007` | MAP-22 | 0 | `planning.v2` | `budget_censored` | `run:web-20261026T123446Z-5982b007` |
| `web-20261026T123447Z-754d80ee` | MAP-22 | 0 | `reflection.v2` | `budget_censored` | `run:web-20261026T123447Z-754d80ee` |
| `web-20261026T123447Z-f1c894b2` | MAP-22 | 0 | `basic.v1` | `budget_censored` | `run:web-20261026T123447Z-f1c894b2` |
| `web-20261026T123447Z-48306370` | MAP-22 | 0 | `memory.v2` | `budget_censored` | `run:web-20261026T123447Z-48306370` |
| `web-20261026T123448Z-1a2c4524` | MAP-22 | 0 | `planning.v2` | `budget_censored` | `run:web-20261026T123448Z-1a2c4524` |
| `web-20261026T123448Z-07c6c351` | MAP-22 | 0 | `reflection.v2` | `budget_censored` | `run:web-20261026T123448Z-07c6c351` |
| `web-20261026T123449Z-d1e9c71c` | MAP-16 | 0 | `basic.v1` | `budget_censored` | `run:web-20261026T123449Z-d1e9c71c` |
| `web-20261026T123449Z-78c27153` | MAP-16 | 0 | `memory.v2` | `budget_censored` | `run:web-20261026T123449Z-78c27153` |
| `web-20261026T123450Z-49e5393e` | MAP-16 | 0 | `planning.v2` | `budget_censored` | `run:web-20261026T123450Z-49e5393e` |
| `web-20261026T123450Z-83e0adf3` | MAP-16 | 0 | `reflection.v2` | `budget_censored` | `run:web-20261026T123450Z-83e0adf3` |
| `web-20261026T123451Z-897ff62d` | MAP-16 | 0 | `basic.v1` | `budget_censored` | `run:web-20261026T123451Z-897ff62d` |
| `web-20261026T123451Z-c5b47c56` | MAP-16 | 0 | `memory.v2` | `budget_censored` | `run:web-20261026T123451Z-c5b47c56` |
| `web-20261026T123452Z-381f9838` | MAP-16 | 0 | `planning.v2` | `budget_censored` | `run:web-20261026T123452Z-381f9838` |
| `web-20261026T123452Z-4819e893` | MAP-16 | 0 | `reflection.v2` | `budget_censored` | `run:web-20261026T123452Z-4819e893` |

## 4. 负面结果（如实保留）

| 实验臂 | 原因 | 锚点 |
|---|---|---|
| `memory.v2` | 成功率与基线相同（0.0），没有可观察提升 | `run:web-20261026T123446Z-e7978af1`、`run:web-20261026T123447Z-48306370`、`run:web-20261026T123449Z-78c27153` |
| `planning.v2` | 成功率与基线相同（0.0），没有可观察提升 | `run:web-20261026T123446Z-5982b007`、`run:web-20261026T123448Z-1a2c4524`、`run:web-20261026T123450Z-49e5393e` |
| `reflection.v2` | 成功率与基线相同（0.0），没有可观察提升 | `run:web-20261026T123447Z-754d80ee`、`run:web-20261026T123448Z-07c6c351`、`run:web-20261026T123450Z-83e0adf3` |

## 5. 成本

- 已结算：CNY 0.0
- 未知消费：否
- 请求数：278

## 6. 失败原因（分层归因）

| 层 | 局数 |
|---|---:|
| `BUDGET_CENSORED` | 10 |
| `MEASUREMENT_COVERAGE` | 6 |

| 地图 | run_id | 类别 | 证据步 | 摘要 |
|---|---|---|---|---|
| MAP-22 | `web-20261026T123446Z-b2e7342b` | `no_progress_window` | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 | 连续 16 步公开进度没有变化。 |
| MAP-22 | `web-20261026T123446Z-b2e7342b` | `key_action_used_no_trigger` | 5, 10, 15 | 机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。 |
| MAP-22 | `web-20261026T123446Z-b2e7342b` | `memory_key_not_in_metric` | 5, 10, 15 | 记忆写入成功，但没有使用指标口径内的键（bearing / path_state），因此 route_recall 为 NOT_APPLICABLE。 |
| MAP-22 | `web-20261026T123446Z-b2e7342b` | `budget_censored` | — | 预算/动作上限耗尽，指标按 CENSORED 处理。 |
| MAP-22 | `web-20261026T123446Z-e7978af1` | `no_progress_window` | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 | 连续 16 步公开进度没有变化。 |
| MAP-22 | `web-20261026T123446Z-e7978af1` | `budget_censored` | — | 预算/动作上限耗尽，指标按 CENSORED 处理。 |
| MAP-22 | `web-20261026T123446Z-5982b007` | `no_progress_window` | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 | 连续 16 步公开进度没有变化。 |
| MAP-22 | `web-20261026T123446Z-5982b007` | `key_action_used_no_trigger` | 4, 8, 12 | 机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。 |
| MAP-22 | `web-20261026T123446Z-5982b007` | `memory_key_not_in_metric` | 4, 8, 12 | 记忆写入成功，但没有使用指标口径内的键（bearing / path_state），因此 route_recall 为 NOT_APPLICABLE。 |
| MAP-22 | `web-20261026T123446Z-5982b007` | `budget_censored` | — | 预算/动作上限耗尽，指标按 CENSORED 处理。 |
| MAP-22 | `web-20261026T123447Z-754d80ee` | `no_progress_window` | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 | 连续 16 步公开进度没有变化。 |
| MAP-22 | `web-20261026T123447Z-754d80ee` | `key_action_used_no_trigger` | 4, 8, 12 | 机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。 |
| MAP-22 | `web-20261026T123447Z-754d80ee` | `memory_key_not_in_metric` | 4, 8, 12 | 记忆写入成功，但没有使用指标口径内的键（bearing / path_state），因此 route_recall 为 NOT_APPLICABLE。 |
| MAP-22 | `web-20261026T123447Z-754d80ee` | `budget_censored` | — | 预算/动作上限耗尽，指标按 CENSORED 处理。 |
| MAP-22 | `web-20261026T123447Z-f1c894b2` | `no_progress_window` | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 | 连续 16 步公开进度没有变化。 |
| MAP-22 | `web-20261026T123447Z-f1c894b2` | `key_action_used_no_trigger` | 5, 10, 15 | 机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。 |
| MAP-22 | `web-20261026T123447Z-f1c894b2` | `memory_key_not_in_metric` | 5, 10, 15 | 记忆写入成功，但没有使用指标口径内的键（bearing / path_state），因此 route_recall 为 NOT_APPLICABLE。 |
| MAP-22 | `web-20261026T123447Z-f1c894b2` | `budget_censored` | — | 预算/动作上限耗尽，指标按 CENSORED 处理。 |
| MAP-22 | `web-20261026T123447Z-48306370` | `no_progress_window` | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 | 连续 16 步公开进度没有变化。 |
| MAP-22 | `web-20261026T123447Z-48306370` | `budget_censored` | — | 预算/动作上限耗尽，指标按 CENSORED 处理。 |

## 7. 重复稳定性

- 可比分组：8；翻转分组：0；翻转率：0.0
- 统计单位：重复次数 ≠ 环境 seed 数：同一 seed 的 3 次重复只说明抽样波动，不能当作 3 张地图实例的泛化证据。

## 8. 地图效度（构念层）

| 地图 | 标签 | 理由 |
|---|---|---|
| MAP-08 | `NEEDS_EVIDENCE` | 观测仅 0 局（< 3）。 |
| MAP-16 | `CENSORED` | 8/8 局预算截尾：0 成功不能读作能力不足。 |
| MAP-18 | `NEEDS_EVIDENCE` | 观测仅 0 局（< 3）。 |
| MAP-22 | `CENSORED` | 8/8 局预算截尾：0 成功不能读作能力不足。 |
| MAP-26 | `NEEDS_EVIDENCE` | 观测仅 0 局（< 3）。 |
| MAP-30 | `NEEDS_EVIDENCE` | 观测仅 0 局（< 3）。 |

## 9. 机制级能力画像

| 维度 | 可测局 | 成功率 | 证据等级 |
|---|---:|---:|---|
| 信息搜集 | 8 | — | `INSUFFICIENT` |
| 记忆 / 状态追踪 | 8 | — | `INSUFFICIENT` |
| 规划 / 重规划 | 8 | — | `INSUFFICIENT` |
| 资源约束 | 8 | — | `INSUFFICIENT` |
| 故障恢复 | 0 | — | `NOT_TESTED` |
| 证据推理 | 0 | — | `NOT_TESTED` |

> 标注状态：`agent_reviewed`（不是 human_approved）

## 10. 统计与解释限制

- 每个配对键通常只有 1 局；重复次数增加不改变「同一环境 seed」这一事实。
- 结论等级由证据结构决定，不由成功率高低决定。
- 模拟数据不能用于声称模型能力；历史数据不能冒充本轮新结果。
- 接口/测量层的问题不算能力差异（见分层归因）。

## 11. 下一轮可验证假设

- 在同一 `(map, seed, replicate_index)` 上只改一个开关，重复 ≥3 次，观察首次差异步是否前移。
- 若某条件翻转率仍 > 20%，先扩大重复次数，再讨论架构优劣。
- 预算截尾的图先做预算阶梯，不要用低预算的 0 成功当作能力结论。

## 12. 复现

```bash
uv run python scripts/verify_v13.py          # 离线一键验收
uv run python scripts/demo_v13.py            # 零 Key 演示（SIMULATED）
```

实验目录：`runs/lab/lab-20261026T123446Z-cf687cd5/`；子局仍在 `runs/web/<run_id>/`。
