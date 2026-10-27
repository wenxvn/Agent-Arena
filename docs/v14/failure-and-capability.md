# V14 失败归因与能力画像（P1-3 / P1-4 / P1-6）

> 只读分析：不修改 V13 的 taxonomy / capability 输出，只在之上补充字段。

## 1. 七层归因与正反 fixture（P1-3）

| 层 | 是否可进能力分母 | 含义 |
|---|---|---|
| `INTERFACE_CONTRACT` | **否** | 接口/契约问题（不是能力） |
| `MEASUREMENT_COVERAGE` | **否** | 测量覆盖问题（不是能力） |
| `BUDGET_CENSORED` | 是 | 预算截尾（没测完） |
| `ENVIRONMENT_MECHANISM` | 是 | 环境机制真实触发但未达成 |
| `POLICY_BEHAVIOUR` | 是 | 策略可观察行为 |
| `PROVIDER` | **否** | Provider/基础设施 |
| `UNKNOWN` | **否** | 证据不足 |

### 1.1 三个 fixture

| fixture | 期望层 | 可进能力分母 | 被拒步 | 有公开进展 | 读法 |
|---|---|---|---:|---|---|
| `REJECTED_NO_PROGRESS` | `POLICY_BEHAVIOUR` | 是 | 3 | 否 | 被拒且没有公开进展 → 归因到策略/接口层，可以进能力分母；但若被拒是契约形状导致，则应改判 INTERFACE_CONTRACT（见反例）。 |
| `PROGRESS_THEN_BUDGET_CENSORED` | `BUDGET_CENSORED` | **否** | 0 | 是 | 有公开进展但预算耗尽 → 归因到 BUDGET_CENSORED，**不得**算进能力分母，也不得写成「推理能力极弱」。 |
| `INTERFACE_ARTEFACT` | `INTERFACE_CONTRACT` | **否** | 2 | 否 | 同样「被拒且无进展」，但原因是契约形状 → INTERFACE_CONTRACT，**不得**进能力分母。这就是正反 fixture 必须成对存在的原因。 |

> 「被拒无进展」与「有进展但预算耗尽」必须分开；「契约形状导致被拒」必须再单独一层。三者混算会同时高估接口缺陷与低估能力。

### 1.2 锚点校验

- 本批没有逐局 Finding 输入（历史 CSV 不含 Finding 明细）；锚点校验逻辑由 3 个 fixture 与单测覆盖。
- 规则：没有 (run_id, decision_index, action, public_result) 的结论只能标 `UNANCHORED`，不得写成「Agent 不理解……」。

## 2. 六维能力画像（P1-4）

- 标注状态：`agent_reviewed`
- 聚合规则：按机制维度聚合，不对异质指标求总分；每个维度都带适用样本、独立 seed、重复数与观察缺口。

| 维度 | 状态 | 适用图 | 已观测图 | 可测局 | 独立 seed | 重复编号 | 成功 | 机制失败 | 截尾 | 成功率 | 缺口 |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| 信息搜集 | `AVAILABLE` | 10 | 3 | 38 | 3 | [0] | 21 | 15 | 2 | 0.5526 | NO_REPLICATES, HAS_CENSORED_RUNS, MISSING_MAPS |
| 记忆 / 状态追踪 | `AVAILABLE` | 7 | 1 | 20 | 3 | [0] | 3 | 15 | 2 | 0.15 | NO_REPLICATES, HAS_CENSORED_RUNS, MISSING_MAPS |
| 规划 / 重规划 | `AVAILABLE` | 10 | 2 | 72 | 5 | [0, 1, 2] | 17 | 54 | 1 | 0.2361 | HAS_CENSORED_RUNS, MISSING_MAPS |
| 资源约束 | `AVAILABLE` | 13 | 4 | 108 | 5 | [0, 1, 2] | 26 | 61 | 21 | 0.2407 | HAS_CENSORED_RUNS, MISSING_MAPS |
| 故障恢复 | `UNAVAILABLE` | 9 | 0 | 0 | 0 | [] | 0 | 0 | 0 | — | UNAVAILABLE, FEW_INDEPENDENT_SEEDS, NO_REPLICATES, MISSING_MAPS |
| 证据推理 | `AVAILABLE` | 11 | 2 | 36 | 3 | [0] | 9 | 7 | 20 | — | NO_REPLICATES, HAS_CENSORED_RUNS, MISSING_MAPS |

> `UNAVAILABLE` 是「没有可测样本」，不是「能力为 0」；所有成功率必须与样本数、独立 seed 数、重复数一起读。

## 3. 结论强度（P1-6）

| 字段 | 取值 | 含义 |
|---|---|---|
| `evidence_level` | `INSUFFICIENT` | 证据形式是否满足门槛 |
| `mechanism_exposure` | `NO_TREATMENT_EXPOSURE` | 干预是否真的发生 |
| `effect_direction` | `NOT_MEASURABLE` | 描述性方向，不是因果 |

禁止的读法：

- 不得写成「已证实」
- 不得写成「策略无效」（干预从未发生）
- 不得写成「有效」或「显著提升」
- `SUPPORTED` 不等于显著改善，也不等于因果证实

理由：
- V14 未获真实模型试验批准：没有 LIVE 样本。
- 历史 V12 CSV 缺 mechanism_triggered 字段，机制暴露未知。

> 三个字段独立：证据形式（能不能算）、干预暴露（有没有发生）、效果方向（描述性差异）。任一为否定时都不能给出「策略有效」的结论。
