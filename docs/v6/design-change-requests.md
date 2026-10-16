# V6 设计差异申请（DCR）

本文件记录每一项对既有 V4/V5 资产的变更申请：原证据、修改理由、影响范围、潜在泄漏与回归测试。所有变更遵循“先记录、后修改”。历史 V5 实验、账本与 registry 字节与 hash 均不触碰。

## DCR-001：MAP-22 非记忆条件宣传了不可用动作（接口可读性）

- **原证据**：`runs/v5/.../map-22__history5__seed_{0,1,2}/agent_trace.jsonl`，共 173 次 `ACTION_NOT_AVAILABLE`，action 均为 `write_memory`；`history5_graph_memory` 局中大量 `return_to_camp` 而不移动（见 `docs/v6/v5-failure-audit.md` §2）。
- **问题**：`v5/prompts.py` 的 MAP-22 action contract 对所有条件列出 `write_memory`，但 `memory_enabled=False` 时环境拒绝它；`return_to_camp` 只设置目标、不移动，语义未在契约中说明。
- **V6 修订（仅 V6 层）**：V6 的 MAP-22 条件提示按条件裁剪动作集（非记忆条件不宣传 `write_memory`），并显式说明 `return_to_camp` 只设目标、移动必须用 `move{bearing}`；V6 环境把禁用记忆的返回码设为 `MEMORY_DISABLED`（通过 `disabled_memory_result` 参数）。**V4 默认行为与 V5 结果不变**，`ACTION_NOT_AVAILABLE` 仍是 V4 默认返回值。
- **影响范围**：仅 V6 prompt 与 V6 fixture；V4 环境默认路径、V5 trace/账本字节不变。
- **潜在泄漏**：无。仅简化公开契约，不注入隐藏信息。
- **回归测试**：`tests/test_scenario_v4_runtime.py`（默认行为）、`tests/test_v6_instances.py`（V6 返回码与可移动性）。

## DCR-002：V4 六图规则引擎参数化（最小可行重构）

- **原证据**：V6 需要结构性不同的拓扑/初态作为独立实例；原 V4 引擎把拓扑、初态、真值写死为模块常量，无法在不复制规则的前提下构造变体。
- **问题**：直接复制规则引擎会产生第二套规则、增加规则分叉风险；因此需要在**单一规则引擎**上开放实例参数。
- **V6 修订**：为 `Map08/16/18/22/26/30Environment` 增加可选关键字参数（拓扑、初态、故障、候选、容量、预算、案情等），**默认值严格复现已评审的 V4 场景**。V6 通过参数注入新实例。
- **影响范围**：`src/agent_arena/worlds/scenario_v4/map*.py`。默认行为不变；`validate_v4_runtime.py` 六图 Oracle 回放仍全绿；全项目 518 项测试通过。
- **潜在泄漏**：无。参数只由离线 fixture 注入，不进入模型请求。
- **回归测试**：`scripts/validate_v4_runtime.py`、`scripts/validate_v5_solvers.py`、`tests/test_scenario_v4_runtime.py`、`tests/test_v5_pilot_controls.py`、全量 `pytest`。
- **备注**：MAP-16 推广为任意列车数与区间容量；MAP-30 把证人问答泛化为数据驱动规则，`condition_key` 仍保留原键名。

## DCR-003：MAP-18 预警与被闭区段参数化

- **原证据**：`closed_segments` 与故障窗口 `5<=tick<10`、预警 tick 4、`FAULT_EDGE=R2_R3` 均写死，无法构造“不同闭塞段/发生时刻/持续时间”的独立故障情景。
- **V6 修订**：`Map18Environment` 接受 `fault_edge/fault_window/fault_enabled/alert_tick/horizon/success_threshold`；`closed_segments` 由 `fault_edge` 派生；`total_demand` 由 TASKS 求和。
- **影响范围**：默认值 = 原场景；Oracle 回放不变。
- **潜在泄漏**：无。预警信息仍为通用非定位文本。
- **回归测试**：`validate_v4_runtime.py` MAP-18 3 条 oracle。

## DCR-004：MAP-26 故障与备件预算参数化

- **原证据**：`FAULT_BY_SEED` 与 `spares_at_b=2` 写死；恢复轨道是单例。
- **V6 修订**：`Map26Environment` 接受 `fault_part/spares/carry_capacity/parts/nodes/edges/log_id`，可构造多个不同故障与备件预算的独立实例。
- **影响范围**：默认值 = 原场景；Oracle 回放不变。
- **潜在泄漏**：无。
- **回归测试**：`validate_v4_runtime.py` MAP-26 2 条 oracle。

## DCR-005：MAP-08 诊断矩阵参数化

- **原证据**：`EDGES/SIGNATURES/LEAK_BY_SEED` 写死，候选点仅 B/D/F。
- **V6 修订**：`Map08Environment` 接受 `edges/signatures/leak_by_seed/water_limit/sealant_count/test_ticks/wrong_repair_ticks`，公开 `published_candidate_set/prior/known_test_semantics` 由签名表派生。
- **影响范围**：默认值 = 原场景（`docs/v5/runtime-contract.md` 的候选集收缩语义保持）。
- **潜在泄漏**：公开语义只描述“各候选在各站的读数”，不揭示真值。
- **回归测试**：`tests/test_v5_pilot_controls.py::test_map08_candidate_set_sizes_shrink_by_observed_signature`。

