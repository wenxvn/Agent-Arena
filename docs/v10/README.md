# V10：30 图核心机制重构、难度校准与多 Seed 有效性验证

- 规格：`研究提纲/V10：30图核心机制重构、难度校准与多Seed有效性验证.md`（用户文件，未纳入 Git）
- 起始 HEAD：`2fa4df2726c486d5064a3db9b3965dc27bbd2898`（main）；工作分支 `v10-validity`
- 原则：V8/V9 只读（`docs/v10/freeze-manifest.json` 守卫）；V10 独立 runtime、指标、账本与 run_id；不按通关率改规则；`n=3` 只作描述；全部 `agent_reviewed`
- 结论口径：**`VALIDATED` 表示“测得住”（8 项 Gate 全过），不表示“MiMo 能通关”**；真实模型成功率另见 `mimo-results.md`

## 进度

| Batch | 内容 | 状态 | commit | 费用 |
|---|---|---|---|---|
| 0 | 基线审计、冻结清单、状态矩阵、决策登记 | 完成 | 见 git log `feat(v10): batch 0` | ¥0 |
| 1 | MAP-03 / MAP-18：DCR-V10-01/02，V10 运行时、Oracle、启发式、消融、6/5 seed | 离线 Gate 通过 | 见 git log `feat(v10): batch 1` | ¥0 |
| 2 | MAP-06 / MAP-15 / MAP-21：DCR-V10-03/04/05，10/10/10 seed | 离线 Gate 通过 | 见 git log `feat(v10): batch 2` | ¥0 |
| 3 | 古堡 MAP-28 / 29 / 30：DCR-V10-06/07，4/4/3 案卷 | 离线 Gate 通过 | 见 git log `feat(v10): batch 3` | ¥0 |
| 4 | 其余 NEEDS_REDESIGN：MAP-04（V10-08）、MAP-14（09）、MAP-19（10）、MAP-20（11）、MAP-22（12）、MAP-23（13）、MAP-24（14） | 离线 Gate 通过 | 见 git log `feat(v10): batch 4` | ¥0 |
| 5 | NEEDS_MORE_EVIDENCE 与 VALIDATED 复核：8 张接口/证据图 + 7 张 VALIDATED 防回归 | 完成（7 张记 3-seed 缺口） | 见 git log `feat(v10): batch 5` | ¥0 |
| 6 | 指标治理：154 枚举 + 128 项 V10 规格 + 20 项缺陷结论 + 五态核对 | 完成 | 见 git log `feat(v10): batch 6` | ¥0 |
| 7 | 多 seed 难度定标：`difficulty.py` + `difficulty-calibration.md` | 完成（Batch 8 后已加入 MiMo 列） | 见 git log `feat(v10): batch 7` | ¥0 |
| 8 | 有界 MiMo 复测：27 张 V10 原生图 × 3 环境 seed + 中断补跑 + 接口修复重跑 + MAP-05/02/27/01 原生首测 | ✅ 完成（107 局记录：101 有效 + 6 中断保留） | 见 git log `feat(v10): batch 8/9` | **CNY 2.07** |
| 9 | 最终验收：8 Gate 判定、30 张逐图审计卡、指标独立复核、trace 级归因、成本审计、最终报告 | ✅ 完成 | 见 git log `feat(v10): batch 8/9` | ¥0 |

## 结论速览

- **30 图状态**：**30 `VALIDATED`**（27 张 V10 原生图 8 项 Gate 全过 + 3 张 V8 回退图沿用 V9 并记
  3-seed 缺口）；`NEEDS_MORE_EVIDENCE`、`NEEDS_REDESIGN`、`BLOCKED` 均为 **0**；
  构念 `BYPASS` 为 **0**，`OPTIONAL` 2（MAP-04、MAP-26）。
