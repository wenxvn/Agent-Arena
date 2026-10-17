# V7 验证报告

- 日期：2026-10-17
- 基线提交：`766ec82529d4ee2499dde9592452eb68592f4637`
- 运行环境：Windows，Python 3.13.3，pytest 8.4.2，pydantic 2.13.4
- 付费 API：0 次；新账本：0 个；`runs/`、`results/`：未写入

本报告只记录本轮真实执行过的离线命令与输出。凡是设计态、离线回放或未执行的内容，均单独标注，不把设计态说成运行时，也不把离线回放说成真实模型实验。

## 1. 结论

| 项目 | 结果 | 证据 |
|---|---|---|
| 30 张逐图指标卡 | 30/30 存在，front-matter 哈希与冻结 V4 源文件一致 | `validate_v7_metrics.py` 通过 |
| 注册指标 | 154 条（6 图 44 条 implemented + 24 图 110 条 design-only） | 注册表与验收脚本一致 |
| 可运行 extractor | 6 图，独立实现，仅共享 schema/common/references 算术 | `src/agent_arena/v7/metrics/map*.py` |
| 六图离线回放 | 29/29 V6 实例全部成功复算，指标无 `invalid_trace` / `unavailable` | 验收脚本 + pytest |
| 24 图运行时 | **未实现**；调用 `compute_metrics` 抛 `NotImplementedError` | 单测固定 |
| 人工审阅 | **未进行**；30 卡保持 `pending_human_review` | front-matter + 验收脚本 |
| 真实模型 V7 结果 | **无**；本轮不产生任何模型对照 | 无 API 调用 |

## 2. 交付物

```text
docs/v7/
  README.md
  source-audit.md
  measurement-principles.md
  difficulty-rubric.md
  experiment-protocol.md
  map-review-checklist.md
  design-change-requests.md
  validation-report.md
  maps/MAP-01.md … MAP-30.md
  pending-runtime/README.md

src/agent_arena/v7/
  __init__.py
  metrics/{__init__,schema,common,references,registry}.py
  metrics/map08.py map16.py map18.py map22.py map26.py map30.py

scripts/
  validate_v7_metrics.py
  report_v7_metrics.py

tests/
  test_v7_metrics.py
  test_v7_map_metrics.py
```

设计态地图的运行时说明采用**单份准入表 + 逐图阻塞项**，而不是 24 份内容高度重复的 `pending-runtime/MAP-XX.md`。理由写在 `pending-runtime/README.md` 开头：避免模板化文件伪装成 24 份独立交付。每张图的完整指标定义仍在各自的 `maps/MAP-XX.md`。

## 3. 机器验收

### 3.1 注册表、卡片与六图回放

```powershell
.venv\Scripts\python.exe scripts\validate_v7_metrics.py
```

真实输出：

```text
V7 metric validation passed: 154 specs across 30 maps (6 runtime-backed, 24 design-only); 29 solver episodes replayed offline.
```

该校验逐项检查：

1. `MAP-01 … MAP-30` 全部注册；metric_id 唯一、前缀与 `map_id` 一致。
2. 每图至少一条 `primary`、一条 `guardrail`、一条 `diagnostic`。
3. 6 张运行时图满足 44 条已实现指标；24 张设计图满足 110 条 design-only 指标。
4. 30 张卡的 `source_map_spec_hash` / `source_design_hash` 与 `worlds/v4/MAP-XX/map_spec.yaml`、`DESIGN.md` 的 SHA-256 一致。
5. 卡片中出现的每个 `mapXX.*` 指标都在注册表中存在，且每张卡覆盖该图全部已注册指标。
6. 24 张设计图都出现在 `pending-runtime/README.md` 的准入表中。
7. 用 V6 求解器在真实 V4 环境重放 29 个实例，成功终局、指标 id 集合一致、无 `invalid_trace` / `unavailable`，并抽检各图关键值。

### 3.2 静态检查

```powershell
.venv\Scripts\python.exe -m ruff check src\agent_arena\v7 scripts\validate_v7_metrics.py scripts\report_v7_metrics.py tests\test_v7_metrics.py tests\test_v7_map_metrics.py
.venv\Scripts\python.exe -m ruff format --check src\agent_arena\v7 scripts\validate_v7_metrics.py scripts\report_v7_metrics.py tests\test_v7_metrics.py tests\test_v7_map_metrics.py
.venv\Scripts\python.exe -m mypy src\agent_arena\v7
```

真实输出：

```text
All checks passed!
16 files already formatted
Success: no issues found in 12 source files
```

### 3.3 测试

```powershell
.venv\Scripts\python.exe -m pytest tests\test_v7_metrics.py tests\test_v7_map_metrics.py -q
.venv\Scripts\python.exe -m pytest -q
```

