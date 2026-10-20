# V11 发布检查清单（本地网页预览版）

**结论：`WEB_PREVIEW_READY` = true（本地单机预览，不是公网生产就绪）。**

## P0 硬门槛

- [x] **30 图最终体验检查**：30/30 可选中、可启动、可回放、可导出；逐图留痕 `map-ux-checklist.md`；6 张占位标题只在展示层修复；MAP-19/20/28/29/30 有详情提醒。
- [x] **统一运行入口**：`uv sync --extra web` + `uv run agent-arena web`（无 extra 时可用 `uv run --with streamlit agent-arena web`）；首页可选 10 世界 30 图；地图、seed、模式、Provider、模型、预算在一处配置；原 CLI 保留。
- [x] **模型 API 配置**：`.env.example`、OpenAI-compatible/MiMo、Ollama、零网络配置检查、显式连接检查、无 Key 离线演示；密钥只显示“已配置/未配置”；真实付费前勾选确认。
- [x] **结果输出**：稳定 `run_id`、地图、rule/metric hash、seed、模式、Agent、outcome、动作、公开观察、token/费用、失败原因；实时进度、历史回放、JSON/CSV 导出。
- [x] **错误处理与安全**：连接/超时/限流/模型不存在、非法动作、usage 缺失、预算耗尽、用户取消、刷新、中断、重复提交、未知费用均有状态与 fail-closed 处理；无自动无限重试；单 worker 串行。
- [x] **README 与安装教程**：Windows PowerShell + macOS/Linux；无 Key 演示、真实 API、常见错误、日志位置、一键自检。
- [x] **一键验收**：`uv run python scripts/verify_v11.py` 或 `uv run agent-arena web --check`；7/7 通过；全量 pytest/ruff/mypy/lock 独立门禁。

## P1

- [x] **难度标签**：30 图 `display_difficulty` + `difficulty_note`；保留 `design_difficulty` 与原 ID；不按 MiMo 3 局胜率重排。
- [x] **网页体验**：地图卡片、配置、启动/停止、实时时间线、状态、回放、结果；中文文案、空状态、加载态、错误提示、移动端基本适配。
- [x] **历史检索与对照**：按地图/状态/模式/日期/模型筛选；同版本同模式才允许直接对照；版本不一致阻止并提示。
- [x] **新手引导**：首页快速开始、规则折叠、费用提示、失败解释、无 Key 演示、空状态。
- [x] **自动化浏览器 E2E**：Playwright + 系统 Chrome，覆盖首页 → 离线运行 → 结果 → 下载 JSON → 深链历史；本地实测通过。

## P2

- [x] **可视化增强**：公开 Observation 数值字段走势图；不使用隐藏真值。
- [x] **本地同模型成绩榜**：同地图/模型/模式/规则指标版本内排序；显示 seed；不联网、不跨模型。
- [x] **快捷启动**：`scripts/launch_web.ps1`、`scripts/launch_web.sh`；截图 `docs/v11/screenshots/`。
- [ ] **演示数据包 / 桌面快捷方式**：DEFERRED，见 `backlog.md`。

## 质量与冻结

- [x] `ruff check .` / `mypy src` / `pytest -q` / `uv lock --check` / `git diff --check` 全部退出码 0。
- [x] `freeze verify` 9/9 unchanged；`recompute --check` 1093/1093；`independent_check --check` 0 违规。
- [x] 未修改 V10 地图规则、成功条件、Oracle、指标公式或历史冻结账本。
- [x] `runs/`、`.env`、账本、截图外的临时文件未进入 Git。
- [x] 真实 API 使用独立 V11 账本：结算 ¥0.04637556 + 未知预留 ¥0.073728 < ¥3。

## 未完成 / 不作为门槛

- [ ] macOS / Linux 本机启动实测（文档与脚本已提供；本次仅有 Windows 11）。
- [ ] 公网部署、登录、多用户隔离、云数据库（明确不做）。
- [ ] 正式 Git tag / GitHub Release（**未经用户确认不推送**）。
- [ ] 人工 `human_approved`（当前均为 `agent_reviewed`）。

## 最短回滚

1. 停网页进程；
2. 删除 `runs/web/` 与 `runs/v11/` 本地生成物；
3. `git revert` 对应 V11 提交；
4. 旧 CLI 与 V8/V9/V10 研究资产不受影响。
