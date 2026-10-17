# DCR-08：MAP-25 公开舱段邻接/耗氧，并修正检查覆盖口径

- 状态：`accepted`（公开信息 + V9 指标叠加）
- 地图：MAP-25
- 关联审计：`docs/v9/maps/MAP-25-audit.md`
- 影响面：prompt（`prompt_hash`）+ 指标叠加（`overlay_schema_hash`）；不改规则
- 证据：V8 R0/R2 各 30 决策耗尽；R2 `required_check_coverage=1.0` 但 `diagnosed=False`，因为一次被拒的 `diagnose(device_id="array")` 被 `required_done` 记为完成；公开启发式 16 决策成功。

## 1. 原始公开信息

Observation 没有邻接表，也没有每步耗氧；词表列出工具与 `array_fuse_B`，但没有 H–T–A–S 的线性拓扑。模型只能靠 `NOT_ADJACENT` 反馈试错。

## 2. 根因

- **B/C**：物理拓扑与耗氧是“世界事实”，却只能靠失败反馈反推；30 步预算中至少 7 步用于试错。
- **METRIC_DEFECT**：覆盖率把被拒诊断算作完成，R2 的 7/7 与 `diagnosed=False` 矛盾。

## 3. 修复

### 3.1 公开规则

`V9_PUBLIC_ADDENDA["MAP-25"]`：

> 舱段邻接为 H–T–A–S（线性）；A 是气闸。舱外每移动一步消耗 1 单位氧气，维修额外消耗 1；氧气耗尽会立即失败。

### 3.2 指标叠加

`map25.required_check_coverage_corrected = (count(required_done - {diagnosed}) + int(diagnosed)) / 7`。

## 4. 预期与风险

- 预期：把 30 步从“猜拓扑”移到“准备顺序 + 一次做对”，与设计意图一致。
- 风险：可能提高通关率；但 Oracle 16 步、预算 30，仍要求依赖顺序，不是加预算。
- `rule_hash` 不变；`prompt_hash`/`overlay_schema_hash` 变化。

## 5. 验证

- `tests/test_v9_overlay.py::test_map25_overlay_does_not_credit_rejected_diagnosis`
- 公开启发式 16 决策成功（`runs/v9/baselines/MAP-25.json`）。

## 6. 回滚

删除 addendum 与 overlay 条目。
