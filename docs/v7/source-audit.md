# V7 起点审计（Batch 0）

- 审计日期：2026-10-17
- 仓库：`wenxvn/Agent-Arena`
- 冻结 HEAD：`766ec82529d4ee2499dde9592452eb68592f4637`
- 工作区基线：`main...origin/main`，无已跟踪文件改动；仅有 `研究提纲/V1..V7` 七个未跟踪文档。
- 工具链：`uv` 未在 PATH，使用项目虚拟环境 `.venv/Scripts/python.exe` 等效执行；Python 3.13.3。
- 审计范围：`AGENTS.md`、`README.md`、`worlds/v4/README.md`、`worlds/v4/MAP-01..30` 的 `DESIGN.md / map_spec.yaml / evidence_or_rules.yaml / acceptance.md / oracle_trace.jsonl / failure_traces/cases.yaml / tests/ACCEPTANCE_CASES.md`、`docs/v5/*`、`docs/v6/*`、`src/agent_arena/worlds/scenario_v4/*`、`src/agent_arena/v6/*`、`tests/`。

本文件只记录审计事实。它不是实测报告；除 V6 已存在的 47 局单次运行外，本轮没有新的付费调用。

## 1. 证据等级

| 等级 | 含义 | 本仓库现状 |
|---|---|---|
| E0 | 设计设想 | 无单独 E0 地图；30 图均有 `map_spec.yaml` 与纸面 Oracle |
| E1 | 形式化规格 + 规则/验收测试材料 | 30/30 具备 |
| E2 | 离线 Oracle 回放或独立求解器 | 6 张运行时地图具备独立求解器；另有 19 张设计图具备离线审计脚本；合计 25 图有 E2 级离线证据 |
| E3 | 真实 API 单次运行 | MAP-08/16/18/22/26/30 共 47 局，单次、每条件 1 局 |
| E4 | 多实例配对重复 | **没有**；固定 scene 的 seed 重复不等于独立实例重复 |
| E5 | 跨模型复现 | **没有**；只测过 `mimo-v2.6-flash` |

### 1.1 逐图证据等级

| 地图 | E1 | E2 | E3 | 说明 |
|---|---|---|---|---|
| MAP-01–07 | ✅ | 纸面 Oracle | ❌ | 无运行时、无独立求解器 |
| MAP-08 | ✅ | ✅ 独立诊断求解器 | ✅ 6 局 | E3 为单次、每条件 1 局 |
| MAP-09–15 | ✅ | 纸面/审计 | ❌ | MAP-12–15 有离线审计脚本，但不是运行时 |
| MAP-16 | ✅ | ✅ BFS 最优 | ✅ 6 局 | L2b 未跑真实 API |
| MAP-17 | ✅ | 纸面 Pareto | ❌ | |
| MAP-18 | ✅ | ✅ 构造解（非最优证明） | ✅ 10 局 | 0/10 地板；见 §4 |
| MAP-19–21 | ✅ | 离线审计 | ❌ | |
| MAP-22 | ✅ | ✅ BFS 最短往返 | ✅ 6 局 | L2 双死路未跑 |
| MAP-23–25 | ✅ | 离线审计 | ❌ | |
| MAP-26 | ✅ | ✅ 构造解 + 恢复尾搜索 | ✅ 13 局 | recovery 0/9；见 §4 |
| MAP-27–29 | ✅ | 离线审计 | ❌ | |
| MAP-30 | ✅ | ✅ 构造解 | ✅ 6 局 | 完整调查 0/3、纯召回 1/3 |

> “纸面 Oracle”表示 `oracle_trace.jsonl` 是设计期手算轨迹，不是运行时回放。不能把它说成 E2。
> MAP-12–15、19–21、23–30 的 `planning/` 审计脚本属于 E2 级**设计约束**证据，仍不证明 Agent 行为或运行时确定性。

## 2. 六张运行时地图的真实接口

本节以 `src/agent_arena/worlds/scenario_v4/` 的实现为准，而不是以设计文档为准。

### 2.1 公共 Trace 形状

V6 `agent_trace.jsonl` 每行是一个 JSON 对象：

- 首行 `event=trace_header`：`episode_id, instance_id, map_id, condition_id, seed, scenario_hash, provider, model, agent_visible_only`。
- 之后每行 `event=decision` 或 `event=prefix_action`：`action, result, observation_before, observation_after, invalid_output_reason, decision_index, state_hash_after`。
- `observation_before/after` 是**公开 Observation**；`state_hash_after` 是裁判状态哈希，不进入 Agent 输入。
- 每局另有 `judge_metrics.json`：`status, v4_status, judge_state, metrics, failure_classifications, usage`。

V7 的 extractor 只读这两类文件；找不到的字段返回 `UNAVAILABLE`，绝不补 0。

### 2.2 逐图字段与私有边界

| 地图 | 公开可算字段 | 仅离线裁判可用 | 备注 |
|---|---|---|---|
| MAP-08 | `location, current_tick, current_core_water, published_candidate_set, published_prior, known_test_semantics, sealant_count, test_results, terminal_reason` | `true_leak`（`judge_state`） | 诊断正确率需要真漏；候选缩小/信息增益只需公开签名 |
| MAP-16 | `tick, topology, train_positions, train_goals, pending_route_reservations, segment_capacities, node_capacities, terminal_reason` | 实例 BFS 最优 makespan（冻结表/`judge_metrics`） | 冲突原因在 `result` 中 |
| MAP-18 | `tick, task_passenger_counts, delivered_tasks, canceled_tasks, delivered_passengers, station_berths, closed_segments, published_dispatch_windows, current_train_locks, alert_message_if_any, recovery_status` | `fault_edge, fault_window, fault_enabled` | 延误可由 `delivered_tasks` + 公开计划到达时刻复算 |
| MAP-22 | `movement_steps, current_coarse_silhouette, visible_exit_bearings, inspected_current_sign_detail, active_goal_marker, agent_authored_memory_journal, terminal_reason` | `target_node, complete_adjacency` | 不可用全图拓扑复算路径；只能用公开签名 |
| MAP-26 | `current_tick, current_node, log_readings, test_readings, spare_units_at_B, carried_spare_units, installed_candidates, communication_restored, last_action_result, terminal_reason` | `fault_part` | 诊断正确率需冻结真值；库存/反馈/回滚均可公开复算 |
| MAP-30 | `current_tick, current_node, local_neighbors, visible_local_evidence, recent_action_window, casebook, current_hypothesis, unsupported_formal_accusations, terminal_reason` | 案情真凶、每条目的必需证据集合 | 召回与调查必须分报 |

