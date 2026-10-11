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
