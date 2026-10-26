# Memory 策略研究（P0-2）

- 数据来源：`HISTORICAL`（V12 真实 159 局中的 memory 相关局）+ `SIMULATED`（V13 机制验证）
- 本轮新增真实付费请求：**0**
- 结论强度：机制层面 `SUPPORTED`（可复现的确定性证据）；真实模型收益 `WAITING_USER_APPROVAL`

## 1. 审计：`memory.v1` 到底做了什么

| 维度 | v1 实现 | 观察 |
|---|---|---|
| 写入条件 | 每步把公开观察字段写进 `state.*`；动作结果写进 `result.*`；里程碑写进 `milestone.*` | 写得很多，但**没有"按步路线"** |
| 容量 | `capacity=24`（LRU 淘汰） | 长局会被历史事实挤掉 |
| 渲染长度 | `max_chars=1200` | 约 20–30 条事实；再长就截断 |
| 额外请求 | 0 | 与 `basic.v1` 请求数相同 |
| 路线 | `route_log=False`（默认关） | V12 后期才加，且只写 `path_state` |

**结论**：v1 的瓶颈不是"没有记忆通道"，而是**没有按步记录可复用的状态**。
这正是 DCR-V12-03 的结论（模型只写 1–4 个方位，真实路线 22–44 步）。

## 2. `memory.v2` 的版本化配置

| 配置 | 默认 | 作用 |
|---|---|---|
| `enabled` | True | 消融开关 |
| `capacity` | 32 | 比 v1 大，因为路线与统计要共存 |
| `max_chars` | 1600 | 渲染上限 |
| `route_log` | **True**（v1 默认 False） | 按步记录被接受的移动 |
| `route_mode` | `env_write` | `env_write`（占决策）/ `context_only`（0 动作） |
| `route_write_every` | 2 | 每 2 步写一次 |
| `route_write_limit` | 24 | 写入次数上限（防预算被吃光） |
| `compress` | True | 长结构压成摘要 |
| `dedupe` | True | 同 key 覆盖而非追加 |
| `relevance` | True | 渲染时路线/里程碑优先 |

**默认行为与 v1 不同**，所以必须是新 `agent_id`（`memory.v2` / `2.0.0`），
不能改 v1 的默认值（否则 159 局历史的 `agent_config_hash` 全部失效，DCR-V12-06）。

## 3. 路线只从**被接受**的公开移动累积

离线证据（`tests/test_v13_policies.py::test_memory_v2_route_only_accumulates_accepted_moves`）：

```text
move north           → MOVED                  → 路线 = [north]
move north           → BEARING_NOT_AVAILABLE  → 路线不变（rejected_moves=1）
move east            → MOVED                  → 路线 = [north, east]
move（缺 bearing）    → <invalid>              → 路线不变（invalid_moves=1）
```

同时记录 `loops`（重复方位）与 `backtracks`（立即反向），两者都是**策略侧**证据，
不是环境事实。

## 4. 写入机制必须显式区分（不能互相冒充）

| 机制 | 动作 | 决策消耗 | 环境记忆 | 诊断标签 |
|---|---|---|---|---|
| `env_write` | `write_memory(facts=[{key:path_state,...}])` | **占 1 次决策** | 写入 `agent_notes` | `write_accepted` / `write_rejected` |
| `context_only` | 无动作 | 0 | 不写 | `render_count` / `block_chars` |

离线证据：
- `test_memory_v2_env_write_consumes_a_decision_and_is_accounted`：`write_attempts=1`、
  `write_accepted=1`、该步 `requests=0`；
- `test_memory_v2_context_only_never_issues_write_action`：`write_attempts=0`，
  但 `memory_data` 里确实有路线。

**为什么重要**：`env_write` 会吃掉决策预算（长局可能因此少走几步），
这正是"记忆的代价"，必须能被看到。

## 5. 三类记忆瓶颈（结构化诊断）