### 2.3 六图运行时实现状态

- MAP-08：`Map08Environment`，X/Y 测试、唯一密封剂、水位 `>7.0` 失败；默认 B/D/F 候选与 V4 一致。
- MAP-16：`Map16Environment`，原子预约/释放/git commit 式移动、节点与区段容量、死锁检测；组合状态 BFS 可求最小 makespan。
- MAP-18：`Map18Environment`，12 tick horizon、六车、封闭段、站台泊位、取消/折返；构造解可交付 18/18，但**不是最优性证明**。
- MAP-22：`Map22Environment`，12 节点局部标志、合法记忆写入、30 步往返预算；`optimal_moves` 按实例取值（L1=4，L2=4/8，L3=8），不能默认 8。
- MAP-26：`Map26Environment`，三部件、三测试、错误替换反馈（full/structured/hidden）、rollback、备件预算。
- MAP-30：`Map30Environment`，8 节点、四段案卷、NPC 条件回答、compare/accuse、40 tick deadline；L1/L2 是不同案情，召回变体共享 L3 前缀。

## 3. 逐图审计

哈希为 `SHA-256` 前 12 位；完整值见附录 A。状态 `DESIGN_COMPLETE_PENDING_RUNTIME` 只表示设计材料完成，**不表示运行时可回放**。

### 3.1 飞船（MAP-01–03）

**MAP-01｜破损的曙光号｜`dependency_planning`｜spec `6fa24c7950f1`**

- 机制：壳体修补、维修臂与供氧争用同一电池；主母线复位与气闸复核构成前后依赖。
- 公开：位置、相邻边、可见物、氧气储备/输出、供电支路、壳体、主母线、气闸状态、公开目标。
- 私有：未来事件（空）、依赖计数器。
- 参考证据：`oracle_trace.jsonl`（18 tick 手算成功链）、`failure_traces/cases.yaml`、`tests/ACCEPTANCE_CASES.md`。
- 矛盾/缺口：`terminal_success` 含 `bridge_confirmation==complete`，但 `map_spec.actions` 中只有通用 `interact`，确认动作名未在 spec 明示；`oxygen_off_ticks` 不在公开字段，Agent 只能从供氧输出推断。V7 运行时实现前必须以 DCR/实现说明固定“确认”动作与断供计数观测。
- 证据等级：E1 + 纸面 Oracle；无运行时。

**MAP-02｜双重警报｜`event_triggered_replanning`｜spec `810c9ed43de3`**

- 机制：第 4 个有效动作触发泄漏；救人、封存导航核、单向闸门互相牵制。
- 公开：位置、导航核与船员位置、双目标、泄漏状态、泄漏后压力 tick、中央闸门。
- 私有：`private_observation_fields`（设计层）；事件触发点对 Agent 不可预知。
- 参考证据：`oracle_trace.jsonl`、两条手写成功顺序、`failure_traces/cases.yaml`。
- 矛盾/缺口：成功条件 `tick_lte_20` 与“双目标权重”没有在 spec 中给出权重；V7 指标卡必须显式固定“不合并”的双目标明细，且不得把权重写入地图规则。
- 证据等级：E1 + 纸面 Oracle。

**MAP-03｜最后的百步｜`long_horizon_goal_maintenance`｜spec `a8b093b23496`**

- 机制：供电→冷藏→EVA→遥测→航线五阶段；K7/校准码早期只出现一次。
- 公开：位置、里程碑位、EVA 补给、航线窗口、读后样本状态。
- 私有：`private_state` 为空；但早期事实不重复出现，属于“时间上的不可逆可观测性”。
- 参考证据：两条手写成功轨迹（30/31 tick）、三条资源/记忆失败、`oracle_trace.jsonl`。
- 矛盾/缺口：`submit` 是动作名但 `map_spec.actions` 的字段未给出；阶段逆序与“忘记码”需要不同的失败原因码，当前 `terminal_failure` 只列资源/窗口类，记忆失败只能由提交结果推断。
- 证据等级：E1 + 纸面 Oracle。

### 3.2 灯塔（MAP-04–06）

**MAP-04｜潮汐密道｜`periodic_phase_prediction`｜spec `1f654d02be43`**

- 机制：潮位周期决定密道通行；观察、等待、过道机会成本不同。
- 公开：位置、邻居、潮相、周期、`S_G` 可通行相位、灯芯位置、灯状态、救援剩余时间。
- 私有：Oracle 轨迹与计分标签。
- 参考证据：14/15 tick 两条成功轨迹、六种潮相边界、`failure_traces/cases.yaml`。
- 矛盾/缺口：公开字段直接给出 `s_g_open_phases`，因此“从观察推断周期”的预登记对照只能改信息呈现，不能声称纯推理能力；V7 卡必须把两组条件标为信息可用性实验。
- 证据等级：E1 + 纸面 Oracle。

