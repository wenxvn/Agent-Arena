# V10：30 图核心机制重构、难度校准与多 Seed 有效性验证

- 规格：`研究提纲/V10：30图核心机制重构、难度校准与多Seed有效性验证.md`（用户文件，未纳入 Git）
- 起始 HEAD：`2fa4df2726c486d5064a3db9b3965dc27bbd2898`（main）；工作分支 `v10-validity`
- 原则：V8/V9 只读（`docs/v10/freeze-manifest.json` 守卫）；V10 独立 runtime、指标、账本与 run_id；不按通关率改规则；`n=3` 只作描述；全部 `agent_reviewed`

## 进度

| Batch | 内容 | 状态 | commit | 费用 |
|---|---|---|---|---|
| 0 | 基线审计、冻结清单、状态矩阵、决策登记 | 完成 | 见 git log `feat(v10): batch 0` | ¥0 |
| 1 | MAP-03 / MAP-18：DCR-V10-01/02，V10 运行时、Oracle、启发式、消融、6/5 seed | 离线 Gate 通过；状态 `NEEDS_MORE_EVIDENCE`（待指标复算与 MiMo） | 见 git log `feat(v10): batch 1` | ¥0 |
| 2 | MAP-06 / MAP-15 / MAP-21：DCR-V10-03/04/05，10/10/10 seed | 离线 Gate 通过；状态 `NEEDS_MORE_EVIDENCE`（待指标复算与 MiMo） | 见 git log `feat(v10): batch 2` | ¥0 |
| 3 | 古堡 MAP-28 / 29 / 30：DCR-V10-06/07，4/4/3 案卷 | 离线 Gate 通过；状态 `NEEDS_MORE_EVIDENCE`（待指标复算与 MiMo） | 见 git log `feat(v10): batch 3` | ¥0 |
| 4 | 其余 NEEDS_REDESIGN：MAP-04（V10-08）、MAP-14（09）、MAP-19（10）、MAP-20（11）、MAP-22（12）、MAP-23（13）、MAP-24（14）——**全部完成** | 离线 Gate 通过；状态 `NEEDS_MORE_EVIDENCE` | 见 git log `feat(v10): batch 4` | ¥0 |
| 5 | NEEDS_MORE_EVIDENCE 与 VALIDATED 复核：MAP-08（V10-16）、MAP-13（15）、MAP-26（17）完成；07/09/10/11/12 与 7 张 VALIDATED 未开始 | 进行中 | 见 git log `feat(v10): batch 5` | ¥0 |
| 6 | 指标治理 | 未开始 | | |
| 7 | 多 seed 定标 | 未开始 | | |
| 8 | 有界 MiMo | 未开始 | | |
| 9 | 最终报告 | 未开始 | | |

## 下一会话续跑点

- 已验收 Gate：Batch 0、1、2、3、4。
- 从 **Batch 5** 继续：MAP-07 / 09 / 10 / 11 / 12 / 26 的接口与多 seed 复核，以及 01/02/05/16/17/25/27 的防回归。已完成 MAP-08（DCR-V10-16）与 MAP-13（DCR-V10-15）。每图按已建立模式落地 —— `v10/runtime/mapXX.py` → `v10/baselines/mapXX.py` → `tests/test_v10_batch5.py` → `docs/v10/dcr/DCR-V10-XX.md` → `evidence_state.DECISIONS` → `agent_arena.v10.status` 重算。
- 已完成的 Batch 4 图：MAP-04（DCR-V10-08）、MAP-14（09）、MAP-19（10）、MAP-20（11）、MAP-22（12）、MAP-23（13）、MAP-24（14）。
- 已知的逐图修复方向见 `decision-register.md` §2（MAP-14/19/20/22/23/24 行）。
- 不要重复 V8/V9 的冻结文件；每批结束时必须跑 `freeze verify`、scoped ruff、`mypy src`、`pytest`。
- Batch 8 之前必须先写 `docs/v10/mimo-preregistration.json` 并通过 ¥10 全局账本门禁；**本会话未发生任何付费调用**。

## 文件

| 文件 | 内容 |
|---|---|
| `baseline-audit.md` | Batch 0：HEAD、质量基线、冻结、V8/V9 证据可达性、seed 现状 |
| `decision-register.md` | 规则变更 vs 接口/指标修复的逐图登记 |
| `freeze-manifest.json` | V8/V9 逐文件 sha256 与树 hash |
| `map-status-matrix.csv/.md/.json` | 30 图状态矩阵（字段见提纲 §2.4） |
| `dcr/DCR-V10-XX.md` | V10 规则变更记录（新旧 hash 并列、对照与反例测试） |

## 代码

| 路径 | 内容 |
|---|---|
| `src/agent_arena/v10/runtime/` | `base.py` V10 地图协议；`catalog.py` 目录（V10 优先、V8 回退）与 hash；`mapXX.py` 逐图新规则 |
| `src/agent_arena/v10/baselines/` | `runner.py` 执行器（环境 seed / policy seed 分离、5 条 history 窗口）；`mapXX.py` Oracle、启发式、消融；`suite.py` 多 seed 套件 |
| `src/agent_arena/v10/metrics/schema.py` | `metric_schema_version=v10`、五态与优先级 |
| `src/agent_arena/v10/evidence_state.py` | 逐图裁定，驱动状态矩阵 |

## 复现

```powershell
.\.venv\Scripts\python.exe -m agent_arena.v10.freeze verify      # 冻结校验
.\.venv\Scripts\python.exe -m agent_arena.v10.baseline_audit     # V8/V9 只读复算
.\.venv\Scripts\python.exe -m agent_arena.v10.baselines.suite    # V10 多 seed 基线 → runs/v10/baselines
.\.venv\Scripts\python.exe -m agent_arena.v10.status             # 生成状态矩阵
.\.venv\Scripts\python.exe -m pytest tests/test_v10_*.py -q
```

`runs/v10/` 与 `runs/v8`、`runs/v9` 一样不纳入 Git；文档中引用的数字都可由上述命令在本机复算。
