# Agent-Arena V13｜第二阶段深化：能力稳定性、策略优化与工程收尾

> **交付给：DeepSeek V4.1 Flash（执行 Agent）**  
> **类型：直接执行的工程任务书 / Markdown**  
> **范围：P0 + P1 + P2 全覆盖；不进入第三阶段**  
> **目标项目：** https://github.com/wenxvn/Agent-Arena  
> **审计参考 HEAD：** `32e27826eab33093d2d5d640d08f47bbd4974df3`（2026-10-26；执行时必须重新核验 HEAD）  
> **目标形态：** `Agent-Arena Lab 1.1`（V12 Lab 1.0 的深化，不是另起炉灶）  
> **明确排除：** Ollama 实机验证、macOS 迁移/实机验证、公网部署、用户系统、云数据库、跨模型排行榜、自动生成新地图、新的论文/Benchmark 发表任务。  
> **最重要的限制：本提纲不构成任何新增付费 API 实验授权。历史 V12 的 ¥6 预算已经结束，剩余余额不能自动挪用到 V13。未经用户另行明确授权，仅能执行离线检查、模拟实验、历史数据再分析、实验预检；不得发起新的真实付费请求。**

---

## 0. 给执行 Agent 的总指令（先读）

请直接在现有仓库中实现 V13，**不是只生成计划，也不要把旧功能重新实现一遍**。

1. 开始之前检查最新 `main`、工作区状态、`AGENTS.md` 和现有 V12 文档与代码。若新提交已经实现本提纲中的内容，将其标记为 `ALREADY_DONE` 并补验收证据，不重复造轮子；不能以文档中写 `DONE` 就代替代码及测试验证。
2. 完成 P0、P1、P2 全部工程任务。按 Batch 0–13 的依赖执行；可拆多次上下文或多轮提交，但各批次结束必须落盘进度，不能仅在聊天中声明完成。每次遇到阻塞先定位最小可行修复，不轻易重构全项目。
3. **先离线开发，再申请真实模型预算。** 实验代码、参数注册、预检、回放重算、模拟数据、自检、UI 全都能在不调用付费 API 的条件下完成；真正需要 LIVE 结果时标记 `WAITING_USER_APPROVAL`，汇报准确的候选矩阵、最多请求量、最坏可计费成本和中止阈值。任何 `--submit` / `LiveApproval` / 请求到收费端点均不得自行越过授权。
4. 固定 V8/V9/V10 的环境规则、已冻结指标、账本与历史运行记录；V11 单局、V12 Lab 原有可用性和兼容性必须保持。新增功能放入 `lab/` 或其合理新模块，用**版本化契约、投影指标和新增输出目录**实现；不要为了涨点改关卡规则、泄漏 Oracle、修改历史结果。
5. 不能以“代码完成”冒充“真实结果验证”；不能以“抽样重复 3 次”声称统计显著；不能把模型输出的随机性视为环境 seed 不稳定；不能把运行成本、被拒动作、预算截尾隐藏在成功率背后。
6. 每批执行完：做局部测试、记录证据、更新 `docs/v13/progress.md`、提交 Git commit；最后运行全套离线质量门禁和可用的浏览器 E2E。若 CI 实际未执行或不存在后台账单，不得伪称通过。
7. 不需要就普通架构设计反复征询用户；仅在**新付费预算、不可逆删改、公开发布/扩大权限、必要的外部凭据**处停下等待授权。默认在本地单用户 Windows 流程内继续工作。
8. 只允许根据 Agent 可见的公开 Observation、公开历史与已经执行的 Action 构造 Memory / Planning / Reflection；不允许使用环境完整状态、测试用答案或 Oracle 在推理时辅助决策。

### V13 最终要回答的 5 个问题

- 同一配置多次运行，其结果波动到底有多大？统计和版本口径是否正确？
- **Memory / Planning / Reflection** 中，什么机制真正被激活，给哪些地图带来哪些改善或额外成本？
- 在 MAP-16、18、22、30 上，失败是能力问题、接口问题还是预算 / 测量问题？
- 对哪些地图，现有指标能区分能力；哪些存在天花板、地板或构念证据不足？
- 使用者能否从网页一键完成合规配置、离线自检、可审计的比较与报告，而不被误导？

---

## 1. 项目基线与当前事实（以实际 HEAD 为准）

### 1.1 V12 继承资产——不允许丢失

- V10：30 张原生手工地图，10 个世界，326 项指标（154 + 172），环境 Seed 有白名单，冻结和独立复算可用。
- V11：本地 Streamlit 网页，30 图单局运行、配置、持久化、预算、历史、回放、导出。
- V12：`basic.v1`、`memory.v1`、`planning.v1`、`reflection.v1`；统一 `DecisionGateway`；父实验/子局、预检、配对对比、五态指标、失败归因、六图 view-model、第三方受信任 Agent SDK、实验导出。
- V12 官方记录：20 个真实 MiMo 实验、159 局、5,641 请求、¥5.43680012 已结算、未知消费 ¥0；主矩阵 54 局，成功 24 局，有效分母 53；自动化测试 `1525 passed`、`verify_v12` 15/15。这些是历史基线，不是 V13 已完成的证明。
- 已查明的实验问题：同条件重复的结局翻转率 22.2%（两次观测）/ 25.0%（三次观测、适当排除跨版本）；MAP-08/26 原六图组合中的天花板；MAP-22 的 memory payload/route_recall 契约问题与路线长度问题；MAP-30 请求/token/费用分层截尾；Reflection 消融从未实际触发（`DCR-V12-05`）。
- V12 留存小差距：CI 的浏览器 E2E 仍为 `continue-on-error`；上千条历史压力仅有单测；部分六图 fixture 是合成数据；缺少 Provider 后台账单核对；真机无障碍仍有局限。**macOS 和 Ollama 继续暂缓，不计 V13 缺项。**

### 1.2 必读资料（顺序）

