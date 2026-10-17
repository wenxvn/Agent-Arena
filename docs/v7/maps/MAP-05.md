# MAP-05｜灯塔｜中等｜三束信号

```yaml
map_id: MAP-05
world: lighthouse
nominal_level: 中等
capability_primary: shared_resource_scheduling
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: eb2021067e56a3211d3e0ae747583acb8faf6bbe8e0ffbb4ba716cea1d34ed5e
source_design_hash: 7dcd822757c73b542840521430d5068acdf4d4e3dd9bb429504eca524077c3d5
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“共享电力下的多窗口排程”。三座塔 R/B/W 各有独立发射窗口、两阶段校准与不同旅行成本；任意时刻最多一座塔接电。校准进度在断电后**永久保留**，但发射必须“人在塔上且该塔接电”。因此难点不是收集三件物品，而是把“旅行/切换成本”与“窗口空等”同时排入时间轴；少走路可能多等，提前校准远塔可能多走路却压低空等。

## 2. 真实规则字段

- 拓扑：`C-R` 1 tick、`C-B` 2 tick、`C-W` 3 tick，均双向；只在 C 能 `switch_power(station)`。
- 窗口（含端点）：R `[15,18]`、B `[22,25]`、W `[29,35]`。
- 校准：每塔依次 `align`、`phase_lock`，各 1 tick；完成后永久保留，断电不衰减。
- 发射：`send_signal` 耗 1 tick，按**动作结束 tick**检查窗口；窗口结束 tick 的发射先结算，因此端点成功。
- 初始：`tick=0, location=C`，三塔未校准、未发射、供电未分配。
- 成功：R/B/W 三束均发出。失败：任一未发信号的窗口结束 tick 已到或被跨过 → `SIGNAL_WINDOW_MISSED`。
- 硬约束：同一时刻供电目标唯一；只在“已校准且接电”的塔发射；不得重复发射。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map05.effective_signals` | primary | 完成校准并在窗口内发射的信号数 | 束 / 高 | 3 | 无终局 → CENSORED |
| `map05.window_utilization` | primary | 实际完成的窗口任务数 / 可完成窗口任务数 | 比例 / 高 | 可完成窗口任务数（本实例 3） | 实例不可行 → UNAVAILABLE |
| `map05.power_overcommit` | guardrail | `count(POWER_LIMIT_EXCEEDED)` | 次 / 低 | episode | 0 合法 |
| `map05.missed_windows` | diagnostic | `count(SIGNAL_WINDOW_MISSED)` | 次 / 低 | episode | 终点前 → 0 |
| `map05.idle_ticks` | diagnostic | 已接电塔上无进展的等待 tick | tick / 低 | episode | 0 合法 |

## 4. 能力混淆分析

- 高 `effective_signals` 可能只因为三个窗口足够宽；必须同时报 `idle_ticks` 与完成 tick。
- 高 `window_utilization` 可能由“只做最容易的一束”造成；分母固定为可完成窗口任务数，不能按尝试数缩小。
- 低分可能由“校准需要持续供电”的误解造成；校准其实永久保留。用 `calibration_lost` 类失败（若运行时记录）与 `SIGNAL_WINDOW_MISSED` 区分。
- 方案 A（31 tick，等待 9）与 B（29 tick，等待 0）都成功；完成 tick 短不等于调度更好，B 多走 6 tick、多切换 1 次。

## 5. 两条手算轨迹

**方案 A（近塔优先，31 tick）**：C 查航表（1）→C→R（2）→R `align`（3）→`phase_lock`（4）→在 R 等待至 tick 15 发射（15）→R→C（16）→C 切 B（17）→C→B（19）→B 校准（20–21）→tick 22 发射（22）→B→C（24）→C 切 W（25）→C→W（28）→W 校准（29–30）→tick 31 发射（31）。指标：有效信号 3/3；窗口利用率 3/3；超配 0；错过 0；空等 9 tick（R 上 11 tick 等待 + W 前 1 tick 等，按设计表合计 9）；完成 31。

