# V9 构念效度：30 图是否真的测到了它声称的能力

- 输入：30 份逐图审计的 §1/§2/§9、`runs/v9/baselines/MAP-XX.json`、V8 90 局 Trace
- 判定口径：**成功路径是否必须使用核心机制**；不是“3/3 就天花板”，也不是“0/3 就能力为零”
- 标签：`FORCED`（机制是通关必需）/ `OPTIONAL`（机制是效率或护栏，可绕过）/ `BYPASS`（存在不触发核心机制的成功路径）/ `BLOCKED`（公开信息或预算使机制不可执行）

## 1. 总表

| map | 声称的核心构念 | 机制在 V8 三局触发? | 最短公开成功路径 | 消融/随机证据 | 判定 |
|---|---|---|---|---|---|
| MAP-01 | 生命支持优先 + 互斥支路依赖链 | 是（断供 2 次、依赖违规 4 次） | 15 决策（启发式） | `no_support_handoff` 失败；随机 0/20 | FORCED |
| MAP-02 | 事件触发的双目标重排 | 是（3/3 泄漏触发） | 10 决策（先封核） | `no_leak_response` 失败；随机 0/20 | FORCED |
| MAP-03 | 五阶段里程碑 + 远期代码召回 | 里程碑是；远期召回**否** | 30 决策（读 tag 后 3 步提交） | `no_key_memory` 失败；但 tag 可放最后 | BYPASS（召回） |
| MAP-04 | 潮汐相位预测 + 回程时机 | 否（R0 全程绕行） | 9 决策（相位算术）；绕行 15；盲撞 14 | `detour_shortcut`/`no_phase_wait` 均成功 | BYPASS |
| MAP-05 | 三窗口共享供电排程 | 是（窗口错过 3/3） | 19 决策 | `no_power_switch`/`no_window_wait` 失败 | FORCED |
| MAP-06 | 80% 条件预报 + 风险预算 | **否**（seed 0 无风暴） | 2 决策直达（seed 0）；5 决策加固（全 seed） | `shortcut`/`forecast_trusting` 在 seed 0 成功 | BYPASS（实例选择） |
| MAP-07 | 阀门方向与水位预判 | 否（0 次阀门操作） | 6 决策（启发式） | 接口错名；随机 0/20 | BLOCKED |
| MAP-08 | 主动测试缩小漏点假设集 | 否（三局 `tests_run=0`） | 5 决策（1 次测试） | `no_hypothesis` 成功；随机 0/20 | BYPASS（条件空转） |
| MAP-09 | 漏水-电力-供氧-通信连锁 | 否（2 决策短路） | 10 决策（先封舱） | `skip_pump` 成功；随机 0/20 | BLOCKED（阈值未公开） |
| MAP-10 | 双仓燃料运输与时间成本 | 否（0 次装载） | 5 决策（load 5 → 发电机 → 发报） | `no_key_mechanism` 失败；随机 0/20 | BLOCKED（规则未公开） |
| MAP-11 | 风暴/噪声下的搜索与生命窗 | 否（seed 0 无风暴；0 次风暴） | 7 决策（resupply 8 → 短道） | 9/10 seed 成功；seed 8 失败 | BYPASS（seed 0）+ BLOCKED（补给） |
| MAP-12 | 30 天跨期库存与劳动槽 | 部分（研究链不可执行） | 60 决策（需边 id） | `no_key_mechanism` 失败；62/62 transfer 被拒 | BLOCKED |
| MAP-13 | 约束满足 + 唯一序列 | 是（2/3 成功） | 20 决策 | `no_direction_nail` 成功 | OPTIONAL（方向钉） |
| MAP-14 | 真假证词推理 | **否**（0 次 ask/compare） | 5 决策盲交（2/3 概率） | `blind_two_submissions` 成功；随机 0/20 | BYPASS |
| MAP-15 | 从训练样例归纳变化规则 | **否**（goal 直接给规则；0 次 predict） | 4 步固定路径 | 随机 5/20；`no_probe`/`no_rule_transfer` 成功 | BYPASS |
| MAP-16 | 会车/侧线/死锁 | 是（3/3） | 16 决策（BFS 最优） | `no_siding` 死锁；随机 0/20 | FORCED |
| MAP-17 | 瓶颈下的四车多目标排程 | 部分（换线是必需；3/3 未正确换线） | 12 决策（10/10） | `no_branch_switch` 失败；随机 0/20 | FORCED |
| MAP-18 | 封锁后的在线恢复 | **否**（0/3 真正触发恢复） | 12 决策 18/18（守窗口）或抢跑旁路 | `ignore_windows` 成功且 delay=0 | BYPASS + BLOCKED（12 上限） |
| MAP-19 | 2 tick 时滞热控 + 预测 | 部分（热控是；预测 0 次） | 15 决策 | `no_lag_load_curtailment` 成功 | OPTIONAL（预测） |
| MAP-20 | 多区热上限 + 有损旁路分配 | 热上限是；旁路从未触发 | 静态不动点 | `no_load_management` 失败 | OPTIONAL（旁路） |
| MAP-21 | 隐藏喷发时刻下的停手决策 | **否**（直达撤离） | 1 决策 `move O_E` | `shortcut_direct_evac` 成功；随机 6/20 | BYPASS |
| MAP-22 | 无地图空间记忆与返程 | 记忆写入是；返程否 | 12 决策（无记忆策略） | `no_memory_write` 成功 | BYPASS（记忆） |
| MAP-23 | 线索推断真入口 + 补给 | 是（R2 成功） | 10 决策 | `no_scout` 成功（证据弱） | OPTIONAL（线索） |
| MAP-24 | 坍塌后重规划 | **否**（两局成功均未改路） | 9–12 决策（避桥） | `no_replan` 失败；随机 0/20 | BYPASS（改路） |
| MAP-25 | 出舱依赖顺序 + 工具匹配 | 部分（依赖是；诊断名错） | 16 决策 | `no_tool_collection` 失败 | FORCED（依赖） |
| MAP-26 | 诊断→修复→回滚 | 是（11/10 决策） | 11 决策 | `no_diagnosis` 也成功（盲换+回滚） | OPTIONAL（诊断） |
| MAP-27 | 电量/氧气/多目标协调 | 是（3/3 电量失败） | 19 决策 | 随机 0/20 | FORCED |
| MAP-28 | 证据收集 + 时间线 | 部分（证据覆盖 0.25–0.75） | 16 步 | `no_record` 失败 | FORCED（记录） |
| MAP-29 | 证词可靠性分诊 | 否（0 次 compare） | 13–17 步 | `no_compare` 失败；0 次统计 | BLOCKED（语义未公开） |
| MAP-30 | 跨阶段案卷推理 | 否（0 次有效案卷链） | 24 步 | `no_casebook` 失败 | BLOCKED（条目映射） |