`AGENTS.md` → `README.md` → `docs/architecture.md` → `docs/v12/final-report.md` → `docs/v12/gap-audit.md` → `docs/v12/experiment-protocol.md` → `docs/v12/mimo-results.md` → `docs/v12/ablations.md` → `docs/v12/risk-register.md` → `docs/v12/metrics-and-attribution.md` → `docs/v12/adapter-api.md` → `docs/v12/dcr/DCR-V12-01.md` 至 `DCR-V12-06.md` → 关键 `lab/`、`web/`、`ui/` 实现及测试。

重点入口：

```text
src/agent_arena/lab/
src/agent_arena/lab/policies/
src/agent_arena/lab/contracts.py
src/agent_arena/lab/experiment.py
src/agent_arena/lab/compare.py
src/agent_arena/lab/diagnostics.py
src/agent_arena/lab/visualization.py
src/agent_arena/lab/report.py
src/agent_arena/lab/sdk.py
src/agent_arena/ui/lab.py
src/agent_arena/web/
scripts/run_v12_matrix.py
scripts/run_v12_ablations.py
scripts/summarize_v12_replicates.py
scripts/verify_v12.py
scripts/e2e_lab.py
examples/custom_agent/
docs/v12/real-runs/
```

> 新增脚本文件名在下文只是建议。必须先找现有能力，能扩展现有脚本就不重复造新入口。

### 1.3 冻结区与安全不变量

- 禁止修改 V8/V9/V10 冻结规则/评测目标、过去的 `runs/v*/`、旧 `runs/web`/`runs/lab` 的原始产物、已记账条目。
- 三种运行通道 `OFFLINE` / `SIMULATED` / `LIVE` 必须严格区分。
- 真实请求全部通过 `DecisionGateway` → `RunBudget`；未知消费 fail-closed，绝不自动重试。
- 不能把 `CENSORED / NOT_APPLICABLE / MISSING / INVALID` 之类状态默认为 0。
- 第三方策略仍限本机受信任插件，不做任意不可信代码在线执行。
- 所有展示与诊断只读公开轨迹；`sealed_truth`、`judge_state`、Oracle 等不可进入 Agent 上下文。

---

## 2. 任务全表：全部纳入 V13

| 等级 | ID | 任务 | 核心交付 |
|---|---|---|---|
| P0 | P0-1 | 实验稳定性验证 | 重复试验设计/执行器、翻转率与不确定性分析 |
| P0 | P0-2 | Memory 策略优化 | `route_log` 等策略消融、状态记忆的收益/代价 |
| P0 | P0-3 | Planning 策略优化 | 子目标、重规划、预算效率与诊断 |
| P0 | P0-4 | Agent 消融实验 | 开关对照/独立配置配对、必要的触发校验 |
| P0 | P0-5 | 实验公平性审计 | 版本/采样/共享 Prompt/预算/可比性校验 |
| P0 | P0-6 | 核心结果重新验证 | MAP-16/18/22 的独立证据包和保守结论 |
| P1 | P1-1 | Reflection 策略优化 | 真触发机制、对照与开销证据 |
| P1 | P1-2 | MAP-30 深度探索 | 预算预检、证据链失败、截尾分型 |
| P1 | P1-3 | 失败诊断增强 | 接口/机制/策略/预算的证据级分类 |
| P1 | P1-4 | 能力画像完善 | 机制级画像、有效分母、置信/证据标签 |
| P1 | P1-5 | 可视化优化 | 轨迹 Diff、六图视图、交互可读性 |
| P1 | P1-6 | 六图有效性审计 | 天花板/地板/构念效度、选图建议 |
| P2 | P2-1 | CI 自动化强化 | 可依赖的 E2E 门禁与故障证据 |
| P2 | P2-2 | 性能压力测试 | 1k/5k 历史、批量实验、导出与资源测试 |
| P2 | P2-3 | Web UI 优化 | 可靠配置/恢复/筛选/预检反馈 |
| P2 | P2-4 | 自动实验报告 | 离线、模板化、可追溯的实验摘要与建议 |
| P2 | P2-5 | 第三方 Agent SDK 完善 | 接入校验、示例、故障隔离、文档 |
| P2 | P2-6 | 数据与费用审计 | 本地账本核验及可选后台账单导入 |
| P2 | P2-7 | 文档与交付整理 | 完整 V13 证据、复现实验、演示和报告 |

**范围判断**：V12 已交付的功能视为 baseline，V13 要形成“可审计的增量”。P0 全部执行，P1 全部执行，P2 全部执行；需要外部账单/真实 API 授权的部分单独 `BLOCKED_EXTERNAL`，不能为了打勾造数据。

---

## 3. 核心实验原则：先冻结协议再改策略

### 3.1 条件身份与重复试验

建议将下述信息写入实验 provenance（现有字段可复用）：

```text
experiment_id / run_id / parent_experiment_id
map_id / environment_seed / replicate_index
mode / provider_id / model_id / available_model_revision
shared_prompt_hash / effective_system_prompt_hash / action_contract_version
agent_id / agent_version / agent_config_hash / policy_code_version
history_window / memory_limit / strategy_flags
sampling_requested / sampling_effective_or_unknown
max_decisions / max_requests / max_input_tokens / max_output_tokens / max_cost
scenario_hash / rule_hash / metric_hash / metric_schema_hash
runtime_version / created_at / run_outcome / termination / truncation_reason
input_tokens / output_tokens / requests / total_cost / cost_unknown
```

- **环境 Seed ≠ 模型生成 Seed**。固定同一个环境 Seed 只保证环境初态一致，不保证 Provider 输出确定；若支持模型 `seed`、`temperature`、`top_p` 等，需记录“请求值/实际被服务端支持情况”，不支持则标记 `UNSUPPORTED`/`UNKNOWN`，严禁伪称 deterministic。
- `replicate_index` 是重复**独立采样**，不能被 V12 `idempotency_key` 去重为旧 run；设计版本化身份，保证同一个重复编号重新提交仍幂等，换重复编号真正新建 run。验证过后才考虑变更旧的 `condition_key`，不得破坏 V12 的历史读取。
- **一致性**：比较不同策略时，环境、模型、共同 Prompt 主体、动作契约、观察历史规则、预算上限固定；策略注入的记忆/计划文本或额外请求属于被测干预，必须显式记录，不能人为要求它们的完整 `prompt_hash` 相同。
- **跨实验配对**：V12 `condition_key = map|seed|agent` 不含 config hash。开关 on/off 默认建立**两个独立父实验**，通过 `(map, seed, replicate_index)` 和共同版本/预算/模型字段做配对；不得把不同配置覆盖进相同键，不能把不同版本历史硬并到一个成功率。
- **历史结果不混合**：V12 历史 `DCR-V12-01/02/06` 之前/之后有契约和默认配置变化，先生成 `comparable_group_id`，严格核对修订档案；只将真正同条件的历史观测加入重复分析。
- 避免开发集过拟合：已有 MAP-16/18/22 轨迹作为诊断/设计集；最终验证优先选用 `seed_space` 中仍合法、尚未用作策略调参的 seed，以及相同旧 seed 的独立重复。**若地图没有新 seed，不能擅自增 seed 空间或修改规则**，应诚实声明测试仍属探索性证据。

