# V13 LIVE 预算申请（`WAITING_USER_APPROVAL`）

> **本文件不构成执行授权。** 未获用户对"模型 / 矩阵 / 总费用上限"的明确批准前，
> V13 不会发出任何真实付费请求。V12 的 ¥6 授权已结束，剩余 ¥0.56319988
> **不**自动挪用到 V13。

- 生成日期：2026-10-26
- 计价依据：本机登记的 MiMo 价目表（`v10/ledger.PRICE_SHEETS["CNY"]`）+ V12 实测分布
- 估算来源：`docs/v12/real-runs/*.csv` 138 局的真实请求/token/费用（只读）
- 预检：`uv run python scripts/run_v12_matrix.py --ablation <模板> ...`（零请求）

## 1. V12 实测单价（作为估算基础）

| 地图 | 局数 | 平均费用 CNY/局 | 平均请求/局 | 平均输入 token/局 |
|---|---:|---:|---:|---:|
| MAP-08 | 9 | 0.003030 | 3.9 | 3 039 |
| MAP-16 | 35 | 0.011533 | 15.5 | 18 411 |
| MAP-18 | 37 | 0.011766 | 9.7 | 17 321 |
| MAP-22 | 21 | 0.033446 | 52.0 | 47 121 |
| MAP-26 | 9 | 0.002107 | 3.3 | 2 635 |
| MAP-30 | 27 | **0.129069** | 109.6 | 174 530 |
| 合计 | 138 | 0.036757 | 36.4 | — |

**单局最贵**：MAP-30 的 token 扩展档（180 请求 / 600k token）平均 ¥0.1665/局，
最贵一局 ¥0.1988。

## 2. 每组的上界与预估

上界 = 子局数 × 单局硬上限；预估 = 子局数 × V12 实测均价 × 1.5（留 50% 余量）。

| 组 | 内容 | 地图 / seed | 条件 × 重复 | 子局 | 单局硬上限 | 上界 CNY | 预估 CNY |
|---|---|---|---|---:|---|---:|---:|
| E0-a | 采样复现（三臂） | MAP-16 / 0,1,2 | 3 臂 × 3 | 27 | 90 请求 / 200k tok / ¥0.50 | 13.50 | 0.47 |
| E0-b | 采样复现（三臂） | MAP-18 / 0,1,2 | 3 臂 × 3 | 27 | 同上 | 13.50 | 0.48 |
| E1-a | `route_log` off vs on（context_only） | MAP-22 / 0,1,2 | 2 臂 × 3 | 18 | 90 / 200k / ¥0.50 | 9.00 | 0.90 |
| E1-b | `env_write` vs `context_only` | MAP-22 / 0,1,2 | 2 臂 × 3 | 18 | 90 / 200k / ¥0.50 | 9.00 | 0.90 |
| E2-a | planning on/off | MAP-16 / 0,1,2 | 2 臂 × 3 | 18 | 90 / 200k / ¥0.50 | 9.00 | 0.31 |
| E2-b | 重规划 off | MAP-16 / 1,2 | 2 臂 × 3 | 12 | 90 / 200k / ¥0.50 | 6.00 | 0.21 |
| E2-c | 低频 Planner | MAP-16 / 1,2 | 2 臂 × 3 | 12 | 90 / 200k / ¥0.50 | 6.00 | 0.21 |
| E2-d | planning on/off | MAP-18 / 0,1,2 | 2 臂 × 3 | 18 | 90 / 200k / ¥0.50 | 9.00 | 0.21 |
| E3-a | reflection off vs on | MAP-22 / 0,1,2 | 2 臂 × 3 | 18 | 90 / 200k / ¥0.50 | 9.00 | 0.90 |
| E3-b | on vs trigger-only | MAP-22 / 0,1,2 | 2 臂 × 3 | 18 | 90 / 200k / ¥0.50 | 9.00 | 0.90 |
| E4 | MAP-30 三档预算 | MAP-30 / 0,1,2 | 1 臂 × 3 档 × 3 | 27 | 180 请求 / 600k tok / ¥0.25 | 6.75 | 3.49 |
| E5 | 独立验证（holdout seed） | MAP-16/18 / 3,4 | 2 臂 × 2 | 8 | 90 / 200k / ¥0.50 | 4.00 | 0.10 |