**MAP-05｜三束信号｜`shared_resource_scheduling`｜spec `eb2021067e56`**

- 机制：单路供电、三束信号、校准先后与发射窗口争用。
- 公开：位置、邻居、tick、当前供电目标、局部校准/发射状态。
- 私有：Oracle、失败标签、计分实现。
- 参考证据：两种非支配手写调度（tick 31/29）、三条窗口失败、窗口可行性 DCR（V4 README 记载）。
- 矛盾/缺口：原始窗口曾被手算证明不可行并提交 DCR；任何运行时实现必须引用修订后的窗口，不能沿用原始稿。spec 的 `terminal_failure` 只在窗口结束时判失败，因此“提前放弃”与“窗口错过”需要不同归因。
- 证据等级：E1 + 纸面 Oracle；DCR 待引用。

**MAP-06｜暴风眼｜`value_of_information_and_risk_decision`｜spec `12cfbc8dcb00`**

- 机制：有成本与误差的天气观测；风暴临界区的行动风险。
- 公开：位置、tick、风险点、风险预算、灯状态、先验、预报准确率、观测读数。
- 私有：风暴类型、seed 联合结果表、Oracle、计分实现。
- 参考证据：十 seed 80% 预报、三策略效用（24.9/27.0/27.3）、四条成功分支、三种失败。
- 矛盾/缺口：`risk_points_lte_4` 是硬上限，但“信息价值”需要同一隐藏天气轨迹的配对；固定 seed 重复只是采样重复。V7 卡必须把“可观测/不可观测”作为配对条件，不得把预报准确率写进 Agent 提示。
- 证据等级：E1 + 纸面 Oracle。

### 3.3 深海（MAP-07–09）

**MAP-07｜逆流阀门｜`causal_consequence_prediction`｜spec `b7b9c6716d57`**

- 机制：阀门开闭改变相邻舱压与流向；局部降压可能造成远端升压。
- 公开：tick、各舱水位、可见阀态、泵状态/功耗、低水位连续 tick。
- 私有：Oracle、预测误差标签、计分实现。
- 参考证据：v1→v2→v3→v4 即时级联、tick 6/8 两种成功、三条溢流失败（A/C/B）。
- 矛盾/缺口：地图没有 `nodes` 列表，只有 `hydraulic_nodes/valves`；V7 实现必须读专属结构，不能套 MAP-08 的图结构。成功条件 `A/B/C<=2 且连续低水位>=2` 与“净流量偏差积分”不是同一构念。
- 证据等级：E1 + 纸面 Oracle。

**MAP-08｜看不见的裂缝｜`active_experiment_design`｜spec `1d40008240e7`**

- 机制：隐藏漏点 B/D/F；X/Y 压力测试的确定签名；唯一密封剂。
- 公开：位置、边、tick、水位、候选集、等先验、签名语义、密封剂数、测试结果。
- 私有：`true_leak`、seed 映射、裁判假设标签、Oracle。
- 参考证据：X-first/Y-first 两棵决策树、tick 12 水位 7.0 边界、三条失败、运行时独立求解器（V6）。
- 矛盾/缺口：V6 把默认场景参数化为 4 个实例（2/3 候选、改拓扑），`map_spec.yaml` 仍是单一 V4 场景；V7 指标必须按实例的公开签名计算，不能把 B/D/F 写死。V6 真实结果 6/6 天花板，见 §4。
- 证据等级：E1 + E2 + E3（单次）。

**MAP-09｜深海连锁故障｜`cross_system_causal_control`｜spec `1ebe942cc542`**

- 机制：电力、泵、氧气、通信互相依赖；局部修复可能诱发级联。
- 公开：位置、tick、电池、P/E 舱水位、舱壁、弃舱状态、发电机、氧气储备/支持、稳定 tick、报文完整性。
- 私有：Oracle 标签、计分实现。
- 参考证据：preserve tick 13 与 sacrifice tick 9 两种成功、三条动作级失败、低电发报边界。
- 矛盾/缺口：`water_E>4` 是终止硬线，但公开只给 `water_E`，不给“二次故障传播”计数；故障传播规模需要额外只读 instrumentation，不能暗改规则。
- 证据等级：E1 + 纸面 Oracle。

### 3.4 极地（MAP-10–12）

**MAP-10｜最后一桶燃料｜`multi_purpose_resource_budgeting`｜spec `0186aea149e0`**

- 机制：取暖、通讯、短途运输竞争同一燃料；基地油库与随身燃料分仓。
- 公开：位置、tick、基地油库、随身燃料/容量、基地温度、加热器、发电机。
- 私有：Oracle 标签、计分实现。
- 参考证据：长坡步行 tick10/2 油 vs 雪地车 tick8/3 油、三种供暖/运输失败、燃料守恒审计。
- 矛盾/缺口：`fuel_ledger_invariant` 是资产；V7 卡必须把“燃料消耗=初值−终值+补给”写成账本公式，不能用动作次数估算。
- 证据等级：E1 + 纸面 Oracle。

**MAP-11｜失联的小队｜`risk_strategy`｜spec `9fbaf264987d`**

- 机制：噪声侦察信号、隐藏天气态、Bayesian 后验、短险路与长安全路。
- 公开：位置、tick、补给、体温、队友状态、风暴、后验、短路预报、侦察信号。
- 私有：隐藏 regime、未来风暴 mask、Oracle、计分实现。
- 参考证据：三种计划（快救/侦察分流/背风长路）、解析风险率、十 seed 夹具、补给/冻伤/生命窗失败。
- 矛盾/缺口：公开 `posterior_unstable_probability_belief` 是模型计算值还是地图给出值，需要在运行时说明；若地图直接给后验，则“Bayesian 推理”能力被部分替代。V7 卡按“信息使用”而非“贝叶斯计算”定义主指标。
- 证据等级：E1 + 纸面 Oracle；后验来源待运行时核对。