### 3.2 实验结果与统计口径

每个地图/seed/策略/重复样本保存：

- 成功/机制失败/预算截尾/取消/Provider 错误/策略错误等**原始终态**；
- 完成率或成功率的分子与每类分母：`all_attempted`、`evaluable`、`uncensored_finished`，并显示 censored 比例；V12 旧口径可兼容但不得悄悄改变。
- 同条件重复的结局翻转率、成功次数 / N；因重复次数少，只能做描述性区间/范围，必要时可展示二项比例的置信区间并写明前提，**不能仅凭 N=3 声称架构显著优胜**。
- 成功率 + 被拒动作 + 无效动作 + 资源/步数 + 请求次数 + input/output token + 实付/估计费用 + 终止原因；成本有未知项则相应聚合显示 `UNKNOWN`。
- 配对输出以 seed 为块，跨策略比较既给 *paired difference* 又给逐个 seed 详情；重复采样不是独立新环境 Seed，避免伪造样本量。
- 对失败样本不要过滤得只剩成功局；描述 success、mechanism failure、censored 比例时要展示完整流转图。

### 3.3 三层实验门禁（不可跳过）

1. **Gate A · 离线单测**：协议解析、模拟策略、消融开关、预算触发、读旧结果、重算和数据泄漏全部通过。
2. **Gate B · 历史/模拟复演**：以 V12 159 局历史数据做只读再分析；离线 scripted 模式验证完整父子实验链；所有结果标明 `HISTORICAL` 或 `SIMULATED`。
3. **Gate C · LIVE**：只有用户**本次 V13 另行授权**具体总费用上限、模型、范围后才能执行 Pilot/Matrix；若未授权，所有新结果状态 `WAITING_USER_APPROVAL`，整个 V13 可达到 `ENGINEERING_READY` 而非 `LIVE_VALIDATED`。

### 3.4 推荐的 V13 真实实验矩阵（仅设计与预检，**不得擅自执行**）

| 组 | 研究目标 | 建议范围 | 地图/策略/重复 | 执行条件 |
|---|---|---|---|---|
| E0 | 采样复现与历史可比性 | 先只读 V12 历史，然后 Pilot | MAP-16/18 各挑合法 seed × Basic/Memory/Planning，逐条件 ≥3 次（已有同版本可计入） | 单独批准后才能补新观测 |
| E1 | Memory `route_log` | 同策略开/关，记录路线与任务代价 | MAP-22 合法 seed × on/off × ≥3 次（成本按预检估算） | 与旧契约版本严格分组 |
| E2 | Planning 效益与成本 | 规划、重规划、缓存/节流消融 | MAP-16/18 × on/off 或版本化策略 × ≥3 次 | 不得把预算增加当作规划收益 |
| E3 | Reflection 激活后收益 | 激活率和激活后恢复率 | 优先从合法 MAP-22 漫长失败局筛选；Reflection on/off × ≥3 次 | Pilot 确认至少出现 trigger 才讨论效益 |
| E4 | MAP-30 机制与预算 | 消除多级截尾造成的地板假象 | 以 V12 扩展结果定阶梯；高预算须单独上限 | 不作为常规矩阵默认批量启动 |
| E5 | 独立验证 | 检查探索结论是否泛化 | 在 `seed_space` 许可下选择未参与调参的 seed 与候选地图 | 若无 holdout，标为探索性 |

**执行成本策略**：先从已跑 V12 的成本分布估价，再做不请求的 `preflight`，形成 `docs/v13/live-budget-proposal.md`，列出每组 `最大子局数 × 单局请求/token/金额硬上限`、实验总上限、已批准金额及剩余额度。没有授权时，以上各组全为 `PLANNED_ONLY`；不要用历史 V12 的 ¥0.56 剩余额度规避本条。

---

## 4. 按批次执行（Batch 0–13）

### Batch 0｜基线审计与 V13 工作台（P0 基础）

**任务：V13-00-01 ~ 00-06**

- [ ] `00-01` 获取最新 HEAD、记录工作区 `git status`、Python/uv/Windows 环境；不覆盖用户未提交的变更，不强制重置分支。
- [ ] `00-02` 按 §1.2 阅读资料、列出相关调用链与现有测试；尤其核对 V12 的 159 局、消融、DCR 状态、CI、现有对照字段。
- [ ] `00-03` 运行 V12 质量门禁，保存**命令、实际退出码、测试数量、环境**；旧结果与仓库文档有差别就先查明。
- [ ] `00-04` 建立 `docs/v13/audit.md`：已具备 / 待改进 / 不做 / 潜在数据风险 / P0–P2 映射。
- [ ] `00-05` 建立 `docs/v13/progress.md`（任务清单、依赖、提交、验收、真实状态）、`docs/v13/decisions.md`（架构决策）。
- [ ] `00-06` 建立 `docs/v13/experiment-protocol.md` 初稿，先冻结比较口径，再做策略优化。

**Gate 0**：可精确复述 V12 现状与问题；未改冻结资产；V12 回归有可审计基线报告。

### Batch 1｜P0-5 公平性 / 协议 / 数据可比性核心修复

**任务：V13-01-01 ~ 01-07**

