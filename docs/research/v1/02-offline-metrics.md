# V1-02 离线重评 45 局（T2）

## 1. 研究问题与假设

- 问题：不限步 45/45 换成固定预算还有多大优势？浪费动作的是探索、回头路、重复读终端，还是终点工具误用？
- 假设：`Success@K` 离线裁剪可估计预算敏感性；`analyze_trace` 的 `no_progress/repeated_*` 可定位瓶颈。
- 前提：只读 T1 已确认 trace，0 次模型调用；离线回放估计 ≠ 告知模型预算后的在线 `Success@K`。

## 2. 代码版本与条件

- 代码 `main@4b3261b` + T1 测试修复；模型 `muse-spark-1.3-contributor`；条件 `memory + H5 + R + P + B=unlimited`；9 配置（3 世界 × 简单/中/难）；去重后 45局（规则见 `00` §2）。
- 工具复用（未新造评测器）：`evaluation/failures.py:123 analyze_trace`、`evaluation/benchmark.py:92 row_from_trace`、CLI `analyze-trace(s)`（`cli.py:330,344`）。

## 3. 引用 trace

- `runs/muse-9maps-*` 51 文件 → 去重 45。5 个 `provider_error` 记 censored（light-easy s0 12步、light-med s2 0步、light-hard s3 356步、ship-hard s1 72步、ship-med s4 56步），无 `step_limit` 截断。
- 最短公开通关下界（规则测试锁定）：飞船简单20步（v1 `react_v*` 路线）/v3 19步/困难21步；灯塔 15/16/20步；深海简单13/中等19/困难21步。`path_efficiency = 下界/实耗`，下界是已知地图最优，不是 Agent 当时已知路径。

## 4. 结果

### 4.1 9 配置统计（verified，去重后）

| 配置 | n | 成功 | 均值 | 中位数 | 最小 | 最大 | 排序 |
|---|---|---|---|---|---|---|---|
| ship-easy | 5 | 5 | 70.4 | 42 | 34 | 133 | 34,37,42,106,133 |
| ship-med | 5 | 5 | 140.8 | 147 | 48 | 279 | 48,76,147,154,279 |
| ship-hard | 5 | 5 | 165.4 | 100 | 63 | 440 | 63,94,100,130,440 |
| light-easy | 5 | 5 | 39.8 | 26 | 23 | 96 | 23,25,26,29,96 |
| light-med | 5 | 5 | 49.4 | 36 | 35 | 87 | 35,35,36,54,87 |
| light-hard | 5 | 5 | 105.8 | 65 | 50 | 261 | 50,53,65,100,261 |
| abyss-easy | 5 | 5 | 26.8 | 30 | 19 | 34 | 19,20,30,31,34 |
| abyss-med | 5 | 5 | 42.2 | 42 | 38 | 46 | 38,41,42,44,46 |
| abyss-hard | 5 | 5 | 83.6 | 53 | 49 | 168 | 49,50,53,98,168 |

核验：提纲 9 个均值 + 飞船中位数 42/147/100 全部 **verified**（去重后成立；`abyss-easy` 依赖取 34 步版，见 `00` §2）。
复核提纲 §0.1：飞船困难中位数（100）低于中等（147）**verified**；“均值单调递增 ≠ 严格显著难度排序”成立——每档 n=5，极值主导均值（如 ship-hard 440、light-hard 261），只报分布不做显著性叙事。

### 4.2 Success@K 离线裁剪（去重 45 集）

| K | 总体 | 飞船15 | 灯塔15 | 深海15 |
|---|---|---|---|---|
| 30 | 7 (15.6%) | 0 (0%) | 4 (26.7%) | 3 (20.0%) |
| 60 | 27 (60.0%) | 4 (26.7%) | 10 (66.7%) | 13 (86.7%) |
| 100 | 36 (80.0%) | 8 (53.3%) | 14 (93.3%) | 14 (93.3%) |
| 150 | 40 (88.9%) | 12 (80.0%) | 14 (93.3%) | 14 (93.3%) |
| 200 | 42 (93.3%) | 13 (86.7%) | 14 (93.3%) | 15 (100%) |

