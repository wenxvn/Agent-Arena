# MAP-02｜飞船｜中等｜双重警报

```yaml
map_id: MAP-02
world: spaceship
nominal_level: 中等
capability_primary: event_triggered_replanning
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 810c9ed43de3745c7c02d3aa82f5145140b6697aa00f1902d03161724f67673e
source_design_hash: 4bdb831631fb858e71c4b405a6a48cc4ed877d81a17436716ab6a24fd42f56d0
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“突发事件后的目标重排序”。第 4 个 schema 合法环境动作结算后公开左区泄漏；泄漏有 2 tick 扩散窗，若不关闭中央闸则进入 R1 损坏导航核；同时 L2 船员只有泄漏后 8 tick 压力预算。导航核封存（R1）与船员护送（L2→C→R2）互相牵制，中央闸 `C-L1` 是**不可逆**气密闸。成功不是“预测到事故”，而是事故公开后及时改变计划。

## 2. 真实规则字段

- 初始：`tick=0, location=C, nav_core_at=R1, repair_pack_at=R1, nav_core_secured=false, crew_at=L2, crew_in_E=false, center_gate=OPEN, leak_active=false, global_deadline=20`。
- 私有：`leak_trigger_index=4`、`leak_spread_ticks=2`、`crew_pressure_ticks=8`（泄漏前不公开）。
- 公开：位置、相邻边、可见物、导航核位置、船员位置、双目标、`leak_active`、泄漏后船员压力 tick、中央闸状态。
- 触发：第 4 个环境动作结算后泄漏；该动作的直接效果先结算，所以第 4 步在 C 锁闸能挡住刚触发的泄漏。
- 硬失败：扩散计数归零（`NAV_CORE_FLOODED`）、船员压力耗尽（`CREW_PRESSURE_LOST`）、tick 20 未完成（`GLOBAL_DEADLINE`）。
- 成功：`nav_core_secured && crew_in_E && tick<=20`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map02.event_response_latency` | primary | 泄漏公开 tick 后首个“改变计划”的有效动作 tick − 泄漏公开 tick | tick / 低 | 观察到泄漏的 episode | 未观察泄漏 → N/A |
| `map02.dual_objective_completion` | primary | 已完成目标数 / 2，并附 `(nav_core_secured, crew_in_E)` 明细 | 比例 / 高 | 2 | 无终局 → CENSORED |
| `map02.crew_decompression` | guardrail | `1[CREW_PRESSURE_LOST]` | 0/1 / 低 | episode | 终局缺失 → CENSORED |
| `map02.stale_plan_actions_after_leak` | diagnostic | 泄漏后仍推进旧目标且未隔离闸的动作数 | 次 / 低 | 泄漏后动作数 | 无泄漏 → N/A |
| `map02.completion_ticks` | diagnostic | 成功终局 tick | tick / 低 | 成功局 | 失败 → N/A |

“改变计划”的判定必须预登记：泄漏后第一次执行 `isolate_L1`、`escort`、或向 L2/R2 方向的移动；普通原地检查不计。

## 4. 能力混淆分析

- 高通关率可能只来自“先锁闸”的单一启发式，而非双目标权衡；必须同时报 `dual_objective_completion` 的两目标明细。
- 低通关率可能由“第 4 个动作触发”这一隐藏时序造成；Agent 不应被要求预测触发点，指标只测事后响应。
- `completion_ticks` 短不等于重规划好：策略 A（11 tick）与 B（14 tick）都成功，但 A 留 1 tick 余量、B 精确用满 8 tick；时间差来自优先级，不是路线长度。
- 若把导航核“封存即可留在 R1”误解为必须运到 E，会产生多余折返；这是流程错误，不是记忆错误。

## 5. 两条手算轨迹

**策略 A（预封存后救援，11 tick）**：C→R1（1）→封存导航核（2）→R1→C（3）→锁中央闸（4，同时触发泄漏，泄漏被封闭）→C→X（5）→X→L2（6）→接应船员（7）→L2→X（8）→X→C（9）→C→R1（10）→R1→R2（11）登舱。指标：响应延迟 0；双目标 2/2；船员压力余量 1；stale actions 0。