- [ ] `01-01` 为策略比较构造一个明确的 **comparability profile**：环境/Seed、Provider/模型、共享 prompt、有效采样参数、动作契约、规则/指标版本、预算、历史窗口、实验模式、运行时版本。
- [ ] `01-02` 处理“共享 Prompt 与策略注入差异”的核验：允许 on/off 只改变指定开关；记录**唯一被操纵变量**；存在额外开关/模型配置漂移时拒绝做因果比较。
- [ ] `01-03` 记录温度/top_p/seed/模型版本支持情况；未被 Provider 确认的值不能写成“已固定”。如模型接口不支持，不得硬编码虚假字段。
- [ ] `01-04` 补充实验身份/配置 hash 和 `replicate_index`，实现独立重复且不重复计费；旧数据升级读取兼容，不在旧文件上原地迁移。
- [ ] `01-05` 扩展两独立父实验之间的配对检查，支持 agent 同 ID 不同 config 的 on/off；V12 的 `condition_key` 不动或通过新 schema 保持兼容。
- [ ] `01-06` 加跨版本“硬拒绝/仅描述/同条件配对”判据及用户可见不可比原因；补历史回归测试，尤其 DCR-V12-01/02/06。
- [ ] `01-07` 实现 protocol manifest 只读摘要 / 冻结检查（来源、参数、实验目标、主要/次要指标、停止规则）。

**Gate 1**：旧实验均能读取；独立重复不会被幂等去重；两个不同版本不会被误并；相同策略不同配置能跨实验安全配对；显式控制额外请求费用；所有检查有单测。

### Batch 2｜P0-1 稳定性测量与重复实验工作流

**任务：V13-02-01 ~ 02-07**

- [ ] `02-01` 检查现有 `--replicate-of`、`--rerun-of`、`--supplement-of`：复用并扩展 `replicate_index`，保证中断后 `--resume` 不会丢失/重复子局。
- [ ] `02-02` 允许用户选择合法地图/Seed/策略/重复数，并在预检时提供 **总子局数、费用范围、实验最大硬门禁、所需时间预算**（如无可信时间数据，只给请求和费用，不编造耗时）。
- [ ] `02-03` 只读导入 V12 历史结果，按真正可比较的配置分组；再次独立复算历史的成功率、翻转率、失败与预算比例。
- [ ] `02-04` 输出 `repeat_variability.csv/json/md`：每条件成功数/N、任何结局变动、重复内费用/决策区间、缺失/截尾、版本不匹配数量。
- [ ] `02-05` 防止数据单位错误：3 次模型重采样 ≠ 3 个新环境 Seed；按 seed 分块显示，不把同一 seed 的重复当成地图泛化能力。
- [ ] `02-06` 对比 UI 新增“样本不足 / 模型随机 / 稳定性未知”显著提示；报告中区分 `DESCRIPTIVE_ONLY` 与稳定可重复证据。
- [ ] `02-07` 对模拟场景测试分组、重复、终态分母；未来 LIVE 列成未批准计划而非假数据。

**Gate 2**：能从历史数据重建 V12 公布的数值与跨版本排除理由；模拟重复互不覆盖；报告不因重复次数增加就自动给架构排名。

### Batch 3｜P0-2 Memory 策略优化

**任务：V13-03-01 ~ 03-07**

- [ ] `03-01` 审计 `memory.v1` 写入条件、容量 24、渲染长度（V12 默认 ≤1200 字符）、已有记忆更新/消费链路和 MAP-22 `route_log`。
- [ ] `03-02` 定义版本化配置：`memory.enabled`、`route_log.enabled`、`route_write_every`，如有必要再增加去重、压缩、相关性选择。默认行为必须兼容 V12，不要偷偷改变 `memory.v1` 的历史含义；新策略可叫 `memory.v2`。
- [ ] `03-03` 路线记忆必须只基于**已接受的公开移动结果**累积，不计被拒移动；记录方位序列时明确重试、循环、折返，不使用隐藏地图。
- [ ] `03-04` 验证自动写路线时执行了什么：若调用环境 `write_memory`，必须计入动作/决策预算、成功与失败、记录事件；若纯内部 context 记忆，必须另标机制，不能假装两者等价。
- [ ] `03-05` 针对 Memory 三个潜在瓶颈做结构化诊断：没有记录 / 记录错误或过短 / 有记录但未被决策引用；使用 `path_state`/公开 key 时与 V10 指标的命名空间分开。
- [ ] `03-06` 设计 MAP-22 on/off 与可选压缩/检索消融；用离线可控轨迹证明 route_recall、wasted_moves 以及请求/token/动作消耗的口径正确。
- [ ] `03-07` 输出 `docs/v13/memory-study.md`：明确假设、旧证据、配置、成本权衡、下一轮 LIVE 待批准矩阵。

**Gate 3**：不会将拒绝移动记为路线；新增策略默认不污染旧 V12；记忆写入与费用/决策计账一致；可检索或显示有效记忆证据，不允许只凭成功率声称“记忆有效”。

### Batch 4｜P0-3 Planning 策略优化

**任务：V13-04-01 ~ 04-07**

- [ ] `04-01` 审计现有 Planner 子目标/监控/重规划次数、`purposes` 计费，以及 MAP-16 对照中的重规划失败。
- [ ] `04-02` 定义 `planning.v2`（或版本化新 config），分别配置：Planner 调用频率、无进展重规划阈值、无效目标恢复、预算感知；保留 `planning.v1` 作为原样对照。
- [ ] `04-03` Planner 输出结构化目标和公开成功条件，不可直接读取私有状态，不允许从规则源码抽取不可见答案。
- [ ] `04-04` 减少不必要重复规划：只有公开进展变化/目标完成/连续错误/预算触发才重规划；增加 cache/TTL 时需测试因过期而不及时改计划的反例。
- [ ] `04-05` MAP-16/18 设计“规划开/关”“重规划开/关”“低频 Planner”三类**分离**消融，不把多个开关同时调优后称为单因子效果。
- [ ] `04-06` 明确输出每个 Planner 请求的作用、关联决策与 token/费用/延迟，支持同条件 Basic 的成本收益对照。
- [ ] `04-07` 输出 `docs/v13/planning-study.md`，包含成功路径和失败路径的可解释案例、哪些是证据、哪些是假设。

