# V10：30图核心机制重构、难度校准与多Seed有效性验证

> 执行者：DeepSeek V4.1 Flash；项目：`wenxvn/Agent-Arena`。本文件是**可执行工程与研究验收规格**，不是要求生成另一份空泛报告。开始前必须拉取并审计最新 HEAD；所有数字以最新仓库可复算证据为准。
>
> 用户授权：**允许自主调用 MiMo API 开展必要测试**，不必每批再次征求许可；但必须遵守费用上限、预登记、幂等与异常停止规则。默认 V10 **累计已知结算+预留预算上限 ¥10**，不得通过拆分账本规避；未知费用或预算账本异常立即停止付费调用并继续离线工作。不得擅自使用其他收费模型。

## 0. 任务背景、目标与不可改变的事实

V8 已交付 30 个运行时、154 项注册指标和 90 次 MiMo 重复测试（固定环境 seed=0，replicate 0/1/2），成功 17/90。V9 已完成 30 图逐图审计，报告状态为：VALIDATED 7 图（01/02/05/16/17/25/27），NEEDS_MORE_EVIDENCE 8 图（07/08/09/10/11/12/13/26），NEEDS_REDESIGN 13 图（04/06/14/15/19/20/21/22/23/24/28/29/30），BLOCKED 2 图（03/18）。V9 有 55 条 Oracle、600 次随机、30 图公开启发式、120 条独立复算，以及 27 次有效 MiMo pilot、2 次 provider 中断。**这些是起点，不得未经复算直接宣布已经解决。**

V9 构念标签另有 FORCED 8、OPTIONAL 5、BYPASS 11、BLOCKED 6；与上述四态分类并非同一维度。V9 的 `agent_reviewed` 不等于用户人工批准。V8/V9 原始日志、哈希、实验账本和报告必须只读保留。

### V10 唯一主目标

**让 30 张手工地图在真实可执行的前提下，具备可证伪、可重复、具有区分度的 Agent 能力测量机制；修复真正的构念旁路、接口阻塞和指标语义问题；建立多环境 Seed 的有效性证据。**

本阶段**不增加地图、不换皮、不追求 MiMo 高通关率、不为好看而改变难度标签、不声称三次运行具有统计显著性**。尽可能完成 30/30 的研究验收；若证据不足，必须保留阻塞状态和未完成项。

### 成功判据

1. 30/30 地图均有完整、逐图独立的 V10 规格：目标构念、最小可观察行为、隐藏信息边界、合法动作、失败与成功条件、反事实消融、主次指标、可行性证据。
2. 先解决 MAP-03、18、06、15、21 五个 P0 机制缺陷；再解决古堡 28–30 和其余 23 张未验证地图。**所有规则变更需 DCR、版本哈希、对照和迁移测试**。
3. 不再存在未经解释的 `BLOCKED`；每一条 `BYPASS` 都须有修复证据，或正式裁定为合法替代策略并以连续指标区分质量。
4. 154 项 V7/V8 指标保留历史版本；逐条审查 V9 发现的 13 项定义/事件问题，并为正式 V10 指标建立版本化 schema、独立计算与 fixture。
5. 至少 3 个**不同环境 Seed**用于每张地图的离线可行性、机制触发和基线测试；P0/高风险图建议扩展至 10 Seed。MiMo 有界复测必须记录环境 Seed 与重复编号两个独立维度。
6. 形成可重放、可审计的 `docs/v10/final-report.md`、30 图状态矩阵、对照实验表、逐图审计卡及所有证据索引；不得把 pilot 写成正式统计结论。

## 1. 必须遵守的工程与研究约束

