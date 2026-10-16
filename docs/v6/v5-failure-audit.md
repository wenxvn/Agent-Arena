# V5 六图失败分类与数据质量审计（V6 Batch 0）

- 审计日期：2026-10-16
- 审计基线 commit：`12bf6558e77813a025e21679ef344cf4312b90fd`（V5 最新文档提交）
- 证据：本机 `runs/v5/experiments/pilot_20261016T013445Z_5de86f869aaa4990b236ca154c7020bf/`（39 局全部存在 `agent_trace.jsonl` 与 `judge_metrics.json`）。**本轮审计读到了原始 trace**，不是二级转述。可复现命令：`python scripts/audit_v5_failures.py --summary`。

> 记录真实性声明：`runs/` 与 `results/` 按项目约定不入 Git。若换机后原始 trace 缺失，本审计脚本会输出 `trace_unavailable: true`，届时只能退回已提交报告作二级审计，不得伪称复核过原始 trace。

## 1. 逐图实测（第二次注册 pilot）

| 条件 | 局数 | 成功 | 截尾桶 | 主要失败码 |
|---|---|---|---|---|
| MAP-08 / hypothesis_table | 3 | 3 | — | INVALID_ACTION(3) |
| MAP-08 / no_hypothesis_table | 3 | 1 | rule_outcome_failure(2) | RESOURCE_EXHAUSTION(2), INVALID_ACTION(1) |
| MAP-16 / react | 3 | 0 | rule_outcome_failure(3) | SAFETY_VIOLATION(3), INVALID_ACTION(2) |
| MAP-16 / constraint_table | 3 | 1 | rule_outcome_failure(2) | SAFETY_VIOLATION(2), INVALID_ACTION(3) |
| MAP-18 / alert_off | 3 | 0 | rule_outcome_failure(3) | SAFETY_VIOLATION(3), INVALID_ACTION(3) |
| MAP-18 / alert_on | 3 | 0 | rule_outcome_failure(3) | SAFETY_VIOLATION(3), INVALID_ACTION(3) |
| MAP-22 / history5 | 3 | 0 | **censored_step_limit(3)** | TIMEOUT(3), INVALID_ACTION(1), **接口异常 173 次** |
| MAP-22 / history5_graph_memory | 3 | 0 | censored_step_limit(3) | TIMEOUT(3) |
| MAP-26 / free_diagnosis | 3 | 2 | rule_outcome_failure(1) | RESOURCE_EXHAUSTION(1), INVALID_ACTION(2) |
| MAP-26 / recovery_full | 1 | 1 | — | — |
| MAP-26 / recovery_structured | 1 | 1 | — | INVALID_ACTION(1) |
| MAP-26 / recovery_hidden | 1 | 0 | rule_outcome_failure(1) | RESOURCE_EXHAUSTION, REPEATED_ACTION, INVALID_ACTION |
| MAP-30 / history_full | 3 | 3 | — | — |
| MAP-30 / history5_casebook | 3 | 3 | — | — |
| MAP-30 / history5 | 3 | 0 | rule_outcome_failure(3) | TIMEOUT(3), INVALID_ACTION(3) |

合计 15/39 成功，与 `docs/v5/capability-validity.md` 一致。

## 2. 逐图归因（失败是模型问题 / 接口问题 / 不可解 / 截尾）

### MAP-22：**接口契约问题**（首要，且被 V5 误判为能力下限）

直接读 trace 得到决定性证据：

- `history5`（非记忆条件）3 局共返回 `ACTION_NOT_AVAILABLE` **173 次**。逐条查看 action，模型在该条件下反复提交
  `{"tool":"write_memory","facts":[{"fact_type":"node_page","sign_id":"RUIN_TRIPLE_ARCH","exit_bearings":["N","W"]}]}`。
  MAP-22 环境在 `memory_enabled=False` 时对 `write_memory` 返回 `ACTION_NOT_AVAILABLE`；但 system prompt 的 action contract 在**所有**条件都宣传了 `write_memory`。模型据此反复尝试写记忆，耗尽动作预算。
- `history5_graph_memory` 3 局中，模型主要提交 `{"tool":"return_to_camp"}`（seed0 达 48/51 次）。该工具只把 `active_goal` 设为营地，**不执行移动**；模型由此停在 L/tick12，`movement_steps` 不再增长。

