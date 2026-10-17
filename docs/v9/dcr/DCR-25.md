# DCR-25：MAP-25 诊断完成度记账与覆盖率分母

- 状态：`proposed`（`requires_user_decision`）
- 地图：MAP-25
- 关联审计：`docs/v9/maps/MAP-25-audit.md`
- 提出人：DeepSeek V4.1 Flash（执行 Agent）
- 日期：2026-10-17
- 规则版本：V8 冻结 `rule_hash=51e3acc1edab3736d0300c112d96539ec316601e0b7c12feab99a9cb96a15065` → V9 候选 **规则不变**；仅 `metric_schema_hash` 变化
- 影响面：指标（候选 A/B）；公开信息（候选 C）

## 1. 原始规则与公开信息

```python
# src/agent_arena/worlds/scenario_v8/maps/map25.py:261-282
def _diagnose(self, action: V8Action) -> str:
    correct = (
        self.node == "S"
        and self.array_inspected
        and "diagnostic_unit" in self.tools
        and self.oxygen >= 1
    )
    self._record_required("diagnosed", correct=correct, done=correct)   # 先记账
    if action.device_id != "diagnostic_unit":                           # 后校验
        return self._reject_zero("INVALID_TOOL_ID")
```

```python
# src/agent_arena/worlds/scenario_v8/maps/map25.py:23-31
REQUIRED_STEPS = ("eva_suit","diagnostic_unit","wrench","safety_tether",
                  "equipment_inspected","array_inspected","diagnosed")
```

公开面：`_VOCABULARY["MAP-25"]` 写 `diagnose(device_id): diagnostic_unit`；`worlds/v4/MAP-25/map_spec.yaml` 第 35 行写 `inspect_equipment_required_for_success: false`。

## 2. 证据与根因

- 事实（V8 R2 决策 30）：`{"tool":"diagnose","device_id":"array"}` → `INVALID_TOOL_ID`，`diagnosis_code_if_obtained=null`；末态 `map25.required_check_coverage=7/7`、`dependency_order_correctness=9/13`。
- 事实（本次独立复算，只调用公开 `step`）：同一状态下调用 `diagnose(device_id="array")`，覆盖率 6/7 → **7/7**，依赖正确率 6/6 → 7/7，而 `judge_state.diagnosed=False`、`diagnosed` 未进入 `required_done` 的正常来源。
- 事实（本次复算）：跳过 `inspect(equipment)` 的 15 步成功路线只能得 `6/7`，说明分母里的 `equipment_inspected` 连成功都不要求。
- 根因分类：**A 环境规则缺陷（记账层）** + **M 指标口径**；不属于 B/C/D/E。
- 推断：R2 的“检查覆盖完成却失败”不是模型做对了准备阶段，而是指标把一次被拒动作记成完成；R2 的真实瓶颈是 `device_id` 填错（7 次中 3 次）导致无诊断码。

## 3. 候选方案

| 方案 | 改动 | 预期收益 | 代价/风险 | 是否改变能力构念 |
|---|---|---|---|---|
| A（推荐） | `map25.metrics()` 的 coverage 分子改为 `len(required_done - {"diagnosed"}) + int(self.diagnosed)`；依赖正确率同样以 `self.diagnosed` 为准 | R2 覆盖率回到 6/7；Oracle/启发式仍 7/7；指标与 `diagnosed` 一致 | `metric_schema_hash` 变化，旧值需只读重算；不改 `rule_hash`/`scenario_hash` | 否 |
| B | 从 `REQUIRED_STEPS` 移除 `equipment_inspected`，分母改 6 | 覆盖率与成功判定一致（15 步路线与 16 步路线同为 1.0） | 与 V7 卡片的 7 项口径冲突，需要同步文档与 fixture | 否（只是分母定义） |
| C（仅公开信息） | `_VOCABULARY["MAP-25"]` 增加“节点邻接 H–T–A–S；舱外每步耗氧 exit/inspect/diagnose=1、repair=2、return=1” | 减少 `NOT_ADJACENT`（三局 8 次）与重复出舱 | `prompt_hash` 变化；可能把 0/3 推到 3/3，削弱简单层区分度 | 否（不改变机制） |

