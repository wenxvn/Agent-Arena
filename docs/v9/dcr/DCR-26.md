# DCR-26：MAP-26 参数值域公开与形状校验

- 状态：`proposed`（`requires_user_decision`）
- 地图：MAP-26（V4 适配图，`condition=free_diagnosis`）
- 关联审计：`docs/v9/maps/MAP-26-audit.md`
- 提出人：DeepSeek V4.1 Flash（执行 Agent）
- 日期：2026-10-17
- 规则版本：V8 冻结 `rule_hash=a0de5a1957c0a82cff7636ba86f8ce513c85d7ec30edee810885dcd882cc595e` → V9 候选 **环境规则不变**；`prompt_hash` 与（可选）`metric_schema_hash` 变化
- 影响面：公开信息 / prompt / 接口 / 指标

## 1. 原始规则与公开信息

```python
# src/agent_arena/v8/prompts.py:284-287
"MAP-26": (
    "move(to): D, A, B；read_log(log_id)；test(test_id)；"
    "take_spare(part_id)；replace(part_id)；rollback()；restart()",
),
```

```python
# src/agent_arena/v8/prompts.py:339-353（action_contract）
f'"{field}": {_FIELD_NOTES.get(field, "按 Observation 类型")}'
# log_id / test_id / part_id 均不在 _FIELD_NOTES 中 → 渲染为“按 Observation 类型”
```

```python
# src/agent_arena/worlds/scenario_v8/v4_adapter.py:197-209（step 未调用 accepts）
result = self._inner.step(converted)
# V8 SHAPES 对 6 张适配图不生效
```

设计侧（**未公开**）：`worlds/v4/MAP-26/map_spec.yaml` 第 32、53、54 行给出
`candidate_parts: [power_regulator, antenna_coupler, software_image]`、
`log_id: COMM_LOSS_LAST_TRANSMIT`、`test_id: [bus_load, antenna_loopback, software_checksum]`。

## 2. 证据与根因

- 事实（R1 决策 15）：`{"tool":"take_spare","part_id":"SPARE_1"}` → `INVALID_PART_ID`。模型**自己编造**了零件名。
- 事实（R0 决策 7，已在 D）：`{"tool":"read_log"}` → `INVALID_LOCATION`；同一动作在 T/A/B/D 全部返回同一个码，模型无法区分“错地点”与“缺参数”。
- 事实（R2 决策 19/27/29/37）：4 次 `test` 都不带 `test_id`，全部 `INVALID_LOCATION`，但 `tests_run` 记成 4。
- 事实（本次 V9 公开启发式）：把 Observation 中出现过的字符串逐个当参数值，38 决策全部被拒（`legal_action_rate=1/38`），`test_readings={}`、备件 2 枚未动。
- 事实（Oracle）：`MAP-26-solver-success` 只有 9 步，说明预算与规则都不是瓶颈。
- 根因分类：**B 公开信息不足（三个参数域）** + **C 接口误导（缺参数 → `INVALID_LOCATION`；adapter 跳过 SHAPES）**。
- 附带事实：适配图的系统提示“本图机制”取到 `V4MapAdapter` 的 docstring `"A V4 environment behind the V8 public contract."`，场景标题退化为 `MAP-26`，`goal` 字段不存在。

## 3. 候选方案

| 方案 | 改动 | 预期收益 | 代价/风险 | 是否改变能力构念 |
|---|---|---|---|---|
| A（推荐） | `_VOCABULARY["MAP-26"]` 补上设计规格里已公开的取值域：节点 `T|D|A|B`、`log_id: COMM_LOSS_LAST_TRANSMIT`、`test_id: bus_load|antenna_loopback|software_checksum`、`part_id: power_regulator|antenna_coupler|software_image` | 测试/取件/更换第一次变得可表达；失败回到“选哪个测试、何时回滚” | `prompt_hash` 变化；不泄漏故障件（仍是 3 选 1） | 否（仍是诊断-反馈-纠错） |
| B | `V4MapAdapter.step` 先走 `accepts(action)`；缺字段返回 `INVALID_ACTION_SCHEMA`，D 处 `log_id` 不匹配返回 `INVALID_LOG_ID` | 错误码不再把“缺参数”伪装成“错地点” | 旧 Trace 的 `INVALID_LOCATION` 序列变化；需新 experiment | 否 |
| C | 指标：`tests_run` 只统计 `TEST_COMPLETED:*`；`diagnosis_accuracy` 的 `replaces` 只收集被执行（非 `INVALID_*`）的 replace | R2 `tests_run` 回到 0；公开启发式 `diagnosis_accuracy` 回到 N/A | `metric_schema_hash` 变化 | 否 |
| D | 为六张适配图提供真实 `title` 与一句话机制（含“通信中断、三个候选部件、两条备件”） | 模型至少知道任务形状 | 纯文案；`prompt_hash` 变化 | 否 |