**Gate 4**：测试覆盖目标达成、无进展、冲突、预算耗尽、Planner 无效输出；不会请求预算外模型；不能借改预算掩盖 Planning 实际增加的费用。

### Batch 5｜P0-4 开关消融与 P0-6 核心结果验证

**任务：V13-05-01 ~ 05-07**

- [ ] `05-01` 编制同一开关 on/off 的标准模板：Memory、Planning、Reflection；记录共享 prompt/contract/版本、单一操纵变量，允许两个独立父实验配对。
- [ ] `05-02` 计划 MAP-16 的 Planning 消融、MAP-18 的 Memory 消融、MAP-22 的 route_log 消融（均列合法 seed/重复、成功/失败/费用指标）。
- [ ] `05-03` 明确不同受测版本：原 `memory.v1`/`planning.v1` 与优化版之间属于 **版本比较**，不能混充“只关闭一个开关”的消融；单因子消融需要同一版本。
- [ ] `05-04` 从 V12 原始 CSV、报告、DCR 中抽取基线，对 MAP-16/18/22 各建一个 `evidence-pack`（原始 run refs、有效分母、反例、截尾、费用、结论强度）。
- [ ] `05-05` 自动生成预检与 LIVE approval proposal；**禁止自动提交**。
- [ ] `05-06` 用户若未批准 LIVE，则用模拟轨迹跑完实验管线，并在所有结果标题标明 `ENGINEERING_VALIDATED / LIVE_PENDING`，不生成臆造的模型优势。
- [ ] `05-07` 对照结果存在反向、零提升或成本升高时保留负面结果；不能为了达到预设涨点删除条件。

**Gate 5**：Memory/Planning 代码逻辑通过可控单因子消融；真实新增成效没有用户授权则一律记待验证；旧的 159 局绝不被改写。

### Batch 6｜P1-1 Reflection 真触发与可归因恢复

**任务：V13-06-01 ~ 06-07**

- [ ] `06-01` 复盘 `DCR-V12-05`：MAP-16 终止太快，原 Reflection 消融 `reflection_triggered=0`，所以结果无效。
- [ ] `06-02` 在公开事件的条件下定义 trigger：连续拒绝动作、重复无进展、动作环、失败后重规划；记录触发器命中条件、决策索引、前后可见证据。
- [ ] `06-03` 以 MAP-22 的长失败前缀或其他通过筛查的合法场景做测试；**先用模拟轨迹证明 trigger 确实触发**，并证明不会在终止后/成功后继续调用模型。
- [ ] `06-04` 增加冷却时间与最高触发次数，避免无限反思；Reflection 的模型额外请求必需计入同一账本。提供 trigger-only 与 disabled 对照，防止“判断触发”本身偷偷注入额外有利提示。
- [ ] `06-05` 记录激活率（eligible / triggered）、触发后恢复率、误触发、浪费的 token/决策、负收益案例；零触发样本标 `NO_TREATMENT_EXPOSURE`，不是“反思无效”。
- [ ] `06-06` 设计独立 LIVE 小矩阵、请求用户单独批准；若未获批准，完成离线反事实/模拟，并在报告中明确不能推断真实效果。
- [ ] `06-07` 输出 `docs/v13/reflection-study.md` 与专门回归测试。

**Gate 6**：至少有一个可复现 **SIMULATED** 轨迹真实触发并写入事件；on/off 从 trigger 维度有可观察差异；如未获 LIVE 授权，报告不得宣称反思实测有效。

### Batch 7｜P1-2 MAP-30 与 P1-6 六图效度审计

**任务：V13-07-01 ~ 07-07**

- [ ] `07-01` 独立重分析 MAP-30 原预算阶梯：90 requests、200k input tokens、单局 ¥0.20 截尾，180 requests 后出现 `ACCUSATION_REJECTED` 等真实机制失败。
- [ ] `07-02` 在预检页增加针对长轨迹地图的预算分解和**预计可支撑回合数的范围**（必须来自观测到的 token/回合分布，不可编造承诺）。
- [ ] `07-03` 设计请求/token/金额预算的三维阶梯实验；V12 提示的 ≥180 请求、≥600k token、≥¥0.25/局仅是**需批准的候选档**，不是自动启用的默认预算。
- [ ] `07-04` MAP-30 失败分类：预算截尾、证据不足、已到法庭但指控被拒、推理链中途失败；全部绑定公开动作证据。
- [ ] `07-05` 审查六图 MAP-08/16/18/22/26/30：成功率天花板/地板、关键机制是否真的被触发、指标是否可用、样本是否有梯度、旧构念效度状态。
- [ ] `07-06` 给 MAP-08/26（易天花板）提出“保留为回归能力案例 / 暂不作为区分度排名样本”的判断；可从 30 个现有世界中推荐替代诊断地图，但**不自动改 V10 规则或凭空构造新 seed**。
- [ ] `07-07` 输出 `docs/v13/map-validity.md` 和 MAP-30 独立报告，特别区分“工程 Gate `VALIDATED`”与“构念效度充分验证”，不得以 30/30 工程可运行声称 30/30 构念可信。

**Gate 7**：每张重点地图具备效度标签（`SUITABLE / CEILING / FLOOR / CENSORED / INTERFACE_ARTEFACT / NEEDS_EVIDENCE` 可复合），有证据来源和适用限制。

### Batch 8｜P1-3 失败诊断与 P1-4 能力画像

**任务：V13-08-01 ~ 08-07**

