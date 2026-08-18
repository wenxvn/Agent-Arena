# 0002. Spaceship Escape 环境

**Date**: 2026-08-17
**Status**: Accepted

## Summary

本 spec 定义第一个可手动完成的确定性飞船逃生世界。世界使用版本化 JSON 保存固定地图和静态内容，Python 只处理规则，Pydantic 模型隔离内部状态与 Agent 可见信息。实现后，Agent 只能使用六个公开工具探索并完成逃生，不能读取完整世界状态。

## Requirements

**User stories**:

1. 作为 Agent，我要通过公开工具探索飞船、修复主电源并逃生，从而为后续 Agent Loop 建立确定性基线。
2. 作为实验开发者，我要用直接环境调用复现每一步世界变化，从而可信地测试规则和比较 Agent 行为。

**Acceptance criteria**:

1. **AC-1**: `spaceship_escape_v1` 定义六个固定房间、固定对象和双向出口。初始位置是 `control_room`，任意整数 seed 和每次 reset 都产生相同世界内容。
2. **AC-2**: `Action` 是一个按 `tool` 判别的严格 Pydantic 联合，只允许 `look`、`move`、`inspect`、`pickup`、`use` 和 `read_terminal` 及其指定参数。
3. **AC-3**: Agent 只接收 `Observation`。它只包含当前房间、描述、可见对象、可达出口、背包和上次工具结果，绝不包含 `WorldState`、房间未发现内容或内部标记。已完成或暂时无效的目标可以从公开可见对象中隐藏。
4. **AC-4**: `look`、相邻 `move`、当前房间 `inspect` 和已揭示物品的 `pickup` 都有确定结果。终端必须使用 `read_terminal`；对终端调用 `inspect` 会返回稳定拒绝结果。所有 schema 有效的 Action 都计入一步。
5. **AC-5**: inspect 前，Storage Room 的 `look` 只显示 `storage_crate`。`inspect("storage_crate")` 后，`look` 显示 crate、screwdriver 和 replacement fuse，之后可分别 pickup。
6. **AC-6**: Maintenance Room 的 diagnostic terminal 在无主电源时可读，并提示手动修复。只有持有 screwdriver 时，`use("screwdriver", "reactor_panel")` 才打开 panel。只有 panel 已打开且持有 replacement fuse 时，`use("replacement_fuse", "damaged_fuse")` 才恢复主电源。面板打开后隐藏已完成的面板目标。
7. **AC-7**: Control Room terminal 在无电时拒绝读取，在有电时返回固定 `ALPHA-731` 并记录授权码已读。授权码读取前，Reactor Room 不公开 `escape_pod` 出口；只有在 Escape Pod 且已读到授权码时，`use("ALPHA-731", "escape_pod")` 才使 `escaped` 为真。
8. **AC-8**: 重复、目标错误、物品缺失和房间错误的有效 Action 返回稳定拒绝结果。未知工具或参数缺失不进入 Environment，由后续 Runner 在调用前按 Action schema 处理。
9. **AC-9**: Environment 记录已执行步数并报告成功状态。后续 Episode Runner 负责 30 步限制、非法模型输出修正与失败终止。

## Decision

**Chosen option**: 版本化静态 JSON，加内存 Pydantic 状态，加 Python 规则。

地图、静态对象、描述和固定授权码放入版本化 JSON。每局世界状态只在内存中存在，所有状态转换集中在 `Environment.step(action)`。

## Feature design

**Data model sketch**:

| 模型 | 字段 | 规则 |
|---|---|---|
| `WorldDefinition` | `world_id`、`version`、`goal`、`start_room`、`authorization_code`、`rooms`、`objects`、`items` | 只读 JSON 定义，`world_id` 为 `spaceship_escape_v1` |
| `RoomDefinition` | `id`、`description`、`exits`、`object_ids` | `id` 唯一，所有出口均有反向出口 |
| `ObjectDefinition` | `id`、`room_id`、`kind`、`inspect_result` | 固定对象包括 `storage_crate`、两个 terminal、`reactor_panel` 和 `escape_pod` |
| `ItemDefinition` | `id`、`container_id` | 初始内容为 screwdriver 与 replacement fuse，均属于 `storage_crate` |
| `WorldState` | `seed`、`current_room`、`inventory`、`revealed_items`、`blocked_objects`、`step_count`、`reactor_panel_open`、`main_power`、`authorization_code_read`、`escaped` | 每局内存状态，reset 恢复全部初始值 |
| `Observation` | `current_room`、`description`、`visible_objects`、`available_exits`、`inventory`、`last_action_result` | Agent 唯一可读状态，reset 后 `last_action_result` 为 `None` |
| `ToolResult` | `status`、`reason`、`summary` | `status` 只为 `success` 或 `rejected`，`reason` 为稳定枚举值 |

