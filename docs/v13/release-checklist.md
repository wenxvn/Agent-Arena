# V13 交付清单与复现

- 版本：`Agent Arena Lab 1.1`（V12 Lab 1.0 的深化，不是另起炉灶）
- 状态：`LAB_1_1_ENGINEERING_READY`（`LIVE` 部分 `WAITING_USER_APPROVAL`）
- 起始 HEAD：`32e27826eab33093d2d5d640d08f47bbd4974df3`
- 真实付费请求：**0**

## 1. 一条命令跑起来

```bash
uv sync --extra web
uv run agent-arena web
```

侧边栏 → `Lab · 实验配置` → 「一键离线演示（3 架构 · 零费用）」。

## 2. 五页 Lab

| 页面 | 用途 |
|---|---|
| `Lab · 实验配置` | 矩阵、预检（零请求）、预算门禁、授权状态、重复口径提示 |
| `Lab · 实验监控` | 父/子状态、进度、停止、续跑 |
| `Lab · 结果与对照` | 实验臂汇总、五态指标、逐局明细、可视化、Diff、导出 |
| `Lab · 稳定性与效度` | 翻转率、逐 seed 分块、六图效度、MAP-30 阶梯、能力画像 |
| `Lab · 报告与审计` | V13 报告（分级+锚点）、账本审计、账单对账、SDK 自检 |

## 3. 代码增量（对 V12 的真实改动）

| 位置 | 增量 |
|---|---|
| `lab/contracts.py` | `SamplingProvenance` / `ProtocolManifest`；`ExperimentSpec` 新增 `replicates` / `sampling` / `protocol` / `experiment_kind` / `contract_version`；`MatrixCell.replicate_index` + `base_condition_key` / `replicate_key` |
| `lab/experiment.py` | `create_replicates`（同实验 N 次重复）；预检给 `replicates` / `conditions` / `cells_per_condition`；子局链接带 `replicate_index` / `experiment_kind` |
| `lab/compare.py` | run_record 新增 `replicate_index` / `prompt_hash` / `base_prompt_hash` / 单局预算字段 |
| `lab/runner.py` | 结果写 `replicate_index` |
| `lab/registry.py` | 注册 `memory.v2` / `planning.v2` / `reflection.v2`（v1 一字未动） |
| `lab/policies/memory_v2.py` | 路线记忆：只累积被接受 move、`env_write`/`context_only`、循环折返、三类瓶颈 |
| `lab/policies/planning_v2.py` | 三模式 + TTL + 预算感知 + 逐请求成本 |
| `lab/policies/reflection_v2.py` | 暴露/触发/冷却/额度/误触发/恢复 + trigger-only |
| `lab/v13/`（新包，10 模块） | 可比性、稳定性、消融、效度、归因、画像、报告、账本、SDK 自检、压测 |
| `web/index.py`（新） | 只读索引：懒加载首页、增量刷新、服务端分页、聚合 |
| `web/service.py` | `page_runs` / `aggregate_runs` / `invalidate_index`；`list_runs` 改走只读索引（不再每次全量解析 manifest） |
| `web/schemas.py` | `RunConfig.replicate_index` |
| `ui/lab.py` | 5 页；预检重复口径；稳定性/效度页；报告/审计页 |
| `scripts/` | `verify_v13.py`、`demo_v13.py`、`summarize_v13_repeats.py`、`audit_v13_ledger.py`、`audit_v13_maps.py`、`stress_v13_history.py`；`run_v12_matrix.py` 新增 `--replicates` / `--repeats-of` / `--ablation` |

**未改**：`v10/`、`v8/`、`v9/` 任何规则/指标/账本；历史 `runs/` 与 `docs/v12/real-runs/`。

## 4. 复现命令

