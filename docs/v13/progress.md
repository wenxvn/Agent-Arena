# V13 进度与验收记录

> 本文件记录**每个批次的落盘证据**：改了什么、跑了什么命令、结果是什么、状态是什么。
> 状态只用这几种：`DONE` / `PARTIAL` / `WAITING_USER_APPROVAL` / `BLOCKED_EXTERNAL` / `NOT_DONE`。

- 起始 HEAD：`32e27826eab33093d2d5d640d08f47bbd4974df3`
- 执行环境：Windows 11（`Windows-11-10.0.26200-SP0`）、Python 3.13.3、uv 0.13.3
- 真实付费请求：**0 次**（本文件所有结果要么是离线、要么是只读历史、要么是 SIMULATED）

## Batch 0｜基线审计与工作台

| 任务 | 状态 | 证据 |
|---|---|---|
| 00-01 HEAD / 工作区 / 环境 | DONE | HEAD `32e2782`；工作区只有两个未跟踪研究提纲；Python 3.13.3 / uv 0.13.3 |
| 00-02 阅读资料与调用链 | DONE | `lab/` 22 个模块、`ui/lab.py`、`web/` 全量入口、`docs/v12/*` |
| 00-03 运行 V12 质量门禁 | DONE | `uv run pytest -q` → **1525 passed**（166.31s，与 V12 文档一致） |
| 00-04 `audit.md` | DONE | `docs/v13/audit.md`（含 V12 数字逐项复核与 17 项缺口） |
| 00-05 `progress.md` / `decisions.md` | DONE | 本文件 + `docs/v13/decisions.md` |
| 00-06 协议初稿 | DONE | `docs/v13/experiment-protocol.md`（口径先冻结） |

## Batch 1｜公平性 / 协议 / 可比性

| 任务 | 状态 | 证据 |
|---|---|---|
| 01-01 comparability profile | DONE | `lab/v13/comparability.py::comparability_profile`（14 个维度，缺失标 `UNKNOWN`） |
| 01-02 共享提示 vs 被测干预 | DONE | `compare_profiles`：`base_prompt_hash` 必须一致，`effective_prompt_hash` 属干预 |
| 01-03 采样参数登记 | DONE | `contracts.SamplingProvenance`（默认 `UNKNOWN`，永不返回 "deterministic"） |
| 01-04 实验身份 + `replicate_index` | DONE | `MatrixCell.replicate_index`；`condition_key` 在 0 时与 V12 逐字一致 |
| 01-05 两独立父实验配对 | DONE | `cross_experiment_pairs`（按 `(map, seed, replicate_index)`） |
| 01-06 跨版本硬拒绝 | DONE | `compare_profiles` 硬不匹配 → `INCOMPARABLE`；`test_v13_comparability.py` 11 项 |
| 01-07 protocol manifest | DONE | `contracts.ProtocolManifest`（`fingerprint()` 参与实验指纹） |

## Batch 2｜重复稳定性

| 任务 | 状态 | 证据 |
|---|---|---|
| 02-01 复用并扩展重复入口 | DONE | `experiment.create_replicates`（同一实验内 N 次重复，独立幂等键） |
| 02-02 预检给总子局/费用/重复口径 | DONE | `PreflightResult.replicates / cells_per_condition / conditions`；不编造耗时 |
| 02-03 只读导入 V12 历史 | DONE | `lab/v13/history.py`（14 份 CSV 登记，含单局预算元数据） |
| 02-04 `repeat_variability.csv/json/md` | DONE | `docs/v13/repeat_variability.*`（V13 生成，可复算） |
| 02-05 防单位错误 | DONE | `seed_blocks`（按 seed 分块）+ 报告固定措辞"重复 ≠ 新 seed" |
| 02-06 UI 提示 | DONE | 「Lab · 稳定性与效度」页：翻转率 ≥20% 警示、单次观测提示 |
| 02-07 模拟场景测试 | DONE | `test_v13_runtime.py::test_replicate_flow`（3 局不覆盖、幂等） |