**固定房间和对象**:

| 房间 id | 描述 | 双向出口 | 初始可见对象 |
|---|---|---|---|
| `control_room` | 主控制中心 | `corridor` | `control_terminal` |
| `corridor` | 连接各区的中央通道 | `control_room`、`storage_room`、`maintenance_room` | 无 |
| `storage_room` | 补给储藏室 | `corridor` | `storage_crate` |
| `maintenance_room` | 维修舱 | `corridor`、`reactor_room` | `diagnostic_terminal` |
| `reactor_room` | 主反应堆舱 | `maintenance_room`、`escape_pod` | `reactor_panel` |
| `escape_pod` | 逃生舱 | `reactor_room` | `escape_pod` |

| 对象或物品 id | 种类 | 位置或容器 | 行为 |
|---|---|---|---|
| `control_terminal` | terminal | `control_room` | 无电时拒绝，有电时返回授权码 |
| `storage_crate` | container | `storage_room` | inspect 后揭示两个物品 |
| `diagnostic_terminal` | terminal | `maintenance_room` | 始终可读 |
| `reactor_panel` | fixture | `reactor_room` | screwdriver 打开 panel |
| `damaged_fuse` | fixture | `reactor_room` | 只在 panel 打开后可见 |
| `escape_pod` | fixture | `escape_pod` | 接受已读到的授权码 |
| `screwdriver` | item | `storage_crate` | 打开 `reactor_panel` |
| `replacement_fuse` | item | `storage_crate` | 修复 `damaged_fuse` |

`Action` 是判别联合，具体成员如下：

| `tool` | 必填参数 |
|---|---|
| `look` | 无 |
| `move` | `destination: str` |
| `inspect` | `target: str` |
| `pickup` | `item: str` |
| `use` | `item: str`、`target: str`，item 为背包物品 id 或已观察到的授权码字符串 |
| `read_terminal` | `target: str` |

**State transitions**:

```text
storage_crate 未检查 -> storage_crate 已检查 -> screwdriver 与 replacement fuse 可拾取
reactor_panel 关闭且主电源关闭 -> reactor_panel 打开且主电源关闭 -> reactor_panel 打开且主电源恢复
授权码未读 -> 授权码已读
未逃生 -> 已逃生
```

**Interface surface**:

| 调用 | 输入 | 输出 | 主要错误 |
|---|---|---|---|
| `reset(seed: int)` | 任意整数 seed | 初始 Observation | 无 |
| `observe()` | 无 | allowlisted Observation | 无 |
| `step(action: Action)` | 已验证的 Action | `ToolResult` 与新 Observation | 有效 Action 的拒绝结果 |
| `is_success()` | 无 | `escaped` 布尔值 | 无 |

**Tool result matrix**:

| 工具 | 成功 `reason` | 拒绝 `reason` | 状态变化 |
|---|---|---|---|
| `look` | `looked` | `already_completed` | 无 |
| `move` | `moved` | `not_adjacent`、`already_completed` | current room |
| `inspect` | `inspected` | `not_visible`、`already_completed` | inspect crate 时揭示物品 |
| `pickup` | `picked_up` | `not_revealed`、`not_present`、`already_collected`、`already_completed` | inventory |
| `use` | `panel_opened`、`power_restored`、`escaped` | `missing_item`、`wrong_target`、`panel_closed`、`code_unread`、`incorrect_code`、`already_completed` | panel、主电源或 escaped |
| `read_terminal` | `diagnostic_read`、`code_read` | `no_power`、`not_visible`、`already_completed` | 读取 Control Room code 时设置 `authorization_code_read` |

`summary` 使用按 `tool` 和 `reason` 定义的固定文本。测试必须断言 `status`、`reason` 和状态变化，不以人类可读文本作为唯一契约。

**Value sourcing**:

