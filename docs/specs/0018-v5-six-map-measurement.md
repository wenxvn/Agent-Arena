# 0018. V5 六图能力测量运行时

**Date**: 2026-10-15
**Status**: In Progress

## Summary

为六张 V4 地图建立隔离的运行时和测量流程。环境规则、Agent 可见内容、裁判真值和真实模型试验分开保存。先完成离线验收，再按用户指定的 MiMo 模型和 seed 范围做小规模配对试验。

## Context

六张地图已有手工规格和公开 Oracle，但仓库当前只有 V3 场景运行时。地图包含同步调度、压力累积、路线记忆、诊断反馈和证据依赖等不同时间与状态规则。直接复用 V3 状态逻辑会混淆契约，统一单步推进也会改变部分地图的动作成本。

研究结果必须能追溯到地图版本、代码版本、seed、实验条件、动作轨迹和模型 usage。隐藏事实只可用于环境裁判和私有指标，不能进入 Agent 请求或公开 Trace。真实请求还需要在环境未验收、provider 失败或未知费用时停止。

## Requirements

**User stories**:
- 作为研究者，我要让 Agent 仅凭公开 Observation 操作六张地图，以便测量其行为而不泄漏裁判事实。
- 作为研究者，我要按固定条件和 seed 重放环境及模型 episode，以便逐图检查能力指标、成本与失败。

**Acceptance criteria**:
- **AC-1**: 六关通过独立 `scenario_v4` 注册表创建；V3、Legacy 的 action、state、selector、Trace 和既有 CLI 行为不变。
- **AC-2**: 每关使用严格的 V4 Action 与显式 Observation allowlist。judge only 真值、答案映射、未发现证据、未来事件、Oracle 和参考路线不进入 prompt、工具响应、Agent 可见 Trace 或日志导出。
- **AC-3**: 六关 reset、step、成功、失败、步数或时间上限和终止后动作均遵循各自 V4 规格；复杂 tick 与原子并发按地图单独实现，不能统一改写动作语义。
- **AC-4**: 六张地图的手写成功 Oracle 在真实环境逐步回放并达到预期终止结果；每个公开 Observation 与其公开预期字段逐步核对，不以文本匹配最终答案代替环境判断。
- **AC-5**: 每图至少三种独立失败机制和关键边界用例在运行时触发，失败原因及发生时刻有证据，终止后状态不变。
- **AC-6**: 固定 seed 与动作序列重复两次产生相同公开 Trace 和裁判状态 hash；MAP-08 独立枚举测试签名与熵，MAP-16 BFS 核对六 tick 最优值，MAP-18 核对无故障时刻表和乘客账本，MAP-22 核对图论距离和路线，MAP-26 核对备件可恢复性，MAP-30 核对证据依赖可达性。
- **AC-7**: 每图最多使用三个 seed。MAP-08 用 0、4、8 覆盖 B/D/F；MAP-26 用 0、1、2 覆盖三类故障。MAP-16、18、22、30 的 0、1、2 是固定场景重复运行，不作为独立实例或独立样本量。
- **AC-8**: V5 API pilot 默认 dry run；真实调用需要显式 `--execute-paid`，provider 与 model 必须匹配本机配置，并依次执行六图 seed 0 smoke 与矩阵内剩余 episode。Smoke 固定为 MAP-08/no_hypothesis_table/0、MAP-16/react/0、MAP-18/alert_off/0、MAP-22/history5/0、MAP-26/free_diagnosis/0、MAP-30/history5/0；这些是预登记矩阵中的 episode，不额外增加局数。只有六局都具有完整 usage、公开 Trace、私有 metrics 和一致 manifest，且账本/预算仍有效，才可开始其余 33 局。
- **AC-9**: 最多 39 个预登记 episode；每局最多 100 个 Agent 决策和 1 次恢复重试、101 次请求尝试，每次最多预留 8,192 个输入 token 和 1,024 个输出 token。按 CNY ¥37.50 / USD $5.25 最坏费率二选一后的全局请求尝试上限为 3,662 次，总 token 预留上限为 33,748,992。单局最长 12 分钟，全局 Provider 墙钟预算最长 240 分钟；单个 episode 出错重试后即终止，连续两个 Provider 请求错误或任一 unknown spend 即关闭整个 pilot。CNY 单次最坏预留 ¥0.01024、3,662 次最多预留 ¥37.49888；USD 单次最坏预留 $0.0014336、3,662 次最多预留 $5.2498432。币种二选一，不换算、不叠加，运行必须显式选择币种。全局请求上限小于 39 × 101 的逐局理论上限；任一全局费用、请求或 token 上限耗尽都 fail closed。2026-10-16 复核费率仍为 CNY 缓存 ¥0.02/M、未缓存 ¥1/M、输出 ¥2/M；USD 缓存 $0.0028/M、未缓存 $0.14/M、输出 $0.28/M。费率冻结自 [MiMo-V2.6-Flash 官方模型价格页](https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash)，执行时账本记录复核日期、费率和所选币种。请求、失败预留和 unknown spend 写入本次唯一 V5 账本；本机持久 `pilot_registry.json` 阻止第二个 ledger 扩充 39 局上限。不得访问或修改 V2 已关闭账本。
- **AC-10**: 每局保存 Agent 可见 Trace、隔离的 judge metrics 与 run manifest；保存 prompt/completion/cache token、费用及币种（provider 可用时）、耗时、停止原因和失败分类；不保存密钥、完整思维链或原始模型响应。失败分类使用提纲中的统一编码；另以 `INPUT_BUDGET_EXCEEDED` 标记运行器在调用 Provider 前发现的输入上限保护，以 `UNCLASSIFIED_OUTCOME` 表示已有失败证据但不足以归到其他原因。成功局可保留其间发生的行为错误分类。
- **AC-11**: 报告分开呈现运行时离线证据、API smoke、能力对照和能力效度；报告每图成功率、专属指标、失败分类、配对差异与不确定性，不从少量样本给模型排名。
- **AC-12**: 最终文档包含运行约定、离线验收、pilot 实际 usage 和费用、逐图效度边界，以及其余 24 图的接入条件；不存在以 Oracle 成功替代模型或能力结论的陈述。

