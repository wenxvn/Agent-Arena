# V1-05 Planning 公平对照（T5）

## 1. 研究问题与假设

- 问题：给 Planning 与成功 Memory 组合同样的公开 H/R/P，显式规划能否改善长程任务，还是继续增加无效重规划？
- 假设：旧失败主因是 Subgoal→Action grounding，而非规划表示本身。

## 2. 旧失败证据（reported 为主，本轮未重跑 qwen）

- Evaluation v2（`qwen2.5:7b`、seeds0-4、30步、autonomous）：0/5，重复动作 93.3%（主为 `look`），Planner call ratio 85.3%（25.6 调用/24.6 重规划），State Progress 0、Epistemic 1、无进展 29、同子目标重复 26。Gate 判断：B grounding 为主、D exploration/recovery 为辅，不实现 v2（`docs/experiments/planning-v1-failure-analysis.md:97-105`）。
- Muse 现状（verified，读 CSV）：`muse-memory-autonomous` 0/5（B30/HRP全关）vs `muse-planning-autonomous(e0302c3f)` 0/4完成+1中断 vs `muse-planning-autonomous2` 0/4完成+1中断——同模型同预算可比的“双输”基线。`1a95834e` 整批 5×provider_error/0步作废，不得计分母。
- 与获胜 Memory（B60/HRP全开 3/5）**不可比**（预算+信息双差异）。

## 3. 公平性核实（verified）

- Runner 透传等价：H/R/P 经 `_request→agent.request` 统一转发（`runner.py:427-433`），与 agent 名无关；`--autonomous` 下三者全关，对谁都一样。
- Agent 内部分叉（对照必须列明）：Planning 走 Planner+Executor 双调用 + 独立 prompt（`planning_v1`/`planning_executor_v1`）+ `plan_data` 代替 `memory_data`（`agents/planning.py:142-196`）；成本分 `planner_*/executor_*`（`runner.py:521-533`）。
- 无偷读（verified）：Planner/Monitor/Runner/LLM 均只收 `Observation`+公开结果（`planning.py:11,146,187`、`monitor.py:76-104`、`progress.py:26-39`、`public_facts.py:84`）；全仓 `WorldState` 仅 worlds/arena 持有。`phase_context=true` 时的世界声明文本是唯一先验通道，本次 autonomous 对照中关闭。

## 4. 对照设计（冻结 v1，新建版本名，本轮未跑）

- `M-C111`：Memory + H/R/P（主基线，B 待定 30 或 60）。
- `P-v1-context`：Planning v1 + 同等 H/R/P（Planner 沿用 v1 文本、Executor 唯一改动见 §5，新版本名如 `planning_v1_context`，provenance 加 `context_variant`；旧 v1 冻结归档）。
- 预算/地图/模型/公开信息相同；prompt/调用次数差异列为研究变量；禁 Planner 偷读 WorldState、唯一动作答案、评估器里程碑。
- 记录：replan 后首个 Action、子目标完成率、Planner call ratio、重复 look/失败动作、成功率/步数、tokens/成本/延迟；失败抽样标 `WRONG_ACTION/FORGOTTEN_FACT/INEFFECTIVE_REPLAN`，区分 Planner vs Executor。

## 5. 单变量 grounding 候选（仅 1 个 G1）

Executor 可见“同子目标已试无进展/已拒绝动作排除列表”，Planner/Monitor/预算全不动（复用 `PublicCandidateTracker._excluded` + `monitor failure_key`，经 `runtime_feedback` 递给 Executor，Planner 输入不变）。不给地图/位置/码值/下一动作。判据：`same_subgoal_repeat` 与 `repeated_known_fact` 下降且 `unique_room/state_progress` 上升而 Planner 调用不涨→grounding 成立。

## 6. 结论边界

- 0/5 是合法结果，不得为漂亮数据给唯一下一动作答案。
- 只在有明确收益/诊断依据时提议 Planning v2。本轮：对照设计完成，在线实验 **not run**（blocked：需 T3 冻结的最优合法机制 + 预算）。

## 7. 在线对照进展（2026-10-11 EXP-Pctx）

- EXP-Pctx-pilot（planning v1 原 prompt, H5 R1 P1, B60, 飞船 v1, seed 0）：**`step_limit` 失败**。
  trace `runs/episode_20261011T115325Z_planning_seed-0_27d7d0ff.json`：
  22/25/31/37/45 步 5 次 `CODE_READ`，corridor↔control_room 循环；
  50–55 步曾到逃生舱（2 次 `inspect`）但未用码即离开，56–60 步游荡结束。
  行为归类：Executor 落地失败（到终点而不用码）+ 重读循环，与 qwen 时代
  `INEFFECTIVE_REPLAN` 同构——补齐 H/R/P 未修复 grounding。
  注意：planning 系 prompt（`planning_v1`/`planning_executor_v1`）不含 E1 第 7 条，
  prompt 差异本身是待测变量之一，如实披露。
- EXP-Pctx 最终：**0/4 完成**（seeds 0–3 全部 `step_limit`；seed 4 两次基础设施杀死 +
  第三次首步 `provider_error`，记 censored，不进分母）。

| seed | outcome | 读码 | Planner 调用/子目标(生成/完成) | input/output tokens | trace |
|---|---|---|---|---|---|
| 0 | step_limit | 5 | 1/1/0 | 77k/76k | `runs/episode_20261011T115325Z_planning_seed-0_27d7d0ff.json` |
| 1 | step_limit | 2 | 2/2/0 | 79k/74k | `runs/episode_20261011T120540Z_planning_seed-1_7f9dff09.json` |
| 2 | step_limit | 5 | 1/1/0 | 77k/66k | `runs/episode_20261011T121908Z_planning_seed-2_b93c10a4.json` |
| 3 | step_limit | 1 | 6/6/5 | 89k/93k | `runs/episode_20261011T122857Z_planning_seed-3_35b9247d.json` |
| 4 | censored | — | — | — | `runs/episode_20261011T125156Z_planning_seed-4_568a7121.json` |

- 结论：同 H5/R1/P1/B60/同模型下，planning 0/4 vs memory+E1 5/5（同代码版本）vs memory C111 3/5。
  **显式规划在本任务上更差，而非更好**——证据充分（4 局一致失败 + 双倍 token 成本），
  故**不提议 Planning v2**，v1 冻结保持。失败定位：Executor 落地失败为主
  （seed 0 到终点而不用码；seeds 1–2 重读循环），seed 3 虽完成 5/6 子目标仍未逃生，
  证明 PlanMonitor 的子目标完成 ≠ 真实逃生进展（0/5 也是合法结果，如实交付）。
- 成本：5 次完成局 ≈ input 322k / output 308k（约 memory 的 2 倍，Planner/Executor 双调用所致）。