分 9 配置（行=配置，列=K=30/60/100/150/200）：ship-easy 0/3/3/5/5；ship-med 0/1/2/3/4；ship-hard 0/0/3/4/4；light-easy 4/4/5/5/5；light-med 0/4/5/5/5；light-hard 0/2/4/4/4；abyss-easy 3/5/5/5/5；abyss-med 0/5/5/5/5；abyss-hard 0/3/4/4/5。
K=200 仍剩 3 长尾（ship-hard s3 440、ship-med s2 279、light-hard s1 261）。censored 5 件不计分子（censored 率 5/51=9.8%）。
机读 CSV 见 `docs/research/v1/assets/success_at_k.csv`（本轮生成，可重算）。

### 4.3 TOP 3 效率瓶颈（证据强度分级）

**B1. 重复读码 + 读码后空转（强证据，跨世界）**
- `runs/muse-9maps-ship-hard/…_seed-3_ae173aea.json` success/440：`read_terminal:control_terminal` 53 次（`code_read` 53 次，步骤 32…324）；`analyze_trace` 口径 `no_progress=165, new_fact_rate=0.023`；steps 348–353 最长无进展 6 连（4×look + 1×重读 + 1×look）。
- `runs/muse-9maps-ship-med/…_seed-2_1ad88ffc.json` success/279：`read_terminal` 32 次；steps 130–137 无进展 8 连（5×look + 重读 + 2×look）。
- 灯塔对称：`runs/muse-9maps-light-hard/…_seed-1_fa596cf4.json` success/261：`read_terminal:lamp_console` 24 次 + `inspect:harbor_skiff` 24 次，`repeated_inspection=23` 为 9 配置最高之一。

**B2. 终点工具误用 `read_terminal(载具)`（强证据，灯塔为主）**
- `runs/muse-3maps-lightv2/…_seed-0_cd0d1ccd.json` success/56：steps 29/38/48 三次 `read_terminal(harbor_skiff)→rejected/wrong_target`，最后 step 56 才 `use(TIDE-3160→harbor_skiff)→escaped`。全量 144 trace 扫出 68 次同类误用（见 `04`）。
- 根因链：prompt 未区分 terminal/fixture + Runner 对所有 `visible_objects` 枚举 `read_terminal` 候选（含载具）+ 终点 inspect 文本只说“需要码”不说“用 use”。

**B3. 控制室/灯室 look 簇空转（中等证据）**
- 上述三局 look 占比 20–33%（86/440、58/279、36/261），`repeated_navigation` 低而 `no_progress` 高，属“合法但无进展”而非 schema 错误（`invalid_output=0`）。
- 阶段分布（评估用，不进 Agent 输入）：读码前探索占比最高，读码后到逃生延迟最长；精确阶段切分待 `analyze-traces` 全量跑后补 CSV（本轮抽样 3 局，余下 42 局用同一工具可重算）。

### 4.4 路径效率示例

- ship-hard s3：下界 21 / 实耗 440 → 效率 0.048（开销 21×）。abyss-easy 典型：下界 13 / 实耗 19–34 → 效率 0.38–0.68。效率只用于横向比较浪费程度，不代表 Agent 应知最优路。

## 5. 结论边界

- 支持：不限步 100% 在 K=60 时只剩 60%、K=100 时 80%；飞船是预算最敏感世界（K=60 仅 26.7%）；B1–B3 有逐 step 引用。
- 不支持：离线裁剪不能推出“给 60 步预算仍 60%”（模型行为会变）；n=5 不做显著性检验；阶段耗时精确分解需全量 `analyze-traces`（已给命令，见 §6）。

## 6. 测试与可重算

- `tests/test_success_at_k.py`：覆盖 K 边界、缺字段（N/A 非零）、重复文件去重、provider_error censored、截断标记。
- 重算：`python scripts/build_run_register.py --runs-dir runs --results-dir results --output docs/research/v1/assets/run_register.csv`；`$env:PYTHONPATH="src"; python -m agent_arena.cli analyze-traces runs/muse-9maps-ship-hard`（逐配置）。
