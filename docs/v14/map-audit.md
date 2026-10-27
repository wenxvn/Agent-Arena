# V14 地图适用性审计（P1-1 / P1-2）

> 只读审计：不改 V10 规则、不新增 seed、不修改历史 trace。
> 数据来源：`docs/v12/real-runs/*.csv`（`HISTORICAL`）。

## 1. 六图标签复算

| 地图 | 标签 | 有效分母 | 成功 | 成功率 | 独立 seed | 机制触发 | 证据版本 | 状态 |
|---|---|---:|---:|---:|---|---|---|---|
| MAP-08 | `CEILING` | 9 | 9 | 1.0 | [0, 1, 2] | UNKNOWN (0 observed / 9 runs) | V12 real-runs（只读） | `DESCRIPTIVE_ONLY` |
| MAP-16 | `SUITABLE` | 35 | 9 | 0.2571 | [0, 1, 2] | UNKNOWN (0 observed / 35 runs) | V12 real-runs（只读） | `DESCRIPTIVE_ONLY` |
| MAP-18 | `SUITABLE` | 37 | 8 | 0.2162 | [0, 1, 2, 3, 4] | UNKNOWN (0 observed / 37 runs) | V12 real-runs（只读） | `DESCRIPTIVE_ONLY` |
| MAP-22 | `SUITABLE` | 20 | 3 | 0.15 | [0, 1, 2] | UNKNOWN (0 observed / 21 runs) | V12 real-runs（只读） | `DESCRIPTIVE_ONLY` |
| MAP-26 | `CEILING` | 9 | 9 | 1.0 | [0, 1, 2] | UNKNOWN (0 observed / 9 runs) | V12 real-runs（只读） | `DESCRIPTIVE_ONLY` |
| MAP-30 | `CENSORED` | 27 | 0 | 0.0 | [0, 1, 2] | UNKNOWN (0 observed / 27 runs) | V12 real-runs（只读） | `DESCRIPTIVE_ONLY` |

> `SUITABLE` 只表示现有样本里出现成功率梯度；`CEILING`/`CENSORED` 只描述样本形态；机制触发全未知的图不能写 0/N。

### 1.1 标签含义与限制

| 标签 | 含义 | 不能推出的结论 |
|---|---|---|
| `CEILING` | 现有样本全部成功 | 不能推出「该图没有难度」或「任何策略都能过」 |
| `SUITABLE` | 现有样本出现成功率梯度 | 不能推出构念效度充分或策略引起改善 |
| `CENSORED` | 失败主要是预算截尾 | 不能推出「模型能力弱」 |
| `FLOOR` | 全部失败且截尾占比低 | 不能推出「该图无法通过」 |

## 2. MAP-30 三维预算阶梯

- 观测局数：27

| 预算档位 | 局数 | 成功 | 截尾 | 机制失败 | 到法庭被拒 | 瓶颈轴 | 瓶颈证据 | 最大决策 | 最大 token | 费用 CNY |
|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|
| `req=90|tok=200000` | 9 | 0 | 8 | 1 | 1 | `REQUESTS` | 8/8 局撞满请求上限。 | 90 | 166960 | 0.887105 |
| `req=180|tok=200000` | 9 | 0 | 5 | 4 | 4 | `UNSPECIFIED` | 5 局截尾，但公开终态码没有暴露具体撞到哪一维（请求/token/费用），不能强行归因。 | 147 | 191524 | 1.0991872 |
| `req=180|tok=600000` | 9 | 0 | 7 | 2 | 2 | `UNSPECIFIED` | 7 局截尾，但公开终态码没有暴露具体撞到哪一维（请求/token/费用），不能强行归因。 | 168 | 252683 | 1.49856088 |

> 预算阶梯的瓶颈轴必须分开看：请求先撞说明「步数不够」，token 先撞说明「上下文太长」，金额先撞说明「单价太高」。三者不能合并成一句「能力不足」。

### 2.1 保守可达区间

