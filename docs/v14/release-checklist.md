# V14 交付验收清单（Release Gate）

- 版本：Agent Arena Lab 1.2 / Stage II Final Evidence & Delivery
- 日期：2026-10-27
- 基线 HEAD：`60c9ba2b64a3bd8d5cd549a7b76d0f3eb3ad092a`（V14 起点）
- 真实付费执行：**227 局 / 6 273 请求 / CNY 3.89636556**（方案 A + 六轮补充；3 局 unknown_spend 预留）

> 判定分成三层，**不允许混写**：
> `ENGINEERING_VERIFIED` / `LIVE_EVIDENCE_VERIFIED` / `STAGE_II_FINAL_READY`。

## 1. 工程验收（`ENGINEERING_VERIFIED`）

| # | 项 | 命令 / 证据 | 结果 |
|---|---|---|---|
| 1 | 依赖锁 | `uv lock --check` | 通过 |
| 2 | 代码规范 | `uv run ruff check .` | 通过 |
| 3 | 类型检查 | `uv run mypy src` | 334 files，0 issues |
| 4 | 离线测试 | `uv run pytest -q` | **1790 passed** |
| 5 | V8/V9/V10 冻结 | `uv run python -m agent_arena.v10.freeze verify` | 全部 unchanged |
| 6 | 公式级复算 | `uv run python -m agent_arena.v10.recompute --check` | 1093/1093 |
| 7 | 指标独立复核 | `uv run python -m agent_arena.v10.independent_check --check` | 0 违规 |
| 8 | V11 验收 | `uv run python scripts/verify_v11.py` | 7/7 |
| 9 | V12 验收 | `uv run python scripts/verify_v12.py` | 15/15 |
| 10 | V13 验收 | `uv run python scripts/verify_v13.py` | 18/18 |
| 11 | **V14 验收** | `uv run python scripts/verify_v14.py` | 14/14 |
| 12 | 浏览器 E2E | `e2e_lab.py --start --port 8516 --report runs/v14/e2e-report.json` | 通过 |
| 13 | 可访问性 | `a11y_v12.py --browser --start` | critical/serious/moderate 全 0 |
| 14 | 远端 CI | `docs/v14/ci-evidence.md` | `lab-e2e` 为阻断门禁，切换后连续成功 |
| 15 | 冻结资产 | `git status` 无 `worlds/scenario_v8` / `v10/runtime` / `real-runs` 改动 | 通过 |

## 2. 数据与证据验收

| # | 项 | 证据 | 结果 |
|---|---|---|---|
| 1 | `UNKNOWN` 不渲染成 `0/N` | `docs/v14/data-validity.md` | 通过 |
| 2 | 跨协议禁止合并 | `POOLED_ACROSS_PROTOCOLS`（MAP-16/18/22/30） | 通过 |
| 3 | seed 与重复分开 | `docs/v14/pairing-audit.md` | 通过 |
| 4 | 预算表算术 | `docs/v14/budget-audit.md`（221 局 / ¥10.97） | 通过 |
| 5 | 诊断锚点 | `docs/v14/failure-and-capability.md` 第 1 节 | 通过 |
| 6 | 能力画像缺口 | 同上第 2 节（`failure_recovery: UNAVAILABLE`） | 通过 |
| 7 | 结论强度三字段 | 同上第 3 节 | 通过 |
| 8 | 账本复算 | `engineering-boundaries.md` 第 5 节（159/5641/¥5.43680012） | 通过 |
| 9 | 导出一致性 | 同上第 6 节 | 通过 |
| 10 | 外部账单 | `NO_EXTERNAL_BILL_PROVIDED` | `BLOCKED_EXTERNAL` |

## 3. 产品交付验收

| # | 项 | 证据 | 结果 |
|---|---|---|---|
| 1 | 五页 Lab 可用 | `docs/v14/screenshots/`（含 430px 窄屏、深色） | 通过 |
| 2 | 一键离线演示 | `uv run agent-arena web` → 一键离线演示 | 通过 |
| 3 | 报告下载 | E2E 下载 `report.md` 并校验脱敏 | 通过 |
| 4 | 首次分歧高亮 | `screenshots/03-lab-first-divergence.png` | 通过 |
| 5 | MAP-22 探索不画被拒移动 | `screenshots/02-lab-map22-exploration.png` | 通过 |
| 6 | 不可比时禁用排名 | 结果页门禁横幅（`comparison_gate`） | 通过 |
| 7 | 中文文档 | `docs/v14/` 全套 16 份 | 通过 |

## 4. 明确未完成 / 不适用

| 项 | 状态 | 原因 |
|---|---|---|
| `memory.v2` 真实效果 | 已测（65 局）| 90 请求 0/10 vs 0/10；150 请求 seed 2 **2/9 → 8/8**，seed 0/1/3 两臂全败 → **条件性** |
| `planning.v2` 真实效果 | 已测（121 局 / 4 图 × 2 模型）| MAP-16 flash 0/25 → 14/22；**pro 2/12 → 12/12（含留出 seed）**；MAP-18 2/9 → 4/9；MAP-26 9/9→9/9（天花板）；MAP-14 0/9→0/9（地板） |
| `reflection.v2` 真实效果 | 暴露稳定 / 效果未检出 | MAP-22@150 单因子 trigger_only 2/6 vs on 1/6（n=6 无功效） |
| 外部账单对账 | `BLOCKED_EXTERNAL` | 用户未提供脱敏账单 CSV |
| 本机 Playwright 自带 chromium 复现 | `NOT_VERIFIED` | CDN 下载受限；CI 侧已真实验证 |
| 真机读屏软件 | `NOT_VERIFIED` | 无读屏环境（自动化 a11y 已 0 严重问题） |
| macOS 实机 | 不在本轮范围 | 按用户指示暂缓 |
| Ollama | 不在本轮范围 | 按用户指示暂缓 |

## 5. 最终状态

- `ENGINEERING_VERIFIED`：**满足**。
- `LIVE_EVIDENCE_VERIFIED`：**不满足（部分达成）**——227 局；规划已跨模型/跨图/留出 seed 复现且有天花板+地板对照，但仍缺外部账单核对、记忆的实例归因与反思功效。
- `STAGE_II_FINAL_READY`：**不满足**；
  按提纲要求，此时不得宣称"第二阶段最终实证完成"。

可复现入口：

```bash
uv sync --extra web
uv run agent-arena web                 # 单机 Lab，无 Key 可跑完整 SIMULATED 流程
uv run python scripts/verify_v14.py    # 14 项 V14 事实边界
```