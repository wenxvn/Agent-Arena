# V8 基线审计

审计日期：2026-10-17。执行前 HEAD：`e81d5dc`（V7 最新已提交状态）。

## 1. 仓库事实

- 当前分支 `main`，V8 开始前工作区只有 7 份未跟踪的研究提纲文件；V8 代码、脚本、测试与 `docs/v8/` 均为新建。
- `runs/` 与 `results/` 被 `.gitignore` 排除，因此 V8 账本、episode 与注册表只存在于本机，不进入 Git。
- 运行环境：Windows，Python 3.13（`.venv`）。`uv` 不在 PATH，统一使用 `.\\.venv\\Scripts\\python.exe`。
- V8 没有修改 V2/V4/V5/V6/V7 的 trace、账本、注册或已关闭实验；所有新运行写入独立的 `runs/v8/`。

## 2. 对 V7 声明的核查

| V7 声明 | 核查结果 |
|---|---|
| 30 张独立指标卡、154 条 MetricSpec | 确认：`specs_for()` 合计 154 条（primary 64、diagnostic 51、guardrail 39） |
| 6 图 44 条指标 implemented，24 图 110 条 design-only | 确认：V7 只有 MAP-08/16/18/22/26/30 有 extractor；其余 24 图 `compute_metrics` 抛 `NotImplementedError` |
| 649 pytest passed | V8 开始前基线按当前仓库复跑为 649 条；新增 V8 测试后为 854 条全部通过 |
| V7 Pilot-001R 12/12 真实 MiMo 局 | 只读确认，6/12 success；不计入 V8 正式 90 局 |
| 12 项 DCR proposed | 确认：`docs/v7/design-change-requests.md`；V8 逐条裁决见 `dcr-resolution.md` |

## 3. V8 运行时审计

### 3.1 新建隔离包

- `src/agent_arena/worlds/scenario_v8/`：30 图 catalog、公共生命周期、严格 `V8Action` / `V8Observation`、Oracle 回放、6 图 V4 适配器、24 图独立运行时。
- `src/agent_arena/v8/`：五态指标投影、¥10 append-only 账本、公开 prompt、90 局 runner。
- `scripts/`：单图自检、离线统一门禁、冻结、正式运行、汇总、报告生成。
- `tests/test_v8_*.py`：203 条 V8 测试。

### 3.2 发现并修复的基线差异

1. **六个 V4 适配图最初用 `scenario_v4.catalog.create_environment(seed=0)` 构建**，其默认实例与 V6 冻结场景并不总是同一套故障参数。审计中发现 MAP-18 的默认实例在 tick 5 关闭 R2–R3，而 V6 `map18_l3_original` 的故障窗口是 (5,10)，导致 V7 已发布的手算轨迹无法复现。修复：适配器改为 `v6.catalog.build_environment(get_scene(instance_id), condition, ...)`，直接绑定冻结场景。修复后 6 图的 V7 手算值全部复现。
2. **MAP-01/02/03 在 V8 首版没有模块级手算 fixture**，只依赖 V4 Oracle 文件。已补充 2 条/图的手算 fixture，并全部通过真实 `step` 回放。
3. **六张适配图各只有 1 条手算 fixture**。已按 `tests/test_v7_hand_traces.py` 的已发布值补充第二条，覆盖成功/失败或边界。
4. **Runner 最初只统计解析失败，不统计环境形状拒绝**，导致 `INVALID_ACTION_SCHEMA` 不计入 `invalid_action_count` 与连续 schema 故障。已修复并加测试。

### 3.3 正式运行前的五次预跑与作废

**预跑 A（pre_timeout_001）**：Runner 的 wall-clock 安全上限最初是 10 分钟。MAP-03 的
最难轨迹在慢请求下会超过该上限，导致“决策预算尚未用完就被截尾”。这不是预登记的
能力约束，而是运行器安全参数，因此：

