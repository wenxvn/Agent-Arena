# V10 决策登记表

- 口径：**规则变更**（改任务语义、成功条件、隐藏信息边界或实例采样）必须有 DCR、新旧 hash 并列、对照实验与迁移测试；**接口/指标修复**（公开已有规则、修正事件计数、修正分母）可在 V10 命名空间直接实施，但仍保留旧值。
- 用户在 V10 提纲中已授权“执行 V10 的必要设计改进”，因此 V9 中标为 `requires_user_decision` 的 DCR 在 V10 由执行 Agent 按证据裁定，状态写 `accepted_by_agent`（`agent_reviewed`），不是 `human_approved`。
- V10 DCR 编号从 `DCR-V10-01` 开始，文件在 `docs/v10/dcr/`；V9 的 DCR-01…14、25–27 只读引用。
- 本表在各 Batch 完成后追加“实施状态”和证据链接。

## 1. 全局决策

| ID | 决策 | 类型 | 理由 |
|---|---|---|---|
| G-01 | V10 运行时放在 `src/agent_arena/v10/runtime/`，按图子类化或包装 V8 地图，不修改 V8/V4 文件 | 工程 | 冻结要求；V8 Trace 必须可原样复算 |
| G-02 | 每图至少 `environment_seed ∈ {0,1,2}`；MAP-06 ≥10；MAP-15/21/28/29/30 目标 10 | 实例采样 | spec §9.1；V8/V9 的三次重复不是三 seed（baseline-audit §5） |
| G-03 | `scenario_hash` 按 `(map_id, rule_hash, environment_seed, 密封变体)` 计算，每 seed 独立 | 工程 | V8 `scenario_hash` 不含 seed |
| G-04 | 环境 seed、policy seed、replicate 三维分开记录；MiMo 不支持生成 seed 时不写“模型 seed” | 记录 | spec §1 |
| G-05 | `legal_random` 每图每环境 seed 20 个 policy seed | 基线 | spec §9.2 |
| G-06 | V10 指标 `metric_schema_version=v10`，旧 V7/V8 值与 V10 值并列，不跨版本求均值 | 指标 | spec §8.3 |
| G-07 | V10 所有 MiMo 账本共享全局 ¥10（已结算 + 预留），由全局账本守卫统一检查 | 预算 | spec §10.1；禁止拆分账本规避 |
| G-08 | 全仓 Ruff 653 条既有错误不在 V10 修改；V10 新文件必须零错误 | 质量 | 避免触碰冻结文件 |

## 2. 逐图候选：规则变更 vs 接口/指标

| 地图 | 问题（V9 证据） | 类别 | V10 处理方向 | DCR |
|---|---|---|---|---|
| MAP-01 | 无 | — | 3 seed 参数化（起始供氧余量/房间布局不变，事件时序变化） | 仅实例采样 |
| MAP-02 | `response_latency` 恒 1 | 指标 | 纳入 V9 `adaptive_response_within_2`；泄漏时点按 seed 变化 | 实例采样 |
| MAP-03 | 码可最后读、只在一个 Observation 出现；无记忆通道；EVA 退出不扣 | **规则** | 读码与提交之间插入不可跳过阶段；读码后关闭回读；新增 agent-owned 记忆动作；码随 seed 变化；EVA 计费与文档对齐 | DCR-V10-01 |
| MAP-04 | 绕行/盲撞都成功；`stranded_ticks` 错误 | 规则 + 指标 | 潮汐相位随 seed；绕行保留但计成本；修计数 | DCR-V10-08 |
| MAP-05 | 无（DCR-02 已公开） | — | 窗口时刻随 seed | 实例采样 |
| MAP-06 | seed0 无风暴；VOI 硬编码 None | **实例采样** + 指标 | 10-seed 分层天气 cohort；实现风险调整完成度与后悔值 | DCR-V10-03 |
| MAP-07 | 待新证据 | 接口 | 初始水位/阀门方向随 seed | 实例采样 |
| MAP-08 | `no_hypothesis` 成功 | 待证 | 漏点随 seed；检验测试是否缩小假设集 | 视证据 |
| MAP-09 | `skip_pump` 成功 | 待证 | 阈值/漏速随 seed；检查因果依赖 | 视证据 |
| MAP-10 | 待新证据 | 接口 | 初始仓位/容量/时限随 seed | 实例采样 |
| MAP-11 | seed0 无风暴 | 实例采样 | 风暴 cohort 预登记 | 实例采样 |
| MAP-12 | 无有效 MiMo | 待证 | 离线验证跨期库存与研究分 | 视证据 |
| MAP-13 | `illegal_door_attempts`/ratio 口径 | 指标 | 修计数；多规则 seed | 指标 |
| MAP-14 | 盲交 2/3 通关 | **规则** | 区分推理与幸运：成功需引用证据或降低盲交概率 | DCR-V10-09 |
| MAP-15 | goal 泄露规则；错误后相位翻转 | **规则** | 删泄露文本；多规则家族；预测证据节点 | DCR-V10-04 |
| MAP-16 | 无 | — | 3 seed | 实例采样 |
| MAP-17 | `overcapacity_events` 口径；line 枚举 | 指标 + 接口 | 修计数；公开 line 枚举 | 指标 |
| MAP-18 | `step_limit=min(.,12)`；抢跑旁路 | **规则** | 分离物理时钟/动作预算/服务窗口/故障时点；故障必须在服务前发生 | DCR-V10-02 |
| MAP-19 | forecast 无反馈 | 规则 + 指标 | 预测影响代价或风险 | DCR-V10-10 |
| MAP-20 | 旁路被直供支配 | 规则 | 动态负载使旁路有价值 | DCR-V10-11 |
| MAP-21 | 1 步直达撤离满分 | **规则** | 拆分 `safety_success`/`science_completion`/`overall_utility` | DCR-V10-05 |
| MAP-22 | 无记忆策略 12 步成功 | 规则 | 遮蔽 + 分岔 + 跨阶段位置记忆 | DCR-V10-12 |
| MAP-23 | `no_scout` 成功；成本分母 | 规则 + 指标 | 线索价值与侦察成本；修分母 | DCR-V10-13 |
| MAP-24 | 成功轨迹未改路；`replanning_latency` 反向 | 规则 + 指标 | 封路发生在主路径上且不可预知 | DCR-V10-14 |
| MAP-25 | 覆盖率计入被拒诊断 | 指标 | 采用修正覆盖率 | 指标 |
| MAP-26 | `no_diagnosis` 成功；计数计入被拒 | 指标 | 保留盲换为合法替代，用备件/风险成本区分；修计数 | 指标 |
| MAP-27 | 无 | — | 3 seed | 实例采样 |
| MAP-28 | 枚举未公开；timeline 未区分 N/A | 接口 + 指标 | 公开案卷枚举与 record/compare 语义；证据依赖图随 seed | DCR-V10-06 |
| MAP-29 | compare 语义未公开 | 接口 + 规则 | 公开比较语义；三类证词随 seed | DCR-V10-06 |
| MAP-30 | 条目映射未公开；记录≠证据 | 接口 + 规则 | 公开条目 ID 与引用格式；跨阶段依赖随 seed | DCR-V10-07 |

