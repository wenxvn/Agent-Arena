# V14 差距审计（19 项逐项）

状态定义：`DONE` / `PARTIAL` / `LIVE_PENDING` / `BLOCKED_EXTERNAL` / `NOT_DONE`
判定原则：**只有可核查证据（代码 + 命令输出 + 文档）才可标 `DONE`**。

- 生成：2026-10-27
- 基线 HEAD：`60c9ba2b64a3bd8d5cd549a7b76d0f3eb3ad092a`
- 真实付费请求：**0**（未获批）

## 0. 一句话结论

**15 项 `DONE`；3 项"工程完成 / 真实收益 `LIVE_PENDING`"（P0-4、P0-5、P0-6）；
1 项本地 `DONE` + 外部 `BLOCKED_EXTERNAL`（P2-6）。**

- 没有任何一项被静默跳过：未完成的都写明了原因与需要谁授权。
- 真实付费请求 **0**；`LIVE_EVIDENCE_VERIFIED` 与 `STAGE_II_FINAL_READY` 都**不满足**。
- 验收：`scripts/verify_v14.py` **14/14**；全量 pytest **1790 passed**。

## 1. P0（6 项）

| ID | 任务 | 起点 | 当前 | 证据 |
|---|---|---|---|---|
| P0-1 | HEAD/CI 证据基线审计 | `PARTIAL` | `DONE` | `baseline-audit.md`（10 项门禁复跑）、`ci-evidence.md`（10 次 run + 7 次连续 `lab-e2e` success） |
| P0-2 | 历史数据/构念效度口径修正 | `DEFECT` | `DONE` | `lab/v13/validity.py` 三档计数；`lab/v14/data_audit.py`；`docs/v14/data-validity.md`；`budget-audit.md`；14 + 114 测试 |
| P0-3 | 重复实验与单因子公平性强化 | `PARTIAL` | `DONE` | `lab/v14/conditions.py`（8 元组身份/seed 白名单/三档判定/配对字段）；`docs/v14/pairing-audit.md`、`experiment-protocol.md`、`live-plan.md`；33 测试 |
| P0-4 | Memory v2 有效性方案与消融 | `PARTIAL` | `DONE（离线）/ LIVE_PENDING` | `lab/v14/agent_studies.py`（3 fixture + 单因子臂 + 36 局预检）；`docs/v14/agent-studies.md` 第 1 节；17 测试；DCR-V14-03；真实收益未测 |
| P0-5 | Planning v2 收益–成本验证 | `PARTIAL` | `DONE（离线）/ LIVE_PENDING` | `lab/v14/planning_study.py`（触发链 + 成本归因 + 3 组单因子 + 72 局预检）；`agent-studies.md` 第 2 节；14 测试 |
| P0-6 | Reflection v2 激活与效果验证 | `PARTIAL` | `DONE（离线）/ LIVE_PENDING` | `lab/v14/reflection_study.py`（六态 + 三臂 + 暴露门禁 + 选择偏倚防护 + 27 局预检）；`agent-studies.md` 第 3 节；15 测试 |

## 2. P1（6 项）

| ID | 任务 | 起点 | 当前 | 证据 |
|---|---|---|---|---|
| P1-1 | MAP-30 约束阶梯与失败类型 | `DONE` | `DONE` | `lab/v14/map_audit.py::map30_three_axis`（三档 × 三维 + 瓶颈轴 + 保守区间）；`docs/v14/map-audit.md` 第 2 节 |
| P1-2 | 关键/候选地图效度再核验 | `PARTIAL` | `DONE` | `six_map_recheck` + `candidate_map_audit`（MAP-19/20/29 只读）；`map-audit.md` 第 1/3 节；12 测试 |
| P1-3 | 七层失败归因审计 | `PARTIAL` | `DONE` | `lab/v14/failure_capability.py`（锚点三态 + 3 fixture + 层级可进性矩阵）；`failure-and-capability.md` 第 1 节 |
| P1-4 | 六维能力画像稳健化 | `PARTIAL` | `DONE` | `capability_with_gaps`（UNAVAILABLE/seed/重复/缺口并列）；`failure-and-capability.md` 第 2 节 |
| P1-5 | 轨迹 Diff 与六图可视化增强 | `PARTIAL` | `DONE` | `lab/v14/ui_views.py`（首次分歧/MAP-22/MAP-30/seed 分组）+ UI 集成 + 7 张截图；`docs/v14/screenshots/` |
| P1-6 | 报告可复现与结论强度修正 | `PARTIAL` | `DONE` | `conclusion_strength`（三字段 + forbidden_claims）；`failure-and-capability.md` 第 3 节；16 测试 |

## 3. P2（7 项）

| ID | 任务 | 起点 | 当前 | 证据 |
|---|---|---|---|---|
| P2-1 | CI 浏览器 E2E 正式门禁 | `PARTIAL` | `DONE` | `ci.yml` 移除 `continue-on-error`（`34a83fe`）；切换后一次红灯保留在 `40477841302`，修复见 `babe194`，`40482235016` 双 job success |
| P2-2 | 大历史/冷启动/异常负载 | `PARTIAL` | `DONE` | `lab/v14/engineering.py`（冷启动/损坏 manifest/并发写/TTL/1000 局导出）；`engineering-boundaries.md` 第 1–3 节 |
| P2-3 | Lab Web 用户体验 | `PARTIAL` | `DONE` | 可比性门禁横幅、MAP-30 阶梯、窄屏/深色截图；`e2e_lab.py` 通过 + a11y 0 critical/serious/moderate |
| P2-4 | 自动报告/导出一致性 | `PARTIAL` | `DONE` | `export_consistency`（行数/分母/模式/空值）+ 真实导出样本；`engineering-boundaries.md` 第 6 节 |
| P2-5 | 第三方 Agent SDK 加固 | `PARTIAL` | `DONE` | `sdk_hardening`（8 项 + 旧签名/异常隔离/预算网关 3 项）；`engineering-boundaries.md` 第 4 节 |
| P2-6 | 本地账本/外部账单核对 | `DONE`/`BLOCKED_EXTERNAL` | `DONE（本地）/ BLOCKED_EXTERNAL（外部）` | `ledger_recompute` 复算 159/159、5641 请求、¥5.43680012、0 重复 0 孤儿；外部账单 `NO_EXTERNAL_BILL_PROVIDED` |
| P2-7 | V14 最终交付封装 | `PARTIAL` | `DONE` | `docs/v14/` 16 份文档 + 7 张截图 + `scripts/verify_v14.py`（14 项）+ CI 步骤 |

## 4. 为什么 P0-4/5/6 不能标 `DONE`

这三项的**工程部分**（机制验证、单因子臂、预检登记、成本归因、暴露门禁）全部完成，
但它们的验收标准包含"真实模型下的收益/暴露"。V14 未获批准，因此：

- 机制层：`SUPPORTED`（可复算的确定性证据）；
- 真实收益：`LIVE_PENDING`（0 局、¥0）；
- 状态因此写作 `DONE（离线）/ LIVE_PENDING`，不写 `DONE`。

## 5. 复算入口

```bash
uv run python scripts/verify_v14.py
```
