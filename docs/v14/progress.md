# V14 进度日志（Batch 0–12）

> 每完成一个 Batch 追加一条，记录：做了什么、跑了什么命令、结果、commit、遗留。
> 不允许把未运行的检查写成已通过。

## Batch 0 · 仓库与收口审计（P0-1）

- 基线 HEAD：`60c9ba2b64a3bd8d5cd549a7b76d0f3eb3ad092a`（与提纲建议一致）
- 工作区：仅 3 个未跟踪的用户本地提纲文件
- 门禁复跑：`uv lock --check` ✅、`ruff` ✅、`mypy src` ✅ 323 文件、`pytest -q` **1639 passed**、
  `v10.freeze verify` ✅、`v10.recompute --check` 1093/1093、`v10.independent_check` 0 违规、
  `verify_v11` 7/7、`verify_v12` 15/15、`verify_v13` 18/18
- 远端 CI 取证：REST API 取得 10 次运行，`lab-e2e` **连续 7 次 success**（详见 `ci-evidence.md`）
- 交付：`baseline-audit.md`、`ci-evidence.md`、`progress.md`、`decisions.md`、`gap-audit.md`、`validation-report.md`
- 发现的文档缺陷（转 Batch 1）：`map-validity.md` 机制触发列 `0/N`、`live-budget-proposal.md` 合计 229≠221
- commit：`docs(v14): batch 0 baseline audit and CI evidence`

## Batch 1 · P0-2 历史口径与数据契约

- 代码：`lab/v13/validity.py` 新增 `mechanism_triggered_summary()` / `format_trigger_ratio()`，
  `map_validity()` 增加 `observed_true/observed_false/unknown/observed/status/display`，
  `validity_markdown()` 全未知输出 `UNKNOWN (0 observed / N runs)`；`SUITABLE` 理由改为
  “只说明现有样本里出现成功率梯度，不证明构念效度或因果”。
- 新模块：`lab/v14/data_audit.py`（协议隔离、六图标签差异复算、预算表算术复核、单价统计）。
- 脚本：`scripts/audit_v14_data.py --write`。
- 文档：新增 `docs/v14/data-validity.md`、`data-validity.json`、`validity-diff.md`、`budget-audit.md`；
  修正 `docs/v13/map-validity.md`（加 V14 修正说明）与 `docs/v13/live-budget-proposal.md` 算术。
- 实测：`pytest tests/test_v14_data_validity.py` **14 passed**；`pytest tests/test_v13_*.py` **114 passed**；
  `verify_v13.py` 18/18；ruff/mypy 通过。
- 关键数字：逐行子局 **221**（原写 229）、方案 A **54 局 / ¥2.11**、B **186 局 / ¥5.60**、C **221 局 / ¥10.97**。
- 新 DCR：`DCR-V14-01`（历史 CSV 缺 `contract_version`/`prompt_hash`，跨契约只能按登记文件隔离）。
- commit：`fix(v14): separate UNKNOWN from zero and recheck V13 arithmetic`

## Batch 2 · P0-3 重复样本、可比性与统计协议

- 新模块：`lab/v14/conditions.py`
  - 8 元组观测条件身份（`observation_condition` / `observation_condition_id`），
    `replicate_index` 不入身份；`budget_profile` / `sampling_profile` 派生画像，
    未登记一律 `UNKNOWN` 且 `recorded=False`；
  - `validate_seed` / `seed_coverage`：seed 只能来自 `seed_space(map_id)`，
    `independent_seed_count` 与 `max_replicates` 分开统计；
  - `condition_comparison`：硬拒绝（地图/seed/模式/模型/Provider/规则/指标/契约/提示/预算/采样已登记且不同）
    vs 软降级（未登记、策略不同）；`UNKNOWN ≠ 不一致`；
  - `build_pairs` / `summarize_pairing`：完成/有效/成功/失败/截尾/可比对/方向/请求-token-费用差值，
    方向只取 `COMPARABLE`，缺失不补零；
  - `descriptive_only_preconditions`：可比对 < 3、存在描述性/不可比对、独立 seed < 3 → 强制描述性；
  - `ablation_pairing_report` / `ablation_pairing_markdown`：V12 三组 on/off 消融重新配对。
