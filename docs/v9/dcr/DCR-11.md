# DCR-11：MAP-15 的 goal 文本直接泄露“偶数同色、奇数互补”规则

- 状态：`requires_user_decision`（改变公开信息条件，可能改变研究构念）
- 地图：MAP-15
- 关联审计：`docs/v9/maps/MAP-15-audit.md`
- 影响面：prompt / Observation `goal`；不改变规则
- 证据：`map15.py:128` 的 `goal` 原文是“从 A/B/C 归纳‘偶数同色、奇数互补’的规则，并在 T 通过四色门。”；`inspect_symbols` 0 tick 且公开墙色与门色。任何能读 goal 的策略都不需要从训练样例归纳。

## 1. 问题

V8 三局 11–14 决策成功，`record_rule` 未被要求、`training_sample_log` 未被使用；`no_probe`/`no_rule_transfer` 消融同样成功；`legal_random` 20 seed 中 5 次成功（25%）。规则已由 goal 给出，归纳机制被旁路。

## 2. 候选

| 方案 | 改动 | 收益 | 风险 |
|---|---|---|---|
| A（推荐） | `goal` 改为“从 A/B/C 的训练样例推断门的规律，并在 T 通过四色门”，不写出规则 | 恢复归纳构念 | 需要重建 prompt hash 与 V9 对照；可能使 3/3 变成低成功率（这是测量恢复，不是加难） |
| B | 保留 goal，但把 `record_rule` 设为成功前置 | 强制显式归纳 | 改规则；可能变成形式化动作 |
| C | 保持现状，标 `CONSTRUCT_BYPASS`，不用于能力结论 | 零成本 | 该图不能回答归纳能力 |

## 3. 结论

V9 不单方修改 goal；记录为 `CONSTRUCT_BYPASS`，并把 A 作为 V10 候选。若要本轮修复，需要用户确认“公开 goal 是否允许直接给规则”。