- **P0 五图**：MAP-03/06/15/21 机制有效；**MAP-18 的 0/3 是接口假象**——类型化动作契约修复后
  （DCR-V10-24）非法动作从 20/20 降到 0，失败转为真实调度冲突；MAP-28 seed0 同因从“从未提交”变为成功；
  MAP-20 经 DCR-V10-25 公开取值结构后非法动作 168/168 → 0/168；MAP-05 原生 seed 化（DCR-V10-27）
  并经 DCR-V10-28 补充整数区间后非法动作 14/31 → 0；MAP-02（DCR-V10-29）与 MAP-27（DCR-V10-30）
  原生 seed 化后 3 局非法动作均为 0。
- **指标独立复核**：23 图 × 116 seed 实例，状态-取值违规从 4 条降到 **0**（MAP-12 取值域修复
  DCR-V10-23），回放确定性与 seed 差异性 23/23；**主指标公式级第二套实现** 21/27 图、761 次检查
  全一致，并据此修掉“截断局漏判 `CENSORED`”的系统性口径缺陷（DCR-V10-26）。
- **MiMo 事实**：有效局 **101**（+6 局中断保留），成功 **36/101**；结算 CNY 1.93401916 + 未知预留
  CNY 0.13312000 = **CNY 2.06713916**，远低于 ¥10 上限；逐局失败归因见 `failure-attribution.md`。

## 文件

| 文件 | 内容 |
|---|---|
| `baseline-audit.md` | Batch 0：HEAD、质量基线、冻结、V8/V9 证据可达性、seed 现状 |
| `decision-register.md` | 规则变更 vs 接口/指标修复的逐图登记 |
| `design-principles.md` | 测量效度八条原则 |
| `freeze-manifest.json` | V8/V9 逐文件 sha256 与树 hash |
| `map-status-matrix.csv/.md/.json` | 30 图状态矩阵（含 MiMo 列） |
| `validation-gates.md` | Batch 9：8 项 Gate 逐图判定与未通过明细 |
| `construct-validity.md` | 构念标签与效度状态两个独立维度 |
| `difficulty-calibration.md` | 设计难度 vs 经验难度（含 MiMo 列） |
| `baseline-results.md` | Oracle/启发式/随机/消融对照表 |
| `independent-metric-check.md` | 规格驱动五态核对 + 回放确定性 + seed 差异性 |
| `failure-attribution.md` | Batch 9：MiMo 逐局 trace 级失败归因（接口/策略/预算/阈值） |
| `trigger-gap-analysis.md` | 未触发机制局的逐局判读（预算/阈值/入口） |
| `castle-budget-analysis.md` | 古堡三图的决策预算剖面与最后动作 |
| `metric-recompute.md` | Batch 9：主指标公式级第二套实现（21/27 图、761 次检查全一致） |
| `metric-schema-v10.md` | v10 指标 schema、五态语义、缺陷处理结论 |
| `mimo-preregistration.json` | Batch 8 预登记（矩阵、预算、stop rule、补跑与阶段 3 登记） |
| `mimo-results.md` | 逐图逐 seed 结果、结局分类、中断与补跑 |
| `cost-ledger-audit.md` | 逐账本与逐局成本、未知消费与封账审计 |
| `maps/MAP-01.md … MAP-30.md` | 30 张逐图审计卡（含指标、消融、MiMo、证据索引） |
| `dcr/DCR-V10-*.md` | 24 份 DCR（规则变更与接口/指标修复） |
| `final-report.md` | 最终报告（8 问 + 剩余风险 + V11 建议） |

## 代码

