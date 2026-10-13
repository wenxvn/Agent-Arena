# V2-02 既有 Trace 离线瓶颈审计

## 范围与方法

- 审计日期：2026-10-13（Asia/Shanghai）；审计代码提交：a372dce9f9e904db31907dc283629bd0b37e6d03。
- 离线命令：python scripts/audit_v2_traces.py --runs-dir runs --results-dir results。脚本仅使用 Python 标准库。
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

实例标识也有限：Trace 没有独立 instance_hash。seeded 条目暂用 world_version、definition_hash 和 seed 派生 effective_instance_signature；非 seeded 条目不把 replicate seed 当成环境实例身份。该签名不是地图内容哈希，因此本审计不报告 oracle 最优步数或 optimality gap。

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

| 家族 | 动作数 | 世界版本 / seed 角色 | 本地 trace 相对路径 |
|---|---:|---|---|
| 深海站 | 168 | abyss_escape_hard / replicate_id | runs/muse-9maps-abyss-hard/episode_20261011T074539Z_memory_seed-2_dbad0ed7.json |
| 古堡 | 69 | castle_escape_hard / replicate_id | runs/muse-21maps-castle-hard/episode_20261011T131606Z_memory_seed-0_8f807e05.json |
| 丛林 | 53 | jungle_escape_hard / replicate_id | runs/muse-21maps-jungle-hard/episode_20261011T131206Z_memory_seed-2_da140ef7.json |
| 灯塔 | 261 | lighthouse_escape_v3 / replicate_id | runs/muse-9maps-light-hard/episode_20261011T074453Z_memory_seed-1_fa596cf4.json |
| 月球 | 232 | lunar_escape_v2_seeded / seeded_instance | runs/muse-flex-lunar-v2s/episode_20261011T142412Z_memory_seed-1_30323f7d.json |
| 极地 | 51 | polar_escape_hard / replicate_id | runs/muse-21maps-polar-hard/episode_20261011T130327Z_memory_seed-2_71be5ad2.json |
| 金字塔 | 159 | pyramid_escape_v2_seeded / seeded_instance | runs/muse-flex-pyramid-v2s/episode_20261011T142750Z_memory_seed-2_e46fe34f.json |
| 飞船 | 440 | spaceship_escape_v3 / replicate_id | runs/muse-9maps-ship-hard/episode_20261011T074451Z_memory_seed-3_ae173aea.json |
| 地铁 | 50 | subway_escape_hard / replicate_id | runs/muse-21maps-subway-hard/episode_20261011T130725Z_memory_seed-2_33208099.json |
| 火山 | 37 | volcano_escape_v1 / replicate_id | runs/muse-21maps-volcano-med/episode_20261011T130905Z_memory_seed-3_3b175310.json |

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

## 后续阶段建议与结论

- S2 优先实现并单独验证 M1；先覆盖 visited room/edge/frontier 和公开里程碑，不把隐藏地图信息写入 Memory。
- S3 再针对 use 配对与条件感知重试做匹配对照；不能将 M1 的空间记忆结果冒充动作 grounding 证据。
- S4 另行比较 P0、事件驱动的 P1 与预告顺序的 P2。现有 V1 材料显示 P2 会提前暴露阶段顺序和物品名；P1 仍缺受控结果，不能由本次 Trace 推断其效果。
- 审计没有导出完整 decision_reason，没有新增 LLM 调用或 GPU 运行。V2 S1 只完成离线观察与假设生成；不报告 oracle 最优性、匹配因果效果或经新实验验证的改进。
