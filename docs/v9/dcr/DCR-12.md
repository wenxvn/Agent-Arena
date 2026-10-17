# DCR-12：MAP-03 的“远期召回”与 EVA 计费

- 状态：`requires_user_decision`（涉及记忆通道与计费规则）
- 地图：MAP-03
- 关联审计：`docs/v9/maps/MAP-03-audit.md`
- 影响面：runner 记忆通道 / EVA 计费 / 指标定义
- 证据：
  1. `map03.py:93` 只在 `just_read_tag` 的那一个 Observation 里公开 `route_tag_value="K7"`；`_apply` 开头即清零。
  2. `v9/runner.py`（与 V8 相同）只把 `action/result/tick` 放进最近 5 条 history，不设置 `memory_data`，`decision_reason` 不回灌。
  3. 里程碑顺序允许把 P2（读 tag + 稳定样本）放到最后；读 tag 后只需 3 个决策即可提交，落在 5 条 history 内 → “远期召回”不是必需。
  4. `evidence_or_rules.yaml` 写“进入、维修、返回各消耗 1”，运行时 `node` 判定导致退出 V 不扣；Oracle 第 24 步 `eva_supply=1` 与文档不符。

## 1. 问题

- `map03.long_delay_recall_accuracy` 名义上测 15 步延迟召回，实际只测“5 条 history 内是否抄下 K7”；若把 P2 放最后，延迟可降到 3。
- EVA 计费与设计文档不一致，导致 `successful_route_cost` 与失败归因偏差。

## 2. 候选

| 方案 | 改动 | 收益 | 风险 |
|---|---|---|---|
| A | 给 Agent 增加公开的 `write_note/read_note`（agent-owned），并把 P2 设为 P3/P4 前置 | 真正测长期记忆 | 改 runner 契约与新动作，属于能力构念变更 |
| B | 保持机制，但把指标改名为 `short_delay_code_copy`，不再宣称 long-delay | 指标诚实 | 失去长期记忆构念 |
| C | 修正 EVA 计费使退出也扣 1，并同步文档/Oracle | 规则与文档一致 | 改规则与 Oracle，需重冻结 |

## 3. 结论

V9 不修改 runner 记忆通道，也不改 EVA 计费；MAP-03 标 `NEEDS_REDESIGN`（P0）并等待用户选择 A/B/C。任何选择都必须新建 V10 版本，不能改写 V8 Trace。
