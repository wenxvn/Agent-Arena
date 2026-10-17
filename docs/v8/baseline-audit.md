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

### 3.3 正式运行前的一次预跑与作废

在第一次启动 90 局时，Runner 的 wall-clock 安全上限是 10 分钟。MAP-03 的最难轨迹在
慢请求下会超过该上限，导致“决策预算尚未用完就被截尾”。这不是预登记的能力约束，
而是运行器安全参数，因此：

- 已产生的 5 个正式 episode 与部分 MAP-03 轨迹全部移入
  `runs/v8/aborted/pre_timeout_001/`，**不计入正式 90 局**；
- 旧账本一并封存，费用约 ¥0.02，不混入新账本；
- 将安全上限改为 30 分钟（正式约束仍是决策预算与 `step_limit`），重新冻结后从零开始；
- 该次预跑的完整 trace、账本与旧 freeze manifest 保留，供审计。

### 3.4 设计文件与 V7 卡片

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