- 脚本：`scripts/audit_v14_data.py` 增加配对与 seed 覆盖输出，新增 `docs/v14/pairing-audit.md`。
- 文档：新增 `docs/v14/experiment-protocol.md`（身份/白名单/三档判定/报告字段/区间门槛/批准边界）。
- 实测：`pytest tests/test_v14_conditions.py` **23 passed**；全量 **1676 passed**（134.89s）；
  `ruff check .` 通过；`mypy src` 326 文件 0 issues。
- 实测结论（真实历史）：三组 V12 消融 **单开关成立（config hash 各侧唯一且不同）**，
  但 6 对全部为 `DESCRIPTIVE_ONLY`（缺 `contract_version` / `prompt_hash`），
  可比对 0，独立 seed 各 2 个 → 不能据此宣称效果；资源差值仍可逐对报告。
- commit：`feat(v14): observation condition identity and pairing fairness`

## Batch 3 · P0-4 Memory v2 机制验证与预检

- 新模块：`lab/v14/agent_studies.py`
  - `memory_offline_probe`：确定性脚本驱动 `memory.v2`（接受/被拒/非法/绕圈回起点），
    统计决策、请求、路线、被拒、非法、写入尝试/接受、渲染、瓶颈、`route_recall`；
  - 三条 fixture：被拒/非法移动不进路线、回到起点可引用完整方位、记忆块无隐藏真值；
  - `memory_bottleneck_v14`：修 `env_write` 下的分母口径（DCR-V14-03）；
  - `MEMORY_ARMS` / `memory_arm_configs` / `memory_single_factor_audit`：
    E1-a 只改 `route_log`（钉 `route_mode=context_only`）、E1-b 只改 `route_mode`（钉 `route_log=True`）；
  - `memory_ablation_plan`：MAP-22 × seed 0/1/2 × 3 重复 × 2 组 = **36 局**，`PLANNED_ONLY`。
- 脚本：`scripts/audit_v14_agents.py --write` → `docs/v14/agent-studies.md` + `.json`。
- 实测（SIMULATED）：`context_only` 路线 `north,east,south,west`、决策 7/请求 7；
  `env_write` 决策 8/请求 6（每次写入占 1 决策、0 请求）、写入载荷完整、`route_recall=1.0`；
  `route_log=False` 路线为空（`NO_RECORD`）；记忆块零泄漏。
- 测试：`pytest tests/test_v14_agent_studies.py` **17 passed**。
- 真实收益：`LIVE_PENDING`（零请求）。
- commit：`feat(v14): memory.v2 mechanism probes and single-factor arms`

## Batch 4 · P0-5 Planning v2 机制与收益–成本

- 新模块：`lab/v14/planning_study.py`
  - `planning_offline_probe`：逐决策触发链（触发 → 是否被 TTL/预算/上限挡下 → 是否真发请求
    → 子目标是否变化 → 动作 → 公开结果），Planner 请求与动作请求同记 `requests`；
  - `PLANNING_ARMS`：E2-a `enabled`、E2-b `planner_mode`（adaptive→initial_only）、
    E2-c `min_steps_between_plans`（4→12，两臂都钉 `periodic`），三组各自单开关；
  - `planning_ablation_plan`：MAP-16 主测 54 局 + MAP-18 负向对照 18 局 = **72 局**，`PLANNED_ONLY`。
- 实测（SIMULATED，12 决策脚本）：
  - `adaptive` 15 请求 / 3 次 Planner / 1 次 TTL 延迟；触发序列 `initial → no_progress → public_progress`；
  - `initial_only` 13 请求 / 1 次 Planner；`periodic_4` 15 请求 / `periodic_12` 13 请求；
  - `disabled` 12 请求 / 0 次 Planner；
  - 预算守卫臂 `skipped_budget=2`、`max_plans` 臂计划数封顶 2。
- 测试：`pytest tests/test_v14_planning_study.py` **14 passed**；累计 V14 测试 31 项通过。
- 真实收益：`LIVE_PENDING`（零请求）。
- commit：`feat(v14): planning.v2 trigger chain and cost attribution`
