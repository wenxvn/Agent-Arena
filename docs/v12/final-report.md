# V12 最终报告：Agent Arena Lab 1.0

- **结论**：`LAB_1_0_READY`（P0 + P1 + P2 全部交付；真实模型矩阵已执行）
- **真实付费实验**：**已获用户授权并完成** —— 20 个实验、**159 局**、
  **CNY ¥5.43680012**、**0 未知消费**、未超 ¥6.00 批准上限
- **执行日期**：2026-10-25 / 2026-10-26
- **起始 HEAD**：`258eadc5039309859fc0385d61650e266e6ab488`
- **平台**：Windows 11 实测；Ubuntu 由 CI 覆盖；macOS / Ollama 按用户指示暂缓
- **未改动**：V8/V9/V10 冻结规则、账本、历史 trace；V11 单局语义

## WHAT：交付了什么

用户可以用**相同模型、相同地图、相同环境 seed、明示预算**比较不同 Agent 架构，
并得到可追溯的失败诊断、交互可视化与可导出报告。

除主流程外，还交付了四类**衍生实验**（都新建独立实验、都不动原实验）：

| 类型 | 用途 | 触发条件 |
|---|---|---|
| 补充（supplement） | 补齐分母 | 中断 / Provider 错误 / 未知消费 / 取消 / 未执行 |
| 版本复跑（version rerun） | 换契约/提示后重测 | 修好接口缺陷 |
| 预算扩展（budget extension） | 解除截尾 | 请求/token/费用任一触顶 |
| 重复（replicate） | 测量抽样波动 | 需要判断差异是否稳定 |

策略侧还提供一个**消融/增强开关** `memory.v1` 的 `route_log`（默认关闭）：
每走 2 步把累积方位写成一条 `path_state`，动作不调用模型（0 请求），
用于检验"跨阶段路线记录"这一假设。

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
| `memory.v1` | 结构化公开记忆（容量/字符上限，可关闭消融；`route_log` 可选） | 0 |
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

### 真实模型（MiMo，2026-10-25/26）

| 实验 | 局数 | 成功 | 机制失败 | 截尾 | 取消 | 请求 | 结算 CNY |
|---|---:|---:|---:|---:|---:|---:|---:|
| Pilot | 6 | 3 | 0 | 3 | 0 | 131 | 0.09949940 |
| 主矩阵 v1（六图 × 3 seed × 3 架构） | 54 | 24 | 19 | 10 | 1 | 1 507 | **1.47181116** |
| 主矩阵 · 补充（取消局） | 1 | 1 | 0 | 0 | 0 | 41 | 0.03376040 |
| MAP-22 契约修复（`contract-1`） | 9 | 4 | 5 | 0 | 0 | 424 | 0.21606796 |
| MAP-22 口径对齐（`contract-2`） | 9 | 0 | 9 | 0 | 0 | 493 | 0.23872508 |
| MAP-22 路线日志（`route_log`） | 3 | 1 | 2 | 0 | 0 | 123 | 0.14253072 |
| MAP-30 预算扩展（180 请求） | 9 | 0 | 4 | 5 | 0 | 935 | 1.09918720 |
| MAP-30 token 扩展（600k） | 9 | 0 | 2 | 7 | 0 | 1 269 | 1.49856088 |
| MAP-16 seed 3（+补充） | 4 | 1 | 2 | 0 | 1 | 22 | 0.01478284 |
| MAP-18 seed 3、4 | 6 | 3 | 3 | 0 | 0 | 57 | 0.07019220 |
| 重复实验 A（MAP-16/18 × 3 seed） | 18 | 4 | 14 | 0 | 0 | 224 | 0.21588532 |
| 重复实验 B（同条件再跑） | 18 | 3 | 14 | 1 | 0 | 276 | 0.23927140 |
| 探针（不参与分析） | 1 | 1 | 0 | 0 | 0 | 3 | 0.00026128 |
| memory on/off 消融（MAP-18） | 4 | 0 | 4 | 0 | 0 | 42 | 0.05185988 |
| planning on/off 消融（MAP-16） | 4 | 1 | 3 | 0 | 0 | 54 | 0.03807000 |
| reflection on/off 消融（MAP-16） | 4 | 2 | 2 | 0 | 0 | 40 | 0.00633440 |
| **合计** | **159** | **48** | **83** | **26** | **2** | **5 641** | **5.43680012** |

主矩阵结果（每条件 1 局，描述性）：

