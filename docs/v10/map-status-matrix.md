# V10 30 图状态矩阵

- 由 `python -m agent_arena.v10.status` 生成；CSV 同目录 `map-status-matrix.csv`。
- `construct_status`（FORCED/OPTIONAL/BYPASS/BLOCKED）与 `validity_status`（VALIDATED/NEEDS_MORE_EVIDENCE/NEEDS_REDESIGN/BLOCKED）是两个独立维度。
- 全部为 `agent_reviewed`，没有 `human_approved`。

| map | 难度 | 构念 | V9 效度 | V10 构念 | V10 效度 | seeds | Oracle | 基线 | 消融 | MiMo | DCR | 结论 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MAP-01 | 飞船简单 | 生命支持优先 + 互斥支路依赖链 | FORCED/VALIDATED | FORCED | VALIDATED | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-02 | 飞船中等 | 事件触发的双目标重排 | FORCED/VALIDATED | FORCED | VALIDATED | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-09 | Batch 0 继承 V9，待 V10 证据 |
| MAP-03 | 飞船困难 | 五阶段里程碑 + 远期代码召回 | BYPASS/BLOCKED | FORCED | NEEDS_MORE_EVIDENCE | 6（0,1,2,3,4,5） | 6/6（机制触发 6/6） | 启发式 6/6；随机 0/120 | late_read 0/6；no_memory 0/6；random_guess 0/6 | V10 未运行 | DCR-V10-01 | Batch 1：码 seed 化、goal 去泄露、清单封存、write_memory、EVA 对齐；三消融 0/6，启发式 6/6 |
| MAP-04 | 灯塔简单 | 潮汐相位预测 + 回程时机 | BYPASS/NEEDS_REDESIGN | BYPASS | NEEDS_REDESIGN | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-09 | Batch 0 继承 V9，待 V10 证据 |
| MAP-05 | 灯塔中等 | 三窗口共享供电排程 | FORCED/VALIDATED | FORCED | VALIDATED | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-02 | Batch 0 继承 V9，待 V10 证据 |
| MAP-06 | 灯塔困难 | 80% 条件预报 + 风险预算 | BYPASS/NEEDS_REDESIGN | FORCED | NEEDS_MORE_EVIDENCE | 10（0,1,2,3,4,5,6,7,8,9） | 10/10（机制触发 9/10） | 启发式 9/10；随机 0/200 | always_direct 5/10；always_reinforce 9/10；forecast_always 8/10 | V10 未运行 | DCR-V10-03 | Batch 2：10-seed 分层天气 cohort；短风暴计入风险；截止随 seed 公开；always_direct 5/10（长风暴全死），启发式 9/10 且效用均值 0.4228 > 三条固定策略 |
| MAP-07 | 深海简单 | 阀门方向与水位预判 | BLOCKED/NEEDS_MORE_EVIDENCE | BLOCKED | NEEDS_MORE_EVIDENCE | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-14 | Batch 0 继承 V9，待 V10 证据 |
| MAP-08 | 深海中等 | 主动测试缩小漏点假设集 | BYPASS/NEEDS_MORE_EVIDENCE | BYPASS | NEEDS_MORE_EVIDENCE | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-14 | Batch 0 继承 V9，待 V10 证据 |
| MAP-09 | 深海困难 | 漏水-电力-供氧-通信连锁 | BLOCKED/NEEDS_MORE_EVIDENCE | BLOCKED | NEEDS_MORE_EVIDENCE | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-03 | Batch 0 继承 V9，待 V10 证据 |
| MAP-10 | 极地简单 | 双仓燃料运输与时间成本 | BLOCKED/NEEDS_MORE_EVIDENCE | BLOCKED | NEEDS_MORE_EVIDENCE | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-04 | Batch 0 继承 V9，待 V10 证据 |
| MAP-11 | 极地中等 | 风暴/噪声下的搜索与生命窗 | BYPASS/NEEDS_MORE_EVIDENCE | BYPASS | NEEDS_MORE_EVIDENCE | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-05 | Batch 0 继承 V9，待 V10 证据 |
| MAP-12 | 极地困难 | 30 天跨期库存与劳动槽 | BLOCKED/NEEDS_MORE_EVIDENCE | BLOCKED | NEEDS_MORE_EVIDENCE | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-06 | Batch 0 继承 V9，待 V10 证据 |
| MAP-13 | 金字塔简单 | 约束满足 + 唯一序列 | OPTIONAL/NEEDS_MORE_EVIDENCE | OPTIONAL | NEEDS_MORE_EVIDENCE | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-14 | 金字塔中等 | 真假证词推理 | BYPASS/NEEDS_REDESIGN | BYPASS | NEEDS_REDESIGN | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-15 | 金字塔困难 | 从训练样例归纳变化规则 | BYPASS/NEEDS_REDESIGN | FORCED | NEEDS_MORE_EVIDENCE | 10（0,1,2,3,4,5,6,7,8,9） | 10/10（机制触发 10/10） | 启发式 10/10；随机 0/200 | fixed_route 1/10；no_probe 0/10；no_transfer 0/10；random_rule 0/10 | V10 未运行 | DCR-V10-04 | Batch 2：删除 goal 泄露；6 规律家族；训练/测试墙色分离；record_rule 提交假设；消除相位自愈；四消融均 ≤1/10，启发式 10/10 |
| MAP-16 | 地铁简单 | 会车/侧线/死锁 | FORCED/VALIDATED | FORCED | VALIDATED | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-07 | Batch 0 继承 V9，待 V10 证据 |
| MAP-17 | 地铁中等 | 瓶颈下的四车多目标排程 | FORCED/VALIDATED | FORCED | VALIDATED | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-18 | 地铁困难 | 封锁后的在线恢复 | BYPASS/BLOCKED | FORCED | NEEDS_MORE_EVIDENCE | 5（0,1,2,3,4） | 5/5（机制触发 5/5） | 启发式 5/5；随机 0/100 | greedy_dispatch 3/5；ignore_windows 0/5；no_replan 1/5 | V10 未运行 | DCR-V10-02 | Batch 1：时钟分离、发车窗口强制、5 个故障变体；抢跑 0/5，no_replan 1/5，greedy 3/5，启发式 5/5 |
| MAP-19 | 火山简单 | 2 tick 时滞热控 + 预测 | OPTIONAL/NEEDS_REDESIGN | OPTIONAL | NEEDS_REDESIGN | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-20 | 火山中等 | 多区热上限 + 有损旁路分配 | OPTIONAL/NEEDS_REDESIGN | OPTIONAL | NEEDS_REDESIGN | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-21 | 火山困难 | 隐藏喷发时刻下的停手决策 | BYPASS/NEEDS_REDESIGN | FORCED | NEEDS_MORE_EVIDENCE | 10（0,1,2,3,4,5,6,7,8,9） | 10/10（机制触发 10/10） | 启发式 10/10；随机 0/200 | always_collect 7/10；always_evac 10/10；measure_then_evac 10/10 | V10 未运行 | DCR-V10-05 | Batch 2：safety_science 分离；10 seed 覆盖三种喷发时刻；always_evac 0.5（科研 0）、always_collect 3 灾难、risk_aware 0 灾难且均值 0.6886 最高 |
| MAP-22 | 丛林简单 | 无地图空间记忆与返程 | BYPASS/NEEDS_REDESIGN | BYPASS | NEEDS_REDESIGN | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-23 | 丛林中等 | 线索推断真入口 + 补给 | OPTIONAL/NEEDS_REDESIGN | OPTIONAL | NEEDS_REDESIGN | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-24 | 丛林困难 | 坍塌后重规划 | BYPASS/NEEDS_REDESIGN | BYPASS | NEEDS_REDESIGN | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-25 | 月球简单 | 出舱依赖顺序 + 工具匹配 | FORCED/VALIDATED | FORCED | VALIDATED | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-08/25 | Batch 0 继承 V9，待 V10 证据 |
| MAP-26 | 月球中等 | 诊断→修复→回滚 | OPTIONAL/NEEDS_MORE_EVIDENCE | OPTIONAL | NEEDS_MORE_EVIDENCE | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-14/26 | Batch 0 继承 V9，待 V10 证据 |
| MAP-27 | 月球困难 | 电量/氧气/多目标协调 | FORCED/VALIDATED | FORCED | VALIDATED | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot | DCR-27 | Batch 0 继承 V9，待 V10 证据 |
| MAP-28 | 古堡简单 | 证据收集 + 时间线 | FORCED/NEEDS_REDESIGN | FORCED | NEEDS_REDESIGN | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-29 | 古堡中等 | 证词可靠性分诊 | BLOCKED/NEEDS_REDESIGN | BLOCKED | NEEDS_REDESIGN | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |
| MAP-30 | 古堡困难 | 跨阶段案卷推理 | BLOCKED/NEEDS_REDESIGN | BLOCKED | NEEDS_REDESIGN | 0（V8/V9 仅 seed0；见 baseline-audit §5） | V9 seed0 | V9 seed0 | V9 seed0 | V8 3 rep / V9 pilot |  | Batch 0 继承 V9，待 V10 证据 |

## 汇总

| 维度 | 状态 | 图数 | 地图 |
|---|---|---:|---|
| 效度 | VALIDATED | 7 | 01、02、05、16、17、25、27 |
| 效度 | NEEDS_MORE_EVIDENCE | 13 | 03、06、07、08、09、10、11、12、13、15、18、21、26 |
| 效度 | NEEDS_REDESIGN | 10 | 04、14、19、20、22、23、24、28、29、30 |
| 效度 | BLOCKED | 0 |  |
| 构念 | FORCED | 13 | 01、02、03、05、06、15、16、17、18、21、25、27、28 |
| 构念 | OPTIONAL | 5 | 13、19、20、23、26 |
| 构念 | BYPASS | 6 | 04、08、11、14、22、24 |
| 构念 | BLOCKED | 6 | 07、09、10、12、29、30 |
