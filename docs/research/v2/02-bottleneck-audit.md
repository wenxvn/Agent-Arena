# V2-02 既有 Trace 离线瓶颈审计

## 范围与方法

- 审计日期：2026-10-13（Asia/Shanghai）；审计代码提交：a372dce9f9e904db31907dc283629bd0b37e6d03。
- 离线命令：python scripts/audit_v2_traces.py --runs-dir runs --results-dir results。脚本仅使用 Python 标准库。
- 可复现性复核：2026-10-13 在独立临时目录重跑同一审计；518 个文件、474 个唯一 episode、44 个副本、0 个冲突/不可读/非法 Trace，outcome 计数不变；生成的 CSV 与 JSON 均与下方已提交产物字节级一致。
- 输入仅为本机 runs/ 与 results/ 下的 episode JSON。审计未调用模型、未启动 GPU；分析代码没有检查或输出完整 decision_reason。
- 产物：[逐 episode 审计 CSV](assets/trace-audit.csv) 与[条件汇总 JSON](assets/trace-audit.json)。CSV 使用字段 allowlist；不含 decision_reason、模型思维链、密钥或完整 provider 响应。原始 trace 继续留在本地生成目录。

## 数据完整性与总体边界

| 项目 | 数量或结论 |
|---|---:|
| 扫描文件 | 518 |
| 唯一 episode_id | 474 |
| 去重的副本 | 44 |
| 同 ID 内容冲突 | 0 |
| 不可读 / 非法 Trace | 0 / 0 |
| 条件汇总组 | 92 |

474 个唯一 episode_id 对应的 outcome 计数为：success 262、step_limit 76、provider_error 135、invalid_action_limit 1。它们混合了不同地图、配置、prompt 和重跑，不能压成一个有代表性的全局成功率。provider_error 是基础设施删失，不应当写成行为失败；step_limit 仅说明该次记录在上限处结束。

### 地图家族与 seed 角色

seed_role 的操作性规则是：world_version 含 seeded 时标为 seeded_instance，否则标为 replicate_id。后者是固定定义地图上的重复标识，不是独立环境实例哈希。表中每个地图家族包含多个 world_version 和配置，因此仅作覆盖盘点，不作配置间比较。

| 家族 | replicate_id：记录数（成功 / step_limit / provider_error / invalid） | seeded_instance：记录数（成功） | 观测到的最长成功动作数（replicate / seeded） |
|---|---:|---:|---:|
| 深海站 | 33（32 / 0 / 1 / 0） | — | 168 / — |
| 古堡 | 36（20 / 0 / 16 / 0） | 5（5） | 69 / 54 |
| 丛林 | 31（15 / 0 / 16 / 0） | — | 53 / — |
| 灯塔 | 50（36 / 5 / 9 / 0） | — | 261 / — |
| 月球 | 35（20 / 0 / 15 / 0） | 5（5） | 50 / 232 |
| 极地 | 32（17 / 0 / 15 / 0） | — | 51 / — |
| 金字塔 | 36（20 / 0 / 16 / 0） | 5（5） | 51 / 159 |
| 飞船 | 138（49 / 71 / 17 / 1） | 8（8） | 440 / 57 |
| 地铁 | 30（15 / 0 / 15 / 0） | — | 50 / — |
| 火山 | 30（15 / 0 / 15 / 0） | — | 37 / — |

这些家族汇总仍然混有不同地图版本和运行配置。最长成功动作数是各家族已记录成功 trace 的上界样本，不代表固定条件的效率差异。代表长尾 trace 路径见下方样本表和 CSV。

### 首次尝试与 Success@K

没有 run-attempt ID，无法确认调用级首次尝试。脚本按实验目录、配置签名和 seed 对 episode 按 created_at 排序，只能选择“最早记录”。这 339 条代理记录的 outcome 是 success 144、provider_error 127、step_limit 67、invalid_action_limit 1；这些数字不能当作首次尝试率，也不能补写到历史实验的首跑统计。

