# Agent-Arena V14 执行提纲

**项目：** [wenxvn/Agent-Arena](https://github.com/wenxvn/Agent-Arena)  
**版本定位：** V14 · 第二阶段收官（Agent Arena Lab 1.2 / Stage II Final Evidence & Delivery）  
**目标：** 在 V13 已实现的 Lab 1.1 上，完成证据口径校准、v2 Agent 有效性验证、CI 和产品交付验收。  
**审计基线：** `main` / `60c9ba2b64a3bd8d5cd549a7b76d0f3eb3ad092a`（2026-10-26 的最新提交；开始执行时须重新记录 HEAD）  
**执行者：** DeepSeek V4.1 Flash（可分多轮/中断续跑）  
**范围限制：** 不做 Ollama、macOS 迁移；不做公网部署、鉴权、跨模型排行榜、训练平台，也不更改冻结地图规则。  
**重要：** **本提纲不是新的 API 付费授权。未经用户对“模型、实验矩阵、总额上限”明确批准，禁止提交 LIVE 请求；V12 的 ¥6 历史授权及剩余额度不延续。**

---

## 0. 任务解释和执行纪律（必须先读）

### 0.1 当前真实基线

在上述 HEAD，以下为**已实现**而非 V14 新任务：

- 30 张 V10 原生地图；V11 单局网页；V12 Lab 父子实验、诊断、可视化、SDK；V13 五页 Lab。
- `memory.v2`、`planning.v2`、`reflection.v2`；重复身份 `replicate_index`、14 维可比性、7 个消融模板、七层归因、六维画像、六图效度、V13 模板报告。
- V13 报告：`1639 passed`、`verify_v13.py` 18/18、本地 E2E 通过、5,000 条合成历史压力测试；以上是**文档所记实测**，执行 V14 时应在当前 HEAD 重新复核。
- V13 增量 LIVE：**0 局、¥0**，真实模型对 v2 策略的有效性仍 `WAITING_USER_APPROVAL`。
- 最新 push 对应 [Actions run 40435185866](https://github.com/wenxvn/Agent-Arena/actions/runs/40435185866) 已完成且两个 job `quality`、`lab-e2e` 都是 `success`。**这是一次远端成功，不代表已连续 3 次通过**；V13 报告“尚未推送、远端 CI 未验证”已过时。

### 0.2 V14 完成的定义

第二阶段最终交付应能在本地完成：

**选地图 / Agent / 配置 → 预检 → 单局或批量实验 → 运行/停止/恢复 → 多重复分析 → 有证据锚的失败解释 → 分级报告/导出 → 历史复现/验证。**

同时把三种“完成”分开：

1. `ENGINEERING_VERIFIED`：代码、离线测试、浏览器 E2E、无泄漏与账本一致性已证实。
2. `LIVE_EVIDENCE_VERIFIED`：已经用户批准并执行真实模型试验；真实结果有合法分母、可比性与机制暴露证据。**不要求策略一定涨点**。
3. `STAGE_II_FINAL_READY`：1 与 2 均满足，且所有 P0/P1/P2 收尾项或有明确接受的非阻断例外。

若用户尚未授权付费试验，只允许声明 `ENGINEERING_VERIFIED / LIVE_PENDING`，不得硬写 `STAGE_II_FINAL_READY`。

### 0.3 必须遵守的边界

- **不改** `worlds/scenario_v8/`、`v10/` 冻结规则、V8/V9/V10 账本、历史 trace，必要修复只放 V14 投影或报告层。
- 先读 `AGENTS.md`、`docs/architecture.md`、`docs/v12/final-report.md`、`docs/v13/{final-report,gap-audit,experiment-protocol,validation-report,live-budget-proposal}.md` 和相关源码。
- 不擅自覆盖 V12/V13 数据、配置文件或用户本地研究提纲；V14 数据写独立目录 `docs/v14/`、`runs/v14/`（后者应继续在 gitignore）。
- 不为了“通过率”改地图机制、降低难度、延长预算后混入旧实验；不将 SIMULATED、HISTORICAL、LIVE 合并为一组模型效果。
- 不允许凭空声称模型思维链、模型意图；诊断只依赖公开 observation/action/result 及安全摘要。
- 不自动运行任何真实付费模型请求；提供 `preflight` 默认，只有明确批准后再 `--submit`。
- 完成一个 Batch 后提交小而可回滚的 commit；如果任务已有证据，标 `ALREADY_DONE` 并记录证据，不重复开发。
- 遇到新发现的事实错误，以代码与可复算 trace 为准，并写 DCR，保留负面结果。

---

## 1. V14 剩余 P0 / P1 / P2（共 19 项，全部纳入）

### P0｜实验可信度与真实策略验证（6 项）

| 编号 | V14 增量任务 | 关键验收 |
|---|---|---|
| **P0-1** | 最新 HEAD 与 CI 证据基线审计 | 最新提交、GitHub Actions job、文档状态一致，复跑 V11–V13 门禁 |
| **P0-2** | 历史数据 / 构念效度口径修正 | `UNKNOWN` 不得输出成 `0/N`；版本与预算混样可追溯，聚合可复算 |
| **P0-3** | 重复实验与单因子公平性强化 | 完整条件身份、同 seed 重复不伪增样本、可比性硬拒绝、效果与成本分开 |
| **P0-4** | Memory v2 的有效性实验方案与消融 | `route_log` on/off、`context_only` vs `env_write`；先 Pilot，LIVE 待授权 |
| **P0-5** | Planning v2 的收益–成本验证 | on/off、重规划、低频，预算同口径，所有 Planner 请求计费 |
| **P0-6** | Reflection v2 的激活与效果验证 | 先证实真实 `triggered > 0`，未激活标 `NO_TREATMENT_EXPOSURE`；LIVE 待授权 |

### P1｜六图能力诊断、MAP-30 与 Web 解释层（6 项）

| 编号 | V14 增量任务 | 关键验收 |
|---|---|---|
| **P1-1** | MAP-30 约束阶梯与失败类型 | 分开请求/token/金额/机制失败，输出预算可达步数的保守区间 |
| **P1-2** | 关键地图与候选地图效度再核验 | MAP-08/16/18/22/26/30 + MAP-19/20/29（可选候选，不修改图规则） |
| **P1-3** | 七层失败归因审计 | 每项有 decision 锚点；接口/测量问题不归因于策略能力 |
| **P1-4** | 六维能力画像稳健化 | 适用样本数、截尾、证据等级并列；不对异质指标求总分 |
| **P1-5** | 轨迹 Diff 与六图可视化增强 | 有意义差异高亮、状态变化、错误提示；不以伪造路径作展示 |
| **P1-6** | 报告可复现与结论强度修正 | 四级结论有严格限定；`SUPPORTED` 不等于显著改善/因果证明 |

### P2｜CI、产品与交付收尾（7 项）

| 编号 | V14 增量任务 | 关键验收 |
|---|---|---|
| **P2-1** | CI 浏览器 E2E 正式门禁 | 先证实三次远端成功，再设置阻断；一旦红灯修复而非屏蔽 |
| **P2-2** | 大历史、真实冷启动与异常负载 | 1k/5k 保留，另测未预热冷启动、损坏 manifest、进程恢复、并发读写 |
| **P2-3** | Lab Web 用户体验 | 5 页流程完整、筛选/历史、授权阻断与成本展示清楚，窄屏可用 |
| **P2-4** | 自动报告 / 导出一致性 | MD/JSON/CSV 同口径、摘要与逐局证据可回溯、失败不消失 |
| **P2-5** | 第三方 Agent SDK 加固 | 旧签名兼容、策略异常隔离、预算网关不可绕、示例可跑 |
| **P2-6** | 本地账本 / 外部账单核对 | 本地完整核对；外部账单不可得则如实保留 `BLOCKED_EXTERNAL` |
| **P2-7** | V14 最终交付封装 | 版本、截图、演示、README、CI 证据、残余风险、使用手册齐全 |

---

## 2. Batch 0｜最新仓库与第二阶段收口审计（P0-1）

**任务 V14-00-01**：`git fetch`、记录 HEAD / dirty status / 依赖锁 / Python/uv 版本；以实际 HEAD 而非本提纲的历史 SHA 为最终锚点。  
**任务 V14-00-02**：逐项对照 V13 19 个工程任务：`DONE` / `PARTIAL` / `LIVE_PENDING` / `BLOCKED_EXTERNAL`；保存 `docs/v14/baseline-audit.md`。  
**任务 V14-00-03**：查询最新 Actions 原始运行和两个 job 的结果，记录链接、run ID、SHA、通过/失败原因。已知一次成功：`40435185866`。  
**任务 V14-00-04**：检查 V11/V12/V13 自检、一套全量 pytest、冻结校验；失败先修复回归。  
**任务 V14-00-05**：建立 `docs/v14/{progress,decisions,gap-audit,validation-report}.md`，严禁把所有任务预填 DONE。

**Gate 0：** 可输出实际 HEAD、证据索引和最新测试结果，不修改真实实验数据。

## 3. Batch 1｜P0-2：修正历史报告口径与数据契约

**发现的具体问题（高优先）：** `src/agent_arena/lab/v13/validity.py` 已有 `mechanism_triggered_available` 判断，并在原因文字中说明旧数据没有字段；然而其 `validity_markdown()` 表格仍直接打印 `mechanism_triggered_runs / runs`，导致未知字段显示成 `0/35` 或 `0/27`。`docs/v13/map-validity.md` 就有这类表格。

- **V14-01-01**：将机制触发汇总拆为 `observed_true` / `observed_false` / `unknown`，只有可观察子集才可写 `x/n_observed`，全未知显示 `UNKNOWN (0 observed)`；禁止分母默认为所有历史局。
- **V14-01-02**：在 UI、CSV、JSON、报告上统一语义；给全部未知、混合已知/未知、显式 false 和 true 各做单测。
- **V14-01-03**：审查 `MAP-22` 跨契约 `contract-1/2`、旧错误动作接口、预算扩展是否误入相同能力分母；旧数据维持只读，新建 `v14.projection.*` 或分层视图，记录版本排除原因。
- **V14-01-04**：校准 `SUITABLE` 的解释——“有成功率梯度”只代表此样本存在差异，不能直接断言构念效度充分、策略引起的因果改善。
- **V14-01-05**：新增数据审计脚本或扩展现有脚本，重算 V13 文档的六图标签、有效分母、未知比例；生成一张可复核差异表。
- **V14-01-06（实质性文档错误）**：重新计算 `docs/v13/live-budget-proposal.md` 各组子局数与方案 B/C 统计。现有逐行数字合计为 **221 局**（E0 54 + E1 36 + E2 60 + E3 36 + E4 27 + E5 8），文件却写 **229 局**；按“E0 + E1 + E2 + E3”逐组相加应是 **186 局**、预估 **¥5.49**（0.95 + 1.80 + 0.94 + 1.80），文件方案 B 写 **150 局、¥4.19**。逐项核对后修正预算申请，不依赖旧表的错误汇总进行任何 LIVE 预检/授权。方案 A（E1-a + E2-a + E3-a）的 54 局独立成立。

**Gate 1：** 全未知不会展示为零触发，混合版本不会默默求均值，LIVE 预算表逐组求和正确；源文件不改写，旧 V13 结果仍可读取。

## 4. Batch 2｜P0-3：重复样本、可比性与统计协议

- **V14-02-01**：以 `(map, environment_seed, agent_id, config_hash, contract_version, effective_prompt_version, budget_profile, sampling_profile)` 为完整观测条件身份；`replicate_index` 只是观测序号。保留原版 `condition_key`/历史兼容，在 V14 分析层加规范化条件 ID，不强改冻结字段。
- **V14-02-02**：检查 `create_replicates`、`cross_experiment_pairs`、`replicate_variability` 与 `run_v12_matrix.py`：两个独立消融父实验不得因 `replicate_index` 或 config hash 丢配对；跨预算/跨提示/跨契约的硬不匹配必须拒绝。
- **V14-02-03**：清楚区分“同一环境 seed 上模型重采样的波动”与“对不同环境 seed 的泛化”；每个 map 的 seed 白名单从 `seed_space(map_id)` 动态检查，绝不编造新的 seed。
- **V14-02-04**：每一对结果同时汇报：完成局数、有效局数、成功/失败/截尾、可比对数、同 seed 方向、请求/token/费用差值和风险；保留负面和无差异结果。
- **V14-02-05**：Wilson/Bootstrap 等区间**注明抽样单位和前提**；少量独立 seed 不进行夸大的显著性/广义泛化判断。可提供按 seed 分块的效果区间，但样本不足明确写 `DESCRIPTIVE_ONLY`。
- **V14-02-06**：修正报告层 `SUPPORTED` 的含义：它最多代表“结构化观测证据满足门槛”，不得直接变成“策略有效/显著提升/因果证实”；将“机制暴露”“效果方向”“效果置信程度”拆成独立字段。

**Gate 2：** 三组已知 V12 翻转率口径可原样复算（4/18、3/12、全历史子集分别展示）；非法配对测试全部拒绝；重复不算新增地图 seed。

## 5. Batch 3｜P0-4：Memory v2 机制验证与真实试验准备

- 审计 `memory.v2` 与 `memory.v1`：是否只统计被接受的 `move`、是否避免重复记入、路线压缩/容量/检索是否使用公开信息。
- 为 `MAP-22` 准备 `memory.route_log` 的单因子 on/off：**同一个 `memory.v2`**、同 `route_mode=context_only`、同模型/提示/预算/seed；只变 `route_log`。另外单独测试 `env_write` vs `context_only`，不要同时变两个配置。
- 重点跟踪 `route_recall`（V10 原始与 V14 研究投影分列）、回头路、浪费移动、有效写入次数、成功率、决策消耗、输入 token 和人民币费用。
- 离线模拟中增加“被拒绝移动不能写入路线”和“回到起点后能引用完整方位”的真实环境 fixture；不得通过直接写答案提高成功率。
- **LIVE：仅建立 Pilot 与主矩阵预检，默认 `PLANNED_ONLY`；没有用户独立授权就停止在此 Gate。**

**Gate 3：** 离线机制无泄漏，开关确实只相差一个变量；有预算上界和预检命令；真实收益未批准时诚实标 `LIVE_PENDING`。

## 6. Batch 4｜P0-5：Planning v2 机制与收益–成本

- 复核 `adaptive` / `initial_only` / `periodic`、`min_steps_between_plans`、TTL、`budget_aware`，确保 Planner 输出非执行、每次请求经过同一网关计费。
- 对 `MAP-16` 主测：规划 on/off；对重规划 on/off、低频 planner 分别设计**独立**消融；`MAP-18` 保留负向/无效对照。
- 增加每次 Planner 触发事件链：触发 → 是否被 TTL/预算挡下 → 实际请求 → 子目标变化 → 后续动作 → 最终结果。
- 预先声明**比较口径是相同总预算、而不是 Planner 免费额外请求**；同时报告每成功局费用、额外请求以及因规划导致的截尾。
- 若节流省钱但成功率下降，保留该结果，不为追涨点放松预算。

**Gate 4：** 消融变量单一，成本归因完整；V13 旧实验无回归；LIVE 未授权不提交。

## 7. Batch 5｜P0-6：Reflection v2 暴露率与真实收益

- 在离线轨迹里筛选**足够长的失败前缀**：先 MAP-22；MAP-19/20/29 只作为候选，须先通过公开动作/触发器离线诊断。
- 设计三臂：`disabled` / `trigger_only` / `reflection_on`。对照条件在同版本 `reflection.v2` 中，只操纵一个开关；复杂对比明确标组合/机制比较。
- 区分 `eligible`、`triggered`、`blocked_cooldown`、`blocked_quota`、`false_triggers`、`recoveries`。反思后的公开进度改善不是自动等于“反思导致改善”。
- 真实 Pilot 的**激活门禁**：`reflection_on` 臂至少出现一次确实发出了反思请求；若未触发，立即记录 `NO_TREATMENT_EXPOSURE`，先改选地图（改阈值须另立版本），不能继续按“反思无效”报告。
- 把暴露后的诊断与包含所有分配局的结果分开：不允许只挑触发成功的局评价增益（选择偏倚）。

**Gate 5：** SIMULATED 触发真实进入运行时、记录并计费；LIVE 审批前零外部请求；未触发不冒充失败。

## 8. Batch 6｜LIVE 方案（独立批准的可选执行门）

**本 Batch 分两个阶段：A 可以立即完成；B 必须另获用户批准。**

### A. 离线预注册与费用申请（必做，零外部请求）

建议首先复用 V13 的 **方案 A 最小闭环**，但需用 V14 修正后的协议与代码重新生成，不直接拿旧 preflight 结论充当新证据：

| 试验 | 地图 | 设计 | 条件局数 |
|---|---|---|---:|
| E1 | MAP-22 | `memory.v2` route_log on/off × 3 seed × 3 次观测 | 18 |
| E2 | MAP-16 | `planning.v2` on/off × 3 seed × 3 次观测 | 18 |
| E3 | MAP-22 | `reflection.v2` on/off × 3 seed × 3 次观测 | 18 |
| **合计** | | 54 局；先做小 Pilot 再推进 | **54** |

历史 V13 方案 A 估算：约 **¥1.68**、推荐整体硬预算 **¥5.00**；注意 V13 方案 B/C 子局总数存在算术矛盾，见 Batch 1，必须先修订再申请。**只是旧数据推算，不是报价或本轮授权**。必须重新核对登记价、模型名、单局 token 上限、预算截尾率，以及“实验硬上限不足时可能跑不完全部 54 局”的风险。Pilot 尽量从这 54 局中选取，不额外计为新的 6 局。

可供用户选择：仅审批 E1、仅审批某个 Pilot，或审批整套；不能自行把一个批准项扩到另一项。记录审批的模型、允许实验、总金额、每局请求/token/成本阈值、未知 usage 处理、何时停止。

### B. 用户明确批准后才允许开始

- `preflight` 通过且确认预算、版本、矩阵、模型；单 worker 串行执行。
- 先 Pilot 验证接口合法、`reflection_triggered` 可真实测到、usage 可结算、没有异常拒绝；发现契约缺陷**先停**，写 DCR，修复后使用新版本实验，不污染原计划。
- 分组逐批跑、每批账本审计；未知消费封账、不自动重试；若成本/截尾显著超预算则停止。
- 做完整分析时严格保留：环境 seed、模型采样不确定性、同条件重复、配对结果、负面结果、成本和删失。
- 无批准时该部分输出 `LIVE_PENDING`，**绝不能以 SIMULATED 代替效果证据**。

**Gate 6：** 新真实试验如果获批，逐局数据与结果可回溯、实验总成本不超批准；未获批则零请求并有完整方案。

## 9. Batch 7｜P1-1 + P1-2：MAP-30 与地图适用范围

- 复盘 MAP-30 的 90 请求 → 180 请求 → 600k input tokens 等预算阶梯，按请求/token/费用三维分析。`ACCUSATION_REJECTED` 属真实机制失败，budget limit 属截尾；两者不可合并。
- 只用历史数据构建 `budget_capacity` 保守区间；在网页预检提示“估计范围、不承诺可跑通”。新的 MAP-30 高成本 LIVE 不默认纳入方案 A。
- 重新核验六图标签，保留 `CEILING`（08/26）、`SUITABLE`（16/18/22，仅描述现有样本有梯度）、`CENSORED`（30）。
- 从 30 张图中**仅筛选**可能具有更长失败前缀的 MAP-19/20/29 做公开机制审计，不凭空添加 seed、不改地图规则，也不强行断言这些图一定更好。

**Gate 7：** 预算截尾与机制失败比例可复算，适用性判断标明证据版本/样本数；候选图不足可明确 `NEEDS_MORE_EVIDENCE`。

## 10. Batch 8｜P1-3 + P1-4 + P1-6：诊断、能力画像和结论语言

- 审核七层 `INTERFACE_CONTRACT` / `MEASUREMENT_COVERAGE` / `BUDGET_CENSORED` / `ENVIRONMENT_MECHANISM` / `POLICY_BEHAVIOUR` / `PROVIDER` / `UNKNOWN`；新增正反 fixture，把“被拒绝导致无进展”与“有公开进展但预算失败”分开。
- 每个 `Finding` 须能定位 `(run_id, decision_index, action, public_result)`；不能凭猜测输出“Agent 是因为不理解……”等未经证实的主观解释。
- 六维能力画像同时显示：适用地图、可测局、独立 seed、重复数、成功/机制失败/截尾和观察缺口。历史没有证据的维度输出 `UNAVAILABLE`，不能填 0。
- 报告等级与“实际收益”分离：`SUPPORTED` 是证据形式质量，不等于策略效果显著；预注册与后验分析分开呈现。加入反例/负面结论检查。

**Gate 8：** 故障归因有锚点、结论无不当因果宣称、画像与汇总可逐局复算。

## 11. Batch 9｜P1-5 + P2-3：五页 Lab 的体验收官

- 在现有 Streamlit 五页基础上补最有信息增益的可视化，禁止为了界面炫技重写核心服务。
- 优先做**双轨迹首次分歧高亮**（两侧动作、公开状态变化、拒绝/成功、版本提示）、重复结果按 seed 分组、MAP-22 地图探索（拒绝移动绝不画成实际走过的路径）、MAP-30 预算阶梯。
- 配对不可比时禁用比较结论，页面直接展示原因；没有证据锚的自动结论显示“证据不足”。
- 真实模型费用确认与启动按钮必须可识别；未批准时只允许预检，不能通过其它入口绕过。
- 实际浏览器跑通：配置 → 合法预检 → SIMULATED 运行 → 监控 → 结果 → Diff → 报告/CSV 下载；再覆盖空历史、浏览器刷新、过滤、停止/恢复。
- 对 430px 窄屏、浅色/深色、键盘访问做无密钥测试；真机读屏不可得标 `NOT_VERIFIED`。

**Gate 9：** 完整本地浏览器流程通过，新增图形不泄漏私有状态，不把合成/历史结果展示成 LIVE。

## 12. Batch 10｜P2-1：GitHub Actions 的正式门禁

- 当前已知：`40435185866` 的 `quality` 和 `lab-e2e` 均已成功；V13 `ci.yml` 仍 `continue-on-error: true`。先更新 `docs/v14/ci-evidence.md`，不要声称尚无远端证据。
- 后续再取得**连续三次**指定 E2E job 成功记录（不同独立 CI 运行/重跑，列明 run ID 和 head SHA；相同 commit 可重跑，但必须是真运行），确认冷安装 Chromium 稳定且无需外部 Key。
- 达标后改 `lab-e2e.continue-on-error: false` 并再运行一次验证；如失败修复依赖/端口/等待条件，不允许 `skip`/`xfail`/降低断言来蒙混。
- 未达三次不应该硬切阻断；保留 PARTIAL 并附真实运行证据。

**Gate 10：** 主质量门禁通过，浏览器 E2E 真实远端可靠；不通过的 E2E 不得被整仓库绿色总状态掩盖。

## 13. Batch 11｜P2-2 + P2-4 + P2-5 + P2-6：工程边界

- 压测：保留 1k/5k 合成 history；新增**不预热的首次打开耗时**与已预热解析耗时分别报告、损坏 manifest、并发读取时新 run 写入、索引 TTL 刷新、长历史导出，记录实测而非承诺。
- 性能不设不切实际的跨机器固定阈值；保护不把全部事件加载到内存；生成测试数据只进临时目录。
- 导出：`run` / `metrics` / `paired_comparison` / `findings` / report 的行数、分母、类别、版本、来源模式一致；CSV 列缺失不能静默补零。
- SDK：本机可信插件例子、旧签名、异常隔离、模型网关/预算限制、去密钥；不宣称可以安全运行任意第三方代码。
- 账本：复算 V12 的 159 局、5641 请求、¥5.43680012、0 孤儿/重复；V14 新 LIVE 有批准才建立独立台账。后台对账若无用户提供脱敏账单则保留 `NO_EXTERNAL_BILL_PROVIDED`，不能假装已经对上。

**Gate 11：** 离线和历史源可被独立复核，账本/导出一致，常见异常不会把工作区破坏。

## 14. Batch 12｜P2-7：第二阶段最终交付验收

必须有以下产物（能复用 V13 时优先复用，不能以“写了文档”代替运行）：

```text
docs/v14/
  README.md                 # 版本入口、完成状态、复现方式
  baseline-audit.md         # V13→V14 真正增量/不重复项
  experiment-protocol.md    # V14 的可比性、重复、门禁与批准边界
  ci-evidence.md            # 远端 Actions run/job 链接、结果
  data-validity.md          # UNKNOWN/0、版本隔离、构念效度
  agent-studies.md          # Memory/Planning/Reflection 机制及 LIVE 状态
  map-audit.md              # 六图+候选图、MAP-30 截尾
  failure-and-capability.md # 诊断/画像的证据与边界
  validation-report.md      # 命令/结果/平台/实际日期/HEAD
  gap-audit.md              # 19 项逐项完成证据和未做项
  release-checklist.md      # 交付验收 Gate
  final-report.md           # 实际结果、负面结果、剩余问题
  decisions.md              # 实施中协议/版本变动
  progress.md               # Batch 进度与每批 commit
  screenshots/             # 真实浏览器截图（脱敏）
```

**推荐新增命令（如现有脚本可以复用，不强制重造）：**

```bash
uv run python scripts/verify_v11.py
uv run python scripts/verify_v12.py
uv run python scripts/verify_v13.py
uv run python scripts/demo_v13.py
uv run python scripts/a11y_v12.py --browser --start
uv run --with playwright python scripts/e2e_lab.py --start --port 8512
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run uv lock --check
uv run python -m agent_arena.v10.freeze verify
uv run python -m agent_arena.v10.recompute --check
uv run python -m agent_arena.v10.independent_check --check
```

若引入 `scripts/verify_v14.py`，它必须检查**V14 新增的事实边界**：混合 trigger unknown、混合版本、seed 分组、批准阻断、CI 证据登记、导出一致性、诊断锚点。不可只重新调用 V13 全套并宣称“新增 N 项”。

**最小交付演示：** Windows 本地 `uv sync --extra web` → `uv run agent-arena web` → 无 API Key 完成完整 SIMULATED Lab → 下载报告与逐局回放 → 展示与源数据一致的历史分层分析。实际 LIVE 若已获准则另提供独立真实试验报告。

---

## 15. 阶段切分、并行安排与预算

### 无需新的付费授权即可完成

**Batch 0–5 的工程/离线部分 + Batch 6A + Batch 7–12** 可直接开发并验证。  
可并行：P0 数据口径、P1 图表、P2 压测/SDK/CI；但可比性协议与数据模型确定后，所有分析页面/报告才应合并。

### 必须取得新的付费授权才能完成

**Batch 6B：真实 MiMo（或用户指定兼容模型）Pilot / 正式矩阵。**

- 每个子实验分配独立模型/版本/Prompt/预算指纹；不沿用旧 LiveApproval。
- 若用户不批准或余额不足，**继续完成所有离线工程**，最终明确记录 `LIVE_PENDING`，不得以“第二阶段最终实证完成”交付。
- 不因为用户指定“继续执行”就把它当作授权具体费用的意思。

### 成果不足时的处理

- Memory、Planning、Reflection 没提升：保留否定结果和成本，**这不构成工程失败**。
- 模型表现翻转率仍高：报告变异和不确定性，不强行制造可靠排名。
- 真实 Reflection 不触发：保留 `NO_TREATMENT_EXPOSURE`，重新审查场景，变阈值另立版本。
- MAP-30 主要截尾：保留 `CENSORED`，不要把预算问题写成推理能力极弱。
- 外部账单、真人读屏/实机不可得：清晰标非阻断外部缺口；不得虚构。

---

## 16. 完工自审与 DS 的最终回复格式

最终回复必须依次写：

1. 实际 HEAD、从 V13 到 V14 修改了哪些关键代码/测试/页面，以及对应 commit；
2. 19 项逐项状态（`DONE`/`PARTIAL`/`LIVE_PENDING`/`BLOCKED_EXTERNAL`），仅有可核查证据才标 DONE；
3. 真实运行的 pytest、mypy、ruff、V10 冻结、V11–V14、自检/E2E 与远端 Actions job 结果；
4. 数据口径修复前后对照：`UNKNOWN`、版本排除、样本数与有效分母；
5. Memory/Planning/Reflection 的机制及真实收益：区分 `SIMULATED` / `HISTORICAL` / `LIVE`；
6. 费用账本与用户批准范围；如没批准则明确“V14 新增外部付费请求 0”；
7. 完整交付演示路径、还剩哪些真问题、建议是否进入第三阶段；
8. 绝不写“全部完成”同时又把核心 LIVE 效果留在未验证状态。

**给 DeepSeek 的首条执行指令：**

> 当前仓库已经有 V13 的 19 项工程实现。你现在执行 V14，不是复制 V13。先以最新 GitHub HEAD 做 Batch 0 审计，再依照本提纲批量推进 Batch 1–12。已有模块和脚本优先复用，逐批实际修改、运行测试、提交 commit，并在 `docs/v14/progress.md` 留证据。先完成所有零费用工作。未经我对新的模型、具体矩阵和总费用上限明确批准，不得发起任何付费 API 实验。不得修改冻结世界、V8/V9/V10 账本或历史 trace。Ollama 和 macOS 不在本轮范围。

