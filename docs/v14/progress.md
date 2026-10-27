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

## Batch 5 · P0-6 Reflection v2 暴露率与真实收益

- 新模块：`lab/v14/reflection_study.py`
  - `reflection_offline_probe`：六态计数（`eligible` / `triggered` / `blocked_cooldown` /
    `blocked_quota` / `false_triggers` / `recoveries`）+ 逐决策链 + 建议注入计数；
  - 三臂：`disabled` / `trigger_only` / `reflection_on`，两组单因子
    （`enabled`、`trigger_only`）与一组显式组合对照；
  - `exposure_gate`：`triggered == 0` → `NO_TREATMENT_EXPOSURE`，禁止报"反思无效"；
  - `evaluate_without_selection_bias`：全分配 vs 触发子集并列，标 `selection_bias`；
  - `reflection_ablation_plan`：MAP-22 三臂 × 3 seed × 3 重复 = **27 局**（两臂子集 18），`PLANNED_ONLY`。
- 实测（SIMULATED，12 决策）：
  - `reflection_on`：eligible 3 / triggered 3 / 冷却挡 6 / 反思请求 3（总请求 15）/ 恢复 2；
  - `trigger_only`：triggered 9 但反思请求 0（暴露成立、无额外请求）；
  - `long_failure_on`：触发 3（额度封顶）+ 额度挡 1 + 恢复 3；
  - `no_trigger_on`（全程有进度）→ `NO_TREATMENT_EXPOSURE`，复现 DCR-V12-05 情形。
- 测试：`pytest tests/test_v14_reflection_study.py` **15 passed**；V14 累计 46 项。
- 真实收益：`LIVE_PENDING`（零请求）。
- commit：`feat(v14): reflection.v2 exposure gate and selection-bias guard`

## Batch 6 · LIVE 方案 A 预注册（零请求）

- 新模块：`lab/v14/live_plan.py`
  - `plan_a_arms` / `plan_a_single_factor_checks`：E1-a（`route_log`，钉 `context_only`）、
    E2-a（`enabled`）、E3（`disabled→reflection_on`，标为**机制级组合对照**）；
  - `plan_a_specs`：6 个父实验规格，默认 `SIMULATED`（误跑也不产生真实请求）；
  - `plan_a_cost_estimate`：按 V12 实测单价 × 1.5 余量 → **54 局 / ¥2.11 / 上界 ¥27.00**，
    建议批准上限 **¥5.00**；单价缺失时 `estimate=None` 而不是 0；
  - `plan_a_seed_audit`：seed 0/1/2 全部在白名单内；
  - 停止条件 6 条（含 `unknown_spend`、90% 上限、连续 3 次 Provider 错误、
    契约缺陷先写 DCR、费用超预估 2 倍、反思零触发按 `NO_TREATMENT_EXPOSURE`）。
- 脚本：`scripts/plan_v14_live.py --check|--write` → `docs/v14/live-plan.md` + `.json`。
- 测试：`pytest tests/test_v14_live_plan.py` **10 passed**。
- 真实付费请求：**0**；状态 `PLANNED_ONLY` / `LIVE_PENDING`。
- commit：`feat(v14): register plan A preflight with pinned single-factor arms`

## Batch 7 · P1-1 + P1-2 MAP-30 与地图适用范围

- 新模块：`lab/v14/map_audit.py`
  - `map30_three_axis`：三档预算 × 请求/token/金额三维，逐档给出**瓶颈轴**与证据
    （`REQUESTS` / `INPUT_TOKENS` / `COST_CNY` / `UNSPECIFIED`）；
  - `map30_conservative_interval`：按已观测分布给可达决策区间（113–155 / 111–155 / 334–460），
    明确"不是承诺"；候选档需批准；
  - `six_map_recheck`：标签复算 + 独立 seed + 证据版本 + `DESCRIPTIVE_ONLY` 状态；
  - `candidate_map_audit`：MAP-19/20/29 只读审计（seed 空间、公开字段、动作、规则条数、
    指标、V10 登记、历史终态），结论上限 `NEEDS_MORE_EVIDENCE`。