真实输出：

```text
.................................................                        [100%]
49 passed in 1.00s

........................................................................ [ 11%]
...
608 passed in 40.30s
```

全量测试必须在未设置 `PYTHONIOENCODING=utf-8` 的 shell 中运行；仓库既有的 `tests/test_flex_v3_seeded.py` 用 `subprocess.run(text=True)` 按本地代码页解码子进程 stderr，强行把子进程输出设为 UTF-8 会让该测试读到 `None`。这是既有测试在 Windows 上的编码假设，与本轮代码无关。

测试分两层：

- `tests/test_v7_metrics.py`：注册表数量、唯一性、三类指标覆盖、五态缺失、零分母 N/A、拒绝码口径、trace 解析错误、`load_trace` 读取。
- `tests/test_v7_map_metrics.py`：29 个 V6 实例真实环境回放；另有 3 个合成 trace 边界用例。

### 3.4 全仓 Ruff 的既有失败

```powershell
.venv\Scripts\python.exe -m ruff check .
```

真实结果：`Found 653 errors`，全部位于已跟踪、本轮未修改的 `worlds/v4/MAP-*/planning/*_audit.py`（E501 行宽、I001 import 排序、B905 `zip` 缺 `strict=`）。`git diff --name-only` 不含这些文件，因此不是 V7 引入的回归。

本轮不批量改写这些冻结设计审计脚本：它们属于 V4 设计证据，修复格式会产生与 V7 无关的大 diff。V7 自身的 Ruff 范围（下节命令）全部通过。若后续要恢复“全仓 Ruff 绿”，应作为独立的历史文件格式整理任务处理，并逐文件确认不改变审计语义。

## 4. 六图离线回放抽检

以下数值全部由 `scripts/validate_v7_metrics.py` 使用的同一套 V6 求解器动作在真实 V4 环境中重放后计算，**不是**模型输出，也不是手工填表。

| 实例 | 条件 | 关键指标 | 值/状态 |
|---|---|---|---|
| `map08_l1_two_candidate` | `hypothesis_table` | `diagnosis_accuracy` / `information_gain_bits` / `peak_core_water` | 1 / 1.0 bit / 4.0 |
| `map08_l2_alt_candidates` | `hypothesis_table` | `diagnosis_accuracy` / `information_gain_bits` | 1 / 1.584963 bit |
| `map16_l3_original` | `constraint_table` | `makespan_gap` / `deadlock` / `legal_reservation_rate` | 0 / 0 / 1.0 |
| `map18_l1_no_fault` | `alert_on` | `service_rate` / `first_reroute_delay` | 1.0 / N/A（无封锁） |
| `map18_l2_alt_segment_r2b2` | `alert_on` | `service_rate` / `first_reroute_delay` / `recovery_delay` | 1.0 / 1 tick / 0 tick |
| `map22_l1_short_return` | `history5_graph_memory` | `return_success` / `path_gap` / `repeated_public_edge_rate` | 1 / 0 / 0.0 |
| `map26_l1_antenna_fault` | `free_diagnosis` | `repair_success` / `recovery_latency` / `repeat_error_rate` | 1 / N/A / N/A |
| `map26_recovery_antenna` | `recovery_full` | `recovery_latency` / `repeat_error_rate` / `spares_remaining` | 6 tick / 0.0 / 1 |
| `map30_l1_two_event_case` | `history5_casebook` | `q4_recall_accuracy` / `evidence_chain_coverage` / `unsupported_accusations` | 1 / 1.0 / 0 |

补充说明：

- `map18_l3_original` 等实例的 `first_reroute_delay` 为 N/A。原因是求解器在封锁生效前已交付全部红线任务，封锁后没有“提交但未成功改线”的时刻表。按预登记规则，这类情形记 N/A，不记 0 或 CENSORED。这正是 V6 已记录的“故障不绑定”现象，V7 只测量，不改规则。
- `map26_l2_spare_rich` 的 `spares_remaining` 为 2，验收脚本对该实例单独覆盖期望值；其余 MAP-26 实例为 1。
- `map18.completed_train_moves` 为 0 是**合法 0**：该指标统计“任务完成后仍移动列车”的违例，求解器没有触发。它不统计正常客运移动。

## 5. 缺失态与边界验证

单测覆盖以下分支：

