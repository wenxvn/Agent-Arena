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
| 5 | NEEDS_MORE_EVIDENCE 与 VALIDATED 复核：8 张接口/证据图 + 7 张 VALIDATED 防回归 | 完成（当时 7 张记 3-seed 缺口；已由 DCR-V10-27/29/30/31/33/34/36 补齐） | 见 git log `feat(v10): batch 5` | ¥0 |
| 6 | 指标治理：154 枚举 + 128 项 V10 规格 + 20 项缺陷结论 + 五态核对 | 完成 | 见 git log `feat(v10): batch 6` | ¥0 |
| 7 | 多 seed 难度定标：`difficulty.py` + `difficulty-calibration.md` | 完成（Batch 8 后已加入 MiMo 列） | 见 git log `feat(v10): batch 7` | ¥0 |
| 8 | 有界 MiMo 复测：30 张 V10 原生图 × 3 环境 seed + 中断补跑 + 接口修复重跑 + MAP-16/20/19 重测 + MAP-01–12 重复运行 | ✅ 完成（159 局记录：152 有效 + 7 中断保留） | 见 git log `feat(v10): batch 8/9` | **CNY 2.41** |
| 9 | 最终验收：8 Gate 判定、30 张逐图审计卡、指标独立复核、trace 级归因、成本审计、最终报告 | ✅ 完成 | 见 git log `feat(v10): batch 8/9` | ¥0 |

## 结论速览

- **30 图状态**：**30 `VALIDATED`**（30 张 V10 原生图 8 项 Gate 全过；V8 回退 0）；
  `NEEDS_MORE_EVIDENCE`、`NEEDS_REDESIGN`、`BLOCKED` 均为 **0**；
  构念 `BYPASS` 为 **0**，`OPTIONAL` 2（MAP-04、MAP-26）。
- **P0 五图**：MAP-03/06/15/21 机制有效；**MAP-18 的 0/3 是接口假象**——类型化动作契约修复后
  （DCR-V10-24）非法动作从 20/20 降到 0，失败转为真实调度冲突；MAP-28 seed0 同因从“从未提交”变为成功；
  MAP-20 经 DCR-V10-25 公开取值结构后非法动作 168/168 → 0/168，再经 DCR-V10-38 补 wait 语义后
  tick 能推进（0.858824/0.329412/截尾）；MAP-19 同因补 wait 语义（DCR-V10-39）后 tick 推进到 4/2/4，
  但三局均过热；MAP-05 原生 seed 化（DCR-V10-27）
  并经 DCR-V10-28 补充整数区间后非法动作 14/31 → 0；MAP-02（DCR-V10-29）与 MAP-27（DCR-V10-30）
  原生 seed 化后 3 局非法动作均为 0。
- **指标独立复核**：30 图 × 144 seed 实例，状态-取值违规从 4 条降到 **0**（MAP-12 取值域修复
  DCR-V10-23），回放确定性与 seed 差异性 30/30；**主指标公式级第二套实现** 30/30 图、1093 次检查
  全一致，并据此修掉“截断局漏判 `CENSORED`”的系统性口径缺陷（DCR-V10-26）。
- **MiMo 事实**：有效局 **152**（+7 局中断保留），成功 **57/152**；结算 CNY 2.27994884 + 未知预留
  CNY 0.13312000 = **CNY 2.41306884**，远低于 ¥10 上限；逐局失败归因见 `failure-attribution.md`。

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
| `metric-recompute.md` | Batch 9：主指标公式级第二套实现（30/30 图、1093 次检查全一致） |
| `action-loop-scan.md` | 159 局 trace 的“重复动作 + tick 不推进”扫描（仅 19/20 命中，均已修复） |
| `thermal-gap-analysis.md` | MAP-19/20 接口修复后的热策略差距（超载/旁路缺口逐局量化） |
| `replicate-analysis.md` | MAP-01–12 的 36 对重复运行一致性（0.8889 成功一致） |
| `castle-gap-analysis.md` | 古堡三图预算耗尽时“还差什么”：证据/提问/案卷完成度与终局位置 |
| `metric-schema-v10.md` | v10 指标 schema、五态语义、缺陷处理结论 |
| `mimo-preregistration.json` | Batch 8 预登记（矩阵、预算、stop rule、补跑与阶段 3–12 登记） |
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
| `src/agent_arena/v10/recompute.py` | 主指标公式级第二套实现（30/30 图、1093 次检查） |
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
.\.venv\Scripts\python.exe -m agent_arena.v10.independent_check --check  # 指标独立复核（失败退出 1）
.\.venv\Scripts\python.exe -m agent_arena.v10.recompute --check          # 公式级复算（30/30、0 不一致）
.\.venv\Scripts\python.exe -m agent_arena.v10.trace_scan --check         # 当前规则下无免费动作循环
.\.venv\Scripts\python.exe -m agent_arena.v10.thermal_gap                 # 19/20 热策略差距
.\.venv\Scripts\python.exe -m agent_arena.v10.castle_gap                  # 古堡三图完成度
.\.venv\Scripts\python.exe -m agent_arena.v10.replicate                   # 重复运行一致性
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

- **V8 回退图已归零**：MAP-01/02/05/16/17/25/27 全部完成原生 seed 化（DCR-V10-27/29/30/31/33/34/36）。
  V11 可扩展 MAP-16 的实例空间（节点容量/侧线组合）或增加每图真实模型局数。
- 未触发机制局的判读已落到 `trigger-gap-analysis.md`（29 局：THRESHOLD 13、BUDGET 12、USED_NO_THRESHOLD 3、ENTRY_REJECTED 1）与 `castle-budget-analysis.md`。
- **公式级指标复算**：已完成 30/30 图（1093 次检查全一致；DCR-V10-32 暴露 03/24/26 的 judge 字段，
  DCR-V10-35 补齐 13/14/21，DCR-V10-36 补齐 MAP-16）。下一步是把它接入 CI。
- 未触发机制局已逐局判读（`trigger-gap-analysis.md`）：29 局 = THRESHOLD 13 / BUDGET 12 /
  USED_NO_THRESHOLD 3 / ENTRY_REJECTED 1；古堡预算见 `castle-budget-analysis.md`。
  旧契约下的 `CONTRACT_ARTIFACT` 局已被新阶段替代，不再计入有效证据；归因只读首局有效证据。
- **MAP-19/20 的机制为何没被触发**：旧局都在重复免费动作、tick 未推进；DCR-V10-38/39 补
  “只有 wait 推进时间”后 tick 已推进，剩余差距是热量分配、旁路时机与冷却排队。
  `action-loop-scan.md` 对全部 159 局做了同类扫描：当前规则下 0 局免费动作循环；
  `thermal-gap-analysis.md` 把剩余失败量化到超载次数与旁路缺口。
- 古堡三图（28/29/30）的预算耗尽已量化（`castle-gap-analysis.md`）：预算都大于 Oracle 动作数，
  失败集中在回提交点/核对链条之前的移动与重复调查，不是信息或预算不足。
- **重复运行**：阶段 15 覆盖 MAP-01–12（36 对，成功率一致 0.8889），因全局请求上限停止；
  其余 18 图仍是单 replicate，需要新预登记与新账本才能补齐。
- 跨模型验证需要第二个 provider 与独立预算，本阶段不做。