DCR 编号是规划，最终以 `docs/v10/dcr/` 中实际文件为准；某图若证据表明无需规则变更，会在此表注明“撤回”。

## 3. 实施状态

| Batch | 内容 | 状态 | commit |
|---|---|---|---|
| 0 | 基线审计、冻结、状态矩阵、本表 | 完成 | 见 README |
| 1 | MAP-03 DCR-V10-01、MAP-18 DCR-V10-02 | `accepted_by_agent`，离线 Gate 通过 | 见 README |
| 2 | MAP-06 DCR-V10-03、MAP-15 DCR-V10-04、MAP-21 DCR-V10-05 | `accepted_by_agent`，离线 Gate 通过 | 见 README |
| 3 | 古堡 DCR-V10-06（28/29）、DCR-V10-07（30） | `accepted_by_agent`，离线 Gate 通过 | 见 README |
| 4 | MAP-04 DCR-V10-08、MAP-14 DCR-V10-09、MAP-19 DCR-V10-10、MAP-20 DCR-V10-11、MAP-22 DCR-V10-12、MAP-23 DCR-V10-13、MAP-24 DCR-V10-14 | `accepted_by_agent`，离线 Gate 通过 | 见 README |
| 5 | MAP-13 DCR-V10-15、MAP-08 DCR-V10-16、MAP-26 DCR-V10-17、MAP-11 DCR-V10-18、MAP-07 DCR-V10-19、MAP-10 DCR-V10-20、MAP-09 DCR-V10-21、MAP-12 DCR-V10-22 | `accepted_by_agent`，离线 Gate 通过 | 见 README |
| 6 | 154 枚举 + 128 V10 规格 + 20 项缺陷结论 | 完成 | 见 README |
| 7 | 多 seed 难度定标 | 完成（Batch 8 后加入 MiMo 列） | 见 README |
| 8 | 有界 MiMo 复测（4 次中断处理 + 阶段 3 接口修复重跑 + 阶段 4 MAP-20 公开规则重跑） | `agent_reviewed`；85 局记录、80 有效、CNY 1.88611620 | 见 README |
| 9 | 8 项 Gate 判定 + 30 张逐图审计卡 + 指标独立复核 + trace 级归因 + 成本审计 + 最终报告 | 完成；**30/30 `VALIDATED`** | 见 README |

### 3.1 Batch 9 追加的接口/指标 DCR

| DCR | 内容 | 类型 | 证据 |
|---|---|---|---|
| DCR-V10-23 | MAP-12 `research_completion` 取值域 `(0,1)`→`(0,3)` | 指标 | `independent-metric-check.md`（4 条违规 → 0） |
| DCR-V10-24 | 公开动作契约按 `V8Action` 注解渲染类型 + MAP-18/19/28 公开格式澄清 | 接口 | `mimo-results.md`；MAP-18 非法 20/20 → 0/13、MAP-28 seed0 由“从未提交”变为成功 |
| DCR-V10-25 | MAP-20 `set_flow`/`adjust_loads`/`open_bypass` 结构与取值写进地图 `public_rules()`（`rule_hash` `81eb7439…`→`e677a0ac…`） | 接口 | `mimo-results.md`；MAP-20 非法 168/168 → 0/168，`mimo` Gate 通过 |

### 3.2 Batch 9 的构念改标

| 地图 | 原标 | 新标 | 证据 |
|---|---|---|---|
| MAP-04 | FORCED | **OPTIONAL** | `detour_only` 6/6 成功但 `time_margin` 0.67 ≪ Oracle 3.33：机制影响效率而非通过与否 |

其余 22 张原生图的构念标签保持不变；`BYPASS` 与 `BLOCKED` 在 V10 均为 0。