- **冻结旧版本**：V8/V9 的 `runs`、结果、manifest、hash、DCR 和报告不修改、不覆盖、不补写成 V10 结果；V10 新目录独立管理。
- **真实手工设计**：10 世界 × 3 难度的世界身份、独特动作因果和玩法必须保留。不得统一改造成模板状态机，也不得为提高通关率删掉关键挑战。
- **防泄漏**：Observation 只包含模型在该时间点应当知道的信息；Oracle、真值、未来事件、私有判据不得出现在 prompt、工具 schema 或 trace 的 agent-visible 部分。
- **接口透明不等于答案泄漏**：公开合法动作枚举、对象名称、单位、资源结算、可观测反馈；不公开隐藏事件答案、最佳路线或未来随机种子。
- **不能只靠通关率**：成功率、成本、非法动作率、时间、资源、主指标和机制触发覆盖率分别报告；区分任务目标与构念质量。
- **严禁成功挑选**：预登记固定 seed/配置/预算；失败、截尾、异常和无效局全部保留；任何补跑必须新 run_id 和原因。
- **真实独立 Seed**：区分环境 seed（改变场景实例）、policy seed（随机基线策略）和 replicate（相同条件重复）；检查 MiMo API 是否支持生成 seed，若不支持不伪称模型随机种子。
- **授权付费但有界**：允许调用 MiMo，默认总上限 ¥10（含预留）；不得调用其他收费 API；unknown provider spend、重复扣费风险、限流/5xx 连续异常立即暂停付费，保留账本并做离线审计。
- **禁止只生成报告**：每批必须产出可运行代码、测试、实际 trace/fixture、可复算结果与文档；未解决问题必须诚实标记。

## 2. Batch 0：最新仓库与证据审计（先做，禁止直接改代码）

1. 记录 HEAD SHA、当前工作树、Python/依赖版本、V8/V9 冻结哈希；读取 `docs/v9/final-report.md`、`construct-validity.md`、`map-status-matrix.md`、`metric-independent-check.md`、`intervention-register.md`、所有 DCR 与 `docs/v9/maps/MAP-XX-audit.md`。
2. 核对 V8 90 局索引与 V9 29 条记录（27 有效 + 2 provider 中断）的真实可访问性；若 `runs/` 未纳入 Git，明确哪些可本机复现、哪些只剩摘要，绝不声称拥有不存在的原始 Trace。
3. 运行当前 pytest、ruff、mypy、离线 Oracle/随机/启发式及指标独立复算，记录实际命令、退出码和差异。
4. 为 30 图生成机器可读状态矩阵：`map_id,world,difficulty,claimed_construct,construct_status,validity_status,defect,dcr_id,rule_hash,metric_hash,environment_seeds,oracle,baseline,ablation,mimo,decision`。
5. 形成 `docs/v10/baseline-audit.md`、`docs/v10/decision-register.md`，明确**规则变更候选**与**只修接口/指标**的区别。

**Batch 0 Gate**：证据索引、冻结清单和优先级矩阵完整；若原始 Trace 缺失，先恢复或明确不可复算边界，不得虚构。

## 3. Batch 1：P0 两张阻塞地图 MAP-03 与 MAP-18

### MAP-03 飞船·最后的百步：真正测长期记忆

现状：关键 tag 可临近终点读取，导致“长期召回”可被绕过。设计**明确分隔的信息获取阶段与远期调用阶段**，例如初期获得一次性代码、后续经过不可跳过的任务阶段并关闭回读通道；同时提供合法的 agent 记忆/笔记通道，不应仅测试上下文长度或隐藏规则。定义 `memory_gap`（间隔动作数/事件数）、读取次数、合法写入/检索、召回准确率与阶段完成度。确保不存在后期直接读 tag 的旁路；做 `no_memory`、`late_read`、`random_guess` 消融。至少 3 环境 seed，含不同代码与路径；Oracle 每个 seed 成功，无法记忆的策略应明显受损，但不要硬编码要求失败率 100%。

### MAP-18 地铁·故障传播：真正测动态恢复

现状：`step_limit=12` 与环境 horizon/恢复动作相冲突，部分路径可跳过恢复。明确分离：环境物理时钟、动作预算、服务窗口、故障触发时点；避免用 `min(step_limit,horizon)` 意外截断恢复过程。给出可行性下界（最少合法操作、必须等待的 tick、容量与会车约束），让每个测试 seed 的真实故障发生且具有可恢复的调度方案。保留失败风险；对照 `no_replan`、`ignore_windows`、`greedy_dispatch`，测恢复延迟、服务率、冲突率和计划变更次数。Oracle 必须在预算内完成，且不可仅靠抢跑绕过故障。

**Batch 1 Gate**：两图新规则 DCR 批准状态明确、旧新 hash 并列、3+ seed Oracle 与消融通过、反旁路测试通过、指标可复算；不得把 `BLOCKED` 仅靠扩大预算改为 `VALIDATED`。

## 4. Batch 2：P0 三张构念旁路地图 MAP-06 / MAP-15 / MAP-21

### MAP-06 灯塔·暴风眼

