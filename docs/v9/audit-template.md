# V9 逐图审计写作规范（Batch 1）

每张地图输出 `docs/v9/maps/MAP-XX-audit.md`。禁止套用其他地图的结论；每一节都必须有本图专属内容与可定位证据。

## 0. 元数据

- 地图、世界、难度、condition、`rule_hash`、`scenario_hash`、决策预算、V8 三局结果（成功数/终止码/决策数）。
- 数据来源：`runs/v9/evidence/MAP-XX.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-XX-final.md`、`worlds/v4/MAP-XX/*`、`src/agent_arena/worlds/scenario_v8/maps/mapXX.py`（六张适配图为 `scenario_v4/mapXX.py`）。

## 1. 能力构念

- 一句话定义“这张图想测什么能力”。
- 什么行为算成功；什么是明确反例。
- 该构念在简单/中等/困难三图中的递进位置（只写本图，跨世界比较留给 Batch 4）。

## 2. 机制与因果链

按“起始状态 → 必需观察 → 关键决策 → 立即后果 → 终局”画一条本图专属因果链，并标出：

- 哪些动作可以绕过核心机制（如果有）；
- 机制是否在三条真实轨迹中实际触发（引用决策序号）；
- 触发所需的最小动作数。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|

必须区分：Observation 字段、system prompt 的动作词表/规则、hidden `judge_state`、Oracle 路径。若某条硬规则只存在于私有 docstring 或代码，明确写“未公开”。

## 4. 可解性与可观察性

- Oracle 用例数与动作数（来自 `python -m agent_arena.v9.baseline_run` 或 `replay_all`）。
- **仅凭公开信息**是否存在可执行策略：说明策略思路与所需观察；不得把 Oracle 的隐藏真值当成公开信息。
- 若只有知道隐藏规则才能避免秒失败，标 `INTERFACE_BLOCKED` 或 `BUDGET_BLOCKED`。

## 5. 预算可行性

- Oracle 动作数 vs 决策预算；`legal_random` 的 20 seed 结果分布（成功、终止码、非法/被拒动作）。
- 公开启发式策略的动作数与终局。
- 判定：是“预算不够”，还是“模型没做对”。

## 6. 指标

逐条列出本图指标，并回答：

- 计算事件、分母、缺失/截尾规则；
- 是否存在**未通关仍有意义**的连续主指标；
- 三局是否出现 `not_applicable` / `censored`；若主指标在三局全 N/A，说明原因（真分母 0 还是投影口径）；
- 指标能否区分 Oracle / 随机 / 启发式 / 消融中的至少两种策略。

## 7. 三次轨迹归因

每局一小节：

- 引用至少 2 个**决策序号 + 动作 + 结果码 + 观察变化**（原文引用，不得改写）；
- 指出**首次偏离合理策略的可观测事件**；
- 给出失败链；
- 给出替代解释（例如：接口误导、预算不足、模型策略错误）；
- 若三局高度相同，明确写“重复证据有限，n=3 不能区分个体差异与固定陷阱”。

## 8. 失败分类

使用 A–I：A 环境规则缺陷；B 公开信息不足；C schema/接口误导；D 决策预算/horizon；E 策略规划错误；F 资源管理错误；G 记忆/推理错误；H 采样或运行异常；I 证据不足。允许一局多因，但必须标首因、次因、可信度（高/中/低）与证据位置。

## 9. 标签

从 `MEASUREMENT_VALID` / `INTERFACE_BLOCKED` / `BUDGET_BLOCKED` / `RULE_DEFECT` / `CONSTRUCT_BYPASS` / `METRIC_DEFECT` / `INCONCLUSIVE` 中选（可多选），每个标签附证据。

## 10. 最小可证伪修复（无证据不修改）

- 旧规则/旧公开信息；
- 证据与根因；
- 候选 A/B（优先“补公开信息”而不是改规则）；
- 预期变化与能力构念影响；
- 反例与回归风险；
- 若无需修改，写“无修复，保持只读”，并说明原因。

## 11. 基线与独立复算

- 引用 `runs/v9/baselines/MAP-XX.json` 的 Oracle/随机/启发式/消融结果；
- 主指标至少一个独立复算证据（手工计算或与 extractor 不同实现的代码），写在 `docs/v9/metric-independent-check.md` 或本图小节；
- 若主指标无法区分策略，写 `LOW_DISCRIMINATION`。

## 12. V9 状态

选一个：`VALIDATED` / `NEEDS_REDESIGN` / `NEEDS_MORE_EVIDENCE` / `BLOCKED`，并给出优先级（P0/P1/P2）与一句话理由。

## 硬性要求

- 全文中文；代码、字段名、结果码保留原文。
- 不得复制 `docs/v8` 的结论；必须从 Trace 与源码重新推导。
- 不得声称人工审核；`human_approved` 只能由用户确认。
- 不得为了让成功率好看而建议加资源/加时间；不得把模型正确失败改成成功。
