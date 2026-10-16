# V6 实例测量矩阵

规则版本 `v6.0`。所有实例 `review_status = pending_human_review`。`instance_id` 是独立环境实例；`seed` 仅控制随机性。Oracle 由 `scripts/validate_v6_instances.py` 在真实环境逐步回放并 100% 成功。

## 实例清单

| instance_id | 图 | 层 | 能力构念 | 配对条件 | 独立初态数 | 求解 |
|---|---|---|---|---|---|---|
| map08_l1_two_candidate | 08 | L1 | 单测试诊断 | no_hypothesis_table / hypothesis_table | 2 | 构造，5 动作 |
| map08_l2_alt_coverage | 08 | L2 | 多步信息增益（改覆盖） | 同上 | 3 | 构造，5–8 动作 |
| map08_l2_alt_candidates | 08 | L2 | 多步信息增益（改候选+拓扑） | 同上 | 3 | 构造，6–9 动作 |
| map08_l3_original | 08 | L3 | 主动诊断（V4 原场景） | 同上 | 12 | 构造，5–8 动作 |
| map16_l1_single_train | 16 | L1 | 单次预约与容量合法性 | react / constraint_table | 1 | BFS 最优 3 |
| map16_l2_siding_variant_a | 16 | L2 | 双车单避让站 | 同上 | 1 | BFS 最优 4 |
| map16_l2_siding_variant_b | 16 | L2 | 双车双避让站 | 同上 | 1 | BFS 最优 5 |
| map16_l3_original | 16 | L3 | 同步容量调度（V4 原场景） | 同上 | 1 | BFS 最优 6 |
| map18_l1_no_fault | 18 | L1 | 静态调度 | alert_off / alert_on | 1 | 贪心交付 18/18 |
| map18_l2_short_closure | 18 | L2 | 已知故障局部改线 | 同上 | 1 | 贪心交付 18/18 |
| map18_l3_original | 18 | L3 | 在线不确定故障（V4 窗口） | 同上 | 1 | 贪心交付 18/18 |
| map18_l3_long_closure | 18 | L3 | 在线不确定故障（更长窗口） | 同上 | 1 | 贪心交付 18/18 |
| map22_l1_short_return | 22 | L1 | 已知短返程 | history5 / history5_graph_memory | 1 | BFS 最优 4 |
| map22_l2_branch_loop | 22 | L2 | 部分图回溯（环+死路） | 同上 | 1 | BFS 最优 4 |
| map22_l2_dead_end_spur | 22 | L2 | 部分图回溯（双死路支） | 同上 | 1 | BFS 最优 8 |
| map22_l3_original | 22 | L3 | 空间返程记忆（V4 原场景） | 同上 | 1 | BFS 最优 8 |
| map26_l1_antenna_fault | 26 | L1 | 单故障诊断 | free_diagnosis | 1 | 构造，9 动作 |
| map26_l2_power_fault | 26 | L2 | 诊断+反馈纠错 | free_diagnosis | 1 | 构造，8 动作 |
| map26_l2_spare_rich | 26 | L2 | 备用件预算变化 | free_diagnosis | 1 | 构造，8 动作 |
| map26_l3_software_fault | 26 | L3 | 三测试诊断 | free_diagnosis | 1 | 构造，10 动作 |
| map26_recovery_antenna | 26 | L3 | 失败反馈纠错 | recovery_full / structured / hidden | 1 | 注册前缀 + 搜索修复尾 |
| map30_l1_two_event_case | 30 | L1 | 短证据链（2 事件，5 节点） | history_full / history5 / casebook | 1 | 构造，15 动作 |
| map30_l2_three_event_alt | 30 | L2 | 长间隔证据（3 事件，新案情） | 同上 | 1 | 构造，20 动作 |
| map30_l3_original | 30 | L3 | 长间隔证据（V4 原案情） | 同上 | 1 | 构造，25 动作 |

合计 24 个独立实例；非换皮独立实例：MAP-08 四个（不同候选/覆盖/拓扑）、MAP-26 四个故障实例 + 一个恢复实例、MAP-30 三个不同案情。

## 分层说明（降低/保留的能力负担）

- **MAP-16**：L1 单列车只保留“单次预约 + 容量/方向合法性”，去掉对向同步；L2 双列车仅保留一次或两次避让；L3 完整同步调度（预约、交换、容量、死锁）。
- **MAP-18**：L1 无故障静态交付；L2 已知短闭塞后的局部改线；L3 无预警/有预警的在线故障。三者共享同一需求与阈值。
- **MAP-22**：L1 两三节点已知返程；L2 部分探索图需回溯与识别重复点；L3 12 节点原任务。移动预算随路径下界设置。
- **MAP-08/26/30**：复杂度体现在诊断矩阵规模、故障/备件预算、证据链长度与解锁顺序，不靠增大步数上限。

## 对照公平性

- MAP-16/18/22 的两条件共享同一实例的初态、公开 Observation、预算与动作契约，只改预登记机制。
- MAP-08 两条件公开观察完全一致，假设表只能记录已公开证据。
- MAP-26 三个恢复条件从同一注册失败前缀分叉；hidden 是信息剥夺下限。
- MAP-30 三条件从同一固定前缀进入，A/C 访问相同已公开事实；案卷只展开已记录 evidence。

## 指标（逐图主指标）

| 图 | 主指标 |
|---|---|
| MAP-08 | 诊断准确率、错误封堵、测试次数、后验候选集大小、信息增益、压力耗尽率 |
| MAP-16 | 合法预约率、容量/交换冲突率、死锁率、makespan 与最优差、无效动作成本 |
| MAP-18 | 服务率、累计延误、故障后首次合法重规划 tick、恢复时长、非法路由 |
| MAP-22 | 返程成功率、有效移动率、重复边比例、回溯正确率、与最短返程差、截尾率 |
| MAP-26 | 失败后首个有效策略调整、重复错误率、剩余备件、诊断准确率、修复成功率 |
| MAP-30 | 关键证据召回、事实引用准确率、错误指控率、延迟步数、最终正确率 |

所有实例输出机器可读 manifest；`scenario_hash`、`public_initial_state_hash`、`private_truth_hash` 在构建时计算（见 `runs/v6/instances/<id>/manifest.json`）。