原 seed=0 两步直达，无风暴机制。设计至少 10 环境 seed 的**分层天气 cohort**：晴稳、短风暴、连续风暴、预报噪声、边界风险；各 cohort 占比、触发机制、资源上限预登记。确保核心评估集合包含必须作出预报/风险选择的实例，同时保留正常天气的合理对照，不为强迫模型失败而作弊。指标：风险调整完成度、预测校准、观察成本、危险暴露、策略后悔值；与 `always_direct`、`always_reinforce`、`forecast_aware` 比较。

### MAP-15 金字塔·会变化的迷宫

删除目标/工具文案中直接泄露变化规则的文字；保留明确合法动作、反馈和可探索样例。使用多个变化规律家族，训练示例与测试路径分离，不能在单一固定路径上背答案。增加必须提交预测或规则假设的**合法动作/证据节点**，但不要把“多点一次按钮”误当作推理能力。消融：`no_probe`、`fixed_route`、`random_rule`、`no_transfer`；指标：样例利用率、规则泛化、预测正确率、探索成本。

### MAP-21 火山·喷发倒计时

原 1 步直达撤离即可拿满成功。将**人员安全**与**科研任务质量**拆成两个不可混淆的目标：`safety_success`、`science_completion`、`overall_utility`，保留“立即撤离”作为安全合法策略但不能获得完整科研分。设计不确定喷发窗口、观测代价与停手边界；既不能强制冒险，也不能把科研最大化凌驾于安全之上。消融：`always_evac`、`always_collect`、`risk_aware`，报告 Pareto 取舍与灾难率。新成功判据需 DCR 与指标版本化。

**Batch 2 Gate**：各图至少 3 seed（MAP-06 至少 10）完成 Oracle、反旁路与独立指标验证；`3/3 success` 不能作为验证依据。

## 5. Batch 3：古堡三图 MAP-28 / 29 / 30（优先打造高质量特色世界）

- **MAP-28 消失的王冠**：明确证据来源、时间戳、人物行动与时间线冲突；可公开的案卷枚举、`record` / `compare` 参数及返回值必须明确；证据缺失、误记与误判有可区分的失败码。`no_record` 应损害证据链完整度。
- **MAP-29 不可靠的证人**：定义证词引用、比较对象、可靠性估计与冲突判定的合法语义；不得在 Observation 里给出真凶或证人真值。支持互相矛盾、部分真实、无关但可信三类情况；`no_compare`、`trust_first`、`blind_accuse` 对照。
- **MAP-30 午夜审判**：跨阶段收集、归档、召回、举证和最终指控形成完整链条；公开案卷条目 ID、引用格式和可执行动作，但隐藏最终结论。检验早期证据是否真的被后期依赖；`no_casebook`、`late_guess`、`evidence_shuffle` 对照。
- 每图至少 3 不同案件 seed；不能仅换嫌疑人名字，必须变化证据依赖图和真假关系。Oracle 和独立裁判必须一致；对比“证据充分但指控错误”和“猜对但证据不足”。

**Batch 3 Gate**：三图都能触发核心证据推理，公开动作可执行，失败可解释，连续指标不全为 N/A。

## 6. Batch 4：其余 NEEDS_REDESIGN 地图逐图治理

每图先写机制反例，再写最小变更，禁止大规模统一重构：

| 地图 | V10 必须检验的机制与修复方向 | 关键反事实 |
|---|---|---|
| MAP-04 潮汐密道 | 绕行和盲撞可成功；使潮汐判断在主评估路径中真正有价值，保留合法绕行但有可衡量成本 | `detour_shortcut`、`no_phase_wait` |
| MAP-14 说谎的祭司 | 盲交可碰巧通过；加强证词一致性与多样化实例，区别正确推理和幸运猜中 | `blind_two_submissions`、`no_compare` |
| MAP-19 温度临界点 | 热控可做但预测可跳过；让时滞预测影响代价、风险或目标质量 | `no_prediction`、`reactive_only` |
| MAP-20 冷却网络 | 静态策略/不触发旁路；引入有意义的动态负载和网络约束，同时审计损耗参数冲突 | `no_bypass`、`static_allocation` |
| MAP-22 没有地图的森林 | 不写记忆也能返程；强化遮蔽、分岔和跨阶段位置记忆，但不泄露完整图 | `no_memory_write`、`fixed_turns` |
| MAP-23 迷雾中的遗迹 | 不侦察也能发现入口；设计线索价值和信息获取成本，保留探索-利用权衡 | `no_scout`、`blind_entrance` |
| MAP-24 消失的道路 | 成功轨迹未真正改路；保证评估实例出现不可预知封路并可恢复 | `no_replan`、`preplanned_detour` |

