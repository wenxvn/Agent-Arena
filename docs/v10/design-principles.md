# V10 设计原则（30 图核心机制重构、难度校准与多 Seed 有效性验证）

- 适用范围：`src/agent_arena/v10/`、`docs/v10/`、`runs/v10/`；V8/V9 只读（`freeze verify` 守卫）。
- 本文件是执行原则清单，不是结果报告；结果见 `final-report.md`，逐图证据见 `maps/`。

## 1. 测量优先于成功率

1. 目标是“可证伪、可重复、有区分度的能力测量”，不是提高通关率。
2. 不按单一模型成败改规则、改难度标签或改 seed；补跑只允许用于修复**接口/账本缺陷**，
   必须新 `run_id` 并在 `mimo-preregistration.json` 记录原因。
3. 成功率只作描述；`n=3`、单 replicate、单模型**不作显著性断言**，禁止跨模型排名。

## 2. 机制必须真实、独立、可触发

1. 每张图保留自己的世界身份、独特动作因果与玩法；不把 30 图统一改造成模板状态机。
2. 核心机制要么是通关必要条件（`FORCED`），要么有经证实的连续质量/成本指标（`OPTIONAL`）；
   不允许“既非必要、又无指标”的装饰性机制。
3. 每图必须声明 `mechanism_triggered()`：Oracle 各 seed 都要真实触发核心机制，
   否则视为实例采样失败（见 `baseline-results.md` 的“机制触发”列）。

## 3. 反旁路与合法替代

1. 每条 V9 `BYPASS` 必须有消融反例（`ABLATIONS`）证明机制不可绕；
   消融率与反例测试登记在 `decision-register.md` 与各 `dcr/DCR-*.md`。
2. 合法替代策略（例如 MAP-26 盲换、MAP-04 绕行）**保留**，但必须能被连续指标区分
   （备件数、余量、精度、后悔值），不得强行改成失败。
3. 区分“机制是通关必要条件”与“机制只影响效率”——后者写 `OPTIONAL` 并给出质量指标。

## 4. 公开接口透明，但不泄露答案

1. `public_rules()` + `SHAPES` + 带类型的动作契约 = 模型应知道的全部接口信息；
   字段类型由 `V10Action` 注解渲染（`v10/contract.py`），不靠模型猜。
2. 隐藏真值只进 `sealed_truth()`、`scenario_hash` 与 judge，**不得**进 Observation、prompt、
   工具描述或 trace 的 agent-visible 部分。
3. 公开“因果与单位”（如阀门只公开因果、不公开开向）属于接口透明；
   公开“答案与最优路线”属于泄漏。

## 5. 实例化与 seed 协议

1. 每图至少 3 个环境 seed（高风险图 5–10 个），seed 必须改变初始状态、事件序列或隐藏真值；
   仅改变 `scenario_hash` 不等于改变实例（用 `seed_effective` 判定）。
2. 环境 seed、policy seed、replicate 三个维度分开记录；provider 不支持生成 seed 时不写“模型 seed”。
3. 无法参数化的图（V10 尚未建原生运行时的 7 张）如实标注缺口，不用三次重复冒充三 seed。

## 6. 指标与五态

1. `metric_schema_version=v10`：V7/V8 的 154 条只读保留，V10 新增规格并列，不跨版本求均值。
2. 五态优先级 `INVALID_TRACE > UNAVAILABLE > NOT_APPLICABLE > CENSORED > VALID`；
   不得把所有 `None` 机械改成 `CENSORED`。
3. 每条指标声明 `role`（primary/secondary/guardrail/diagnostic）、公式、分母、零分母口径、
   截尾口径、单位与 `valid_range`；跨图只比较语义同构量，不做单一榜单加总。
4. 每图 1–2 条主指标；主指标必须能区分“真机制”与“替代策略”。

## 7. 预算与账本纪律

1. 付费调用总上限 **CNY 10**（含预留），所有 V10 账本共享同一额度，拆分账本会被 `prior_spend` 计入。
2. 请求前按登记上限预留、按供应商真实 usage 结算；供应商费用未知 → 标记
   `UNKNOWN_PROVIDER_SPEND`、保留全额预留、立即封账，**不得当 0 处理**。
3. 先 dry-run、再小批、再全矩阵；失败与中断记录全部保留，不静默覆盖。
4. 每次真实运行记录 `run_id、map、seed、replicate、模型与温度、scenario/rule/metric/prompt hash、
   commit、终止结果、决策数、主指标、成本`。

## 8. 工程质量

1. 规则变更必须 DCR（新旧 hash 并列 + 对照 + 反例测试）；接口/指标修复也要留版本与证据。
2. 每批结束运行：`freeze verify`、scoped `ruff`、`mypy src`、`pytest`，记录真实退出码。
3. 文档中的数字必须能由仓库内命令复算；不能复算的数字不写进结论。
