# V14 · Agent Arena Lab 1.2 / Stage II Final Evidence & Delivery

> **当前状态：`ENGINEERING_VERIFIED` / `LIVE_PARTIAL`。**
> 真实 MiMo 已执行 **227 局 / ¥3.89636556**（flash + pro，方案 A + 六轮补充）：
> `planning.v2` 跨模型/跨图/留出 seed 复现（MAP-16 flash 0/25→14/22；pro 2/12→**12/12**；
> MAP-18 2/9→4/9），并有负向对照（MAP-26 天花板 9/9→9/9、MAP-14 地板 0/9→0/9）；
> `route_log` 仅在 MAP-22 seed 2 且 ≥150 请求时有效（2/9→8/8）；
> `reflection.v2` 暴露已稳定（MAP-22@150 触发 4/6 vs 5/6），但 n=6 效果未检出。
> 因此 **不是** `STAGE_II_FINAL_READY`——缺负向对照与账单核对，不得宣称收官。
>
> 验收：`uv run python scripts/verify_v14.py` → **14/14 通过**；
> 全量 `uv run pytest -q` → **1790 passed**。

## 这是什么

V14 在 V13（Lab 1.1）之上做**第二阶段收官**：口径校准、v2 策略有效性验证方案、
CI 与产品交付验收。不新增世界、不改冻结规则、不做公网部署。

## 三种"完成"必须分开

| 状态 | 含义 |
|---|---|
| `ENGINEERING_VERIFIED` | 代码、离线测试、浏览器 E2E、无泄漏、账本一致已证实 |
| `LIVE_EVIDENCE_VERIFIED` | 用户批准并执行真实模型试验，结果有合法分母、可比性与机制暴露证据（**不要求涨点**） |
| `STAGE_II_FINAL_READY` | 两者都满足，且 P0/P1/P2 收尾项或有明确接受的非阻断例外 |

## 文档索引

| 文件 | 内容 |
|---|---|
| `baseline-audit.md` | 最新 HEAD、门禁复跑、V13→V14 真实增量、19 项起点 |
| `live-plan.md` | LIVE 方案 A 预注册（54 局 / ¥2.11 预估 / ¥5.00 上限） |
| `live-report.md` | **真实 MiMo 执行报告**（39 局、账本、三组结果、停批事件） |
| `live-results.md` / `.json` | 逐组数据明细（只读聚合生成） |
| `map22-instances.md` / `.json` | MAP-22 实例差异归因（公开轨迹，解释「为什么只有 seed 2」） |
| `engineering-boundaries.md` | 冷启动、异常负载、长历史导出、SDK 加固、账本复算 |
| `pairing-audit.md` | V12 三组消融按 8 元组条件身份重新配对 |
| `budget-audit.md` | V13 预算申请算术复核（221 局 / ¥10.97） |
| `validity-diff.md` | V13→V14 六图口径差异表 |
| `ci-evidence.md` | 远端 Actions run/job 逐条证据 |
| `data-validity.md` | `UNKNOWN` vs `0`、版本隔离、构念效度口径修正 |
| `experiment-protocol.md` | 可比性、重复、门禁、批准边界 |
| `agent-studies.md` | Memory / Planning / Reflection 机制与 LIVE 状态 |
| `map-audit.md` | 六图 + 候选图、MAP-30 截尾 |
| `failure-and-capability.md` | 七层归因与六维画像的证据边界 |
| `validation-report.md` | 实际运行的命令与结果 |
| `gap-audit.md` | 19 项逐项状态与证据 |
| `release-checklist.md` | 交付验收 Gate |
| `final-report.md` | 实际结果、负面结果、剩余问题 |
| `decisions.md` | 协议/版本变动 |
| `progress.md` | Batch 进度与 commit |
| `screenshots/` | 真实浏览器截图（脱敏） |

## 复现入口

```bash
uv sync --extra web
uv run agent-arena web          # 单机 Lab（无 Key 可跑 SIMULATED 全流程）
uv run python scripts/verify_v14.py                 # 14 项 V14 事实边界
uv run python scripts/audit_v14_data.py --write
uv run python scripts/audit_v14_agents.py --write
uv run python scripts/audit_v14_maps.py --write
uv run python scripts/audit_v14_failures.py --write
uv run python scripts/audit_v14_engineering.py --write
uv run python scripts/plan_v14_live.py --check
```

## 边界

- 不修改 `worlds/scenario_v8/`、`v10/runtime/` 冻结规则、V8/V9/V10 账本与历史 trace；
- 不自动发起任何真实付费请求；
- Ollama 与 macOS 不在本轮范围。