以上各图需区分：**机制必须是通关必要条件**与**机制仅影响效率/安全/质量**。后者可合理保留 OPTIONAL，但必须有经证实的连续质量指标，不能强行改成 FORCED。

## 7. Batch 5：NEEDS_MORE_EVIDENCE 与已 VALIDATED 图复核

- **MAP-07** 阀门方向：V9 公开控制面板后 0/1→1/1；多 seed 测阀门方向、水位预测与成本，检查是否只是固定脚本。
- **MAP-08** 漏点诊断：接口修复后仍 0/1；必须验证测试动作确实减少假设集，`no_hypothesis` 成功是否表示诊断非必要。
- **MAP-09** 连锁故障：修复后失败从短路转为缺氧；检查泵/封舱的因果依赖与阈值公开。
- **MAP-10** 燃料运输：0/2→2/2；变换初始仓位、容量和时限，验证装载与燃料分配确实必需。
- **MAP-11** 搜救：0/2→2/2；引入真实风暴/噪声与生命窗 cohort，验证不靠单条短路。
- **MAP-12** 极夜三十天：V9 修复臂无有效 MiMo 结果；先离线验证跨期库存与研究积分，再有界复测，不因 provider 错误强行补跑。
- **MAP-13** 四神之门：方向钉 OPTIONAL；判断是合理辅助还是指标虚设，使用多规则 seed。
- **MAP-26** 失败的维修计划：0/1→1/1，但 `no_diagnosis` 也成功；比较盲换、回滚、诊断的风险和备件成本，若诊断只是节约成本，则按质量指标验收。
- **MAP-01/02/05/16/17/25/27**：已 VALIDATED 也做防回归和至少 3 环境 seed Oracle/消融；不要因为已有标签而免检。

**Batch 5 Gate**：所有 30 图的 `public_heuristic`、Oracle、核心机制消融和跨 seed 稳定性都有记录；仍有问题的地图保留待证状态。

## 8. Batch 6：154 指标与五态语义治理

1. 从 V7/V8 注册表枚举 154 项；读取 V9 的 13 项缺陷清单，逐条给出 `metric_id`、缺陷类型、事件来源、公式、分母、零分母、成功/失败/截尾处理、可计算时点、单元和可比较范围。
2. 对 `VALID`、`NOT_APPLICABLE`、`CENSORED`、`INVALID_TRACE`、`UNAVAILABLE` 五态建立明确优先级：无事件分母为 0 与预算耗尽但可计算的部分进度不能混淆；**不能机械地把所有 None 改成 CENSORED**。
3. 将 V9 overlay 中合理的指标通过新 `metric_schema_version=v10` 纳入正式 schema；旧值和新值并列，不能覆盖或跨版本直接求均值。
4. 每项关键指标至少覆盖：成功、合法失败、预算截尾、零分母、非法动作、缺失事件、跨 seed。使用独立实现（非调用原 extractor）复算；对不一致逐项解释。
5. 为每图确定 1–2 个主指标及必要护栏；跨地图只比较标准化且语义同构的量。允许雷达图/能力剖面，不允许无依据把所有指标简单加总成单一榜单。
6. 建立 `metric_schema_hash`、fixture hash、追溯至原始 trace 的数据血缘；旧数据重算仅作为历史再解释，不得改写原文件。

**Batch 6 Gate**：13 项已知缺陷逐条有处理结论；30 图主指标可复算且有非平凡区分证据；残留 N/A 有合法解释。

## 9. Batch 7：多环境 Seed 难度定标与能力区分度

### 9.1 Seed 协议

- 每图最低 `environment_seed={0,1,2}`，保持规则不变但变化初始状态、事件序列或隐藏真值；对 MAP-06/15/21/28/29/30 等高风险图扩展到 10 seed（若成本/实现限制，则在报告中明确缺口）。
- 每个 seed 有独立 `scenario_hash`、隐藏真值的密封记录和 Oracle；同一 seed 下不同策略共享环境实例。禁止按 MiMo 成败选择 seed。
- 若某地图本质上固定实例不可参数化，必须说明原因并使用预登记的手工变体，而不是将相同实例的三次重复冒充三 seed。

