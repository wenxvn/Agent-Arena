# MAP-09 定稿：深海连锁故障

| 字段 | 值 |
|---|---|
| 世界 | abyss |
| 难度 | 困难 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `74f17503668585f1d243dcf9a3d83722d8eeb4054db4745696427aa4f8f76ccb` |
| rule_hash | `603948debd2faa2a785e625d14b9a79f5e73676691d5743366c7866652af68d5` |
| prompt_hash | `df9f3ec9eb4d8fc804bafdc4e7d629ac3a8073a3a2cf0e0d4587c1a80d4cb919` |
| metric_schema_hash | `5b66c933d65a5ed2879772f6cd37e8b9234520f5b545cd3d0cab6d26a893acd4` |
| oracle_hash | `89f01678768bb0b19717f0f03113d43673d17ac29005dec37e9b2e2b704ec7d3` |
| commit | `a13ba1e11e267447fbb3c8a4c6b1f5319a313806` |

## 1. 设计意图与独特机制

本图测能否同时控制漏水短路、供氧中断和有限电量，而不是逐个修好三个独立按钮。P-E 水路会把泵房水推向动力舱；泵能保住 P 却消耗刚好够发报的电量；弃置 P 则通过 E-C 应急廊更快恢复供氧和通信。

MAP-09｜深海连锁故障：漏水、电量、供氧与通信四条链的跨系统耦合。

本图与同世界另两图的机制差异：MAP-07 只有单一水路内部的顺序转移，水位直接可见、
动作只改变水量；MAP-08 用主动测试缩小隐藏漏点假设集。本图没有隐藏故障位置，难点
是同一 tick 内的资源循环——E-P 漏水会把泵房水推进动力舱并短路，抽水消耗刚好够
发报的电量，断电只影响供氧线路而不回充电池，供氧稳定计数又决定能否发报。

指标口径（与 docs/v7/maps/MAP-09.md 一致）：
- ``stable_time_ratio`` = 满足 ``water_E<=4 且 oxygen_reserve>0`` 的已结算 tick 数 /
  全部已结算 tick；未行动（0 tick）时分母为 0，即 N/A。
- ``fault_propagation_scale`` = 首个故障后进入不安全/不可达状态的子系统数
  （E 短路、氧耗尽、P 被弃置）。完全没有故障事件时返回 None（N/A）。
- ``hard_threshold_breaches`` = 1[water_E>4] + 1[oxygen_reserve<=0] +
  1[INSUFFICIENT_TRANSMIT_POWER]；每个 episode 每项最多计一次。
- ``repair_dependency_violations`` = 前置条件不足而被拒的修复/开机/补氧/发报尝试数。
- ``repair_actions`` = 成功执行的封舱、抽水、修线、开氧、补氧动作数。

## 2. 与同世界另两图的区别

- **MAP-07**（简单）：本图与同世界另两图的机制差异：MAP-08 用主动测试缩小隐藏漏点的假设集合，MAP-09 是漏水/电量/供氧/通信的跨系统资源耦合；本图没有行走图，Agent 始终在控制台 P 远程操作，因果难度来自“一个 tick 内可变水位按固定次序级联”以及单向回流 v4（C→A）——给 C 降压会把水送回 A，而不是排掉。
- **MAP-08**（中等）：本图测 Agent 如何选择能最大幅度缩小故障假设集合的压力实验，并判断何时证据足够、何时应停下实验去修复。三个候选点水位曲线、传感器底噪和房间描述起初完全相同；唯一可分辨来源是主动执行 X/Y 测试。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`battery`, `bulkhead_state`, `generator_online`, `goal`, `location`, `oxygen_reserve`, `oxygen_stable_ticks`, `oxygen_support_on`, `p_sacrificed`, `packet_complete`, `tick`, `visible_edges`, `water_E`, `water_P`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`battery`, `bulkhead_closed`, `generator_online`, `location`, `oxygen_depleted`, `oxygen_reserve`, `oxygen_stable_ticks`, `oxygen_support_on`, `p_sacrificed`, `packet_complete`, `repair_actions`, `safe_ticks`, `short_circuit`, `transmit_power_failed`, `valid_ticks`, `violations`, `water_E`, `water_P`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `inspect`：`target_id`
- `interact`：`arguments`, `operation`, `target_id`
- `interact`：`operation`, `target_id`
- `move`：`edge_id`
- `wait`：`ticks`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：每 tick 依次结算漏水、泵、电池/短路、供氧、通信；四链共享同一资源池。

- 成功码：`DISTRESS_PACKET_SENT`
- 失败码：`OXYGEN_DEPLETED`, `SHORT_CIRCUIT`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map09.fault_propagation_scale` | primary | lower_is_better | count(subsystems entering unsafe state after first fault) | 子系统总数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map09.hard_threshold_breaches` | guardrail | lower_is_better | count(WATER_HARD_LIMIT) + count(OXYGEN_HARD_LIMIT) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map09.repair_actions` | diagnostic | lower_is_better | count(repair/power/oxygen/pump/seal actions) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map09.repair_dependency_violations` | diagnostic | lower_is_better | count(REPAIR_DEPENDENCY_VIOLATION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map09.stable_time_ratio` | primary | higher_is_better | safe_system_ticks / valid_ticks | 有效 tick 数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：preserve_and_pump（12 步）, sacrifice_P（8 步）
- 手算 fixture：sacrifice_route_sends_packet（8 步）, open_bulkhead_wait_shorts_power_bay（2 步）, oxygen_restart_without_generator_is_refused（4 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-09` → `MAP-09: OK`。

## 9. MiMo 三次正式运行

正式 90 局尚未生成；本节由 `scripts/report_v8_maps.py` 在运行结束后回填。

## 10. 未决问题与边界说明

传播规模使用裁判侧事件计数；公开侧只能看到系统状态，无法自行区分同故障持续与二次传播。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`pending`；最终状态：`runtime_verified`。