**MAP-12｜极夜三十天｜`cross_cycle_management`｜spec `8a83689858bf`**

- 机制：30 天库存、供热、温室/科研周期、设备维护、每日 2 动作。
- 公开：日、库存、燃料、供热、控制器、温室、科研、连续欠供天数、劳力槽。
- 私有：Oracle、规划搜索前沿、计分实现。
- 参考证据：`planning/policy_search.py`、有界可行日历、研究优先/安全垫两套 30 日账。
- 矛盾/缺口：设计期只有纸面/搜索重放，没有运行时；`DAILY_ACTION_LIMIT` 与资源结算顺序必须由运行时测试固定，否则长期指标可被结算顺序改变。
- 证据等级：E1 + E2（离线搜索）。

### 3.5 金字塔（MAP-13–15）

**MAP-13｜四神之门｜`constraint_satisfaction`｜spec `634b03e0783a`**

- 机制：四门符号与顺序约束；错误开启重置状态；三次错误上限。
- 公开：tick、位置、线索文本/已记录、试验布局、错误次数、门状态。
- 私有：目标布局、正确性评估器、Oracle、计分实现。
- 参考证据：`constraint_audit.py` 的 24 排列唯一解与逐条删约束必要性（2/5/2/4）、两条 20 tick 成功、三条失败。
- 矛盾/缺口：唯一解由审计脚本证明；V7 的“约束满足比例”必须用独立约束集合计算，不能直接用 `trial_layout==target`，否则退化为通关率。
- 证据等级：E1 + E2（约束审计）。

**MAP-14｜说谎的祭司｜`truth_logic`｜spec `bbf61c4856f9`**

- 机制：三锁型×三真话者的九态真值表；四问码唯一；错误提交两次失败。
- 公开：tick、位置、陈述卡、档案、问答、问询余量、对比记录、错误提交次数。
- 私有：真值表与被封存比对结果。
- 参考证据：`truth_table_audit.py`、自适应最少问、两条 tick 11/8 成功、三条两次错交失败。
- 矛盾/缺口：问询预算与“最少问询差距”需要实例级最优值；审计给出唯一码，但 V7 卡需冻结“最少问”定义（是否允许重复问）。
- 证据等级：E1 + E2（真值表审计）。

**MAP-15｜会变化的迷宫｜`abstract_rule_transfer`｜spec `c642621a45d3`**

- 机制：颜色/奇偶转换规则；同门在不同相位效果不同；失败资源与测试错误上限。
- 公开：区域、tick、奇偶、符号颜色、临时门色、错误资源、测试错误、训练样本、规则假设。
- 私有：无显式 `private_state`；完整规则不在 Observation 中。
- 参考证据：`rule_audit.py`、A/B/C/T 四组布局、两条成功路线、三条失败、两次 Oracle 哈希一致。
- 矛盾/缺口：“未见状态预测正确率”需要 Agent 显式提交预测；当前动作只有 `choose_door`，没有 `predict`。V7 卡把它定义为“首次进入未见组合时的选择正确率”，并明确它不是显式预测。
- 证据等级：E1 + E2（规则审计）。

### 3.6 地铁（MAP-16–18）

**MAP-16｜单线会车｜`deadlock_avoidance`｜spec `387e4dcba46e`**

- 机制：双向列车争用避让站/区段容量；相向交换立即失败；死锁检测。
- 公开：tick、拓扑、方向表、车位置/目标、区段/节点容量、占用节点、待定预约。
- 私有：无 `private_state`；实例目标是公开的。
- 参考证据：`schedule_audit.py`、8 个无碰撞位置状态枚举、6 tick 最优 makespan、三条冲突 + 一条死锁失败、seed0 32 行 Oracle 字节重放。
- 矛盾/缺口：V6 L1 单列车只用于接口定标；不能用 L1 100% 宣称会车能力。V6 真实结果 L1 2/2、L2a/L3 0/4，见 §4。
- 证据等级：E1 + E2 + E3（单次）。

**MAP-17｜早高峰｜`multi_objective_schedule_optimization`｜spec `da028ad6bd76`**

- 机制：环线+支线、4 车、乘客等待与能耗竞争；Pareto 双锚点。
- 公开：tick、剩余时间、拓扑、需求矩阵、车位置/容量、车上乘客、等待需求、已交付、能耗/余量、累计等待。
- 私有：无 `private_state`。
- 参考证据：`schedule_audit.py`、`pareto_reference.json`、两份独立 12 tick 表（等待 16/能耗 11 与等待 38/能耗 8）、互不支配。
- 矛盾/缺口：没有单一成功谓词；V7 不得合成单一总分，必须报告服务率、等待、能耗与支配关系。`map_spec.yaml` 的 `success_predicate` 需在运行时实现时核对。
- 证据等级：E1 + E2（Pareto 审计）。

**MAP-18｜故障传播｜`online_disruption_recovery`｜spec `40a862b1f3d1`**

- 机制：三线六车、三个不同闭塞段、站台泊位、取消/折返、公开预警。
- 公开：tick、剩余时间、拓扑、车位置、泊位、任务乘客数、公开时刻表、已交付/取消、封闭段、锁、预警、恢复状态。
- 私有：`fault_id_until_tick_5`、预期 Oracle 路线、计分参考（部分字段在运行时由 `judge_state` 提供）。
- 参考证据：无故障可行时刻表、等修复与取消折返两类恢复、合法失败前缀、seed0 36 行 Oracle 双哈希一致。
- 矛盾/缺口：**故障不一定约束最优策略**——若列车在 tick 5 前已完成红线任务，闭塞对结果无影响；成功阈值 13/18 也允许取消两条红线任务。V6 0/10 主要是策略/容量失败，但仍不能把 0/10 当成“故障恢复能力为零”的效度证明。V7 卡必须先做“故障是否实际约束最优策略”的离线检查，不满足则提 DCR。
- 证据等级：E1 + E2（构造解）+ E3（10 局，0/10）。

