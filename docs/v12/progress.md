# V12 进度与证据

- **更新日期**：2026-10-26
- **起点 HEAD**：`258eadc5039309859fc0385d61650e266e6ab488`
- **总状态**：`LAB_1_0_READY`（P0 + P1 + P2 全部交付；真实模型实验 20 个、159 局、¥5.43680012、0 未知消费）

## Batch 0（P0）仓库审计

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-00-01 HEAD/工作树/环境/测试数 | DONE | `docs/v12/00-audit.md` §0 |
| V12-00-02 审计 V11 web/ui/schemas/execution 与旧 agents/planning | DONE | 同上 §1–2 |
| V12-00-03 冻结哈希与三项检查 | DONE | `freeze verify` 9/9 unchanged；`recompute --check` 1093/1093；`independent_check --check` 0 违规 |
| V12-00-04 审计/progress/风险册 | DONE | 本文件、`00-audit.md`、`risk-register.md` |
| V12-00-05 Provider 路径与存储口径清单 | DONE | `00-audit.md` §4–5 |

**Gate 0**：通过。唯一基线缺陷（`test_home_shows_per_map_run_history`）已定位为测试自身的同秒排序假设并修复。

## Batch 1（P0）ADR 与契约

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-01-01 ADR：父 Experiment + 子 Run | DONE | `architecture-decision.md` |
| V12-01-02 `AgentIdentity`/`AgentPolicy`/`AgentDecision`/`AgentEvent`/`ExperimentSpec`/`ExperimentManifest`/`ComparisonResult` | DONE | `lab/contracts.py`、`lab/policies/base.py` |
| V12-01-03 `experiment_id` + `run_id` + `matrix_index` + `condition_key` + 指纹 | DONE | `ExperimentSpec.matrix()`、`MatrixCell` |
| V12-01-04 版本化 schema + 旧 V11 读取 + 入队前拒绝非法配置 | DONE | `test_legacy_v11_config_without_agent_fields_still_loads`、`test_unknown_agent_config_key_is_rejected_before_enqueue` |
| V12-01-05 `preflight` 输出 | DONE | `lab/experiment.py::preflight`、`PreflightResult` |
| V12-01-06 LIVE/OFFLINE/SIMULATED 三通道隔离 | DONE | `web/schemas.py::RunMode`、`test_simulated_mode_cannot_use_real_provider`、`test_run_config_offline_semantics_unchanged` |

**Gate 1**：通过（`tests/test_v12_contracts.py` 25 项）。

## Batch 2（P0）Adapter 与统一 Runner

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-02-01 V10 `V8Observation`/`V8Action`/契约对接 | DONE | `lab/adapters.py`、`lab/runner.py` |
| V12-02-02 公开 `PublicEpisodeContext`/`AgentContext` + 泄漏扫描 | DONE | `assert_public`、`test_public_observation_rejects_hidden_truth` |
| V12-02-03 抽出 `DecisionGateway` | DONE | `lab/gateway.py` |
| V12-02-04 reset/step/observe_result/close + 失败分类 | DONE | `run_lab_episode`、`test_policy_exception_becomes_policy_error` |
| V12-02-05 保存策略版本/配置哈希/`agent_events`，兼容 V11 导出 | DONE | `result.provenance`、`test_provenance_fields_are_complete` |
| V12-02-06 30 图 SIMULATED 完整执行路径 | DONE | `selfcheck.simulated_all_maps`（30/30）、`test_all_thirty_maps_run_one_simulated_episode` |

**Gate 2**：通过。`basic.v1` 与 V11 `execute_live` 在同一 Provider 下动作序列、请求文本、预算语义逐项一致（`test_basic_policy_matches_v11_action_loop_with_same_provider`）。

## Batch 3（P0）三种核心架构

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-03-01 `basic.v1` + 固定 Fake 回归 | DONE | 同上一致性测试 |
| V12-03-02 `memory.v1`（公开记忆、容量、淘汰、消融） | DONE | `lab/policies/memory.py`、`test_memory_policy_respects_capacity`、`test_memory_ablation_off_removes_memory_data` |
| V12-03-03 `planning.v1`（子目标、监控、重规划、不执行动作） | DONE | `lab/policies/planning.py`、`test_planning_creates_plan_and_counts_planner_requests`、`test_planning_replans_on_no_progress` |
| V12-03-04 registry 元信息与配置 schema | DONE | `lab/registry.py::agent_catalog` |
| V12-03-05 无状态串局 + 额外请求入账 | DONE | `test_state_is_not_shared_between_runs`、`test_planning_extra_requests_are_counted` |
| V12-03-06 消融开关改变指纹 | DONE | `test_memory_ablation_off_removes_memory_data`、`selfcheck.registry` |

