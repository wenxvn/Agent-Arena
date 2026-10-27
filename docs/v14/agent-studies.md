# V14 Agent 机制与 LIVE 状态

- 版本：`v14-agent-studies-1`（2026-10-27）
- 数据来源：`SIMULATED`（离线确定性 probe）+ `HISTORICAL`（V12 只读 CSV）
- V14 新增真实付费请求：**0**
- 三种证据严格分列：`SIMULATED` / `HISTORICAL` / `LIVE`

> 本文件不构成执行授权。所有真实模型效果一律 `LIVE_PENDING`：
> 未获用户对"模型 / 矩阵 / 总费用上限"的明确批准前，不得提交任何 LIVE 请求。

## 1. Memory（P0-4）

### 1.1 离线机制 probe（SIMULATED，零模型请求）

脚本：`north`（接受）→ `north`（被拒）→ `east`（接受）→ 缺 `bearing`（非法）→ `south`（接受）→ `west`（接受）→ 收尾 `wait` 一次以抓取最终记忆块。

| 臂 | 决策 | 请求 | 路线 | 被拒 | 非法 | 写入尝试 | 写入接受 | 渲染 | 瓶颈 |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| `context_only_on` | 7 | 7 | `north,east,south,west` | 1 | 1 | 0 | 0 | 7 | `RECORDED_AND_RENDERED` |
| `context_only_off` | 7 | 7 | `—` | 0 | 0 | 0 | 0 | 7 | `NO_RECORD` |
| `env_write_on` | 8 | 6 | `north,east,south,west` | 1 | 1 | 2 | 2 | 6 | `RECORDED_AND_RENDERED` |
| `disabled` | 7 | 7 | `—` | 0 | 0 | 0 | 0 | 0 | `DISABLED` |

> 瓶颈列是 **V14 投影**（`memory_bottleneck_v14`）：``env_write`` 按「已写入方位数」判定。
> ``memory.v2.bottleneck()`` 原口径把「写入次数」与路线长度比较，一次写入整段路线时会被误判为 `RECORDED_TOO_SHORT`（DCR-V14-03）。

三条 fixture（全部可在 `tests/test_v14_agent_studies.py` 复算）：

1. **被拒/非法移动不进路线**：`route_preview` 恒等于脚本里被接受的方位序列（`route_matches_expected`）；
2. **回到起点仍能引用完整方位**：`context_only` 的最终记忆块与`env_write` 的写入载荷都包含 `north,east,south,west`（`final_block_has_all_bearings`）；
3. **不写答案**：记忆块里没有隐藏真值关键词（`memory_block_leaks` 为空），路线只来自公开 `move` 结果。

### 1.2 写入机制的代价（不可互相冒充）

| 臂 | 决策 | 请求 | 说明 |
|---|---:|---:|---|
| `context_only_on` | 7 | 7 | 不发动作，路线只进 prompt |
| `env_write_on` | 8 | 6 | 每次写入占 1 次决策、0 次请求 |

- `env_write` 写入载荷：`north,east,south,west`；V14 投影 `route_recall = 1.0`（`VALID`）。
- `context_only` 不写环境，V10 官方 `route_recall` 在本臂为 `NOT_APPLICABLE`——必须与 V14 投影分列，不能混算。

### 1.3 单因子审计

| 组 | 对照 | 处理 | 唯一变化键 | 单开关 |
|---|---|---|---|---|
| E1-a | `E1-a-control` | `E1-a-treatment` | `route_log` | 是 |
| E1-b | `E1-b-control` | `E1-b-treatment` | `route_mode` | 是 |

- 全部单因子：是
- 每组只改一个配置键；``route_mode`` 在 E1-a 两组里被钉成 context_only，因此 E1-a 测的是 route_log 本身，不会混入写入机制的差异。

### 1.4 预检登记（`PLANNED_ONLY`，零请求）

| 项 | 值 |
|---|---|
| 地图 | MAP-22 |
| seed | [0, 1, 2] |
| 重复 | 3 |
| 组 | E1-a, E1-b |
| 子局 | 36 |
| 单局预算 | 90 请求 / 200000 token / ¥0.5 |
| 实验费用上限 | ¥5.0 |
| 状态 | `PLANNED_ONLY` / `LIVE_PENDING` |

- 比较口径：同一总预算、同一 memory.v2 版本、同一 prompt 主体、同一 seed；只允许被测开关不同（E1-a 改 route_log，E1-b 改 route_mode）。
- V14 未获用户对模型/矩阵/总额的批准，因此本计划不得执行；``scripts/run_v12_matrix.py --ablation`` 只允许在默认预检模式下运行。


## 4. 汇总状态

| 机制 | 离线机制证据 | 单因子臂 | 预检登记 | 真实收益 |
|---|---|---|---|---|
| Memory（`memory.v2`） | `SUPPORTED`（确定性 probe） | E1-a `route_log` / E1-b `route_mode` | `PLANNED_ONLY` | `LIVE_PENDING` |

## 5. 不支持的主张

- ❌ "Memory 提高成功率 X%"：离线 probe 不含模型，不能给出成功率；
- ❌ "route_log 一定更好"：机制成立 ≠ 收益成立，需要真实配对实验；
- ❌ "`env_write` 比 `context_only` 好"：前者多吃决策预算，长局可能因此截尾；
- ❌ "V10 `route_recall` 为 0 说明没记忆"：`context_only` 不写环境，该口径本就 `NOT_APPLICABLE`。