- 脚本：`scripts/audit_v14_maps.py --write` → `docs/v14/map-audit.md` + `.json`。
- 关键发现：MAP-30 只有 90 请求档能明确归因为"撞满请求"（8/8）；180 请求与 600k token
  两档的 5 局/7 局截尾**公开终态码没有暴露撞哪一维**，因此标 `UNSPECIFIED`，不强行归因。
- 测试：`pytest tests/test_v14_map_audit.py` **12 passed**。
- commit：`feat(v14): map applicability audit with MAP-30 three-axis ladder`

## Batch 8 · P1-3 + P1-4 + P1-6 诊断、能力画像与结论语言

- 新模块：`lab/v14/failure_capability.py`
  - `finding_anchor` / `audit_findings`：锚点校验 `(run_id, decision_index, action, public_result)`，
    三态 `ANCHORED` / `PARTIALLY_ANCHORED` / `UNANCHORED`；
  - 三个 fixture：`REJECTED_NO_PROGRESS`（策略层，可进能力分母）、
    `PROGRESS_THEN_BUDGET_CENSORED`（截尾，不可进）、`INTERFACE_ARTEFACT`（接口层，不可进）；
    层级可进性矩阵显式列出；
  - `capability_with_gaps`：六维 + 适用样本 + 独立 seed + 重复编号 + 缺口
    （`UNAVAILABLE` / `FEW_INDEPENDENT_SEEDS` / `NO_REPLICATES` / `HAS_CENSORED_RUNS` / `MISSING_MAPS`）；
  - `conclusion_strength`：`evidence_level` / `mechanism_exposure` / `effect_direction`
    三字段独立 + `forbidden_claims`。
- 实测（历史 138 局）：`failure_recovery` 维度 **`UNAVAILABLE`**（V12 无 MAP-05/19/20 数据），
  其余五维可测但都缺重复或存在截尾；结论强度为
  `INSUFFICIENT` / `NO_TREATMENT_EXPOSURE` / `NOT_MEASURABLE`。
- 脚本：`scripts/audit_v14_failures.py --write` → `docs/v14/failure-and-capability.md` + `.json`。
- 测试：`pytest tests/test_v14_failure_capability.py` **16 passed**。
- commit：`feat(v14): anchored failure attribution and capability gaps`

## Batch 9 · P1-5 + P2-3 五页 Lab 体验收官

- 新模块：`lab/v14/ui_views.py`（纯函数，全部可单测）
  - `first_divergence_view`：双轨迹首次分歧高亮（动作/公开结果分别判分歧，版本不同时提示"版本比较"）；
  - `seed_grouped_repeats`：按 `(map, seed)` 分组，显式声明"重复不是新环境样本"；
  - `map22_exploration_view`：接受边与被拒移动分列，**被拒移动绝不画成走过的边**；
  - `map30_ladder_view`：预算阶梯 + 瓶颈轴 + 截尾/成功分开读；
  - `comparison_gate`：`INCOMPARABLE` 禁用排名，`DESCRIPTIVE_ONLY` 可看数字不可下结论，
    `COMPARABLE` 也不得写"显著改善"。
- 服务层：`LabService.trace_steps()`（只读，供视图取公开决策步骤）。
- UI：结果页加可比性门禁横幅与 MAP-30 预算阶梯；可视化页加 MAP-22 探索声明与被拒移动表；
  证据与差异页加首次分歧高亮表；稳定性页加"V14 视图：按 seed 分组的重复结果"。
- 截图：`scripts/capture_v14_screenshots.py` → `docs/v14/screenshots/` 7 张（含 430px 窄屏、深色）。
- 浏览器实测：`e2e_lab.py --start --port 8514` 通过，新增断言
  `v14_map22_view` / `v14_first_divergence` 均为 true；`a11y_v12.py --browser` 浅/深色
  critical/serious/moderate 全 0。
- 测试：`pytest tests/test_v14_ui_views.py` **12 passed**。
- commit：`feat(v14): lab views for divergence, seed groups, map22 and map30`

## Batch 10 · P2-1 CI 浏览器 E2E 正式门禁