**Gate 3**：通过。Memory 产生真实 `memory_updated` 事件；Planning 产生 `plan_created`/`plan_replanned`；均不宣称能力提升。

## Batch 4（P0）矩阵、队列与预算

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-04-01 多图/多臂/seed 数组 + dry-run | DONE | `ExperimentSpec.matrix()`、`preflight` |
| V12-04-02 单 worker 串行 | DONE | `ExperimentService._run` 串行循环；`test_only_one_experiment_runs_at_a_time` |
| V12-04-03 实验级 + 单局门禁（含 Planner） | DONE | `check_budget`、`test_experiment_request_cap_stops_partial`、`test_unknown_spend_stops_experiment` |
| V12-04-04 父状态机 | DONE | `EXPERIMENT_TRANSITIONS`、`test_stop_before_start_marks_cancelled`、`test_stop_mid_run_leaves_remaining_pending` |
| V12-04-05 幂等启动 | DONE | `test_create_is_idempotent_by_key`、`test_duplicate_submit_does_not_create_second_run_set` |
| V12-04-06 断点续跑以子局为单位 | DONE | `test_resume_after_interruption_fills_gaps`、`test_resume_only_runs_pending_children` |
| V12-04-07 CLI/Python API + append-only 事件 | DONE | `scripts/run_v12_matrix.py`、`runs/lab/<id>/events.jsonl` |
| 补充实验流程（中断/未知消费/未执行 → 新实验） | DONE | `supplement_candidates` / `create_supplement`、`tests/test_v12_supplement.py`（11 项） |

**Gate 4**：通过。预检零请求（`test_dry_run_does_not_touch_disk`）；54 局 dry-run 通过（`test_fifty_four_cell_dry_run_is_zero_cost`）。

## Batch 5（P0）聚合、配对与导出

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-05-01 六类互斥分类 + 有效分母 | DONE | `lab/compare.py::classify_child`、`test_valid_denominator_excludes_provider_errors` |
| V12-05-02 配对统计 | DONE | `build_comparison`、`pair_records` |
| V12-05-03 五态保留、不补零 | DONE | `test_metrics_do_not_fill_zero_for_missing_states` |
| V12-05-04 `COMPARABLE`/`DESCRIPTIVE_ONLY`/`INCOMPARABLE` | DONE | 4 个不可比测试 |
| V12-05-05 五种导出 | DONE | `lab/report.py::write_exports` |
| V12-05-06 聚合单测（不等量 seed、缺失、unknown、全失败、全成功等） | DONE | `tests/test_v12_compare.py` 16 项 |

**Gate 5**：通过。`exports/runs.csv` 可独立复算 `summary.json`（`selfcheck.export_recompute`）。

## Batch 6（P1）Reflection

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-06-01 公开触发器（无进展/重复被拒/重复动作/空转） | DONE | `lab/policies/reflection.py::_detect` |
| V12-06-02 次数/冷却/费用限额 | DONE | `test_reflection_is_bounded_by_max_reflections`、`test_reflection_cooldown_limits_frequency` |
| V12-06-03 只给公开历史/摘要 | DONE | `test_reflection_trigger_is_rule_based_not_model_decided` |
| V12-06-04 记录触发证据/决策索引/额外费用 | DONE | `reflection_triggered` 事件含 `payload.evidence`、`requests` |
| V12-06-05 独立小试验集 | DONE（协议） | `experiment-protocol.md` §2 明确反思不进 54 局主矩阵 |

**Gate 6**：通过。

## Batch 7（P1）诊断与 Diff

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-07-01 结构化 `Finding` | DONE | `lab/contracts.py::Finding` |
| V12-07-02 基础行为检测 | DONE | 18 类诊断规则 |
| V12-07-03 六图专属证据规则 | DONE | `_map08/_map16/_map18/_map22/_map26/_map30` |
| V12-07-04 事件序列对照（不用第 n 步硬减） | DONE | `test_pairwise_diff_handles_length_mismatch_without_naive_subtraction` |
| V12-07-05 首次差异/失败链路/证据不足/下一次假设 | DONE | `pairwise_diff` + `diff_hypotheses` |
| V12-07-06 LLM 解说默认关闭 | DONE（可选路径未实现） | 核心诊断零 API；提纲标注"可选"，未实现已在 `gap-audit.md` 披露 |
| V12-07-07 正负 fixture | DONE | `tests/test_v12_diagnostics.py` 22 项含否定用例 |

**Gate 7**：通过。