### 3.7 火山（MAP-19–21）

**MAP-19｜温度临界点｜`delayed_thermal_prediction`｜spec `50ee8a132fc0`**

- 机制：两 tick 阀门时滞；温度转移 `max(0,T+load−cooling)`；过量冷却浪费资源。
- 公开：tick、温度带、当前冷却、负荷、待执行冷却、产能/目标。
- 私有：精确温度（只返回当前传感器读数）、预期预测、计分参考。
- 参考证据：`thermal_audit.py`、提前冷却/延迟降载两种策略（28/30 分）、精确 30 分方案、三类热失控、四类边界、seed0 36 行 Oracle 双哈希。
- 矛盾/缺口：公开只给温度带，精确温度是私有；“温度超阈面积”需要运行时提供精确温度或允许按带下界保守计算，二者不可混用。
- 证据等级：E1 + E2（热审计）。

**MAP-20｜冷却网络｜`lossy_water_resource_allocation`｜spec `e35ac16b9e02`**

- 机制：S→A/B/C 限流支管、A-B/B-C 双向旁路、10% 损耗、十分之一整数流量。
- 公开：tick、温度带、负荷模式、上一 tick 流量账、源水余量、产能/目标。
- 私有：精确温度、未来 Oracle 分配、计分参考。
- 参考证据：`flow_audit.py`、`flow_reference.json`、A 区保守/动态轮换（56/59）、15 分方案、72 分线性松弛上界、三类失败、seed0 30 行 Oracle。
- 矛盾/缺口：“平均温度下降但关键节点爆表”的反例必须在指标里显式体现；不能以全网均值作为主指标。
- 证据等级：E1 + E2（流量审计）。

**MAP-21｜喷发倒计时｜`risk_conditioned_stopping`｜spec `eb8eb1f9ae88`**

- 机制：隐藏喷发时刻 12/16/20、有噪测量、样品分级与加固、O-E 六 tick 直撤路。
- 公开：tick、位置/在途边、可走边、测量可用/读数、后验、样本等级、加固包、携带样品。
- 私有：喷发时刻、测量随机抽样、未揭示结果。
- 参考证据：`decision_audit.py`、Bayes 信息增益 0.138 nats、四条路线期望 100/105/112/120、分流策略 112.02 分/存活率 96%、三条失败、tick12 同刻到达边界、seed0 25 行 Oracle。
- 矛盾/缺口：“预警提前量”只对实际发生的事件计算；假阳性不能奖励。公开后验把部分推断交给地图，V7 主指标应以行动风险暴露和撤离覆盖为主。
- 证据等级：E1 + E2（决策审计）。

### 3.8 丛林（MAP-22–24）

**MAP-22｜没有地图的森林｜`topological_memory`｜spec `79b5501b83d0`**

- 机制：12 节点 15 边、局部标志、合法记忆写入、30 步内往返。
- 公开：移动步、粗轮廓、可见出口、当前标志细节、目标标记、Agent 记忆日志。
- 私有：规范节点 ID、完整邻接表、目标已访私有位、未检查标志特征。
- 参考证据：`topology_audit.py`、`graph_reference.json`、A-L 最短唯一往返 8 步、两条节点不相交路、无记忆贪心 J-K 循环、外部记忆 8 步全边巡回 27 条证据卡、完整 DFS 30 步回营、三条失败、seed0 18 行 Oracle。
- 矛盾/缺口：`movement_steps` 是唯一时间量；“重复边率”不能用隐藏全图解码，只能用公开位置签名。V6 L3 首次出现记忆条件方向性差异，但 L1/L2 步数并未更优。
- 证据等级：E1 + E2 + E3（单次）。

**MAP-23｜迷雾中的遗迹｜`exploration_information_value`｜spec `6553f77fa052`**

- 机制：隐藏真入口、成组私有线索、付费侦察、补给约束。
- 公开：当前节点、可见邻居/补给成本、补给余量、侦察站、已收线索、已搜入口、标记候选。
- 私有：variant、真入口、未侦察线索、未揭示入口状态。
- 参考证据：`information_audit.py`、`information_reference.json`、四策略×三变体逐步补给账、信息增益/补给效率、三条失败、真入口正补给边界、seed0 9 行 Oracle。
- 矛盾/缺口：`clues_received` 的“已证实”状态与线索可靠度必须区分；V7 的“线索利用率”只能按已被反证/证实的公开线索计算。
- 证据等级：E1 + E2（信息审计）。

**MAP-24｜消失的道路｜`map_update`｜spec `eacb2d29835b`**

- 机制：tick 8 桥断、局部潮窗相位隐藏、F 慢路常开、抢运/探桥/山路/旧笔记四条路径。
- 公开：tick、节点、局部连接与耗时、可见物、携带物、潮汐读数、探桥结果、路线笔记。
- 私有：桥断 tick、潮相偏移、未来事件日志。
- 参考证据：`map24_audit.py`、`map24_reference.json`、四条手算路径、三类因果失败、桥上与 tick24/25 边界、四相位潮窗、seed0 21 行 Oracle。
- 矛盾/缺口：桥断前若已完成运输，则“重规划延迟”N/A；不能把未触发事件算成 0。潮相偏移是隐藏的，公开只能通过 `measure_tide` 获得局部读数。
- 证据等级：E1 + E2（地图更新审计）。

### 3.9 月球（MAP-25–27）

