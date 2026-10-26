# Reflection 策略研究（P1-1）

- 数据来源：`SIMULATED`（V13 真触发探针）+ `HISTORICAL`（V12 未激活证据）
- 本轮新增真实付费请求：**0**
- 结论强度：**触发机制 `SUPPORTED`；真实收益 `WAITING_USER_APPROVAL`**

## 1. 复盘 DCR-V12-05

| 事实 | 数值 |
|---|---|
| 实验 | `reflection.v1` on/off，MAP-16，seed 0/1，各 1 局 |
| 两臂结局 | **完全一致**（seed 0 `DEADLOCK`、seed 1 `GATE_OPENED`） |
| `reflection_triggered` | 两臂均为 **0** |
| 根因 | MAP-16 失败太快（第 6 步终止），没有任何公开信号累积到阈值 |

**结论**：这不是"反思无效"，而是**反思从未被叫醒**。V12 的对照因此无效，
V13 必须把"是否真的触发"变成可测量的一等公民。

## 2. 触发器（全部是公开规则，不由 LLM 自判）

| 触发器 | 规则 | 备注 |
|---|---|---|
| `repeated_rejection` | 连续 `reject_threshold`（默认 2）次动作被拒/非法 | 若同时是重复动作，优先报这个（更具体） |
| `repeated_action` | 同一动作连续出现 3 次 | |
| `no_progress` | 公开进度指纹连续 `stall_threshold`（默认 3）次未变 | |
| `budget_drain` | 同一动作重复且 tick 在推进 | 标记为**潜在误触发** |

`budget_drain` 被单独标记为 `false_trigger`，因为它可能只是正常的周期性动作
（例如每回合都要 `wait`）。

## 3. 暴露与效果必须分开

| 计数 | 含义 | 为什么必须分开 |
|---|---|---|
| `eligible` | 触发条件成立、冷却已过、额度未用尽 | 这才是"可以反思"的次数 |
| `triggered` | 真的发出了反思请求 | 与 `eligible` 的差 = 被冷却/额度挡下 |
| `blocked_cooldown` | 被冷却挡下 | 说明冷却是否过紧 |
| `blocked_quota` | 被上限挡下 | 说明上限是否过低 |
| `false_triggers` | 触发了但当时进度在推进 | 误触发率 |
| `recoveries` | 触发后 `recovery_window` 步内公开进度发生变化 | 唯一的"效果"代理指标 |

`triggered == 0` → `exposure = NO_TREATMENT_EXPOSURE`：
**不是"反思无效"，而是"本轮没有暴露"**。

## 4. SIMULATED 真触发证据（Gate 6）

`scripts/demo_v13.py` 生成 `runs/v13/demo/reflection-trigger-probe.json`：

```json
{
  "schema": "v13-reflection-probe-1",
  "mode": "simulated",
  "state": "BUDGET_REACHED",
  "triggered": 2,
  "eligible": 2,
  "exposure": "TREATMENT_TRIGGERED",
  "events": [{"kind": "reflection", "agent_event": "reflection_triggered", ...}]
}
```

同时 `test_reflection_v2_triggers_in_real_simulated_episode` 验证：

1. 事件真的写入 `agent_events`（`reflection_triggered`）；
2. 反思建议真的进入后续决策的 `runtime_feedback`（"反思建议"出现在请求里）；
3. 该局 `triggered >= 1` 且 `exposure == TREATMENT_TRIGGERED`。

**探针不是 Oracle**：它用固定脚本动作（连续做同一件事）制造重复动作触发，
不代表真实模型会触发。

## 5. 冷却与上限

| 配置 | 默认 | 作用 | 证据 |
|---|---|---|---|
| `cooldown_steps` | 4 | 两次反思之间至少隔几步 | `test_reflection_v2_cooldown_blocks_and_is_counted` |
| `max_reflections` | 3 | 每局上限 | `test_reflection_v2_quota_blocks_and_is_counted` |
| `recovery_window` | 3 | 触发后多少步内算"恢复" | `test_reflection_v2_recovery_is_measured_from_public_progress` |

**额外请求全部计入同一账本**：`context.gateway.ask_json(purpose="reflection")`
走同一个 `RunBudget`，`usage.purposes["reflection"]` 可核对。

## 6. trigger-only 对照（防"判断触发"偷偷注入提示）

`trigger_only=True` 时：

- 仍然判定触发、仍然计入 `triggered`；
- **不请求模型、不注入建议**（`reflection_event.requests == 0`）；
- 事件名 `reflection_trigger_only`。

因此"trigger-only vs disabled"测的是"触发判定本身是否改变了行为"；
"on vs trigger-only"测的才是"反思内容是否起作用"。

## 7. 零触发时必须怎么写

| 情形 | 正确写法 | 错误写法 |
|---|---|---|
| `triggered = 0` | "本轮 `NO_TREATMENT_EXPOSURE`：触发器未命中，无法回答反思是否有效" | "反思无效" |
| `triggered > 0`，成功率不变 | "反思被触发 N 次，未观察到成功率差异（样本不足）" | "反思没用" |
| `triggered > 0`，成功率上升 | "描述性：反思触发后成功率 X→Y，样本 N，翻转率 Z" | "反思提升能力 X%" |

## 8. 为什么优先选 MAP-22 做 LIVE

| 地图 | 决策数中位数（V12 真实） | 失败前缀长度 | 是否可能触发 |
|---|---|---|---|
| MAP-16 | 6–14 | 短（第 6 步就 `DEADLOCK`） | 基本不会 |
| MAP-18 | 12–30 | 中 | 偶尔 |
| MAP-22 | 40–60 | **长**（迷路 + 被拒移动） | **会** |
| MAP-30 | 90–170 | 很长 | 会，但撞预算 |

MAP-22 的"被拒移动 + 重复方位"正好命中 `repeated_rejection` / `repeated_action`。

## 9. 下一轮 LIVE 小矩阵（PLANNED_ONLY）

| 组 | 地图 | seed | 对照 | 重复 | 预估 |
|---|---|---|---|---|---|
| E3-a | MAP-22 | 0,1,2 | `reflection.v2` off vs on | ≥3 | 18 局 |
| E3-b | MAP-22 | 0,1,2 | on vs trigger-only | ≥3 | 18 局 |

36 局，单局上界 90 请求 / 200k token / ¥0.50 → 上界 ¥18，预计 ¥1.5–3。
**前置条件**：Pilot 里必须至少出现 1 次 `triggered > 0`，否则结论仍是
`NO_TREATMENT_EXPOSURE`。

## 10. 不支持的主张

- ❌ "Reflection 提升能力"——本轮没有任何真实模型的 on/off 有效对照；
- ❌ "反思能救回长失败局"——SIMULATED 探针只证明触发链路可用；
- ❌ "V12 已证明反思无效"——DCR-V12-05 已明确那是未暴露，不是无效。
