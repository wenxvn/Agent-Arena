# V9 数据完整性审计

- 复算脚本：`python -m agent_arena.v9.audit`、`python -m agent_arena.v9.evidence`、`python -m agent_arena.v9.report`
- 逐局索引：`docs/v9/run-index.csv`（含每局 `trace_sha256`、judge 决策数、失败码、五态计数）
- 证据包：`runs/v9/evidence/MAP-01.json` … `MAP-30.json`（每包只含公开 Observation 与 judge 指标，不含隐藏 `judge_state`）

## 1. 记录完整性

| 检查 | 结果 | 证据 |
|---|---|---|
| registry 行数 | 90 | `runs/v8/results_90.csv` |
| (map, replicate) 唯一 | 90/90 | 无重复、无缺失 |
| run_id 唯一 | 是 | 90 个不同 UUID 后缀 |
| Trace 可读 | 90/90 | 每局 `agent_trace.jsonl` |
| judge / v8 metrics 可读 | 90/90 | 每局两文件 |
| Trace 决策行 = judge `decision_count` | 90/90 | 逐局比对 |
| judge success/终止原因 = registry | 90/90 | 逐局比对 |
| 终止后仍有决策行 | 0 | Trace 在终局即停止 |
| 非法动作（schema 拒绝） | 1 局 1 次（MAP-17 R0） | `invalid_action_count` |
| provider 错误的正式局 | 0 | registry `provider_error` 为空 |
| unknown spend 的正式局 | 0 | 4 次均发生在被替换的旧尝试 |
| 不可验证（`UNVERIFIABLE`）项 | 0 | — |

`runs/v8` 下 `episode_manifest.json` 共 100 个 ≠ 90，因为包含 4 个 superseded 旧局与 6 个预跑/补充尝试；正式 90 行以 `results_90.csv` 的 run_id 为准，其余目录只作历史保留，不进入 V9 统计。

## 2. 版本与冻结一致性

- 90 条 Trace header 的 `scenario_hash`、`rule_hash`、`source_hash`、`prompt_hash`、`metric_schema_hash` 与 `runs/v8/freeze_manifest.json` **逐条一致**（不一致 0 条）。
- 当前 HEAD 重新计算 30 图上述 5 类 hash，与冻结清单 **30/30 一致**；MAP-12 的 `decision_budget=60` 例外按其 map 条目比较，prompt hash 也按 60 重新生成后一致。
- 三个 commit 分布为 60 / 27 / 3，但测量 hash 完全相同；可视为同一测量条件。
- V9 没有改写任何 V8 hash 或文件；新增内容全部在 `src/agent_arena/v9/`、`docs/v9/`、`runs/v9/`。

## 3. 费用完整性

| 口径 | 金额（CNY） | 说明 |
|---|---|---|
| 正式 90 局 | 1.27464628 | registry 逐局求和 = CSV = judge usage 求和 |
| main + supplement_001–006 | 1.39004496 | 含 10 个 superseded/补跑旧局 |
| 全部 V8 账本（含 5 次 aborted 预跑） | 1.45502656 | 另含 26 个作废预跑 episode |

- 90 个正式 run_id 各自只在**一个**账本产生 settled 费用，合计与正式口径一致。
- 4 次 unknown spend：`V8-MAP-13-R2-…`、`V8-MAP-15-R0-…`、`V8-MAP-26-R2-…`、`V8-MAP-28-R0-…`；均保留原记录并由新 run_id 补跑。
- 未发现“有 settled 无 reserved”或“有 reserved 无 settled”的正式局。

## 4. 指标五态完整性

全部 30 图、90 局的投影结果中：

- `unavailable`：0
- `invalid_trace`：0
- `censored`：5，全部来自 MAP-18 的 2 个 `step_limit_reached` 局
- `not_applicable`：其余全部来自分母为 0 或地图返回 `None` 的指标
- 每图指标条目数 12–24（3 局合计），与 V7 registry 的 4–8 条/图一致