**复算结果**：2 次观测翻转率 **0.2222（4/18）**、3 次观测 **0.25（3/12，排除 6 组跨版本）**，
与 V12 公布值逐字一致。

## Batch 3｜Memory 策略优化

| 任务 | 状态 | 证据 |
|---|---|---|
| 03-01 审计 v1 写入/容量/渲染 | DONE | `docs/v13/memory-study.md` §1（容量 24、1200 字符、写入条件） |
| 03-02 版本化配置 | DONE | `memory.v2`（`route_log` 默认 True，新增 `route_mode`/`compress`/`dedupe`/`relevance`） |
| 03-03 只累积被接受的移动 | DONE | `test_memory_v2_route_only_accumulates_accepted_moves`（被拒/非法不写入） |
| 03-04 写入机制显式区分 | DONE | `route_mode=env_write`（占 1 次决策、记成功/失败）vs `context_only`（0 动作） |
| 03-05 三类瓶颈诊断 | DONE | `bottleneck()`：`NO_RECORD` / `RECORDED_TOO_SHORT` / `RECORDED_NOT_REFERENCED` / `WRITE_REJECTED_INTERFACE` |
| 03-06 MAP-22 on/off 设计 | DONE | `ABLATION_TEMPLATES["memory.route_log"]`；离线脚本轨迹验证口径 |
| 03-07 `memory-study.md` | DONE | 含假设、旧证据、成本权衡、待批准矩阵 |

## Batch 4｜Planning 策略优化

| 任务 | 状态 | 证据 |
|---|---|---|
| 04-01 审计 Planner 调用 | DONE | `docs/v13/planning-study.md` §1 |
| 04-02 `planning.v2` | DONE | 三模式 `adaptive` / `initial_only` / `periodic` + `min_steps_between_plans` + `budget_aware` |
| 04-03 结构化公开目标 | DONE | Planner 输出仍无 `tool`/`action`；`test_planning_v2_planner_output_is_non_executive` |
| 04-04 减少重复规划 | DONE | 公开触发（无进展/连续被拒/目标变化/进度变化 + TTL）；TTL 延迟留事件证据 |
| 04-05 三类分离消融 | DONE | `planning.on_off` / `planning.replan_off` / `planning.low_frequency` 三个模板 |
| 04-06 每请求成本归因 | DONE | `snapshot()["plan_requests"]`（触发、决策索引、token、延迟） |
| 04-07 `planning-study.md` | DONE | 含成功/失败路径与"哪些是证据、哪些是假设" |

## Batch 5｜消融与核心验证

| 任务 | 状态 | 证据 |
|---|---|---|
| 05-01 标准模板 | DONE | 7 个模板，全部 `single_switch_ok=True` |
| 05-02 MAP-16/18/22 消融计划 | DONE | `docs/v13/core-evidence.md` §3（合法 seed + 重复数 + 指标） |
| 05-03 版本比较 vs 消融 | DONE | `classify_pair` → `VERSION_COMPARISON` / `MULTI_SWITCH_COMBINATION` |
| 05-04 三张证据包 | DONE | `build_evidence_pack`；`docs/v13/core-evidence.md` 三节 |
| 05-05 预检与 LIVE proposal | DONE | `docs/v13/live-budget-proposal.md`；`--ablation` 只预检不自动提交 |
| 05-06 模拟跑通管线 | DONE | `scripts/demo_v13.py`（16 局 SIMULATED，标题强制 `SIMULATED`） |
| 05-07 保留负面结果 | DONE | 报告第 4 节「负面结果」；`test_report_keeps_negative_results` |

## Batch 6｜Reflection

