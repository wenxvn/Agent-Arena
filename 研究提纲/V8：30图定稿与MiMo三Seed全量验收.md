# V8：30图定稿与MiMo三Seed全量验收

> 执行 Agent：DeepSeek V4.1 Flash  
> 仓库：https://github.com/wenxvn/Agent-Arena  
> 阶段目标：**30 张独立设计的地图全部规则冻结、运行时可玩、指标可计算；MiMo 对每张地图完成 3 次有效独立运行，总计 90 局，形成完整可审计结果。**  
> 用户授权：**允许 DeepSeek 自主调用 MiMo API 进行本 V8 任务所需的测试，无须逐批重新询问**。授权仅覆盖本项目的 MiMo 测试，不覆盖其他模型、无上限费用或任意重跑。必须先实施预算上限、失败停止与账本保护；若未获用户给定的明确金额上限，先以 **人民币 ¥10 总费用硬上限**作为 V8 暂定安全上限，接近上限时停止并向用户申请提高，**不得自动突破**。不得把既有 V5–V7 支出混入 V8 账本。

## 0. 首要原则与不允许的捷径

1. **不批量生成换皮地图。** 逐图阅读 `worlds/v4/MAP-XX/{DESIGN.md,map_spec.yaml,evidence_or_rules.yaml,oracle_trace.jsonl,acceptance.md}` 与 `docs/v7/maps/MAP-XX.md`、`docs/v7/pending-runtime/MAP-XX.md`（若存在），确认独特状态机、因果机制、动作、失败、指标。通用接口可复用，玩法逻辑不可复制改名。
2. **不是以 MiMo 通关为目标修改地图。** 规则先冻结，再测 MiMo。失败可以是合法结果；不可解、接口不明、隐藏信息泄漏、无效 Trace 不可作为正式结果。
3. **10 世界×3 难度不等于可跨地图比较的同一量表。** 各图独立主指标，简单/中等/困难需体现认知负担差异；不能将步数、资源消耗、成功率直接相加排名。
4. **固定正式版本。** 每图的 scenario/rules/prompt/metrics/Oracle hash 与 commit 在正式运行前冻结；测试后修改即新版本，旧结果不得静默挪用。
5. **只读历史。** 不改写 V2/V4/V5/V6/V7 的历史 trace、账本、实验注册与已关闭实验；V8 新建隔离目录。
6. **严禁伪造验证。** 设计、Oracle 回放、离线模拟、真实 MiMo 调用分开报告；不把 Seed 当作独立场景实例。
7. **用户已授权 MiMo API 测试**，但只允许在通过离线门禁、预算/计费保护和预登记后自动执行。任何 unknown spend、连续 provider 错误或预算风险都应 fail closed。

## 1. 当前基线（开始时必须重新核查，不得盲信）

- V7 最新已知提交 `e81d5dc`（2026-10-17）：30 张独立指标卡、154 项 MetricSpec；MAP-08/16/18/22/26/30 六图共 44 项指标已实现；其余 24 图 110 项仍 design-only。
- V7 649 pytest passed、29 个 V6 实例离线回放、六图 36 条手工 fixture；V7 Pilot-001R 12/12 真实 MiMo 局完成（6/12 success），**不计入 V8 正式 90 局**。
- 12 项 V7 DCR proposed；MAP-05 时间窗不可行、MAP-20 损耗 10%/20% 冲突、MAP-25 失败码不一致等须优先处理。
- V7 的 `human_approved` 总体字段与逐项清单“待审”存在不一致；不能把总字段当作所有规则变更已批准。对 DCR 采用**明确证据 + 保守裁决 + 独立审计记录**，重大玩法分歧交用户决定，未决地图不得定稿。
- 先执行 `git status --short`、`git rev-parse HEAD`、`git log -10 --oneline`，逐项确认是否已有 V8 进展。

## 2. 验收定义与交付物

每张地图的生命周期：`design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized`。任一阻塞则标 `blocked`，不能靠文档覆盖。

### 每张地图必交