| 预算档位 | 可达决策区间 | 已观测最大决策 | token/决策 (p10/p50/p90) |
|---|---|---:|---|
| `req=90|tok=200000` | 113–155 | 90 | 1286.78 / 1700.35 / 1760.37 |
| `req=180|tok=200000` | 111–155 | 147 | 1288.24 / 1717.07 / 1786.57 |
| `req=180|tok=600000` | 334–460 | 168 | 1302.46 / 1739.22 / 1794.41 |

> 区间来自**已观测** token/决策分布：下限按最贵观测、上限按最便宜观测。它不是对真实模型的承诺，也不含墙钟时间；预检页只能显示「估计范围」。
> 候选档**需批准**，不得自动启用；新 MAP-30 高成本 LIVE 不默认纳入方案 A。

## 3. 候选图公开机制审计（只读）

| 地图 | 世界/难度 | seed 空间 | 公开字段 | 动作数 | 历史局 | 长失败前缀局 | 反思候选 |
|---|---|---|---:|---:|---:|---:|---|
| MAP-19 | volcano / 简单 | [0, 1, 2, 3] | 16 | 5 | 0 | 0 | `NEEDS_MORE_EVIDENCE` |
| MAP-20 | volcano / 中等 | [0, 1, 2, 3] | 16 | 5 | 0 | 0 | `NEEDS_MORE_EVIDENCE` |
| MAP-29 | castle / 中等 | [0, 1, 2, 3] | 13 | 5 | 0 | 0 | `NEEDS_MORE_EVIDENCE` |

逐图明细：

### MAP-19 · 温度临界点

- 规则版本：`v10.map19.1`，`rule_hash = 57b2e25d838f`
- 主指标：`map19.v10.production_credit`（5 条指标规格）
- 公开规则条数：6
- 动作：adjust_loads, forecast_next, read_temperature, set_cooling, wait
- 历史终态分布（V12 CSV）：无
- V10 登记：V10 0/3（seed 0,1,2；CNY 0.15646452；含未知消费；另有 7 局重跑/中断保留）
- 最长决策数 / 请求数：0 / 0
- 本审计只读公开规则与历史终态；**不修改地图规则、不新增 seed、不声称这些图一定更适合反思**。

### MAP-20 · 冷却网络

- 规则版本：`v10.map20.2`，`rule_hash = 9640623b4f0c`
- 主指标：`map20.v10.production_credit`（5 条指标规格）
- 公开规则条数：10
- 动作：adjust_loads, open_bypass, read_temperature, set_flow, wait
- 历史终态分布（V12 CSV）：无
- V10 登记：V10 0/3（seed 0,1,2；CNY 0.24980340；另有 6 局重跑/中断保留）
- 最长决策数 / 请求数：0 / 0
- 本审计只读公开规则与历史终态；**不修改地图规则、不新增 seed、不声称这些图一定更适合反思**。

### MAP-29 · 不可靠的证人

- 规则版本：`v10.map29.1`，`rule_hash = 90fd7560d393`
- 主指标：`map29.v10.contradiction_detection_rate`（6 条指标规格）
- 公开规则条数：6
- 动作：ask, compare_testimony, investigate, move, submit
- 历史终态分布（V12 CSV）：无
- V10 登记：V10 0/3（seed 0,1,2；CNY 0.10676056）
- 最长决策数 / 请求数：0 / 0
- 本审计只读公开规则与历史终态；**不修改地图规则、不新增 seed、不声称这些图一定更适合反思**。

## 4. 适用范围结论

- 六图结论**保持** V13 的标签（`CEILING` 08/26、`SUITABLE` 16/18/22、`CENSORED` 30），
  但机制触发一律显示 `UNKNOWN (0 observed)`，不再写 `0/N`；
- MAP-30 的 0 成功必须读作「没测完」，不能读作能力结论；
- 候选图 MAP-19/20/29 的结论最多到 `NEEDS_MORE_EVIDENCE`：
  历史样本不足以支持「更适合反思」的断言，需要离线触发诊断 + 真实 Pilot。