| 路径 | 内容 |
|---|---|
| `src/agent_arena/v10/runtime/` | `base.py` V10 地图协议；`catalog.py` 目录（V10 优先、V8 回退）与 hash；`mapXX.py` 逐图规则 |
| `src/agent_arena/v10/baselines/` | `runner.py` 执行器（环境 seed / policy seed 分离、5 条 history 窗口）；`mapXX.py` Oracle、启发式、消融；`suite.py` 多 seed 套件 |
| `src/agent_arena/v10/metrics/` | `schema.py` v10 五态与规格；`governance.py` 154+128 枚举、缺陷结论、五态核对 |
| `src/agent_arena/v10/ledger.py` | V10 独立 append-only 预算账本（¥10 全局共享、未知消费封账） |
| `src/agent_arena/v10/contract.py` | 按类型渲染公开动作契约（DCR-V10-24） |
| `src/agent_arena/v10/validation.py` | Batch 9 的 8 项 Gate 机器判定 |
| `src/agent_arena/v10/recompute.py` | 主指标公式级第二套实现（21/27 图、761 次检查） |
| `src/agent_arena/v10/trigger_gap.py` | 未触发机制局判读与古堡预算剖面 |
| `src/agent_arena/v10/attribution.py` | MiMo 逐局 trace 级失败归因（含早期单文件布局兼容） |
| `src/agent_arena/v10/map_cards.py` / `mimo_report.py` / `construct_validity.py` / `difficulty.py` | 文档与状态矩阵生成器（禁止手填数字） |
| `scripts/run_v10_mimo.py` | 有界 MiMo runner（阶段 main / ext / i2，幂等续跑，逐局 trace/judge/manifest） |
| `tests/test_v10_*.py` | V10 单元与反例测试（1063 项全仓测试通过） |

## 复现

```powershell
.\.venv\Scripts\python.exe -m agent_arena.v10.freeze verify      # 冻结校验（9/9 unchanged）
.\.venv\Scripts\python.exe -m agent_arena.v10.baseline_audit     # V8/V9 只读复算
.\.venv\Scripts\python.exe -m agent_arena.v10.baselines.suite    # 多 seed 基线 → runs/v10/baselines
.\.venv\Scripts\python.exe -m agent_arena.v10.independent_check  # 指标独立复核
.\.venv\Scripts\python.exe -m agent_arena.v10.validation         # 8 项 Gate 判定
.\.venv\Scripts\python.exe -m agent_arena.v10.status             # 状态矩阵
.\.venv\Scripts\python.exe -m agent_arena.v10.map_cards           # 30 张审计卡
.\.venv\Scripts\python.exe -m agent_arena.v10.mimo_report        # MiMo 结果与成本审计
.\.venv\Scripts\python.exe -m agent_arena.v10.difficulty          # 难度定标与基线对照
.\.venv\Scripts\python.exe -m agent_arena.v10.construct_validity  # 构念效度
.\.venv\Scripts\python.exe -m agent_arena.v10.attribution        # trace 级失败归因
.\.venv\Scripts\python.exe -m pytest tests -k v10 -q
```

`runs/v10/` 与 `runs/v8`、`runs/v9` 一样不纳入 Git；文档中引用的数字都可由上述命令在本机复算。

## 下一会话续跑点（V11 候选）

- **5 张 V8 回退图**（01/16/17/25/27）的 **seed 参数化**：参照 MAP-05（DCR-V10-27）与
  MAP-02（DCR-V10-29）的模板，建 V10 原生运行时后补 3-seed Oracle/消融/MiMo。
- 未触发机制局的判读已落到 `trigger-gap-analysis.md`（29 局：THRESHOLD 13、BUDGET 12、USED_NO_THRESHOLD 3、ENTRY_REJECTED 1）与 `castle-budget-analysis.md`。
- **公式级指标复算**：已完成 21/27 图（761 次检查全一致）；剩余 6 图（03/13/14/21/24/26）需先把
  航线码、案卷真值、假设表、喷发时刻、`bridge_used_before_collapse`、故障真值纳入可复算的 `judge_state`。
- 未触发机制局已逐局判读（`trigger-gap-analysis.md`）：29 局 = THRESHOLD 13 / BUDGET 12 /
  USED_NO_THRESHOLD 3 / ENTRY_REJECTED 1；古堡预算见 `castle-budget-analysis.md`。
  `CONTRACT_ARTIFACT` 10 局均为旧契约下的历史记录（DCR-V10-24/25/28 之前的重跑证据）。
- **MAP-20 的机制为何没被触发**：接口已补全（非法 0/168，DCR-V10-25），但动作直方图显示只用了
  `set_flow`；仍需判读预算/阈值/提示哪一环不足。
- 古堡三图（28/29/30）在 MiMo 下大量预算耗尽，需评估**决策预算**与案卷规模是否匹配。
- 跨模型验证需要第二个 provider 与独立预算，本阶段不做。