## Batch 8（P1）六图可视化

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-08-01 view-model 隔离层 | DONE | `lab/visualization.py` |
| V12-08-02 MAP-08 诊断漏斗 | DONE | `_map08`、`test_map08_funnel_shrinks_candidates` |
| V12-08-03 MAP-16 占用时间线 | DONE | `_map16` |
| V12-08-04 MAP-18 故障/恢复 Gantt | DONE | `_map18` |
| V12-08-05 MAP-22 只画已发现路标 | DONE | `_map22`、`test_map22_only_draws_discovered_nodes` |
| V12-08-06 MAP-26 维修事件链 | DONE | `_map26` |
| V12-08-07 MAP-30 证据卡片 | DONE | `_map30`、`test_map30_evidence_cards_only_include_recorded_entries` |
| V12-08-08 其余 24 图通用回退 | DONE | `_generic`、`test_generic_fallback_for_other_maps` |
| V12-08-09 代表性 fixture | DONE | 真实 SIMULATED 轨迹 + 合成 UI fixture |

**Gate 8**：通过。六图全部 `available=True`，无隐藏真值，空态可解释。

## Batch 9（P1）Lab 网页与报告

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-09-01 Lab 入口，V11 六页不受影响 | DONE | `ui/app.py::VIEWS`、`test_lab_views_are_in_navigation` |
| V12-09-02 配置页 + 矩阵 + 显式费用确认 | DONE | `ui/lab.py::_config_view` |
| V12-09-03 监控页 + 停止 | DONE | `_monitor_view` |
| V12-09-04 结果页（概览/可比性/配对/成本/明细/五态/失败） | DONE | `_result_view` |
| V12-09-05 并排回放/差异锚点/证据/JSON+CSV+MD 导出 | DONE | 「证据与差异」「导出」标签页 |
| V12-09-06 可读 Markdown 报告 | DONE | `lab/report.py::build_report` |
| V12-09-07 空状态与防误用提示 | DONE | 三个页面的空态 + 未批准提示 |
| V12-09-08 复用 design tokens、中文、窄屏 | DONE | `docs/v12/screenshots/07-lab-results-mobile.png` |

**Gate 9**：通过。浏览器 E2E 走通"配置 → 预检 → 离线提交 → 运行 → 对照 → 回放 → 报告导出"。

## Batch 10（P2）第三方 SDK 与只读导入

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-10-01 SDK 级插件入口 | DONE | `lab/sdk.py::install_plugin` |
| V12-10-02 `examples/custom_agent/` | DONE | 示例策略 + README |
| V12-10-03 registry allowlist | DONE | `AGENT_ARENA_LAB_PLUGIN_ALLOWLIST`、`test_plugin_allowlist_blocks_unknown_module` |
| V12-10-04 纳入可比性检测 | DONE | `agent_config_hash` / `agent_version` |
| V12-10-05 只读导入 + schema/大小/hash 校验 | DONE | `read_public_run_file`、5 项导入测试 |
| V12-10-06 `adapter-api.md` + FAQ | DONE | `docs/v12/adapter-api.md` |

**Gate 10**：通过。

## Batch 11（P2）稳健性与质量门禁

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-11-01 `scripts/verify_v12.py` | DONE | 15/15 通过 |
| V12-11-02 CI 浏览器 E2E | DONE | `.github/workflows/ci.yml` `lab-e2e`（`continue-on-error`） |
| V12-11-03 430px/桌面/深色截图 + 可访问性 | DONE | 8 张截图；新增 `lab/a11y.py` + `scripts/a11y_v12.py`（对比度/焦点/DOM/键盘），修复 4 个真实缺陷 |
| V12-11-04 Windows/Ubuntu/macOS | PARTIAL | Windows 实测；Ubuntu 由 CI 覆盖；**macOS `NOT_VERIFIED`** |
| V12-11-05 mypy/Ruff/pytest/lock/freeze/复算/独立检查 | DONE | 见 `validation-report.md` |
| V12-11-06 三组 Demo 包 | DONE | `docs/v12/demo/` |
| V12-11-07 压力/故障测试 | DONE | `tests/test_v12_robustness.py` 13 项 |

**Gate 11**：通过（macOS 与真机可访问性除外，已披露）。

## Batch 12 真实 API 验证

**状态：已获用户授权（"可以用 API"），Pilot 与主矩阵已执行。** 明细见 `docs/v12/mimo-results.md`。

| 任务 | 状态 | 说明 |
|---|---|---|
| V12-12-01 展示规格与预算并记录批准 | DONE | `LiveApproval(approved=True, approved_by="user", max_cost_cny=6.00)`；预检零请求 |
| V12-12-02 3–6 局 Pilot | DONE | 6 局（MAP-22/26 × 3 架构 × seed 0），131 请求，¥0.0995，0 未知消费 |
| V12-12-03 预登记 54 局主矩阵 | DONE | 六图 × 3 seed × 3 架构，54/54，¥1.4718 |
| V12-12-04 Provider/环境/策略/预算失败分开编码 | DONE | 六类分母 + `Finding.confidence_scope` + 约束阶梯（DCR-V12-04） |
| V12-12-05 反思独立小矩阵 | DONE | 12 局消融（¥0.09626428）；**两臂 `reflection_triggered` 均为 0**（触发器未激活，DCR-V12-05） |
| V12-12-06 核对 usage 与本地费用估算 | DONE | 159 局 `run_started` = `run_settled`；结算 ¥5.43680012；未知 ¥0 |
| 衍生实验：补充 / 版本复跑 / 预算扩展 / 重复 | DONE | 4 类各 1 条真实产物；`--supplement-of` / `--rerun-of` / `--budget-ext-of` / `--replicate-of` |
| 接口与口径缺陷（DCR-V12-01/02/03/04） | DONE | 复测：拒绝率 96.2%→0%、`route_recall` 从 N/A→VALID、约束阶梯量化 |

