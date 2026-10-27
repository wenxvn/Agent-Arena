# V14 Batch 0 · 最新仓库与第二阶段收口审计

- 执行日期：2026-10-27（本地）
- 审计基线 HEAD：`60c9ba2b64a3bd8d5cd549a7b76d0f3eb3ad092a`
  （`chore(v13): keep V12/V13 research outlines user-local (final)`，2026-10-26 23:11:14 +0800）
- 提纲建议基线：`60c9ba2`（一致，无漂移）
- 工作区状态：`main...origin/main` 无本地提交差异；仅 3 个未跟踪文件
  （`研究提纲/V12…`、`V13…`、`V14…` 用户本地提纲，按 V13 决策保持不提交）
- 工具链：本地 `python 3.11.9` 用于启动 `uv`；项目解释器由 `uv` 锁定为 3.13（`uv.lock` 未改动）
- 真实付费请求：**0**（本轮 Batch 0 只跑离线门禁）

## 1. 基线门禁复跑（实际运行，2026-10-27）

| 门禁 | 命令 | 结果 |
|---|---|---|
| 依赖锁 | `uv lock --check` | 通过（Resolved 65 packages） |
| 代码规范 | `uv run ruff check .` | 通过（All checks passed） |
| 类型检查 | `uv run mypy src` | 通过（323 source files，0 issues） |
| 离线测试 | `uv run pytest -q` | **1639 passed**（122.25s） |
| V8/V9/V10 冻结 | `uv run python -m agent_arena.v10.freeze verify` | 通过（全部 `unchanged`） |
| 公式级复算 | `uv run python -m agent_arena.v10.recompute --check` | `{"checks":1093,"maps_covered":30,"match":1093,"mismatch":0}` |
| 指标独立复核 | `uv run python -m agent_arena.v10.independent_check --check` | `{"maps":30,"seed_instances":144,"violations":0,"seed_distinct_ok":30,"deterministic_ok":30}` |
| V11 验收 | `uv run python scripts/verify_v11.py` | 7/7 通过 |
| V12 验收 | `uv run python scripts/verify_v12.py` | 15/15 通过 |
| V13 验收 | `uv run python scripts/verify_v13.py` | 18/18 通过 |

> 与 V13 报告记录的数字（1639 / 323 / 1093 / 18 项）完全一致，说明 V13 到 V14 之间没有未记录的回归。

## 2. V13 → V14 的真实增量（不重复开发）

已实现、V14 **不重做**的模块：

- 世界层：30 张 V10 原生运行时（`worlds/scenario_v8` 24 张 + `v10/runtime` 6 张适配），V8/V9/V10 账本与 trace 只读。
- 平台层：V11 `web/` 服务层与 Streamlit 页面；V12 `lab/` 契约、策略注册表、`DecisionGateway`、`AgentRunnerV12`、父子实验、诊断、Diff、导出；V13 `lab/v13/` 只读分析层（可比性、稳定性、消融、taxonomy、capability、validity、ledger、perf、sdkcheck、report）。
- 策略层：`memory.v2` / `planning.v2` / `reflection.v2` 与 v1 并存（v1 未改）。
- 文档层：`docs/v12/`、`docs/v13/` 全套。

V14 只做四类增量：**口径修正**、**新增可复算证据**、**门禁与交付**、**UI 信息增益**。

## 3. 19 项工程任务的真实起点（Batch 0 判定）

| ID | 起点状态 | 起点依据 |
|---|---|---|
| P0-1 | `PARTIAL` | V13 记录的 CI 结论只有一次远端成功（`40435185866`）；本轮已补全 Actions 证据索引 |
| P0-2 | `DEFECT` | `v13/validity.py::validity_markdown` 把未知字段打印成 `0/N`；`docs/v13/map-validity.md` 已受影响；`live-budget-proposal.md` 合计 229 ≠ 逐行 221 |
| P0-3 | `PARTIAL` | 已有 `comparability.py` / `stability.py`，但缺 8 维观测条件 ID 与报告层字段拆分 |
| P0-4 | `PARTIAL` | `memory.v2` 已实现；真实收益 `WAITING_USER_APPROVAL`，缺 on/off 预检登记 |
| P0-5 | `PARTIAL` | `planning.v2` 已实现；缺每次触发的费用归因链 |
| P0-6 | `PARTIAL` | `reflection.v2` 已实现；真实 `triggered > 0` 未在 LIVE 证实 |
| P1-1 | `DONE` | `map30_ladder` + `docs/v13/map30-budget-ladder.md`（V14 需补保守区间措辞） |
| P1-2 | `PARTIAL` | 六图已审计；MAP-19/20/29 候选图未审计 |
| P1-3 | `PARTIAL` | 七层 taxonomy 已实现；缺"拒绝导致无进展"与"有公开进展但预算失败"的正反 fixture |
| P1-4 | `PARTIAL` | 六维画像已实现；缺 `UNAVAILABLE` 显式缺口字段与并列证据等级 |
| P1-5 | `PARTIAL` | V13 已记 P1-5 为 `PARTIAL`（未新增图形化组件） |
| P1-6 | `PARTIAL` | 四级结论已实现；`SUPPORTED` 语义仍需与"效果显著/因果"分离 |
| P2-1 | `PARTIAL` | `lab-e2e.continue-on-error: true`；本轮已确认连续 7 次远端 E2E 成功 |
| P2-2 | `PARTIAL` | 1k/5k 已测；缺冷启动、损坏 manifest、并发写、TTL 刷新 |
| P2-3 | `PARTIAL` | 5 页可用；窄屏/键盘/授权阻断未系统验证 |
| P2-4 | `PARTIAL` | 导出已实现；缺跨格式行数/分母一致性审计 |
| P2-5 | `PARTIAL` | SDK 8 项自检；缺旧签名与异常隔离的显式回归用例 |
| P2-6 | `DONE（本地）/ BLOCKED_EXTERNAL（后台账单）` | 本地 159/159 复算通过；无脱敏账单 |
| P2-7 | `PARTIAL` | V13 交付包完整；V14 交付包本轮新建 |

## 4. 已知文档错误（必须在 Batch 1 修正）

1. `docs/v13/map-validity.md`：六图"机制触发局"列全部打印 `0/N`，实际是历史 CSV 无该字段 → 应为 `UNKNOWN`。
2. `docs/v13/live-budget-proposal.md`：
   - 逐行子局合计 **221**，文件写 **229**；
   - 方案 B（E0+E1+E2+E3）逐组相加为 **186 局 / ¥5.49**，文件写 **150 局 / ¥4.19**；
   - 方案 A（E1-a+E2-a+E3-a）**54 局**成立，但预估应为 **¥2.11**（0.90+0.31+0.90），文件写 ¥1.68；
   - E2-d（MAP-18）与 E4（MAP-30）行的"预估"与文档自己声明的 1.5 倍余量公式不一致。
3. `docs/v13/README.md` 记"尚未推送、远端 CI 未验证"已过时（`40435185866` 两个 job 均 success）。

## 5. 结论

- 工程基线健康：10 项门禁全部通过，无回归。
- V14 不需要重做 V11–V13，重点是**数据口径、证据边界、门禁与交付**。
- 本轮不修改任何冻结世界、V8/V9/V10 账本或历史 trace。
