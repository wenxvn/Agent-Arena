# V5 设计差异与解释

审计日期：2026-10-15。没有修改地图拓扑、主能力或胜负谓词。发现一项 MAP-22 Oracle 的隐藏信息预载与 V5 合法探索前缀之间的冲突；通过环境观测生成新的配对前缀，不修改原始 V4 设计材料。

## DCR-001：MAP-22 Oracle 预载未来地图事实

- **位置**：`worlds/v4/MAP-22/oracle_trace.jsonl` 初始 `agent_authored_memory_journal`；与 `worlds/v4/MAP-22/planning/hand_traces.json` 的 `external_graph_memory_euler_tour` 策略说明冲突。
- **冲突**：设计 Oracle 在探索开始前已经包含全 12 个地点与 15 条边的 27 条地图记忆事实；MAP-22 规则要求节点只有在本地观察后、边只有在实际穿越后才能记忆。把这个 Oracle 状态当成 Agent 历史会泄漏未来拓扑。
- **最小修订**：V5 条件对照从合法路线的前 12 次移动生成共同公开前缀。两条件共有同一位置、公开 Observation 和 movement history；`history5_graph_memory` 仅额外记录当时现场检查过的地点和刚走过的边，容量仍由 MAP-22 环境限制为 32 条。前缀从 A 到 L，tick 12。
- **影响范围**：只改变 V5 测量前缀 fixture，不改地图环境、胜负条件、拓扑或原 Oracle 文件。完整设计 Oracle 留作既有离线证据，但不作为 API 输入或 Agent memory。
- **验证方法**：分别在两份新环境中实际执行同一方向序列；逐步比对公开 movement history 与终点/时钟；检查记忆事实均可追溯到刚刚检查的 signpost 或已走过的 edge；哈希 `hand_traces.json` 并纳入冻结 offline gate。

## API 错误账务分类

MiMo 官方错误码页建议对 HTTP 429、500、503 退避重试，但没有声明同步 API 对这些错误免计费，也没有保证响应包含 usage。因此 V5 将 timeout、connection loss、429、5xx 归为 `unknown_spend`，保留该次完整费用预留并关闭 pilot，不自动重试。只有将来获得可审计的明确“未计费且 usage=0”协议证据，才允许一次同 hash 恢复请求；该条件现在不会触发。官方建议与本项目的 fail-closed 规则分别保留，不推断实际计费行为。

## Seed 覆盖解释

用户要求每图最多测试三个 seed。V4 规格中只有 MAP-08 和 MAP-26 定义了多个真值实例。MAP-08 使用 0、4、8 分别覆盖 B、D、F；MAP-26 使用 0、1、2 分别覆盖天线、电源和软件故障。MAP-16、MAP-18、MAP-22、MAP-30 明确是固定拓扑、固定事件或固定真值的场景。可用 seed 0、1、2 重复运行以核对执行稳定性，但它们不是三个独立实例，不用于泛化或独立样本量声明。

## MAP-26 标准化失败前缀

能力试验要求从合法、相同且保留成功资源的错误替换反馈状态开始。前缀必须由 V4 环境实际执行并保存公开历史，不能构造 WorldState。实现阶段验证回滚后仍至少保留一个正确维修备件；如果该条件不能从真实状态满足，则停止该试验并记录阻塞，不更改 MAP-26 胜负谓词。

## 预算边界

提纲中的 2 美元仅是命令示例，不是用户预算。实际 pilot 使用用户指定的 `mimo-v2.6-flash` 与每图最多三 seed，并按官方缓存/未缓存输入与输出价格、单局动作与 token cap 计算全局硬上限。执行命令明确选择一个账单币种；CNY/USD 费率分别记入独立 V5 账本。V2 账本保持封闭且不相关。

## 付费前独立复审修复