离线 Success@K 按 30、60、100、150、200 个 recorded actions 分别计算，产物按实验目录、world_version 和配置签名分组。success 且动作数不大于 K 才计成功；provider_error 从分母删失；已知 step_limit 小于 K 的记录也从该 K 的分母删失。其他 outcome 留在分母作为未成功记录。该口径只描述现有 trace 在不同预算截点的结果，不代表重新运行。

实例标识也有限：Trace 没有独立 instance_hash。seeded 条目暂用 world_version、definition_hash 和 seed 派生 effective_instance_signature；非 seeded 条目不把 replicate seed 当成环境实例身份。该签名不是地图内容哈希。后续 S1.3 补充仅对静态地图使用 `(world_version, world_definition_id, world_definition_hash)` 精确匹配 spec 路径参考；seeded 与 hash 不匹配的成功记录不补算，且旧 Trace 未记录环境规则代码 SHA，不能由 map hash 证明历史规则实现完全相同。

## 可观察行为概况

| 指标 | 全部 474 个唯一 episode |
|---|---:|
| 提供 progress 字段的动作 | 17,741 |
| progress=false | 6,323（占提供 progress 的 35.6%）|
| look 在同一地点重复且 progress=false | 2,429 |
| 公开位置序列中的二边往返代理 | 628 |
| 完全相同 action + rejection reason 再次出现 | 229 |
| code_read 事件 | 862，其中首读后的重复读 535 |
| wrong-target read_terminal | 74 |
| code 读出后的 move/look | 5,128 |

动作/token 覆盖也不完整：474 条中 461 条有 input_tokens 和 output_tokens；14 条有 planner token 字段。可加总字段分别是 executor input 26,608,895、output 12,453,363、planner input 44,916、planner output 161,227。配置和模型混杂，不能将这些总数解释成某个方法的成本。

两个高频 prompt hash 的记录并非匹配对照：

| prompt hash 前缀 | episode 数 | progress=false / progress 字段动作 | 二边往返 | 重复 code_read | wrong-target terminal | 重复失败动作 | use wrong_target / missing_item |
|---|---:|---:|---:|---:|---:|---:|---:|
| 44229085 | 313 | 2,543 / 8,339（30.5%） | 172 | 20 | 0 | 28 | 13 / 20 |
| 5dc2038b | 141 | 3,627 / 8,902（40.7%） | 353 | 506 | 74 | 135 | 10 / 0 |
| 265010e0 | 20 | 153 / 500（30.6%） | 103 | 9 | 0 | 66 | 0 / 5 |

hash 同时混合地图、配置、prompt 周边设置与运行批次。表中数值只能描述各 cohort 的记录，不能归因于 prompt 单项变化。

## 每个世界家族的长尾成功样本

下表为每个家族已记录成功 trace 中动作数最大的样本，便于逐步复核。成功样本不是行为失败；provider_error 不参与这张表，也不当作失败案例。

