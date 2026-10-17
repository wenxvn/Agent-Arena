# MAP-15｜金字塔｜困难｜会变化的迷宫

```yaml
map_id: MAP-15
world: pyramid
nominal_level: 困难
capability_primary: abstract_rule_transfer
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: c642621a45d3de9a1c4b31f25d032abc06dcd1376c541e5085d4e0baca9b3f2a
source_design_hash: b44f851e2e79f976f8a1831dc876c1350b9aa66b41e32c25cd2d9997b73cb263
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“动态规则归纳与迁移”。门色目标由 `墙符号色 × 全局 tick 奇偶` 决定：偶数 tick 目标色 = 墙符号色，奇数 tick 目标色 = 其互补色（红↔蓝、金↔绿）。A/B/C 是三间训练室，各有不同门色排列，只有一次成功通行会形成带标签样例；T 把门色扩为四种且重排，不回到训练区。核心不是背门号或训练序列，而是把“同色/互补”规则迁移到 T 的未见组合。

## 2. 真实规则字段

- 符号/门色：红、蓝、金、绿；互补配对红↔蓝、金↔绿。
- 判定：`choose_door(slot)` 在动作开始时读当前 tick；偶数目标=墙色，奇数目标=互补色；检查后 tick+1。错误留在当前区域，下一次按新 tick 重算。
- 状态：单向 `A→B→C→T`；训练区 A/B/C 各 3 门，T 4 门；错误扣 1 枚尝试资源（初始 4），正确不扣。
- 测试区：T 第 1 次错误可重试，第 2 次立即 `TEST_WRONG_LIMIT`；资源先耗尽则 `RESOURCE_DEPLETED`。
- 已知样例：A tick0 红墙 `[红,蓝,金]` 目标红槽1；B tick1 红墙 `[绿,蓝,红]` 目标蓝槽2；C tick2 金墙 `[蓝,金,绿]` 目标金槽2；T tick3 金墙 `[金,红,绿,蓝]` 目标绿槽3。
- 公开：区域、tick、tick 奇偶、当前墙/门色（检查后）、错误资源、测试错误、训练样例日志、规则假设、门状态。
- `inspect_symbols` / `record_rule` 不耗 tick、不改相位；`choose_door` 耗 1 tick。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map15.unseen_transition_accuracy` | primary | T 首次选择是否正确（0/1），按可评估 T 进入次数聚合 | 比例 / 高 | 可评估 T 进入次数 | 未进入 T → N/A |
| `map15.probes_to_target` | primary | 成功前 `choose_door` 次数 | 次 / 低 | 成功局 | 失败 → N/A |
| `map15.invalid_transitions` | guardrail | 错误 `choose_door` 次数（含训练/测试） | 次 / 低 | episode | 0 合法 |
| `map15.loop_states` | diagnostic | 同一区域同一 tick 奇偶下重复错误选择次数 | 次 / 低 | episode | 0 合法 |
| `map15.reset_losses` | diagnostic | 错误消耗的资源与额外 tick | 资源单位 + tick / 低 | episode | 0 合法 |

“未见状态预测”在本图是**代理**：动作契约没有显式 `predict`；T 的首次选择被当作对“未见奇偶×墙色组合”的预测。不得把它说成显式预测能力。

## 4. 能力混淆分析

- 高 T 首次正确率可能只因为“四种门色里猜中”，概率 1/4；必须报 `probes_to_target`、训练错误与规则记录。
- 低分可能由“把奇偶读成动作后状态”造成，不是规则归纳失败；用每步动作前 tick 与目标色序列归因。
- 高 `probes_to_target` 少可能只是训练区短；T 四门、训练三门，长度不可直接比较。
- `record_rule` 是零 tick 的自我记录，回执不评价真假；记录公式不等于会用公式。

## 5. 两条手算轨迹

**显式记录、零错（4 tick）**：A `inspect_symbols`（0 tick）→`choose_door(1)`（tick0 偶数，红=红，通过，tick1）→B inspect→`choose_door(2)`（tick1 奇数，红→蓝，槽2 蓝，通过，tick2）→C inspect→`choose_door(2)`（tick2 偶数，金=金，通过，tick3）→T inspect→`choose_door(3)`（tick3 奇数，金→绿，槽3 绿，通过，tick4）。指标：T 首次正确 1；probes 4；错误 0；重复 0；资源损失 0。