| 实验臂 | 局 | 有效分母 | 成功 | 成功率 | 平均决策 | 平均请求 | 平均费用 CNY | 被拒动作 | 非法动作 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `basic.v1` | 18 | 18 | 7 | 0.389 | 30.2 | 30.2 | 0.0205 | 103 | 0 |
| `memory.v1` | 18 | 17 | 8 | 0.471 | 27.4 | 27.4 | 0.0331 | 85 | 0 |
| `planning.v1` | 18 | 18 | 9 | 0.500 | 24.7 | 26.1 | 0.0282 | 20 | 1 |

**逐图（合并种子扩展后）**：

| 地图 | basic | memory | planning | 判定 |
|---|---|---|---|---|
| MAP-08 | 3/3 | 3/3 | 3/3 | 天花板（测不出差异） |
| MAP-16 | 0/4 | 0/4 | **3/4** | 唯一正向梯度；planning 请求约 3 倍 |
| MAP-18 | 0/4 | **2/5** | 0/5 | 有梯度，方向与 MAP-16 相反 |
| MAP-22 | 1/3 | 0/3 | 1/3 | **接口假象**（DCR-V12-01），作废 |
| MAP-26 | 3/3 | 3/3 | 3/3 | 天花板 |
| MAP-30 | 0/3 | 0/3 | 0/3 | 截尾；扩展后见下 |

**不做显著性断言**。而且有两条更硬的证据：

1. **同条件重复的结局翻转率**：2 次观测 4/18（22.2%），3 次观测 3/12（25.0%）；另 6 组 `memory.v1` 因默认配置键变化跨版本，已按 DCR-V12-06 排除；
2. 3 次观测里**唯一稳定成功的条件**是 `planning.v1` 在 MAP-16 seed 1 的 **3/3**
   （代价是请求数约 3 倍）；`memory.v1` 在 MAP-18 的两个 seed 是 2/3（部分稳定）；
   其余 12 个条件全为 0/3。

在这些图上，单个条件的 1 次运行**不足以判断**架构优劣。

可说的是**代价结构**：memory 平均最贵（记忆注入抬高输入 token 而请求数不变），
planning 额外 Planner 请求可见但总费用低于 memory，planning 的被拒动作最少。

### 三个真实测量缺陷（发现 → 定位 → 修复 → 复测）

**DCR-V12-01（接口）**：MAP-22 的 `write_memory` **96.2% 被拒**（175/182，
`INVALID_MEMORY_PAYLOAD`）。根因：公开契约把 `facts: list[dict]` 渲染成
`[{"<key>": <value>}]`，没说明必须恰好是 `{"key": str, "value": str}`。
修复：`lab/contract_v12.py`（`v12-contract-1`）只对含 `facts` 的图追加精确形状说明，
写入 provenance，改变 `prompt_hash` → 跨版本不配对；V10/V11 与环境校验不动。
复测：拒绝率 **96.2% → 0%**。

**DCR-V12-02（口径）**：`route_recall` 只读 `key ∈ {bearing, path_state}`，
公开规则没表达。修复：`v12-contract-2` 给出键名建议 + 新增
`v12.projection.route_recall`（键名宽容的**研究投影**，独立命名空间）。
复测：`map22.v10.route_recall` 首次变成 `VALID`（6/9）。

**DCR-V12-03（策略）**：键名修好之后暴露的真问题——模型只写 **1–4** 个方位，
而真实路线 **22–44** 步，`route_recall` 只有 0.0–0.045。这不是接口问题，
是"跨阶段状态维护"能力本身的表现。

**验证**：给 `memory.v1` 加了一个默认关闭的策略变量 `route_log`（每走 2 步把累积
方位写成一条 `path_state`，**不调用模型**）。MAP-22 三局：`route_recall`
**0.0 → 0.4545 / 0.75 / 1.0**，seed 2 直接通关（`wasted_moves` 34 → 8）。
假设成立：缺的不是"记忆通道"，而是"按步记录路线的策略"。

**DCR-V12-04（预算）**：MAP-30 的"地板"其实是**约束阶梯**——
90 请求 → 200k 输入 token → ¥0.20 单局费用，每抬一档就换一个瓶颈。
抬到 180 请求后 **4/9 局真的走到法庭并给出 `ACCUSATION_REJECTED`**，
这是真实机制失败，不是"没测完"。

### 三次真实事故（均已修复并有回归测试）

