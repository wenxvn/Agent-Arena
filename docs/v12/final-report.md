# V12 最终报告：Agent Arena Lab 1.0

- **结论**：`LAB_1_0_READY`（P0 + P1 + P2 全部交付，真实模型矩阵已执行）
- **真实付费实验**：**已获用户授权并完成** —— Pilot 6 局 + 主矩阵 54 局 + 契约修复复跑 9 局，
  合计 **CNY ¥1.82140020**，**0 未知消费**，未超 ¥6.00 批准上限
- **执行日期**：2026-10-25
- **起始 HEAD**：`258eadc5039309859fc0385d61650e266e6ab488`
- **平台**：Windows 11 实测；Ubuntu 由 CI 覆盖；macOS / Ollama 按用户指示暂缓
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

### 真实模型（MiMo，2026-10-25）

| 实验 | 局数 | 状态 | 请求 | 结算 CNY | 未知消费 |
|---|---:|---|---:|---:|---:|
| Pilot | 6 | COMPLETED | 131 | 0.09949940 | 0 |
| 主矩阵 v1（六图 × 3 seed × 3 架构） | 54 | COMPLETED | 1 507 | **1.47181116** | 0 |
| MAP-22 契约修复复跑 | 9 | COMPLETED | 424 | 0.21606796 | 0 |
| 补充（取消局） | 1 | COMPLETED | 41 | 0.03376040 | 0 |
| 早期探针 | 1 | COMPLETED | — | 0.00026128 | 0 |
| **合计** | **71** | — | **2 103** | **1.82140020** | **0** |

主矩阵结果（每条件 1 局，描述性）：

| 实验臂 | 局 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 被拒动作 | 非法动作 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `basic.v1` | 18 | 18 | 7 | 0.389 | 30.2 | 30.2 | 0.0205 | 103 | 0 |
| `memory.v1` | 18 | 17 | 8 | 0.471 | 27.4 | 27.4 | 0.0331 | 85 | 0 |
| `planning.v1` | 18 | 18 | 9 | 0.500 | 24.7 | 26.1 | 0.0282 | 20 | 1 |

**逐图**：

| 地图 | basic | memory | planning | 判定 |
|---|---|---|---|---|
| MAP-08 | 3/3 | 3/3 | 3/3 | 天花板（测不出差异） |
| MAP-16 | 0/3 | 0/3 | **2/3** | 有梯度，planning 请求 3 倍 |
| MAP-18 | 0/3 | **2/3** | 0/3 | 有梯度，方向与 MAP-16 相反 |
| MAP-22 | 1/3 | 0/3 | 1/3 | **接口假象**（DCR-V12-01），作废 |
| MAP-26 | 3/3 | 3/3 | 3/3 | 天花板 |
| MAP-30 | 0/3 | 0/3 | 0/3 | 地板 + 8 局截尾 |

**不做显著性断言**：18 局、每条件 1 局、3 seed；成功率 7/8/9 的差异不足以支持
"某架构更好"。可说的是**代价结构**：memory 平均最贵（记忆注入抬高输入 token 而请求数不变），
planning 额外 Planner 请求可见但总费用低于 memory，planning 的被拒动作最少。

### 一个真实的接口缺陷（发现 → 定位 → 修复 → 复测）

主矩阵暴露出 MAP-22 的 `write_memory` **96.2% 被拒**（175/182，`INVALID_MEMORY_PAYLOAD`）。
根因：公开契约把 `facts: list[dict]` 渲染成 `[{"<key>": <value>}]`，只说明"是字典"，
没说明必须恰好是 `{"key": str, "value": str}`。模型写出语义正确、结构不合规的内容。

- 记为 **DCR-V12-01**（接口假象，非能力差异）；
- 修复：`lab/contract_v12.py`（`v12-contract-1`）只对含 `facts` 的图追加精确形状说明，
  写入 `provenance.contract_augmentation`，改变 `prompt_hash` → 跨版本不配对；
  **V10/V11 与环境校验一律不动**；
- 复测：拒绝率 **96.2% → 0%**，MAP-22 成功 2/9 → 4/9；
- 残余问题：`route_recall` 仍全为 `NOT_APPLICABLE`，因为模型用的键名（`at_sign` /
  `came_from` / `path_to_here`）不在指标口径（`bearing` / `path_state`）内 →
  **DCR-V12-02**。结论：**MAP-22 的"记忆是否减少迷路"本轮仍不可回答**。