**MAP-25｜第一次出舱｜`tool_dependency_and_safety_sequence`｜spec `f20327d21585`**

- 机制：气闸/EVA 链、6 类 typed 工具、氧气与绳索前置检查、返舱。
- 公开：tick、节点、氧气、气闸压力、内舱门、服装、绳索、携带工具、可见设备、阵列症状、诊断码、修复状态。
- 私有：隐藏阵列故障、评估 seed、未执行动作结果。
- 参考证据：`map25_audit.py`、两种 tick17/耗氧6 成功顺序、typed 工具 6/6 有效、三条失败、六个氧气/Schema 边界、seed0 36 行 Oracle。
- 矛盾/缺口：`typed_tool_call_validity_rate` 依赖动作 schema 的严格性；V7 主指标应聚焦“必需检查覆盖 + 顺序正确”，不能把 schema 合法率当安全能力。
- 证据等级：E1 + E2（流程审计）。

**MAP-26｜失败的维修计划｜`error_attribution_and_self_correction`｜spec `aecc9f149a8a`**

- 机制：T-D-A-B 链、三部件三测试、错误替换反馈、rollback、两枚备件。
- 公开：tick、节点、日志、测试读数、备件、携带、已装候选、通信、错误码。
- 私有：故障件、seed 映射、未执行测试结果。
- 参考证据：`map26_audit.py`、先诊断 tick11/反馈回滚 tick16 两条成功、盲换/重复同错/忽视测试三类失败、六个边界、seed0 12 行 Oracle；V6 恢复前缀搜索证明存在修复尾。
- 矛盾/缺口：V6 recovery 0/9 全部 `SPARES_EXHAUSTED`，是策略/流程失败；hidden 反馈是信息剥夺条件，不能当作同信息基线。成功还要求剩余备件≥1，因此“修好但耗尽”仍失败，指标必须分开。
- 证据等级：E1 + E2 + E3（13 局，3/13）。

**MAP-27｜月面联合行动｜`long_horizon_tool_and_resource_coordination`｜spec `b31e01f7dff7`**

- 机制：五节点、二格货舱、14 电/18 氧、一次充电、中继/采样/救援依赖。
- 公开：tick、节点、局部道路成本、电池、氧气、货位、补给、充电单元、relay/样本/伤员/船员状态。
- 私有：评估 seed、未执行动作结果。
- 参考证据：`map27_audit.py`、`map27_reference.json`、先修中继 tick25/余电0 与先稳伤员 tick20/余电2 两条成功、三条失败、六个充能/货位/返程边界、seed0 28 行 Oracle。
- 矛盾/缺口：成功允许部分目标？`ALL_OBJECTIVES_COMPLETE` 与 `OBJECTIVES_INCOMPLETE_AT_BASE` 需要明确“部分完成”的记分；V7 卡把它拆成协同完成率与关键路径，不合成单分。
- 证据等级：E1 + E2（协同审计）。

### 3.10 古堡（MAP-28–30）

**MAP-28｜消失的王冠｜`cross_source_evidence_integration`｜spec `d75b3643587b`**

- 机制：H-V-G-K-S-V 环路 + A 档案支线、四类证据来源、每条主张需双来源。
- 公开：tick、节点、邻居、警报、已观察证据、已记录证据 ID、结果。
- 私有：真凶、真实路径、精确进出时间、未观察证据、替代最终主张结果。
- 参考证据：`map28_audit.py`、`map28_reference.json`、Celine 与 S-V 的 21:06/21:14 唯一真相证明、先物证/先证词两条 tick20 成功、三条终局失败、六个边界、seed0 21 行 Oracle。
- 矛盾/缺口：`observed_evidence` 与 `recorded_evidence_ids` 是两种状态；V7 的“已证实关键证据覆盖”只能计已记录且被来源支持的事实，不能计“看见过”。
- 证据等级：E1 + E2（证据审计）。

**MAP-29｜不可靠的证人｜`active_question_selection_and_source_assessment`｜spec `3c2e67f37b5d`**

- 机制：证人偏见/矛盾、有限问询、物证与证词交叉、单一证人不可信。
- 公开：tick、节点、邻居、警报、问询余量/已用、听到的回答与来源、已见物证、对比结果。
- 私有：真实事件时间/地点、NPC 知识表、偏见参数、未问答案、可靠性裁决。
- 参考证据：`map29_audit.py`、`map29_reference.json`、唯一真相与偏差校准、结构化问询模板、两条成功、三条失败、seed0 手工轨迹。
- 矛盾/缺口：V7 的“矛盾识别率”需要植入矛盾清单（私有裁判数据）；公开回答可能互相一致但被物证推翻，这正是手工验收焦点。
- 证据等级：E1 + E2（证词审计）。

**MAP-30｜午夜审判｜`long_horizon_evidence_memory_and_cautious_decision`｜spec `3913ca2f2898`**

- 机制：三起相关案件、Q4 编码/人物身份早期出现、案卷记录、40 tick deadline、两次无据指控上限。
- 公开：tick、节点、邻居、局部证据、最近动作窗口、案卷、当前假设、无据指控数、结果。
- 私有：真凶、案情真值、未解锁证据、seed 重放。
- 参考证据：`map30_audit.py`、`map30_reference.json`、`seed_replay.yaml`、三条案件（L1 2 事件/L2 3 事件/L3 原案）、纯召回变体（固定前缀 + 一步提交）、完整调查与召回分开报告。
- 矛盾/缺口：**完整调查 0/3 是流程/可玩性地板，不是记忆结论**；纯召回 1/3 才是记忆条件的方向性证据。`history_full` 在 V5 为 3/3、V6 为 0/3，属单局噪声。V7 卡必须把“已解锁身份映射”的公平可见性写清楚。
- 证据等级：E1 + E2 + E3（6 局，1/6）。

