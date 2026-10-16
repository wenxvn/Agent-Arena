# 0019. V6 能力测量效度修复与泛化验证

**Date**: 2026-10-16
**Status**: In Progress

## Summary

V5 六图 pilot 暴露了三类问题：MAP-22 的失败由动作接口可读性支配而非能力；MAP-16/18/22/30 用固定场景重复 seed 充当样本，无法支撑泛化；部分条件（MAP-30）被固定前缀压缩成“一步提交”。V6 不以提高通过率为目标，而以**可靠识别能力差异**为目标：为六图建立可确定复现的独立实例、分层难度（L1/L2/L3）、公平配对条件、独立求解器与无泄漏验证，并单独给出**可选**真实 API 复测方案（默认不执行）。本轮只做离线工作，不调用任何收费 API。

## Context

- 基线：`main` @ `12bf6558e77813a025e21679ef344cf4312b90fd`。
- 依据：`研究提纲/V6 能力测量修复与泛化验证.md`、`docs/v5/*`、`docs/specs/0018-v5-six-map-measurement.md`。
- V5 失败审计（真实 trace）：见 `docs/v6/v5-failure-audit.md`。

## Requirements

**Acceptance criteria**：

- **AC-1 隔离**：V6 实例、solver、leakage 检查与既有 V3/Legacy/V4/V5 运行时、账本、trace 隔离；V4 默认行为不变，`validate_v4_runtime.py` 全绿。
- **AC-2 实例单位**：`instance_id` 表示独立环境实例，`run_id` 表示一次模型执行，`seed` 仅控制随机性；固定场景重复 seed 不得当作独立样本。
- **AC-3 可解与最优**：每个 V6 实例都有可在真实环境逐步回放成功的合法 Oracle，并有独立求解器给出最优或下界。Oracle 回放 100% 通过；相同动作序列的状态 hash 一致。
- **AC-4 分层**：MAP-16/18/22 每图 L1/L2/L3 三层各有独立 fixture 与求解；L1/L2/L3 必须说明降低了什么能力负担、保留了什么核心机制，不得只加步数上限或降阈值。
- **AC-5 非换皮**：MAP-08/26/30 每图至少 3 个**结构不同**（改变拓扑/故障/案情/覆盖关系，而非仅换人名或 seed）的独立实例，且不改变 V4 原始地图文件。
- **AC-6 公平配对**：同一 instance 的对照条件共享初态、公开信息、预算与动作契约，只改变预登记目标机制；结构化表/案卷不得写入隐藏真值。
- **AC-7 无泄漏**：所有公开提示与 Observation 由 public state 构建；反例测试检查 seed、内部答案、Oracle 路线、未解锁证据、未来事件不出现于 prompt/trace。
- **AC-8 边界**：每个实例至少三种可复现的非法/边界路径（如非法预约、超容量、错指控），且终止后状态不变。
- **AC-9 无付费**：实例生成与离线验证不调用任何收费 API；V2/V5 账本与 registry 字节不变。
- **AC-10 报告**：如实区分纸面可解、离线回放、独立求解与真实模型表现；失败必须如实标注，不得“改验收条件直到通过”；人工审阅字段保持 `pending_human_review`，由执行 Agent 之外的审阅者填写。

## Feature design

### V6 instance model and runtime boundary

新增 `src/agent_arena/v6/`：`scenes.py`（实例数据）、`catalog.py`（实例注册、manifest、hash）、`solvers.py`（独立求解器）、`oracles.py`（求解器驱动的 Oracle 生成与回放校验）、`prompts.py`（V6 条件契约）、`leakage.py`（泄漏扫描）。V6 通过 `scenario_v4` 的参数化构造器创建环境，复用同一规则引擎，不新增 Action contract 版本。

每个实例输出机器可读 manifest，字段包括：`instance_id / map_id / rule_version / level / capability / scenario_hash / public_initial_state_hash / private_truth_hash / oracle_trace / solver_result / paired_conditions / review_status`。占位符在交付中必须替换为真实生成值。

### Difficulty levels