1. CLI 默认 1800s 超时 → 进程退出 → 执行线程被杀 → 孤儿 `QUEUED` 子局：
   `_reconcile_children` 以磁盘 run 为准 + `--timeout 0` + `--resume`；
2. 扩展脚本一次提交两个实验 → `ExperimentBusy` + 第一个子局被取消：
   改为串行提交，用 `supplement` 重跑被取消的局；
3. **改完契约后 `--rerun-of` 静默返回旧实验**（幂等键不含代码版本）：
   `ExperimentSpec.runtime_version` 参与指纹，回归测试
   `test_runtime_version_is_part_of_experiment_identity`。

### 质量门禁（Windows 11，全部实跑）

| 命令 | 结果 |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run mypy src` | 306 文件 0 issues |
| `uv run pytest -q` | **1525 passed** |
| `uv run uv lock --check` | 无变更 |
| `git diff --check` | 无输出 |
| `v10.freeze verify` | **9/9 unchanged** |
| `v10.recompute --check` | 1093/1093，0 不一致 |
| `v10.independent_check --check` | 0 违规，回放确定 30/30，seed 互异 30/30 |
| `scripts/verify_v11.py` | 7/7 |
| `scripts/verify_v12.py` | **15/15** |
| `scripts/a11y_v12.py --browser --start` | 0 critical / 0 serious / 0 moderate |
| `scripts/e2e_web.py --start` | 通过（15 步，24 751 B） |
| `scripts/e2e_lab.py --start` | 通过（父实验 COMPLETED，报告 8 157 B） |

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
| MAP-22 记忆假设 | **机制已验证，样本不足** | `route_log` 把 `route_recall` 从 0 拉到 0.45–1.0，seed 2 通关；但只有 3 局、跨配置不配对 |
| MAP-16 / MAP-18 | 有梯度但**翻转率 22–25%** | 3 次观测里唯一稳定信号是 planning@MAP-16 seed 1（3/3） |
| MAP-08 / MAP-26 | 天花板 | 三臂 9/9 成功，测不出架构差异 |
| MAP-30 | 约束阶梯 | 90 请求 → 200k token → ¥0.20 费用；180 请求下 4/9 走到法庭且 `ACCUSATION_REJECTED` |
| 反思独立小矩阵 | **DONE（触发器未激活）** | 12 局消融已跑；MAP-16 失败过快（seed 0 第 6 步 `DEADLOCK`），`reflection_triggered` 两臂均为 0 → 该对照无法回答提效（DCR-V12-05） |
| 样本量 | 描述性 | 主矩阵 1 次/条件 + 2 次重复；翻转率已量化，不作显著性断言 |
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

1. **重复扩到 3 次/条件并固定模型采样**：当前 3 次观测的翻转率 25.0%
   且只有 `planning@MAP-16 seed 1` 是 3/3；要谈架构差异必须先把噪声压下来。
2. **`route_log` 默认化评估**：已证明能把 `route_recall` 从 0 拉到 0.45–1.0，
   需要用配对重复确认它是否稳定，以及代价（决策预算占用）。
3. **MAP-30 三档预算固定**：≥180 请求 + ≥600k 输入 token + ≥¥0.25/局，
   并把"预计可跑回合数"写进预检提示。
4. **Provider 账单对账**：把本地估算与后台账单核对一次。
5. **macOS / Ollama 实机**：按用户指示暂缓，恢复后跑 `verify_v12.py` + 网页冒烟。

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

# 续跑 / 版本复跑 / 补充实验 / 预算扩展 / 重复
uv run python scripts/run_v12_matrix.py --resume <experiment_id> --submit
uv run python scripts/run_v12_matrix.py --rerun-of <experiment_id> --conditions "..." --submit
uv run python scripts/run_v12_matrix.py --supplement-of <experiment_id> --list-candidates
uv run python scripts/run_v12_matrix.py --budget-ext-of <experiment_id> --ext-requests 180 --ext-input-tokens 600000 --conditions "..." --submit
uv run python scripts/run_v12_matrix.py --replicate-of <experiment_id> --conditions "..." --submit

# 补登记 seed（等价于主 CLI）
uv run python scripts/run_v12_matrix.py --maps MAP-18 --seeds 3 4 \
    --provider openai_compatible --model mimo-v2.6-flash \
    --decisions 90 --requests 90 --per-run-cost 0.2 \
    --experiment-requests 540 --experiment-cost 0.8 \
    --approval-cap 0.8 --i-have-budget-approval --submit

# 三条开关消融（memory / planning / reflection on-off，12 局约 ¥0.10）
uv run python scripts/run_v12_ablations.py            # 预检，零请求
uv run python scripts/run_v12_ablations.py --submit

# 重复实验的翻转率统计
uv run python scripts/summarize_v12_replicates.py <exp_a> <exp_b> [...]
```

