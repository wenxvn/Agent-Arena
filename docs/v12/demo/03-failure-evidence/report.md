# 失败证据样例（SIMULATED）

> 演示脚本：动作由人工按公开规则编写，不是模型输出，也不是 Oracle；结果只用于展示对照、诊断与可视化链路。

- 实验：`lab-20260101T000000Z-demo0001`
- 诊断总数：27（critical 0 / warning 21）

| 地图 | 类别 | 严重度 | 证据步 | 说明 |
|---|---|---|---|---|
| MAP-10 | `key_action_used_no_trigger` | warning | 1 | 机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。 |
| MAP-10 | `key_action_never_attempted` | warning | — | 核心机制动作 ['load', 'unload'] 一次都没有调用。 |
| MAP-22 | `no_progress_window` | warning | 5, 6, 7, 8, 9, 10, 11, 12 | 连续 8 步公开进度没有变化。 |
| MAP-22 | `key_action_used_no_trigger` | warning | 10 | 机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。 |
| MAP-22 | `memory_not_used` | warning | 10 | 写过记忆，但没有记录方位（bearing/path_state），无法用于返程。 |
| MAP-22 | `no_progress_window` | warning | 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 | 连续 10 步公开进度没有变化。 |
| MAP-22 | `no_progress_window` | warning | 4, 5, 6, 7, 8, 9, 10, 11, 12 | 连续 9 步公开进度没有变化。 |
| MAP-22 | `key_action_used_no_trigger` | warning | 9 | 机制动作被接受，但核心机制仍未触发（阈值/时序未达成）。 |

每条结论都能在 `runs/web/<run_id>/events.jsonl` 的 `decision` 事件里找到对应
`decision_index`；不包含任何隐藏真值。
