# DCR-27：MAP-27 动作地点表、受困判定与失败局指标

- 状态：`proposed`（`requires_user_decision`）
- 地图：MAP-27
- 关联审计：`docs/v9/maps/MAP-27-audit.md`
- 提出人：DeepSeek V4.1 Flash（执行 Agent）
- 日期：2026-10-17
- 规则版本：V8 冻结 `rule_hash=b993858b9d0b62305ac1950e6f3a1e5cd1a8f3c479606e1aa1f8a2850e255cf7` → V9 候选 **规则不变**；仅 `prompt_hash`（候选 A/C）或 `metric_schema_hash`（候选 B）变化
- 影响面：公开信息 / prompt / 指标

## 1. 原始规则与公开信息

```python
# src/agent_arena/v8/prompts.py:288-292
"MAP-27": (
    "load(item_id): sample_container|medical_kit|relay_repair_kit；"
    "drive(to)；charge()；repair_relay()；sample(item_id)",
    "rescue(operation[, item_id]): field_stabilize（配 medical_kit）|"
    "remote_evacuation；submit()",
),
```

```python
# src/agent_arena/worlds/scenario_v8/maps/map27.py:251-253
def _charge(self) -> str:
    if self.node != "S":
        return "INVALID_LOCATION"
```

```python
# src/agent_arena/worlds/scenario_v8/maps/map27.py:246-248（受困判定）
if self.node != "B" and self._min_energy_to_base(self.node) > self.battery:
    self._fail("VEHICLE_STRANDED")
```

```python
# src/agent_arena/worlds/scenario_v8/maps/map27.py:408-410（critical_path_delay）
delay: int | None = None
if self.is_success:
    delay = max(0, self.tick_count - self.REFERENCE_CRITICAL_PATH)
```

设计侧规则（**未公开**）：`worlds/v4/MAP-27/map_spec.yaml` 的 `charging.location: S`、`sample.location: P`、`relay.location: R`、`rescue.field_stabilization.location: E`、`vehicle.strand_condition`。

## 2. 证据与根因

- 事实（R1 决策 9）：`{"tool":"charge"}` 在 **E** → `INVALID_LOCATION`；同局 `charger_cells_remaining` 在 E 为 `null`、在 S 为 `1`（R0 决策 2 观察可证）。这是地点错误，不是 `CHARGER_EMPTY` / `BATTERY_ALREADY_FULL` / `RESOURCE_CONFLICT`。
- 事实（R0 决策 8）：电 2 在 R，回 B 最低需 3 → `VEHICLE_STRANDED`；R2 决策 6：电 1 在 P，回 B 最低需 5 → 同样终止。
- 事实（本次公开启发式）：只用 Observation（`local_edges` 成本、`supplies_here`、`charger_cells_remaining`、`objectives`）与零成本探测，**19 决策成功**，余电 2、余氧 6、`critical_path_delay=0`。
- 事实：三局 `critical_path_delay` 全为 N/A，因为 `metrics()` 只在成功时赋值；三局都是失败。
- 根因分类：**F 资源管理（首因）** + **E 路线规划**；公开信息缺口（**B**）只抬高门槛、不阻塞。
- 推断：三局都把“到 P”当成任务终点，未读 `objectives`，也未利用 `supplies_here`。

## 3. 候选方案

| 方案 | 改动 | 预期收益 | 代价/风险 | 是否改变能力构念 |
|---|---|---|---|---|
| A（推荐） | `_VOCABULARY["MAP-27"]` 增加一行：`load` 的三种物品地点、`charge` 只在 S（一次性电芯 +4、需 1 格空货舱）、`sample` 只在 P、`repair_relay` 只在 R、`field_stabilize` 只在 E、每次 `drive` 后若电量不足以回 B 立即 `VEHICLE_STRANDED` | 把失败从“猜地点/不知道受困规则”移到“排程与电量预算” | `prompt_hash` 变化；可能把 0/3 推到 3/3，削弱困难层 | 否 |
| B | 新增失败局可算的连续量，如 `battery_margin_at_terminal = battery − min_cost_to_B`（可为负） | 能区分“差一步受困”与“一步没做” | 需新 `MetricSpec`、`valid_range`、extractor 与历史重算 | 否 |
| C | `goal` 扩写为“先稳定伤员、修复中继、封存样本，再回 B 提交” | 降低“把到 P 当终点”的误读 | `prompt_hash` 变化；属文案层 | 否 |

