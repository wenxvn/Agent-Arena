# 0017. V3 主题世界与场景运行时

**日期**：2026-10-14
**状态**：Accepted；30 关离线实现与阶段验收已完成

## 背景

V1/V2 的十世界矩阵验证了拓扑、任务结构和 seeded 变体，但其核心仍沿用维修、供电、读码和逃生链。V3 需要十个真正不同的确定性机制，每个家族包含 easy、medium、hard 三关，共 30 个手工关卡。研究提纲是内容来源；它不是已交付实现或模型结果。

V2 的 provider ledger 与 seeded holdout 已冻结。V3 是新的离线世界设计与工程交付，不读取、不修改、不复用这些账本或 holdout，也不发起真实 Provider 请求。

## 决策

### 版本隔离与身份

- 保留既有 `WorldState`、旧六种 `Action`、旧 selector、世界定义、prompt 和 trace 读取行为。
- 新世界使用独立 selector：`<family>-escape-world-v3-<difficulty>-zh`；`scenario_id` 为 SP-E 至 CA-H 中的唯一 ID。注册必须显式列举，未知 selector 直接报错。
- V3 定义逐关独立保存，完整规范化定义计算稳定 SHA-256；身份另记录 family、difficulty、`mechanic_version`、`ruleset_sha` 与 `source_design_id`。运行时状态、解答与私有线索不进入 Agent Observation。

### Action 与 Observation 契约

- 保留 `Action` 与 `action_adapter` 为 legacy V1 契约。新增严格 discriminator union `ScenarioAction`：复用原六种动作，并增加 `interact(target, choice)`、`wait(turns=1)` 和 `submit(target, answer)`。不允许额外字段。
- Provider 请求增加 `action_contract_version`，默认 `legacy_v1`；默认 JSON Schema 字节语义、提示词和旧 provider fixture 不变。V3 明确请求 `scenario_v3` schema，所有 provider 共用同一 Pydantic Action 定义。
- V3 Observation 使用独立的 `ScenarioObservation`，包含当前公开目标、tick、allowlisted `public_status` 和当前可见目标的 `available_interactions`。隐藏答案、未来事件、完整地图状态和 oracle 轨迹不得序列化到 Observation、Agent prompt、公开阶段或 Trace。
- `interact` 只允许 Observation 对应实体列出的选择；`wait` 单次只能推进一个 tick；`submit` 的错误反馈不得泄漏答案或允许逐字符探测。

### ScenarioEnvironment 与时间语义

- 新增与 legacy `WorldState` 隔离的 `ScenarioState` 及 `ScenarioEnvironment` 公共骨架。基础层负责身份、reset/observe/step、位置/物品、tick、事件、终止状态与安全公开字段；十个家族分别持有类型化状态和独立规则模块，不建设按 `scenario_id` 分支的超级环境。
- 结构合法且交给 Environment 的每个 Action 消耗一个世界 tick，包括语义拒绝和 `look`/`inspect`；schema 非法候选在 Environment 外拒绝，不消耗 tick。每步顺序固定为：检查动作前置条件、应用直接效果、推进环境资源/周期事件、刷新 Observation、判定终局。动作直接完成主目标时先确认成功，不能被同 tick 后续风险覆盖。
- 动态效果仅依赖 tick 与明示 seed，不依赖墙钟、Python hash 随机性、Provider 或推理耗时。失败状态提供可观察的阈值与安全 `failure_reason`；partial success 与完整成功区分。

### Episode、Trace 与评估

- `Environment` 的旧实现与 `is_success()` 保持有效。ScenarioEnvironment 增加显式 `ScenarioTerminalStatus`、`failure_reason`、逐步公开 `scenario_event` 与安全 `score_components`。
- Trace 用可选 schema 字段记录 scenario 身份、事件、状态和失败原因；缺字段的旧 Trace 按历史格式读取，不反推 scenario 结果。新增 outcome `scenario_success`、`partial_success`、`scenario_failure`；benchmark 主成功率只把 `success` 与 `scenario_success` 计为完整成功。
- `StepTrace.action` 可读写两种版本的 Action；旧 Action JSON 保持原形。UI 对新增公开字段只读展示，不能读取内部 ScenarioState。
- CLI 使用显式 world selector 创建 V3 世界并选用 V3 prompt/contract。候选选择、规划辅助和旧 Memory 统计若未声明支持 V3，必须明确拒绝或关闭，不能静默降级。

### 内容与验收

- 30 个 `scenario_id` 与 10×3 定义逐关手工审阅；十家族有不同的胜利谓词、状态转移与失败因果。每关保存地图、初始状态、公开线索、操作语义、参考行动轨迹、失败/拒绝情形和 0–12 设计评分。
- Gate 1 先完成金字塔、地铁、深海纵向原型；之后依次完成十个 easy、十个 medium、十个 hard。每关必须有只根据公开 Observation 选择动作的完整 oracle、至少两种机制相关负例、reset/hash、Observation 泄漏和可见文案一致性检查。
- 先静态检查全部 30 条提纲内的参考策略与初始值，不因实现尚未完成而搁置；发现矛盾时逐条记录并局部修订。
- 最终验收要求 30/30 oracle 完整成功、全部关卡质量评分至少 10/12、动态/谜题/调度/NPC 等专项测试通过、旧 10×3 与 Seeded v3 回归保持、Trace 安全、项目文档同步及基础质量门禁通过。
- 不以模型运行、真实成功率、统计显著性或“最短解”作为本 spec 验收；任何后续真实模型实验须独立设计、登记并授权。

## 阶段状态

| Gate | 范围 | 状态 |
|---|---|---|
| 0 | 基线、冻结边界、spec、30 个设计卡与静态可行性 | 完成 |
| 1 | Scenario 契约与 PY/SU/AB 纵向原型 | 完成 |
| 2 | 十家族 easy | 完成 |
| 3 | 十家族 medium | 完成 |
| 4 | 十家族 hard 与有界公开策略可解性检查 | 完成 |
| 5 | 30 关 oracle、审计、兼容、文档和冻结 | 完成 |

## 验收证据

验收证据见 `docs/world-design-v3/README.md`、十份家族设计卡、`mechanics-crosscheck.md`、`review-and-score.md` 和 `oracle-acceptance.md`。30/30 公开 Observation Oracle 在 100 动作上限内完整成功且无拒绝动作；回放 SHA 固定每关动作轨迹。该有限路线见证证明存在可执行策略，不是搜索穷举、最短步数证明或模型行为证据。

兼容性通过旧测试套件、30 selector reset/hash/Observation allowlist、Trace schema/redaction 与 CLI 限制覆盖。最终质量门禁结果和 lockfile 工具限制写在 `docs/engineering-log.md`。本 spec 阶段未发起真实 Provider 请求或 GPU 运行。
