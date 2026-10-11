# V1-00 基线审计与运行台账（T1 前置）

> 代码版本：`main@4b3261b`。状态：`verified`=本轮读代码/文件证实，`reported`=文档声称未重验，`not verifiable`=缺源。
> 本文件登记预算与实验 ID；任何补跑先在此登记，不得修改已冻结实验定义追逐成功率。

## 1. 基线核对（verified）

- HEAD `4b3261b` 与提纲基准一致（`git log --oneline -5` 首行）。
- `tests/test_phase_tracker.py:3` 未使用 `LIGHTHOUSE_MILESTONES` 导入触发 Ruff F401，导致 CI `quality` 在 ruff 步失败，后续 mypy/pytest 未执行。已修复（见 `01-ci-and-provenance.md`）。
- 本机：Python 3.11.9 + `PYTHONPATH=src` 跑 `pytest` 159 passed；`uv`/`ruff`/`mypy` 均未安装（`python -m ruff/mypy` 无模块），属 T1 遗留阻塞，只能本地 pytest + 待 CI 全绿。
- `runs/` 下 `muse-9maps-*` 共 **51 个 trace 文件**（`verified`，`glob` 计数），不是 45。`results/` 下 `muse-memory-s60*` 等消融 benchmark 齐全（见 §3）。

## 2. 去重台账：51 文件 → 45 组合

去重规则（T2 采用，与提纲 §0.2 一致）：

1. 同一 `(world, world_version, seed)` 有 2 文件时：若一 `provider_error` 一 `success`，丢前者留后者（网关重试）。
2. `abyss-easy seed-2` 双 `success`（21 步 `712cc1d5` vs 34 步 `9535945d`）：保留 34 步版才对上提纲均值 26.8；规则注明“同 seed 双 success 取先到（`9535945d`）”，否则均值变 24.2。
3. 5 个 `provider_error` 记 `censored`，不计入成功率分子分母，单独披露。

| # | world+seed | 丢弃文件（outcome/exec） | 保留文件（outcome/exec） |
|---|---|---|---|
| D1 | abyss-easy seed-2 | `…/muse-9maps-abyss-easy/…_seed-2_712cc1d5.json` success/21 | `…_seed-2_9535945d.json` success/34 |
| D2 | light-easy seed-0 | `…/muse-9maps-light-easy/…_seed-0_eab47c55.json` provider_error/12 | `…_seed-0_97210f20.json` success/26 |
| D3 | light-hard seed-3 | `…/muse-9maps-light-hard/…_seed-3_f888b9a0.json` provider_error/356 | `…_seed-3_214c0017.json` success/100 |
| D4 | light-med seed-2 | `…/muse-9maps-light-med/…_seed-2_e6c75f70.json` provider_error/0 | `…_seed-2_c216228c.json` success/36 |
| D5 | ship-hard seed-1 | `…/muse-9maps-ship-hard/…_seed-1_0c8ed719.json` provider_error/72 | `…_seed-1_526fa7e9.json` success/94 |
| D6 | ship-med seed-4 | `…/muse-9maps-ship-med/…_seed-4_e88e2da4.json` provider_error/56 | `…_seed-4_a2010b20.json` success/48 |

结论（verified）：原始 **46 success + 5 provider_error = 51 文件**；去重后 **45 组合全 success**。
提纲“45 成功 trace + 6 次网关异常”应修正为“46 success + 5 provider_error，去重后 45 组合”（D1 为双 success 而非网关错误）。
按所有实际尝试计算的端到端成功率：`46/51 = 90.2%`（`verified`）；去重后 `45/45 = 100%` 仅在“每组合至少一次成功”口径下成立。

## 3. 已有实验去重索引（verified，读 benchmark 头）

| 实验 | world/预算 | H/R/P | 结果 | 可比性 |
|---|---|---|---|---|
| `results/muse-memory-s60` | 飞船v1/B60 | 000 | 0/5 | C000 基准 |
| `results/muse-memory-s60-h5` | 飞船v1/B60 | 100 | 0/5 | C100 |
| `results/muse-memory-s60-h5r` | 飞船v1/B60 | 110 | 0/5 | C110 |
| `results/muse-memory-s60-p` | 飞船v1/B60 | 001 | 0/5 | C001 |
| `results/muse-memory-s60-h5p` | 飞船v1/B60 | 101 | 1/5 | C101 |
| `results/muse-memory-s60-h5rp` | 飞船v1/B60 | 111 | 3/5 | C111 主结果 |
| `results/muse-memory-s60-h5rp-s59` | 飞船v1/B60 seeds5-9 | 111 | 2/5 | 复验，不可与 0-4 合并 |
| `results/muse-memory-s30-h5rp` | 飞船v1/B30 | 111 | 0/5（含1 provider_error） | 预算不同，不可比 |
| `results/muse-memory-autonomous` | 飞船v1/B30 | 000 | 0/5 | 自主 C000/B30 |
| `results/muse-react-autonomous` | 飞船v1/B30 | 000 | 0/5 | React C000/B30 |
| `results/muse-planning-autonomous`（`e0302c3f`） | 飞船v1/B30 | 000 | 0/4 完成+1中断 | 与 memory-autonomous 可比 |
| `results/muse-planning-autonomous2` | 飞船v1/B30 | 000 | 0/4 完成+1中断 | 同上 |
| `results/muse-planning-autonomous`（`1a95834e`） | — | — | 5×provider_error/0步 | 作废批次，不得计分母 |
| `results/muse-lighthouse-h5r` | 灯塔v1/B60 | 110 | 0/5 | 跨图，不可并入飞船矩阵 |
| `results/muse-lighthouse-h5rp-s14` | 灯塔v1/B60 seeds1-4 | 111 | 4/4 | 干净复跑，seeds 不对齐 |
| `results/muse-shipv3-unlimited-s24` | 飞船v3/B0 | 111 | 3/3 | 地图+预算双变，不可比 |
| `runs/muse-9maps-*`（51文件） | 9配置/B0 | 111 | 去重后 45/45 | 主成绩，见 §2 |