| 家族 | 动作数 | `world_version` | `world_definition_id` / seed 角色 | 本地 trace 相对路径 |
|---|---:|---|---|---|
| 深海站 | 168 | abyss-escape-hard-zh | abyss_escape_hard / replicate_id | runs/muse-9maps-abyss-hard/episode_20261011T074539Z_memory_seed-2_dbad0ed7.json |
| 古堡 | 69 | castle-escape-hard-zh | castle_escape_hard / replicate_id | runs/muse-21maps-castle-hard/episode_20261011T131606Z_memory_seed-0_8f807e05.json |
| 丛林 | 53 | jungle-escape-hard-zh | jungle_escape_hard / replicate_id | runs/muse-21maps-jungle-hard/episode_20261011T131206Z_memory_seed-2_da140ef7.json |
| 灯塔 | 261 | lighthouse-escape-v3-zh | lighthouse_escape_v3 / replicate_id | runs/muse-9maps-light-hard/episode_20261011T074453Z_memory_seed-1_fa596cf4.json |
| 月球 | 232 | lunar-escape-v2-seeded-zh | lunar_escape_v2_seeded / seeded_instance | runs/muse-flex-lunar-v2s/episode_20261011T142412Z_memory_seed-1_30323f7d.json |
| 极地 | 51 | polar-escape-hard-zh | polar_escape_hard / replicate_id | runs/muse-21maps-polar-hard/episode_20261011T130327Z_memory_seed-2_71be5ad2.json |
| 金字塔 | 159 | pyramid-escape-v2-seeded-zh | pyramid_escape_v2_seeded / seeded_instance | runs/muse-flex-pyramid-v2s/episode_20261011T142750Z_memory_seed-2_e46fe34f.json |
| 飞船 | 440 | spaceship-escape-v4-zh | spaceship_escape_v3 / replicate_id | runs/muse-9maps-ship-hard/episode_20261011T074451Z_memory_seed-3_ae173aea.json |
| 地铁 | 50 | subway-escape-hard-zh | subway_escape_hard / replicate_id | runs/muse-21maps-subway-hard/episode_20261011T130725Z_memory_seed-2_33208099.json |
| 火山 | 37 | volcano-escape-v1-zh | volcano_escape_v1 / replicate_id | runs/muse-21maps-volcano-med/episode_20261011T130905Z_memory_seed-3_3b175310.json |

## S1.3 可计算指标补充：分层分布与公开里程碑

从逐 episode 审计 CSV 生成[条件分布 CSV](assets/condition-distributions.csv)：

```powershell
python scripts/summarize_v2_distributions.py
```

该脚本只读 `trace-audit.csv`，以 `experiment_bucket`、`world_version`、`configuration_signature` 分组；不读取原始 Trace 或 `decision_reason`。成功动作数、成功 Trace executor token 数与延迟分别输出 n、P50、P75、P90、max；P50 使用中位数，P75/P90 使用 `int(p * (n - 1) + 0.5)` 最近索引规则，以保持与既有 P90 算法一致。CSV 共 92 个条件、474 条记录、262 条成功；每组数据仍可能很小或来自不同运行批次，不应用于未经匹配的条件优劣比较。

把全部成功样本合并仅作总体描述时，动作数 P50/P75/P90/max 为 37/48/69/440。该混合分布不能代表单一配置、地图或模型。所有 262 条成功记录都有 executor input/output token 对和 latency；成功记录的 planner token 覆盖为 0/262，因而无法由这些记录估算成功局 Planner 成本。`known_executor_tokens_per_recorded_success` 只将有 token 记录的尝试加总后除以已记录成功数；provider-error 等删失记录可能缺少 usage，因此该值只能视为观测下界，不是 provider 确认账单或有效的配置成本比较。各条件内的 token 与 latency 分布见 CSV。

公开任务里程碑均出现在 262 条成功 Trace 中：252 条顺序为 panel→power→code→escape，10 条为 code→panel→power→escape。按公开事件 step 差计算的跨条件区间如下；它们是相邻已记录事件的动作步数差，不是模型内部的阶段耗时。

| 公开事件间隔 | n | P50 | P75 | P90 | max | 反序记录 |
|---|---:|---:|---:|---:|---:|---:|
| panel→power | 262 | 2 | 3 | 4 | 204 | 0 |
| power→code | 252 | 5 | 7 | 13 | 49 | 10（code 先于 power，未纳入正向间隔分位数）|
| code→escape | 262 | 6.5 | 10 | 33 | 408 | 0 |

同样，这些跨条件总体数仅作旧记录描述，不证明某阶段机制导致长尾。下方的 spec 路径比值有独立的精确 identity join 和条件分层；token 缺失和 provider-error 删失不补零、不推算为真实成本。

### Spec 最短公开路径参考比值