**合计**：**229 局**，上界 **¥103.75**，预估 **¥9.08**。

> 上界与预估差 11 倍，因为"单局硬上限"是 fail-closed 的护栏，不是期望值。
> 若按 V12 的实际触顶率（26/159 ≈ 16% 的局撞上限），真实费用更接近预估。

## 3. 建议的批准方式（三档，任选其一）

| 方案 | 范围 | 子局 | 预估 CNY | 批准上限建议 |
|---|---|---:|---:|---:|
| **A 最小闭环**（推荐） | E1-a + E2-a + E3-a | 54 | 1.68 | **¥5.00** |
| **B 机制全覆盖** | E0 + E1 + E2 + E3 | 150 | 4.19 | **¥8.00** |
| **C 全部（含 MAP-30）** | E0–E5 | 229 | 9.08 | **¥15.00** |

推荐 **方案 A**：先确认三个机制（Memory route_log、Planning on/off、Reflection 真触发）
是否有可测效果；如果翻转率仍 > 20%，再加重复而不是加地图。

## 4. 硬门禁（任何方案都必须满足）

```text
per_run_request_cap   ≤ 90（MAP-30 允许 180）
per_run_input_token_cap ≤ 200k（MAP-30 允许 600k）
per_run_cost_cap_cny  ≤ 0.50（MAP-30 允许 0.25）
experiment_request_cap = 子局数 × per_run_request_cap
experiment_cost_cap_cny = 批准上限（不得高于本节表格）
unknown_spend_policy = stop（未知消费立即封账，不重试）
执行方式 = 单 worker 串行（禁止并发付费）
```

## 5. 停止条件（必须写进 `LiveApproval.note`）

1. 任一局 `unknown_spend` → 立即停止整个批次并封账；
2. 累计结算达批准上限的 90% → 停止未开始的子局；
3. Provider 连续 3 次错误 → 停止；
4. 发现契约/接口缺陷 → 停止，先写 DCR；
5. 实际平均单局费用超过预估 2 倍 → 停止并重新申请。

## 6. 预检命令（零请求，可随时跑）

```bash
# 单因子消融（默认只预检）
uv run python scripts/run_v12_matrix.py --ablation memory.route_log \
    --maps MAP-22 --seeds 0 1 2 --replicates 3 \
    --provider openai_compatible --model mimo-v2.6-flash \
    --decisions 90 --requests 90 --per-run-cost 0.5 \
    --experiment-requests 540 --experiment-cost 3.0 --approval-cap 3.0

# 实验内 N 次重复
uv run python scripts/run_v12_matrix.py --repeats-of <experiment_id> \
    --replicates 3 --conditions "MAP-22|seed=0|memory.v2"
```

## 7. 批准后才会做的事

1. 用 `LiveApproval(approved=True, max_cost_cny=<批准上限>, note=<模型+矩阵+停止条件>)`
   记录批准；
2. 单 worker 串行提交；
3. 每批结束立即 `audit_v13_ledger.py` 对账；
4. 结果写入 `docs/v13/` 并标注 `LIVE`，与 `HISTORICAL` / `SIMULATED` 严格分列。

## 8. 不批准时的状态

- 所有组保持 `PLANNED_ONLY`；
- V13 交付状态为 `LAB_1_1_ENGINEERING_READY`（不是 `LIVE_VALIDATED`）；
- 报告里所有"真实模型效果"一栏写 `WAITING_USER_APPROVAL`，不用模拟数据填充。