- 前置证据：`lab-e2e` 连续 **7 次**远端 success（不同 commit、`run_attempt=1`），见 `ci-evidence.md` 第 2 节。
- 切换：`34a83fe` 移除 `continue-on-error: true`，`lab-e2e` 变为**阻断**门禁。
- 第一次真实红灯（**保留证据**）：`40477841302`（`34a83fe`）`quality` success、`lab-e2e` **failure**。
  根因是本轮新增的 E2E 断言用"固定 sleep + body 子串"判断页面渲染，CI 慢时读到中间态。
- 修复（`babe194`）：改为显式 `wait_for` 元素；新增 `--report runs/v14/e2e-report.json`、
  `AGENT_ARENA_E2E_KEEP=1` 与 CI `if: failure()` 上传 artifact；**未**用 skip/xfail/降级断言或恢复
  `continue-on-error` 掩盖。
- 修复后验证：`40482235016`（`babe194`）两个 job 均 success，门禁保持阻断。
- 本地：`e2e_lab.py --start --port 8516 --report ...` 通过；`a11y_v12 --browser` 0 critical/serious/moderate。
- 仍未验证：本机 Playwright 自带 chromium 因 CDN 受限未安装，`AGENT_ARENA_E2E_BROWSER=chromium`
  的本地复现路径记为 `NOT_VERIFIED`。
- commit：`34a83fe`、`babe194`

## Batch 11 · P2-2 + P2-4 + P2-5 + P2-6 工程边界

- 新模块：`lab/v14/engineering.py`
  - `cold_start_measurement`：**未预热**冷启动与预热后解析分开报告；
  - `corrupted_manifest_handling`：坏 manifest 被跳过、不混入统计；
  - `concurrent_read_during_write`：写线程 + 读线程 40 轮，0 异常；
  - `ttl_refresh`：TTL 到期与 `invalidate()` 都能看到新 run；
  - `long_history_export`：1000 局全量导出行数与字节；
  - `export_consistency`：行数/分母/模式/空值四类一致性（非可空列空值、`VALID` 指标空值都判失败）；
  - `sdk_hardening`：8 项 V13 自检 + 3 项 V14 补充（旧签名、异常隔离、预算网关不可绕）；
  - `ledger_recompute`：优先读本机只读账本（**159/159、5641 请求、¥5.43680012、0 重复 0 孤儿**，
    与 V13 记录一致）；账本缺失时报 `LEDGER_NOT_PRESENT_LOCALLY`，绝不用 CSV 的 138 局冒充全账本。
- 脚本：`scripts/audit_v14_engineering.py --write` → `docs/v14/engineering-boundaries.md` + `.json`。
- 实测（本机，临时目录）：冷启动 277ms / 预热首页 0.03ms / 预热重建 41ms；
  并发读写 0 异常；TTL 3→4；导出 1000 行；导出一致性 4 文件全通过。
- 外部账单：`NO_EXTERNAL_BILL_PROVIDED`（`BLOCKED_EXTERNAL`，未虚构）。
- 测试：`pytest tests/test_v14_engineering.py` **18 passed**。
- commit：`feat(v14): engineering boundaries with perf, export and ledger evidence`

## Batch 12 · P2-7 第二阶段最终交付封装

- 新增 `scripts/verify_v14.py`（**14 项** V14 事实边界，不是"重跑 V13"）：
  `unknown_semantics` / `protocol_isolation` / `seed_and_replicates` / `approval_blocked` /
  `ci_evidence` / `export_consistency` / `diagnostics_anchor` / `agent_mechanisms` /
  `map30_ladder` / `capability_gaps` / `conclusion_strength` / `sdk_and_ledger` /
  `docs_present` / `frozen_assets`。
- CI：`quality` job 增加 `V14 Lab 1.2 离线验收` 步骤。
- 文档定稿：`final-report.md`、`release-checklist.md`、`gap-audit.md`（19 项终态）、
  `README.md`（状态改为 `ENGINEERING_VERIFIED` / `LIVE_PENDING`）。
- 实测：`verify_v14.py` **14/14 通过**；全量 pytest **1790 passed**；ruff/mypy 通过。
- 最终状态：`ENGINEERING_VERIFIED` 满足；`LIVE_EVIDENCE_VERIFIED` 与
  `STAGE_II_FINAL_READY` **不满足**（零 LIVE 请求）。
- commit：`feat(v14): final delivery package with verify_v14 gate`

## 远端 CI 复核（Batch 10 收尾）