原始提纲 S1.3 要求在 oracle 与地图版本匹配时计算 `actual actions / reference shortest actions`。接受的 [spec 0011](../specs/0011-seven-worlds/index.md)、[spec 0012](../specs/0012-flex-pilots/index.md)、[spec 0013](../specs/0013-redesign-old-worlds/index.md) 为 42 个固定地图 selector 记录了最短公开路径步数。新增脚本以当前 `create_environment(...).identity` 生成地图 identity，再按 Trace 的 `world_version`、`world_definition_id`、`world_definition_hash` 三元组做精确匹配；只有成功 outcome 才计算比值和多用动作数：

```powershell
python scripts/audit_v2_oracle_ratios.py
```

可复算逐 episode 结果见[参考路径比值明细](assets/oracle-optimality-traces.csv)，按 `experiment_bucket`、地图 identity 和 `configuration_signature` 分组的 P50/P75/P90/max 见[条件汇总](assets/oracle-optimality-conditions.csv)。474 条审计记录中 439 条匹配到登记的静态地图 identity；227/262 条成功 trace 获得精确参考路径匹配，分布在 50 个条件。另 35 条成功 trace 不计算：seeded 飞船 8 条、lunar v2 5 条、lunar seeded 5 条、castle v2 5 条、castle seeded 5 条、pyramid v2 2 条、pyramid seeded 5 条；它们没有与登记参考同时满足精确 hash 匹配。

在 227 条已匹配成功 trace 的跨地图混合描述中，`actions / spec_reference_min` 的 P50/P75/P90/max 为 2.05/2.43/3.80/20.95；超出参考步数的动作数为 17/29/48/419。所有匹配样本均不低于 spec 声明步数。按来源 spec 计，0011 有 107 条、0012 有 75 条、0013 有 45 条。上述混合分布不能解释为单一地图或配置的效率，也不能作为方法间因果比较。

术语边界：报告称其为“spec 声明最短路径参考比值”，因为 spec 将这些动作序列标为最优且验收了精确步数，但本次没有独立求解器重新证明全局最短；Trace 也未保存环境规则代码 SHA。因此这些数值补足了可匹配样本的 S1.3 描述，但不是对历史运行环境规则实现的独立证明。未匹配样本继续标为 unavailable，不将其差值填零。

## S1.4 逐世界家族案例复核

按未跟踪原始提纲的 S1.4，对 10 个世界家族各选一条最短已记录成功和一条已登记的长尾成功；异常样本优先选 `invalid_action_limit` / `step_limit`，若该家族没有这两类，则选动作数最多的 `provider_error` 并明确标为基础设施删失。短/长样本的地图难度、`world_version`、实例或条件可能不同，只用于逐步案例审阅，不构成效率或机制对照。精确 episode ID、相对路径、配置/地图身份和可观察指标见[案例索引 CSV](assets/trace-case-review.csv)。

| 家族 | 最短成功（动作 / `world_version`） | 长尾成功（动作 / `world_version`） | 非成功 outcome 计数（`provider_error` / `step_limit` / `invalid_action_limit`） |
|---|---|---|---:|
| 深海站 | 19 / abyss-escape-easy-zh | 168 / abyss-escape-hard-zh | 1 / 0 / 0 |
| 古堡 | 22 / castle-escape-easy-zh | 69 / castle-escape-hard-zh | 16 / 0 / 0 |
| 丛林 | 22 / jungle-escape-easy-zh | 53 / jungle-escape-hard-zh | 16 / 0 / 0 |
| 灯塔 | 21 / lighthouse-escape-v4-zh | 261 / lighthouse-escape-v3-zh | 9 / 5 / 0 |
| 月球 | 21 / lunar-escape-easy-zh | 232 / lunar-escape-v2-seeded-zh | 15 / 0 / 0 |
| 极地 | 17 / polar-escape-easy-zh | 51 / polar-escape-hard-zh | 15 / 0 / 0 |
| 金字塔 | 18 / pyramid-escape-easy-zh | 159 / pyramid-escape-v2-seeded-zh | 16 / 0 / 0 |
| 飞船 | 28 / spaceship-escape-v2-zh | 440 / spaceship-escape-v4-zh | 17 / 71 / 1 |
| 地铁 | 20 / subway-escape-easy-zh | 50 / subway-escape-hard-zh | 15 / 0 / 0 |
| 火山 | 19 / volcano-escape-easy-zh | 37 / volcano-escape-v1-zh | 15 / 0 / 0 |