## 真实结果档案（可审计、已脱敏）

| 文件 | 内容 |
|---|---|
| `docs/v12/real-runs/main-54-report.md` / `-runs.csv` | 主矩阵 54 局报告与逐局明细 |
| `docs/v12/real-runs/main-54-paired.csv` | 配对对照（含 verdict 与不可比原因） |
| `docs/v12/real-runs/map22-contract-fixed-report.md` | DCR-V12-01 修复后（`contract-1`）9 局 |
| `docs/v12/real-runs/map22-contract2-report.md` / `-runs.csv` | DCR-V12-02 口径对齐（`contract-2`）9 局 |
| `docs/v12/real-runs/map30-budget180-report.md` / `-runs.csv` | MAP-30 预算扩展（180 请求） |
| `docs/v12/real-runs/map30-token600k-report.md` / `-runs.csv` | MAP-30 token 扩展（600k） |
| `docs/v12/real-runs/replicate-16-18-report.md` / `-runs.csv` | 重复实验 A（18 局） |
| `docs/v12/real-runs/replicate-summary-2obs.txt` | 2 次观测的翻转率（22.2%） |
| `docs/v12/real-runs/replicate-summary-3obs.txt` | 3 次观测的翻转率（25.0%，含跨版本排除） |
| `docs/v12/real-runs/map18-seed3-4-report.md` / `-runs.csv` | MAP-18 新 seed 覆盖 |
| `docs/v12/real-runs/pilot-report.md` | Pilot 6 局 |
| `docs/v12/mimo-results.md` | 汇总、逐图结论、成本与事故记录 |
| `docs/v12/dcr/DCR-V12-01.md` | `facts` 契约缺陷（接口） |
| `docs/v12/dcr/DCR-V12-02.md` | `route_recall` 键名口径缺陷（口径） |
| `docs/v12/dcr/DCR-V12-03.md` | 记忆序列过短（策略） |
| `docs/v12/dcr/DCR-V12-04.md` | 长观测地图的 token 瓶颈（预算） |
| `docs/v12/dcr/DCR-V12-05.md` | 反思触发器未激活（测量配置） |
| `docs/v12/dcr/DCR-V12-06.md` | 新增默认配置键会改变全部历史指纹（实验身份） |
| `docs/v12/ablations.md` | 三条开关消融的对照与结论 |
| `docs/v12/gap-audit.md` | 提纲逐项状态（未做项与原因） |
| `docs/v12/real-runs/ablation-*-runs.csv` | 消融逐局明细（6 份） |

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
| 成功率差异 | **是（描述性）** | 主矩阵 7/8/9；种子扩展后 MAP-16 planning 3/4、MAP-18 memory 2/5 |
| 成本差异 | **是** | memory 最贵 0.0331，planning 0.0282，basic 0.0205（元/局） |
| 失败原因 | **是** | 139 条证据级诊断，每条指向具体 `decision` 事件 |
| 差异是否稳定 | **否（已量化）** | 同条件重复翻转 22.2%（2 次）/ 25.0%（3 次，12 组可比）；仅 planning@MAP-16 seed 1 是 3/3 |
| MAP-22 记忆假设 | **是（机制验证）** | `route_log` 把 `route_recall` 从 0 拉到 0.45–1.0，seed 2 通关（DCR-V12-03） |
| MAP-30 能力 | **是（部分）** | 抬预算后 4/9 走到法庭且 `ACCUSATION_REJECTED`；其余受 token/费用约束（DCR-V12-04） |
| 可复现 | **是** | `experiment.json` 冻结矩阵与指纹（含 `runtime_version`）；可从 CSV 复算 |

**结论**：这个判据在"能不能测出差异"这一层成立，在"差异是否稳定"这一层给出了
**否定的答案** —— 这正是 V12 最诚实也最有用的结论：1 次/条件的设计不足以下架构结论。
天花板（MAP-08/26）、接口假象（MAP-22 v1）、口径缺失（`route_recall`）都已排除，
剩下的差异基本落在 22–25% 的翻转率之内；唯一穿透噪声的信号是 planning 在单图单 seed 的 3/3。
