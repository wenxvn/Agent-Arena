# MAP-11｜极地｜中等｜待接入运行时

> 状态：`design_only`。本图没有 V4/V6 运行时、没有 Episode Trace、没有真实模型结果。
> 设计卡：[../maps/MAP-11.md](../maps/MAP-11.md)。人工复核：`pending_human_review`。
> 本文件只记录“接入运行时还缺什么”，不把设计态写成已验证，也不伪造零分。

## 1. 为什么现在不能跑

- 能力构念：`risk_strategy`。
- 阻塞项（必须人工确认）：公开 `posterior_unstable_probability_belief` 已替代部分推断，条件须标“信息可用性”
- 对应 DCR/卡片：V7-DCR-005。
- 当前缺失：环境与 Action 契约、Oracle 回放、公开/私有字段冻结、V7 extractor、手算 fixture。
- 明确未发生：0 次真实 API、0 个新账本、0 条 `runs/` 或 `results/` 产物。

## 2. 建议第一刀（未批准，不代表已实现）

噪声侦察 + 短险/长稳两路

第一刀只允许覆盖一个可证伪的机制切片；完成前不得把其余机制一起塞进通用生成器。

## 3. 已注册的指标契约（全部 `implemented=False`）

- `map11.abandoned_reachable_targets`（失败归因/成本指标，人，lower_is_better）：缺失规则“运行时缺少来源事件 → UNAVAILABLE；不得默认为 0”
- `map11.first_clue_delay`（失败归因/成本指标，tick，lower_is_better）：缺失规则“运行时缺少来源事件 → UNAVAILABLE；不得默认为 0”
- `map11.rescue_count`（核心连续指标，人，higher_is_better）：缺失规则“运行时缺少来源事件 → UNAVAILABLE；不得默认为 0”
- `map11.rescuer_hypothermia`（安全/约束指标，次，lower_is_better）：缺失规则“运行时缺少来源事件 → UNAVAILABLE；不得默认为 0”
- `map11.resource_cost_per_rescue`（核心连续指标，资源/人，lower_is_better）：缺失规则“运行时缺少来源事件 → UNAVAILABLE；不得默认为 0”

这些指标已在 `src/agent_arena/v7/metrics/registry.py` 注册并带 `valid_range`、缺失/截尾规则；
调用 `compute_metrics` 必须抛 `NotImplementedError`，不得返回 0 或合成总分。

## 4. 接入时必须同时交付

- [ ] 规则冻结：核对 `worlds/v4/MAP-11/map_spec.yaml`、`DESIGN.md` 与设计卡 §2，冲突先开 DCR。
- [ ] 独立 Oracle：至少一条构造可行解；有最优证明则写证明，没有则明确写“仅构造解”。
- [ ] 手算 fixture：把设计卡 §5 的两条轨迹变成真实 trace 重放，断言具体数值。
- [ ] 失败/边界 fixture：设计卡 §6 的三个机制失败与 §7 的两个边界都必须在环境里复现。
- [ ] V7 extractor：新增 `src/agent_arena/v7/metrics/map11.py`，逐条实现上述指标。
- [ ] 泄漏检查：私有字段不得进入 Observation、prompt、公开 trace；条件对照只差预登记机制。
- [ ] 验收记录：真实命令、真实输出、未解决项、DCR 状态与 `git diff --check`。

## 5. 当前结论

这张图目前只有**逐图设计卡与指标契约**。在人工确认阻塞项、完成运行时和上述验收之前，
它不能进入模型对照，也不能与六张已运行图合并统计。人工复核签署前，状态保持
`pending_human_review`。