| 任务 | 状态 | 证据 |
|---|---|---|
| 06-01 复盘 DCR-V12-05 | DONE | `docs/v13/reflection-study.md` §1 |
| 06-02 公开触发器定义 | DONE | 4 个触发器 + `eligible`/`triggered` 分离计数 |
| 06-03 SIMULATED 真触发 | DONE | `reflection-trigger-probe.json`：`triggered=2`、`TREATMENT_TRIGGERED` |
| 06-04 冷却/上限/trigger-only | DONE | `cooldown_steps` / `max_reflections` / `trigger_only`（0 请求臂） |
| 06-05 激活率/恢复率/误触发 | DONE | `activation_rate` / `recovery_rate` / `false_triggers`；零触发 → `NO_TREATMENT_EXPOSURE` |
| 06-06 LIVE 小矩阵 | WAITING_USER_APPROVAL | `docs/v13/live-budget-proposal.md` E3 |
| 06-07 `reflection-study.md` | DONE | 含"未获授权不得宣称实测有效" |

## Batch 7｜MAP-30 与六图效度

| 任务 | 状态 | 证据 |
|---|---|---|
| 07-01 MAP-30 阶梯重分析 | DONE | `map30_ladder`：3 档，`ACCUSATION_REJECTED` 1/4/2 |
| 07-02 预算分解与回合数区间 | DONE | `budget_capacity`（来自观测分布，声明不是承诺） |
| 07-03 三维阶梯设计 | DONE | 候选档 180 请求 / 600k token / ¥0.25 **需批准**，不默认启用 |
| 07-04 MAP-30 失败分型 | DONE | 5 类：截尾 / 证据不足 / 法庭被拒 / 推理链中途 / 成功 |
| 07-05 六图效度审查 | DONE | `six_map_audit`（可复合标签 + 证据） |
| 07-06 天花板图建议 | DONE | MAP-08/26 → 「保留为回归能力案例，暂不作为区分度排名样本」 |
| 07-07 文档 | DONE | `docs/v13/map-validity.md`、`map30-budget-ladder.md` |

## Batch 8｜诊断与画像

| 任务 | 状态 | 证据 |
|---|---|---|
| 08-01 复用 Finding 并核对证据锚 | DONE | `taxonomy.attribute_run`（每条锚到 `decision` 步） |
| 08-02 七层归因 | DONE | `INTERFACE_CONTRACT` / `MEASUREMENT_COVERAGE` / `BUDGET_CENSORED` / `ENVIRONMENT_MECHANISM` / `POLICY_BEHAVIOUR` / `PROVIDER` / `UNKNOWN` |
| 08-03 正反例 fixture | DONE | `FIXTURES` 4 组 8 例，`check_fixtures()` 全绿 |
| 08-04 六维机制画像 | DONE | `capability_profile`（不平均 326 个指标） |
| 08-05 每维证据等级 | DONE | 适用图数 / 可测局 / 成功失败截尾 / 代表指标 / 等级；缺失不补 0 |
| 08-06 版本适用性 | DONE | `version_comparable`；`label_status="agent_reviewed"`（不自行 `human_approved`） |
| 08-07 文档 | DONE | `docs/v13/diagnosis-taxonomy.md`、`capability-profile.md` |

## Batch 9｜可视化与 Web UI

| 任务 | 状态 | 证据 |
|---|---|---|
| 09-01 复查 Lab 三页 | DONE | 新增两页（稳定性与效度、报告与审计），共 5 页 |
| 09-02 同条件不同 Agent 对照 | DONE | 结果页保留配对表 + Diff；稳定性页逐条件明细 |
| 09-03 重复实验视图 | DONE | 翻转率、截尾数、可比性、`DESCRIPTIVE_ONLY` 提示 |
| 09-04 六图可视化边界 | DONE | MAP-22 被拒移动单列、不计边（V12 已修，V13 未回退） |
| 09-05 预检/门禁/授权状态 | DONE | 配置页 stat tiles + 重复口径提示 + 授权状态 |
| 09-06 分页与状态保持 | DONE | `web/index.py`（懒加载 + 增量刷新 + 服务端分页）；`RunService.list_runs` 也改为走索引 |
| 09-07 主题/窄屏/键盘审计 | PARTIAL | 离线审计沿用 V12（0 critical/serious/moderate）；**本机未跑浏览器审计**（见 gap） |

## Batch 10｜报告与账本