| 标签 | 判据 | 归属层 |
|---|---|---|
| `NO_RECORD` | 没有路线、也没有写入尝试 | 策略（没记录） |
| `WRITE_REJECTED_INTERFACE` | 有写入尝试但全部被拒 | **接口**（`INVALID_MEMORY_PAYLOAD`） |
| `RECORDED_TOO_SHORT` | 已写入的方位 < max(3, 路线长度/2) | 策略（记录太短） |
| `RECORDED_NOT_REFERENCED` | 有路线但从未渲染进 prompt | 策略（记录了没用） |
| `RECORDED_AND_RENDERED` | 记录且渲染 | 正常 |

这五类直接对应"没有记录 / 记录错误或过短 / 有记录但未被决策引用"三种瓶颈，
且接口层与策略层不会混算。

## 6. 口径正确性（离线可控轨迹）

| 指标 | 定义 | 验证方式 |
|---|---|---|
| `route_recall`（V12 投影） | 写入序列与真实被接受 move 序列逐位匹配 / 真实路线长度 | 键名宽容（`bearing`/`path_state`/含方位值的键）；`NOT_APPLICABLE` 当无路线或无写入 |
| `wasted_moves` | 被拒 move 数（不改变位置） | 与 `rejected_moves` 对齐；被拒移动**不计入**探索边 |
| 请求/动作消耗 | `usage.requests` + `decision_count` | `env_write` 模式下写入步 `requests=0` 但 `decision_count+1` |

## 7. 旧证据（V12 真实结果，只读）

| 条件 | 结果 | 说明 |
|---|---|---|
| MAP-22 主矩阵 `memory.v1` | 0/3 | 当时 `route_recall` 读不到（DCR-V12-02），且契约有缺陷（DCR-V12-01） |
| MAP-22 `contract-2` | 0/9 | 键名修好后 `route_recall` 变成 VALID，但值 0.0–0.045 |
| MAP-22 `route_log`（3 局） | 1/3 成功；`route_recall` 0.45 / 0.75 / 1.0 | `wasted_moves` 34 → 8（seed 2） |
| MAP-18 `memory.v1` | 2/5（含 seed 3/4） | 唯一有正向梯度的记忆条件 |

**读法**：`route_log` 的机制成立（`route_recall` 从 0 拉到 0.45–1.0），但只有 3 局、
且与主矩阵跨配置不配对。因此只能说"机制已验证，收益样本不足"。

## 8. 成本权衡（需要下一轮 LIVE 才能量化）

| 机制 | 请求 | 决策 | token | 风险 |
|---|---|---|---|---|
| `route_log=False` | 不变 | 不变 | 不变 | 无路线可用 |
| `route_log=True` + `context_only` | 不变 | 不变 | 每步 +路线文本（≤1600 字符上限） | 上下文变长 → 输入 token 上升 |
| `route_log=True` + `env_write` | 不变 | **+1 次/写入** | 写入步无模型请求 | 决策预算被占，长局可能截尾 |

## 9. 下一轮 LIVE 待批准矩阵（PLANNED_ONLY）

| 组 | 地图 | seed | 对照 | 重复 | 预估单局上限 |
|---|---|---|---|---|---|
| E1-a | MAP-22 | 0,1,2 | `route_log` off vs on（`context_only`） | ≥3 | 90 请求 / 200k token / ¥0.50 |
| E1-b | MAP-22 | 0,1,2 | `route_log` on（`context_only` vs `env_write`） | ≥3 | 90 请求 / 200k token / ¥0.50 |
| E1-c | MAP-18 | 0,1,2 | `memory.v1` vs `memory.v2`（**版本比较**） | ≥3 | 90 请求 / 200k token / ¥0.50 |

预计 27 局 × 3 组 = 最多 81 局；费用上界按 ¥0.50/局 = ¥40.50，实际预计 ¥2–3。
**未获授权前不执行。**

## 10. 不支持的主张

- ❌ "Memory 让成功率提升 X%"——V12 的 memory 条件只有 2/5，翻转率 22–25%；
- ❌ "route_log 能提高通关率"——3 局、跨配置，只能算机制演示；
- ❌ "记忆容量越大越好"——容量与渲染上限都会抬高输入 token，成本未测。
