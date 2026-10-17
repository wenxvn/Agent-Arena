# V7：30 张地图的分层能力测量

V7 只做一件事：把“地图是否通关”拆成**逐图预登记、可由 trace 确定性复算**的能力、约束、失败归因与成本指标，并把可运行地图的指标真正实现成离线 extractor。

V7 **不**修改 V2/V4/V5/V6 的规则、Action/Observation/Trace、Oracle、账本或注册表；默认离线，任何付费调用必须按 `experiment-protocol.md` 单独预登记；**不**把设计态地图说成已实现。

## 当前状态

| 项目 | 数量 | 状态 |
|---|---|---|
| 逐图手工指标卡 | 30 | 已交付（`maps/MAP-01.md` … `MAP-30.md`） |
| 设计态运行时说明 | 24 | 已交付（`pending-runtime/MAP-XX.md` 各图准入说明 + `README.md` 总表） |
| 可运行指标 extractor | 6 | 已实现（MAP-08/16/18/22/26/30） |
| 六图手工校验 | 36 | 6 图 × 6 条真实环境重放，覆盖成功/失败/边界/截尾 |
| 注册指标 | 154 | 6 图 44 条 + 24 图 110 条（`MetricSpec`，全部带 `valid_range`） |
| 泄漏与只读扫描 | 12 源 / 68 文档 | 通过 |
| 人工审阅 | 30 | `human_approved`（用户 2026-10-17 确认复核；DeepSeek 未代签） |
| 已有 MiMo trace 复算 | 47 | V6 真实 trace 的 post-hoc V7 二次分析（`real-trace-rescore.md`） |
| V7 预登记 pilot-001 | 12 | 10 启动 / 9 完整 / 1 中断（`unknown_provider_spend`）；已封账，见 `pilot-001-report.md` |
| V7 Pilot-001R 完整重跑 | 12 | 12/12 完整；独立新账本；CNY `0.08521648`；109 请求；见 `pilot-001r-report.md` |
| 新增付费 API（两次 pilot 合计） | 176 请求 | CNY `0.13607696`；129,600 input / 18,354 output；两次账本分别独立 |

## 文件地图

```text
docs/v7/
  README.md                    本文件
  source-audit.md              Batch 0 仓库与 30 图事实审计
  measurement-principles.md    四类指标、状态、事件契约、比较层级
  difficulty-rubric.md         六维设计向量与 30 图定位
  experiment-protocol.md       预注册、样本单位、预算、统计与报告规范
  map-review-checklist.md      六项人工复核清单（不代签）
  design-change-requests.md    V7-DCR 清单（proposed，未改规则）
  self-review.md               机器自审与第二遍修正记录（非人工签署）
  maps/MAP-01.md … MAP-30.md   逐图设计卡（权威细节）
  pending-runtime/MAP-XX.md     24 张无运行时地图的逐图准入说明（README.md 为总表）
  validation-report.md         本轮真实命令、测试结果、限制
  real-trace-rescore.md        已有 V6 MiMo 47 局 trace 的 V7 post-hoc 复算（非新实验）
  pilot-001-registration.md    六图 12 局付费 pilot 的预登记、预算与停止规则
  pilot-001-report.md          该 pilot 的执行结果、中断原因、指标读数与边界
  pilot-001r-report.md         同一矩阵在独立新账本上的 12/12 完整重跑结果

src/agent_arena/v7/metrics/
  schema.py                    MetricSpec / MetricValue / TraceRecord
  common.py                    共享派生量（比率、熵、合法动作、截尾）
  references.py                六图离线裁判常量（不进 prompt）
  map08.py … map30.py          六图独立 extractor
  registry.py                  30 图注册表与 compute_metrics 入口

scripts/validate_v7_metrics.py 30 卡/注册表/六图 fixture 机器验收
scripts/report_v7_metrics.py   从 V6 episode 目录离线生成 V7 指标表
scripts/run_v7_pilot.py       六图 12 局 V7 pilot 预检与付费运行入口
scripts/audit_v7_cards.py     30 卡结构、指标覆盖与构念相似度自审
scripts/check_v7_leakage.py   V7 只读边界与凭据形状文本扫描
tests/test_v7_metrics.py       schema/common/registry/文档验收测试
tests/test_v7_map_metrics.py   六图真实环境回放 fixture 指标测试
tests/test_v7_hand_traces.py   6 图 × 6 条手算轨迹的真实环境重放
tests/test_v7_leakage.py      V7 只读与泄漏扫描测试
tests/test_v7_cards.py        30 卡结构自审测试
```

## 快速开始（离线）

```powershell
# 全部 V7 测试
.venv\Scripts\python.exe -m pytest tests/test_v7_metrics.py tests/test_v7_map_metrics.py tests/test_v7_hand_traces.py tests/test_v7_leakage.py tests/test_v7_cards.py -q

# 30 卡 + 注册表 + 六图 fixture 验收
.venv\Scripts\python.exe scripts\validate_v7_metrics.py

# 卡片结构自审与泄漏扫描
.venv\Scripts\python.exe scripts\audit_v7_cards.py
.venv\Scripts\python.exe scripts\check_v7_leakage.py

# 对已有 V6 episode 目录复算（不调用模型）
.venv\Scripts\python.exe scripts\report_v7_metrics.py runs\v6\experiments\<id>\episodes\<episode>

# V7 Pilot-001 预检（不调用模型；需要当前 HEAD 的 V6 冻结门禁）
.venv\Scripts\python.exe scripts\run_v7_pilot.py --preflight

# V7 Pilot-001 付费运行（仅在预检通过、预登记已提交后使用）
.venv\Scripts\python.exe scripts\run_v7_pilot.py --execute-paid
```

`scripts/report_v7_metrics.py` 只读 `agent_trace.jsonl` 与可选的 `judge_metrics.json`；不启动环境、不调用 provider、不写账本。

## 设计边界

1. **不是 30 份同一模板**：每张卡有独立构念、公式、分母、反例、边界与同世界差异；注册表只共享类型与算术。
2. **不是跨世界总分**：默认不发布单一总分；30 图矩阵按世界/能力/难度分面展示。
3. **难度不是长度**：每图记录 `(可见性, 依赖深度, 事件动态性, 资源耦合, 记忆跨度, 分支复杂度)` 六维设计向量。
4. **指标不替代结果**：结果、能力、安全、过程四类分开；安全违例不能被效率收益抵消。
5. **缺失值不是 0**：`valid / not_applicable / censored / unavailable / invalid_trace` 五态显式记录。
6. **私有真值只用于离线裁判**：`true_leak`、`fault_part`、案情真凶等只进入 extractor，不进入 prompt、公开 Observation、公开日志或报告表格。
7. **历史不可改写**：V6 29 个实例仍为 `pending_human_review`；V7 不重写 V6 trace，也不关闭或新建账本。

## 本轮不包含

- 24 张设计图的运行时、Agent 行为或真实模型结果。
- 30 图正式 V7 矩阵；六图 12 局 pilot 已完成一次 9 局中断版和一次 12/12 完整重跑，但仍是单 seed、每条件 1 局，不能外推到 30 图。
- 任何地图规则修改；发现冲突只写 `V7-DCR-*`。
- 24 图运行时接入；30 卡已由用户复核并记录为 `human_approved`，但这不等于 24 图已可运行。
