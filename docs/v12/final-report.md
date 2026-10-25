# V12 最终报告：Agent Arena Lab 1.0

- **结论**：`LAB_1_0_OFFLINE_READY`（P0 + P1 + P2 离线交付完成）
- **真实付费矩阵**：`LIVE_VALIDATION_PENDING_APPROVAL`（未获批准，未发出任何请求）
- **执行日期**：2026-10-25
- **起始 HEAD**：`258eadc5039309859fc0385d61650e266e6ab488`
- **平台**：Windows 11 实测；Ubuntu 由 CI 覆盖；macOS `NOT_VERIFIED`
- **未改动**：V8/V9/V10 冻结规则、账本、历史 trace；V11 单局语义

## WHAT：交付了什么

用户可以用**相同模型、相同地图、相同环境 seed、明示预算**比较不同 Agent 架构，
并得到可追溯的失败诊断、交互可视化与可导出报告。

### 一条运行链路

```text
Lab 页面 / CLI / Python SDK
      │
      ▼
ExperimentSpec + preflight（零请求）+ 显式 LiveApproval
      │
      ▼
ExperimentService（矩阵 / 串行队列 / 父子状态 / 实验级预算）
      │  复用 V11 RunService（单 worker / 取消 / 恢复 / 幂等 / 跨进程锁）
      ▼
AgentRunnerV12 ──> AgentPolicy（basic / memory / planning / reflection / external）
      │                    │
      │             PublicObservation + 公开历史 + episode-local 记忆/计划
      │                    │
      │             DecisionGateway（唯一模型出口 + 单一预算汇）
      ▼                    ▼
V10 Environment ── V8Action 公开契约校验
      │
      ▼
V12 result + provenance + agent_events（兼容 V11 manifest/events/result）
      │
      ├──> 配对比较 / 五态指标
      ├──> 证据级诊断 + 两轨迹 Diff
      ├──> 六图 view-model
      └──> runs.csv / metrics.csv / paired_comparison.csv / findings.csv / report.md
```

### 三种执行通道（严格隔离）

| 通道 | Provider | 费用 | 账本 | 用途 |
|---|---|---|---|---|
| `OFFLINE` | `offline_public_policy` | 0 | 不写 | V11 公开启发式演示，**语义未变** |
| `SIMULATED` | `simulated_scripted` | 0 | **不写付费账本** | 跑通完整调用链、对照、诊断、可视化 |
| `LIVE` | `openai_compatible` / `ollama` | 真实 | 写 `runs/web/_ledger/` | 真实模型实验，需 `LiveApproval` |

### 四种架构

| ID | 注入的额外上下文 | 额外请求 |
|---|---|---|
| `basic.v1` | 无（基线锚点，与 V11 `execute_live` 逐项一致） | 0 |
| `memory.v1` | 结构化公开记忆（容量/字符上限，可关闭消融） | 0 |
| `planning.v1` | Planner 子目标 + 计划监控 + 重规划 | 有，全部计费 |
| `reflection.v1` | 公开触发器（无进展/重复被拒/重复动作/空转）触发的有限反思 | 有，全部计费 |

### 产物清单

| 路径 | 内容 |
|---|---|
| `src/agent_arena/lab/` | 13 个模块：契约、注册表、适配器、网关、Runner、父实验、比较、诊断、可视化、报告、SDK、模拟 Provider、演示脚本 |
| `src/agent_arena/ui/lab.py` | Lab 三页（配置 / 监控 / 结果） |
| `examples/custom_agent/` | 第三方 Agent 示例（`test_first.v1`）+ 接入说明 |
| `scripts/verify_v12.py` | 一键离线验收（11 项） |
| `scripts/demo_v12.py` | 零 Key 可复现演示 |
| `scripts/run_v12_matrix.py` | 矩阵 CLI（预检 / 提交 / 汇总） |
| `scripts/build_v12_demo.py` | 生成脱敏演示数据包 |
| `scripts/e2e_lab.py` | 浏览器端到端 |
| `scripts/capture_v12_screenshots.py` | 8 张截图 |
| `docs/v12/` | 审计、ADR、协议、指标归因、接入 API、进度、风险、验证、清单、本报告、截图、演示包 |

