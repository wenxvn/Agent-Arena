# V13 实验协议（预注册）

- **状态**：协议与口径已冻结；**本轮不包含任何新付费 LIVE 运行**
- **契约版本**：`v13-lab-1`（在 `v12-lab-1` 上**只增字段**，旧文件按默认值读取）
- **登记日期**：2026-10-26
- **对应代码**：`src/agent_arena/lab/contracts.py`（`ExperimentSpec` / `SamplingProvenance` /
  `ProtocolManifest`）、`lab/experiment.py`（`preflight`、`create_replicates`）、
  `lab/v13/comparability.py`（可比性判定）

> **先冻结口径，再改策略。** 本文件的目的是让"改了什么、和谁比、能说什么"在跑之前
> 就写清楚；任何事后调整都要记进 `docs/v13/decisions.md` 并说明原因。

## 1. 研究问题（V13）

1. 同一配置多次运行，结局波动到底有多大？统计单位与版本口径是否正确？
2. Memory / Planning / Reflection 中，**哪个机制真的被激活**，给哪些地图带来改善或额外成本？
3. 在 MAP-16、18、22、30 上，失败是能力问题、接口问题还是预算/测量问题？
4. 对哪些地图，现有指标能区分能力？哪些存在天花板、地板或构念证据不足？
5. 使用者能否从网页一键完成合规配置、离线自检、可审计的比较与报告？

**不包含**：跨模型排行榜、地图难度总评、显著性检验、任何"架构更优"的总体断言。

## 2. 条件身份（provenance）

每一局必须能回答"它和谁可比"。身份字段分三类：

| 类 | 字段 | 作用 |
|---|---|---|
| 条件 | `map_id`、`environment_seed`、`replicate_index`、`agent_id`、`agent_config_hash` | 唯一确定一个子局 |
| 口径 | `mode`、`provider_id`、`model`、`action_contract_version`、`base_prompt_hash`、`history_window`、`rule_hash`、`metric_hash`、`metric_schema_hash` | 决定"能不能比" |
| 预算 | `max_decisions`、`max_requests`、`max_input_tokens`、`max_output_tokens`、`max_cost` | 决定"比的是不是同一件事" |

**条件键**：

```text
condition_key = map_id|seed=<n>|agent_id              # replicate_index = 0（与 V12 逐字一致）
condition_key = map_id|seed=<n>|agent_id|rep=<n>      # replicate_index > 0
pairing_key   = map_id|seed=<n>                       # 配对与统计以 seed 为块
```

- `replicate_index = 0` 保持 V12 键不变，历史脚本与历史文件不受影响；
- 重复编号参与幂等键：同一重复重新提交仍幂等，换重复编号真正新建 run；
- **配对键忽略重复编号**：重复是"同一块的多次观测"，不是新样本。

## 3. 环境 seed ≠ 模型 seed

- 固定环境 seed 只保证**环境初态**一致；
- 模型采样参数（temperature / top_p / seed）写入 `SamplingProvenance`，默认 `support=UNKNOWN`；
- 服务端未确认支持时，对外口径只能是 `UNKNOWN` 或 `UNSUPPORTED`；
- **即使服务端接受 seed，输出也不保证可复现**（`SEED_ACCEPTED_BUT_OUTPUT_NOT_GUARANTEED`）；
- 任何文档、UI、报告都不得写"deterministic"。

## 4. 可比性判定（三层）

```text
硬不匹配（地图/规则/指标 schema/模型/Provider/模式/契约/共享提示/预算/历史窗口）
        → INCOMPARABLE：不给差值，不给排名，只并列展示
只有版本或登记缺失
        → DESCRIPTIVE_ONLY：给差值但明确标注
只有被测干预不同
        → COMPARABLE
```

**被测干预**（允许不同，且不构成不可比）：`agent_config_hash`、注入的记忆/计划/反思文本、
额外 Planner/Reflection 请求。要求它们"prompt_hash 相同"等于禁止实验，因此不要求。

**单变量检查**（`single_switch_check`）：

| 情形 | 判定 |
|---|---|
| 同 `agent_id` + 恰好一个配置键不同 | 单因子消融（可比，可归因） |
| 同 `agent_id` + 多个配置键不同 | **拒绝**（只能作为"组合方案"描述） |
| 不同 `agent_id` | 版本/架构比较（不是消融） |

## 5. 重复与稳定性口径

- 分组键 `(map_id, environment_seed, agent_id)`；一次观测 = 一次独立重采样；
- 只有同 `agent_config_hash`、同 `agent_version`、同单局预算、同 `prompt_hash`（若有）
  的观测计入翻转率；其余标 `跨版本` / `跨预算` / `跨模型` / `跨模式` 并**排除**；
- 翻转 = 同一分组内 `category` 出现两种及以上取值；
- 观测 < 3 一律 `DESCRIPTIVE_ONLY`；
- Wilson 区间只作描述，前提（组间共享模型与提示）必须写进报告。

**禁止**：把 3 次重采样写成 "N=3 个地图实例"；用重复次数增加来暗示泛化能力。

