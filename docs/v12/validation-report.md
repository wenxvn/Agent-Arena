# V12 验证报告

- **执行日期**：2026-10-25
- **HEAD**：`258eadc5039309859fc0385d61650e266e6ab488`（未提交新 commit，工作树含 V12 改动）
- **平台**：Windows 11；Ubuntu 由 GitHub Actions 覆盖；**macOS 未验证**

## 1. 质量门禁（全部实跑）

| 命令 | 实际结果 | 退出码 |
|---|---|---|
| `uv run ruff check .` | `All checks passed!` | 0 |
| `uv run mypy src` | `Success: no issues found in 302 source files` | 0 |
| `uv run pytest -q` | `1433 passed`（耗时 83.48s） | 0 |
| `uv run uv lock --check` | `Resolved 65 packages`（无变更） | 0 |
| `git diff --check` | 无输出 | 0 |
| `uv run python -m agent_arena.v10.freeze verify` | **9/9 根目录 `unchanged`** | 0 |
| `uv run python -m agent_arena.v10.recompute --check` | `{"checks":1093,"maps_covered":30,"match":1093,"mismatch":0}` | 0 |
| `uv run python -m agent_arena.v10.independent_check --check` | `{"maps":30,"seed_instances":144,"violations":0,"seed_distinct_ok":30,"deterministic_ok":30}` | 0 |
| `uv run python scripts/verify_v11.py` | `ok: true, failed: 0`（7 项） | 0 |
| `uv run python scripts/verify_v12.py` | `ok: true, failed: 0`（**15 项**） | 0 |
| `uv run python scripts/a11y_v12.py --browser --start` | `ok: true`；critical 0 / serious 0 / moderate 0 | 0 |

### pytest 增长

| 阶段 | 用例数 |
|---|---|
| V12 起点（HEAD） | 1252 passed + **1 failed**（`test_home_shows_per_map_run_history`） |
| V12 离线交付 | 1433 passed |
| 可访问性 + 补充实验 | 1469 passed |
| DCR-V12-01 契约补丁 + 版本复跑 | **1489 passed** |

## 2.0 真实模型执行（MiMo）

| 项 | 值 |
|---|---|
| 授权 | 用户明确指示"可以用 API" |
| 实验数 | 5（Pilot / 主矩阵 / 契约修复复跑 / 补充 / 探针） |
| 局数 | 71 |
| 请求 | 2 103 |
| 结算 | **CNY ¥1.82140020** |
| 未知消费 | **¥0.00** |
| 批准上限 | ¥6.00（未超） |
| 账本一致性 | `run_started` 71 = `run_settled` 71；每局 `result.usage` 与账本一致 |

明细见 `mimo-results.md`；原始报告与 CSV 在 `docs/v12/real-runs/`。

> 起点那 1 个失败是测试自身缺陷：`_prepare_runs` 用 `service.list_runs()[0]` 取"刚创建的第二局"，
> 而 `created_at` 只精确到秒，同秒两局的排序不稳定。改为直接使用第二个 `run_id`。
> 该修复不改变任何运行时语义，且与 V12 改动无关（属于 V11 遗留基线缺陷）。

## 2. `verify_v12.py` 逐项结果

| 检查项 | 结果 | 细节 |
|---|---|---|
| `catalog` | PASS | 30 图、6 重点图、30 组唯一 rule/metric hash |
| `v10_freeze` | PASS | 7 根目录（不含 runs）无漂移 |
| `contracts` | PASS | 矩阵 2、指纹 `6b6dae34f94b`；非法臂与模拟冒充真实均被拒 |
| `registry` | PASS | 4 个内置策略、6 种消融配置指纹 |
| `simulated_six_maps` | PASS | 18 局（6 图 × 3 架构）、58 个 agent 事件、零泄漏 |
| `simulated_all_maps` | PASS | 30/30 图各跑通一局 |
| `parent_child` | PASS | 6 子局全完成、父子状态逐局一致、重复提交不新增 |
| `budget` | PASS | 实验请求上限触发 `PARTIAL`、只完成 1 局 |
| `visualization` | PASS | 6 图 view-model 全部可用、类型正确、无隐藏真值 |
| `export_recompute` | PASS | 6 行 runs.csv、39 行 metrics.csv、有效分母可复算 |
| `redaction` | PASS | 8 个导出文件、0 密钥回显 |
| `a11y` | PASS | 22 个 token × 2 方案全部 ≥ AA；焦点样式合规 |
| `theme_tokens_in_css` | PASS | 7 个 `--aa-*-text` 都真实出现在样式表里 |

## 2.1 可访问性审计（`scripts/a11y_v12.py --browser --start`）

