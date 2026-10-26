# 机制级能力画像

- 标注状态：`agent_reviewed` — 本画像由 Agent 生成，状态只能是 `agent_reviewed`；`human_approved` 必须由真实人工批准，Agent 不得自行盖章。
- 聚合规则：按机制维度聚合，不对 326 个异质指标做整体平均；每个维度只在适用地图内统计，缺失机制不补 0。
- 版本：['1.0.0', '2.0.0']；指标 schema 一致：是

| 维度 | 适用图 | 已观测图 | 可测局 | 成功 | 机制失败 | 截尾 | 成功率 | 证据等级 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 信息搜集 (`information_gathering`) | 10 | 1 | 8 | 0 | 0 | 8 | — | `INSUFFICIENT` |
| 记忆 / 状态追踪 (`memory_tracking`) | 7 | 1 | 8 | 0 | 0 | 8 | — | `INSUFFICIENT` |
| 规划 / 重规划 (`planning_replanning`) | 10 | 1 | 8 | 0 | 0 | 8 | — | `INSUFFICIENT` |
| 资源约束 (`resource_constraints`) | 13 | 1 | 8 | 0 | 0 | 8 | — | `INSUFFICIENT` |
| 故障恢复 (`failure_recovery`) | 9 | 0 | 0 | 0 | 0 | 0 | — | `NOT_TESTED` |
| 证据推理 (`evidence_reasoning`) | 11 | 0 | 0 | 0 | 0 | 0 | — | `NOT_TESTED` |

## 代表指标与缺口

### 信息搜集
- 代表指标：`map22.v10.mission_success`, `map22.v10.goal_recorded`, `map22.v10.memory_writes`, `map22.v10.route_recall`, `map22.v10.wasted_moves`
- 未观测地图：MAP-01, MAP-02, MAP-06, MAP-08, MAP-14, MAP-15, MAP-21, MAP-25, MAP-26
- 缺失机制不记为 0；`success_rate=None` 表示证据不足，不是「能力为零」。

### 记忆 / 状态追踪
- 代表指标：`map22.v10.mission_success`, `map22.v10.goal_recorded`, `map22.v10.memory_writes`, `map22.v10.route_recall`, `map22.v10.wasted_moves`
- 未观测地图：MAP-01, MAP-03, MAP-11, MAP-23, MAP-24, MAP-28
- 缺失机制不记为 0；`success_rate=None` 表示证据不足，不是「能力为零」。

### 规划 / 重规划
- 代表指标：`map16.v10.mission_success`, `map16.v10.committed_ticks`, `map16.v10.deadlock_count`, `map16.v10.legal_action_rate`, `map16.v10.makespan_gap`
- 未观测地图：MAP-05, MAP-10, MAP-12, MAP-13, MAP-17, MAP-18, MAP-24, MAP-25, MAP-27
- 缺失机制不记为 0；`success_rate=None` 表示证据不足，不是「能力为零」。

### 资源约束
- 代表指标：`map16.v10.mission_success`, `map16.v10.committed_ticks`, `map16.v10.deadlock_count`, `map16.v10.legal_action_rate`, `map16.v10.makespan_gap`
- 未观测地图：MAP-02, MAP-04, MAP-07, MAP-09, MAP-10, MAP-12, MAP-17, MAP-18, MAP-19, MAP-20, MAP-26, MAP-30
- 缺失机制不记为 0；`success_rate=None` 表示证据不足，不是「能力为零」。

### 故障恢复
- 代表指标：—
- 未观测地图：MAP-04, MAP-05, MAP-07, MAP-09, MAP-11, MAP-19, MAP-20, MAP-21, MAP-29
- 缺失机制不记为 0；`success_rate=None` 表示证据不足，不是「能力为零」。

### 证据推理
- 代表指标：—
- 未观测地图：MAP-03, MAP-06, MAP-08, MAP-13, MAP-14, MAP-15, MAP-23, MAP-27, MAP-28, MAP-29, MAP-30
- 缺失机制不记为 0；`success_rate=None` 表示证据不足，不是「能力为零」。

## 限制

- 维度标签是**人工登记的公开机制**，不是从指标里反推出来的；
- 同一局可能同时属于多个维度（例如 MAP-30 既在证据推理也在资源约束）；
- 成功率只描述已观测样本，不构成跨地图可比的能力分数。
