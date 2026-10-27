# V14 · Agent Arena Lab 1.2 / Stage II Final Evidence & Delivery

> **当前状态：`IN_PROGRESS`（Batch 0 完成）。** 真实模型效果：`LIVE_PENDING`
> （未获用户对模型 / 矩阵 / 总费用上限的明确批准，V14 新增外部付费请求 **0**）。

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
uv run python scripts/verify_v14.py
```

## 边界

- 不修改 `worlds/scenario_v8/`、`v10/runtime/` 冻结规则、V8/V9/V10 账本与历史 trace；
- 不自动发起任何真实付费请求；
- Ollama 与 macOS 不在本轮范围。
