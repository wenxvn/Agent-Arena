# DCR-07：MAP-16 公开预约/释放语义

- 状态：`accepted`（仅 `v9_fixed` 臂的公开信息补充）
- 地图：MAP-16（V4 适配图）
- 关联审计：`docs/v9/maps/MAP-16-audit.md`
- 影响面：prompt（`prompt_hash`），不改适配层与 V4 规则
- 证据：R0 决策 1–6 从未给 b 安排移动，6 决策 `DEADLOCK`；R1 决策 6/8/9/10 连续 `release_section` 返回 `INVALID_ROUTE`；R2 决策 22 接口接受 `{"a":"M","b":"M"}` 的冲突预约，决策 24 才 `move_train` 终局。

## 1. 原始公开信息

词表：`set_route`、`occupy_siding`、`release_section`、`inspect_network`、`move_train`，没有说明：

- `release_section` 只撤销本车**未提交**的预约；
- `occupy_siding` 只能预约与当前节点相邻的侧线 D；
- 同一节点可被两车同时预约，冲突在 `move_train` 才结算。

## 2. 根因

**C（接口语义误导）** 为首因，**E（规划）** 为次因。动作名暗示“释放已占用区段”，实际语义不同；容量冲突不在预约时拒绝，而在结算时判负。

## 3. 修复（只补公开规则）

`V9_PUBLIC_ADDENDA["MAP-16"]`：

> release_section 只撤销本车尚未提交的预约，不会释放已被占用的区段；occupy_siding 只能把与当前节点相邻的侧线 D 预约给指定列车；两车同时预约同一节点会在 move_train 结算时冲突。

## 4. 预期与风险

- 预期：模型不再用 `release_section` 清占用；R2 型冲突可在预约阶段避免。
- 风险：规则本身不变，Oracle/指标不变；`prompt_hash` 变化。
- V4 适配层与 V6 实例保持只读。

## 5. 验证

- 公开启发式 16 决策成功（`runs/v9/baselines/MAP-16.json`）。
- `pytest tests/test_v9_overlay.py -q`。

## 6. 回滚

删除该 addendum。