| 分支 | 用例 | 期望 |
|---|---|---|
| 设计态地图 | `compute_metrics(MAP-17 trace)` | 抛 `NotImplementedError`，不返回 0 |
| 零分母 | `ratio(..., 0, 0)` | `not_applicable`，`value=None` |
| 预算/提供方截尾 | judge `provider_error_limit` | `episode_is_censored=True` |
| 未终局 | `terminal=False` | CENSORED，而非成功 0 |
| 无封锁 | `map18_l1_no_fault` | `first_reroute_delay=not_applicable` |
| 自由诊断 vs 恢复条件 | MAP-26 两组实例 | `recovery_latency` 分别 N/A 与 VALID |
| 合法往返 | 合成 A→B→A→B | `repeated_public_edge_rate=1/3`，A→B 与 B→A 是有向不同边 |
| 空 trace / 缺 header / 缺 decision_index | `parse_trace_rows` | 抛 `TraceFormatError` |

### 5.1 MAP-30 casebook 可见性

MAP-30 的 Observation 在不可见 casebook 的记忆条件下也会序列化 `casebook: []`。若直接把空列表当成“已暴露但未记录”，`evidence_chain_coverage` 会被错算成 0，违反“缺失不是 0”。

本轮在 `map30.py` 中的处理：

1. 若 judge 提供 `judge_state.casebook_visible`，以它为准。
2. 否则若 `condition_id` 不含 `casebook`，视为未暴露 → UNAVAILABLE。
3. 否则视为已暴露；空 casebook 是合法的 0。

对应单测：

- `test_map30_empty_casebook_is_unavailable_without_visibility_flag`
- `test_map30_explicit_visibility_makes_empty_casebook_a_legal_zero`

该规则只影响 V7 只读 extractor，不修改 MAP-30 环境、Observation 或 V6 trace。

## 6. 报告脚本

`scripts/report_v7_metrics.py` 只读已有 episode 目录：

```powershell
.venv\Scripts\python.exe scripts\report_v7_metrics.py <episode-dir> [<episode-dir> ...] [--json out.json]
```

已用一个临时合成 trace 冒烟（不写入 `runs/`）：

```text
MAP-17 | map17_synthetic | synthetic | seed=0
  design_only: 该图的 V7 指标尚未实现 extractor；不生成替代分数。
MAP-22 | map22_l1_short_return | synthetic | seed=0
  map22.return_success                     primary    1
  map22.path_gap                           primary    -4              (BFS 最优 4 moves。)
  ...
processed 2 trace(s): 1 computed, 1 design_only, 0 invalid_trace.
```

该冒烟只验证读取、五态展示、design-only 跳过与 JSON 写出，不构成任何地图结果。正式使用时对 V6 episode 目录逐局复算。

## 7. 未完成与限制

1. **24 张设计图没有运行时。** 它们的 110 条指标只是注册与设计卡，`compute_metrics` 会拒绝计算。接入门槛见 `pending-runtime/README.md`。
2. **没有真实模型 V7 实验。** 本报告不包含任何按 V7 指标比较模型的结论；六图数值来自确定性求解器回放。
3. **没有人工审阅。** 30 张卡的 `review_status` 全部是 `pending_human_review`，V6 的 29 个实例状态未改变。
4. **V6 结果未被改写。** 本轮的 29 次回放是新生成的离线 trace，不覆盖 `runs/v6` 或既有账本。
5. **冲突只登记，不改规则。** `V7-DCR-001 … 012` 仍为 `proposed`；其中 MAP-20 旁路损耗、MAP-20 成功阈值、MAP-25 原因码、MAP-21 动作字段、MAP-27 冲突码等仍需设计侧确认。
6. **MAP-18 的故障在部分实例不绑定。** 指标按预登记规则给出 N/A，不把“没触发”误记为“恢复得 0 tick”。
7. **`report_v7_metrics.py` 不校验账本或成本。** 它只复算 trace 内的指标，不推断 API 费用。
8. **全仓 Ruff 仍因冻结 V4 审计脚本失败。** V7 范围检查通过；653 个既有错误不属于本轮改动，未批量改写。

## 8. 复现

```powershell
# 静态检查
.venv\Scripts\python.exe -m ruff check src\agent_arena\v7 scripts\validate_v7_metrics.py scripts\report_v7_metrics.py tests\test_v7_metrics.py tests\test_v7_map_metrics.py
.venv\Scripts\python.exe -m ruff format --check src\agent_arena\v7 scripts\validate_v7_metrics.py scripts\report_v7_metrics.py tests\test_v7_metrics.py tests\test_v7_map_metrics.py
.venv\Scripts\python.exe -m mypy src\agent_arena\v7

# 注册表 + 30 卡 + 六图离线回放
.venv\Scripts\python.exe scripts\validate_v7_metrics.py

# 测试
.venv\Scripts\python.exe -m pytest tests\test_v7_metrics.py tests\test_v7_map_metrics.py -q
```

全部命令离线执行，不读取 `.env`，不创建 provider，不调用网络。
