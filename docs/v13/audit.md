# V13 审计：已具备 / 待改进 / 不做 / 风险 / P0–P2 映射

- 生成日期：2026-10-26
- 审计参考 HEAD：`32e27826eab33093d2d5d640d08f47bbd4974df3`（V13 开工前）
- 执行环境：Windows 11（`Windows-11-10.0.26200-SP0`）、Python 3.13.3、uv 0.13.3
- 工作区状态：开工时只有两个未跟踪的研究提纲文件（V12 / V13），无未提交的代码改动

## 1. V12 基线复核（不采信文档，逐项实跑）

| 项 | 文档声称 | 本次实测 | 结论 |
|---|---|---|---|
| 自动化测试 | 1525 passed | `uv run pytest -q` → **1525 passed**（166.31s） | 一致 |
| 真实实验 | 20 实验 / 159 局 / 5 641 请求 / ¥5.43680012 | 读 `runs/web/_ledger/web_ledger.jsonl`：started 159 / settled 159 / requests 5641 / 结算 **5.43680012** / 未知消费 0 | 一致 |
| 重复翻转率 | 2 次 22.2%、3 次 25.0% | V13 独立复算：`4/18 = 0.2222`、`3/12 = 0.25`（排除 6 组跨版本） | 一致，可复现 |
| 父实验 | 20 个 | 本机 `runs/lab/` 有 22 个（含 V13 开工前的 2 个探针实验） | 差异已查明：`探针` 与早前补充实验未进 V12 汇总表 |
| MAP-30 阶梯 | 90 → 180 请求 → 600k token | 逐局 CSV 重算：3 档，`ACCUSATION_REJECTED` 分别 1 / 4 / 2 局 | 一致 |

**结论**：V12 的公开数字可复现；差异项已定位，不影响结论。

## 2. 已具备（可直接复用，V13 不重写）

- **运行与持久化**：`web/`（RunService 单 worker、取消、恢复、幂等、跨进程锁、单局预算）；
- **实验层**：`lab/experiment.py`（父实验、矩阵、预检、队列、补充/版本复跑/预算扩展/重复）；
- **唯一模型出口**：`lab/gateway.py`（`DecisionGateway` + `RunBudget`，未知消费 fail-closed）；
- **策略**：`basic.v1` / `memory.v1` / `planning.v1` / `reflection.v1` + 第三方适配器；
- **分析与产物**：配对比较、五态指标、证据级诊断、轨迹 Diff、六图 view-model、CSV/MD 导出；
- **治理**：30 图冻结、公式级复算、独立复核、可访问性自动审计、浏览器 E2E（本地已通过）。

## 3. 待改进（V13 的真实增量来源）

| # | 缺口 | 影响 | 对应任务 |
|---|---|---|---|
| 1 | `condition_key` 不含 config hash、也没有重复编号 | 同条件重复会被矩阵去重；on/off 跨实验无法配对 | 01-04 / 01-05 / 02-01 |
| 2 | 没有采样参数登记（temperature/top_p/seed） | 无法说明"环境 seed 固定 ≠ 模型确定" | 01-03 |
| 3 | 没有可比性画像与单变量检查 | 多开关同时改动也能被当成"消融" | 01-01 / 01-02 / 05-03 |
| 4 | 重复只有"再跑一次"（跨实验），没有实验内 N 次 | 重复分析要跨实验拼接，易混入版本差异 | 02-01 … 02-07 |
| 5 | Memory 只有 v1，`route_log` 只有一个开关 | 无法区分"没记录 / 记录太短 / 记录了没用" | 03-01 … 03-07 |
| 6 | Planning 只有"周期 + 无进展"重规划，无节流/预算感知 | 无法做"规划开/关 / 重规划开/关 / 低频"三类分离消融 | 04-01 … 04-07 |
| 7 | Reflection 在 MAP-16 从未触发（DCR-V12-05） | "反思无效"与"没有暴露"混为一谈 | 06-01 … 06-07 |
| 8 | 诊断没有分层 | 接口/测量问题可能被写成能力不足 | 08-01 … 08-03 |
| 9 | 能力只按成功率看，没有机制维度 | 326 个异质指标无法组织成"能力画像" | 08-04 … 08-06 |
| 10 | 六图没有构念效度标签 | 天花板图被当成"能区分架构" | 07-05 / 07-06 |
| 11 | MAP-30 只做过一次预算阶梯复盘 | 截尾/机制失败/证据不足未分型 | 07-01 … 07-04 |
| 12 | 历史列表每次 `discover()` 全量解析 | 上千条历史时页面开销线性增长 | 09-06 / 12-04 |
| 13 | 报告只有"实验级"模板，无结论分级与锚点 | 读者无法判断结论强度 | 10-01 … 10-03 |
| 14 | 账本只有本地估算，没有一致性审计工具 | 重复计费/孤儿任务无法被发现 | 10-04 … 10-06 |
| 15 | SDK 只有示例，没有接入自检与故障隔离测试 | 第三方插件出错会显得像"模型不行" | 11-01 … 11-06 |
| 16 | CI 的浏览器 E2E 是 `continue-on-error` | 无阻断门禁 | 12-01 … 12-03 |
| 17 | 压力测试只有边界单测 | 无 1k/5k 实测数字 | 12-04 … 12-08 |