## WHY：为什么这样设计

1. **不重造运行服务**：父实验只编排，子局仍是 V11 的 `run`。子局免费获得取消、
   刷新不重复计费、进程重启恢复、单 worker 串行、跨进程锁。
2. **唯一模型出口**：`DecisionGateway` 是策略唯一能调用的模型入口，Planner/Reflection
   的额外请求走同一 `RunBudget`，因此"规划的代价"无法被隐藏。
3. **只操纵一个变量**：提示、动作契约、历史窗口、预算、seed 全部固定，差异只来自
   注入的记忆/计划/反思上下文。
4. **诚实优先**：五态不补零、Provider 错误不进能力分母、样本不足只给描述性统计、
   模拟结果强制标注、每条诊断都指向具体事件。

## RESULT：实测结果

### 质量门禁（Windows 11，全部实跑）

| 命令 | 结果 |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run mypy src` | 302 文件 0 issues |
| `uv run pytest -q` | **1433 passed**（83.48s） |
| `uv run uv lock --check` | 无变更 |
| `git diff --check` | 无输出 |
| `v10.freeze verify` | **9/9 unchanged** |
| `v10.recompute --check` | 1093/1093，0 不一致 |
| `v10.independent_check --check` | 0 违规，回放确定 30/30，seed 互异 30/30 |
| `scripts/verify_v11.py` | 7/7 |
| `scripts/verify_v12.py` | **11/11** |
| `scripts/e2e_web.py --start` | 通过（15 步，24 751 B） |
| `scripts/e2e_lab.py --start` | 通过（父实验 COMPLETED，报告 7 921 B / 122 行） |

### `verify_v12.py` 11 项

`catalog`、`v10_freeze`、`contracts`、`registry`、`simulated_six_maps`（18 局）、
`simulated_all_maps`（30/30）、`parent_child`（6 子局父子一致）、`budget`（实验级截断）、
`visualization`（6 图）、`export_recompute`（可复算）、`redaction`（0 泄漏）。

### 离线演示（`scripts/demo_v12.py`，退出码 0）

- 3 图（MAP-10/22/26）× 1 seed × 3 架构 = 9 局，全部 `COMPLETED`；
- 有效分母 9：成功 1、机制失败 3、预算截尾 5；
- 平均请求：basic 5.67 / memory 8.67 / planning 10.33（Planner 额外请求可见）；
- 首次差异可定位：`MAP-22 seed=0 basic.v1 vs memory.v1 → 第 2 步`；
- 六图 view-model 可用；报告 6 576 字符，含不可比声明。

### 一个自查发现的真实缺陷（已修）

截图审阅时发现 MAP-22 探索图把**被拒绝的 `move`** 画成了"走过的边"（`camp → camp`）。
这会让读者误以为 Agent 探索了不存在的路径。修复：只有位置真正改变才记边，被拒移动
单列 `rejected_moves` 并在页面标注"未改变位置，不计入探索边"。

## KNOWN ISSUES

| 项 | 状态 | 说明 |
|---|---|---|
| 真实 54 局矩阵 | `PENDING_APPROVAL` | 未获付费预算批准；`LiveApproval` 默认未批准，`submit` 直接拒绝 |
| macOS 实机 | `NOT_VERIFIED` | 无可用机器；`.command` 保留 |
| Ollama 实机 | `NOT_VERIFIED` | 本机未运行 Ollama |
| 可访问性自动检测 | 未接入 | 键盘/对比度仍是人工项；有 430px 与深色截图 |
| 移动端真机 | `NOT_VERIFIED` | 只有 430px 视口截图 |
| 浏览器 E2E 进 CI | 已加但 `continue-on-error` | 首次跑需要 `playwright install`，失败不阻断主门禁 |
| Provider 账单对账 | 未做 | 超出 V12 范围 |
| 第三方代码隔离 | 仅本机受信任插件 | 公网任意代码沙箱明确不在范围 |
| 图表形式 | 表格 + 基础折线 | 未引入额外绘图依赖；数值仍可核对原始 trace |

## 数据可信性

- **有效分母**只含 `completed_success` / `mechanism_failure` / `budget_censored`；
  Provider 错误、取消、中断、策略异常**不计入**。
- **配对键**是 `(map_id, environment_seed)`；模型/Provider/模式/规则/指标 schema 任一不一致
  即 `INCOMPARABLE`。
- **五态不补零**：`CENSORED`/`NOT_APPLICABLE`/`UNAVAILABLE`/`INVALID_TRACE` 只计频次。
- **模拟 ≠ 真实**：`mode=simulated` 贯穿 manifest、result、UI、报告；模拟不写付费账本。
- **演示脚本 ≠ Oracle**：`lab/demo.py` 的动作由人工按公开规则编写，默认不加载。

## NEXT（只列最优先 3–5 项）

1. **获得预算批准后跑 Pilot**（3–6 局，覆盖 Basic/Memory/Planning 与至少两图），核对动作
   契约、账单、终态、计划事件与指标；通过后再跑 54 局主矩阵。
2. **macOS 实机验证**：`uv sync --extra web` → `verify_v12.py` → 网页 Lab 冒烟。
3. **Ollama 实机单局**：验证本地模型路径与 `SIMULATED`/`LIVE` 切换。
4. **可访问性自动检测**：接入 axe-core 或等价工具，覆盖对比度与键盘导航。
5. **补跑机制**：为"已中断/未知消费"的子局设计显式补充实验流程（当前只能新建实验）。

## 复现方式

```bash
# 零 API Key：完整离线演示（预检 → 提交 → 对照 → 诊断 → 可视化 → 导出）
uv run python scripts/demo_v12.py