- [ ] `08-01` 复用 V12 `lab/diagnostics.py`，核对所有 Finding 是否能回溯到具体公开 decision/event；修复误分类和重复归因。
- [ ] `08-02` 用分层归因：`INTERFACE_CONTRACT / MEASUREMENT_COVERAGE / BUDGET_CENSORED / ENVIRONMENT_MECHANISM / POLICY_BEHAVIOUR / PROVIDER / UNKNOWN`；接口问题不能被写成 Agent 能力差。
- [ ] `08-03` 为 Memory route short、Planning 冲突、Reflection 未激活、MAP-30 截尾增加含正反例的离线 fixture。证据不足使用 `NOT_ENOUGH_EVIDENCE`。
- [ ] `08-04` 能力画像按“信息搜集、记忆/追踪、规划/重规划、资源约束、故障恢复、证据推理”等**地图机制标签**组织，而不是对 326 个异质指标不加区分平均。
- [ ] `08-05` 每维展示：适用图数、可测样本数、成功/失败/截尾、代表性指标和证据等级；缺失机制不记为 0，数据不足不强制六维打分。
- [ ] `08-06` 计算机制画像的版本适用性与标注状态；`human_approved` 必须仅由真实人工批准，Agent 不得自行盖章。
- [ ] `08-07` 生成 `docs/v13/diagnosis-taxonomy.md`、`docs/v13/capability-profile.md`，附可审计的 CSV/JSON 输出契约。

**Gate 8**：任一非空结论能打开对应 run/decision 证据；诊断层未调用模型、未读取 hidden truth；跨地图绝对值不被违规合并。

### Batch 9｜P1-5 可视化与 P2-3 Web UI

**任务：V13-09-01 ~ 09-07**

- [ ] `09-01` 复查 Lab 的配置、监控、结果和历史页；围绕真实任务流程提升导航，不另起前端框架或重造 Streamlit 服务。
- [ ] `09-02` 对照视图同时显示相同条件的不同 Agent：终态、成本、请求、被拒动作、首次重要轨迹分叉、机制标签、可比性状态。
- [ ] `09-03` 增加重复实验视图：相同 seed 的 N 次运行分布/翻转、被截尾个数、采样配置未知提示；默认不展示可误导的“模型总榜”。
- [ ] `09-04` 六图特色可视化按“可追溯的公开事件”展示；MAP-22 被拒移动不能画成已走边；MAP-30 的证据时间线需区分已观察/推断/未知。
- [ ] `09-05` 实验配置页强调 `preflight`、费用硬门禁、授权状态，以及离线/模拟/LIVE 区分；没授权时按钮绝不能触发付费请求。
- [ ] `09-06` 加大数据列表的 server-side 或惰性分页，修复刷新/恢复/筛选的状态丢失；保留 V11 单局入口与 V12 旧实验历史。
- [ ] `09-07` 执行浅/深主题、430px 窄屏、键盘可达性/对比度审计，截图与 DOM 检查写入 V13 验证文件；真机读屏若无条件明确 `NOT_VERIFIED`，不伪称。

**Gate 9**：浏览器上能从配置 → 预检 → 模拟运行 → 结果 → 能力画像 → 单步证据 → 导出走通；数据来源和不可比原因始终可见。

### Batch 10｜P2-4 自动报告 + P2-6 数据/费用审计

**任务：V13-10-01 ~ 10-07**

- [ ] `10-01` 复用 `lab/report.py`，自动输出 Markdown/CSV/JSON：研究问题、实验设置、模型与版本、有效分母、结果、负面结果、成本、失败原因、统计限制、下一轮可验证假设。
- [ ] `10-02` 默认**离线模板化报告**，不使用 LLM 解说；若考虑 LLM 润色，必须独立可选、独立费用批准、不能杜撰结论或覆盖基础报告。
- [ ] `10-03` 所有报告结论带定位信息（`experiment_id/run_id/decision/event` 或明确数据汇总来源）；结论等级至少分 `SUPPORTED / TENTATIVE / INSUFFICIENT / NOT_TESTED`。
- [ ] `10-04` 对本地历史账本执行只读一致性审计：父子 run 数量、起止状态、请求 token/费用、`run_started/run_settled`、unknown spend、重复账单与孤儿任务。
- [ ] `10-05` 实现 Provider 后台账单的**本地离线导入与对账接口**（若用户提供经脱敏 CSV），并定义容差、货币/时区/统计窗口规则；如未提供账单，写 `NOT_RECONCILED_EXTERNAL`，不得假装完成后台对账。
- [ ] `10-06` 任何修复都不能修改历史账本；发现不一致生成 DCR 与差额表，保留原始证据。
- [ ] `10-07` 做报告快照测试、缺失/截尾/成本未知测试，以及不携带密钥或私有真值的脱敏测试。

**Gate 10**：从只读 V12 数据可以生成结构化报告和本地账本一致性检查；外部账单不存在时清楚标注；报告中的每条数字可复算。

### Batch 11｜P2-5 第三方 SDK 完善

**任务：V13-11-01 ~ 11-06**

- [ ] `11-01` 复核现有 `agent_arena.lab.sdk` 和 `examples/custom_agent/`，保持原 `agent_policy_v1` 兼容或提供清晰 version adapter。
- [ ] `11-02` 新增 SDK 接入自检：Observation 公开字段、Action 格式、生命周期钩子、网关预算、模拟模式行为、异常隔离、版本标识。
- [ ] `11-03` 实现最简“编写/注册/运行/对照”本机示例与常见错误提示，确保不要求自定义策略直接接触 Provider secret。
- [ ] `11-04` 处理 agent 抛异常或非法动作时的回收、父实验继续、敏感错误截断、总预算硬停止；避免一个插件损坏全局状态。
- [ ] `11-05` 编写第三方插件 allowlist/受信任边界说明；**不是沙箱**，不支持用户上传任意 Python 代码到公网运行。
- [ ] `11-06` 新旧 SDK 兼容测试及文档示例自动运行验证。

**Gate 11**：一个外部本机示例 Agent 可通过相同公开观察/预算/动作校验完成 SIMULATED 试验，异常时不会让其他 run 丢失或越权访问隐藏字段。

### Batch 12｜P2-1 CI 强化 + P2-2 性能压力

**任务：V13-12-01 ~ 12-08**

