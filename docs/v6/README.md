# V6 能力测量效度目录

本目录记录 V6（能力测量修复与泛化验证）的审计、设计差异、实例矩阵与验证结果。V6 不以提高通过率为目标，而以**可靠识别能力差异**为目标；本轮只做离线开发，不调用任何收费 API。

## 文件

| 文件 | 内容 |
|---|---|
| [`v5-failure-audit.md`](v5-failure-audit.md) | 基于本机真实 trace 的 V5 六图失败分类与数据质量审计 |
| [`design-change-requests.md`](design-change-requests.md) | V6 对既有资产的变更申请（DCR），含证据、影响与回归 |
| [`measurement-matrix.md`](measurement-matrix.md) | V6 实例矩阵：instance × condition × level × 指标 |
| [`pilot-report.md`](pilot-report.md) | **真实 API 复测结果**（MiMo `mimo-v2.6-flash`，24 局，CNY ¥0.17891580）与效度判读 |
| `validation-report.md` | 离线验收与独立求解结果（含真实 API 运行证据） |
| `api-experiment-proposal.md` | 真实 API 复测协议与预算门禁（已执行一次；再次执行需重新登记） |
| `next-24-gate.md` | 是否扩展到其余 24 图的建议门槛与当前结论（`HOLD`） |

## 代码与命令

| 位置 | 作用 |
|---|---|
| `src/agent_arena/v6/` | 实例 scene、catalog/manifest、独立求解器、Oracle 生成、泄漏扫描 |
| `scripts/audit_v5_failures.py` | 只读审计本机 V5 trace；无 trace 时输出 `trace_unavailable` |
| `scripts/validate_v6_instances.py` | 回放每个实例的 Oracle、核对 solver、检查确定性与边界 |
| `scripts/validate_v6_leakage.py` | 扫描公开提示/Observation/trace 的泄漏反例 |
| `scripts/run_v6_pilot.py` | V6 付费/假 dry-run runner（默认 dry-run；付费需 `--execute-paid`） |
| `scripts/summarize_v6_pilot.py` | 汇总最新 V6 实验的逐实例结果与费用 |

```bash
python scripts/audit_v5_failures.py --summary
python scripts/validate_v6_instances.py
python scripts/validate_v6_leakage.py
python scripts/run_v6_pilot.py            # fake dry-run
python scripts/summarize_v6_pilot.py      # summarize the newest paid experiment
python -m pytest -q
```

## 边界

- 不改 V4 原始地图文件；V4 引擎仅做向后兼容的参数化（见 DCR-002）。
- 不触碰 V5 实验、账本、registry 与 V2 已关闭账本。
- 所有 V6 实例 `review_status` 保持 `pending_human_review`，需人工审阅后才可用于真实模型实验。
