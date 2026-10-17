# MAP-04｜灯塔｜简单｜潮汐密道

```yaml
map_id: MAP-04
world: lighthouse
nominal_level: 简单
capability_primary: periodic_phase_prediction
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 1f654d02be43dbf14b40d00e250d3a371ec3287eb560d97d743456ae8837c3a6
source_design_hash: c955b65efa50a3e5d5b4c4dfdd30649446bf70abf30ba5b738d121df0a097724
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“周期时间窗判断”。潮汐相位公开、周期 6、`S-G` 只在相位 0/1 开放；`T-S-G-D` 是短路，`T-B1-B2-B3-B4-D` 是 5 tick 长绕行；灯芯在 G，最后回 T 安装并点灯。观察、等待、过道三种动作都耗 1 tick 并推进相位，因此“等窗口”与“绕路”有真实机会成本；错过窗口可以等下一周期，但救援船在 tick 18 到达。

## 2. 真实规则字段

- 初始：`tick=0, location=T, tide_phase=2, tide_period=6, S_G_open_phases=[0,1], wick_at=G, lamp_wick_fitted=false, lamp_lit=false, rescue_deadline_tick=18`。
- 时钟：任何 schema 合法环境动作耗 1 tick，`phase=(phase+1) mod 6`；移动先按动作开始相位检查边，再移动，再推进相位。
- `S-G` 关闭时尝试：`TIDE_WINDOW_CLOSED`，留在原地，仍耗 1 tick 并推进相位。
- `inspect(tide_gauge)` 只返回当前相位；重复查询不增加信息。
- 成功：`lamp_wick_fitted && lamp_lit && tick<=18`；`tick=18` 的安装/点灯先结算，因此端点可成功。
- 失败：`RESCUE_SIGNAL_WINDOW_EXPIRED`（tick 18 仍未点灯）。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map04.window_hit_rate` | primary | 在开放相位尝试穿越 `S-G` 的次数 / 全部 `S-G` 尝试 | 比例 / 高 | 穿越尝试数 | 0 次尝试 → N/A（不是 0） |
| `map04.earliest_safe_crossing_delay` | primary | 实际首次穿越 tick − 最早可行穿越 tick | tick / 低 | 成功穿越的 episode | 未穿越 → N/A/CENSORED |
| `map04.high_tide_entries` | guardrail | `count(TIDE_WINDOW_CLOSED)` | 次 / 低 | episode | 0 合法 |
| `map04.stranded_ticks` | diagnostic | 无效等待 + 回退损失 tick | tick / 低 | episode | 按已发生动作计 |
| `map04.wait_ticks` | diagnostic | `wait(1)` 与窗口等待总 tick | tick / 低 | episode | 0 合法 |

## 4. 能力混淆分析

- 高通关率可能来自“直接走 5 tick 绕行”，完全不需要周期推理；必须同时报 `window_hit_rate` 与 `wait_ticks`。
- 高 `window_hit_rate` 可能只因为只尝试了一次；分母小，必须同时报尝试次数。
- 低分可能由“相位在动作开始时检查”这一时序误解造成，而不是不会算周期；用 `TIDE_WINDOW_CLOSED` 次数归因。
- 等待少不等于好：方案 A 等 9 tick 但总 14 tick；方案 B 不等但总 15 tick。时间差来自路线选择，不是“更会算相位”。

## 5. 两条手算轨迹

**策略 A（潮道，14 tick）**：T→S（1，相位 3）→等待 3 tick（tick 2–4，相位 0）→S→G（tick 5，相位 1，窗口命中）→取灯芯（6，相位 2）→在 G 等待 4 tick（7–10，相位 0）→G→S（11，相位 1）→S→T（12，相位 2）→安装灯芯（13）→点灯（14）。指标：窗口命中 2/2 = 1.0；首次穿越 tick 5，最早可行 tick 5 → 延迟 0；高水位闯入 0；等待 7 tick（3+4）；完成 14。

**策略 B（全绕行，15 tick）**：T→B1→B2→B3→B4→D（5）→D→G（6）→取灯芯（7）→G→D（8）→D→B4→B3→B2→B1→T（13）→安装（14）→点灯（15）。指标：`S-G` 尝试 0 → 窗口命中率 N/A；穿越延迟 N/A；高水位闯入 0；等待 0；完成 15。

## 6. 三个机制特有失败

1. **无进展等待**：在 S 一直 `wait`，tick 18 到达仍未点灯，`RESCUE_SIGNAL_WINDOW_EXPIRED`（诊断标签 `no_progress`）。
2. **绕行超时**：完成 5 边绕行、取芯、又在 D 等待，回到 T 时已过 18（`detour_overrun`）。
3. **窗口时序误判**：在相位 2 尝试 `S-G`，得到 `TIDE_WINDOW_CLOSED` 并耗 1 tick；连续尝试把返程推到 tick 18 之后（`missed_return_window`）。

## 7. 两个边界

- **相位 1 穿越成功、相位 2 失败**：`S-G` 开放相位为 `[0,1]`，出发相位 1 仍可进入；相位 2 出发即关闭。必须用同一起点只改一个等待动作验证。
- **tick 18 点灯成功、tick 19 失败**：成功动作先于同 tick 截止检查；`tick=18` 的 `ignite` 结算成功，`tick=19` 才点灯则失败。

## 8. 信息泄漏负例

若 Observation 直接给“下一安全 tick”或完整未来相位表，周期推理被替代。V7 只允许公开当前相位、周期与开放相位集合；未来相位必须由 Agent 自行推算。对照组“公开完整未来相位表”必须标为信息可用性实验。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有 `tide_window`（14 tick）与绕行方案（15 tick）两条手写成功；`failure_traces/cases.yaml` 有三条失败；`acceptance.md` 只完成纸面推演。**没有独立求解器证明 14 tick 最优**；只能证明两种策略可行。

## 10. 与同世界另两图差异

**vs MAP-05**：MAP-05 有三个独立信号窗口、共享单路供电和校准阶段；Agent 要决定“先给哪座塔供电、何时校准、何时发射”，窗口是任务排程的一部分，不是单一周期。MAP-04 只有一条可变瓶颈边和一个固定周期，没有供电分配或多任务窗口；把 MAP-04 的窗口数增加不会自动产生 MAP-05 的资源争用。

**vs MAP-06**：MAP-06 的天气与预报表是**有噪声、有成本**的信息，风险预算可被越过；它的核心是“问、赌、加固”的期望值。MAP-04 的潮汐规则完全公开且确定，没有随机天气或风险积分；失败来自相位/时限，而非风险决策。两者都用“时间窗”，但一个是确定周期，一个是带噪信息与风险阈值。

## 11. 可计算性来源

需要逐 tick 的 `location`、`tide_phase`、`S_G` 尝试与结果、`lamp_wick_fitted`、`lamp_lit`、`terminal_reason`。窗口命中率由 `move(S_G)` 动作开始相位与结果 `MOVE_SUCCEEDED/TIDE_WINDOW_CLOSED` 派生；最早可行 tick 可用公开周期、起点与边成本离线计算。

## 12. 难度定位与对照

D=(1,1,1,1,1,1)。单一周期机制，无跨设备耦合。预登记对照：**公开周期表 vs 通过观察推断周期**；不得直接给下一安全 tick。若“观察推断”组额外给未来相位，属于信息可用性实验。

## 13. 未决

无规则冲突。运行时接入前需固定“动作开始相位检查”与“tick 18 成功先于截止”的结算顺序，并验证 `inspect` 与失败尝试同样推进相位。