- [ ] `12-01` 阅读现有 GitHub Actions job 与 Playwright 安装、`continue-on-error` 原因；锁定浏览器版本/依赖缓存/可观察启动步骤。
- [ ] `12-02` 使用固定的无 API Key、临时 `runs` 路径执行 V11/V12/V13 浏览器 E2E；收集失败截图、日志、浏览器控制台与超时原因。
- [ ] `12-03` **在 CI 连续可靠通过并有证据后**再将 E2E 改为阻断门禁。若未能实际验证 CI，保留非阻断但在 Gap Audit 显式记录，不为达标移除测试。
- [ ] `12-04` 合成 1,000 / 5,000 条历史 run 元信息与代表性事件文件，标明为压力数据，放入临时目录而非真实账本；压测分页、查询、筛选、聚合和下载。
- [ ] `12-05` 记录冷/热加载的耗时、峰值内存、输出大小；先记录 Windows 基线，至少避免页面一次加载全部轨迹或随数据增长无限占用内存。
- [ ] `12-06` 负向场景：损坏 JSONL、进程退出、父子不一致、重复提交、过大导出、费用未知/超限、Provider 错误与网络超时；原来测试已覆盖者只补证据，不重复实现。
- [ ] `12-07` 验证旧 V11/V12 用户流没有性能/交互回归；如果性能较基线恶化，给出定量对照并修复。
- [ ] `12-08` 新建 `docs/v13/performance-report.md`、CI 运行证据、失败回归用例。

**Gate 12**：大历史量能够分页检索且无明显的无界内存增长；报告必须含真实数值和测试环境；CI 结论不得把本地通过等同于 GitHub Actions 通过。

### Batch 13｜P2-7 全面交付、复现与复盘

**任务：V13-13-01 ~ 13-08**

- [ ] `13-01` 整理文档总入口：README、`docs/architecture.md`、`docs/scope/scope.md`、`AGENTS.md`（若确需变更），突出 V13 功能与限制。
- [ ] `13-02` 新建/扩展 `scripts/verify_v13.py`：离线可一键检查协议、真实/模拟隔离、重复身份、消融、Memory/Planning/Reflection fixture、地图效度、报告/账本、30 图冻结、旧数据读取、预算和泄漏。
- [ ] `13-03` 提供 `scripts/demo_v13.py` 或扩展旧 demo：无 API Key 演示三种 Agent + Reflection trigger + 重复比较 + 自动报告，并在页面明确 `SIMULATED`。
- [ ] `13-04` 全量执行 `ruff`、`mypy`、`pytest`、lock、V10 freeze/recompute/independent、V11/V12/V13 自检、可用的浏览器 E2E；记录实际命令、退出码、测试数和 HEAD。
- [ ] `13-05` 对所有已批准的 LIVE 实验（若有）制作只读证据归档；**没有新 LIVE 授权则正常交付全部离线功能**，并列清需要授权才可进行的后续验证。
- [ ] `13-06` 最终 `docs/v13/gap-audit.md`：覆盖全部 P0/P1/P2，每个任务 `DONE / PARTIAL / WAITING_USER_APPROVAL / BLOCKED_EXTERNAL / NOT_DONE`，不许含糊写“全部完成”而无证据。
- [ ] `13-07` `docs/v13/final-report.md`：what / why / how / results / limitations / next；列真实成绩、历史只读结果、模拟测试三个不同来源；写结论强度与已知失败。
- [ ] `13-08` 形成 V13 交付清单、截图/演示数据、运行说明、下一阶段候选项；清除临时敏感文件；按批次提交，最后检查 `git diff --check`、`git status`。

**Gate 13**：P0/P1/P2 的工程交付均有代码或可执行报告和测试；需要付费验证的部分被明确标记，未获授权也不妨碍提交 `LAB_1_1_ENGINEERING_READY`；只有获授权且取得真实证据，才能标 `LAB_1_1_LIVE_VALIDATED`。

---

## 5. 优先级与依赖图（别按编号盲目并行）

```text
Batch 0 基线审计
  └── Batch 1 公平协议 / 配对 / 身份
       ├── Batch 2 重复与稳定性（P0-1）
       ├── Batch 3 Memory（P0-2） ──┐
       ├── Batch 4 Planning（P0-3） ├── Batch 5 消融与核心验证（P0-4/6）
       └── Batch 6 Reflection（P1-1）┘

Batch 0 + 1 ── Batch 7 MAP-30/六图效度（P1-2/6）
Batch 1 + 2 + 7 ── Batch 8 诊断/画像（P1-3/4）
Batch 8 ── Batch 9 UI/可视化（P1-5/P2-3）
Batch 1 + 2 + 8 ── Batch 10 报告/费用（P2-4/6）
Batch 1 ── Batch 11 SDK（P2-5）
Batch 9 + 10 + 11 ── Batch 12 CI/压测（P2-1/2）
全部 ── Batch 13 Final（P2-7）
```

**并行许可**：Batch 3/4/6 可以在 Batch 1 完成且各自改动范围隔离后并行；Batch 7 可与策略实现并行；最终合并前串行运行回归。**禁止**在相同 `runs/lab` 真实预算、同一个单 worker 或同一组接口契约上多进程并发启动有费实验。代码任务可并行，账本/环境版本/实际 API 运行必须统一编排。

建议中间里程碑：

- **M1（批次 0–2）**：实验可比性 + 重复观测体系；不花 API 费。
- **M2（批次 3–6）**：Memory/Planning/Reflection 策略和消融管线；可形成待授权实验单。
- **M3（批次 7–10）**：地图效度、诊断画像、UI、自动报告/本地账本审计。
- **M4（批次 11–13）**：SDK、CI、压测、文档、Lab 1.1 离线交付。
- **M5（有条件）**：用户明确批准后按 E0→E4 分批真实执行，不与 M4 强绑定。

---

## 6. P0/P1/P2 可量化验收总表

| 等级 | 必须通过的验收 | 不满足时的诚实结果 |
|---|---|---|
| P0 | 旧结果读取/复算；重复身份不冲突；公平性 guard；Memory/Planning 单因子离线验证；MAP-16/18/22 证据包；预注册 LIVE 方案 | `ENGINEERING_READY, LIVE_PENDING`，不得宣称能力改进 |
| P1 | Reflection 的模拟 trigger 至少 1 个明确可复现；MAP-30 多级截尾拆分；六图效度标签；诊断证据锚；能力画像无错误归一化；交互回放正常 | 分项 `PARTIAL` 并列未测真实模型原因 |
| P2 | E2E 有 CI 实际证据；历史 1k/5k 压测报告；UI 完整流程；模板报告可复算；SDK 插件异常隔离；本地账本检查；完整最终文档 | CI 或后台账单若外部条件不具备，分别 `NOT_VERIFIED` / `BLOCKED_EXTERNAL` |