- `docs/v8/maps/MAP-XX-final.md`：设计差异、机制、难度、公开/私有字段、动作契约、结算顺序、胜负/失败码、资源边界、主要指标 1–2 项、护栏、失败归因、与同世界另两图区别、未决问题。
- 可执行 runtime 与注册入口；复用公共 `Action/Observation/Trace` 形状，**保留各图独立逻辑**。
- Oracle 成功轨迹可真实重放；可行解不冒充最优解。复杂图尽可能附独立求解器或可行性证明。
- 至少 **3 个机制特有失败、2 个边界、1 个终止后不变性、1 个无泄漏、2 个手算指标 fixture**；每图真实环境回放通过。
- 指标 extractor：`MetricSpec` 来源字段、单位、范围、分母、方向、缺失/截尾规则；没有来源时 `UNAVAILABLE` 而非 0。
- 正式 MiMo 3 局的 trace、judge metrics、V8 metrics、usage/cost、seed/run metadata、冻结 hash、失败原因。

### 全局必交

`docs/v8/README.md`、`baseline-audit.md`、`dcr-resolution.md`、`runtime-matrix.md`、`metric-matrix.md`、`offline-validation.md`、`mimo-preregistration.md`、`mimo-90-results.md`、`failure-analysis.md`、`final-acceptance.md`；以及机器可读 `runs/v8/registry.json`、每局不可覆盖的运行产物、自动汇总脚本。结果表应包含 30×3=90 行（若中断则列明缺口，不能称 90 完成）。

## 3. Batch 0：事实审计与 DCR 冻结

逐图核对 V4/V7 规格与现有实现，建立 30 行 `runtime-matrix`，字段包括：`world,map,difficulty,construct,design_status,runtime_status,metric_status,oracle_status,blocking_dcr,rule_hash,review_status`。

DCR 决策必须区分：①纯命名/文档矛盾，可依据权威规则做无语义修复；②可证明不可行/冲突，先给最小变更及反例；③会改变能力构念/难度/胜负条件，**暂停该图并向用户确认**，不可自行偷偷改。至少重点审计：MAP-01 bridge confirmation、MAP-05 三束信号窗口、MAP-06/11/21 先验信息、MAP-07/09 级联仪表、MAP-12 日结算、MAP-17 多目标胜负、MAP-20 旁路损耗、MAP-25 失败码、MAP-27 部分完成、MAP-29 矛盾计数。

**验收**：30 行真实状态，12 项 DCR 各有决策、证据、影响和回归；未解决项显式 `blocked`。

## 4. Batch 1–10：按世界逐图完成，不批量换皮

**每次只推进一张地图至 runtime+metrics+offline gate，之后才开始下一张。** 一个世界内三图分别有独立验收，不允许“共享成功”代替。已实现的六图也必须重新冻结、回归并校验难度，不可跳过。

| 批次 | 世界与地图 | 每张地图独立的机制焦点与验收 |
|---|---|---|
| 1 | 飞船 MAP-01/02/03 | 01 修补→供氧依赖、氧气停供时长；02 单向闸门与救援/导航双目标，不合成任意权重；03 五阶段里程碑与早期一次性代码记忆，区分阶段遗漏/代码错误 |
| 2 | 灯塔 MAP-04/05/06 | 04 潮相与灯芯搬运窗口；05 三束信号共享电力/窗口排程，先证明窗口可行；06 风险预算下的观测与天气预测，严格区分先验与后验 |
| 3 | 深海 MAP-07/08/09 | 07 三舱阀门净流量与二次传播；08 主动诊断与信息增益，处理现有天花板但不为降低通过率乱改；09 电力→泵→氧气级联与因果传播规模 |
| 4 | 极地 MAP-10/11/12 | 10 分仓燃料、供热与通讯窗口；11 噪声侦察与路线风险，控制公开信息；12 多日供热/口粮库存与欠供，冻结结算顺序 |
| 5 | 金字塔 MAP-13/14/15 | 13 符号约束与错误重置；14 受限问询下九态真值表；15 训练规则→未见状态迁移，不能用首次选择替代明确预测而不标代理局限 |
| 6 | 地铁 MAP-16/17/18 | 16 同步会车容量与交换冲突；17 多目标客流/换乘与 Pareto 向量；18 闭塞预警与故障重规划，明确静态调度地板，故障不能被无条件提前发车规避 |
| 7 | 火山 MAP-19/20/21 | 19 阀门延迟与温度越界面积；20 多节点冷却流量守恒、旁路损耗；21 不确定热风险与测量，拒绝用私有精确温度泄漏给 Agent |
| 8 | 丛林 MAP-22/23/24 | 22 合法探索记忆与返程，图记忆只记录亲历边；23 补给与侦察的成本/价值；24 桥断与潮窗动态改道，分开测路径效率与恢复延迟 |
| 9 | 月球 MAP-25/26/27 | 25 气闸安全→EVA→维修单链；26 故障诊断与 rollback 纠错，恢复地板单独标注；27 货舱、救援、中继、采样多目标资源冲突，部分完成单列 |
| 10 | 古堡 MAP-28/29/30 | 28 多来源证据支撑指控；29 证词矛盾发现与有限问询；30 完整调查与长期证据召回分别报告，不混为一个能力 |