### 4.1 系统性口径问题（需在 Batch 6 评估）

`src/agent_arena/v8/metrics.py::_empty_status` 对 `None` 只区分两种结局：

```python
return MetricStatus.CENSORED if outcome == "censored" else MetricStatus.NOT_APPLICABLE
```

因此在 **32 个 `decision_budget_reached` 局**中，凡是地图未给出值的指标（包括本可计算的连续指标）一律被投影为 `not_applicable`，而不是“预算截尾的 censored”。这会让 15 张地图的主指标在预算耗尽时整列变成 N/A——例如：

| map | 3 局均 N/A 的指标 | 局数 |
|---|---|---|
| MAP-07 | `map07.correct_direction_rate` | 3（全部预算耗尽） |
| MAP-08 | `map08.diagnosis_accuracy`、`map08.wrong_repair` | 3 |
| MAP-14 | `map14.globally_consistent_hypothesis_rate` | 3 |
| MAP-22 | `map22.path_gap` | 3 |
| MAP-26 | `map26.diagnosis_accuracy`、`map26.recovery_latency`、`map26.repeat_error_rate` | 3 |
| MAP-29 | `map29.evidence_supported_testimony_ratio` | 3 |
| MAP-30 | `map30.accusation_claim_precision`、`map30.q4_recall_accuracy` | 2 或 3 |

这些 N/A 里，一部分是分母确实为 0（例如没有任何修复动作时的 `wrong_repair`），另一部分是地图在未完成时主动返回 `None`；两者语义不同但当前投影把它们混在一起。V9 把它登记为 **METRIC_DEFECT 候选**，修复前必须先逐图确认“未完成时是否真的有可计算值”，不能简单改状态。

### 4.2 每图缺失明细

见 `runs/v9/reports/data-digest.md` §2。汇总特征：

- 只有 MAP-05、MAP-09、MAP-10、MAP-12、MAP-15、MAP-17、MAP-19、MAP-20、MAP-25、MAP-28 的 3 局没有任何 N/A。
- N/A 最集中的图：MAP-26（9/21）、MAP-08（6/21）、MAP-18（4/20 + 5 censored）、MAP-24（4/12）。
- MAP-18 是唯一同时出现 `censored` 与 N/A 的图，说明“环境 horizon 截尾”与“决策预算耗尽”在指标层被区别对待，但 `decision_budget_reached` 没有进入 censored 分支。

## 5. 可复算性与重放边界

- 所有 Trace 均带 `state_hash_after`；`scripts/replay_v3_oracles.py` 一类的离线回放只能验证规则与 Oracle，不能把 V8 Trace 的动作序列直接重放到修改了规则的 V9 环境。
- V9 的规则修改必须新建 `docs/v9/dcr/DCR-XX.md`，并把 old/new rule hash 与“旧 Trace 不可直接回放”的结论写清楚。
- 证据包对 Observation 只保留变化字段，无法据此伪造未发生的状态；原始 Trace 才是权威来源。

## 6. 已知限制

1. **n=3 不是独立场景 seed**：三次重复使用 `seed=0` 与 `replicate_id=0/1/2`，只能描述重复运行。
2. **6 张 V4 适配图**（MAP-08/16/18/22/26/30）复用 V6 冻结实例，场景哈希指向 `mapXX_l3_original` 等；其地板/天花板效应与 V6/V7 历史一致，不能当作 V8 新机制的效果。
3. **prompt 只以 hash 校验**：V8 没有把完整 system prompt 存入 Trace；V9 只能重算 hash 证明“同代码同 prompt”，不能从 Trace 还原当时逐字文本。
4. **成本单价来自供应商公开价目**：账本按 MiMo 公开单价结算，实际账单可能有折扣/缓存差异；V9 不宣称与真实账单逐分一致。
5. **judge 指标不是独立第二实现**：V8 的 extractor 与 fixture 同源；V9 Batch 5 才建立独立复算路径。
