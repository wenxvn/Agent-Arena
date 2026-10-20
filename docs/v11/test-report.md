# V11 测试报告

- 执行环境：Windows 11 10.0.26200（x64）、Python 3.13.3、uv 0.13.3、Streamlit 1.66.0
- 起始 HEAD：`eb2f64a281677a0fce881769a6592cce1be6f7d9`
- 最终 HEAD / 提交：见 `final-report.md` 与 `git log`

## 1. 质量门禁

| 命令 | 结果 | 退出码 |
|---|---|---:|
| `uv run ruff check .` | All checks passed | 0 |
| `uv run mypy src` | 273 source files，0 issues | 0 |
| `uv run pytest -q` | **1231 passed** | 0 |
| `uv run uv lock --check` | Resolved 36 packages | 0 |
| `git diff --check` | 无输出 | 0 |
| `uv run python -m agent_arena.v10.freeze verify` | 9/9 unchanged | 0 |
| `uv run python -m agent_arena.v10.recompute --check` | 1093/1093 match，30 图 | 0 |
| `uv run python -m agent_arena.v10.independent_check --check` | 0 violations，144 seed 实例 | 0 |

改动前基线：`1157 passed in 103.62s`。新增 74 个 V11 测试（Web 服务、执行、预算、catalog、导出、历史、UI 冒烟、自检、CLI）。

## 2. 一键自检（零 API）

`uv run python scripts/verify_v11.py`：

| 检查 | 结果 | 耗时 |
|---|---|---:|
| catalog（30 图 / 10 世界 / 无泄漏键） | pass | 0.06s |
| offline_matrix（30 图真实离线运行 + 回放 + CSV） | pass，30/30 success，473 步 | 28.7s |
| budget（请求 / 未知 usage / 费用） | pass | <0.01s |
| redaction（密钥模式、Provider 状态） | pass | <0.01s |
| paths（遍历、run_id、符号链接） | pass | <0.01s |
| export_consistency（JSON/CSV 字段与步数） | pass | 0.4s |
| service_recovery（RUNNING → INTERRUPTED） | pass | 0.3s |

报告：`runs/v11/selfcheck.json`。

## 3. 离线端到端

- 30/30 图可选择、可启动、可回放、可导出；
- 总步数 473，全部 `success`（公开启发式策略；不代表模型能力）；
- 每图 JSON 回放与 CSV 行数一致；
- 导出扫描未出现 `sealed_truth` / `judge_state`；
- `docs/v11/map-ux-checklist.md` 逐图留痕。

## 4. 真实 MiMo 冒烟

| # | run_id | 地图 | 结果 | 决策 | 请求 | 输入 / 输出 token | 结算 CNY |
|---|---|---|---:|---:|---:|---|---:|
| 1 | `web-20261020T024847Z-38111ee4` | MAP-01 | FAILED / `OXYGEN_SUPPLY_INTERRUPTION_LIMIT` | 4 | 4 | 2,465 / 60 | 0.00139332 |
| 2 | `web-20261020T024923Z-849e9e0d` | MAP-19 | FAILED / `THERMAL_RUNAWAY` | 8 | 8 | 6,430 / 120 | 0.00579192 |
| 3 | `web-20261020T024951Z-3e3249a7` | MAP-30 | BUDGET_REACHED / `decision_budget_exhausted` | 46 | 46 | 56,646 / 1,276 | 0.03919032 |

- 已记录请求：58；已结算：**CNY 0.04637556**；
- 未知预留：**CNY 0.073728**（修复前 4 次未落盘请求的上界）；
- V11 总占用：**CNY 0.12010356**，低于 ¥3 上限；
- 0 unknown spend（已记录局）；0 自动重试；0 成功（均为环境规则/预算终局，未改规则凑成功）。

修复前失败尝试 `web-20261020T024505Z-d221e453` 保留在 `runs/v11/web/`，原因与修复见 `safety-and-budget.md` §3。

## 5. 浏览器实测

- 实际启动：`uv sync --extra web` 后 `uv run agent-arena web --headless --port 8501`；
- 页面：首页、挑战配置、运行监控、结果与回放、历史与对照、设置与帮助；
- 验证内容：中文渲染、30 图卡片、MAP-30 真实结果（46 步、¥0.0392、五态表）、运行时间线、导出按钮、Provider 状态、历史对照；
- 截图：`docs/v11/screenshots/`；
- 页面刷新不重复执行；`st.fragment` 自动刷新只读 manifest。

### 自动化浏览器 E2E（Playwright + 系统 Chrome）

```bash
uv run --with playwright --with streamlit python scripts/e2e_web.py --start
```

流程：首页 → 离线演示 → 运行监控 → 查看结果 → 下载回放 JSON → 深链历史页。使用临时 `runs/web`，不污染本机数据。实测输出：

```json
{"ok": true, "state": "SUCCEEDED", "run_id": "web-20261020T061702Z-084056f6",
 "steps": 15, "download_bytes": 24307}
```

该 E2E 发现并修复了两个真实 UI 缺陷：Streamlit radio widget key 在组件实例化后被写入导致导航失效（改为 `pending_nav` + rerun 前写入），以及单局历史页过早返回导致成绩榜不显示。

## 6. 修复的缺陷

1. **Decimal 序列化**：`RunBudget.snapshot()` 的 limits 含 `Decimal`，写 JSONL 失败；改为字符串 + 存储层 `default=str`，新增回归测试与服务层集成测试。
2. **Windows manifest 读竞争**：原子替换瞬间读取可能 `PermissionError`；增加 20 次短重试。
3. **Streamlit 弃用/Arrow 混合类型**：`use_container_width=True` → `width="stretch"`；指标“值”列统一字符串，避免 Arrow 转换回退。
4. **导航失效**：`st.session_state["nav"]` 在 radio 实例化后写入被 Streamlit 拒绝；改为 `pending_nav`，下一次 rerun 创建组件前写入。
5. **重复点击复用旧运行**：快速开始/配置页的 idempotency nonce 永不变化；创建成功后递增 nonce，下一次点击生成新 run_id。
6. **单局历史页无成绩榜**：对照区提前 `return`；改为只跳过对照，继续渲染本地成绩榜。
7. **UI 截断**：首页“需自备 API”、费用小数、token 过长、历史表列过多；改为“需 API”、`¥0.0392`、k 缩写、精简列。
8. **指标表缺范围**：补 `valid_range`，公式移到折叠区；`None` 显示为“—”，`CENSORED` 不写 0。

## 7. OS 覆盖

| 系统 | 状态 |
|---|---|
| Windows 11 | **已实测**（安装、启动、离线 30 图、真实 3 局、浏览器页面） |
| Ubuntu | CI 配置为 `ubuntu-latest`，本次未在本机执行；列为未验证 |
| macOS | 未执行；启动脚本与文档已提供，列为未验证 |

不虚报跨系统通过；全量 CI 需要 GitHub Actions 实际运行结果。

## 8. 未覆盖 / 已知缺口

- 未做自动化浏览器 E2E（截图与手工导航为主）；
- 未做移动端真机测试；
- 未做 Provider 账单对账（本地只有 usage 估算/结算）；
- 未做断点续跑环境状态（只恢复为 `INTERRUPTED`）；
- `decision_reason` 在 V10 契约中不存在，页面显示“—”。