### 每张地图的固定开发循环

1. 阅读五类原始文件与 V7 指标卡，手写独立状态转移表，解释**与同世界其他两图的真实机制差异**。
2. 先实现最小真实可玩切片，再完整补齐机制；动作合法性、公开 Observation、私有裁判状态、时间/资源结算顺序逐条单测。
3. 构造成功 Oracle 并通过真实 `step` 回放；失败/边界与停止条件逐条回放。
4. 实现本图所有已注册指标，保留 `valid/not_applicable/censored/unavailable/invalid_trace` 五态，附精确手算 fixture。
5. 泄漏测试、回归测试、指标稳定性检查，生成 `MAP-XX-final.md`，状态更新后才开始下一张。

## 5. Batch 11：30 图离线统一门禁

必须通过：全量 pytest、作用域 Ruff/mypy、30 图 Oracle replay、每图独特失败/边界/终止测试、指标复算、泄漏扫描、相同初态确定性重放、Runner smoke、费用预估 dry-run。全仓既有 lint 问题单独报告，不得通过大范围重写冻结 V4 资料掩盖。

**反作弊式检查**：抽查三组同世界地图的状态变量/动作/失败因果图，若只是名称替换则退回；抽查至少 6 张新地图的 Oracle 与指标由第二条独立实现路径核对。30 图应有专属场景规则，而非共享同一图的 30 套数值。

难度检查：每世界简单/中等/困难应在可见性、依赖深度、动态性、资源耦合、记忆跨度、分支复杂度中有可解释差异；不要求 MiMo 成功率单调，但若简单全失败、困难轻松通过，应先检查构念与接口是否失衡，不得直接按结果调难度。

冻结产物：`runs/v8/freeze_manifest.json` 包含 30 图的 `scenario_hash,rule_hash,prompt_hash,metric_schema_hash,oracle_hash,commit`。任何更改重新冻结受影响地图；不得将不同 hash 的局混进同一正式三次运行。

## 6. Batch 12：MiMo API 三次运行（用户已授权）

### 6.1 预登记

- 模型：当前已连接且可用的 **MiMo** 模型；优先复用 V7 `mimo-v2.6-flash` 及其现有 provider adapter，核实真实模型 ID、定价、是否支持 `seed`、temperature、reasoning 和 JSON mode；不得臆造 API 能力。
- 正式样本：每张固定地图 **3 次独立 episode**，30×3=90。建议 `seed=0,1,2`；若 provider 不支持 seed 或 temperature=0 导致 seed 无效，则记为 `replicate_id=0,1,2`，如实注明“重复运行而非有效采样 Seed”，并评估用户目标是否需模型侧 seed 支持；环境随机 seed 不得改变冻结地图的核心规则。
- **单一正式条件**：每图固定一套默认 Agent 配置、prompt、预算和资源；V5–V7 消融条件不混入 90 局。每图专属动作说明允许不同，但同图三次必须相同。
- 不为失败增加步数或换提示词；预登记每图 `max_decisions/max_ticks/max_tokens`，以及 schema、provider、未知费用停止条件。
- MiMo 实验仅使用公开 Observation；Oracle、隐藏真值、裁判指标和求解器路径不得进入 prompt。

### 6.2 成本和失败保护