切换为阻断门禁后连续成功 4 次：`40482235016` / `40482773825` / `40486150217` / `40487657690`；
其中 `40487657690` 的 `V14 Lab 1.2 离线验收` 步骤也通过。此前 `40477841302` 的失败记录保留。

## Batch 13 · LIVE 执行（用户授权 MiMo，方案 A 子集）

- 授权：用户"按照提纲执行，你可以自行调用 mimo" → 按 `live-plan.md` 方案 A 执行（上限 ¥5.00）。
- 新增：`scripts/run_v14_live.py`（钉住配置的 6 个父实验；`--pilot` / `--groups` / `--submit`；
  独立账本 `runs/v14/live/`）、`scripts/summarize_v14_live.py`（只读聚合）。
- 执行：`mimo-v2.6-flash`，Pilot 6 局 + 主矩阵 33 局 = **39 局 / 1 313 请求 / ¥0.72437412**；
  1 局 `unknown_spend`（预留，未计入结算）；0 重复、0 孤儿；未超 ¥5.00（用量 14.5%）。
- 结果：
  - **E1-a**（MAP-22 `route_log` on/off，20 局）：`route_recall` 0.045 → **0.557**（4 局满分），
    成功率 **0/10 vs 0/10**，平均费用 ¥0.0242 → ¥0.0302（+25%），1 局截尾；
  - **E2-a**（MAP-16 `planning` on/off，17 局）：off **0/10**、on **3/7**（3.43 次计划/局），
    但 `PROVIDER_ERROR` + `unknown_spend` 触发停批 → 臂只有 7/9，描述性；
  - **E3**（MAP-22 `reflection`，2 局）：`triggered = 0` → **`NO_TREATMENT_EXPOSURE`**，停止扩展。
- 修掉一个真实缺陷：V14 `condition_comparison` 把 effective `prompt_hash` 当硬不匹配，
  导致 on/off 臂全部判 `INCOMPARABLE`；改为比较 `base_prompt_hash`，把配置/effective prompt
  标为 `INTERVENTION`（新增 2 条测试，24 项全过）。
- 新 DCR：`DCR-V14-04`（reflection 零暴露）、`DCR-V14-05`（Provider 错误 → 停批封账、不重试）。
- 文档：`docs/v14/live-report.md`、`live-results.md/.json`；`final-report.md` / `release-checklist.md` /
  `README.md` / `gap-audit.md` 同步为 `LIVE_PARTIAL`。
- commit：`feat(v14): run plan A live subset with MiMo and report partial evidence`


## Batch 14 · LIVE 补充实验（三轮，按推荐执行）

- 用户："选择你更推荐的就行，钱不是问题" → 我选择消除三个"让结论不可解释"的混淆：
  1. **补足 planning 臂**（E2-a 同预算、每 seed 5 次重复）；
  2. **预算扩展**（E1-a 150 请求，测"0/10 是不是预算造成的"）；
  3. **reflection 换图重测**（先离线诊断 MAP-19/20/29 触发能力，再上 MAP-19）。
- 新增：`scripts/run_v14_supplement.sh` / `run_v14_supplement2.sh`、执行器支持
  `--phase/--kind/--request-cap/--decision-cap/--token-cap/--per-run-cost/--map-override`。
- 结果（122 局累计，¥2.06710508）：
  - **E2-a**：off **0/25**、on **14/15 有效局**（7 截尾）→ 强描述性收益，每成功局 ¥0.0498；
  - **E1-a**：90 请求 0/10 vs 0/10；150 请求 **seed 2 2/9 → 8/8**、seed 0/1 两臂全败
    → 效果是"实例 × 预算"条件性的（DCR-V14-06/07）；
  - **E3**：MAP-22 零暴露 → MAP-19 **on 3/9 局真触发**（暴露达成），但两臂 0/9（地板）→ 效果不可测。
- 事件：2 次 `unknown_spend` 各自停批（DCR-V14-05），未重试；累计 0 重复 0 孤儿。
- 文档：`live-report.md` 重写；`gap-audit.md` / `final-report.md` / `release-checklist.md` / `README.md` 同步。
- commit：`feat(v14): supplement live runs for planning, memory budget and reflection exposure`