### 9.2 对照策略

- `oracle`：证明可解性，不当作可发现性。
- `legal_random`：每图每环境 seed 至少 20 个 policy seed，记录随机通关/质量分布；严禁隐藏真值访问。
- `public_heuristic`：只读 Observation 的规则启发式；记录先验设计知识与是否依赖未公开常量。
- `ablation`：移除目标机制的策略；验证是否通关、质量是否下降及下降幅度。
- `greedy/shortest-path`（适用图）：提供局部最优与全局约束的对照。

### 9.3 难度判定

按世界内部简单→中等→困难，分别报告必要推理深度、状态规模、不可逆风险、信息不确定性、最优操作下界、失败代价、预算余量和策略基线表现。**不要求单一模型成功率严格单调**，但必须解释明显反转；设计难度与经验难度分开标注。

**Batch 7 Gate**：30 图多 seed Oracle 成功、反旁路和基线结果齐全；无法满足的实例标为失败并修复，不可筛掉。

## 10. Batch 8：有界 MiMo API 验证（已获用户授权）

### 10.1 预算与安全门禁

- MiMo 模型与版本、endpoint、temperature、max tokens、prompt 模板、单局最大决策数、timeout、环境 seed、replicate、预计费用和 stop rule 必须在运行前写入 `docs/v10/mimo-preregistration.json` 并计算 manifest hash。
- **默认 ¥10 累计上限**，所有主账本与补充账本共享全局额度；每请求先预留、结算后释放差额；若 provider 返回费用未知，标记 `UNKNOWN_PROVIDER_SPEND`、封账并停止自动调用，不得把未知费用当 0。
- 先 `--dry-run`，再小批 `pilot`，最后只对通过离线 Gate 的地图运行；不对明显不可解的图浪费 token。
- 不以成功为重试条件。Provider 中断可在审计后按预登记规则补跑，必须新 ID、记录原因、保留旧记录；不可无限补跑。

### 10.2 建议最小 MiMo 复测矩阵

- **P0 五图（03/06/15/18/21）**：各 3 个不同环境 seed，至少 15 局。
- **古堡三图（28/29/30）**：各 3 个不同环境 seed，至少 9 局。
- **V9 接口/证据图（07/08/09/10/11/12/26）**：各 3 个不同环境 seed，至少 21 局。
- **其余 15 图**：根据离线证据与剩余预算做分层抽样；若预算充足且 Gate 通过，可扩展至 **30 图 × 3 环境 seed = 90 局**。这是**目标上限矩阵，不是必须在 ¥10 内强行跑满**。
- 各组优先按世界分批，配对比较相同 seed 的 `v9_compat` 与 `v10_fixed`（仅对可比较的公开信息变更）；规则变化须明确不同实验版本，不能称严格同条件 A/B。

### 10.3 每局必须保存

`run_id,map_id,world,difficulty,environment_seed,replicate,model_id,model_version,temperature,scenario_hash,rule_hash,prompt_hash,metric_schema_hash,code_commit,termination,success,decision_count,mechanism_triggered,primary_metric_state,primary_metric_value,token_input,token_output,cost_settled,cost_unknown,trace_path,judge_path`。

**Batch 8 Gate**：所有实际调用有可审计账本；失败与中断保留；仅对完成的 seed 报告事实，不以不完整样本作跨模型排名。

## 11. Batch 9：最终验收与交付

### 11.1 目录结构建议

```text
docs/v10/
  README.md
  baseline-audit.md
  decision-register.md
  design-principles.md
  map-status-matrix.md
  difficulty-calibration.md
  construct-validity.md
  metric-schema-v10.md
  independent-metric-check.md
  baseline-results.md
  mimo-preregistration.json
  mimo-results.md
  cost-ledger-audit.md
  final-report.md
  maps/MAP-01.md ... MAP-30.md
  dcr/DCR-*.md
src/agent_arena/v10/
  runtime/           # 新版规则/兼容适配，保持每图机制独立
  metrics/           # v10 schema 和独立验证
  baselines/         # Oracle、随机、启发式、消融
  experiments/       # seed 生成、runner、预算与数据血缘
tests/test_v10_*.py
scripts/run_v10_*.py
runs/v10/             # 逐局 trace、judge、manifest、ledger；明确是否 Git 追踪
```