- 用户已允许 DeepSeek 自行调用 MiMo API；**不需要逐批再次征求调用许可**。
- **V8 默认总费用硬上限 ¥10**（仅在用户未另行指定额度时使用），建议预警阈值 50%/80%，达到上限前主动停止；费用需按实际供应商报价计算，不以 V7 极低成本推定 V8 一定同价。
- 使用独立 append-only ledger；每次请求前 reserve 最坏情形费用，成功后 settle；未知消费 `unknown_provider_spend` 时立即停止、封存现场，不自动重试；连续 3 次 provider/schema 故障停止当前批并审计。
- 每世界 9 局、每张地图 3 局作为 checkpoint；仅在离线门禁全绿且预算可用时继续。
- 允许因**传输/供应商中断**补跑未完成 episode，但必须保留原失败记录、独立 run ID、费用记录；**模型正常失败不补跑**。
- 费用达到硬上限或供应商不可用时，报告已完成数与剩余缺口，等待用户决定，不得虚报 90/90。

### 6.3 每局不可缺字段

`experiment_id,map_id,world,difficulty,scenario_hash,rule_hash,prompt_hash,metric_schema_hash,commit,model_id,provider,temperature,seed_or_replicate,run_id,condition_id,decision_budget,status,success,termination_reason,agent_trace_path,judge_metrics_path,v8_metrics_path,input_tokens,output_tokens,requests,cost,currency,provider_error,unknown_spend`。

所有结果在独立目录保存；账本与结果汇总可由脚本重新生成。记录每图 3 局原始指标、均值/范围、有效分母、截尾、无效轨迹、失败归因。**n=3 不做显著性断言**。

## 7. Batch 13：逐图定稿与最终报告

逐图验收：`design_frozen && runtime_verified && metrics_verified && three_valid_mimo_runs` 才标 `finalized`。**MiMo 通关不是必要条件**；三次失败但合法可解释也能定稿。若三局都因接口误导或无效 schema 失败，则修复后重新冻结重跑，不能计入原正式版本。

最终报告必须给出：

1. 30 行地图定稿表：世界、难度、独特机制、规则 hash、运行时/指标/Oracle/审阅状态。
2. **90 行真实 MiMo 结果**：3 局/图，逐局原始记录链接、成功/失败/截尾、主指标与安全护栏、成本。
3. 每图单独解释“同样未通关但部分能力不同”的例子；每世界三难度分面，但不把不同地图的原始指标强行比较。
4. 30 图的难度/玩法差异审计与 DCR 决议清单。
5. Oracle/合法随机/规则启发式基线：若未实现则明确缺失，**不可把 Oracle 成功率当成 MiMo 能力**。
6. 失败类型分布、地板/天花板、资源消耗、Token/费用、提供方异常、泄漏审计。
7. 未解决风险与后续 V9 研究建议；不得为达成“90/90”掩盖阻塞。

## 8. Agent 分批提交与停机条件

- Batch 0、1–10、11、12、13 每批独立 commit、独立验收日志。每完成一张地图记录 commit、测试命令与输出、Oracle 长度、指标 fixture 断言和剩余阻塞。
- 不要一次性生成 24 张 runtime 再统一调试；不要一次性提交 110 个返回常数的 extractor。
- **必须暂停并向用户提问的情况**：需要决定改变核心胜负/能力构念的 DCR；预算需突破 ¥10；无法确认 MiMo 计费或 provider 状态；发现隐藏真值泄漏或 Oracle 不可解且无无语义修复方案。
- 若发现当前仓库已有新进展，优先复用真实成果、修订状态矩阵，避免重复实现；不能因为文件存在就认定可玩。

## 9. 给 DeepSeek V4.1 Flash 的最终执行指令

> 先读取最新仓库并建立真实 30 图状态矩阵，然后按世界逐张实现、逐张验证、逐张冻结。你已获得用户对本 V8 所需 MiMo API 测试的许可；通过离线门禁和费用保护后，可自主进行每图 3 次真实 MiMo 测试，无需每批征求许可。不得超过 V8 ¥10 暂定硬上限，不得把历史 Pilot 算进正式 90 局。30 图必须拥有不同机制、可运行规则、Oracle、专属指标和失败边界。对无法定稿的地图如实标注阻塞，不准伪造测试、不准通过换皮凑数。最终以 30 图定稿清单、90 局原始记录、完整账本和可复现验收报告交付。
