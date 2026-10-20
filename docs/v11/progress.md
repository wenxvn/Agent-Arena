# V11 执行进度

起始 HEAD：`eb2f64a281677a0fce881769a6592cce1be6f7d9`（2026-10-20）。

| Batch | 内容 | 状态 | 证据 |
|---|---|---|---|
| 0 | 仓库盘点、HEAD/工作树、UI/runner/catalog 审计 | done | `00-audit.md` |
| 1 | RunService、状态机、持久化、取消、恢复、预算 | done | `src/agent_arena/web/`、`tests/test_web_*.py` |
| 2 | 30 图 catalog、展示难度、地图详情 | done | `web/catalog.py`、`difficulty-display.md` |
| 3 | 可操作 Streamlit 页面、离线完整流程 | done | `ui/app.py`、`ui-pages.md`、截图 |
| 4 | 真实 Provider、费用保护、3 局 MiMo 冒烟 | done | `final-report.md` §7、`runs/v11/` |
| 5 | 指标五态、失败解释、JSON/CSV 导出 | done | `web/export.py`、`web/explain.py`、`test-report.md` |
| 6 | 文档、README、CI、一键自检、安装演练 | done | `quickstart.md`、`scripts/verify_v11.py` |
| 7 | P1/P2 体验冲刺 | done（P2 部分延期） | `backlog.md`、截图 |

## 关键验证

- 离线矩阵：30/30 图可启动、可回放、可导出，473 步；
- 一键自检：7/7 通过（catalog、offline_matrix、budget、redaction、paths、export、recovery）；
- 全量测试：1230 passed；
- `ruff check .` / `mypy src` / `uv lock --check` / `git diff --check` 全部退出码 0；
- V10 `freeze verify` 9/9 unchanged；`recompute --check` 1093/1093；`independent_check --check` 0 违规；
- 真实 MiMo：3 局有效（MAP-01/19/30），58 次已记录请求，结算 ¥0.04637556，未知预留 ¥0.073728。

## 提交

按 Batch 拆分为若干提交，具体 hash 与最终 HEAD 见 `final-report.md` 与 `git log`。本文不复制全部 commit 列表，避免与 Git 历史重复。
