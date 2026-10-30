# V14 实验协议（可比性、重复、门禁、批准边界）

- 版本：`v14-protocol-1`（2026-10-27）；2026-10-29 V14.1 补写 §6.1 的“历史登记 vs 当前状态”区分（规则未改）
- 适用：V14 之后的所有分析层与实验层；不回溯修改 V12/V13 已发布数字
- 真实付费请求（本文件登记时）：**0**（本文件不构成执行授权；实际执行见 §6.1）

## 1. 观测条件身份（8 元组）

一次观测的**条件身份**由以下 8 个字段决定，顺序固定：

```text
(map_id, environment_seed, agent_id, config_hash,
 contract_version, effective_prompt_version, budget_profile, sampling_profile)
```

实现：`agent_arena.lab.v14.conditions.observation_condition()`，`condition_id` 是这 8 个
值的 canonical SHA-256 前 16 位。

三条硬规定：

1. **`replicate_index` 不属于身份**。同一条件的第 0/1/2 次观测共享同一个
   `condition_id`；它只是观测序号，**不是**新的环境 seed，也不是新样本。
2. **`config_hash` 参与身份**。因此同一策略的 on/off 两臂天然是不同条件，
   可以直接配对（不会像 V12 的 `condition_key` 那样因缺 config hash 而丢配对）。
3. **未登记字段写 `UNKNOWN`，不写默认值**。历史 CSV 没有 `contract_version`、
   `prompt_hash`、`sampling`，于是这三项为 `UNKNOWN`，并进入
   `unrecorded_fields`（见 DCR-V14-01）。

派生画像：

| 画像 | 字段 | 未登记时 |
|---|---|---|
| `budget_profile` | `request_cap` / `input_token_cap` / `decision_cap` / `cost_cap_cny` | 各项为 `None`，指纹里写 `UNKNOWN`，`recorded=False` |
| `sampling_profile` | `temperature` / `top_p` / `seed_requested` / `support` | `support=UNKNOWN`，`deterministic_claim=UNKNOWN` |

采样画像永远不返回 "deterministic"：即使服务端确认接受 seed，也只写
`SEED_ACCEPTED_BUT_OUTPUT_NOT_GUARANTEED`。环境 seed 固定只保证环境初态一致。

## 2. 环境 seed 白名单

- 合法 seed 只能来自 `agent_arena.v10.runtime.catalog.seed_space(map_id)`；
- `validate_seed()` 对越界 seed 返回 `valid=False` 并给出允许列表；
- `seed_coverage()` 分别统计 `independent_seed_count`（真样本）与
  `max_replicates`（同条件重采样），并在输出里显式写
  `replicates_are_not_seeds = True`；
- 任何"3 次重复 = 3 个 seed"的说法都是错的，报告层必须分开写。

## 3. 可比性判定（三档，禁止合并）

| 判定 | 触发条件 | 允许的结论 |
|---|---|---|
| `COMPARABLE` | 8 维全部一致（或被测干预之外的软维度也一致） | 可做配对方向统计 |
| `DESCRIPTIVE_ONLY` | 只有软不匹配（版本/采样/预算**未登记**、策略不同） | 只能并列展示，不得宣称因果或显著 |
| `INCOMPARABLE` | 任一硬不匹配（地图/seed/模式/模型/Provider/规则/指标/契约/提示/预算/采样**已登记且不同**） | 只保留在数据里，排除出效果统计 |

硬不匹配原因代码：`MAP` / `SEED` / `MODE` / `MODEL` / `PROVIDER` / `RULE` /
`METRIC` / `CONTRACT` / `PROMPT` / `BUDGET` / `SAMPLING`。

**关键区分**：`UNKNOWN`（未登记）**不等于**不一致。未登记只能降级为描述性，
不能升级为"不可比"，否则会把所有历史数据判死；反过来也不能当成"一致"，
否则会伪造可比性。

## 4. 配对结果必须同时报告

`summarize_pairing()` 的固定字段：