## 4. 选择理由

A 是“补公开信息”的最小改动，不改变任何数值或判定；C 与 A 可合并为一次 prompt 版本，但 C 单独实施无法解决 `charge`/`sample` 的地点试错。B 只解决“失败有多接近”，不能提高可解性；应在 A 之后作为补充指标评估，避免把“补信息”和“加指标”混为一次实验。

不违反“不为通关率改规则”：电量仍 14、氧气仍 18、电芯仍 1 枚、道路成本不变、受困判定不变。

## 5. 预期能力构念影响

- 修复后仍需自己算“每一段后是否还能回 B”，仍要在两格货舱里安排“样本 + 医疗包”与“样本 + 维修盒”的先后；`charge` 仍是只有一次机会的补偿，而不是免费补电。
- 合法失败仍存在：先修中继的 A 方案会在电 0 时成功，但任何折返都会受困；把医疗包与维修盒同时装进两格会挤掉样本容器。

## 6. 兼容性与版本隔离

- `rule_hash` / `scenario_hash` / `source_hash` **不变** → 旧 V8 Trace 可继续在同一环境回放；`prompt_hash` 变化 → 不能与 V8 视为同一测量条件，需 V9 新 arm。
- 候选 B 改变 `metric_schema_hash`；旧值用 `runs/v9/rescore/` 只读重算。
- V8 文件保持只读。

## 7. 指标变化

- A/C 不改变指标。
- B 新增一个失败局可算的连续指标；`critical_path_delay` 仍保持“只在成功时定义”，不改成对失败局取负值（那会把“没完成”误读成“迟到”）。
- `resource_conflicts` 在本图三局、两个 Oracle、启发式与随机中恒为 0，建议在 Batch 6 确认它是否只对“货舱塞满再充电”这一边界敏感。

## 8. 反例测试（先写失败测试）

新增 `tests/test_v9_map27_public_rules.py`：

1. `test_charge_outside_s_is_invalid_location`：在 E 提交 `charge`，断言 `INVALID_LOCATION` 且电/氧不变。
2. `test_strand_rule_matches_published_text`：按公开文本算出的“回程最低电量”与 `_min_energy_to_base` 一致（用 5 条边的手算表）。
3. `test_public_policy_with_published_table_succeeds`：只用公开表与 `local_edges` 的 19 步策略成功，`critical_path_delay=0`。
4. `test_battery_margin_metric_on_failure`（B）：三局 V8 的 `battery_margin_at_terminal` 分别为 −1（R0，R 处电 2 / 回程 3）、+1（R1，E 处电 3 / 回程 2，但下一步 P 需 4）、−4（R2，P 处电 1 / 回程 5）。
5. 泄漏扫描：`check_v8_map.py MAP-27` 通过。

## 9. 回滚方案

prompt 词表与 `goal` 是单处常量，回滚即恢复原文本；`prompt_hash` 回到冻结值。候选 B 的指标以注册表条目形式新增，删除即可回滚，不影响既有指标。

## 10. 验证记录

| 命令 | 结果 |
|---|---|
| `pytest tests/test_v9_map27_public_rules.py` | 待实现 |
| `python -m agent_arena.v9.baseline_run MAP-27` | 当前：Oracle 2/2、启发式 19 步成功、随机 0/20 |
| `python scripts/validate_v8_offline.py`（只读回归） | 待跑 |
| 泄漏扫描 | 当前 `MAP-27: OK` |

## 11. 结论与后续

- `requires_user_decision`：A 与 C 可合并为一次 prompt 修订；B 建议单独评估。
- 未解决：三局都没有装载任何备件/医疗包，说明“读目标”是独立于“知道地点”的能力缺口；补公开信息未必能解决“把到 P 当终点”，需要在 V9 对照中单独观察。
