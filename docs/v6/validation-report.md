# V6 离线验收与独立求解报告（Batch 7）

- 日期：2026-10-16
- 范围：离线。**未调用任何收费 API**；V2/V5 账本与 registry 字节未改动。
- 结论：全部离线门禁通过。

## 1. 实际命令与结果

| 命令 | 结果 |
|---|---|
| `python -m pytest -q` | **552 passed**（含 V6 新增 34 项） |
| `python -m ruff check src scripts tests` | All checks passed |
| `python -m mypy src` | Success: no issues found in 85 source files |
| `python scripts/validate_v4_runtime.py` | V4 oracle replay passed：08:4、16:2、18:3、22:1、26:2、30:3 |
| `python scripts/validate_v5_solvers.py` | V5 independent solver checks passed（六图指标不变） |
| `python scripts/validate_v6_instances.py` | **V6 instance validation passed: 40 instance/seed oracle replays verified** |
| `python scripts/validate_v6_leakage.py` | V6 leakage checks passed |
| `python scripts/audit_v5_failures.py --summary` | 输出 39 局逐条件分类（见 `v5-failure-audit.md`） |

> 本机 `uv` 未在 PATH 上，使用项目虚拟环境 `.venv/Scripts/python.exe` 等效执行；命令语义与 `uv run` 一致。

## 2. 验收清单对照（spec 0019）

| 条目 | 状态 | 证据 |
|---|---|---|
| AC-1 隔离；V4 默认行为不变 | 通过 | `validate_v4_runtime.py` 六图全绿；全量 pytest；DCR-002 |
| AC-2 实例/运行/seed 单位 | 通过 | manifest 字段与 `measurement-matrix.md`；MAP-08 seed 为不同候选而非重复 |
| AC-3 可解与最优 | 通过 | 40/40 Oracle 回放成功；MAP-16/22 由 BFS 证明最优并核对 makespan/movement |
| AC-4 分层 | 通过 | MAP-16/18/22 各含 L1/L2/L3，见矩阵 |
| AC-5 非换皮独立实例 | 通过 | MAP-08 四实例、MAP-26 四故障+一恢复、MAP-30 三案情 |
| AC-6 公平配对 | 通过 | `test_paired_conditions_share_rule_outcomes`；MAP-22 仅记忆日志可差异 |
| AC-7 无泄漏 | 通过 | `validate_v6_leakage.py`：无私有真值/Oracle 路线/未解锁证据泄漏 |
| AC-8 边界与终止不变 | 通过 | 每实例一条非法动作被拒且 judge state 不变；终止后再次 step 状态不变 |
| AC-9 无付费 | 通过 | 全流程离线；不触碰账本 |
| AC-10 报告诚实 | 通过 | 人工审阅字段保持 `pending_human_review` |

## 3. 关键验证细节

- **确定性与重放一致**：每个实例连续两次回放得到完全相同的公开 Observation 序列与 `state_hash`。
- **Oracle 100% 可回放**：实例 Oracle 由求解器生成，逐动作经真实环境 `step` 执行并达到成功终止。
- **独立求解**：MAP-16 用组合状态 BFS 得最小 makespan（L3 = 6，与既有 V5 solver 一致）；MAP-22 用 (节点, 是否已访目标) BFS 得最短往返走法；MAP-08/26/30 用构造路线；MAP-26 恢复轨道用“注册前缀 + 受限搜索”证明存在修复尾。
- **MAP-18 求解性质**：贪心调度可交付 18/18（含长闭塞窗口），但**不是最优性证明**。这暴露一个测量设计事实：MAP-18 的闭塞只有在智能体延迟 R2/R3 时才成为约束；若前移发车即可规避。因此 L3 的“在线重规划”载荷依赖于智能体的发车时点选择，而不是强制的不确定故障。此项列为待人工审阅的设计问题（见 DCR 建议）。

## 4. 已知限制（如实记录）

1. **人工审阅未完成**：所有实例 `pending_human_review`；执行 Agent 不宣称人工审阅已完成。
2. **MAP-18 最优性缺失**：只有构造性可行解，没有 BFS 级最优证明。
3. **MAP-18 故障载荷**：见 §3；当前不改规则，留给审阅者决定是否登记新的窗口强制规则。
4. **V6 未接真实模型**：本节全部是运行时与求解证据，不代表任何模型能力；失败归因与能力结论需真实实验后才能给出。
5. **MAP-08 实例 12 个 seed 源自 V4 真值映射**：它们是 V4 已定义的不同漏点，不构成随机总体样本。

## 5. 与 V5 回归的关系

- V4 引擎参数化后默认路径不变：`validate_v4_runtime.py` 与 `validate_v5_solvers.py` 输出与基线一致。
- V5 报告、账本、registry 未改动；`docs/v5/*` 只读。
- V6 新增不改变 V3/Legacy/V4/V5 的 Action、Observation、Trace 与 CLI 行为。