```bash
# 质量门禁
uv run ruff check .
uv run mypy src
uv run pytest -q
uv lock --check
git diff --check

# 冻结与复算
uv run python -m agent_arena.v10.freeze verify
uv run python -m agent_arena.v10.recompute --check
uv run python -m agent_arena.v10.independent_check --check

# 旧版本验收
uv run python scripts/verify_v11.py
uv run python scripts/verify_v12.py

# V13
uv run python scripts/verify_v13.py
uv run python scripts/demo_v13.py

# 研究产物（全部只读历史）
uv run python scripts/summarize_v13_repeats.py --history --write
uv run python scripts/audit_v13_maps.py --write
uv run python scripts/audit_v13_ledger.py --write
uv run python scripts/stress_v13_history.py --write

# 浏览器（需 playwright）
uv run --with playwright --with streamlit python scripts/e2e_lab.py --start
uv run --with playwright --with streamlit python scripts/e2e_web.py --start
uv run --with playwright --with streamlit python scripts/a11y_v12.py --browser --start
```

## 5. 文档索引

| 文件 | 内容 |
|---|---|
| `audit.md` | V12 基线复核、17 项缺口、数据风险、P0–P2 映射 |
| `experiment-protocol.md` | 预注册协议：身份、可比性、统计口径、停止规则 |
| `progress.md` | 13 个批次逐任务状态与证据 |
| `decisions.md` | 14 条 ADR（含被拒绝的备选） |
| `memory-study.md` / `planning-study.md` / `reflection-study.md` | 三个策略的机制、代价、待批准矩阵 |
| `core-evidence.md` | MAP-16/18/22 证据包 |
| `map-validity.md` / `map30-budget-ladder.md` | 六图构念效度；MAP-30 阶梯与分型 |
| `diagnosis-taxonomy.md` / `capability-profile.md` | 七层归因；六维画像 |
| `repeat_variability.{md,json,csv}` | 重复稳定性（V13 生成，可复算） |
| `data-and-cost-audit.{md,json}` | 本地账本审计 + 外部对账状态 |
| `performance-report.{md,json}` | 1k/5k 压测实测 |
| `live-budget-proposal.md` | 三档预算申请（**未批准**） |
| `validation-report.md` | 全部门禁实跑结果 |
| `gap-audit.md` | 逐任务状态（含 `PARTIAL` 解释） |
| `final-report.md` | 总结论、限制、下一步 |
| `sdk-guide.md` | 第三方插件接入与自检 |
| `demo/` | SIMULATED 演示产物（含 `DEMO_SIMULATED.txt`） |

## 6. 演示数据包

`docs/v13/demo/`（由 `scripts/demo_v13.py` 生成，全部 `SIMULATED`）：

| 文件 | 内容 |
|---|---|
| `DEMO_SIMULATED.txt` | 声明"不联网、不产生费用、不得当作能力证据" |
| `report_v13.md` / `.json` | 16 局实验报告（分级 + 锚点 + 负面结果） |
| `repeat_variability.md` / `.json` | 重复稳定性 |
| `map-validity.md` | 六图效度（基于演示记录） |
| `capability-profile.md` | 机制画像 |
| `diagnosis-taxonomy.md` | 分层归因 |
| `reflection-trigger-probe.json` | Reflection 真触发证据 |

## 7. 回滚办法

每个批次一个 commit；回滚只需 `git revert <commit>`，不涉及数据迁移：

- 契约只增字段，旧文件仍可读 → 回滚代码不会让旧实验"读不出来"；
- 新策略是**新 `agent_id`** → 回滚注册表即可，不影响 v1；
- 新页面/新脚本是新增文件 → 删除即回滚；
- 历史 `runs/`、`docs/v12/real-runs/`、账本**从未被写入** → 无需回滚数据。

## 8. 下一步候选（不自动执行）

1. **方案 A 的 LIVE 验证**（54 局，预估 ¥1.68，见 `live-budget-proposal.md`）；
2. 把重复从 2 次提到 3–5 次，看翻转率是否下降；
3. CI E2E 连续 3 次成功后改阻断门禁；
4. 用户提供后台账单后补 `RECONCILED_WITH_EXTERNAL_BILL`；
5. 六图之外的长失败前缀地图（MAP-19/20/29）用 V13 运行时重采机制触发证据。