## 4. 不做（明确排除）

- Ollama 实机验证、macOS 迁移/实机验证（用户指示暂缓，不计 V13 缺项）；
- 公网部署、用户系统、云数据库、跨模型排行榜；
- 自动生成新地图、修改 V8/V9/V10 冻结规则或 seed 空间；
- 任意不可信代码的在线沙箱；
- **任何未经用户单独授权的真实付费 API 请求**（V12 的 ¥6 授权已结束，余额不挪用）。

## 5. 潜在数据风险与处置

| 风险 | 表现 | 处置 |
|---|---|---|
| 重复被当成新样本 | 把 3 次重采样写成 "N=3 张地图" | 统计单位固定为 `(map, seed, agent)`，重复只作组内观测；报告显式写"重复 ≠ 新 seed" |
| 跨版本硬并 | DCR-V12-06 之后 `memory.v1` 默认配置变了 | 只有同 `agent_config_hash` / 同预算的观测计入翻转率，其余标"跨版本"并排除 |
| 接口问题算成能力 | MAP-22 `facts` 载荷被拒 | 分层归因：`INTERFACE_CONTRACT` / `MEASUREMENT_COVERAGE` 永不计入能力分母 |
| 截尾算成失败 | MAP-30 撞 token/费用上限 | `BUDGET_CENSORED` 单列，且构念标签可复合 `CENSORED` |
| 模拟冒充真实 | SIMULATED 结果被当成模型成绩 | 三种通道隔离；报告/UI/产物标题强制标注；SIMULATED 不写付费账本 |
| 历史被改写 | 复跑覆盖旧 run | 所有衍生实验新建父实验 + 新 run_id；历史 CSV/账本只读 |

## 6. P0–P2 任务映射

| 等级 | 任务 | 落地位置 |
|---|---|---|
| P0-1 | 重复稳定性 | `lab/v13/stability.py`、`experiment.create_replicates`、`ui/lab.py` 稳定性页 |
| P0-2 | Memory 优化 | `lab/policies/memory_v2.py`、`docs/v13/memory-study.md` |
| P0-3 | Planning 优化 | `lab/policies/planning_v2.py`、`docs/v13/planning-study.md` |
| P0-4 | 开关消融 | `lab/v13/ablation.py`、`run_v12_matrix.py --ablation` |
| P0-5 | 公平性审计 | `lab/v13/comparability.py`、`contracts.py`（采样/协议/重复） |
| P0-6 | 核心结果重验 | `lab/v13/ablation.py::build_evidence_pack`、`docs/v13/core-evidence.md` |
| P1-1 | Reflection | `lab/policies/reflection_v2.py`、`docs/v13/reflection-study.md` |
| P1-2 | MAP-30 | `lab/v13/validity.py::map30_ladder`、`docs/v13/map30-budget-ladder.md` |
| P1-3 | 失败诊断 | `lab/v13/taxonomy.py`、`docs/v13/diagnosis-taxonomy.md` |
| P1-4 | 能力画像 | `lab/v13/capability.py`、`docs/v13/capability-profile.md` |
| P1-5 | 可视化 | `ui/lab.py`（稳定性/效度页、逐 seed 分块、轨迹 Diff 保留） |
| P1-6 | 六图效度 | `lab/v13/validity.py::six_map_audit`、`docs/v13/map-validity.md` |
| P2-1 | CI 强化 | `.github/workflows/ci.yml`、`docs/v13/validation-report.md` |
| P2-2 | 性能压力 | `lab/v13/perf.py`、`web/index.py`、`docs/v13/performance-report.md` |
| P2-3 | Web UI | `ui/lab.py`（5 页）、`web/index.py`（服务端分页） |
| P2-4 | 自动报告 | `lab/v13/report.py`、UI「报告与审计」页 |
| P2-5 | SDK | `lab/v13/sdkcheck.py`、`docs/v13/sdk-guide.md` |
| P2-6 | 数据/费用审计 | `lab/v13/ledger.py`、`docs/v13/data-and-cost-audit.md` |
| P2-7 | 文档交付 | `docs/v13/` 全套 |

## 7. 与 V12 的边界（不变量）

- 不改 `src/agent_arena/v10/`、`v8/`、`v9/` 的任何规则、指标、账本；
- 不改历史 `runs/v*/`、`runs/web/*`、`runs/lab/*` 的原始产物与已记账条目；
- V11 单局语义不变（`OFFLINE` 通道未动）；
- V12 的 `schema_version = v12-lab-1` 保持不变，V13 只在**新增字段**上扩展，
  旧文件缺字段时按默认值读取（`replicates=1`、`sampling.support=UNKNOWN`、`protocol=None`）。
