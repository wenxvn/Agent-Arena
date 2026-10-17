# DCR-01：预算截尾指标不再投影为 `not_applicable`

- 状态：`accepted`（V9 层实现，不改 V8）
- 地图：全部 30 图
- 关联审计：`docs/v9/data-integrity.md` §4.1、各图审计 §6
- 规则版本：V8 `metrics._empty_status` → V9 `v9.metrics.empty_status`
- 影响面：指标五态投影（不改规则、不改 prompt、不改 V8 数据）

## 1. 原始规则

`src/agent_arena/v8/metrics.py:42`：

```python
def _empty_status(outcome: str) -> MetricStatus:
    return MetricStatus.CENSORED if outcome == "censored" else MetricStatus.NOT_APPLICABLE
```

V7 登记的 `censor_rule` 写的是“预算/provider 截尾 → CENSORED，并保留原因码”。

## 2. 证据与根因

- 90 局中 `decision_budget_reached` 有 **32 局**；这些局的 `None` 指标全部变成 `not_applicable`。
- 受影响最明显：MAP-07 `correct_direction_rate` 3/3 N/A、MAP-26 三条主指标 3/3 N/A、MAP-29/30 主指标 N/A。
- 90 局重算后共有 **28 个状态** 从 `not_applicable` 变为 `censored`，有效值与分母 0 变化（`runs/v9/rescore/summary.json`）。
- 根因分类：**METRIC_DEFECT**（实现与登记规则不一致），不是地图失败。

## 3. 候选方案

| 方案 | 改动 | 收益 | 风险 |
|---|---|---|---|
| A（采用） | V9 投影把 `decision_budget_reached`/`episode_timeout`/`schema_fault_limit`/provider 结局纳入 CENSORED | 与 V7 登记规则一致；区分“没做完”与“不适用” | 旧 V8 投影不变，需并列展示 |
| B | 直接改 V8 `metrics.py` | 统一口径 | 破坏 V8 冻结，禁止 |

## 4. 选择理由

V8 的 90 局与 hash 必须只读；V9 用独立投影层重算，旧值保留在 `runs/v9/rescore/MAP-XX.json` 的 `old` 字段。

## 5. 预期能力构念影响

不改变任何地图规则或成功率；只让“预算耗尽”在指标层被正确标记为截尾，避免把“没走完”误读成“该指标不存在”。

## 6. 兼容性与版本隔离

- 旧 Trace 可回放；仅重新解释 `v8_metrics.json` 的 `None`。
- V9 runner 的 `v9_metrics.json` 使用新投影，并额外记录 `overlay_schema_hash`。
- V8 文件未修改。

## 7. 指标变化

- 28 个 `not_applicable → censored`；无有效值变化。
- 仍保留“分母为 0”的真 N/A（如 MAP-04 R0 的 `window_hit_rate`）。

## 8. 反例测试

`tests/test_v9_audit.py::test_budget_censoring_is_not_not_applicable`、
`tests/test_v9_overlay.py::test_budget_censoring_marks_none_as_censored`、
`tests/test_v9_audit.py::test_rescore_counts_changes_without_touching_values`。

## 9. 回滚方案

删除 `src/agent_arena/v9/metrics.py` 的 CENSORING 分支即可；V8 不受影响。

## 10. 验证记录

| 命令 | 结果 |
|---|---|
| `python -m agent_arena.v9.metrics` | 90 局、30 图、28 个状态变化 |
| `pytest tests/test_v9_audit.py` | 8 passed |

## 11. 结论

`accepted`。这是 V9 唯一全图适用的指标修复；不构成实验启动授权，也不改 V8 历史。
