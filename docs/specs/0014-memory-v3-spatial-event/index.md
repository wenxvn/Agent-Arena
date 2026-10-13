# 0014. Memory v3 Spatial/Event

**日期**：2026-10-13
**状态**：Accepted（离线实现已完成；预算门禁已实现并验证；真实模型 pilot 待提交 SHA 冻结）

## 摘要

在现有 MemoryAgent 上增加可切换的 v3-SpatialEvent 策略，优先检验已知 room/edge/frontier 和公开因果事件记忆能否减少 seeded 地图长尾循环。默认 memory v2 行为、prompt、世界定义和 Action schema 保持原样。

## 研究依据

- S1 审计在 seeded lunar trace 中观察到 232-action 成功局，depot_store 与 telemetry_nook 的往返边各出现 41 次；seeded pyramid trace 中 relic_store 与 sand_tunnel 的往返边各出现 26 次。
- 当前 MemoryState 保存有限访问地点、背包、事实、失败动作和问题，不保存公开连边或未探索出口。
- 更多字段本身不是成功证据。M1 只在固定条件 pilot 显示稳定方向后才进入后续组合；M2/M3 暂不实现。

## 决策

### 策略选择与兼容

- RuntimeSettings 增加 memory_version，取值 v2 或 v3_spatial_event，默认 v2；run 与 benchmark 提供同名 CLI 覆盖。
- 仅 agent=memory 可选 v3。planning、planner_assisted、candidate_select 始终使用既有 v2 记忆策略，避免改变其结果口径。
- MemoryAgent v2 reducer、渲染内容和既有 provenance 值保持原样。v3 使用独立状态/reducer/renderer，不重写 MemoryAgent。
- v3 provenance 标记 memory_schema_version=v3、memory_renderer_version=v3_spatial_event。基础 system prompt hash 保持一致。

### 只使用公开证据的 M1 状态

- 以 reset Observation 初始化 current_room 和该地点可见的 available_exits。
- 以独立且有界的 visited_rooms 集合记录公开 Observation 中实际进入过的房间；v2 的 12 项 visited_locations 是有损短列表，不能单独作为 frontier 的“未访问”判断依据。
- 仅当已校验的 MoveAction 获得成功 ToolResult 时，从上一个公开 room 与新的 Observation 推导 traversed directed edge；拒绝的 move 不构成已走通边。
- 按历史公开 Observation 保存已知 room→exit 对。frontier 是目标 room 尚未访问且边尚未成功 traversed 的已观察有向出口；回到已访问 room 的出口不计入 frontier。不查询地图 JSON、WorldState 或 Environment 私有邻接表。
- 从成功 ToolResult 的公开原因与摘要记录 panel_opened、cell_staged、power_restored、code_read、escaped 事件及 step index。重复事件更新 last_seen_step，不推断未经历阶段或目标顺序。
- 继续沿用 v2 的公开背包、事实、失败动作与问题；不永久封禁失败 action，不在 M1 引入 M3 条件失效规则。

### 容量、压缩与统计

- v3 memory-data 上限 12,000 字符；访问房间、有向出口、成功边和事件集合分别有显式数量上限，所有文本仍经过既有脱敏器。
- 字符预算超限时按固定顺序省略普通旧事实、旧失败摘要和 v2 短访问列表，并输出 omission counts。v3 的访问房间、出口、边、frontier 和因果事件会影响后续导航语义，不静默淘汰；任一必需集合超过数量或字符上限时，在 provider 请求前明确失败。
- v3 的每个 executed step 记录累计 insertions、updates、invalidations、compactions、rendered_chars 与 estimated_tokens；estimated_tokens 明确标作字符估算值。M1 的 invalidations 应为 0。
- 统计结构是可选 Trace 字段；缺字段的历史 trace 继续可读取。Trace 不记录记忆文本快照或完整 reasoning。

## 验收条件

1. 相同完整公开 trace 回放得到相同 v3 memory digest、frontier 和事件顺序；两个 episode 间无状态泄漏。
2. 状态只从 Observation、经过校验的 Action、ToolResult 更新。Move 拒绝、非法 provider 候选与 correction request 不创建 traversed edge 或因果事件。
3. 测试覆盖回程、单向出口、已读码后的导航、任务顺序反转、前置条件修复和错误公开事实更新；不访问 hidden WorldState。
4. 强制超预算 fixture 验证可省略字段的压缩顺序、omission counts、保留必需信息、统计递增，以及必需房间/出口/边/事件超容量或超字符预算时的失败行为。
5. 默认 v2 的 provider 请求与现有 fixture 等价；CLI/config 可显式选择 v3；trace provenance 能区分 v2/v3；旧 Trace 无新统计字段时仍能读取。
6. Ruff、mypy、pytest、本机 audit 与 GitHub Actions 通过。真实 pilot 未运行前不得声称机制改善。

## Pilot 边界

- M1 只选择一个 S1 长尾地图和 2 个冻结 seed；Memory v2 基准与 M1 各 2 局，单局 B=100，串行运行。使用 E1 ON、H5/R1 和同一 phase 条件，逐项核验模型、prompt、地图 hash 与 seed。
- 报告 Success@60/100、动作数分布、重复边/动作、Token、provider_error 和 first-recorded attempt 标记。旧 unlimited trace 可离线裁剪预算作补充，不能替代 matched pilot。
- 真实模型调用先登记到 docs/research/v2/00-run-registry.md；设置全局超时、并发 1、每局 100 步和预先声明的 token/request 上限。超预算即停止，不自动扩充条件。
- 现有配置若不能提供可执行的 token 硬上限或模型权限，只完成所有离线工作，在 registry 标记 blocked 并写出解锁条件。

## 后果

- v2 与历史 trace 保持可复现，v3 可以单独消融。
- Trace 将增加少量可选统计字段；旧读取器必须容忍缺省。
- 一个 pilot 未显著或未出现稳定方向时，M1 可作为阴性结果结束；不以无限步通关或增加地图数替代结论。
