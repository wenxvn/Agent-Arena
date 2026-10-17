# DCR-06：MAP-12 公开 `transfer` 边 id、研究周期与维修零件

- 状态：`accepted`（公开信息 + V9 指标叠加）
- 地图：MAP-12
- 关联审计：`docs/v9/maps/MAP-12-audit.md`
- 影响面：prompt（`prompt_hash`）+ V9 指标叠加（`overlay_schema_hash`）；不改规则
- 证据：V8 三局共 62 次 `transfer` 全部 `INVALID_EDGE`（审计 §7），零件始终停在 S=8，维修链不可执行；三局均在 60 决策后 `RESEARCH_TARGET_MISSED`。

## 1. 原始公开信息

Observation 没有 `visible_edges`，词表只说 `transfer(commodity, from_node, to_node, edge_id, quantity)`，没有列出任何 edge id。规则模块 `map12.py:37-43` 的 `EDGES` 是唯一来源。

## 2. 根因

**B（硬阻断）**：合法解必须把 2 件 parts 从 S 运到 E，而 edge id 不在公开面；这是一个“可解但不可发现”的接口缺口。
**METRIC_DEFECT**：五条登记指标都不含 `research_points`，而胜负判据正是 `research_points>=12`；失败局与成功局在主指标上可能同分。

## 3. 修复

### 3.1 公开规则（`V9_PUBLIC_ADDENDA["MAP-12"]`）

> transfer 的可用无向边为 H_E、E_G、G_S、S_L、H_S、G_L；from_node 与 to_node 必须是该边两端。维修控制器需要 2 件 parts 送到 E。连续 3 天执行 research 才获得 3 分；磨损日未维修会记一次计划违约。

### 3.2 V9 指标叠加

`src/agent_arena/v9/metric_overlay.py`：

- `map12.research_points_completion = research_points / 12`（primary，higher_is_better）。

该值直接从 `judge_state["research_points"]` 读取，不新增规则。

## 4. 预期与风险

- 预期：`transfer` 从“不可发现”变为“可规划”；维修链与 30 天排程成为真正负担。
- 风险：边 id 公开后，模型仍需排 24 个必要劳动槽（12 研究 + 4 维修 + 8 转运），预算 60；不构成“加时间”。
- `rule_hash` 不变；`prompt_hash` 与 `overlay_schema_hash` 变化。

## 5. 验证

- V8 Oracle 2/2（`baseline_run` 已按 `ORACLE_CASES` 正确回放，不再走通用 jsonl 解析）。
- 公开启发式 60 决策成功，`research_points=12`、`plan_breach_days=0`。
- `tests/test_v9_overlay.py::test_map12_overlay_exposes_research_points`。
- MiMo 同期对照：`v8_compat` 完成 2/2（均 `RESEARCH_TARGET_MISSED`）；`v9_fixed` 两次尝试都在约 20 决策遇到 provider `InternalServerError` 并按 unknown spend 封账，未完成。因此 MAP-12 的修复只有离线证据，V9 不宣称在线效果。

## 6. 回滚

删除 addendum 与 MAP-12 overlay 条目；V8 指标不变。