- MAP-16：L1 单列车/单次预约与容量合法性；L2 双列车避让但减少同步冲突；L3 完整 V4 同步调度。
- MAP-18：L1 静态无故障调度；L2 已知故障后的局部改线；L3 在线不确定故障 + 有限预警。
- MAP-22：L1 已探索两三节点的返程；L2 部分探索图、需回溯与识别重复点；L3 12 节点原任务。
- MAP-08/26/30：以独立实例的复杂度分层（诊断矩阵规模 / 故障与备件预算 / 证据链长度与解锁顺序）。

### Condition fairness

- MAP-16：基础公开规则 vs 同信息量的结构化约束表（表不含下一步最优动作）。
- MAP-18：alert_on vs alert_off，冻结同一故障场景，信息隔离（预警不揭示闭塞段与持续时长）。
- MAP-22：history5 vs history5 + 合法外部图记忆；共同前缀、共同公开信息、共同动作预算。
- MAP-08：hypothesis_table vs no_table，公开观察完全一致。
- MAP-26：等信息的 structured vs full（信息剥夺 hidden 单列）。
- MAP-30：history_full / history5 / history5+casebook，A/C 访问相同已公开事实。

### Metrics and analysis rules

逐图主指标沿用各图能力构念（合法预约率、容量/交换冲突率、死锁率、makespan/最优差；服务率、累计延误、故障后首次合法重规划 tick；返程成功率、有效移动率、重复边比例、与最短返程差；诊断准确率、测试次数、信息增益、后验候选集大小；失败后首个有效策略调整、剩余备件、修复成功率；关键证据召回、事实引用准确率、错误指控率）。截尾不得默认为推理失败；实例不足时不做显著性断言。

## Options considered

### Option 1：复制六图规则引擎到 V6
- **Pros**：完全不触碰 V4 文件。
- **Cons**：两套规则引擎会分叉，Oracle/求解器无法保证与真实环境一致。**否决**。

### Option 2：在单一引擎上开放实例参数（选用）
- **Pros**：单一事实来源；默认行为不变即可保持 V4/V5 回归。
- **Cons**：需要最小可行重构（见 DCR-002）。**选用**。

## Decision

**Chosen option**：Option 2。为 V4 引擎增加可选实例参数，默认值复现原场景；V6 用数据化 fixture 注入结构不同的实例，并配套独立求解器、Oracle 回放与泄漏检查。

## Rationale

单引擎 + 数据化实例既能构造真正结构不同的样本，又能保证求解器结论适用于真实运行环境；默认行为不变使 V4/V5 回归可控。

## Build plan

1. 建立 V6 fixture/solver/leakage 骨架与 manifest，满足 **AC-1**、**AC-2**、**AC-9**。
2. MAP-22（先修接口）、MAP-16、MAP-18 三层实例与求解，满足 **AC-3**、**AC-4**、**AC-8**。
3. MAP-08、MAP-26、MAP-30 非换皮独立实例与等信息配对，满足 **AC-5**、**AC-6**。
4. 泄漏反例测试与全量离线验收，满足 **AC-7**、**AC-10**。
5. 报告、独立复审清单与可选 API 实验提案；停止并等待用户批准。

## Migration plan

**Strategy**：side by side。V6 只新增 `src/agent_arena/v6/`、`scripts/validate_v6_*.py`、`docs/v6/*`，并对 V4 引擎做向后兼容的参数化。

**Rollback**：回退 V6 新增文件与 V4 参数默认值即可；V4/V5 运行数据不迁移。

**Risks**：V4 参数化若改变默认行为会破坏既有回归——用 `validate_v4_runtime.py` 与全量 pytest 在每步拦截。

## Consequences

**Positive**：六图具备独立实例、分层难度、独立求解与泄漏检查；失败可归因。
**Negative**：V6 fixture 需人工审阅；离线层不代表模型表现。
**Neutral**：生成数据写入忽略路径，默认不入 Git。

## Follow-up

- [ ] 人工审阅 V6 实例清单（`review_status` 待填）。
- [ ] 用户批准预算后，才按 `docs/v6/api-experiment-proposal.md` 执行可选 API 复测。

## References

- `研究提纲/V6 能力测量修复与泛化验证.md`
- `docs/v6/v5-failure-audit.md`、`docs/v6/design-change-requests.md`、`docs/v6/measurement-matrix.md`
- `docs/specs/0018-v5-six-map-measurement.md`