**预登记的条件矩阵**:

| 地图 | 条件一 | 条件二 |
|---|---|---|
| MAP-08 | 可做测试，不提供外部假设记录 | 可做测试，提供 Agent-owned 结构化假设表 |
| MAP-16 | 直接 ReAct | 相同 Observation，提供公开约束表 |
| MAP-18 | 告警关闭 | 告警开启，其他状态和规则相同 |
| MAP-22 | 最近 5 步公开历史 | 最近 5 步历史加 Agent-owned 地图记忆，并使用同一合法探索前缀单独核对返程 |
| MAP-26 | 自由诊断轨道，按 0/1/2 覆盖三种故障 | seed 0 的合法标准化失败后恢复轨道，分别测试完整错误反馈、隐藏错误反馈和结构化错误摘要；三种条件使用同一个由环境真实前缀生成的状态 |
| MAP-30 | A：完整公开历史；B：最近 5 步公开历史 | C：最近 5 步历史加四格结构化案卷；三条件共用固定调查前缀 |

MAP-26 的 seed 0 标准化恢复轨道包含完整反馈、隐藏错误反馈和结构化摘要三个条件，均从同一真实失败前缀分叉；隐藏错误反馈是信息剥夺条件，不能与等信息量的摘要对照混称。它属于独立诊断，不和三个自由诊断 seed 合并计为三个恢复样本。MAP-22、MAP-30 的固定前缀来自环境逐步回放；MAP-30 的三条件接收相同合法公开经历和当前状态，区别在可见历史窗口/案卷。

## Feature design

### Data model and runtime boundary

`scenario_v4` owns six typed environments, a V4 Action contract, a public Observation allowlist, reset/step results, terminal states, and a registry keyed only by the six approved map IDs. Agent requests contain the selected condition, the allowlisted Observation, and declared Agent-owned public history or memory. The V4 runner owns episode lifecycle and never hands judge state to an Agent.

The V5 run manifest records an opaque run ID, map ID and source hash, runtime commit, provider and model labels, seed, condition ID, request/token/cost reservations, and completion status. Each episode writes an Agent-visible JSONL trace and a separate judge metrics JSON file. The local V5 ledger records every reservation, provider outcome category, retry, checkpoint, and resume. All three live under ignored `runs/` or `results/` paths; secrets, raw provider responses, and full chain of thought are excluded.

### Decision request and response

