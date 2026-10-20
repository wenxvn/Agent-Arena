# V11 Backlog（P2 与后续）

## 1. P2 状态

| 项 | 状态 | 说明 | 下一步 |
|---|---|---|---|
| P2-1 公开状态可视化 | **DONE（基础版）** | 结果页可选公开 Observation 数值字段画折线；数据只来自 agent-visible 事件 | 增加地图主题卡片、资源条、进度图 |
| P2-2 本地同模型成绩榜 | **DONE** | 同地图/模型/模式/规则指标版本内排序；显示 seed、费用与决策预算 | 按 seed 分组/个人最好成绩分层 |
| P2-3 快捷启动脚本 | **DONE** | `launch_web.ps1`、`launch_web.sh`、`launch_web.command`、Windows 桌面快捷方式脚本、Linux `.desktop` 模板 | 跨平台安装器 |
| P2-3 演示截图 | **DONE** | `docs/v11/screenshots/` 八张（含移动端） | 深色模式对照 |
| P2-3 演示数据包 | **DONE** | `docs/v11/demo/` + `scripts/install_v11_demo.py`，一键安装 MAP-01 离线 15 步记录 | 扩展到 3 局样本 |
| P2-3 桌面快捷方式 | **DONE（模板）** | Windows 脚本可直接创建；macOS `.command`；Linux `.desktop` 模板需改路径 | 各平台安装器 |

## 2. 后续工程项

| 项 | 优先级 | 工作量 | 说明 |
|---|---|---|---|
| macOS 实机启动验证 | P0 补证 | 1–2 h | Ubuntu 已通过 CI；macOS 仍需实际执行 `.command`/浏览器 |
| 连接检查/Ollama/错误码真实触发 | P1 补证 | 0.5–1 d | 代码已提供；需实际发一次探测、跑一局 Ollama、触发限流/额度错误 |
| 自动化浏览器 E2E | **DONE（本地）** | — | `scripts/e2e_web.py` + `scripts/verify_v11_map_pages.py`；使用临时 runs 目录；可选加入 CI |
| 移动端真机 / 深色 / 可访问性 | P1 | 1–2 d | 当前只有 430px headless 截图，无真机与 a11y 审计 |
| 取消的真实网络中断 | P2 | 2–3 d | 当前只能等当前请求结束；需要 provider 层超时/取消协议 |
| Provider 账单对账 | P2 | 1 d | 用供应商账单核对本地 usage 估算 |
| 环境断点续跑 | P2 | 3–5 d | 当前只恢复到 `INTERRUPTED`，不能继续未完成环境 |
| 决策理由字段 | 研究依赖 | 需契约变更 | V10 `scenario_v4` 不返回 `decision_reason`；不能伪造 |
| 公开部署 / 鉴权 | 明确不做 | — | 需要独立安全设计，不在 V11 范围 |
| 跨模型排行榜 | 明确不做 | — | 本地成绩榜不是跨模型公平排名 |

## 3. 已完成硬化（本轮补齐）

- 跨进程单实例锁（Windows `msvcrt` / POSIX `fcntl`）；
- Streamlit 锁定到 `[project.optional-dependencies].web`，`uv sync --extra web`；
- 公开动作级失败归因（复用 V10 `MECHANISM_TOOLS`）与 `trace.jsonl` 导出；
- 历史 Provider/Seed 筛选、2–4 局对照、成绩榜决策预算列；
- Windows 干净克隆安装 176.9s（首次）/87–96.5s（复跑）、无 `.env` 自检 7/7；Ubuntu CI 已观察到 success；
- 30 图网页深链映射 30/30；Playwright E2E 通过；
- 演示数据包、启动脚本、桌面快捷方式模板、版本 `0.2.0`。

## 4. 已知体验改进

- 指标表在窄屏仍可能横向滚动；可改为卡片式布局；
- 运行监控只显示最近 20 条动作；长局需要分页或虚拟列表；
- 历史表格未内嵌详情跳转；可加“打开结果”按钮；
- 设置页连接检查仍会产生极少量费用；可增加“只做离线检查”的默认路径；
- 首页 30 张卡片一次性渲染；数据量增大后可分页/懒加载。