| 类别 | 字段 |
|---|---|
| 局数 | `pairs` / `left_completed_runs` / `left_valid_runs` / `right_valid_runs` |
| 结局 | `left_successes` / `right_successes` / `left_censored` / `right_censored` / `left_mechanism_failures` / `right_mechanism_failures` |
| 可比性 | `comparable_pairs` / `descriptive_pairs` / `incomparable_pairs` |
| 方向（仅可比对） | `right_only` / `left_only` / `both_success` / `neither` / `paired_difference` |
| 资源（可比与描述性对） | `requests_delta_mean` / `input_tokens_delta_mean` / `cost_cny_delta_mean` / `cost_cny_delta_total` / `resource_delta_pairs` |

两条口径：

1. **方向统计只取 `COMPARABLE`**。描述性对可以展示资源差值（这是事实测量），
   但不能进方向统计。
2. **缺失不补零**。一侧缺 `cost_cny` 时差值为 `None`，不是 0。

## 5. 区间与"显著"的门槛

`descriptive_only_preconditions()` 会在下列情况强制标 `DESCRIPTIVE_ONLY`：

- 可比对 < 3；
- 存在描述性对（版本/采样/预算未登记）；
- 存在不可比对；
- 独立环境 seed < 3。

区间的前提必须写明：**抽样单位是环境 seed**；区间只覆盖已观测 seed；
重复次数只反映模型采样波动，不扩大 seed 覆盖。

`SUPPORTED`（V13 四级结论）只描述**证据形式**，不代表策略有效、显著改善或因果证实。
V14 报告层把结论拆成三个独立字段（见 `failure-and-capability.md`）：
`evidence_level` / `mechanism_exposure` / `effect_direction`。

## 6. 批准边界（LIVE）

```text
默认模式            = PLANNED_ONLY（preflight，零请求）
执行前置            = LiveApproval(approved=True, max_cost_cny=<上限>, note=<模型+矩阵+停止条件>)
per_run_request_cap ≤ 90（MAP-30 允许 180）
per_run_input_token_cap ≤ 200k（MAP-30 允许 600k）
执行方式            = 单 worker 串行（禁止并发付费）
unknown_spend_policy = stop（未知消费立即封账，不重试）
```

停止条件（必须写进 `LiveApproval.note`）：

1. 任一局 `unknown_spend` → 立即停止并封账；
2. 累计结算达批准上限 90% → 停止未开始的子局；
3. Provider 连续 3 次错误 → 停止；
4. 发现契约/接口缺陷 → 停止，先写 DCR；
5. 实际平均单局费用超过预估 2 倍 → 停止并重新申请。

**（历史登记，已不再描述当前状态）** 本协议首次写下时 V14 尚未获得任何批准，
因此当时 `docs/v14/` 中所有真实模型效果都标 `LIVE_PENDING`。该表述保留作为
**预注册历史**，不得据此判断现在是否已执行。

### 6.1 当前状态（2026-10-29，V14.1）

| 项 | 登记时（2026-10-27） | 当前（已执行并封账） |
|---|---|---|
| 批准 | 无（`PLANNED_ONLY`） | 用户逐轮授权 MiMo `flash` + `pro`，方案 A + 九轮补充 |
| 真实付费局 | 0 | **308 局 / 10 034 请求 / ¥5.55809328**（4 局 `unknown_spend` 各自停批、未重试） |
| 文档状态字段 | `LIVE_PENDING` | 已改为实际结果（见 `live-report.md`、`live-results.md`） |
| 外部账单 | 未提供 | 仍未提供 → `BLOCKED_EXTERNAL` |
| 采样支持 | `UNKNOWN` | 仍未登记 → 所有配对仍为 `DESCRIPTIVE_ONLY` |

历史预注册文件（`live-plan.md`、`agent-studies.md`）中的 `PLANNED_ONLY` / `LIVE_PENDING`
一律按“当时的登记值”阅读，不代当前状态；当前状态以 `live-results.json` 为准。
本协议本身仍然有效：任何**新增**付费请求都需重新 `LiveApproval`，本轮 V14.1 为零请求。

## 7. 可复算入口

```bash
uv run python scripts/audit_v14_data.py --write
```

输出 `docs/v14/{data-validity.md,pairing-audit.md,budget-audit.md,validity-diff.md}`
与机读版 `data-validity.json`；全部来自只读历史 CSV。