统计：FORCED 8 图（01、02、05、16、17、25、27、28）；OPTIONAL 5 图（13、19、20、23、26）；BYPASS 11 图（03、04、06、08、11、14、15、18、21、22、24）；BLOCKED 6 图（07、09、10、12、29、30）。MAP-11/18 同时有“实例旁路”和“接口/预算阻塞”，按主要问题归类并在逐图审计中说明。

## 2. 关键结论（RQ2）

1. **“机制被触发”与“机制是必需”是两件事。** MAP-02/05/16/17 的机制在失败轨迹中真实触发；MAP-14/15/21 的成功轨迹完全没有触发核心推理。
2. **最强的旁路证据来自随机与消融**：MAP-15 随机 5/20、MAP-21 随机 6/20；MAP-04 的绕行与盲撞都成功；MAP-14 的 5 步盲交在 seed 0–8 上 6/9 成功。
3. **“困难图”三张里有三张旁路**：MAP-06（实例 seed）、MAP-15（goal 泄露）、MAP-21（直达撤离）。因此 11/30 的困难层成功不能读作“困难能力更强”。
4. **MAP-03 的长期召回不是必需**：tag 可最后读、3 步内提交；runner 只保留 5 条 history。指标名 `long_delay_recall_accuracy` 与实际延迟不符。
5. **MAP-18/22/24 的“动态重规划/空间记忆”没有被成功路径使用**：MAP-18 抢跑可在封锁前完成；MAP-24 避开桥即可；MAP-22 无记忆策略 12 步成功。
6. **MAP-26 的“诊断”可被盲换+回滚替代**，但两者在 `tests_run`、`recovery_latency` 上可区分；这属于“替代策略”而不是完全旁路。
7. **MAP-28 是唯一证据任务里 FORCED 的图**：`no_record` 失败、`key_evidence_coverage` 区分 0.25/0.75，说明“记录”是硬前置；但公开枚举缺口仍需修。

## 3. 对指标的要求（RQ4）

- 成功/失败是二值；要区分“真正使用机制”与“绕过”，至少需要一个**机制事件计数**或**质量分母**。
- V9 已补的叠加指标：`map21.scientific_units_evacuated`（直达 1/3 vs 完整 3/3）、`map02.adaptive_response_within_2`（旧 latency 恒 1）、`map04.tide_route_used`、`map12.research_points_completion`、`map25.required_check_coverage_corrected`。
- 仍缺的：MAP-15 的“是否从样例归纳”、MAP-14 的“是否用证词”、MAP-24 的“是否真的改路”、MAP-18 的“是否在封锁后恢复”。这些在 V9 只记录为候选，不伪造分数。

## 4. 证据边界

- `OPTIONAL` 不等于“地图无效”：护栏/效率机制可以是有意义的测量，只要报告里不把它当作成功前置。
- `BYPASS` 是**构念层**结论，不等于规则 bug；修复通常需要改成功判据或实例选择，标 `requires_user_decision`。
- 本表的状态是 `agent_reviewed`；`human_approved` 未标记。