- 已产生的 5 个正式 episode 与部分 MAP-03 轨迹全部移入
  `runs/v8/aborted/pre_timeout_001/`，**不计入正式 90 局**；
- 旧账本一并封存，费用约 ¥0.02，不混入新账本；
- 将安全上限改为 30 分钟（正式约束仍是决策预算与 `step_limit`），重新冻结后从零开始；
- 该次预跑的完整 trace、账本与旧 freeze manifest 保留，供审计。

**预跑 B（pre_vocab_001）**：重跑后 MAP-01 三局都在 4 个决策内失败，且从未尝试
`interact`。审计发现运行时没有公开交互目标的字符串词表：V4 `map_spec.yaml` 把
`visible_objects` 列为公开字段，但 V8 的 `PUBLIC_FIELDS` 只有状态量；模型只能猜
`oxygen_relay`、`start_support` 等目标名。按提纲“接口不明不可作为正式结果”，这属于
接口缺陷，不是能力失败。

- 已产生的 6 个 episode 与账本移入 `runs/v8/aborted/pre_vocab_001/`；
- 在 `prompts.py` 增加**公开静态交互词表**（只列可尝试的字符串，不表示当前位置可执行
  或顺序正确，不泄露隐藏真值），覆盖 MAP-01–06 这类需要 `target/choice` 的地图；
- 规则模块没有改动，`rule_hash` 不变；`prompt_hash` 对 MAP-01–06 变化；
- 重新冻结后从零开始正式 90 局。

**预跑 C（pre_vocab_full_001）**：只覆盖 01–06 的词表仍不足。审计发现 MAP-14/15/17/
23/25/27/28/29/30 也存在“动作字符串不在 Observation 中”的同类问题（如
`A_sun_wheel`、`OPEN_ACCOUNT`、`array_fuse_B`、`EVENT_1_HANDOFF`）。因此：

- 已产生的 episode 与账本移入 `runs/v8/aborted/pre_vocab_full_001/`；
- 将公开词表扩展到全部需要字符串枚举/操作名的 19 张图；仍只列可尝试的名字与值域，
  不列隐藏真值、正确顺序或正确答案；
- 规则模块仍未改动，`rule_hash` 不变；`prompt_hash` 变化；
- 重新冻结后开始正式 90 局。

**预跑 D（pre_map01_rule_001）**：补齐词表后 MAP-01 仍在第 4 tick 失败，轨迹显示
模型从 B→H→P→H→P 探索，从未尝试供氧。审计发现 MAP-01 的公开 `goal` 只说“恢复供氧”，
没有公开“连续断供超过 3 tick 立即失败”的硬规则；Agent 无法从 `oxygen_reserve=18`
推断出真实阈值。按“接口不明不可作为正式结果”，这不是能力失败。

- 已产生的 episode 与账本移入 `runs/v8/aborted/pre_map01_rule_001/`；
- 在 MAP-01 的公开词表中加入该硬规则（不暴露私有计数器，只公开规则文本）；
- 规则模块仍未改动；`prompt_hash` 变化，重新冻结后开始正式 90 局。

**预跑 E（pre_location_001）**：MAP-01 仍在第 4 tick 失败，轨迹为 B→H→O→H→O：
模型知道要恢复供氧，但不知道 `oxygen_relay` 在 B/H，而不是供氧舱 O。V4 设计的
`public_observation_fields` 含 `visible_objects`，V8 运行时没有实现该字段。

- 已产生的 episode 与账本移入 `runs/v8/aborted/pre_location_001/`；
- 在 MAP-01–06 的公开词表中加入“位置对象”行，说明每个可交互对象出现在哪些位置；
  这是公开世界知识，不包含隐藏真值或正确顺序；
- 规则模块仍未改动；`prompt_hash` 变化，重新冻结后开始正式 90 局。

### 3.4 正式运行中的 provider 中断与版本修复

正式 90 局不是一次不中断的批处理；每次停机都保留原账本与 trace，补跑使用独立账本和
新 run_id。当前记录：