## 4. V6 特殊结果复核（不得外推为 30 图效度）

| 现象 | 证据 | V7 解读 |
|---|---|---|
| MAP-08 6/6 天花板 | 3 实例 × 2 条件，单次 | 对当前模型过易；不能证明 MAP-08 无区分度，只能说明该模型+该实例集已饱和 |
| MAP-16 L1 2/2 vs L2/L3 0/4 | 单次 | 接口定标与完整会车必须分报；L1 的 100% 不是会车能力 |
| MAP-18 0/10 地板 | 含无故障 L1、三个封闭段、预警开/关 | 服务率 0–0.33；失败为容量/碰撞/截尾，非 schema；**故障是否约束最优策略仍未证明** |
| MAP-22 L3 条件差异 | history5 52 决策截尾 vs graph_memory 15 决策成功 | 单局方向性证据；L1/L2 记忆条件不快，不能称稳定记忆效应 |
| MAP-26 free 3/4、recovery 0/9 | 恢复全 `SPARES_EXHAUSTED` | 自由诊断近天花板、恢复地板；hidden 是信息剥夺下限 |
| MAP-30 完整调查 0/3、纯召回 1/3 | 完整调查 0 案卷条目 | 调查流程地板 ≠ 记忆能力；召回条件与完整调查必须分开 |

## 5. 冲突与待人工确认清单

1. **MAP-01**：`bridge_confirmation` 的确认动作/观测语义未在 spec 明示；运行时实现前需确认。
2. **MAP-02**：双目标权重未定义；V7 不合成加权总分，只报明细。
3. **MAP-03**：记忆失败与资源失败缺少独立原因码；V7 用“保留码却漏阶段”和“阶段全过但码错”两条轨迹区分。
4. **MAP-05**：原始窗口不可行，已有手算 DCR；引用修订窗口前不得实现。
5. **MAP-06/11/21**：公开后验/预报字段可能替代部分推理；实验条件必须标“信息可用性”，不能称纯能力提升。
6. **MAP-07/09**：故障传播/级联规模需要额外只读 instrumentation，不可改规则。
7. **MAP-12**：日结算顺序未运行时固定；长期指标对顺序敏感。
8. **MAP-15**：没有显式 `predict` 动作；“未见状态预测正确率”只能用首次选择代理。
9. **MAP-18**：故障载荷依赖发车时点；需离线证明“故障实际约束最优策略”，否则 DCR。
10. **MAP-19/20**：精确温度是私有，公开只有温度带；面积类指标必须声明用的是精确值还是带下界。
11. **MAP-22**：`optimal_moves` 必须按实例取，不能默认 8；重复边只能用公开签名。
12. **MAP-24/25**：隐藏相位/故障的公开读数边界需在运行时确认。
13. **MAP-27**：部分完成是否算成功未明确；V7 拆分为完成率与关键路径。
14. **MAP-30**：完整调查与纯召回必须分报；`history_full` 的 V5/V6 冲突是单局噪声，不构成结论。

以上 14 项中，第 1、2、3、5、6、7、8、9、10、11、13 项进入 V7 设计卡与 `design-change-requests.md` 的待决清单；第 4 项引用既有 DCR；第 12、14 项在运行时接入前保持 `pending_human_review`。

## 6. 本轮不做什么

- 不覆盖、不重写任何 V2/V4/V5/V6 的 Oracle、设计文档、账本、注册表或原始 trace。
- 不实现 24 张设计图的运行时，不伪造 24 图实测。
- 不调用付费 API，不新建预算账本。
- 不修改 V4 规则；发现规则冲突先写 DCR。
- 不把 `DESIGN_COMPLETE_PENDING_RUNTIME` 解释为 runtime validated。
- 所有地图的 `review_status` 保持 `pending_human_review`；DeepSeek 只做 `self_review` 与 `second_pass_check`。

## 附录 A：完整规则哈希