## 4. 选择理由

选 A：它是**唯一不改变规则、只让指标名实相符**的改动，且能直接用 `judge_state.diagnosed` 交叉验证。B 也正确但会牵动 V7 卡片与冻结 fixture；C 属于“补公开信息”，应作为独立 DCR 在 Batch 6 用对照实验评估，不与指标修复捆绑——否则无法判断成功率变化来自信息补充还是指标修正。

不违反“不为通关率改规则”：A/B 都不改任何致死条件、资源数值或成功判定，只改“什么算完成了一次诊断”。

## 5. 预期能力构念影响

- 机制不变：仍需穿服、挂绳、排压、检查、诊断、精确工具维修、返舱。
- 修复后，`required_check_coverage=1.0` 将**只可能**出现在真正取得诊断码的局；模型仍可合法失败（R0/R1 的路径不受影响）。
- 不引入新的隐藏真值：`diagnosed` 已是 `judge_state` 字段，公开面通过 `diagnosis_code_if_obtained` 等价可见。

## 6. 兼容性与版本隔离

- 旧 V8 Trace **可回放**（规则与动作契约未变），但指标需用 `runs/v9/rescore/` 只读重算，不覆盖 `runs/v8`。
- 新 hash：`scenario_hash` / `rule_hash` / `source_hash` / `prompt_hash` **不变**；`metric_schema_hash` 变化（需重新冻结）。
- 不需要新 instance seed 或 condition；V8 目录保持只读。

## 7. 指标变化

- `map25.required_check_coverage`：分子从 `len(required_done)` 改为“真实完成项”，R2 由 1.0 → 0.857143。
- `map25.dependency_order_correctness`：`diagnosed` 的 `correct` 记账同样改为“设备名正确且执行成功”，R2 由 9/13 → 8/12（示例值，以修复后重算为准）。
- 修复 `METRIC_DEFECT` 候选；不改变 `oxygen_shortfall` 与 `unsafe_eva_attempts`。

## 8. 反例测试（先写失败测试）

新增 `tests/test_v9_map25_metrics.py`：

1. `test_rejected_diagnose_does_not_complete_check`：在 S 且持诊断仪时提交 `device_id="array"`，断言 `required_check_coverage < 1.0` 且 `judge_state.diagnosed is False`。**修复前失败**。
2. `test_oracle_and_public_heuristic_still_full_coverage`：重放两个 Oracle 与 `Map25Heuristic`，断言 7/7（或按 B 为 6/6）。
3. `test_fifteen_step_route_is_full_under_option_b`（仅 B）。
4. 泄漏扫描：`scripts/check_v8_map.py MAP-25` 通过。

## 9. 回滚方案

单提交回滚 `map25.metrics()`；`metric_schema_hash` 回退到冻结值；V9 重算结果保留在 `runs/v9/`，不影响 V8。

## 10. 验证记录

| 命令 | 结果 |
|---|---|
| `pytest tests/test_v9_map25_metrics.py` | 待实现 |
| `python -m agent_arena.v9.baseline_run MAP-25` | 待重跑（预期 Oracle 2/2、启发式成功、消融 `OXYGEN_DEPLETED`） |
| `python scripts/validate_v8_offline.py`（只读回归） | 待跑 |
| 泄漏扫描 `scripts/check_v8_map.py MAP-25` | 当前为 `MAP-25: OK` |

## 11. 结论与后续

- `requires_user_decision`：A 与 B 二选一（建议 A），C 单独评估。
- 未解决：MAP-25 的三局都没有执行过 `repair`，本图“维修→返舱”链路仍缺真实模型证据；即使修复指标，也只能说明 R2 的覆盖率不再是假 1.0，不能说明模型会维修。