| 层 | 结果 |
|---|---|
| 主题对比度 | 22 个 token（11 文字 + 10 填充 + 2 正文）× 2 方案，0 失败 |
| 焦点样式 | 无 `outline` 抑制；存在 `:focus-visible` |
| 浏览器 DOM（6 页） | 0 critical / 0 serious / 0 moderate |
| 键盘（每页 12 次 Tab） | 焦点全部前进、全部可见；0 陷阱 |
| 浅色 / 深色 | 两者都 0 问题 |

审计过程中修复的 4 个真实缺陷（详见 `metrics-and-attribution.md` §6）：

1. `--aa-warning` 白底 2.65:1（低于 3:1），其余 tone 文字色低于 AA 4.5:1 → 拆出
   `--aa-*-text` 文字 token（浅/深两套）；
2. 标题层级 `h1 → h3` 跳级 → 区块标题改 `st.header`（h2），视觉样式迁移到 h2；
3. `st.json` 工具栏的无名称图标按钮 → 改为表格；
4. 审计脚本自身的 2 处误报（折叠 expander、同名锚点）→ 修正可见性与去重判定。

**已知框架限制**：`<html lang>` 固定为 `en`（Streamlit 前端控制），已单列不计入通过。

## 3. 浏览器端到端

| 脚本 | 结果 | 关键数据 |
|---|---|---|
| `scripts/e2e_web.py --start`（V11 回归） | **通过** | 离线运行 15 步、下载 JSON 24 751 B |
| `scripts/e2e_lab.py --start`（V12 新增） | **通过** | 父实验 `COMPLETED`、报告 7 921 B / 122 行 |

`e2e_lab.py` 覆盖：首页 → Lab 配置 → 一键离线演示入队 → 监控（等到 `COMPLETED`）→
结果页（`有效分母`、`SIMULATED`、`COMPARABLE`）→ 导出 → 下载报告并校验内容。

浏览器：系统 Chrome（本地）；CI 环境回退 Playwright 自带 chromium。

## 4. 与 V11 的回归

| 项 | 结果 |
|---|---|
| V11 六页 UI 冒烟 | 通过（`tests/test_web_ui_smoke.py` 全部） |
| V11 单局离线 30 图 | 通过（`verify_v11.py`） |
| V11 服务层（取消/恢复/幂等/预算/路径） | 通过 |
| V11 导出格式 | 通过（`test_web_export.py`） |
| V11 浏览器 E2E | 通过（见 §3） |
| V11 `v10_action_loop` 语义 | **未改动**；Lab 走独立分派分支 |

## 5. 内存 / 费用 / 兼容边界

| 项 | 结论 |
|---|---|
| 模拟模式费用 | 恒为 `0`，且**不写** `runs/web/_ledger/`（`test_simulated_mode_writes_no_global_ledger`） |
| 真实模式费用 | 由 `RunBudget` 硬门禁；未知 usage fail-closed |
| Planner/Reflection 额外请求 | 计入 `usage.requests` 与 `usage.purposes`（`test_planning_extra_requests_are_counted`） |
| 旧 V11 manifest 读取 | 通过（`agent_config`/`experiment_id` 可空） |
| 旧 V11 结果读取 | 通过（`lab.compare.run_record` 容忍缺字段） |
| 单局内存 | 记忆容量默认 24 条、渲染 ≤1200 字符；历史窗口 5 条 |
| 大 CSV | 2 000 行导出通过（`test_large_csv_export_is_streamed_and_parsable`） |
| 损坏 JSONL | 跳过并计数，回放仍可读（`test_corrupt_events_line_is_tolerated`） |

## 6. 安全 / 隐私 / 冻结审核

| 检查 | 结果 |
|---|---|
| 密钥扫描（导出 8 文件、报告、UI 状态） | 0 命中 |
| 隐藏真值键扫描（`sealed_truth`/`truth_seal`/`judge_state`/`oracle`） | 0 命中 |
| 30 图执行后结果泄漏扫描 | 0 命中 |
| 策略可见上下文泄漏扫描 | `assert_public` 强制；测试覆盖 |
| V8/V9 冻结根目录 | 9/9 unchanged |
| V10 账本/历史 trace | 未读写 |
| `runs/` 是否入库 | 否（`.gitignore`） |

## 7. 未验证项（诚实披露）

| 项 | 状态 | 原因 |
|---|---|---|
| macOS 实机 | `NOT_VERIFIED` | 用户指示暂缓 |
| Ollama 实机 | `NOT_VERIFIED` | 用户指示暂缓 |
| MAP-22 记忆假设 | **不可回答** | DCR-V12-02：`route_recall` 键名口径与公开信息未对齐 |
| MAP-30 能力 | **不可回答** | 8/9 局在 90 请求内截尾 |
| 反思独立小矩阵 | NOT_RUN | 需单独预算批准 |
| Provider 账单对账 | 未做 | 超出 V12 范围 |
| `<html lang>` | 框架限制 | Streamlit 前端固定 `en` |
| 移动端真机 | `NOT_VERIFIED` | 只有 430px 视口截图 |
