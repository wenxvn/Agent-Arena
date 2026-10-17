# V8 DCR 裁决记录

V7 的 12 条 `proposed` DCR 在 V8 逐条裁决。原则：
纯命名/文档矛盾做无语义修复；可证明冲突给最小变更与反例；改变能力构念或胜负条件的项
保持原构念并在报告中标注局限。每条决策都落成运行时行为或明确的“不实现”，并有回归证据。

## 一、V7 既有 12 项

| DCR | 地图 | V8 裁决 | 运行时证据 | 回归 |
|---|---|---|---|---|
| V7-DCR-001 | MAP-01 | 采纳“显式确认”语义：`interact(bridge_console, confirm_repair)`；断供计数仍私有，公开只给氧气余量 | `map01.py` 的 `confirm_repair` 分支；成功码 `REPAIR_CONFIRMED` | Oracle 18 步；`four_tick_support_interruption_fails` fixture 断言第 4 tick 失败 |
| V7-DCR-002 | MAP-02 | 不合成加权胜负；`dual_objective_completion` 只作报告比例（0.5/0.5），成功仍要求导航核 + 救生舱 | `map02.metrics()` 与 `_after_tick` 的成功条件 | 成功 fixture（9 步）与“保住核心但失去船员”失败 fixture |
| V7-DCR-003 | MAP-03 | 不新增终局码；阶段覆盖与长延迟召回分开报告，失败归因保留原四码 | `map03.py` 的 `MILESTONES` 与失败分支 | 提前提交失败 fixture；冷窗过期 fixture |
| V7-DCR-004 | MAP-05 | 采用修订后的可行窗口；旧版不可行窗口不再使用 | `map05.py` 的窗口表；Oracle 27/21 步成功 | 两条 Oracle 与 2 条手算 fixture |
| V7-DCR-005 | MAP-06/11/21 | 保留公开先验/后验字段，但条件标为“信息可用性”，不宣称纯推断能力 | `PUBLIC_FIELDS` 含 `forecast_accuracy`、`posterior_*` | 各图 Oracle + 3 条 fixture；报告中单列条件性质 |
| V7-DCR-006 | MAP-07/09 | 允许裁判侧只读事件计数；公开侧仍只有系统状态 | `map07.py` 的溢流/回流计数；`map09.py` 的级联事件 | 3 条/图 fixture，包括溢出与短路 |
| V7-DCR-007 | MAP-12 | 冻结“动作→资源→欠供判定→日推进”；每日 2 个劳动槽 | `map12.py` 的 `_settle_day()` 顺序 | 60 步 Oracle ×2；4 条 fixture |
| V7-DCR-008 | MAP-15 | 不新增显式 `predict`；首次未见状态选择作为代理并在文档标注局限 | `map15.py` 的未见状态选择与测试上限 | 4 条 fixture，含显式未见预测与第二次测试错误 |
| V7-DCR-009 | MAP-18 | 保留 V6 `map18_l3_original` 的故障窗口 (5,10) 与 13/18 阈值；静态调度地板仍在，报告中单列 | 适配器绑定 V6 冻结场景；Oracle 12 步 | `observed-recovery` 与 `head-on-collision` 两条 V7 手算值 |
| V7-DCR-010 | MAP-19/20 | 指标使用裁判侧精确温度；Agent 只看到温度带 | `map19.py`/`map20.py` 的 `temperature_bands` 与私有 `temperatures` | 越界面积 fixture；MAP-20 旁路网络 fixture |
| V7-DCR-011 | MAP-22 | 使用“按实例最优 + 有向公开边”；实例固定 `map22_l3_original`，最优 8；不增加节点别名 | `v4_adapter.py` 的实例绑定；V7 extractor | 30 步手算轨迹；非法方位 fixture |
| V7-DCR-012 | MAP-27 | 成功要求全部目标；部分完成单列，不折算为成功 | `map27.py` 的目标结算 | 3 条 fixture，含货舱冲突与未充电 stranded |

## 二、V8 新增裁决

| 编号 | 地图 | 问题 | 裁决 | 反例/边界 |
|---|---|---|---|---|
| V8-DCR-002 | MAP-02 | 泄漏触发当 tick 是否扣扩散与压力 | 不扣；触发 tick 只公开事件，下一 tick 开始结算 | 4 动作触发 fixture 的 tick 计数 |
| V8-DCR-004 | MAP-04 | 最早可行过桥 tick 不明确 | 固定 `EARLIEST_FEASIBLE_CROSSING_TICK = 5`，作为规则常量 | `ticks_and_phase` fixture 在 tick 2 进入相位 0/1 窗口 |
| V8-DCR-006 | MAP-06 | seed 与先验/预报映射未固定 | seed 0–9 使用固定映射，seed 0 = 长风暴先验 | 4 条 Oracle 覆盖短/长风暴 |
| V8-DCR-019 | MAP-19 | V7 卡片写早期冷却越界面积 20 | 以运行时精确复算为准，早期路径为 22；卡片 20 为笔误 | `early_cooling_area_and_production` 断言 22 |
| V8-DCR-020 | MAP-20 | 非法控制帧是否终止或耗 tick | 整帧拒绝、零时间、不终止；只返回错误码 | `zone_valve_rejected_atomically` fixture 断言时钟不变 |
| V8-DCR-021 | MAP-23 | seed=0 的真入口与先验 | 真入口固定为 Z；三入口先验等概率只在未观测前成立 | `river_clue_then_z` fixture |
| V8-DCR-024 | MAP-24 | `route_cost_ratio` 的分母 | 只统计有本地潮位读数的边；D-E 潮道无读数时不计入分母 | `stale_note_repeats_collapsed_edge` fixture |
| V8-DCR-025 | MAP-25 | `repair` 是否必须带 `diagnosis_code` | 允许省略；诊断准确率单独报告 | `untethered_eva_keeps_partial_coverage` 与标准流程 fixture |
| V8-DCR-028 | MAP-28 | 终局拒绝是否新增失败码 | 不新增；由 `verdict` 写入 `terminal_reason`，保持 truth-neutral | 窗口猜测矛盾与未观察记录两条 fixture |
| V8-DCR-030 | MAP-30 | Q4 召回与调查完整度是否合并 | 不合并；`q4_recall_accuracy` 与 `investigation_progress` 分开 | 完整链与缺 Q4 两条手算轨迹 |

## 三、未决与影响

- 没有“改变核心胜负/能力构念”的未决项需要暂停 V8；V7 的构念级分歧以“保留原构念 + 报告局限”处理。
- MAP-08 的天花板、MAP-18 的静态调度地板、MAP-26 的恢复地板仍存在，不能由 V8 的三次重复消除；报告中单独标注。
- MAP-19 的 22、MAP-20 的整帧拒绝、MAP-25 的可省略诊断码等均已在 runtime 与 fixture 中冻结；任何后续改动必须重新冻结并作为新版本运行。