## Batch 13 验收与文档

| 任务 | 状态 | 证据 |
|---|---|---|
| V12-13-01 README/architecture/scope/研究总纲 | DONE | 见对应文件 |
| V12-13-02 validation-report / release-checklist | DONE | 本目录 |
| V12-13-03 final-report | DONE | `final-report.md` |
| V12-13-04 可复现演示脚本 | DONE | `scripts/demo_v12.py`（退出码 0） |
| V12-13-05 diff/安全/冻结/hash 审核 | DONE | `validation-report.md` §6 |
| V12-13-06 阶段标记 + 下一阶段 backlog | DONE | `final-report.md` §NEXT |

## 交付后追加（用户指示"先把其他的做完，可以用 API"）

| 项 | 状态 | 证据 |
|---|---|---|
| 可访问性自动审计（主题对比度 / 焦点 / DOM / 键盘） | DONE | `lab/a11y.py` + `scripts/a11y_v12.py`；25 项测试；修复 4 个真实缺陷 |
| 补充实验流程（中断 / Provider 错误 / 未知消费 / 取消 / 未执行） | DONE | `supplement_candidates` / `create_supplement`；14 项测试 |
| 版本复跑（新契约版本下重跑已完成条件） | DONE | `create_version_rerun`；5 项测试 + 运行时版本指纹 |
| 预算扩展（抬高请求/token/费用上限） | DONE | `create_budget_extension`；7 项测试 |
| 重复实验（同版本同配置再跑） | DONE | `create_replicate`；5 项测试 + `summarize_v12_replicates.py` |
| 运行时版本指纹（防"改完代码复跑命中旧实验"） | DONE | `lab/runtime_version.py`、`ExperimentSpec.runtime_version` |
| V12 研究投影指标（`v12.projection.route_recall`） | DONE | `lab/metrics_v12.py`；导出 `namespace` 列；13 项测试 |
| 父实验子局链接对账（真实事故回归） | DONE | `_reconcile_children`；`test_stale_child_link_is_reconciled_from_real_run_state` |
| CLI `--resume` / `--rerun-of` / `--supplement-of` / `--budget-ext-of` / `--replicate-of` / `--timeout 0` | DONE | `scripts/run_v12_matrix.py` |
| 真实 Pilot 6 局 | DONE | ¥0.09949940 |
| 真实主矩阵 54 局 | DONE | ¥1.47181116 |
| MAP-22 契约修复复跑 9 局 + 口径对齐复跑 9 局 | DONE | ¥0.21606796 / ¥0.23872508 |
| MAP-30 预算扩展（180 请求）+ token 扩展（600k） | DONE | ¥1.09918720 / ¥1.49856088 |
| MAP-16 / MAP-18 种子覆盖（seed 3 / 3,4） | DONE | ¥0.00632096 + ¥0.00846188 / ¥0.07019220 |
| 重复实验 36 局（2 次观测翻转 22.2%、3 次观测 25.0%） | DONE | ¥0.45515672 |
| DCR-V12-01…04 记录 | DONE | `docs/v12/dcr/` |
| 真实结果档案（脱敏） | DONE | `docs/v12/real-runs/` |

## 下一步入口

1. 重复实验扩到 3 次/条件（当前翻转率 22.2%）
2. MAP-22 路线日志策略（策略变量）
3. MAP-30 三档预算固定 + 预检提示可跑回合数
4. Provider 账单对账
5. macOS / Ollama（按用户指示暂缓）

## 收尾（2026-10-26）

按执行提纲逐项复核：无静默跳过的必做项。本轮补做 §4.3 的三条开关消融
（Memory / Planning / Reflection，12 局 ¥0.09626428，明细见 `ablations.md`；
Reflection 为"触发器未激活"，见 DCR-V12-05），并把逐项状态收敛到
`docs/v12/gap-audit.md`（5 项未完成 + 3 项部分完成，均有原因）。

真实实验累计：**20 个实验 / 159 局 / 5 641 请求 / ¥5.43680012 / 未知 ¥0**，
剩余 ¥0.5632 主动保留。