## DCR-006：MAP-30 案情与证人规则参数化

- **原证据**：案情、NPC、证据、`ENTRY_ORDER`、`CLAIMS`、真凶 `MARA_VENN`、deadline 40 写死。
- **V6 修订**：新增 `Map30Case`/`WitnessRule` 数据模型；`Map30Environment(case=...)` 注入不同案情；证人问答改为一组有序规则（前置证据或前置案卷条目未满足则跳过，最后一条无前置规则作为弱回答兜底）。
- **影响范围**：模块级 `CLAIMS`/`ENTRY_ORDER`/`EVIDENCE` 等常量保留以兼容既有导入；默认 `DEFAULT_CASE` = 原场景。
- **潜在泄漏**：案卷仍只展开已记录 evidence 的公开 fact/text；未解锁证据不进入任何公开字段。
- **回归测试**：`validate_v4_runtime.py` MAP-30 3 条 oracle、`tests/test_v5_pilot_controls.py` 的 MAP-30 历史条件测试。

## DCR-007：非执行性可选字段不再作废整条决策

- **原证据**：真实 smoke（实验 `e479755e…`）中模型在未启用假设表的条件里把 `agent_hypothesis_table` 填成自由草稿（list），`decision_reason` 超过 280 字符，或把该字段嵌进 `action`；V4 的 `_clean_candidate` 因此返回 `action=null`，连续触发 `INVALID_ACTION_SCHEMA` 并 fail-closed。
- **V6 修订**：新增 `_v6_clean_candidate`：只严格校验可执行 Action（严格 schema + 每图字段形状 allowlist），把 `decision_reason` 视为自由文本、允许 `agent_hypothesis_table` 为空/草稿/嵌套并从 `action` 中剥离。
- **影响范围**：仅 V6 runner；V5 `_clean_candidate` 与 V4 契约不变。
- **潜在泄漏**：无。
- **回归测试**：`tests/test_v6_instances.py::test_v6_clean_candidate_is_lenient_about_optional_fields`。

## DCR-008：MAP-08 提示恢复交互语义

- **原证据**：真实 smoke 中模型反复提交 `interact{target_id:"B"|"D", operation:"pressure_test_B"}` 得到 `INVALID_TEST_LOCATION`/`INVALID_OPERATION`，从未完成测试。
- **V6 修订**：MAP-08 任务与动作契约写明只有 `pressure_test_X`/`pressure_test_Y`，`target_id` 必须是同名测试站，`repair_leak` 的 `target_id` 才是候选漏点。
- **影响范围**：仅 V6 提示。
- **潜在泄漏**：公开编码说明，不泄漏真值。
- **回归测试**：`scripts/validate_v6_leakage.py`（提示不得含 oracle 动作）。

## DCR-009：MAP-26 合法 ID 清单与公开循环提醒

- **原证据**：真实 smoke 中模型臆造 `log_1` 并在同一无效动作上循环 62 步，触发 provider 超时（`unknown_provider_spend`）。
- **V6 修订**：MAP-26 提示恢复合法日志/测试/部件 ID；V6 runner 新增只由自身公开结果派生的“最近 3 次动作都被拒”提醒（`runtime_feedback`）。
- **影响范围**：仅 V6 提示与 runner；提醒不含裁判信息。
- **潜在泄漏**：无（内容来自 Agent 自己的公开 action/result）。
- **回归测试**：`tests/test_v6_instances.py::test_public_repeat_reminder_only_fires_on_stuck_refusals`。

## DCR-010：MAP-30 公开案卷条目顺序；MAP-22 按实例最短路

- **原证据**：真实矩阵中 MAP-30 完整调查 0 案卷条目——合法 `entry_id` 在公开 Observation 中不可见（V5 靠固定前缀掩盖）；MAP-22 非 L3 实例的 `shortest_route_gap` 误用默认最优 8，导致 l1 出现负 gap。
- **V6 修订**：MAP-30 提示公开**案卷条目 id 顺序**（不含证据内容/真凶）；`Map22Scene.env_kwargs` 注入按实例 BFS 计算的 `optimal_moves`。
- **影响范围**：V6 提示与 scene 参数；公开信息仅结构性标签。
- **潜在泄漏**：无（不揭示哪条证据满足哪个条目，也不揭示真凶）。
- **回归测试**：`tests/test_v6_instances.py`、`scripts/validate_v6_instances.py` 的 MAP-22 最优核对。

## 不予变更（明确记录）

- 不修改任何 `worlds/v4/MAP-*/map_spec.yaml`、`oracle_trace.jsonl`、`planning/hand_traces.json`。
- 不修改 V5 spec 0018、V5 报告的原则性结论。
- 不触碰 `runs/v5/ledgers/`、`runs/v5/pilot_registry.json`、V2 已关闭账本。
- 不为提高通过率修改正式胜负谓词；V6 新实例一律标注 `review_status: pending_human_review`。