| Action | 产生或显示的值 | 来源 |
|---|---|---|
| `look` | 房间描述、可见对象、出口 | `RoomDefinition`、当前 room、`revealed_items` 和 inventory。crate 未检查时只显示 crate，检查后显示未拾取物品 |
| `move` | 进入的房间、可达出口 | `Action.destination` 与当前 `RoomDefinition.exits` |
| `inspect` | 固定线索、物品揭示结果 | `ObjectDefinition.inspect_result` 与 `WorldState` |
| `pickup` | 背包变化、成功或拒绝结果 | `ItemDefinition.container_id`、`revealed_items`、当前房间和 inventory |
| `use` | panel、主电源或逃生状态变化 | Action 参数、inventory、`reactor_panel_open`、`authorization_code_read` 和固定授权码 |
| `read_terminal` | 诊断信息或 `ALPHA-731` | target、`main_power`、`WorldDefinition.authorization_code`。diagnostic terminal 无电时提示手动维修，有电后返回主电源稳定 |

**Key invariants**:

1. `WorldState` 只可由 Environment 修改，绝不作为 Agent 输入或工具结果字段。
2. 每个 schema 有效 Action 恰好增加 `step_count` 一次，成功和拒绝都如此。
3. `replacement_fuse` 只能在 panel 已打开且位于 inventory 时恢复主电源。
4. `ALPHA-731` 只有在 Control Room terminal 有电时通过 `read_terminal` 出现在 Agent 可见结果中。
5. 所有名称为稳定 snake case 标识，Observation 文本可以使用人类可读描述。
6. Runner 在 `is_success()` 为真后停止调用 Environment。直接在已逃生环境调用 `step` 返回 `already_completed`，不改变谜题状态。Environment 不实现 30 步失败规则。
7. 任意整数 seed 都可传入 reset 并记录在 `WorldState.seed`。当前版本没有随机分支，因此 seed 不改变世界内容。

**Security model**:

这是本地单用户环境，没有身份或角色。信息安全边界是数据模型边界，Agent、trace 和日志只能获得 Observation allowlist 与 ToolResult 摘要。密钥、原始模型请求和完整 WorldState 不属于此功能的数据面。

**Configuration required**:

不需要新的环境变量、密钥或外部服务。世界选择、版本和 seed 继续通过现有 `RuntimeSettings` 与世界 JSON 配置。

**Critical test scenarios**:

1. 主路径从 reset 到 escape，按公开工具完成 Storage、reactor、Control Room 和 Escape Pod，验证 **AC-1**、**AC-4**、**AC-5**、**AC-6**、**AC-7**。
2. 无电读取 Control Room terminal 被拒绝，验证 **AC-7**。
3. 无 screwdriver、未打开 panel 或无 replacement fuse 的修复尝试被拒绝且不改变状态，验证 **AC-4**、**AC-6**、**AC-8**。
4. 读取 Observation 与 ToolResult 不含未揭示内容、内部标记或完整 WorldState，验证 **AC-3**。
5. 相同 seed 的 reset 产生相同 Observation 和状态，验证 **AC-1**、**AC-9**。

## Build plan

1. 在 `arena` 定义 Action、Observation、ToolResult、WorldState 和 Environment 抽象，并创建 `spaceship_escape_v1` JSON 世界定义，满足 **AC-1**、**AC-2**、**AC-3**、**AC-9**。
2. 实现世界工厂以及 `look`、`move`、`inspect`、`pickup` 的确定规则和 Observation allowlist，满足 **AC-3**、**AC-4**、**AC-5**、**AC-8**。
3. 实现 diagnostic terminal、reactor panel、replacement fuse、Control Room terminal 与 Escape Pod 的状态转换，满足 **AC-6**、**AC-7**、**AC-8**。
4. 编写直接环境规则测试和手动通关路径测试，覆盖拒绝结果、信息边界和 reset 可重复性，满足 **AC-1** 至 **AC-9**。

## Consequences

**收益**:

1. 环境规则独立于模型调用，可作为后续 Agent 实验的稳定对照。
2. 明确的 Action 与 Observation 契约阻止 Agent 直接读取或修改内部状态。

**限制与代价**:

1. 世界是固定且线性的，不能代表复杂分支任务。
2. Python 规则在世界数量增加时需要抽象，但当前不引入通用规则引擎。

**中性影响**:

1. 30 步失败终止、trace 持久化和模型错误修正仍由后续 Runner 功能实现。
2. 当前 CLI 继续写 scaffold episode，直到 Agent Loop 与 Trace 功能替换该路径。

## Rationale

决策依据与备选方案见 [rationale.md](rationale.md)。