The V5 runner calls the existing map-independent `DecisionProvider` once per decision and validates structured output against the strict V4 Action schema before stepping the environment. A provider response may include only the Action and explicitly declared Agent-owned memory updates. Model-specific prompt assembly, conditions, feedback handling, and V4 state stay outside the shared V3/Legacy agents and environments. Provider/model configuration is read from existing local settings; paid execution additionally requires `--execute-paid`, the exact `openai` provider, exact `mimo-v2.6-flash` model, a live budget ledger, and a passing frozen offline gate.

Only an explicit provider rejection that is documented as unbilled and reports zero usage may receive one recovery request per episode, after a bounded backoff of at most 5 seconds; the recovery must reuse the exact same request hash and is fully reserved. A timeout, connection loss, 429, 5xx, or other response whose billing/usage cannot be confirmed is `unknown_spend`: retain its full reservation, close the pilot, and do not retry. MiMo documents backoff for 429/500/503 but does not state that these synchronous failures are unbilled, so they remain fail-closed until billing semantics are documented. A completed response with invalid structured output is an Agent decision: the response usage is settled, the trace records `action: null` and an `invalid_output_reason`, and the Runner calls the map's invalid-action handler without fabricating an executable Action or issuing another provider request. Each map's handler applies its own action-time semantics. Backoff is included in episode and global wall-clock limits.

### Frozen measurement configuration and prefixes

The complete registered episode list contains 39 episodes: MAP-08 uses seeds 0/4/8; MAP-16, MAP-18, MAP-22, and MAP-30 use fixed-scene repeat labels 0/1/2 in every registered condition; MAP-26 free diagnosis uses 0/1/2 and its three recovery conditions each use seed 0. MAP-30's full-history control gets the complete ordered public action/result history and deduplicated public evidence/witness payloads, with no rolling truncation; the 8,192-byte input guard still applies. MAP-26's six episodes are a free-diagnosis track (three fault instances) and a standardized recovery track (three feedback conditions), not a balanced two-condition paired design. MAP-08/16/18/22/30 are paired by same seed and share the map's registered physical scene.

| Protocol item | Frozen value |
|---|---|
| Provider/model | OpenAI-compatible Xiaomi endpoint; `mimo-v2.6-flash` |
| Temperature / reasoning | temperature 0; reasoning disabled (`none`) |
| Output / context | strict V4 local Action validation; max output 1,024 tokens; recent-history conditions use the last 5 public actions; MAP-30 full-history condition receives the complete ordered public action/result history and deduplicated evidence/witness payloads; max 100 Agent decisions per episode; 8,192-byte input guard applies to all |
| MAP-08 hypothesis table | B/D/F starts uniform; only model-authored updates grounded in currently observed X/Y test results are accepted; no external oracle or prior is injected |
| MAP-16 constraint table | Derived only from the current public route, capacities, reservations, and public goal fields |
| MAP-22 shared prefix | First 12 movement directions from `planning/hand_traces.json` → `strategies.external_graph_memory_euler_tour`; both conditions receive identical physical actions and observations; the memory condition records only locally inspected node pages and traversed edge pages; ends at L on tick 12 |
| MAP-26 recovery prefix | First 7 actions from `planning/hand_traces.json` route `feedback_then_correct`; environment replay must end at A/tick 7 with one uninstalled spare, a failed `power_regulator` replacement, and the true antenna fault still recoverable; feedback is the only condition difference |
| MAP-30 shared prefix | `planning/hand_traces.json` route `event_by_event_archive_first`, excluding its final formal accusation; both conditions stop at J before terminal accusation with the same four discovered casebook entries |
| Price and protocol binding | Paid execution requires explicit CNY or USD; the frozen offline gate binds runtime, all six map-source hashes, prompt/condition/schema hashes, prefix-source hashes, and validation results. Any change invalidates the gate and requires a new offline run before paid calls. |

The MAP-22 design Oracle preloads future map facts before exploration and is not a legal model prefix. It remains unchanged as a source artifact; the V5 paired prefix above is grounded by live environment observations and is recorded as a design discrepancy without changing the map's win condition.

### Value sourcing