逐步复核只使用 `Observation`、实际 `Action`、公开 `ToolResult` 和公开 progress 字段，不读取或导出 `decision_reason`。长尾样本的可复核事件包括：深海站在 panel/power/code 的 step 22/24/46 后到 step 168 才逃出，期间 5 次 wrong-target、4 次重复读码和 14 个导航二循环；灯塔相应事件在 step 27/29/33，step 261 才逃出，观察到 6 次 wrong-target、23 次重复读码和 173 个读码后的 move/look；飞船事件在 step 24/26/32，首次 wrong-target 在 code_read 之前的 step 12，随后 52 次重复读码、330 个读码后的 move/look，step 440 逃出。月球 seeded 样本在 step 17 打开 panel，到 step 221 才恢复供电、step 226 读码，记录到 41 次重复 look 和 42 个二边往返代理；金字塔 seeded 样本先在 step 8 读码，step 155/157 才打开 panel/恢复供电，step 159 逃出，记录到 18 个二边往返代理。对精确 identity 匹配的三条固定图长尾样本，spec 声明路径参考比值分别为：深海站困难 168/21=8.00（多 147 步）、灯塔 v3 困难 261/20=13.05（多 241 步）、飞船 v4 困难 440/21=20.95（多 419 步）。月球、金字塔 seeded 样本无精确参考 hash，不计算比值。这些都是已观察到的成功长尾，不证明当时可避免或由记忆遗忘导致。

其余长尾案例在该条 trace 中没有 wrong-target terminal 或重复读码；古堡与极地各有一次相同失败动作/理由重复。灯塔有 5 条 `step_limit`，飞船有 71 条 `step_limit` 和 1 条 `invalid_action_limit`；其余 8 个家族在当前 474 个唯一 episode 中没有记录这两类行为 outcome。135 条 `provider_error` 跨家族单列为基础设施删失，不作行为失败。案例索引为每个家族保留了一条异常记录：8 个家族为 provider-error 删失样本，灯塔为 step-limit，飞船另含 step-limit 与 invalid-action-limit。

Trace 能回答的是公开输入/已执行动作/工具结果序列，不能回答内部记忆事实、阶段判断或未选动作候选：474 条 Trace 中 `memory_statistics` 为 0；所选成功案例没有非空的 `current_subgoal`、`suggested_action` 或 `planner_feedback`。422/474 条 Trace 的 `public_phase_context_enabled` 为 true，但开关值不是模型的阶段判断记录。因此「忘记事实」与「阶段推断错误」仍是待检验假设；该数据不足以作认知根因结论，也不能当作 P1 自主 Phase 证据。

## Top 5 可检验瓶颈

### 1. Seeded 地图出现长距离边往返

- 证据：月球 seeded trace 共 232 个动作、成功；depot_store→telemetry_nook 与反向各出现 41 次，导航二边往返代理计数 42。step 221 恢复供电、226 读取密码、232 逃出。金字塔 seeded trace 共 159 个动作、成功；relic_store→sand_tunnel 与反向各出现 26 次，读码在 step 8，step 157 才恢复供电，159 逃出。
- 影响：成功被保留，但分别消耗 82 和 52 次在同一边对上的移动；不能把长 trace 直接称为失败，也不能跨配置比较总步数。
- 可证伪假设 M1：在冻结的 E1 + H5 / recovery / phase 条件下加入房间、双向边、未探索出口和公开里程碑的结构化记忆；在预先固定的 seeded 月球/金字塔实例上，重复二边往返次数相对基线下降至少 20%，且 Success@100 不下降。若只减少 look 而不减少边往返，或 Success@100 下降，假设不成立。