缺失格：`C010`（R-only）、`C011`（R+P 无 H）无数据；`React-C111`（M 消融）无数据。见 `03-factor-ablation.md`。

## 4. 缺失项与尝试分母

- 原始失败数据缺失：5 个 `provider_error` trace 齐全，但提纲“6 次网关异常”中的第 6 次无对应文件（D1 为双 success）。只陈述能验证的下界，不擅自声称总计恰好 51 次尝试之外的数字。
- 来源缺失标记：`input/output tokens` 在 9maps trace 中以 `StepTrace.input_tokens/output_tokens` 存在，可聚合；`results/` 旧 benchmark 的 prompt hash 见 `condition_json`，缺失则填 N/A（不填零）。
- 运行台账再生：`scripts/build_run_register.py`（T1 新增）从 `runs/` + `results/*/benchmark_*.json` 生成机读 CSV，列含 `experiment_id,episode_id,world,world_version,definition_hash,agent,provider,model,prompt,recent_history,stuck_recovery,phase_context,step_limit,seed,outcome,action_count,input_tokens,output_tokens,error_type`。来源缺失记 `unavailable`。

## 5. 下一步最小必要任务

1. T1：修 CI + provenance 报告（`01`），冻结本台账为后续唯一分母。
2. T2：离线重算（`02`），0 次新 LLM 调用。
3. T3 缺口 `C011`（+可选 `React-C111`）在登记预算后补测；此前不得把 30 步基线与 unlimited 成功率相减当架构收益。

## 6. 在线补测冻结登记（2026-10-11，用户已批准在线对照）

公共冻结条件：`provider=openai, model=muse-spark-1.3-contributor`（`verify-model` 通过），
`world=spaceship-escape/world_version=spaceship-escape-v2-zh`（飞船 v1），
`--autonomous` 基座（通用 prompt，hints/candidates/guard 全关），temperature/reasoning 与既有 s60 矩阵一致。
停止条件：单局 `provider_error` 中断单列重跑一次仍失败则记 censored；连续 2 局网关限流则暂停并记录。

| 实验 ID | 条件 | 预算/规模 | 预期调用 | 状态 |
|---|---|---|---|---|
| EXP-C011-pilot | memory, H0 R1 P1, B60, seed 0（1 局） | ≤60 动作 | ≤70 请求 | done：step_limit |
| EXP-C011 | memory, H0 R1 P1, B60, seeds 0–4（5 局 +1 重跑） | 5×60 | ≤350 请求 | done：**0/5**（seed1 首跑 provider_error→重跑仍 step_limit） |
| EXP-ReactC111-pilot | react, H5 R1 P1, B60, seed 0（1 局） | ≤60 | ≤70 | done：step_limit（遗忘授权码，见 03 §9） |
| EXP-ReactC111 | react, H5 R1 P1, B60, seeds 0–4（5 局 +1 重跑） | 5×60 | ≤350 | done：**0/4 完成**（seed4 两次 provider_error 记 censored） |
| EXP-E1-pilot | memory+E1, H5 R1 P1, B60, seed 0（1 局） | ≤60 | ≤70 | done：success/44 步（见 04 §5） |
| EXP-E1 | memory+E1, H5 R1 P1, B60, seeds 0–4（5 局） | 5×60 | ≤350 | done：**5/5**（均值 30.6，零误用；C111 3/5 均值 47.2） |
| EXP-Pctx-pilot | planning, H5 R1 P1, B60, seed 0（1 局） | ≤60×2 调用 | ≤140 | done：step_limit（见 05 §7） |
| EXP-Pctx | planning, H5 R1 P1, B60, seeds 0–4（5 局 +2 基础设施中断 +1 重跑） | 5×60 | ≤700 | done：**0/4 完成**（seed4 censored；不提议 Planning v2） |

对照声明：EXP-C011/ ReactC111 /E1/Pctx 均与既有 `muse-memory-s60*` 同模型同 world 同 B60；
与 B30 自主基线比较时必须声明预算差。不得修改已冻结实验定义追逐成功率。
