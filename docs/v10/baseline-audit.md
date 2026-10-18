# V10 Batch 0：仓库与证据基线审计

- 审计对象 HEAD：`2fa4df2726c486d5064a3db9b3965dc27bbd2898`（`main`，与 `origin/main` 同步）；V10 工作分支 `v10-validity`
- 工作树：只有 `研究提纲/` 下 10 份未跟踪的用户提纲文件（V1–V10），V10 不提交、不修改它们
- 运行时：Python 3.13.3；pydantic 2.13.4、pydantic-settings 2.15.0、openai 1.109.1、typer 0.27.1；pytest 8.4.2、ruff 0.16.3、mypy 1.20.2
- 本机 `uv` 不在 PATH，所有命令使用 `.\.venv\Scripts\python.exe -m ...`
- 复算脚本：`python -m agent_arena.v10.baseline_audit`（只读 V8/V9，输出 `runs/v10/baseline_audit/baseline_audit.json`）

## 1. 质量检查基线

| 命令 | 退出码 | 结果 |
|---|---:|---|
| `python -m pytest -q` | 0 | 888 passed（57.8 s） |
| `python -m mypy src` | 0 | 0 issues（166 files） |
| `python -m ruff check .` | 1 | 全仓 653 errors（628 条 E501、24 条 B905、23 条 I001 等），全部是 V10 之前的既有状态 |
| `python -m ruff check src/agent_arena/v9 src/agent_arena/v10 tests/test_v9_*.py scripts/run_v9_mimo.py` | 0 | V9 scoped 范围与 V10 新代码干净 |

V9 报告的 “Ruff 通过” 只针对 scoped 路径，这与全仓 653 条不矛盾。V10 采用同样口径：新文件必须零错误，全仓数字只记录、不在 V10 中顺手修改旧文件。

## 2. 冻结清单

`docs/v10/freeze-manifest.json` 由 `python -m agent_arena.v10.freeze write` 生成，记录逐文件 sha256 与每个根目录的树 hash。`verify` 子命令在每个 Batch 结束时运行，任何漂移即退出码 1。

| 根目录 | Git 跟踪 | 文件数 | 树 hash |
|---|---|---:|---|
| `runs/v8` | 否（本机） | 599 | `e2ab47f700c98d1e…` |
| `runs/v9` | 否（本机） | 257 | `58c0b2b2ea479a3f…` |
| `docs/v8` | 是 | 42 | `342fa23a7f2305a9…` |
| `docs/v9` | 是 | 67 | `fa7124ded528cb38…` |
| `src/agent_arena/v8` | 是 | 5 | `2dfdf1bb41d6538a…` |
| `src/agent_arena/v9` | 是 | 29 | `43fb62a6d142b889…` |
| `src/agent_arena/worlds/scenario_v8` | 是 | 32 | `2eaef36a9c37b23f…` |
| `src/agent_arena/worlds/scenario_v4` | 是 | 10 | `a593488a6302a4b0…` |
| `worlds/v4` | 是 | 288 | `a6eeeb86e6bdd3b9…` |

另记录 V8 自身冻结：`runs/v8/freeze_manifest.json` 的 `freeze_hash=b174a6f734fbc6b2f1d25c0b6beba40f62431ce0572b281a40c0c3049c32dbb0`（冻结 commit `039e25ce…`）。V10 复算时 30 图的 rule/scenario/source/prompt/metric 五个 hash 与该冻结 **0 处漂移**。

注意：V9 的 `baseline_run`、`metric_checks.run_all` 等入口会直接写入 `runs/v9/`。V10 审计不调用这些写盘入口，只调用其纯函数，并把结果写到 `runs/v10/`，因此冻结树在审计后保持不变（已用 `verify` 确认 9/9 `unchanged`）。

## 3. 原始证据可访问性

`runs/` 被 `.gitignore` 排除，Git 中 **0 个** runs 文件。以下全部是“本机可复算”，换机器只剩 `docs/` 中的摘要与 `docs/v9/run-index.csv`。

### V8 90 局

| 项目 | 结果 |
|---|---|
| `results_90.csv` 行数 | 90（30 图 × replicate 0/1/2，环境 seed 全部为 0） |
| `agent_trace.jsonl` / `judge_metrics.json` / `v8_metrics.json` | 90 / 90 / 90 存在 |
| judge 与注册表不一致 | 0 |
| Trace 头 hash 与冻结不一致 | 0 |
| 当前运行时 hash 与冻结不一致 | 0 |
| 成功 | 17/90 |
| 账本 | 12 个（main、supplement_001…006、5 个 aborted 预跑）；settled 请求 2290、失败 4（均 unknown spend） |
| 全部账本 settled | ¥1.45502656（含 aborted 预跑）；V8 文档的 ¥1.39004496 为不含 aborted 的口径 |
| 正式 90 局费用 | ¥1.27464628（账本按 episode 汇总与 CSV 完全一致，覆盖 90/90） |