2026-10-15 的第二模型代码复审在首次 MiMo 请求前发现了提示泄漏、Action 崩溃边界、案卷可读性、MAP-30 Q4 过度计分、首次响应恢复、未文档化 Provider 字段及 MAP-08 候选数语义问题。处理状态与最终复核结论追加在 [`docs/reviews/2026-10-15-main.md`](../reviews/2026-10-15-main.md)；此处记录设计行为：

- MAP-18 system prompt 不再给出 R2–R3 的未来闭塞时间；tick 5 前只允许模型看到通用且不定位/不说明持续时间的预警，公开 `closed_segments` 依实际 Observation 更新。
- V4 Action、联合调度操作和地图记忆事实拒绝必填空值；V5 Runner 再用 map-specific 字段形状 allowlist 拒绝跨图动作，记录无可执行 Action 的非法响应。
- MAP-30 案卷只展开已记录 evidence ID 的公开 fact/text；隐藏案卷 condition 不展开旧事实。Q4 gap 后的指标在正式主张前为 `null`，再依据模型最终主张中正确身份与 Q4 案卷引用判定。
- MAP-26 prompt 提供公开拓扑及合法日志、测试、部件 ID，不提供 seed/真值映射或未执行测试读数。
- 首个已结算响应已在账本持久化、但 Trace 尚未追加时，resume 从唯一 settled checkpoint 补写决策并确定性继续，不重复请求 Provider。
- MiMo `scenario_v4` Responses 请求不携带官方参数表未列出的 `store`；其他 contract 保留既有参数行为。
- MAP-08 `candidate_set_sizes` 按真实观测签名过滤剩余候选。

本轮定向回归已通过，最终只读复核结论为 Approve；提交后完整离线门禁仍待完成，期间未发起任何真实模型 API 请求。

后续对照 A/B/C 的定向复审发现，完整历史 A 的 Q4 证人答复原先只有中文文本，而结构化案卷 C 展示的已记录 fact 还包含正式 Action 所需的 canonical person ID。修正后，证人合法解锁 evidence ID 时，公开答复同时提供同一 evidence fact 与 witness answer；完整历史 A 和案卷 C 因而可读到相同的已解锁身份映射，短历史 B 只在最近五条观察窗口内可读到。A/B/C 固定前缀此前都没有该映射。回归测试检查解锁前不可见、解锁后 A/C 可见、B gap 后不可见，以及增加一条决策后的 A 输入仍低于 8,192-byte 上限。2026-10-16 第二模型审查为 Approve；manifest 标签 Minor 已修复并复核。冻结离线门禁和 API pilot 仍未开始。

## MAP-30 完整历史控制补入矩阵

对照《V5能力测量体系测试.md》MAP-30 能力段的 A/B/C 定义复核时发现，第一版 pilot matrix 只登记了 B（最近 5 步）与 C（最近 5 步 + 案卷），遗漏 A（完整历史）。Stage C 允许每图选择 2–3 个条件；完整历史、短历史、结构化案卷能分别测出历史截断和外部记忆收益，因此在付费前将 A 加入同一固定前缀和三个 scene label 对照。

新 matrix 共 39 episode。每图仍最多三个 seed label，六个 smoke episode 仍与矩阵重用。为保持 CNY ¥37.50 / USD $5.25 硬上限，global request cap 设为 3,662（比 39 × 101 的逐局理论上限小），最大 token reservation 为 33,748,992；任何全局请求、token 或费用上限耗尽都会 fail closed。

完整历史 condition 不复制每个完整 Observation 快照；它以完整顺序传入全部公开 Action/result，并在首次可见时加入去重的证据/证词公开负载。合法问询释放 canonical 身份事实时，A 与 C 同时获得该事实；B 只在滚动窗口中短暂看到它。三个条件固定前缀的请求均低于 8,192-byte 上限；A 前缀请求界 7,880 bytes，增加一步后为 7,985 bytes。任意后续长历史仍可能触发运行时 context stop，须如实报告。
