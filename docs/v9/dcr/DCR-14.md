# DCR-14：MAP-07 / MAP-08 / MAP-26 的公开词表枚举缺口

- 状态：`accepted`（仅 `v9_fixed` 臂的公开信息补充）
- 地图：MAP-07、MAP-08、MAP-26
- 关联审计：对应 `docs/v9/maps/MAP-XX-audit.md`
- 影响面：prompt（`prompt_hash`），不改规则、不改适配层

## 证据

| 地图 | 缺口 | 证据 |
|---|---|---|
| MAP-07 | 词表写 `target_id=console`，运行时只接受 `control_panel` | V8 三局 30 决策、`interventions=0`；每次 `TARGET_NOT_VISIBLE` |
| MAP-08 | `visible_edges` 是 `"A_B:B"` 复合串；词表没有 `move`；`inspect` 词表写 X/Y，运行时只接受 `ordinary_sensor` | R0 决策 1 `INVALID_INSPECT_TARGET`、决策 2 `INVALID_EDGE`；38 决策耗尽，`tests_run=0` |
| MAP-26 | `log_id`/`test_id`/`part_id` 取值域完全不在公开面 | R1 决策 15 `take_spare(part_id="SPARE_1")` → `INVALID_PART_ID`；三条轨迹一次有效测试/更换都没有 |

## 修复

`V9_PUBLIC_ADDENDA`：

- MAP-07：控制台 `control_panel`；`set_valve` arguments 形状。
- MAP-08：`visible_edges` 的 `边名:另一端` 格式；`move` 用裸边名；`inspect` 用 `ordinary_sensor`；压力测试用 `interact(X|Y, pressure_test_*)`。
- MAP-26：三个枚举与动作地点。

这些枚举在 `map_spec.yaml` 中本来就是公开设计域；修复不泄露故障件、不泄露测试结果，只移除“猜字符串”的接口噪声。

## 预期与风险

- MAP-07：从 0 次干预变为可操作阀门，才真正开始测“顺序预判”。
- MAP-08：从“猜边名/猜 inspect 目标”回到“诊断与修复”。
- MAP-26：从 38 步全被拒回到“读日志 → 测试 → 更换 → 重启”。
- 风险：MAP-26 的枚举公开后，诊断空间仍由测试结果决定，不构成答案泄露。
- `rule_hash` 不变；`prompt_hash` 变化。

## 验证

- `tests/test_v9_overlay.py::test_addenda_do_not_leak_internal_identifiers`
- 公开启发式：MAP-07 6 步、MAP-08 5 步、MAP-26 待复测（见 `runs/v9/baselines/`）。

## 回滚

删除三条 addendum。
