# V6 真实 API 复测报告（MiMo `mimo-v2.6-flash`）

- 日期：2026-10-16
- 实验：`runs/v6/experiments/pilot_20261016T035353Z_5bd53a36aca0436f81a75bb19768c09a`
- 实验 ID：`a4c916d8-b48e-4043-9122-bbb76754eceb`
- 离线门禁：`2dfa63eda78ad5e89af662841012d893e561af52b2068b80d64c5082148a8f36`
- 条件：24 局全部完成；`temperature=0`、reasoning 关闭、`json_object` + 本地严格 Action 校验、每局最多 100 决策。
- 计费（CNY，报告 usage）：**¥0.17891580**；请求尝试 281；provider 墙钟 1510.348 秒；账本未关闭。
- 说明：这是**单次运行**的描述性结果，不是模型排名，也不构成泛化结论。所有 V6 实例仍为 `pending_human_review`。

> 本报告的口径：V6 的目标是**测量效度**，不是通过率。下面按“能力是否被有效测量”判读，而不是按胜负排名。

## 1. 逐局结果

| 实例 / 条件 | 状态 | 决策 | 专属指标 |
|---|---|---|---|
| map08_l1_two_candidate / hypothesis_table | success | 6 | sealed，tests=1，peak=4.0 |
| map08_l1_two_candidate / no_hypothesis_table | success | 11 | sealed，tests=1，peak=6.0 |
| map08_l3_original / hypothesis_table | success | 6 | sealed，tests=1，peak=4.0 |
| map08_l3_original / no_hypothesis_table | success | 5 | sealed，tests=1，peak=4.0 |
| map16_l1_single_train / constraint_table | success | 7 | makespan=3，gap=0 |
| map16_l1_single_train / react | success | 6 | makespan=3，gap=0 |
| map16_l3_original / constraint_table | failure | 8 | makespan=2，NODE_CAPACITY_CONFLICT |
| map16_l3_original / react | failure | 10 | makespan=2，NODE_CAPACITY_CONFLICT |
| map18_l1_no_fault / alert_off | failure | 3 | rate=0.33，STATION_CAPACITY_EXCEEDED |
| map18_l1_no_fault / alert_on | failure | 1 | rate=0.0，HEAD_ON_COLLISION |
| map18_l3_original / alert_off | censored | 12 | rate=0.33，ACTION_LIMIT_REACHED |
| map18_l3_original / alert_on | failure | 1 | rate=0.0，STATION_CAPACITY_EXCEEDED |
| map22_l1_short_return / history5 | success | 11 | moves=8 |
| map22_l1_short_return / history5_graph_memory | success | 7 | moves=6 |
| map22_l3_original / history5 | success | 18 | moves=14，gap=6 |
| map22_l3_original / history5_graph_memory | success | 25 | moves=12，gap=4 |
| map26_l1_antenna_fault / free_diagnosis | success | 14 | restored，wrong=0，spare=1 |
| map26_l2_power_fault / free_diagnosis | success | 11 | restored，wrong=0，spare=1 |
| map26_l3_software_fault / free_diagnosis | success | 11 | restored，wrong=0，spare=1 |
| map26_recovery_antenna / recovery_full | failure | 7 | SPARES_EXHAUSTED |
| map26_recovery_antenna / recovery_hidden | failure | 5 | SPARES_EXHAUSTED |
| map26_recovery_antenna / recovery_structured | failure | 4 | SPARES_EXHAUSTED |
| map30_l1_two_event_case / history5_casebook | failure | 39 | entries=0，DEADLINE_REACHED |
| map30_l3_original / history5_casebook | failure | 53 | entries=0，DEADLINE_REACHED |

合计 13/24 成功。

## 2. 效度判读（逐图）

### MAP-22：**V5 的 0/6 确认为接口假象**

V6 修复契约后（DCR-001），MAP-22 **4/4 成功**，包括 V5 全部失败的原 12 节点场景。这是本轮最重要的结论：V5 把接口缺陷误读成了空间记忆下限。附带信号：L3 上 `history5_graph_memory` 用 12 步返回，`history5` 用 14 步（gap 4 vs 6），方向支持“合法图记忆减少返程步数”，但两者都成功，需更多实例才能谈增益。

### MAP-08：**天花板效应**

4/4 成功，且两条件无差异（含 L1 与 L3）。有表/无表条件在当前 3 候选场景下不可区分，属于天花板。V5 曾观察到无表 1/3，V6 因提示修复后无表也全过——说明该场景对当前模型过易，需加大诊断规模或提高成本才能恢复区分度。

### MAP-16：**干净的难度梯度，但条件无差异**

L1（单列车）2/2、makespan=3=最优；L3（同步双车）0/2，均因 `NODE_CAPACITY_CONFLICT` 失败。react 与 constraint_table 结果完全一致，**结构化约束表未产生可观测差异**。梯度方向正确，对照机制需重新设计。