结论：MAP-22 的 0/6 主要是**动作接口可读性问题**（契约宣传了不可用动作、`return_to_camp` 语义易误解），不是空间记忆能力下限。V5 `capability-validity.md` 的“不能据此判断记忆增益”成立，但应升级为“已定位接口缺陷，先修接口再谈能力”。

### MAP-16：规则结果失败为主，能区分信息条件

- `react` 0/3：terminal 全为 `NODE_CAPACITY_CONFLICT`(2) 与 `HEAD_ON_SWAP`(1)。模型在同步预约阶段把两车送进同一节点或对向同一区段。
- `constraint_table` 1/3：seed2 成功（makespan 8，BFS 最优 6，gap 2）；seed0/1 仍是 `NODE_CAPACITY_CONFLICT`。
- 归因：这是真实的同步约束规划失败，非接口问题；但 3 局共享同一拓扑，约束表 vs ReAct 的差异不显著（每条件 3 个重复执行，不是独立实例）。

### MAP-18：规则结果失败，且故障/预警对照未分离

- 两个条件 0/6。失败码以 `INVALID_LINK`（非法相邻移动尝试）与 `HEAD_ON_COLLISION`、`STATION_CAPACITY_EXCEEDED` 为主。
- 服务率 0–0.33，均未达 13/18 阈值。告警开/关的失败模式相同，**无法分离预警效果**。
- 归因：既有接口/规则理解问题（大量 `INVALID_LINK`），也有策略失败。任务在 12 tick、18 需求的约束下是否可达需要独立求解器确认（V5B 用 `worlds/v4/MAP-18/planning/schedule_audit.py` 证明存在 18/18 的手写方案）。

### MAP-08：条件差异方向成立，但每故障点仅一个实例

- 无表 1/3、有表 3/3。无表失败（seed4/seed8）峰值水位 7.5 触发 `CORE_WATER_LIMIT_EXCEEDED`，与“两次测试后仍未区分”一致。
- 归因：真实的信息增益差异，但 B/D/F 各仅一个 seed，不能当作独立实例；有对固定签名过拟合的风险。

### MAP-26：方向成立但恢复轨道单例

- free_diagnosis 2/3，recovery_full 1/1、structured 1/1、hidden 0/1。
- 归因：hidden 是信息剥夺，不是等信息基线；每个恢复条件仅 1 局，是描述性证据。

### MAP-30：**固定前缀 + 一步提交**，长时程规划未被测量

- `history_full` 与 `history5_casebook` 均 3/3，且**决赛决策数 = 1**（前缀停在 J，模型一步 `formal_accuse` 成功）。`history5` 0/3，40 tick 到 `DEADLINE_REACHED`。
- 归因：成功条件确实是长间隔证据召回，但任务被固定前缀压缩成“纯召回 + 一步提交”，没有测量多步调查规划。这与提纲要求“不能只从固定前缀一步提交就宣称长期规划”一致。

## 3. 数据质量结论

1. **截尾不得当作能力**：MAP-22 的 6 局全部是 `step_limit_reached` 截尾，且已在 §2 定位到接口根因。
2. **接口错误占比**：MAP-22 `history5` 的接口异常占决策 173/(63×3)=91.5%；MAP-18 的 `INVALID_LINK` 也是接口/规则可读性问题。凡此类 episode 都不能支撑能力结论。
3. **固定场景重复 ≠ 独立实例**：MAP-16/18/22/30 的 seed 0/1/2 是同一场景重复执行；MAP-08 的 0/4/8 是三个故障点但每点一个实例；MAP-26 有 3 个真实故障 + 3 个单例恢复分支。
4. **条件差异只在部分图可见**：MAP-08（表）、MAP-26（结构化 vs 隐藏）、MAP-30（完整历史/案卷 vs 短历史）方向可解释；MAP-16/18/22 在当前条件下敏感性不足或受接口支配。

## 4. 需要用户提供的原始材料（若换机缺失）

- `runs/v5/experiments/pilot_20261016T013445Z_5de86f869aaa4990b236ca154c7020bf/` 全量 episode 目录。
- `runs/v5/ledgers/pilot_20261016T013445Z_5de86f869aaa4990b236ca154c7020bf.jsonl` 与 `runs/v5/pilot_registry.json`。

以上材料只读，本任务不修改、不重放任何历史账本。
