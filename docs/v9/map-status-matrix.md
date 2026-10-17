# V9 地图状态矩阵

- 状态定义：`VALIDATED` 目前可作研究级测量；`NEEDS_MORE_EVIDENCE` 接口已修但尚无新证据；`NEEDS_REDESIGN` 存在构念/规则/指标缺陷；`BLOCKED` 需要用户先裁定规则或构念
- “V9 修复后”是**待复核判断**，不是用户批准；`human_approved` 未标记
- V8 90 局与 hash 保持只读；状态不按通关率重标

| map | 世界 | 难度 | V8 | 审计状态 | 已实施 V9 修复 | 修复后状态 | 优先级 | 下一步 |
|---|---|---|---|---|---:|---|
| MAP-01 | 飞船 | 简单 | 0/3 | VALIDATED | 无 | VALIDATED | P2 | 保持只读；可作依赖链测量 |
| MAP-02 | 飞船 | 中等 | 0/3 | VALIDATED | DCR-09 指标叠加 | VALIDATED | P2 | 用新自适应指标替代恒 1 的 latency |
| MAP-03 | 飞船 | 困难 | 0/3 | NEEDS_REDESIGN | 无 | BLOCKED | P0 | DCR-12：记忆通道/EVA 计费需用户裁定 |
| MAP-04 | 灯塔 | 简单 | 1/3 | NEEDS_REDESIGN | 无（候选：补 tick） | NEEDS_REDESIGN | P1 | DCR-09 路线指标 + 公开 tick 候选 |
| MAP-05 | 灯塔 | 中等 | 0/3 | VALIDATED | DCR-02 公开切电/窗口 | VALIDATED | P1 | 可作共享供电排程测量 |
| MAP-06 | 灯塔 | 困难 | 3/3 | NEEDS_REDESIGN | 无（DCR-10 待裁定） | NEEDS_REDESIGN | P0 | 改为 10-seed cohort；补 VOI |
| MAP-07 | 深海 | 简单 | 0/3 | BLOCKED | DCR-14 公开 control_panel | NEEDS_MORE_EVIDENCE | P1 | 重跑 MiMo 验证阀门链 |
| MAP-08 | 深海 | 中等 | 0/3 | NEEDS_REDESIGN | DCR-14 公开复合边名/inspect | NEEDS_MORE_EVIDENCE | P1 | 处理空壳 hypothesis_table；扩 seed |
| MAP-09 | 深海 | 困难 | 0/3 | BLOCKED | DCR-03 公开短路规则 | NEEDS_MORE_EVIDENCE | P0 | 已从 2 决策死亡推进到 12 决策；再测 |
| MAP-10 | 极地 | 简单 | 0/3 | NEEDS_REDESIGN | DCR-04 公开燃料分仓 | NEEDS_MORE_EVIDENCE | P1 | 重跑；观察是否从“未装载”转为规划错误 |
| MAP-11 | 极地 | 中等 | 0/3 | NEEDS_REDESIGN | DCR-05 公开补给消耗 | NEEDS_MORE_EVIDENCE | P1 | 重跑；覆盖非 seed 0 |
| MAP-12 | 极地 | 困难 | 0/3 | BLOCKED | DCR-06 边 id + 研究分叠加 | NEEDS_MORE_EVIDENCE | P0 | 重跑；研究分应成为主失败点 |
| MAP-13 | 金字塔 | 简单 | 2/3 | NEEDS_REDESIGN | 无 | NEEDS_MORE_EVIDENCE | P2 | 修 `illegal_door_attempts`/ratio 口径 |
| MAP-14 | 金字塔 | 中等 | 0/3 | NEEDS_REDESIGN | 无 | NEEDS_REDESIGN | P0 | 盲交 2/3；改成功判据需用户裁定 |
| MAP-15 | 金字塔 | 困难 | 3/3 | NEEDS_REDESIGN | 无（DCR-11 待裁定） | NEEDS_REDESIGN | P0 | goal 泄露规则；需删除规则文本 |
| MAP-16 | 地铁 | 简单 | 0/3 | VALIDATED | DCR-07 预约语义 | VALIDATED | P1 | 可作会车/死锁测量 |
| MAP-17 | 地铁 | 中等 | 0/3 | VALIDATED | 无（line 枚举待补） | VALIDATED | P1 | 补 `line ∈ ring|branch` 一行 |
| MAP-18 | 地铁 | 困难 | 0/3 | NEEDS_REDESIGN | 无 | BLOCKED | P0 | step_limit=12 规则缺陷需用户裁定 |
| MAP-19 | 火山 | 简单 | 0/3 | NEEDS_REDESIGN | 无 | NEEDS_REDESIGN | P1 | forecast 反馈/指标缺失 |
| MAP-20 | 火山 | 中等 | 2/3 | NEEDS_REDESIGN | 无 | NEEDS_REDESIGN | P1 | 旁路分配被直供支配 |
| MAP-21 | 火山 | 困难 | 3/3 | NEEDS_REDESIGN | DCR-09 科研单位叠加 | NEEDS_REDESIGN | P0 | 成功判据需用户裁定（DCR-13） |
| MAP-22 | 丛林 | 简单 | 0/3 | NEEDS_REDESIGN | 无（公开记忆已由策略使用） | NEEDS_REDESIGN | P0 | 公开胜利条件；预算口径待裁定 |
| MAP-23 | 丛林 | 中等 | 1/3 | NEEDS_REDESIGN | 无 | NEEDS_REDESIGN | P1 | 修 `cost_per_discovery` 分母 |
| MAP-24 | 丛林 | 困难 | 2/3 | NEEDS_REDESIGN | 无 | NEEDS_REDESIGN | P1 | 让成功路径必须穿越坍塌区 |
| MAP-25 | 月球 | 简单 | 0/3 | NEEDS_REDESIGN | DCR-08 拓扑/耗氧 + 覆盖率 | VALIDATED | P1 | 可作 EVA 依赖顺序测量 |
| MAP-26 | 月球 | 中等 | 0/3 | BLOCKED | DCR-14 枚举公开 | NEEDS_MORE_EVIDENCE | P0 | 重跑；区分诊断与盲换+回滚 |
| MAP-27 | 月球 | 困难 | 0/3 | VALIDATED | 无 | VALIDATED | P2 | 可作电量/氧气协调测量 |
| MAP-28 | 古堡 | 简单 | 0/3 | NEEDS_REDESIGN | 无 | NEEDS_REDESIGN | P1 | 公开 person/entry 枚举与记录前置 |
| MAP-29 | 古堡 | 中等 | 0/3 | NEEDS_REDESIGN | 无 | NEEDS_REDESIGN | P1 | 公开比对/提交语义 |
| MAP-30 | 古堡 | 困难 | 0/3 | NEEDS_REDESIGN | 无 | NEEDS_REDESIGN | P1 | 公开 entry 映射/法庭节点 |

## 汇总

| 状态 | 图数 | 地图 |
|---|---:|---|
| VALIDATED | 7 | 01、02、05、16、17、25、27 |
| NEEDS_MORE_EVIDENCE | 8 | 07、08、09、10、11、12、13、26 |
| NEEDS_REDESIGN | 13 | 04、06、14、15、19、20、21、22、23、24、28、29、30 |
| BLOCKED | 2 | 03、18 |

## 优先级

- **P0（10）**：03、06、09、12、14、15、18、21、22、26（其中 09/12/26 已在 V9 修接口，等复测）
- **P1（17）**：04、05、07、08、10、11、13、16、17、19、20、23、24、25、28、29、30
- **P2（3）**：01、02、27

> 注：优先级按“阻塞程度”而非成功率；05/16 已 VALIDATED 但仍建议补公开信息，因此列 P1。

## 研究级测量结论

- **可直接用于能力结论的图**：01、02、05、16、17、25、27（7 张）。
- **修接口后需要新证据**：07、08、09、10、11、12、13、26（8 张）。
- **仍只是工程可运行、不是研究级测量**：其余 15 张；其中 03/18 需要先裁定规则，06/14/15/21/22/24 需要先修构念，19/20/23/29/30 需要先修指标/公开语义。
