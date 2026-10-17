# DCR-02：MAP-05 公开 `switch_power` 位置与信号结算窗口

- 状态：`accepted`（仅 `v9_fixed` 臂的公开信息补充）
- 地图：MAP-05
- 关联审计：`docs/v9/maps/MAP-05-audit.md`
- 影响面：prompt（`prompt_hash`），不改规则
- 证据：V8 R0 决策 1–11 在非 C 位置反复 `switch_power`，全部返回 `TARGET_NOT_VISIBLE`；R1 决策 14（tick 17，站在 C）仍有 11 个动作的完胜线。

## 1. 原始公开信息

词表只写 `switch_power(station): R, B, W`，没有说该动作只能在 C 执行；`send_signal` 的窗口语义也只靠 `windows` 字段与结果码推断。

## 2. 根因

- 首因 **C**：错误码 `TARGET_NOT_VISIBLE` 暗示“目标不可见”，而实际原因是“当前位置不能切电”，反馈与真实前置不一致。
- 次因 **B**：窗口外 `send_signal` 不返回专门错误码，模型无法从反馈区分“已发射”与“未计入窗口”。

## 3. 修复（只补公开规则）

在 `V9_PUBLIC_ADDENDA["MAP-05"]` 增加：

> switch_power 只能在 C（总电源）执行；在其他位置执行会被拒绝。send_signal 的结算 tick 必须落在对应窗口内，窗口外发射不会计入有效信号。

## 4. 预期与风险

- 预期：减少非 C 位置的无效切电；不改变 Oracle（Oracle 本来就在 C 切电）。
- 风险：可能让 MAP-05 从 0/3 提升；这是接口修复的预期效果，不是“加资源”。
- 不改变 `rule_hash`/`scenario_hash`；`prompt_hash` 变化，V9 必须用同期 `v8_compat` 对照。

## 5. 验证

- `tests/test_v9_overlay.py::test_v8_compat_prompt_is_unchanged_for_fixed_maps`
- `tests/test_v9_overlay.py::test_addenda_do_not_leak_internal_identifiers`
- 公开启发式 `Map05Heuristic` 19 决策成功（`runs/v9/baselines/MAP-05.json`）。

## 6. 回滚

删除 `V9_PUBLIC_ADDENDA["MAP-05"]` 即回到 V8 prompt。
