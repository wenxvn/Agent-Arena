# DCR-05：MAP-11 公开“移动消耗随身补给 + 不足即失败”

- 状态：`accepted`（仅 `v9_fixed` 臂的公开信息补充）
- 地图：MAP-11
- 关联审计：`docs/v9/maps/MAP-11-audit.md`
- 影响面：prompt（`prompt_hash`），不改规则
- 证据：V8 三局全部在决策 2 `move B_P_SHORT` 返回 `SUPPLY_SHORTAGE`；此前 R0–R2 决策 1 都只 `scout`，`carried_supply` 仍为 0。

## 1. 原始公开信息

Observation 有 `carried_supply=0`、`carried_supply_capacity=8`、`supply_depot_B=8`；词表有 `resupply(quantity)`，但没有说明移动会消耗补给、消耗量、以及不足即终局。

## 2. 根因

**B + C**：`SUPPLY_SHORTAGE` 出现在“从 B 出发的第一步”，模型很容易把它理解为“补给总量不足”，而实际是“没有随身携带”。规则“短道 2/长道 1”只存在于 `map11.py::EDGE_SUPPLY`。

## 3. 修复（只补公开规则）

`V9_PUBLIC_ADDENDA["MAP-11"]`：

> 每次 move 都消耗随身补给：短道 B_P_SHORT / P_S_SHORT 各 2，长道每段 1；携带不足会立即 SUPPLY_SHORTAGE 失败。resupply 只能在 B 执行，容量 8；救回队员后的负重返程需 loaded_return=true。

## 4. 可行性复算

Oracle 3/3、公开启发式成功（`runs/v9/baselines/MAP-11.json`）；短道路线只需 8 单位，正好等于容量与油库初值，说明设计是“装满载再走”。

## 5. 预期与风险

- 预期：模型先 `resupply(8)`，再进入真正的天气/热量/救援权衡。
- 风险：公开后短道路线几乎没有补给压力；长道路线仍有 6 单位与风暴风险，构念保留。
- `rule_hash` 不变；`prompt_hash` 变化。

## 6. 验证

- V9 MiMo 同期对照见 `docs/v9/mimo-results.md`；
- 泄漏检查同 DCR-02。

## 7. 回滚

删除该 addendum。
