# DCR-04：MAP-10 公开燃料分仓与发电机门槛

- 状态：`accepted`（仅 `v9_fixed` 臂的公开信息补充）
- 地图：MAP-10
- 关联审计：`docs/v9/maps/MAP-10-audit.md`
- 影响面：prompt（`prompt_hash`），不改规则
- 证据：V8 R0/R2 决策 2、R1 决策 5 均以 `GENERATOR_FUEL_SHORTAGE` 结束；R0 终局 `fuel_depot=10` 但 `carried_fuel=0`，即油库并不缺燃料。

## 1. 原始公开信息

- Observation 有 `fuel_depot`、`carried_fuel`、`carry_capacity`、`base_temperature`。
- 词表有 `load_fuel(quantity): 1..5`、`activate_generator()`, 但没有说：
  - 油库只供暖、发电机只吃随身燃料；
  - `load_fuel` 只能在 B 执行；
  - 发电机需要 3 单位随身燃料；
  - 燃料不足会立即结束本局。

## 2. 根因

**B（公开信息不足）+ C（终止码误导）**。终止码 `GENERATOR_FUEL_SHORTAGE` 让“没装燃料”看起来像“全局燃料耗尽”；三局都在同一个隐藏前置条件上终止，n=3 证据高度相同。

## 3. 修复（只补公开规则）

`V9_PUBLIC_ADDENDA["MAP-10"]`：

> fuel_depot 只用于基地供暖；发电机与雪地车只消耗 carried_fuel。load_fuel 只能在 B 执行，随身容量 5；activate_generator 需要至少 3 单位随身燃料；雪地车通过 E–W 需要 2 单位。随身燃料不足时动作会立即失败并结束本局。

## 4. 可行性复算

最低消耗 8（发电机 3 + 偶数 tick 供暖 5），初始 12，余量 4；公开启发式 5 决策成功（`runs/v9/baselines/MAP-10.json`）。因此不是资源总量或预算问题。

## 5. 预期与风险

- 预期：模型在 B 先 `load_fuel(3..5)`，失败从“不知道规则”回到“资源规划”。
- 风险：`load_fuel` 后仍需决定装 3/4/5；装少会导致发电机失败，构念保留。
- `rule_hash` 不变；`prompt_hash` 变化。

## 6. 验证

- `pytest tests/test_v9_overlay.py -q`（addendum 边界与泄漏）
- V9 MiMo 同期对照见 `docs/v9/mimo-results.md`。

## 7. 回滚

删除该 addendum。