**策略 B（救援优先，14 tick）**：检查控制器（1）→C→R1（2）→R1→C（3）→锁闸（4）→泄漏公开后立即执行护送（5）→C→X（6）→X→L2（7）→接应（8）→L2→X（9）→X→C（10）→C→R1（11）→R1→R2（12）→登舱（13）→R2→R1（14）→封存导航核。指标：响应延迟 0（第 5 步是首个改变计划动作，若把锁闸算响应则也是 0）；双目标 2/2；船员压力余量 0（精确用满 8 tick）；stale actions 0。

> 若把“第 4 步锁闸”视为对泄漏的响应，则 A/B 都是 0；但 B 的第 4 步在泄漏公开前已结算，严格定义下其响应是第 5 步，延迟为 1。卡片冻结定义：**泄漏公开后的第一个动作**才算响应，因此 A=0、B=1。

## 6. 三个机制特有失败

1. **无视扩散窗**：泄漏后继续去 R1 取工具，2 tick 后 `NAV_CORE_FLOODED`；双目标 1/2（船员可能仍可救）。
2. **先救人导致导航风险**：先接船员再回 C 锁闸，超过 2 tick，导航核被淹；即使船员获救也失败。
3. **锁闸后救援绕路超时**：锁闸正确，但走 C-R1-R2 内侧路线护送，超过 8 tick，`CREW_PRESSURE_LOST`；这验证“先锁闸”不是充分策略。

## 7. 两个边界

- **第 4 步锁闸**：动作 4 的直接效果先结算，泄漏事件后结算，因此锁闸成功挡住泄漏；若把锁闸放到第 5 步，扩散计数先减 1，仍可能成功但余量只剩 1 tick。
- **第 8 tick 抵达 R2**：规则规定“到第 8 tick 的动作若直接带入 R2，先确认救援成功，之后才检查超时”，所以第 8 tick 到达仍成功；第 9 tick 到达失败。必须用同一路线只改一个等待动作验证。

## 8. 信息泄漏负例

若 prompt 或 Observation 提前给出 `leak_trigger_index=4`、`leak_spread_ticks=2` 或船员压力预算，Agent 可以预先安排而不需要事件后重规划。V7 只允许在泄漏发生后公开“泄漏已发生、扩散状态、剩余压力 tick”，不得公开触发序号或未来事件。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有 `core_first`（11 tick）与 `crew_first`（14 tick）两条手写成功；`failure_traces/cases.yaml` 有三类失败；`acceptance.md` 只完成纸面推演。**没有独立求解器证明 11 tick 最优**；两条轨迹只证明“多策略可行”。

## 10. 与同世界另两图差异

**vs MAP-01**：MAP-01 是静态前置依赖与供氧/维修臂互斥，没有事件触发器；它的失败是断供超限或违规复位。MAP-02 的状态核心是 `leak_active`、扩散计数与船员压力预算，失败是导航核被淹或船员失压。把 MAP-01 的电池容量改小不会产生“事件后目标重排序”，两者不可互换。

**vs MAP-03**：MAP-03 是五阶段长期目标保持与一次性 K7 远期召回，没有突发事件；它的失败是漏阶段、样本窗口或航线窗。MAP-02 只跨 20 tick，且核心是“泄漏公开后是否立即改计划”；MAP-03 的核心是“几十个动作后是否还记得早期事实”。两图的记忆跨度（M=1 vs M=3）与事件动态性（E=2 vs E=1）不同。

## 11. 可计算性来源

需要逐 tick 的 `leak_active`、`crew_pressure_ticks_after_leak`、`current_gate`、`nav_core_secured`、`crew_in_E`、`terminal_reason`；事件响应延迟由“首次 `leak_active=true` 的 tick”与之后首个预登记响应动作派生。`leak_trigger_index` 与扩散计数只在离线裁判中使用，不进入公开 Observation。

## 12. 难度定位与对照

D=(1,2,2,2,1,2)。相对 MAP-01 提升 E（事件动态性）与 B（分支），不靠路线变长。预登记对照：**突发泄漏 vs 无泄漏**、**提前预警 vs 现场发现**；两者共享泄漏位置、合法动作、预算。提前预警若额外给泄漏位置，标为“信息可用性实验”。

## 13. 未决

双目标权重未在 spec 定义（`V7-DCR-002`）。本卡默认**不合成加权总分**，只报两目标明细与完成数/2；若未来需要单值，必须先冻结权重与敏感性。