### 一次真实事故（进程被杀）

主矩阵首跑时 CLI 默认等待 1800 秒，54 局跑不完 → 进程退出 → 执行线程被杀，
留下 1 个孤儿 `QUEUED` 子局，而真实 run 已被收尾为 `CANCELLED`。修复：

- `_reconcile_children()` 以磁盘 run manifest 为准刷新父实验链接；
- `--timeout` 默认 0（等到终态），新增 `--resume` / `--rerun-of`；
- 回归测试 `test_stale_child_link_is_reconciled_from_real_run_state`；
- 用 `--resume` 补齐剩余 19 局，最终 54/54，无重复计费。

### 质量门禁（Windows 11，全部实跑）

| 命令 | 结果 |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run mypy src` | 304 文件 0 issues |
| `uv run pytest -q` | **1487 passed** |
| `uv run uv lock --check` | 无变更 |
| `git diff --check` | 无输出 |
| `v10.freeze verify` | **9/9 unchanged** |
| `v10.recompute --check` | 1093/1093，0 不一致 |
| `v10.independent_check --check` | 0 违规，回放确定 30/30，seed 互异 30/30 |
| `scripts/verify_v11.py` | 7/7 |
| `scripts/verify_v12.py` | **15/15** |
| `scripts/a11y_v12.py --browser --start` | 0 critical / 0 serious / 0 moderate |
| `scripts/e2e_web.py --start` | 通过（15 步，24 751 B） |
| `scripts/e2e_lab.py --start` | 通过（父实验 COMPLETED，报告 7 921 B） |

### 可访问性（新增自动审计）

修复了 4 个真实缺陷：`--aa-warning` 白底 2.65:1（低于 3:1）→ 拆出 `--aa-*-text`
文字 token（浅/深两套，全部 ≥ 4.5:1）；标题层级 `h1 → h3` 跳级 → 区块标题改 `st.header`；
`st.json` 工具栏无名称图标按钮 → 改表格；审计脚本自身 2 处误报 → 修正可见性与去重判定。

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
| MAP-22 记忆假设 | **不可回答** | 契约修复后拒绝率归零，但 `route_recall` 仍 N/A（DCR-V12-02）；需 V13 决策 |
| MAP-08 / MAP-26 | 天花板 | 三臂 9/9 成功，测不出架构差异 |
| MAP-30 | 地板 + 截尾 | 0/9，8 局在 90 请求内未到法庭提交；需更高预算的独立实验 |
| 反思独立小矩阵 | NOT_RUN | 需单独预算批准；未混入主矩阵 |
| 样本量 | 描述性 | 每条件 1 局、3 seed；不作显著性断言 |
| macOS 实机 | 按用户指示暂缓 | `NOT_VERIFIED` |
| Ollama 实机 | 按用户指示暂缓 | `NOT_VERIFIED` |
| Provider 账单对账 | 未做 | 本地按登记价目与返回 usage 计算；未与 Provider 后台对账 |
| `<html lang>` | 框架限制 | Streamlit 前端固定 `en`，应用层无法覆盖 |
| 浏览器 E2E 进 CI | 已加但 `continue-on-error` | 首次跑需 `playwright install` |
| 第三方代码隔离 | 仅本机受信任插件 | 公网任意代码沙箱不在范围 |

## 数据可信性

- **有效分母**只含 `completed_success` / `mechanism_failure` / `budget_censored`；
  Provider 错误、取消、中断、策略异常**不计入**（主矩阵 54 局 → 有效分母 53）。
- **配对键**是 `(map_id, environment_seed)`；模型/Provider/模式/规则/指标 schema 任一不一致
  即 `INCOMPARABLE`。DCR-V12-01 修复改变了 `prompt_hash`，因此复跑与主矩阵**不配对**。
- **五态不补零**：`CENSORED`/`NOT_APPLICABLE`/`UNAVAILABLE`/`INVALID_TRACE` 只计频次。
- **模拟 ≠ 真实**：`mode=simulated` 贯穿 manifest、result、UI、报告；模拟不写付费账本。
- **演示脚本 ≠ Oracle**：`lab/demo.py` 的动作由人工按公开规则编写，默认不加载。
- **接口假象单独归类**：`memory_payload_rejected`（`interface_not_behavior`）与
  `memory_key_not_in_metric`（`metric_coverage_not_behavior`）都不当作能力差异。
- **不做显著性断言**：每条件 1 局、3 seed，只给描述性对照。

## NEXT（只列最优先 5 项）

1. **DCR-V12-02 决策**：MAP-22 的 `route_recall` 口径与公开信息对齐（新增版本命名空间，
   不覆盖 V10 历史值）；对齐后重跑 MAP-22 才能回答记忆假设。
2. **MAP-30 提高预算重测**：当前 0/9 且 8 局截尾，是"没测完"而不是"做不到"；
   需要 ≥200 请求/局的独立实验。
3. **增加重复次数**：对有梯度的 MAP-16 / MAP-18 各加 2–3 个 replicate，才可能谈稳定性。
4. **macOS / Ollama 实机**：按用户指示暂缓，恢复后跑 `verify_v12.py` + 网页冒烟。
5. **Provider 账单对账**：把本地登记价目估算与 Provider 后台账单核对一次。

## 复现方式

```bash
# 零 API Key：完整离线演示
uv run python scripts/demo_v12.py