### 2. 旧 prompt cohort 有终端目标混淆和读码后重复

- 证据：5dc2038b cohort 的 141 条记录中有 74 次 wrong-target read_terminal 和 506 次首读后的重复 code_read。440 步飞船成功 trace 在 step 12 与 439 错读终端，step 40 开始重复读码，step 440 才逃出。44229085 cohort 的 313 条记录中 wrong-target terminal 为 0、重复 code_read 为 20。
- 影响：后一个 cohort 的表象明显少，但条件未匹配，不能据此声称 prompt 变化造成改善。V1 中 E1 的受控结果仍是小样本历史证据，不与本次混合 trace 合并成 V2 结论。
- 可证伪假设：在冻结相同地图、seed 和预算时，将“code 已读取”与“可读终端”作为不同公开 affordance 状态；若 E1 基线下 wrong-target 和已知 code 重读仍不下降，阶段提示不够；若基线已经为零，则不把这项列为本轮主要收益。

### 3. use(item, target) 的工具/目标配对仍有拒绝

- 证据：44229085 cohort 有 13 次 use:wrong_target、20 次 use:missing_item。月球 seeded trace step 19 将 core_cell_b 用于 main_cell，step 31 将 torque_driver 用于 aux_panel；两次均收到 missing_item。它们不是“背包为空”，而是物品与目标所需工具的配对不符。
- 影响：需要改进动作候选与可见 affordance 对齐；不能把所有 missing_item 一概判成记忆遗忘，因为库存变化和前置条件仍重要。
- 可证伪假设：只向 Agent 提供可从当前 Observation 推导的可用对象/工具配对提示，在冻结实例上比较 use 拒绝数与 Success@100；若拒绝数没有下降，或 Success@100 变差，提示机制无效。不得把隐藏 WorldState 或地图私有 repair 配置注入 Agent。

### 4. 相同失败动作会在相同拒绝理由后重复

- 证据：所有混合记录累计 229 次完全相同 action + reason 的重复；44229085 cohort 为 28，旧 5dc2038b cohort 为 135。脚本只比较公开 action 字段和 result.reason。
- 影响：这是候选浪费步数的信号，不证明重复在当时可避免；库存、电源、位置或可见对象改变后，重试可能合理。
- 可证伪假设：在拒绝后记录失败条件，只在房间、库存、供电或可见目标等相关公开状态改变时允许相同动作重试；若 matched 测试没有减少相同 action + reason 重复，或会阻断状态改变后的有效重试，则方案被证伪。

### 5. 单一 progress 标志不足以区分探索与原地循环

- 证据：有 progress 字段的动作中 35.6% 标为 false；另有 628 个公开位置二边往返窗口和 2,429 次同地点、无进展的重复 look。成功长尾样本也包含这些模式。
- 影响：progress=false 不是无用动作的充分标签；移动到已知房间可能为取资源或完成因果顺序服务。只用一个布尔值触发 recovery 会过度打断有效探索。
- 可证伪假设：把新增公开事实/阶段事件与近期边重复结合为连续停滞诊断；在固定的 seeded held-out 实例上，诊断应能定位长尾 trace 的重复片段，同时不将通往新物品、供电或出口的移动标为停滞。若误报率高于基线，或无助于降低二边往返，停止使用该信号。

## S5.2 seeded 长尾行为开销分解

为拆分 lunar/pyramid seeded 的 232/159 步长尾，新增 `scripts/audit_v2_seeded_overhead.py`，结果写入 [seeded overhead CSV](assets/seeded-overhead.csv)。分析覆盖两张图各 seed 0–4 的 10 条成功 Trace。每条都按 Trace 的 world version、definition ID 和 seed 重建当前 seeded 环境，并从成功 inspect 后的公开 `next_observation.visible_objects` 复核道具容器，再用成功 pickup 时的公开房间复核放置；10/10 实例布局一致。