**方案 B（远塔预校准，29 tick）**：C 查表（1）→C→W（4）→W 校准（5–6）→W→C（9）→切 R（10）→C→R（11）→R 校准（12–13）→tick 15 发射（15）→R→C（16）→切 B（17）→C→B（19）→B 校准（20–21）→tick 22 发射（22）→B→C（24）→切 W（25）→C→W（28）→tick 29 发射（29）。指标：有效信号 3/3；窗口利用率 3/3；超配 0；错过 0；空等 0；旅行 15 tick；切换 4 次；完成 29。

## 6. 三个机制特有失败

1. **校准后切走供电**：R 校准完成但未到窗口就切给 B，R 未接电无法发射，窗口 18 结束后 `SIGNAL_WINDOW_MISSED`；有效信号 2/3。
2. **误以为校准需要持续供电**：在 R 过窗前一直保持供电空等，错过 B 的窗口；有效信号 1/3。
3. **在 B 校准后反复读接收机**：B 已可发射但 Agent 继续 `inspect`，跨过 tick 25，`SIGNAL_WINDOW_MISSED`；空等 tick 增加，信号 2/3。

## 7. 两个边界

- **窗口端点发射**：R 在 tick 18、B 在 tick 25、W 在 tick 35 发射仍成功；tick 19/26/36 则失败。必须用同一前缀只改一个等待动作验证。
- **远塔断电保留**：W 校准完成后断电去 R，再回 W 仍可直接发射；若运行时错误地清零校准，`effective_signals` 会假性下降。该边界用于验证“校准永久保留”。

## 8. 信息泄漏负例

若 prompt 直接给出发射顺序（如“先 R 后 B 后 W”）或最优调度表，排程能力被替代。V7 只允许公开窗口表、旅行成本与校准规则，不公开“先给谁供电”的建议。`oracle_trace.jsonl` 与 Pareto 前沿只在离线裁判侧使用。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有 `near_first`（31 tick）与 `far_first_prep`（29 tick）两条非支配手写调度；`failure_traces/cases.yaml` 有三条窗口失败。原始窗口曾被手算证明不可行并提交 DCR（见 `worlds/v4/README.md`）；**本卡只使用修订后可行情景**。没有运行时穷举/Pareto 求解器，运行时接入前必须先做可行性枚举（`V7-DCR-004`）。

## 10. 与同世界另两图差异

**vs MAP-04**：MAP-04 只有一条 `S-G` 瓶颈边和一个固定 6 tick 周期，动作只影响“现在能不能过”；MAP-05 有三座塔、三个独立窗口、共享单路供电、可保留的校准进度和不同旅行成本。MAP-04 的等待是单点相位等待，MAP-05 的等待是“给哪座塔供电、何时校准、何时发射”的多任务排程；两者不共享目标函数。

**vs MAP-06**：MAP-06 的天气/预报带噪声，风险预算可被越过，核心是信息价值与风险决策；MAP-05 的窗口与校准完全确定，没有随机天气或风险积分。MAP-05 的失败是窗口错过/供电错配，MAP-06 的失败是风险超预算或截止前未修复；把 MAP-05 的窗口改成随机不会自动产生 MAP-06 的信息价值构念。

## 11. 可计算性来源

需要逐 tick 的 `location`、`current_power_target`、`local_calibration_state`、`local_transmission_state`、`current_tick`，以及 `send_signal` 的结束 tick 与结果。`idle_ticks` 由“已接电且已校准但未发射”的 tick 段派生；窗口利用率的分母来自公开窗口表与实例可行性审计。

## 12. 难度定位与对照

D=(1,2,1,3,2,2)。相对 MAP-04 提升 R（共享电力）与 B（多窗口排程），E 不变（无随机事件）。预登记对照：**时间表结构化 vs 文字叙述（信息量等价）**；不得暗示发射顺序。若结构化表额外给顺序，标为信息可用性实验。

## 13. 未决

原始窗口不可行已有手算 DCR；运行时必须以修订版窗口为准，并把窗口表哈希写入 scenario hash。本卡不修改规则。