# 一键离线验收
uv run python scripts/verify_v12.py

# 网页
uv run sync --extra web 2>/dev/null || uv sync --extra web
uv run agent-arena web
# → 侧边栏「Lab · 实验配置」→ 一键离线演示 → 「Lab · 结果与对照」

# 浏览器 E2E（需要 playwright）
uv run --with playwright --with streamlit python scripts/e2e_lab.py --start

# 生成演示数据包与截图
uv run python scripts/build_v12_demo.py
uv run --with playwright --with streamlit python scripts/capture_v12_screenshots.py
```

## 截图

| 文件 | 内容 |
|---|---|
| `docs/v12/screenshots/01-home-with-lab.png` | 首页新增 Lab 入口 |
| `docs/v12/screenshots/02-lab-config.png` | 实验配置 + 矩阵 + 预检 |
| `docs/v12/screenshots/03-lab-monitor.png` | 父实验监控 + 子局表 |
| `docs/v12/screenshots/04-lab-results.png` | 结果概览 + 可比性 |
| `docs/v12/screenshots/05-lab-visualization.png` | MAP-22 探索图（仅公开路标） |
| `docs/v12/screenshots/06-lab-evidence.png` | 证据级诊断 |
| `docs/v12/screenshots/07-lab-results-mobile.png` | 430px 窄屏 |
| `docs/v12/screenshots/08-lab-monitor-dark.png` | 深色模式 |

## 完成判据自检

> "在同一张任务地图上，我更换 Agent 架构以后，它的行为、成功率、成本与失败原因
> 究竟有哪些可验证的差异？"

- 行为差异：`pairwise_diff` 给出首次差异步 + 锚点 + 指标增量；
- 成功率差异：有效分母 + 六类互斥分类；
- 成本差异：请求/token/费用/延迟，Planner 额外请求单列；
- 失败原因：18 类证据级诊断，每条指向具体 `decision` 事件；
- 可复现：`experiment.json` 冻结矩阵与指纹，`summary.json` 可从 `runs.csv` 独立复算。

**结论：在离线（SIMULATED）意义上，这个判据成立；在真实模型意义上，仍需预算批准后验证。**
