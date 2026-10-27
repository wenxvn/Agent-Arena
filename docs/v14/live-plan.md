# V14 LIVE 方案 A 预注册（`PLANNED_ONLY`）

> **本文件不构成执行授权。** V14 新增真实付费请求：**0**。
> V12 的 ¥6 授权已结束，剩余额度不延续；本方案需要用户对「模型 / 矩阵 / 总费用上限」逐项批准。

## 1. 矩阵（54 局）

| 组 | 地图 | 臂 | 单臂子局 | 组子局 | 被操纵变量 | 单开关 |
|---|---|---|---:|---:|---|---|
| E1-a | MAP-22 | E1-a-control / E1-a-treatment | 9 | 18 | `route_log` | 是 |
| E2-a | MAP-16 | E2-a-control / E2-a-treatment | 9 | 18 | `enabled` | 是 |
| E3 | MAP-22 | E3-control / E3-treatment | 9 | 18 | `enabled` | 是 |
| **合计** | | | | **54** | | 配置层单开关 |

seed：0 / 1 / 2（每组），重复：3 次独立观测。

> **E3 的读法**：`disabled → reflection_on` 只差 `enabled` 一个配置键，但它同时开启「触发判定 + 反思请求 + 建议注入」，所以是**机制级组合对照**；要回答「反思请求本身有没有用」，需改跑 `trigger_only → reflection_on`（同样 18 局）。

seed 白名单校验：全部合法。

## 2. 费用

| 组 | 子局 | V12 实测均价 CNY/局 | 预估 CNY（×1.5） | 上界 CNY |
|---|---:|---:|---:|---:|
| E1-a | 18 | 0.03344638 | 0.9 | 9.0 |
| E2-a | 18 | 0.01153262 | 0.31 | 9.0 |
| E3 | 18 | 0.03344638 | 0.9 | 9.0 |
| **合计** | **54** | — | **2.11** | **27.0** |

- 建议批准上限：**¥5.0**（高于预估，低于上界）。
- 预估 = 子局数 × V12 实测均价 × 1.5；上界 = 子局数 × 单局硬上限。上界远高于预估是 fail-closed 护栏，不是期望花费。

## 3. 单局硬上限

| 项 | 值 |
|---|---|
| `per_run_request_cap` | 90 |
| `per_run_decision_cap` | 90 |
| `per_run_input_token_cap` | 200000 |
| `per_run_cost_cap_cny` | 0.50 |

## 4. 停止条件

1. 任一局 unknown_spend → 立即停止整个批次并封账，不自动重试
2. 累计结算达批准上限的 90% → 停止未开始的子局
3. Provider 连续 3 次错误 → 停止
4. 发现契约/接口缺陷 → 停止，先写 DCR，修复后用新版本实验，不污染原计划
5. 实际平均单局费用超过预估 2 倍 → 停止并重新申请
6. reflection_on 臂全部 0 触发 → 停止并记 NO_TREATMENT_EXPOSURE（改阈值须另立版本）

## 5. 子计划状态

| 子计划 | 子局 | 状态 | 真实收益 |
|---|---:|---|---|
| memory | 36 | `PLANNED_ONLY` | `LIVE_PENDING` |
| planning | 72 | `PLANNED_ONLY` | `LIVE_PENDING` |
| reflection | 27 | `PLANNED_ONLY` | `LIVE_PENDING` |

## 6. 批准要求

- 需用户明确批准：模型名、实验矩阵、总费用上限、每局请求/token/费用阈值、未知 usage 处理与停止条件。未获批不得提交任何 LIVE 请求。
- V12 的 ¥6 历史授权已结束，剩余额度不延续；V14 不沿用旧 LiveApproval。

## 7. 零请求预检命令

```bash
# 只构造规格并打印，不提交（默认即预检模式）
uv run python scripts/plan_v14_live.py --check

# 单因子消融的 V13 预检入口（同样默认不提交）
uv run python scripts/run_v12_matrix.py --ablation memory.route_log \
    --maps MAP-22 --seeds 0 1 2 --replicates 3 \
    --provider simulated_scripted --decisions 90 --requests 90
```

> V14 的三组臂使用**钉住配置**（例如 E1-a 固定 `route_mode=context_only`），与 V13 模板的默认值不同；因此正式提交时必须用 V14 规格，不能直接复用 V13 模板。
