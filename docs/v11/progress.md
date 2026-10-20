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
- 全量测试：1239 passed；
- `ruff check .` / `mypy src` / `uv lock --check` / `git diff --check` 全部退出码 0；
- V10 `freeze verify` 9/9 unchanged；`recompute --check` 1093/1093；`independent_check --check` 0 违规；
- 真实 MiMo：3 局有效（MAP-01/19/30），58 次已记录请求，结算 ¥0.04637556，未知预留 ¥0.073728。

## 后续完善

- 修复 Streamlit 导航 widget key 失效；程序化跳转改用 `pending_nav`。
- 快速开始/配置页创建成功后递增 idempotency nonce，避免重复点击复用旧运行。
- 单局历史页继续渲染本地同模型成绩榜。
- 新增 `scripts/e2e_web.py`：Playwright + 系统 Chrome 覆盖首页 → 离线运行 → 结果 → 下载 JSON → 深链历史，本地通过。
- 新增 `scripts/verify_v11_map_pages.py`：30 图配置页浏览器映射 30/30。
- 新增跨进程单实例锁；Streamlit 锁定到 `uv.lock` 的 `web` extra。
- 新增公开动作级失败归因与 `trace.jsonl`；历史补 Provider/Seed 筛选、2–4 局对照、成绩榜预算列。
- Windows 干净克隆安装 176.9s（首次）/96.5s（复跑），无 `.env`，自检 7/7；Ubuntu CI `d51f472` success。
- 演示数据包、启动/桌面快捷方式模板、版本 `0.2.0`。

## 提交

- `8c4b8cb`：Web 服务层、30 图 catalog、离线执行、预算、存储、导出、历史与测试；
- `c0c5e0b`：可操作 Streamlit 页面、`agent-arena web` CLI、UI/CLI 测试；
- `a7e72ff`：验收/截图/冒烟脚本、交付文档、README、CI、截图；
- `54c3951`：导航 widget key、idempotency、单局历史成绩榜修复；Playwright E2E；
- `4d6a219`：CLI 测试平台差异修复（Ubuntu CI 转 success）；
- `65806ef`：跨进程锁、失败归因、筛选/多局对照、Streamlit extra 锁定；
- `e4fb40c`：shell 启动脚本可执行位；
- `d51f472`：文件锁 mypy 跨平台修正；
- 最终报告、验收数据与进度回填：本提交（见 `git log -1`）。

最终 HEAD 与完整历史以 `git log` 为准。
