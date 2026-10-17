# DCR-XX：<标题>

- 状态：`proposed` / `accepted` / `rejected` / `requires_user_decision`
- 地图：MAP-XX
- 关联审计：`docs/v9/maps/MAP-XX-audit.md`
- 提出人：DeepSeek V4.1 Flash（执行 Agent）
- 日期：2026-10-17
- 规则版本：V8 冻结 `rule_hash=...` → V9 候选 `rule_hash=...`
- 影响面：规则 / 公开信息 / prompt / 指标 / 预算 / 实例 seed

## 1. 原始规则与公开信息

逐条引用改动前的代码与 prompt 文本。

## 2. 证据与根因

- 引用至少 2 条 V8 Trace 的决策序号、动作、结果码；
- 引用 Oracle / 随机 / 公开启发式 / 消融结果；
- 根因分类：A 环境规则缺陷 / B 公开信息不足 / C schema 接口误导 / D 预算 / E 策略 / F 资源 / G 记忆推理 / H 运行异常 / I 证据不足；
- 明确区分事实、推断、假设。

## 3. 候选方案

| 方案 | 改动 | 预期收益 | 代价/风险 | 是否改变能力构念 |
|---|---|---|---|---|
| A（推荐） | | | | |
| B | | | | |

## 4. 选择理由

为什么选 A；为什么不选 B；是否违反“不为通关率改规则”。

## 5. 预期能力构念影响

- 机制是否从“可绕过”变为“必需”；
- 是否仍允许合法随机/启发式失败；
- 是否引入新的隐藏真值或未公开规则。

## 6. 兼容性与版本隔离

- 旧 V8 Trace 是否可回放（规则改动后通常**不可直接回放**）；
- 新 hash：`scenario_hash` / `rule_hash` / `source_hash` / `prompt_hash` / `metric_schema_hash`；
- 是否需要新的 instance seed、condition 或 V9 实验 ID；
- V8 文件是否保持只读（必须是）。

## 7. 指标变化

- 哪些指标的分母/缺失规则变化；
- 旧值如何保留（`runs/v9/rescore/` 只读重算，不覆盖）；
- 是否修复 `METRIC_DEFECT`。

## 8. 反例测试（先写失败测试）

列出新增测试文件与断言。必须包含：
- 修复前会失败的最小复现；
- 修复后 Oracle 仍成功；
- 公开策略仍可执行；
- 泄漏扫描通过。

## 9. 回滚方案

一行开关/提交级回滚；V8 数据不受影响。

## 10. 验证记录

| 命令 | 结果 |
|---|---|
| `pytest tests/test_v9_*.py` | |
| `python -m agent_arena.v9.baseline_run MAP-XX` | |
| `python scripts/validate_v8_offline.py`（只读回归） | |
| 泄漏扫描 | |

## 11. 结论与后续

- 是否 `requires_user_decision`；
- 若 accepted，V9 前后对照结果引用 `docs/v9/mimo-results.md`；
- 未解决问题。