| Value | Source |
|---|---|
| Map IDs, initial and private state, transition rules, terminal conditions | The six reviewed `worlds/v4/MAP-*/map_spec.yaml` and `evidence_or_rules.yaml`; runtime constants are checked against their source hashes |
| Legal actions and public Observation fields | Each map's `acceptance.md` and `tests/ACCEPTANCE_CASES.md`, plus explicit runtime allowlists |
| Oracle actions and expected public observations | The corresponding `oracle_trace.jsonl`, used only by offline validator fixtures |
| Failure mechanisms and MAP-26 recovery prefix | `failure_traces/cases.yaml` and an environment-generated replay prefix |
| Seed-to-variant mapping | MAP-08 and MAP-26 source specifications; MAP-16/18/22/30 fixed deterministic scenario definitions |
| Condition IDs, Agent memory policy, shared exploration/evidence prefixes | This spec's pre-registered condition matrix and deterministic prefix replay |
| Provider, model, API endpoint, local timeout and credentials | Existing local `.env`/`RuntimeSettings`; secrets remain process-local and are never emitted |
| Token caps, per-episode limits, retry count, global spend ceilings | AC-9 and the V5 pilot ledger policy below |
| Runtime version, start/end times, status, stop reason, and hashes | V5 runner and run manifest, derived from actual execution |
| Model usage, latency, errors, and cost | Provider response usage and elapsed-time measurement; absent or ambiguous usage is recorded as unknown and fully reserved |
| Capability metrics, success, failures, censoring and paired differences | Private judge state plus public trace and registered pair identity; no Oracle-derived model outcome is permitted |

### Critical test scenarios

| Scenario | Acceptance criteria |
|---|---|
| Prompt and export scans reject private answers, future events, hidden evidence, Oracle routes, keys, and raw responses | AC-2, AC-10 |
| All six hand-written Oracles replay against the actual runtime and public fields match at every step | AC-3, AC-4 |
| At least three distinct failure mechanisms per map, boundaries, terminal immutability, and deterministic repeats | AC-3, AC-5, AC-6 |
| Independent MAP-08 signature enumeration, MAP-16 BFS, MAP-18 schedule/accounting, MAP-22 graph solver, MAP-26 spare recovery, and MAP-30 evidence reachability agree with runtime | AC-6 |
| A Fake provider dry run cannot spend; a real call is refused unless paid mode, provider/model match, offline gate, and all limits pass | AC-8, AC-9 |
| Reservations include retries; provider uncertainty, token cap, episode timeout, global timeout, or error cap closes the ledger before another call | AC-9 |
| Resume recovers only an incomplete V5 checkpoint and cannot duplicate a charged decision or reopen a terminal episode | AC-9, AC-10 |
| Paired conditions share the registered seed and fixed public prefix; hidden feedback is reported as information deprivation | AC-7, AC-11 |
| Reports label repeated fixed maps, small sample uncertainty, censoring, and validity limits | AC-11, AC-12 |

### Metrics and analysis rules

| Map | Episode metrics | Analysis boundary |
|---|---|---|
| MAP-08 | diagnosis accuracy, wrong repair, first test station, tests run, pressure at finish, repair tick; independent signature enumeration reports prior/posterior entropy and information gain | Report B/D/F separately. The three seeds deliberately cover three fault locations, not a random population sample; show exact counts and no population confidence interval. |
| MAP-16 | success, makespan, gap from BFS optimum, each reservation/capacity conflict, deadlock count | Same-scene seed labels are execution repeats. Report per-repeat outcomes and descriptive paired differences only. |
| MAP-18 | delivered passengers/service rate, delay person-ticks, first recovery tick, recovery duration, rejected/unsafe schedule counts | Pair alert-on/off at each label. The three labels are fixed-scene repeats, not independent samples. |
| MAP-22 | found/returned status, movement steps, unique nodes/edges, repeated visits, memory facts, return-route gap | The shared 12-move prefix makes this a return-memory comparison; it does not measure exploration efficiency. Same-scene labels are repeats. |
| MAP-26 | free diagnosis: diagnosis actions, wrong replacements, spares retained, outcome; recovery: first correction after feedback, repeated same-part errors, recovery outcome and remaining spares | Keep the three seeded free-diagnosis faults separate from the three seed-0 feedback branches. Recovery branches have one fixed-prefix episode each and are descriptive only. |
| MAP-30 | Q4 recall after gap, four-entry casebook completeness, evidence-source count, claim accuracy, timeline consistency, unsupported accusations, finish tick | Same investigation prefix isolates evidence recall and submission caution. Three scene labels are repeats, not independent cases. |