## 4. 选择理由

A 是**唯一能让公开策略真正进入机制**的修复；B/C 是必要的接口与指标卫生，但不能单独解决“没有字符串可提交”。D 补的是任务语义，可与 A 合并为一次 prompt 版本。

不违反“不为通关率改规则”：A/D 只公开设计文档里本来就写着、模型必须自己猜的字符串；不公开 `fault_part`、不公开 seed 映射、不增加备件、不延长预算。

## 5. 预期能力构念影响

- 修复前：三局连一次测试都没执行，构念“错误归因与自我纠错”未被激活。
- 修复后：`read_log` 仍是**模糊线索**，三个测试仍是唯一的确定证据，2 枚备件仍不可增加；模型仍可能盲换、重复同件、无视阴性读数（三条失败 fixture 保持有效）。
- 合法失败仍存在：只测一项就盲选剩余两个、或把两枚备件都用在错误件上。

## 6. 兼容性与版本隔离

- `rule_hash` / `scenario_hash` / `source_hash` **不变**，所以 V8 Trace 的**动作序列**仍可在同一环境回放；但 `prompt_hash` 变化，V8 的“同一测量条件”不再成立，必须作为 V9 新 arm（如 `v9_fixed`）运行。
- 候选 B 若实施，则 `INVALID_LOCATION` → `INVALID_ACTION_SCHEMA`/`INVALID_LOG_ID`，旧 Trace 的失败码含义改变，需新 DCR 与只读重算。
- V8 文件保持只读；新结果写入 `runs/v9/`。

## 7. 指标变化

- C 修复两个分母/事件口径：`map26.tests_run` 与 `map26.diagnosis_accuracy`。
- 旧值保留：在 `runs/v9/rescore/` 用旧 extractor 重算，不覆盖 V8。
- `recovery_latency` / `repeat_error_rate` 的口径不需要改（已按“错误替换反馈/错误替换数”计），但 `adapter_cases` 的 fixture 期望 `None` 与 V7 状态 `censored` 不一致，建议同批统一。

## 8. 反例测试（先写失败测试）

新增 `tests/test_v9_map26_public_vocab.py`：

1. `test_rejected_replace_is_not_a_diagnosis`：提交 `replace(part_id="garbage")`，断言 `diagnosis_accuracy` 为 N/A 而非 0。**修复前失败**。
2. `test_tests_run_counts_executed_only`：提交 `test` 不带 `test_id`，断言 `tests_run=0`。**修复前失败**。
3. `test_public_vocabulary_only_policy_reaches_success`：只用新增词表中的字符串（不读 `fault_part`）写一个 9 步策略，断言 `communication_restored=true` 且 `spares_remaining=1`。
4. `test_missing_log_id_has_distinct_error`（B）：在 D 提交 `read_log` 无 `log_id`，断言不是 `INVALID_LOCATION`。
5. 泄漏扫描：`check_v8_map.py MAP-26` 通过；断言 prompt 中不出现 `antenna_coupler` 与“fault”组合。

## 9. 回滚方案

prompt 词表是单行常量，回滚即恢复 `_VOCABULARY["MAP-26"]` 原行；`prompt_hash` 回到冻结值。候选 B 以开关形式包在 `V4MapAdapter.step` 的 `if self.condition_id != ...` 分支，可按需关闭。

## 10. 验证记录

| 命令 | 结果 |
|---|---|
| `pytest tests/test_v9_map26_public_vocab.py` | 待实现 |
| `python -m agent_arena.v9.baseline_run MAP-26` | 当前：Oracle 1/1、启发式失败（38 决策、合法率 1/38） |
| `python -m agent_arena.v9.baseline_run MAP-26`（修复后预期） | 启发式成功、`tests_run=2`、`spares_remaining=1` |
| `python scripts/validate_v8_offline.py`（只读回归） | 待跑 |
| 泄漏扫描 | 当前 `MAP-26: OK` |

## 11. 结论与后续

- `requires_user_decision`：A 必须先做，否则本图无法测量；B/C/D 建议同批。
- 未解决：即使 A 完成，`recovery_latency` 仍只在“发生错误替换”时有值；需要至少一局“换错→回滚→换对”的真实模型轨迹，才能验证该指标能否区分 Oracle 与消融。
