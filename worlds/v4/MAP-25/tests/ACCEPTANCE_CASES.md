# MAP-25 环境实现后验收用例

本设计阶段不运行pytest；以下为环境实现后的精确验收规格。

1. Reset在H，氧气12/12，气闸增压且内外舱门关闭；EVA服、诊断仪、扳手只在T，固定安全绳锚点在A且未挂接。
2. H-T、T-A室内边每次1 tick、不耗便携氧；A-S只接受`eva_exit`与`return_to_A`，普通`move`不得越过外舱门。
3. `equip(item_id=...)`和`repair(tool_ids=...)`使用精确ID enum；未知`spanner`必须执行前返回`INVALID_TOOL_ID`且不推进时间或氧气。
4. 未穿服调用`eva_exit`立即终止为`UNSUITED_EVA`；穿服但未挂绳立即终止为`UNSAFE_UNTETHERED_EVA`；两种都不能改动阵列状态。
5. `depressurize`需在A且穿服、内外门关闭；出舱后返A关闭外门，`pressurize`后才允许走A-T-H。
6. T的装备检查只列出可用工具，不泄漏S点隐含故障；S点检查只返回症状`ARRAY_OUTPUT_ZERO`。
7. 携带`diagnostic_unit`并先检查阵列后，`diagnose`返回唯一精确枚举`FUSE_BANK_B_OPEN`。维修前缺诊断码返回`DIAGNOSIS_REQUIRED`；已诊断但`tool_ids=[wrench]`返回`MISSING_REQUIRED_TOOL:diagnostic_unit`。
8. 执行于S点的检查/诊断各耗1 tick和氧；维修无论成功或域错误尝试均耗2 tick/氧；舱外时间不得扣成负氧。
9. `return_to_A`最低启动库存1；扣至0时必须已经到达A，之后可增压并回H；S点库存0立即无法返舱。
10. 只有修复数组并携带该完成状态返回H才成功；只修复不返舱、只返舱未维修、未取得正确诊断码都不能成功。
11. F01-F03及B01-B04每个动作后的氧气、错误码、位置和array状态逐项比对YAML。
12. 未知`FUSE_BANK_C_OPEN`诊断枚举执行前返回`INVALID_DIAGNOSIS_CODE`，不推进tick或氧气；与诊断成功后使用错误但已知码返回域错误分开。
13. 执行两拍维修前必须至少有3氧，保留1氧返舱；余2氧调用有效维修返回`OXYGEN_RESERVE_REQUIRED_FOR_RETURN`，时间和氧气不变。
14. 相同seed0回放时Oracle只含公开 Observation 与typed动作结果；私有fixture诊断码仅在正确诊断后进入公共记录，绝无隐藏故障字段或思维链。