## 6. 统计口径（分母显式）

| 口径 | 定义 |
|---|---|
| `all_attempted` | 所有已执行的子局 |
| `evaluable` | 完成且成功 + 机制失败 + 预算截尾 |
| `uncensored_finished` | 完成且成功 + 机制失败 |
| `censored` / `censored_ratio` | 预算截尾数与占比 |
| `invalid` | Provider 错误、取消、中断、策略异常、未执行 |

- Provider 错误、取消、中断、策略异常**不计入能力分母**；
- 缺失/不适用/不可用**不补零**；
- 成本有未知项时，聚合显示 `UNKNOWN`，未知局不并入已结算金额。

## 7. 结论等级

| 等级 | 条件 |
|---|---|
| `SUPPORTED` | 有效分母 ≥ 3、截尾比例 < 30%、配对 `COMPARABLE`、有可复核证据锚 |
| `TENTATIVE` | 上述任一项不足（例如单次观测、`DESCRIPTIVE_ONLY`） |
| `INSUFFICIENT` | 截尾比例 ≥ 30%、全部不可比、或关键机制未触发 |
| `NOT_TESTED` | 没有可评估子局 |

等级只看**证据结构**，不看成功率高低；负面结果与正面结果同级保留。

## 8. 三层实验门禁

| 门禁 | 内容 | 本轮状态 |
|---|---|---|
| Gate A · 离线单测 | 协议解析、模拟策略、消融开关、预算触发、旧结果读取、重算、泄漏扫描 | **通过**（见 `validation-report.md`） |
| Gate B · 历史/模拟复演 | V12 159 局只读再分析 + SIMULATED 完整父子实验链 | **通过**（`verify_v13.py` 18 项） |
| Gate C · LIVE | 需用户**本次 V13** 单独授权的模型、矩阵与总费用上限 | **WAITING_USER_APPROVAL** |

## 9. 预注册实验矩阵（全部 `PLANNED_ONLY`）

| 组 | 目标 | 建议范围 | 最小重复 | 状态 |
|---|---|---|---|---|
| E0 | 采样复现与历史可比性 | MAP-16/18 × Basic/Memory/Planning | ≥3 | `PLANNED_ONLY` |
| E1 | Memory `route_log` | MAP-22 × route_log on/off | ≥3 | `PLANNED_ONLY` |
| E2 | Planning 效益与成本 | MAP-16/18 × on/off、replan off、低频 | ≥3 | `PLANNED_ONLY` |
| E3 | Reflection 激活后收益 | 优先 MAP-22 长失败局 | ≥3 | `PLANNED_ONLY`（需先证明 trigger>0） |
| E4 | MAP-30 机制与预算 | 180 请求 / 600k token / ¥0.25 三档 | ≥3 | `PLANNED_ONLY` |
| E5 | 独立验证 | `seed_space` 内未参与调参的 seed | ≥3 | `PLANNED_ONLY`（无 holdout 则标探索性） |

**执行成本策略**：先 `preflight`（零请求）→ `docs/v13/live-budget-proposal.md` →
用户批准 → 才可 `--submit`。V12 的 ¥0.56 剩余额度**不**自动继承。

## 10. 停止规则（任何 LIVE 运行都必须先写进协议）

1. 单局请求/token/费用任一触顶 → 该局 `BUDGET_REACHED`，不重试；
2. 未知消费（`unknown_spend`）→ 立即停止整个实验并封账，不自动重试；
3. 实验级请求/费用上限触顶 → 停止未开始的子局，状态 `PARTIAL`；
4. 墙钟上限触顶 → 停止并保留已完成的子局；
5. Provider 连续错误 → 停止，不重试；
6. 观测到契约/接口缺陷 → 停止，先写 DCR，修好后另立实验（不与旧版本配对）。

## 11. 数据不可混合规则

- V12 历史 `DCR-V12-01/02/06` 前后的契约与默认配置不同，必须先按
  `comparable_group_id`（只含"必须一致"的维度）分组；
- 只有真正同条件的观测才进入重复分析；
- 跨版本一律 `INCOMPARABLE`，报告写"跨版本不配对"；
- 历史 CSV 是只读来源，任何再分析都不改写它。

## 12. 复现命令

```bash
uv run python scripts/verify_v13.py            # 18 项离线验收（零请求）
uv run python scripts/demo_v13.py              # 零 Key 演示（SIMULATED）
uv run python scripts/summarize_v13_repeats.py --history --write
uv run python scripts/audit_v13_maps.py --write
uv run python scripts/audit_v13_ledger.py --write
uv run python scripts/stress_v13_history.py --write

# 单因子消融（只预检；加 --submit 才会入队）
uv run python scripts/run_v12_matrix.py --ablation memory.route_log \
    --maps MAP-22 --seeds 0 --replicates 3

# 实验内 N 次独立重复（只创建；加 --submit 才会入队）
uv run python scripts/run_v12_matrix.py --repeats-of <experiment_id> \
    --replicates 3 --conditions "MAP-22|seed=0|memory.v2"
```