Trace 记录的旧 `world_definition_hash` 有 6/10 与当前稳定 hash 不同。已知根因是 flex identity 曾按不稳定的 `frozenset` 顺序序列化；提交 `0d3bb0b` 只规范化 hash 输入，两个 seeded JSON 未变。旧 Trace 没有环境规则代码 SHA，因此下表的 BFS 最短值严格对应当前检出的 `FlexEnvironment` 规则与已复核的 seeded 布局，不是对历史运行二进制的独立证明。hash 是否相等不作为实例筛选条件。

BFS 对有限环境状态按 `(动作数, 移动动作数)` 字典序搜索；所有有效移动、可见 inspect、道具 pickup、repair/escape use 和目标 terminal read 均按一步计数，`look` 与不改变环境状态的动作不可能缩短路线。`action_overhead` 是 Trace 动作数减当前规则下的最少动作数；`move_action_delta` 是 Trace 移动动作数减一条全局最短动作路线中的移动数。`tool_room_returns_after_first_visit` 计入首次到达后再次进入任一含工具容器的房间，不等同于二边循环次数。阶段拒绝仅计 `panel_closed`、`code_unread`，以及针对正式密码终端/逃生载具的 `no_power`；重试只计相同失败 action payload 与 reason 的重复次数。没有新增 provider 请求或 GPU 运行。

| seeded 地图 | 5-seed Trace 动作数中位数 / 当前最少动作数 / overhead 中位数；最大 Trace / 最少动作数 / overhead | 长尾 seed | 长尾 Trace / 最少动作 | 移动动作 / 最短动作路线移动数（差值） | 工具房回访 | 重复 look | 阶段拒绝 | 重复失败重试 |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| lunar | 63 / 22 / 41；232 / 22 / 210 | 1 | 232 / 22 | 136 / 14（+122） | 40 | 41 | 1 | 0 |
| pyramid | 39 / 16 / 23；159 / 16 / 143 | 2 | 159 / 16 | 104 / 8（+96） | 28 | 32 | 0 | 0 |

这 10 条都来自各自单一配置的 5-seed 小样本。结果把长尾分成大量移动动作、重复进入工具房、重复 look 和少量阶段拒绝；不能据此把每个额外动作归因于单一机制，也不证明改动会改善成功率。逐 Trace 数值、旧/稳定 hash、房间进入计数与 BFS 扩展状态数见 CSV。

同一分析脚本另盘点两个 seeded 生成器的 seed 0–999：对每个 seed 重复构造均得到相同工具放置，但每张图只有 2 种不同布局/hash（lunar 分布 497/503，pyramid 497/503）。两种布局都能由当前环境 BFS 求解，且同图最少动作数相同（lunar 22，pyramid 16）；定义中没有预设 difficulty 标签。[布局覆盖 CSV](assets/seeded-layout-coverage.csv) 保存代表 seed、放置、频数和最短路径。当前 v2 因只有两个实例布局且没有难度标记，未满足“足够多样实例 + 预定义难度”的泛化前置条件；不能据此宣称实例泛化。若继续扩展，应创建新 `world_version`，先冻结多样布局及 dev/test `instance_hash` 划分，再让任何提示词或模块接触开发集。

因此，旧 v2 的长尾分解已完成，v2 不改写、不重用布局且不剔除困难实例。后续的新版本设计与冻结拆分见下节。

### V3 seeded 离线实例全集与 holdout 冻结