### MAP-18：**地板效应，且预警无法分离**

4/4 失败，服务率 0–0.33，含**无故障的 L1 也失败**（0/2）。alert_on/off 失败模式不同但都失败，无法分离预警效果。失败以 `STATION_CAPACITY_EXCEEDED`、`HEAD_ON_COLLISION`、`INVALID_LINK`、`COMPLETED_TRAIN_MOVED` 为主，是真实的联合调度策略失败（非 schema 问题）。当前 6 车 / 12 tick 联合时刻表对 MiMo 属地板。

### MAP-26：**自由诊断天花板 vs 恢复地板**

free_diagnosis 3/3（三个不同故障，均 restored、0 错换、余 1 备件）；恢复轨道 0/3（均 `SPARES_EXHAUSTED`）。自由诊断对当前模型过易，恢复轨道过难且三条件无差异——`recovery_full` 与 `recovery_hidden` 表现相同，未能体现信息剥夺。

### MAP-30：**地板，且暴露一个可玩性缺陷**

0/2，两局都在 39/53 决策内**从未成功记录任何案卷条目**。定位：V6 无固定前缀，模型必须自己 `record`；而合法 `entry_id`（`Q4_CODEBOOK`/`EVENT_1_HANDOFF`/…）在 V5/V6 公开 Observation 中**不可见**，模型只能臆造 `E001` 等 → `INVALID_CASEBOOK_ENTRY`。V5 因使用固定前缀（由环境代填案卷）掩盖了该缺陷。

- 本轮矩阵用的是**修复前**提示；矩阵完成后已加入“公开案卷条目顺序”披露并在诊断中验证：披露后模型改用合法 `entry_id`，但仍在 `interview`/NPC 与地理导航上失败（`NPC_NOT_HERE` 与 H↔J 往返），因此 MAP-30 的残余失败属策略/可玩性，需要人工重新设计取证流程，而不是继续加提示。

## 3. 天花板 / 地板汇总（触发暂停规则）

| 类型 | 图 | 证据 |
|---|---|---|
| 天花板 | MAP-08、MAP-22、MAP-26（free）、MAP-16 L1 | 全部或近乎全部成功，条件无差异 |
| 地板 | MAP-18、MAP-26（recovery）、MAP-30 | 全部失败，条件无差异 |

按提纲规则，**暂停扩大矩阵**，先修正测量设计。当前 24 局可用于效度判读，但不足以支持任何模型能力排名或泛化结论。

## 4. 本轮新增的接口修复（DCR-007…010）

1. **DCR-007**：非启用条件下的 `agent_hypothesis_table` 草稿不再作废整条决策；`decision_reason` 长度与嵌套表位置不再影响 Action 合法性（可执行 Action 仍严格校验）。
2. **DCR-008**：MAP-08 提示恢复 `interact` 测试站语义（`target_id` 必须是站 X/Y，不存在 `pressure_test_B/D/F`）。
3. **DCR-009**：MAP-26 恢复合法日志/测试/部件 ID 清单；新增“连续 3 次动作被拒”公开提醒以打断循环。
4. **DCR-010**：MAP-30 公开案卷条目顺序；MAP-22 非 L3 实例的 `optimal_moves` 指标按实例最短路计算（此前误用默认 8，导致 l1 出现负 gap）。

## 5. 与 V5 的对照

| 图 | V5（39 局矩阵） | V6（24 局，修复后） | 判读 |
|---|---|---|---|
| MAP-22 | 0/6，全部 step-limit 截尾 | 4/4 成功 | 接口修复后不再有下限假象 |
| MAP-08 | 有表 3/3、无表 1/3 | 4/4，两条件无差异 | 对当前模型过易 |
| MAP-16 | react 0/3、约束表 1/3 | L1 2/2、L3 0/2 | 梯度更清晰 |
| MAP-18 | 0/6 | 0/4（含无故障 L1） | 仍为地板 |
| MAP-26 | free 2/3、恢复 2/3 | free 3/3、恢复 0/3 | 恢复轨道更暴露困难 |
| MAP-30 | 案卷/完整历史 3/3（固定前缀） | 0/2（无前缀） | 固定前缀掩盖了可玩性缺陷 |

## 6. 限制

- 单次运行、每条件 1 局，不做显著性断言。
- MAP-16/18/22 的 seed 0 是固定场景；MAP-08 的 V4 原实例覆盖 B/D/F 三个漏点。
- 无固定前缀的 MAP-26 恢复与 MAP-30 是“困难且未校准”的实例，不代表能力上限。
- 未测 MAP-18 的 L2（短闭塞）与 MAP-16 的 L2 变体、MAP-22 的 L2、MAP-26 的 `spare_rich`：本轮为控制预算只选取了 L1/L3 与三个故障。
