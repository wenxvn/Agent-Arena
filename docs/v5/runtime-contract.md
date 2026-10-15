# V5 运行契约

## 数据流

`DecisionProvider` 每次只收到当前 allowlisted Observation、系统任务说明、最近五条公开动作历史，以及该条件允许的 Agent-owned 记忆。provider 没有 shell、文件、网页、环境真值或 Oracle 工具。响应先转成 V4 严格 Action，再通过当前地图的字段形状 allowlist 后调用 `step`。必填字段为空、Action 与地图契约不符、非法 JSON、缺字段和 schema 不匹配均记录 `action: null`，调用地图的 `reject_invalid_action()`，不拼造 Action；环境按自己的 tick 规则处理。MAP-18 在闭塞发生前只展示未定位且未给时长的公开预警；R2–R3 闭塞状态仅在 Observation 实际出现后提供。

裁判状态只保存在环境实例与 `judge_metrics.json`。Agent-visible `agent_trace.jsonl` 只含 Trace header、合法固定前缀、决策 Action、前后公开观察、环境公开结果、token usage 和延迟。MAP-30 的合法问询一旦公开引用证据，就在同一答复中给所有条件提供相同的结构化公开 evidence fact 和 witness answer；未发现或未解锁的证据不会出现。`history5_casebook` 观察还会为案卷中已合法记录的证据 ID 展示这些事实与文本；未记录证据不会进入案卷视图。隐藏案卷条件不提供案卷快照。`history_full` 条件接收从调查开始至今的全部公开 Action/result 序列，以及去重后的公开证据/证词 payload；它不会把压缩后的历史裁剪成最近五步，仍受 8,192-byte 请求保护。MAP-30 的 `q4_recalled_after_gap` 在 gap 后、模型正式指控前为 `null`；只有最终主张同时引用正确身份和 Q4 案卷时才为真。裁判真值、完整 WorldState、密钥、模型原始响应和完整思维过程不进入模型输入或公开 Trace。

## 地图专属时钟

| 地图 | 执行动作和边界 |
|---|---|
| MAP-08 | 普通动作推进一 tick，压力测试推进两 tick；水位超过 7.0 才失败，等于 7.0 仍可运行；正确或错误修复按设计结算。 |
| MAP-16 | 路线预约/撤销不推进 tick；`move_train` 原子同步结算预约位置，冲突与死锁由地图判定。 |
| MAP-18 | 每个 `set_timetable` 联合提交一个 tick；闭塞窗口为 tick 5–9，tick 10 恢复；告警只给不定位、不含时长的预警。 |
| MAP-22 | 只有实际移动增加步数；路标观察和记忆更新不移动；记忆只能写刚检查的 node 或刚走过的 edge，最多 32 条。共享 prefix 在 L/tick 12 结束。 |
| MAP-26 | 走动、测试、维修各按设计推进 tick；错误替换可得到所选反馈、回滚后仍消耗重试成本；恢复 prefix 是真实回放到 A/tick 7，留下一个可用备件。 |
| MAP-30 | 成功动作逐步推进调查 tick，40 tick 截止；调查前缀在 J、正式指控前结束，四格案卷已由对应条件初始化。 |

MAP-08 `candidate_set_sizes` 从三项公开候选开始，按实际已观察测试结果逐项过滤签名集合；该字段表示剩余候选数，不是不同输出类别数。

## Episode / trace / manifest

每局目录包含 `agent_trace.jsonl`、`judge_metrics.json` 与 `episode_manifest.json`。每局 manifest 记录该条件真实的 `context_policy`，包括完整公开历史、最近五步、结构化案卷及其他登记记忆。外层 `run_manifest.json` 记录 39 局 matrix、六局 smoke、模型与版本、币种、offline gate、运行 commit/tree hash、V4 map source hash、上限、运行目录与 ledger 位置。V5 JSONL ledger 在 provider 请求前 fsync 费用与 token 预留；settled response 同时记录实际 usage、保守估算成本、请求 hash 与只含安全 Action 的恢复 checkpoint。

可恢复状态必须能从同一 run 的公开 trace 与追加账本确定性重放。被忽略目录内的 `pilot_registry.json` 为整个 V5 pilot 保留唯一 run/ledger 身份；新建 second ledger 会被拒绝，完成、关闭或 unknown-spend 后 registry 不得删除或替换。存在未结算 reservation、账本损坏、来源 hash 不一致或 ledger 已关闭时，停止并保留证据；不重复可能已计费的决定，不改写历史账本。真实 pilot 的一次恢复重试只对明确证实未计费且 usage 为零的 provider 拒绝开放；现接入 adapter 对 timeout、连接中断、429、5xx 与未知错误一律 `unknown_spend` 并关闭 pilot。

## 预算

单局最多 100 个 Agent 决策和一次恢复请求；每次请求预留上限为 8,192 input 与 1,024 output tokens，单局最长 12 分钟，Provider 累计墙钟最长 240 分钟。39 局最多 3,662 次全局请求与 33,748,992 个预留 token；全局请求数低于 39 × 101 的逐局理论上限，费用 ceiling 优先。每次预留都计入费用硬上限：CNY ¥37.50 或 USD $5.25，必须显式选择一个币种，不能转换或相加。unknown usage 留存完整 reservation 并停止后续调用。