**尤其不允许**以“新增代码量”“通过单元测试数”“主矩阵只跑 1 次”的形式代替能力稳定性验证；V13 是否真正改善 Agent 行为只能靠可比的真实模型重复对照判断，未运行应明确为假设。

---

## 7. 必跑的质量门禁与应有产物

### 7.1 质量命令（按仓库当时可用命令复核）

```bash
uv sync --extra web
uv run ruff check .
uv run mypy src
uv run pytest -q
uv run uv lock --check
git diff --check
uv run python -m agent_arena.v10.freeze verify
uv run python -m agent_arena.v10.recompute --check
uv run python -m agent_arena.v10.independent_check --check
uv run python scripts/verify_v11.py
uv run python scripts/verify_v12.py
# V13 新增后：
uv run python scripts/verify_v13.py
uv run python scripts/e2e_web.py --start
uv run python scripts/e2e_lab.py --start
# 若 V13 新增 E2E：运行并记下实际结果
```

Windows 若 shell/cmd 环境不同，按实际环境适配，不能把未执行写成 Pass。Playwright 需要安装时，先在本机或 CI 使用受控版本完成。**不得因某测试暂时失败而直接删除测试或关闭校验规则。**

### 7.2 建议的 V13 文件与文档交付

```text
docs/v13/
  audit.md
  experiment-protocol.md
  progress.md
  decisions.md
  memory-study.md
  planning-study.md
  reflection-study.md
  core-evidence.md
  map-validity.md
  diagnosis-taxonomy.md
  capability-profile.md
  live-budget-proposal.md
  data-and-cost-audit.md
  performance-report.md
  validation-report.md
  gap-audit.md
  final-report.md
  screenshots/             # 可选：真实 UI 截图
  demo/                    # 明确 SIMULATED 的演示包

# 新增模块/文件名由仓库实际组织决定，优先改现有：
src/agent_arena/lab/...
src/agent_arena/ui/lab.py
scripts/verify_v13.py
scripts/demo_v13.py
scripts/...                 # 需要才新增，不造重复 CLI
tests/test_v13_*.py
```

### 7.3 禁止提交或公开的内容

`.env`、API keys、用户私有账单原件、费用凭证中可识别个人账户的内容、未脱敏 trace、`runs/` 整目录、模拟结果冒充 LIVE 的 CSV、依赖真实密钥的默认测试。现有公开仓库的可见性不得扩大；不得自动发布网站。

---

## 8. 遇到不可执行的项目怎么办？

| 阻塞 | 应做 | 不得做 |
|---|---|---|
| 未给 V13 费用授权 | 完成代码/预检/模拟/历史再分析，给出细分费用申请 | 擅自继承 V12 ¥6 授权、触发模型请求 |
| 没有 Provider 后台账单 | 完成本地账本审计、提供离线导入模板并标待对账 | 说“后台已核对无误” |
| 模型不支持固定采样参数 | 记录 `UNSUPPORTED`，增加独立重复并报告输出波动 | 在文档宣称模型 deterministic |
| Seed 白名单不足 | 使用登记 Seed 做重复，并声明缺独立环境 Holdout | 擅自扩大 Seed 空间/改规则 |
| 浏览器 E2E 的 CI 不稳定 | 修复依赖/等待条件/日志；保留显式 gap | 为“全部通过”直接移除测试 |
| 某优化无涨点甚至更差 | 如实保存负面结果，按证据定位机制 | 反复换 Prompt 直到单次成绩好，然后冒充公平对照 |
| 冻结层与优化冲突 | 用 V13 投影、公开提示或策略层修复；不改旧规则 | 直接修改 V10 裁定逻辑、重写历史 trace |

---

## 9. 最终交付回复格式（DS 执行完成时照填）

```text
# Agent-Arena V13 交付结果
- 最终 HEAD / 分支：
- V13 状态：LAB_1_1_ENGINEERING_READY / LAB_1_1_LIVE_VALIDATED / PARTIAL
- 完成情况：P0 x/6、P1 x/6、P2 x/7（逐项表附链接）
- 功能增量：对 V12 做了哪些真实改动（不要重复罗列 V12 原有功能）
- 测试：pytest / ruff / mypy / V10 freeze / verify_v11/12/13 / E2E 的实际结果
- 实验：HISTORICAL / SIMULATED / LIVE 分组，新增 LIVE 局数与金额（若无写 0）
- 主要结论：Memory、Planning、Reflection、MAP-16/18/22/30 的证据强度
- 不支持的主张：样本不足/版本不可比/未触发/预算截尾等
- 费用：本次新增 LIVE 使用量、已批准总额、剩余额度、是否后台对账
- 未完成/暂缓项：必须解释阻塞和下一步
- 关键文档：audit / protocol / final-report / gap-audit / 复现命令
- 所有提交记录与可回滚办法：
```

### 完成标准一句话

**V13 不以“再增加一堆功能”为成功，而以“在现有 Lab 1.0 上建立可信、可复现、可诊断、可控预算的 Agent 策略改进闭环”为成功。**

---

## 10. 交给 DeepSeek 的最终执行命令（自然语言）

> 请你作为 Agent-Arena 的主程，按照本 `V13` 提纲直接执行全部 P0、P1、P2。先审计最新仓库和 V12 现有实现，按 Batch 0–13 的依赖分批开发、测试和提交；以复用为原则，不重复重写 V12 已交付模块。不得修改 V8/V9/V10 冻结环境及历史实验账本；测试、演示和报告不能将 `SIMULATED` 冒充模型真实能力。**除非我另行明确批准 V13 的模型、矩阵和总费用预算，否则绝不执行新付费 API 请求**，需要 LIVE 的任务先完成代码与预检并标记 `WAITING_USER_APPROVAL`。本轮不要做 macOS、Ollama、公网部署、跨模型排行榜。最后提供实际 commit、测试结果、各任务状态、实验方案、最终报告和剩余差距；对优化失败的实验也如实记录，不要为了涨点改规则或挑选结果。