**从反馈迁移、恢复一次测试错误（5 tick）**：A/B/C 同样槽1/2/2 通过（tick3 进入 T）→T `choose_door(2)`（tick3 奇数，目标绿，槽2 红，错误，资源 4→3，tick4）→重新 inspect（tick4 偶数，金=金）→`choose_door(1)`（槽1 金，通过，tick5）。指标：T 首次正确 0；probes 5；错误 1；重复 0；资源损失 1 + 额外 1 tick。

## 6. 三个机制特有失败

1. **槽位号码记忆**：A 槽1 碰巧红门通过；到 B 仍选槽1，反复撞门，每次错误推进 tick 并改变目标色；4 枚资源耗尽，`RESOURCE_DEPLETED`，未进入 T。
2. **奇偶读成动作后状态**：在 A 按 `tick+1` 预测，t0 选蓝、t1 选红、t2 选蓝、t3 选红，全部与动作前规则相反；资源耗尽。
3. **测试区沿用旧选择**：训练三室全过；T tick3 选槽2 红错一次，tick4 后仍重复槽2 红，第二次错误 `TEST_WRONG_LIMIT`；正确恢复应重算偶数目标金并选槽1。

## 7. 两个边界

- **T 错 1 次可恢复、错 2 次失败**：第 1 次错误只扣资源并推进 tick；第 2 次立即失败。必须用同一训练前缀只改 T 的第二次选择验证。
- **资源 1 时再错**：错误先扣到 0，立即 `RESOURCE_DEPLETED`，优先于 `TEST_WRONG_LIMIT`；这是两个终止码的优先级边界。

## 8. 信息泄漏负例

若 Observation 预告 T 的门色布局、未来 tick 目标色或直接给规则 `R_EVEN_SAME_ODD_COMPLEMENT`，规则归纳被替代。V7 只允许公开当前区域、动作前 tick、当前墙/门色与训练样例；T 布局只在进入后公开。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有两条成功路线（零错/恢复一次测试错误）；`failure_traces/cases.yaml` 有三条失败；`planning/rule_audit.py` 复核四个目标色、恰一匹配门、同墙异相位对照与测试序列未重复，输出 `rule_audit.json`。**没有运行时**；审计证明规则自洽，不证明 Agent 可迁移。

## 10. 与同世界另两图差异

**vs MAP-13**：MAP-13 的约束静态、明确、无状态转换，Agent 只需把四条碑文传播到唯一排列；MAP-15 的门效果随 tick 奇偶变化，同一墙色在偶/奇 tick 要求不同门色，核心是规则发现与迁移。MAP-13 的错误来自漏约束/镜像，MAP-15 来自相位误读/重复旧选择；两者不共享状态机。

**vs MAP-14**：MAP-14 的规则静态，难点是不可靠证词与问询预算；MAP-15 的证词/门反馈是确定的，难点是规则随状态变化并需迁移到未见组合。MAP-14 没有 tick 奇偶或门色；把 MAP-14 的答案改成随 tick 变化会变成另一张图。

## 11. 可计算性来源

需要公开的 `area`、`current_tick`、`current_tick_parity`、`inspected_current_area`、`current_wall_symbol_color_if_inspected`、`current_door_colors_in_ephemeral_slot_order_if_inspected`、`wrong_attempt_resources`、`test_wrong_attempts`、`training_sample_log`、`recorded_rule_hypothesis`、`gate_open`。T 首次正确性由 T 区域第一次 `choose_door` 与动作前目标色比较。

## 12. 难度定位与对照

D=(3,3,2,1,3,3)。相对 MAP-14 提升 V（规则隐藏）、D（跨区域迁移）与 M（训练样例记忆），E 为 2（相位动态但无随机）。预登记对照：**可记录转换表 vs 仅短历史**；不能公开完整状态机。若转换表额外给 T 布局，标为信息可用性实验。

## 13. 未决

没有显式 `predict` 动作（`V7-DCR-008`）；本卡把 T 首次选择作为“未见状态预测”代理，并明确其局限。运行时接入前需固定“动作前奇偶读取”与两个终止码的优先级。
