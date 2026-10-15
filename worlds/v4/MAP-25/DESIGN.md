# MAP-25｜第一次出舱

状态：`DESIGN_COMPLETE_PENDING_RUNTIME`。本关手工设计成一次严格依赖次序的EVA维修，不是物品收集：玩家从H出发，经工具室T准备，在气闸A穿过专用出舱门抵达阵列S；诊断症状、用匹配工具修复后，还必须回到H才算成功。

## 舱段、工具和明确动作接口

唯一拓扑是H—T—A—S。H-T和T-A各走1 tick，处于增压舱内，不耗便携氧；A-S只可用`eva_exit`/`return_to_A`通行，不能用普通`move`。初始位于H，氧气12/12；气闸增压、内外舱门关闭；EVA服、诊断仪、扳手放在T；安全绳固定在A的锚点但尚未挂接。E没有额外应急氧源。

所有动作参数使用固定ID。`equip(item_id=...)`只接受`eva_suit`、`diagnostic_unit`、`wrench`、`safety_tether`；前三件只能在T装备，绳只可在A挂到`anchor`。`inspect(target=equipment)`在T返回可用清单，`inspect(target=array)`在S只返回表象`ARRAY_OUTPUT_ZERO`。`diagnose(device_id=diagnostic_unit)`需要已经检查阵列并携带诊断仪，返回固定诊断枚举`FUSE_BANK_B_OPEN`。维修接口是`repair(target_id=array_fuse_B, tool_ids=[diagnostic_unit,wrench], diagnosis_code=FUSE_BANK_B_OPEN)`，ID、数组成员和诊断码必须精确匹配。

正确流程是：在T选装EVA服与两件工具、核实清单；到A挂安全绳并排压；再由A出舱。检查症状不等于诊断，维修必须晚于诊断；返舱时关外舱门，A重新增压后沿A-T-H回到生活舱。`depressurize`要求穿服且内外门关闭，但挂绳是独立步骤；这使“穿服却漏挂绳”能进入明确的危险边界测试。

## 氧气、失败反馈和成功路线

氧气只在S区段逐外舱tick消耗：出舱1、阵列表面检查1、诊断1、维修2、返A 1。维修动作只有在开始时至少有3氧才会执行，保证两拍操作后还能保留一拍返舱；余2氧时返回`OXYGEN_RESERVE_REQUIRED_FOR_RETURN`且不开始维修。标准成功共用6氧，12起始后到H余6。室内步行、装备、增压不消耗便携氧。执行中的错误工具调用仍在S耗时2 tick/氧气2，并返回具体错误；例如未诊断先维修回`DIAGNOSIS_REQUIRED`，只带扳手维修回`MISSING_REQUIRED_TOOL:diagnostic_unit`。不在枚举里的`spanner`属于schema错误`INVALID_TOOL_ID`，执行前拒绝，不耗时也不扣氧。氧气在S降至0立即终止；返舱动作可从1氧启动并在抵达A时归零，因为人已进入安全气闸。

- **检查优先路线**：H-T；先检查清单，再按诊断仪、扳手、EVA服次序装备；T-A、挂绳、排压、EVA；S检查、诊断、按精确工具ID维修；返A、增压、A-T-H。预计tick17回H、耗氧6、无流程错误。
- **服装优先路线**：H-T；先穿服，再取扳手与诊断仪，最后检查设备；其余严格安全步骤和工具链相同。装备顺序不同，成功结果与氧气账一致。

工具效率统计以实际执行的typed tool calls为分母；schema拒绝与在舱外执行的工具不匹配分开记数，不能把自然语言里“工具大概对了”算作有效调用。

## 手写失败与边界

- **F01 未穿服出舱**：H-T-A后直接调用`eva_exit`，立即`UNSUITED_EVA`，不开始舱外段、不虚扣氧气。
- **F02 穿服但未挂绳**：按正确位置装备EVA服与工具，抵达A并排压，却跳过`equip(safety_tether)`直接出舱；立即`UNSAFE_UNTETHERED_EVA`。
- **F03 不读反馈地浪费氧气**：成功出舱并检查表面后，在未诊断时维修一次，收到`DIAGNOSIS_REQUIRED`并耗2氧；随后诊断正确，却三次只用`tool_ids=[wrench]`，每次明确收到缺诊断仪错误并耗2氧。余氧1时安全返A，氧气在舱口归零；增压并回H但阵列仍未修，终止`OBJECTIVE_INCOMPLETE_AT_H`。
- **B01/B02 氧气返舱界限**：完成其他EVA工序后，在S剩1氧可启动返舱并在A归零；S剩0不能启动返舱，原地`OXYGEN_DEPLETED`。完整标准路线从12正好耗6。
- **B03/B04 工具错误分层**：未知`spanner`在schema层零成本拒绝；已知但不足的`[wrench]`是有效typed调用，只有在S执行后返回缺工具码并耗2氧。

seed0固定阵列诊断枚举为`FUSE_BANK_B_OPEN`，但直到成功调用诊断仪才向Agent公开。公开Oracle保存一条完整EVA闭环；不得含私有故障字段、未调用工具的未来结果或chain-of-thought。状态`DESIGN_COMPLETE_PENDING_RUNTIME`只表示流程、API枚举、氧气账和反例已离线自审；不表示运行环境、Agent或模型已验证。
