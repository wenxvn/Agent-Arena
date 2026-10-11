# V1-07 Reflection 与 UI（T7）

> 两者为独立验收子阶段。无新增收益证据就不强行实现 Reflection；无可靠数据契约就不做复杂控制台。

## T7-A ReflectionAgent（研究性、条件触发）

### 1. 现状与门槛

- T2–T4 已确认可被反思修复的重复模式：`REPEATED_CODE_READ`（53 次极端）、`WRONG_TOOL_AT_TERMINAL`（68 hits）、读码后回游、无进展 look 簇。门槛“仍有可修复重复错误”**满足**。
- 但：45/45 已证不加 Reflection 也能通关（剩效率问题）；Planning v1 已证高频第二调用≠策略变化（85% call ratio/0% 完成）。**第二调用有效性未证**，E1/E3 更便宜且未做。

### 2. 最小设计（若实施，需新 spec）

- 新建 `agents/reflection.py:ReflectionAgent(ReactAgent)`，复用 `request` 签名；`reset/observe/finish` episode-local 清空（仿 `planning.py:78-112`）。
- 触发只依赖公开历史：连续无进展 N=3（沿用 `monitor no_progress_threshold`）、重复失败 M=2（沿用 `monitor failure_count`）、同子目标重复 K=3–5、重复已知事实 ≥2、导航环（已有规则）。输入 `Observation/ToolResult/ProgressEvent/PublicFact/StepTrace`，禁 `WorldState`/oracle/完整思维链。
- 必须第二模型调用：新增 `output_contract="reflection"` + `StepTrace.reflection_*` + `Provenance.reflection_*` + benchmark `reflection_*` 分账（仿 planner），不得隐藏 token 成本。反思输出非执行性短摘要，最终 Action 仍走统一校验。
- 对照：同模型同 H/R/P 同 world 同 budget，`Reflection off/on`，判 `Success@K`/重复拒绝率/token 效率，不看无限步成功率。

### 3. Gate 决策：**deferred**

> 当前 45/45 证明剩余瓶颈是终点工具接地与读码后导航效率，而非缺少反思层；Planning v1 高频重规划零完成率证明第二模型调用本身不带来策略变化。在完成 E1/E3 消融与 Planning 同上下文对照、并以同预算证明 off/on 改善前，ReflectionAgent 继续 deferred，不新增实现。

## T7-B Streamlit UI（只做研究可视化 MVP）

### 1. 数据契约（verified 稳定，可只读消费）

- `ui/__init__.py` 仅 1 行 docstring，无实现；`architecture.md:28,51` 明确 Streamlit 延后到 Release 3。
- Episode trace schema v2（`trace.py:39-163`）：头 + `ExperimentProvenance`（全部开关/model/hash）+ `StepTrace`（observation/decision_reason≤280/action/result/tokens/runtime_feedback≤500/progress/planner_*）+ 脱敏（`_redact_value`）。
- Benchmark CSV 全字段（`benchmark.py:22-90`，含 Eval v2 `state_progress/epistemic/new_fact_rate/repeated_*/navigation_cycle/planner_call_ratio`）+ `failure_analysis.json/csv` + CLI `analyze-trace(s)`。
- 自主性三档 UI 必须原样显示：纯 observation / world-declared phase guidance（`public_phase_context_enabled=true`，不得标“自主发现”）/ `planner_assisted`（红字“辅助上界，非自主”）+ guarded/planning/candidate_select。

### 2. 最小只读 MVP（本轮未实施）

三页只读：①单 trace 步骤回放；②benchmark 对照表（读 CSV + `conditions.aggregates`）；③失败分布。经 `read_episode_trace`/`csv.DictReader` 加载，不新增 schema；禁调 `Runner/provider/Environment.step`；禁读 `.env`/密钥（CI grep `OPENAI_API_KEY|DASHSCOPE_API_KEY|get_secret_value` 在 `ui/` 零命中；展示白名单仅 provenance 非秘密字段）。

### 3. 验收

可加载一份已有 trace、复盘 Action 链、对比两种条件。本轮：设计论证 + deferred 决策完成，实现 **not run**（blocked：T1/T2 契约刚稳定 + 资源）。