| 账本 | 正式局 | 结束原因 | 处理 |
|---|---|---|---|
| `runs/v8/ledger.jsonl` | 38 | MAP-13 R2 `InternalServerError` → unknown spend | 封账；MAP-13 R2 由 supplement_001 补跑 |
| `runs/v8/supplement_001/ledger.jsonl` | 4 | MAP-15 R0 `InternalServerError` → unknown spend | 封账；剩余局由 supplement_002 补跑 |
| `runs/v8/supplement_002/ledger.jsonl` | 24 | MAP-22 连续 3 局 `schema_fault_limit` | 审计后封账；MAP-22 旧三局标 superseded |
| `runs/v8/supplement_003/ledger.jsonl` | 14 | MAP-26 R2 `InternalServerError` → unknown spend | 封账；剩余局由 supplement_004 补跑 |
| `runs/v8/supplement_004/ledger.jsonl` | 4 | MAP-28 R0 `InternalServerError` → unknown spend | 封账；剩余局由 supplement_005 补跑 |
| `runs/v8/supplement_005/ledger.jsonl` | 9 | 正常完成 → 90/90 | 完成；MAP-12 预算修复由 supplement_006 重跑 |
| `runs/v8/supplement_006/ledger.jsonl` | 3 | MAP-12 预算修正重跑 | 完成 |

**MAP-22 版本修复**：三局 schema 失败的原因是 `write_memory(facts)` 的
`node_page` / `traversed_edge_page` 字段结构没有公开，模型反复提交了结构相似但字段
不合法的对象。修复只在公开 prompt 中加入事实 schema，规则模块未改；MAP-22 的
`prompt_hash` 变化，其他 29 图的 `scenario_hash / rule_hash / prompt_hash /
metric_schema_hash` 不变。旧三局保留但标记 `SUPERSEDED.json`，不计入正式结果。
这是提纲允许的“三局都因无效 schema 失败 → 修复后重新冻结重跑”，不是静默改规则。

**MAP-12 预算修复**：MAP-12 的规则是 30 天 × 每日 2 个劳动槽，至少需要 60 个动作；
预登记按“困难 46”给出的预算使完成在算术上不可行。三局 `decision_budget_reached` 是预算
设计错误，不是能力失败。已将 MAP-12 的冻结 `decision_budget` 修正为 60（公开 prompt 中
的预算数字随之变化，`prompt_hash` 变化），旧三局标 `SUPERSEDED.json`，在
supplement_006 中以 60 预算重跑。其他 29 图预算不变。

### 3.5 设计文件与 V7 卡片

- 30 图的 `worlds/v4/MAP-XX/{DESIGN.md,map_spec.yaml,evidence_or_rules.yaml,oracle_trace.jsonl,acceptance.md,failure_traces/cases.yaml}` 全部存在。
- V7 的 30 张指标卡已由用户于 2026-10-17 复核为 `human_approved`；V8 沿用其 `MetricSpec`，没有新增或改名。
- V7 卡片中的已知笔误与边界在 `dcr-resolution.md` 中登记；不以总字段覆盖逐项未决问题。

## 4. 工具与质量门

| 项目 | 结果 |
|---|---|
| `pytest` 全量 | 854 passed |
| 作用域 Ruff | 通过（V8 源码、脚本、测试、`docs/v8` 生成物不参与 lint） |
| `mypy src` | 137 files，0 issues |
| 全仓 Ruff | 676 条历史问题，集中在冻结的 `worlds/v4` 资料与既有脚本；本次未大范围重写冻结资料，单独报告 |
| 单图自检 | 30/30 `MAP-XX: OK` |
| 离线统一门禁 | 30/30 通过，详见 `offline-validation.md` |

## 5. 结论

V8 的基线是可信的：V7 的指标、场景与历史实验未被改写；V8 在独立包内实现了 30 图规则、154 条指标的运行时来源和与历史隔离的账本。发现的适配器实例差异在冻结前修复并回归，未进入正式 90 局。
