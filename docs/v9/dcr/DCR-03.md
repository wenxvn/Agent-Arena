# DCR-03：MAP-09 公开“隔板开放 → 水位 +1 → >4 短路”的硬规则

- 状态：`accepted`（仅 `v9_fixed` 臂的公开信息补充）
- 地图：MAP-09
- 关联审计：`docs/v9/maps/MAP-09-audit.md`
- 影响面：prompt（`prompt_hash`），不改规则
- 证据：V8 三局均在决策 2 以 `SHORT_CIRCUIT` 结束；R0 决策 1 `inspect water_gauges`（tick1，water_E 3→4），决策 2 再次 inspect（tick2，water_E 4→5）即失败。初始 Observation 只给 `water_E=3`、`water_P=5`、`bulkhead_state=open`，没有任何速率或阈值。

## 1. 原始规则（V8 私有实现）

`map09.py:264-281`：隔板开放且 `water_P>0` 时每 tick `water_P-=1, water_E+=1`；`water_E>4` 立即 `SHORT_CIRCUIT`。首动作只有 `isolate_compartment` 能阻止第 2 tick 的失败。

## 2. 根因

**B（公开信息不足）+ C（致命规则只在代码里）**。玩家看不到阈值与速率；硬约束是“**必须在第 2 个决策内、在 E 完成封舱**”（第 1 tick 后 water_E=4 仍可救，第 2 tick 后 water_E=5 即死）。首动作 inspect 仍可活，但必须立即封舱；任何 `wait(ticks=2)` 或先 `move` 都会死。Oracle 与公开启发式都靠“尽早封舱”成功，但这不能从公开面推导。

## 3. 修复（只补公开规则，不改阈值）

`V9_PUBLIC_ADDENDA["MAP-09"]`：

> E 舱与 P 舱之间的隔板开放时，每结算 1 tick 会把 1 单位水从 P 舱推入 E 舱（water_E +1）；water_E 超过 4 会立即短路失败。在 E 舱执行 interact(target_id=bulkhead_E_P, operation=isolate_compartment, arguments={mode: preserve|sacrifice}) 可关闭隔板并立即停止推进；关舱后 P 舱仍可抽水，但 sacrifice 会使 P 舱不可再进入。

## 4. 预期与风险

- 预期：模型可以在第一个决策就采取保命动作；后续仍要决定 preserve/sacrifice、抽水、恢复供电、供氧与发报，核心连锁构念不变。
- 风险：若 3/3 通关，说明接口修复消除了“盲猜首步”，而不是难度降低；仍需 V9 同期 `v8_compat` 对照。
- `rule_hash` 不变，`prompt_hash` 变化。

## 5. 验证

- Oracle 2/2、公开启发式成功（`runs/v9/baselines/MAP-09.json`）。
- 泄漏测试不含 `judge_state`/`metric_id`/`oracle`。
- V9 MiMo 同期对照见 `docs/v9/mimo-results.md`。

## 6. 回滚

删除该 addendum。