按新增 [spec 0016](../../specs/0016-seeded-instance-diversity/index.md)，对每图 6 个候选容器穷举任意两点激活与工具分配：lunar 有 90 种，pyramid 有 30 种。现有 FlexEnvironment BFS 在全部 120 个候选定义上均找到成功路线。最少动作分布为 lunar `{17:24, 18:12, 19:6, 20:36, 22:12}`、pyramid `{12:6, 14:12, 16:10, 18:2}`。因此预注册地图内两档：lunar `simple ≤18`、`complex ≥19`；pyramid `simple ≤14`、`complex ≥16`。标签只表示同一地图中的 oracle 路线长度分层，不表示跨地图难度等价。

冻结脚本 `scripts/audit_v3_seeded_layout_freeze.py` 将 stable definition hash 按确定性 affine seed 顺序映射到 seed 0–89 / 0–29，并在每个 `world_version × difficulty` 桶中以固定 SHA-256 次序分配约 1/3 test。生成的 [V3 布局冻结清单](assets/seeded-v3-layout-freeze.csv) 含 120 个 hash、seed、难度、最少动作/移动数、激活容器、工具位置及 split；核对结果为 lunar 60 dev / 30 test，pyramid 20 dev / 10 test，跨版本 hash 碰撞为 0。最短路使用的 `flex.py` SHA-256 为 `11393734c890312a3ae5e19057ae809a8a5c976c4bd43a91e6c4152304a51752`，BFS oracle 来源 `audit_v2_seeded_overhead.py` SHA-256 为 `908fa6ff181557a885041be747dd245ac1f86ce6b9fd2346d446a26d0a5e556`。旧 v2 定义未改。

V3 JSON、两个运行时 selector 与 affine seed builder 随后实现。`--verify-runtime` 将冻结清单逐行和实际 `create_environment` 对照，检查全部 120 个实例的 hash、placement、active containers、未激活容器隐藏及 seed+全集大小的周期映射；默认及 `PYTHONHASHSEED=1/42` 独立进程结果均为 120/120 一致。该核对只证明实现符合冻结定义与 split，不是模型评估。`FlexEnvironment` 动作规则和 V2 数据文件没有变化。

回归覆盖位于 `tests/test_flex_v3_seeded.py` 与 `tests/test_flex_world_identity.py`：断言 120 个冻结 hash/placement/difficulty/split、非激活容器不进入公开房间对象、seed 周期、负 seed 拒绝及跨进程 identity 稳定。全量 pytest 361 passed，Ruff 全仓与 mypy 49 个源文件通过。这些检查验证实现和预注册契约，不构成 v3 模型泛化证据。

Git 历史核对确认冻结早于运行时实现：提交 `f01b38d35029ea16a90c338fcd6911b753bd5b39`（2026-10-13 20:28 +08:00）已包含 spec、冻结清单和生成脚本，但不含 V3 seeded JSON；提交 `fac58fe0df226d14903573c6d778e91e67553949`（20:37 +08:00）随后加入两个 V3 JSON。该顺序证明实例全集及 split 在对应运行时实现前冻结。test 布局与 placement 仍可从仓库文件读取，因此这是需遵守的程序性 holdout，不是隐藏或盲测集。不得用 test 结果调 prompt、机制、阈值或生成器。S5.2 仍为 partial，待 S2 Gate 允许后按预登记方案进行行为评估；没有 provider 请求或 GPU 运行。

## 后续阶段建议与结论

- S2 优先实现并单独验证 M1；先覆盖 visited room/edge/frontier 和公开里程碑，不把隐藏地图信息写入 Memory。
- S3 再针对 use 配对与条件感知重试做匹配对照；不能将 M1 的空间记忆结果冒充动作 grounding 证据。
- S4 另行比较 P0、事件驱动的 P1 与预告顺序的 P2。现有 V1 材料显示 P2 会提前暴露阶段顺序和物品名；P1 仍缺受控结果，不能由本次 Trace 推断其效果。
- 审计没有导出完整 decision_reason，没有新增 LLM 调用或 GPU 运行。V2 S1 只完成离线观察与假设生成；不报告 oracle 最优性、匹配因果效果或经新实验验证的改进。