| 任务 | 状态 | 证据 |
|---|---|---|
| 10-01 结构化报告 | DONE | `build_report_v13`（Markdown）+ `report_payload`（JSON） |
| 10-02 默认离线模板 | DONE | 零 LLM；无任何"润色"调用 |
| 10-03 结论分级 + 锚点 | DONE | `SUPPORTED`/`TENTATIVE`/`INSUFFICIENT`/`NOT_TESTED`；`experiment:` / `run:` / `decision:` |
| 10-04 本地账本审计 | DONE | `audit_v13_ledger.py`：159 局 / 5641 请求 / ¥5.43680012 / 0 孤儿 / 0 重复 |
| 10-05 后台账单导入 | DONE（接口）+ `BLOCKED_EXTERNAL`（数据） | `write_bill_template` + `reconcile_bill`；无账单时 `NO_EXTERNAL_BILL_PROVIDED` |
| 10-06 不改历史账本 | DONE | 全部只读；差异只生成记录 |
| 10-07 快照/缺失/脱敏测试 | DONE | `test_v13_report_ledger.py` 19 项（含 `sk-` / `sealed_truth` 扫描） |

## Batch 11｜第三方 SDK

| 任务 | 状态 | 证据 |
|---|---|---|
| 11-01 复核 SDK | DONE | `lab/sdk.py` 与 `examples/custom_agent/` 未改语义 |
| 11-02 接入自检 8 项 | DONE | `sdkcheck.run_sdk_checks`：契约/公开观察/动作/钩子/预算/隔离/模式/版本 |
| 11-03 最简示例 | DONE | `docs/v13/sdk-guide.md`（编写 → 注册 → 运行 → 对照） |
| 11-04 异常隔离 | DONE | 插件抛错 → `policy_error`；敏感串被 `sanitize_text` 截断 |
| 11-05 受信任边界说明 | DONE | `sdk-guide.md` §6（不是沙箱） |
| 11-06 兼容测试 | DONE | `legacy_act_signature`（`act(observation, history)` 仍可用） |

## Batch 12｜CI 与压测

| 任务 | 状态 | 证据 |
|---|---|---|
| 12-01 阅读 CI 与 E2E | DONE | `.github/workflows/ci.yml`；`continue-on-error` 原因已定位 |
| 12-02 固定无 Key E2E | DONE（本地） | 本机 `scripts/e2e_lab.py --start` 结果见 `validation-report.md` |
| 12-03 E2E 改为阻断门禁 | **PARTIAL** | 保留非阻断并在 gap-audit 记录（未取得连续可靠的 CI 证据） |
| 12-04 1k/5k 压力数据 | DONE | `lab/v13/perf.py`（临时目录、`stress_data=true`） |
| 12-05 冷热耗时/内存/输出 | DONE | `docs/v13/performance-report.md`（本机实测数字） |
| 12-06 负向场景 | DONE | 损坏 JSONL / 孤儿任务 / 重复结算 / 未知消费 / 账单缺列 |
| 12-07 旧流程回归 | DONE | V11/V12 测试全绿；Lab 5 页 stub 冒烟 |
| 12-08 文档 | DONE | `performance-report.md` |

## Batch 13｜交付

| 任务 | 状态 | 证据 |
|---|---|---|
| 13-01 文档入口 | DONE | `README.md`、`docs/architecture.md`、`docs/scope/scope.md`、`AGENTS.md` |
| 13-02 `verify_v13.py` | DONE | 18 项，`--report` 落盘 |
| 13-03 `demo_v13.py` | DONE | 16 局 SIMULATED + Reflection 探针 + 报告 |
| 13-04 全量门禁 | DONE | 见 `validation-report.md` |
| 13-05 LIVE 归档 | WAITING_USER_APPROVAL | 本轮无新 LIVE；历史只读归档已在 `docs/v12/real-runs/` |
| 13-06 `gap-audit.md` | DONE | 逐任务状态 |
| 13-07 `final-report.md` | DONE | what/why/how/results/limitations/next |
| 13-08 交付清单 | DONE | `release-checklist.md` |
