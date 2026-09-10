# PlanningAgent v1 Failure Analysis & Evaluation v2

更新时间：2026-09-10

## 结论摘要

Evaluation v2 已在不改变 PlanningAgent v1 Planner→Executor 核心、prompt、world、模型和动作 contract 的前提下完成。固定 `qwen2.5:7b`、seed 0–4、每局 30 步、`--autonomous` 的独立重跑结果仍为 **0/5 成功**。

主要证据不是单一的 Planner 文本问题，而是：Executor 在当前子目标下持续选择无效的 `look`，探索没有产生房间或物品变化，失败反馈也没有改变行为。主决策 Gate 为 **B：Action Grounding Failure**，并伴随 **D：Exploration/Recovery Failure**。Evaluation v2 能识别首次公开事实，但这不足以解释全部失败；因此本阶段不实现 PlanningAgent v2，先进行人工抽样和单变量验证。

## 实验身份与数据

| 项目 | 值 |
|---|---|
| Agent | `planning`，PlanningAgent v1 |
| 模型 | Ollama `qwen2.5:7b` |
| World | `spaceship-escape` / `spaceship-escape-v2-zh` |
| seeds | 0、1、2、3、4 |
| step limit | 30 |
| runtime feedback | 关闭 |
| public action guard / candidate / phase context | 关闭 |
| 结果目录 | `results/planning-v1-eval-v2/` |

分析使用两组数据：既有的 5 个 Planning v1 trace 用于离线复盘；Evaluation v2 完成后，在独立目录重新运行同一实验矩阵。新 trace 包含 `trace_schema_version=2` 和逐步 `ProgressEvent`，没有密钥、原始模型响应或完整思维链。

## Evaluation v2 重跑结果

| 指标 | 平均值 | 解释 |
|---|---:|---|
| 成功率 | 0/5（0%） | 5 局均为 `step_limit` |
| 执行动作数 | 30.0 | 每局达到上限 |
| 重复 Action 比例 | 93.3% | 主要为重复 `look` |
| Planner 调用 / Replan | 25.6 / 24.6 | Planner call ratio 为 85.3% |
| State Progress | 0.0 | 没有房间、可见对象、出口或背包变化 |
| Epistemic Progress | 1.0 | 每局首次得到 `control_terminal:no_power` |
| Total Progress | 1.0 | 仅有上述一次进展 |
| No-progress actions | 29.0 | 之后的重复观察均无新增状态或事实 |
| 已知事实重复动作 | 2.0 | 重复获得相同 `NO_POWER` 事实 |
| 唯一 PublicFact | 1.0 | 每局只有 `control_terminal/result/no_power` |
| 唯一 Subgoal / Switch | 3.0 / 2.0 | 子目标有变化，但动作模式没有有效变化 |
| 同 Subgoal 重复 Action | 26.0 | Grounding proxy 的强信号 |
| 同 Subgoal rejected Action | 3.0 | 每局重复拒绝读取无电终端 |
| 唯一房间 / 对象交互 | 1.0 / 1.0 | 没有实际探索到新房间 |

规则失败分析每局识别 3 次 `INVALID_ACTION`（Environment rejected）和 2 次 `REPEATED_FAILURE`；没有识别出 `REPEATED_INSPECTION` 或 `REPEATED_NAVIGATION`，因为本轮主要循环是 `look`，不是 `inspect` 或房间往返。这个边界由 `no_progress_action_count` 和 grounding proxy 补充，而不是把所有重复行为强行归入同一种 FailureType。

作为对照，原始 5 个 Planning v1 trace 的离线回放得到：0/5 成功、平均 28 次 Planner 调用、Planner call ratio 93.3%、State Progress 0、Epistemic Progress 1、无进展动作 29、唯一 PublicFact 1、同子目标重复 Action 26、唯一房间 1。原始 trace 的自动分布为 8 次 `INVALID_ACTION` 和 3 次 `REPEATED_FAILURE`。Evaluation v2 重跑的精确调用和 rejected 数量有所波动，但失败方向和进展结构一致；这也说明不能把结论建立在某一局的单个调用计数上。

## RQ1：Planner 生成的 Subgoal 是否具有可执行性？

**结论：操作层面不足。** 5 局都出现约 3 个不同子目标，例如 `inspect control_terminal`、`find power_source`、`explore corridor`。这些文本在语义上并非完全空泛，但没有稳定约束 Executor 选择下一步有效 Action：模型在 `explore corridor` 下仍连续调用 `look`，没有调用 `move`。

`unique_subgoal_count=3` 只能说明 Planner 改过子目标，不能证明子目标已被执行。`state_progress_count=0`、`unique_room_count=1` 和 `same_subgoal_repeated_action_count=26` 共同表明，从子目标到可执行动作的桥接没有形成。

## RQ2：Planner 是否发生过度 Replan？

**结论：是。** 平均 25.6 次 Planner 调用、24.6 次 replan，占 30 个执行动作的 85.3%。重规划大多由无进展或重复失败触发，但后续动作仍保持 `look`/`read_terminal` 模式，说明重规划没有带来有效策略变化。

这不是“Planner 完全没有被调用”的问题，而是 Planner 调用频繁、计划切换有限、Executor 行为高度不变的组合信号。下一步应分别测量触发原因和 replan 后首个 Action，避免只用调用次数推断 Planner 质量。

## RQ3：当前 no-progress 判断是否存在误判？

**结论：Evaluation v1 的确会漏掉首次事实进展；Evaluation v2 已能区分，但当前失败主体仍是真实无进展。**