| 地图 | `map_spec.yaml` SHA-256 | `DESIGN.md` SHA-256 |
|---|---|---|
| MAP-01 | `6fa24c7950f14e8086db97b5a877ba61b7bd88c876c54162a95e8b73c48fe3b3` | `66da1da5ed6fb68209860209c6520fa3539edbeadb5b029608e717dace1f6ee6` |
| MAP-02 | `810c9ed43de3745c7c02d3aa82f5145140b6697aa00f1902d03161724f67673e` | `4bdb831631fb858e71c4b405a6a48cc4ed877d81a17436716ab6a24fd42f56d0` |
| MAP-03 | `a8b093b23496cd108f60d57b47e1ee9991c52465b89feab68cae86028b9258c8` | `0698f1a023ed30503fef20b4e6ec7875ce15cce84ffb12f520673e26db55be21` |
| MAP-04 | `1f654d02be43dbf14b40d00e250d3a371ec3287eb560d97d743456ae8837c3a6` | `c955b65efa50a3e5d5b4c4dfdd30649446bf70abf30ba5b738d121df0a097724` |
| MAP-05 | `eb2021067e56a3211d3e0ae747583acb8faf6bbe8e0ffbb4ba716cea1d34ed5e` | `7dcd822757c73b542840521430d5068acdf4d4e3dd9bb429504eca524077c3d5` |
| MAP-06 | `12cfbc8dcb00b68ece4abd3bdbddcd4e6ab56639d0e6923e82cbdcae493951d4` | `649ae0a3b73459df930f46a2a73892bbcc9fdb5bfa2804956b60203eefc3b4b0` |
| MAP-07 | `b7b9c6716d57f34ebb5e1512465290a308b1cf14892ec807b0369eb04842105d` | `f2ec9e0092d138bc8252090f153db9ea992775cf1ca5599de5ecd57f35ef5086` |
| MAP-08 | `1d40008240e719d1af0c7189a9456dcc313ce0c9e2e136d49e56665f197dab8d` | `9c7cc3ef4445bc80ee19942196a5964ea01d4b15c1ba0a5c89c517619dad90b4` |
| MAP-09 | `1ebe942cc5423c031c5c65b32b6efb48c7c5b1a1d0069031c3e737cd5c35d2bf` | `8aafad5f9ed9c5d6191c7835735a2b19c5c9c78c0c841ad391876354af6aa5de` |
| MAP-10 | `0186aea149e03e93b50db10440d2735cf31e07b06050d4e4958d64761d8b57a0` | `a33287e546ae085db6ff436b06f04366959a2c6f8fc9ec19905e4d0bd6b000b5` |
| MAP-11 | `9fbaf264987d57bb388b00181ed1da96feb9bbf9d6dde45b6754d3f08cb08401` | `97bd1182126cecb7e5152eab0883d2bd52b30bb8fe08c0dd7d335c6d6cba4fae` |
| MAP-12 | `8a83689858bfd57a5a00da8c7733fcd678e1d2f9fa29aeaa9461bb36a6081483` | `e4cfff1ad7bd9882c1d69292700249205275009c260c4d5980bae050666f5764` |
| MAP-13 | `634b03e0783ac226188286af0de54e9c964c78ee8358dd2e38a7b65e2f9bc654` | `50fe696e371eb535676161cab4131e8cad0ded293941c8849609b54fd5e02817` |
| MAP-14 | `bbf61c4856f98d1a6e4dd623239ea5c364e2a71f7a7394e6fad4eb20c3148543` | `112ee6690ab21bdd4cdc8399e5818d8e73cbb7065afabfe40a2b8eabe2c057ab` |
| MAP-15 | `c642621a45d3de9a1c4b31f25d032abc06dcd1376c541e5085d4e0baca9b3f2a` | `b44f851e2e79f976f8a1831dc876c1350b9aa66b41e32c25cd2d9997b73cb263` |
| MAP-16 | `387e4dcba46e38acfbad5044644cbd1bcf1c22ae033123e423b15825f59b1389` | `aa8ef5365fe8a11de4d9f51e846ca593be6499f7f5d623f15687d898b0fc6f09` |
| MAP-17 | `da028ad6bd76a751b9cfacf0c13a2b7cdada0d697d19fa604c6d01ce1e4fa339` | `259ab66b150fcbc42b174ba6e006aa859b5fbccfabde6312df51e52bafb3f978` |
| MAP-18 | `40a862b1f3d1eb06ebca99049272f9d5071d49b88a7de76ddc65826f142e7985` | `009b29912cc021278bf0fe415ffd31bc4ca9ee12c9940ed969b0bca0b258ebe5` |
| MAP-19 | `50ee8a132fc079b1f8f09cba0b508a901d5a948078af5f0b1ca72dcdcfc94bf1` | `9883b7e893339d853261dc664c61ccb27b86296927962e129084e2d5d65e3b43` |
| MAP-20 | `e35ac16b9e02881753f19a39438eafd5da2d38b6432c4c8f16bdd3679d51797e` | `6c306808efd61d0b11f4dda5aafc0eb999b8c733d4325d38d16091e8aaf159c8` |
| MAP-21 | `eb8eb1f9ae8846fc57884f4850f99fb0ae19383368f832794074b1e4e4049aee` | `f24289ecbad95b18d3770013106d63e07cd4cf7b3533a25b66d59f4085af461e` |
| MAP-22 | `79b5501b83d09858a80a1d7a89ca96080440e1a121885125311d27cfd3c93c36` | `a228b2cc8418fe2701be00e8565d9c889b7f522d936efd675e37f120cfdd791b` |
| MAP-23 | `6553f77fa05248f995615ff1cd0dd47b5399d2ec02c59f6d6e8e68120aaec952` | `ee791a8edff4f2ecb2e47b331fbaaa43ec9478287a11ad09a4b503fbfbeea8f9` |
| MAP-24 | `eacb2d29835b0bd0c0ee95c25f5b77ae40315b5d51bda7bf10c5bc276b1d32e6` | `2c788c3f6b491c3ade654cb5bd02c4d591c7d2a1521924b04e5bbffd741cf15f` |
| MAP-25 | `f20327d215855561de9a7bafe075ca530e99724d83a79622bd1d97556f076b57` | `533bd978e29b6c89122177f9694eb61cec1c7cfb01f08897c73e9a4205cb07b9` |
| MAP-26 | `aecc9f149a8afeddff968549599058f3bb54dfdad38d806bd9483292771b5b81` | `193fdc2cb074e99017757e9170254d4f006d154edd810b690dc41968aa1046ae` |
| MAP-27 | `b31e01f7dff799262c3aa6ae3e1902d44d7b1de40ba2adcf0111d2bb2d4d3c09` | `dd3dd1dbf97c713e6b8cd9d43a01a341ce8b4f83e562f7310247ce951804a266` |
| MAP-28 | `d75b3643587b4301ff7f5f3873f8cf16d0e8a523498139521e5f49bdaa9e99f4` | `cba4a5035a7a6fa9e866a416c73150be5f940334ca698decabdb47ff9fb21a2e` |
| MAP-29 | `3c2e67f37b5de11bf388e476d78634bdee4b5b670bf5db759b82d74af9e6e378` | `c59ac4582d0743486b5cc9fc6f81527ca6ee93c3ede1728bce868fbb11d5cec4` |
| MAP-30 | `3913ca2f2898cb3278ac413bc574ae08454dfe2c379085cefc40ad90fbc58388` | `9fa618228569778e1bb06006377baa8c2b517e8f0919a18a9be5e5a74a20d11b` |