All denominators, censored runs, provider errors, actual reported usage, reserved costs and unknown usage are reported explicitly. Five matched maps show exact same-seed condition differences; MAP-26 feedback branches are not paired as independent cases. No model ranking or general capability claim is made from this pilot. Uncertainty is stated through sample-unit and fixed-scene limits; inferential intervals are omitted where their independence assumption would be false.

### Independent review disposition

On 2026-10-15, a second-model read-only review of the initial 36-row design identified ambiguities in matrix closure, condition and prefix definitions, price and offline-gate binding, retry accounting, smoke release criteria, metric/report scope, solver independence, and malformed-action handling. Those findings were fixed and individually reviewed. A subsequent cross-check against the user-provided outline found that MAP-30 condition A (complete public history) had been omitted from the initial matrix. This version registers the outline's A/B/C conditions for MAP-30, expanding the exact generator to 39 rows while preserving the user's six-map boundary and three-seed-label limit. The 2026-10-16 second-model review approved the expanded matrix and budget after fixing the Stage B count, MAP-30 legal evidence visibility, and manifest context-policy metadata. The offline freeze gate passed on runtime commit `e440cc1b599a5de4a57650f418d78b03c4746399`. The registered MiMo pilot then stopped during its first Stage B episode after 70 consecutive `INVALID_ACTION_SCHEMA` decisions; the 71st request was unresolved at interruption, so AC-9 closed the pilot for unknown spend. The ledger records 0/39 completed episodes, 38 not started, no accepted smoke gate, and no Stage C execution. The pilot registry forbids a successor ledger after closure; this spec remains In Progress.

## Options considered

### Option 1: 扩展 V3 场景契约

将六图映射进现有 `ScenarioAction`、`ScenarioObservation` 和 `ScenarioEnvironment`。

**Pros**:
- 复用已存在的 selector、Runner 和 Trace 类型。
- 需要新增的代码较少。

**Cons**:
- V3 公开字段和单步转移假设不能表达部分 V4 时钟、裁判状态及行动成本。
- 容易让两种版本共享或误解同一 Action contract。

### Option 2: 在现有 Provider 边界旁新增隔离的 V4 运行时

新建 V4 Action/Observation、地图环境和 V5 Runner，只复用不持有地图状态的 `DecisionProvider` 和通用 provider/token budget。

**Pros**:
- 保持六图规则与 V3、Legacy 隔离。
- 不改造已有 Agent、Trace 和 selector 的固定语义。
- 可按地图实现不同的 tick 与并发结算。

**Cons**:
- 需要维护一套小型 V4 runner、Trace 和 Memory 输入格式。
- Provider token budget 可复用，费用与 episode 语义仍需在 V5 明确登记。

### Option 3: 为六关新增统一模板环境

用相同的一步动作循环和通用状态容器描述全部地图。

**Pros**:
- 公共代码和 Agent 接入较为统一。

**Cons**:
- MAP-16 同步预约、MAP-18 联合时刻结算和 MAP-08 持续压力会被错误压平成普通步进。
- 很难证明模板没有改变各图原有的胜负和动作成本。

## Decision

**Chosen option**: Option 2: 在现有 Provider 边界旁新增隔离的 V4 运行时。

六图使用独立的 `scenario_v4` contract、环境类、allowlist 注册表、episode runner 和分层 Trace；仅复用地图无关的 Provider 与请求预算部件。按 V4 原设计实现条件对照，完成离线门禁后再调用本机配置的 `mimo-v2.6-flash`。

## Rationale

六关规则之间有不可统一的时钟、同步移动、空间记忆和调查证据约束。保持版本隔离比改造稳定的 V3 契约更容易审计，也可以先做一条完整的离线回放闭环，再增加真实 Provider pilot。