每局第一次 `read_terminal(control_terminal)` 返回 `NO_POWER` 时，持久状态没有变化，但 Evaluation v2 记录了：

```text
state_progress = false
epistemic_progress = true
new_fact = control_terminal / result / no_power
```

之后重复获得相同结果时，`epistemic_progress=false`，并计入 no-progress。也就是说，29 次 no-progress 中，首次事实不会被错误计入；但若回放旧的 persistent-only 逻辑，该首次事实无法被表达为进展。新监测器修复了这类评估盲点，但它没有改变模型后续持续 `look` 的行为，因此不能把 0/5 归因于 Monitor 误判。

## RQ4：Executor 是否存在明显 Plan → Action Grounding Failure？

**结论：有强代理证据，需要人工确认语义标签。** Executor 已接收到 `find power_source` 和 `explore corridor` 等当前子目标，却在同一子目标内反复选择 `look`，没有把“探索走廊”落实为 `move`。同时每局有 3 次被 Environment 拒绝的 `read_terminal(control_terminal)`。

Evaluation v2 不使用 LLM Judge，因此没有自动声称这些步骤一定是 `WRONG_ACTION` 或 `WRONG_TARGET`。人工抽样应重点检查每局的第 7 步之后，以及每次 replan 后的第一个 Action，区分：子目标定义不足、Executor 忽略子目标、模型忘记 `NO_POWER`，还是 Action 候选本身缺少约束。

本轮已对 5 局各自前 10 个执行动作及重规划边界完成抽样。人工标签保持为中等置信度：`find power_source`/`explore corridor` 之后仍调用 `look`，标记为候选 `WRONG_ACTION`；在已得到 `NO_POWER` 后再次读取控制终端，标记为候选 `FORGOTTEN_FACT` 或 `INEFFECTIVE_REPLAN`。这些标签用于研究判断，不写入自动 Failure Distribution，也没有交给 LLM 评审。

| 抽样范围 | 公开证据 | 人工候选标签 | 置信度 |
|---|---|---|---|
| 5 局，首次 `NO_POWER` 后的重复终端读取 | 相同目标和失败原因再次出现，背包、房间和出口均未变化 | `FORGOTTEN_FACT` | medium |
| 5 局，第一次 replan 后的第一个 Action | 当前子目标转为 `find power_source`，Action 仍为 `look` | `INEFFECTIVE_REPLAN` / `WRONG_ACTION` | medium |
| 5 局，进入 `explore corridor` 后的连续 Action | `corridor` 已在公开出口中，但连续 `look` 未产生移动 | `WRONG_ACTION` | medium |

## RQ5：0% Subgoal Completion 来自真实失败还是 Criteria 检测失败？

**结论：现有证据更支持真实失败，但尚未完成语义级证明。** 旧的 v1 字符串 criteria 仍可通过兼容 evaluator 读取；Evaluation v2 重跑中每局都没有 State Progress、没有新房间、没有物品变化，也没有完成任何公开里程碑。因此没有证据表明“实际上完成了子目标，只是 evaluator 全部漏判”。

同时，本次真实 Planner 仍输出 v1 字符串 criteria，而不是新的 structured criteria，所以 structured SuccessCriterion 的真实模型覆盖仍需单独的 Fake/fixture 和后续受控实验验证。最终结论必须结合人工抽样的 `subgoal_completed`、criteria 内容和实际公开结果，不能只凭 0% 一个字段下结论。

## RQ6：PlanningAgent v2 最应该修改哪一层？

**当前 Gate：B 为主，D 为辅；暂不实现 v2。**

优先问题是 `Subgoal → Action` grounding：让 Executor 在公开 Observation 下把“寻找电源”“探索走廊”落实为可验证、可执行的下一步。其次是 exploration/recovery：面对 `NO_POWER` 和连续无进展时，应产生改变位置或交互目标的动作，而不是仅增加 Planner 调用。

当前证据不足以证明应该先重写 Planner 表示（Gate A），也不支持把问题主要归为 Evaluation failure（Gate C）。在实现 PlanningAgent v2 前，先完成以下门禁工作：

1. 扩展已完成的人工抽样到每局完整的 replan 后首个 Action，覆盖 `VAGUE_SUBGOAL`、`WRONG_SUBGOAL`、`WRONG_ACTION`、`FORGOTTEN_FACT` 和 `INEFFECTIVE_REPLAN`。
2. 保持模型、world、prompt 和 PlanningAgent v1 不变，分别验证 grounding 与 exploration/recovery 的单变量改动。
3. 只有当人工标签与受控消融确认主要瓶颈后，才创建 PlanningAgent v2 的新 spec 和实现任务。

## 产物与可复现命令

- [failure_analysis.json](../../results/planning-v1-eval-v2/failure_analysis.json)
- [failure_analysis.csv](../../results/planning-v1-eval-v2/failure_analysis.csv)
- [benchmark JSON](../../results/planning-v1-eval-v2/benchmark_20260910T015109Z_planning_5-seeds_5-episodes_1d45909a.json)

```bash
uv run agent-arena analyze-traces \
  results/planning-v1-eval-v2 \
  --output-dir results/planning-v1-eval-v2
```

报告中的自动分类是规则结果，不是 LLM 评审；没有自动生成语义型 FailureAnnotation。PlanningAgent v1 保持冻结，ReflectionAgent、Streamlit 和第二个 world 均不在本阶段范围内。