结构可适配现有工程，不要求强行迁移所有文件；但旧版本不得污染。

### 11.2 30 图最终状态矩阵

每张图只能依据证据进入：

- `VALIDATED`：机制有效、可执行、可解、核心指标有效、多 seed/消融证据满足 Gate。
- `NEEDS_MORE_EVIDENCE`：机制看似合理但样本/指标/对照不足。
- `NEEDS_REDESIGN`：存在构念旁路或成功条件与构念不一致。
- `BLOCKED`：接口、规则、预算或 Oracle 阻止正常测量。

同时独立报告 `FORCED/OPTIONAL/BYPASS/BLOCKED` 构念标签，不能混成一个状态。审计状态由 Agent 产生时标记 `agent_reviewed`，**不得伪造 `human_approved`**。

### 11.3 最终报告必须回答的问题

1. 哪些地图从 V9 状态提升到 VALIDATED？逐图证据是什么？
2. 哪些核心机制仍可绕过？合法替代策略是否被指标正确识别？
3. 10 个世界的三难度递进是否在认知负担上成立？哪些仍反转，为什么？
4. MiMo 的失败究竟来自策略、接口、预算、资源还是随机场景？
5. 154 指标与 V10 新指标中，哪些具备可靠区分度，哪些不适合作主指标？
6. 所有 MiMo 实验使用了多少环境 seed、多少重复、多少真实费用，哪些 provider 失败？
7. 旧 V8/V9 的数据是否完整保持、是否能复算、哪些跨版本比较不合法？
8. V11 是否需要跨模型验证，还是仍应优先修复少数地图？必须基于 V10 结果提出，不得预先宣布论文结论。

### 11.4 机器验收清单

- [ ] 最新 HEAD 与冻结版本已记录；V8/V9 文件未被修改。
- [ ] 30/30 逐图审计卡与机制证据完整。
- [ ] MAP-03、18、06、15、21 的 P0 反例被测试覆盖。
- [ ] 古堡 28–30 案卷、证据、比较接口可执行且不泄漏答案。
- [ ] 13 项指标缺陷均有版本化处理结论。
- [ ] 30/30 图至少 3 不同环境 seed 的 Oracle 可行性验证（或明确未达标）。
- [ ] 随机、启发式、消融与反旁路实验均可重放。
- [ ] pytest、ruff、mypy、diff-check 执行结果记录真实退出码。
- [ ] MiMo 预算门禁、预登记、trace、账本和异常恢复可验证。
- [ ] 30 图状态不虚报；无法解决的缺陷明确列出。
- [ ] `docs/v10/final-report.md` 含完整前后对照与剩余风险。

## 12. 给 DeepSeek V4.1 Flash 的直接执行指令

1. **立即开始 Batch 0**，核查最新仓库后自行拆分提交，不必等待我逐批回复。
2. 对明确的工程 Bug、公开接口缺陷、指标计算错误，可在 V10 命名空间自主修复；涉及任务语义/成功条件/隐藏信息边界的变更，必须先写 DCR、保存旧规则与新规则、设计对照并自审。用户已授权执行 V10 的必要设计改进，但不允许无证据地改变目标构念。
3. 每批执行完成必须更新 `docs/v10/README.md` 进度和状态矩阵，提交可复现代码与测试，标注 commit SHA、完成项、阻塞项、费用。
4. **允许自主使用 MiMo API 测试**；只要符合 ¥10 全局上限和预登记门禁即可，不需要逐次请示。未知费用或异常时立即停止付费，不能因要完成任务而绕过上限。
5. 不允许用大量自动生成的相似地图替代 30 个独立机制；不得凭报告文字冒充代码、Trace、人工批准或统计证据。
6. 如果 V10 规模超过一次上下文或执行窗口，按 Batch 0→9 顺序持续提交，下一次从最后已验收 Gate 继续，**不重复已完成的昂贵 MiMo 调用**。
7. 最终汇报必须包含：最新 HEAD、30 图状态前后对比、P0 逐图修复证据、多 seed 覆盖、MiMo 有效局/异常局、累计真实结算、测试结果、剩余缺陷、下一阶段建议。

---

**最终原则：30 图是否能可靠地区分 Agent 能力，比 30 图是否都能通关更重要。V10 要修的是测量效度，不是美化成功率。**