用户指定每图最多三个 seed。MAP-08/16/18/22 四张两条件地图各有 2 条件 × 3 seed 共 24 局；MAP-30 有完整历史、最近 5 步和案卷条件各 3 seed 共 9 局；MAP-26 有 3 个自由诊断 seed 和 seed 0 上 3 个反馈条件共 6 局，合计 39 局。六图 seed 0 smoke 均复用矩阵内 episode。单局最多 100 个 Agent 决策和 1 次恢复重试，最多 101 次请求尝试；每次最多预留 8,192 个输入 token 与 1,024 个输出 token。按 CNY ¥37.50 / USD $5.25 全局费用硬上限计算，最多 3,662 次请求与 33,748,992 个预留 token；这低于 39 × 101 的逐局理论请求上限。单局 Provider 墙钟最多 12 分钟，整个 pilot 最多 240 分钟。CNY 的单次/全局最坏预留为 ¥0.01024 / ¥37.49888；USD 为 $0.0014336 / $5.2498432；两种账单币种不换算、不叠加。请求计数含重试。usage 不可用或状态不明时按完整请求预留额计入，unknown spend 立即关闭 pilot。单个 episode 在一次恢复重试后如仍有错误即终止；两个连续 Provider 请求错误也关闭 pilot。费用估算不代表账户余额、优惠或 Token Plan 额度。

## Build plan

1. 定义严格的 V4 Action、Observation、step result、终止状态、hash 和六图 allowlist 注册表，不改变 V3/Legacy，满足 **AC-1**、**AC-2**、**AC-3**。
2. 按 16、08、22、26、18、30 实现各自规则、公开视图和裁判状态；将 MAP-26 标准化失败前缀由真实环境执行，满足 **AC-3**、**AC-4**、**AC-5**。
3. 实现 V5 runner、Agent 请求上下文、Agent-owned history 与记忆条件、分层 Trace、judge metrics 和 run manifest，满足 **AC-2**、**AC-7**、**AC-10**。
4. 实现每图边界与失败测试、Oracle 真回放、seed hash 检查、观察泄漏扫描及独立求解器；全项目回归通过后解除 API 门禁，满足 **AC-4**、**AC-5**、**AC-6**。
5. 冻结 conditions、温度、提示词、完整 episode 列表、固定前缀与单价；实现默认 Fake/dry-run 的 V5 pilot、有限重试、resume、费用估算和 fail-closed 账本。真实调用先跑六图 smoke，完整核验 trace、usage、metrics、manifest 与账本后才放行剩余矩阵；汇总逐图指标与配对差异，满足 **AC-7**、**AC-8**、**AC-9**、**AC-11**。
6. 完成运行时、validation、pilot、效度和其余 24 图文档，运行项目质量检查并同步 Scope 与工程日志，满足 **AC-10**、**AC-11**、**AC-12**。

## Migration plan

**Strategy**: side by side。

**Phases**:
1. 在新 package、CLI script、trace 名称和本机 V5 ledger 中加入 `scenario_v4`，不修改现有 V3/Legacy 运行数据。
2. 六图离线验收全绿后，单独启动 V5 pilot；暂停或重跑只从本 V5 ledger 的持久化 episode checkpoint 决定。

**Rollback**: 回退本次新增 V4 代码和脚本即可；原有 V3/Legacy 代码、runs、results 和已关闭 V2 ledger 不迁移。

**Risks**: V4 单独的 Runner、Trace 与 agent-owned memory 会增加少量重复实现；如果 Agent request 或导出 trace 混入裁判状态，必须停下相关地图，不运行 API。

## Consequences

**Positive**:
- 复杂地图时钟与私有真值在自己的 contract 中表达。
- 运行时正确性、模型行为和能力效度分别报告。
- API 请求有可审计的上限、账本和恢复点。

**Negative / tradeoffs**:
- 需要维护独立 V4 Runner、Trace 解析和 prompt 输入，不能直接套用 Legacy MemoryAgent。
- 预设的 100 动作限制会删失超长 episode；不得把删失记录当作最终失败或模型能力下界。

**Neutral**:
- 新数据只写入本机 `runs/` 与 `results/`，生成数据按项目约定默认不入 Git。
- 固定地图上的重复 seed 只能测执行稳定性，不能支持泛化推断。

## Follow-up

- [ ] 如果六图 API 结果显示测量敏感性，再独立规划其余 24 图的运行时接入；本规格不实现它们。

## References

**Project sources**:
- 用户提供的 `研究提纲/V5能力测量体系测试.md`。
- `worlds/v4/README.md` 与 MAP-08、16、18、22、26、30 的设计、规则、Oracle 和验收材料。
- `docs/architecture.md`、`docs/specs/0017-world-redesign-v3/index.md`、`docs/specs/0015-v2-provider-budget-guard/index.md`。

**Links**:
- [Xiaomi MiMo-V2.6-Flash 官方价格与 API 接入](https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash)。
- [Xiaomi MiMo Batch API 价格说明](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/batch-api)。