# 一键离线验收（15 项）
uv run python scripts/verify_v12.py

# 可访问性审计（离线 + 浏览器）
uv run python scripts/a11y_v12.py --browser --start

# 网页
uv sync --extra web
uv run agent-arena web

# 真实矩阵（需预算批准；--timeout 0 表示等到终态）
uv run python scripts/run_v12_matrix.py --maps MAP-22 MAP-26 \
    --agents basic.v1 memory.v1 planning.v1 --seeds 0 \
    --provider openai_compatible --model mimo-v2.6-flash \
    --decisions 90 --requests 90 --per-run-cost 0.5 \
    --experiment-requests 4860 --experiment-cost 6.0 \
    --approval-cap 6.0 --i-have-budget-approval --submit

# 续跑 / 版本复跑 / 补充实验
uv run python scripts/run_v12_matrix.py --resume <experiment_id> --submit
uv run python scripts/run_v12_matrix.py --rerun-of <experiment_id> --conditions "..." --submit
uv run python scripts/run_v12_matrix.py --supplement-of <experiment_id> --list-candidates
```

## 真实结果档案（可审计、已脱敏）

| 文件 | 内容 |
|---|---|
| `docs/v12/real-runs/main-54-report.md` | 54 局主矩阵的可读报告 |
| `docs/v12/real-runs/main-54-runs.csv` | 54 行逐局明细（含 run_id / 类别 / 费用 / hash） |
| `docs/v12/real-runs/main-54-paired.csv` | 配对对照（含 verdict 与不可比原因） |
| `docs/v12/real-runs/map22-contract-fixed-report.md` | DCR-V12-01 修复后的 9 局报告 |
| `docs/v12/real-runs/pilot-report.md` | Pilot 6 局报告 |
| `docs/v12/mimo-results.md` | 汇总、逐图结论、成本与事故记录 |
| `docs/v12/dcr/DCR-V12-01.md` | `facts` 契约缺陷 |
| `docs/v12/dcr/DCR-V12-02.md` | `route_recall` 口径缺陷 |

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

| 问题 | 本轮是否回答 | 依据 |
|---|---|---|
| 行为差异 | **是** | `pairwise_diff` 给出首次差异步 + 锚点 + 指标增量 |
| 成功率差异 | **是（描述性）** | 7/8/9 局，18 局样本，3 seed |
| 成本差异 | **是** | memory 最贵 0.0331，planning 0.0282，basic 0.0205（元/局） |
| 失败原因 | **是** | 139 条证据级诊断，每条指向具体 `decision` 事件 |
| MAP-22 记忆假设 | **否** | 契约修复后仍受 DCR-V12-02 阻塞（键名口径） |
| MAP-30 能力 | **否** | 8/9 局截尾，属于"没测完"而非"做不到" |
| 可复现 | **是** | `experiment.json` 冻结矩阵与指纹；`summary.json` 可从 `runs.csv` 独立复算 |

**结论：判据在"可比较的图"上成立**（MAP-16 / MAP-18 有梯度、MAP-08 / MAP-26 天花板、
成本结构清楚）；在 MAP-22 与 MAP-30 上不成立，但原因已被证据定位到具体的接口/预算问题，
不是含糊的"模型不行"。这是本轮最重要的诚实结论。