### V9 29 条 MiMo 记录

| 项目 | 结果 |
|---|---|
| episode 目录 | 29，均有 trace/judge/v9_metrics/manifest |
| 有效 / provider 中断 | 27 / 2（均为 MAP-12 的 `InternalServerError` → `unknown_provider_spend`） |
| 有效局成功 | 7（MAP-07 v9_fixed、MAP-10 ×2、MAP-11 ×2、MAP-15、MAP-26 v9_fixed） |
| 环境 seed | 28 条 seed=0，1 条 seed=5（MAP-06） |
| 主账本 | settled ¥0.08963340，150 请求，1 次 unknown spend，`experiment_closed=UNKNOWN_PROVIDER_SPEND` |
| supplement_001 | settled ¥0.04993204，78 请求，1 次 unknown spend，同样封账 |
| supplement_002 | settled ¥0.20093340，284 请求，0 失败，未封账（预登记局已全部跑完） |
| 合计 settled | ¥0.34049884（与 V9 报告一致） |

V8/V9 费用均不计入 V10 的 ¥10 上限；V10 只统计 `runs/v10/` 下的账本。

## 4. 离线基线与独立复算（重跑）

| 项目 | V10 重跑 | 与 V9 存档比较 |
|---|---|---|
| Oracle | 55/55 成功 | 30/30 图的完整记录与 `runs/v9/baselines/MAP-XX.json` 逐字节等价 |
| legal_random（20 policy seed/图，环境 seed 0） | 11/600 成功（MAP-15 5/20、MAP-21 6/20） | 同上 |
| 公开启发式 | 30/30 成功 | 同上 |
| 消融 | 见下表 | 同上 |
| 独立指标复算 | 120 checks，120 matched，0 mismatched，0 not_computable | 与 `runs/v9/metric_checks/summary.json` 完全一致 |

消融在 seed 0 上 **仍然通关** 的地图（构念旁路或 OPTIONAL 的直接证据）：

MAP-04 `detour_shortcut`/`no_phase_wait`、MAP-06 `shortcut`/`forecast_trusting`、MAP-08 `no_hypothesis`、MAP-09 `skip_pump`、MAP-13 `no_direction_nail`、MAP-14 `blind_two_submissions`/`no_compare`、MAP-15 `no_probe`/`no_rule_transfer`、MAP-18 `ignore_windows`、MAP-19 `no_lag_load_curtailment`、MAP-21 `shortcut_direct_evac`、MAP-22 `no_memory_write`、MAP-23 `no_scout`、MAP-26 `no_diagnosis`。

MAP-07、MAP-27 在 V9 没有登记消融。

## 5. 环境 Seed 现状（V10 的主要缺口）

V8/V9 的 Oracle 几乎全部在 seed 0（只有 MAP-11 有 seed 7 一条）。对 30 图逐一枚举 seed 0–9，比较初始 `judge_state` 与 Observation：

| 类别 | 地图 | 说明 |
|---|---|---|
| seed 完全无效（实例相同） | 01、02、03、04、05、07、09、10、12、13、15、17、19、20、25、27、28、29 | `_reset_state` 中 `del seed`；三个 “seed” 只是同一实例的重复 |
| 只改变一个隐藏量 | 06（seed 5 起风暴参数不同，0–4 相同）、21（`eruption_tick`，0–9 中只有 3 种）、23（`true_entrance`）、24（`phase_offset`） | 有参数化但覆盖很窄；MAP-06 seed 0/1/2 完全相同 |
| 多隐藏量 | 11（风暴掩码 + 侦察信号）、14（锁型配置 + 真祭司） | 已有实质变化 |
| V4 适配图只接受 3 个标签 | 08、16、18、22、26、30 | seed 0–2 合法、3–9 抛 `ValueError`；状态差异只在 `judge.seed` 字段（MAP-08 除外，0–9 都接受但状态同样只差 seed 字段） |

结论：V8 的 “三 replicate” 与 V9 的 seed 0 证据都不是多环境 seed 证据。V10 必须为 18 张 “seed 无效” 图和 6 张 V4 适配图实现真正的参数化或预登记手工变体（spec §9.1），并为每个 seed 计算独立 `scenario_hash`。

## 6. 本 Batch 的 Gate 判定

- 证据索引：完成（本文件 + `runs/v10/baseline_audit/baseline_audit.json`）。
- 冻结清单：完成（`docs/v10/freeze-manifest.json`，9 个根目录）。
- 优先级矩阵：完成（`docs/v10/map-status-matrix.csv/.md`，起点完全继承 V9）。
- 原始 Trace：V8 90/90、V9 29/29 本机存在；可复算边界是“仅本机”，已明确记录。

Gate 通过。
