# MAP-05 审计：三束信号

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-05 / lighthouse / 中等 |
| condition | `default` |
| scenario_hash | `b9201a539d66119baedf3cf9e6b6057b266b94e98ce5a564c740c0d2c0bd2560` |
| rule_hash | `4aa810269535dad84ce3ad40f5d524edaabe084ab970085b851d0e6a8dd298b4` |
| 决策预算 / step_limit | 38 / 160 |
| V8 三局 | R0 failure `SIGNAL_WINDOW_MISSED` 19 决策；R1 同名 20 决策；R2 同名 19 决策 → **0/3** |

数据来源：`runs/v9/evidence/MAP-05.json`（本审计所有 Observation 引用来自该证据包及 `scripts/v9_show_map.py MAP-05`）、`docs/v9/run-index.csv` 第 14–16 行、`docs/v8/maps/MAP-05-final.md`、`worlds/v4/MAP-05/{map_spec.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map05.py`。

## 1. 能力构念

- **定义**：在"一次只能给一座塔供电、切换只能在中心台 C 执行"的约束下，把"校准两阶段 + 发射"排进三个互不重叠的时间窗，并在"多走路"与"多空等"之间取舍。
- **成功行为**：`transmitted = {R: true, B: true, W: true}`，且每次 `send_signal` 的结算 tick 落在该塔窗口内 → `THREE_SIGNALS_SENT`。
- **明确反例**：在没有供电的情况下校准（`STATION_UNPOWERED`）；在非 C 节点切电（`TARGET_NOT_VISIBLE`）；把 `send_signal` 结算在窗口外（信号被静默丢弃，随后窗口关闭 → `SIGNAL_WINDOW_MISSED`）。
- **本图在三图递进中的位置**：唯一带"共享资源 + 时间窗"的中等图；它比 MAP-04 多一层"必须先回 C 才能换塔"的空间约束，但三座塔的窗口彼此相隔 4–7 tick，容错空间比 MAP-06 大得多。

## 2. 机制与因果链

```
起始 C, tick0, power_target=null, calibration={R:0,B:0,W:0}
  → 必需观察：windows={R:[15,18],B:[22,25],W:[29,35]}、tick、power_target、calibration、transmitted
  → 关键决策：先在 C 切电（唯一允许切电的位置），再移动、align、phase_lock、send
  → 立即后果：切电成功 power_target=<station>；未供电时校准返回 STATION_UNPOWERED；send 的结算 tick
              不在窗口内则 transmitted 不变（但返回码仍是 SIGNAL_SENT）
  → 终局：任一未发射塔的窗口 end 被跨过 → SIGNAL_WINDOW_MISSED；三塔全发射 → THREE_SIGNALS_SENT
```

**顺序是强制的**：R 的窗口最先关闭（18），任何"先 B 或先 W"的完整计划都会让 R 窗口失效。先做 B：`switch B`(t1)→`C_B`(t3)→`align`(t4)→`lock`(t5)，最早 t22 才能发射 B，回 C 已 t24，`switch R`(t25) 时 R 的 [15,18] 早已关闭。先做 W 更慢（单程 3 tick，最早 t29 才能发射）。因此合法计划必须 R→B→W 发射，可优化的只有"在哪里烧掉空档"。

**可绕过/弱化的环节（实测）**：

1. `inspect(schedule_chart)` 完全冗余：`windows` 本来就在 Observation 里。Oracle `near_first` 花 1 tick 去读它。最小策略直接跳过这一动作。
2. `idle_ticks` 只看"已在满校准塔上 wait"（`map05.py` 第 97–98 行），把同样的等待搬到 C（此时 `calibration[target]=0`）就不计数。`public_heuristic` 在 C 一次等 10 tick，`idle_ticks=0`（对比 Oracle `near_first` 在 R 上等 9 tick）。
3. `power_overcommit` 恒为 0：`switch_power` 只是覆盖 `power_target`，没有任何容量/并发校验，也没有计数器。设计里的硬约束"at_most_one_power_target"由"单值字段"天然满足，因此这条护栏永远不会触发。

**机制是否在三条真实轨迹里触发**：

- R0：供电机制触发 1 次（决策 3 `calibrate_align` → `STATION_UNPOWERED`），切电位置机制触发 3 次（决策 4、5、12 `switch_power` → `TARGET_NOT_VISIBLE`）；窗口机制在决策 19 触发终局。
- R1：供电机制 2 次（决策 6 `STATION_UNPOWERED`、决策 16 同码），切电位置机制 3 次（决策 3、17、20 `TARGET_NOT_VISIBLE`）；窗口机制在决策 20 触发终局。
- R2：供电机制 2 次（决策 3、15），切电位置机制 2 次（决策 4、16）；窗口机制在决策 19 触发终局。
- 触发所需最小动作数：窗口机制 = **5**（`switch_power`、`move`、`calibrate_align`、`calibrate_phase_lock`、`send_signal`）。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `windows = {R:[15,18], B:[22,25], W:[29,35]}` | 是（Observation） | 开局即全部公开 | 是 |
| `tick` | 是 | 每步 | 是（三图里唯一直接公开 tick 的） |
| `location` / `visible_edges` | 是 | 每步 | 是 |
| `power_target`、`calibration`、`transmitted` | 是 | 每步 | 是 |
| `schedule_chart_inspected` | 是 | 每步 | 冗余（窗口已公开） |
| 规则"`switch_power` 只能在 C 执行" | **未公开**；词表只有一句"位置对象：C=schedule_chart、总电源" | 只能靠试错 | 否——必须试出 `TARGET_NOT_VISIBLE` 才能定位 |
| 返回码"`TARGET_NOT_VISIBLE`"的语义 | 是（结果反馈） | 首次尝试后 | **误导**：站在 R 上时 R 显然"可见"，真实原因是"这里没有总电源" |
| 规则"`send_signal` 的**结算** tick（动作开始 tick + 1）必须落在窗口内" | **未公开**；目标文本写"在 R[15,18]…窗口内各发出一束信号" | 只能靠失败反推 | 否——在 `tick=18` 时发射会被判失败，而 `18∈[15,18]` |
| 规则"窗口外的 `send_signal` 仍返回 `SIGNAL_SENT` 但不置 `transmitted`" | **未公开**（设计稿声明的 `SIGNAL_WINDOW_NOT_OPEN` 在实现里不存在） | 只能靠核对 `transmitted` 发现 | 否——结果码与终局互相矛盾 |
| `FEASIBLE_TASK_COUNT=3`（`window_utilization` 的固定分母） | 否 | — | 不影响解题 |
| hidden `judge_state`：`idle_ticks`、`missed_windows` | 否 | — | 不影响解题 |
| Oracle 路径（`near_first` / `far_first_prep`） | 否 | — | — |

结论：**时间窗数据是公开且完整的，但两条动作前置规则（只能在 C 切电、结算 tick 必须在窗口内）没有公开**，且第一条的错误码指错了对象。

## 4. 可解性与可观察性

- Oracle：`near_first`（27 动作）、`far_first_prep`（21 动作），`baseline_run` 复算 2/2 ok。
- **仅凭公开 Observation 的可执行策略存在**，已实测：`Map05Heuristic` 19 决策、`THREE_SIGNALS_SENT`、`idle_ticks=0`、`effective_signals=3/3`。
  - 它只用公开字段：按窗口 `end` 排序取未发射塔、在 C 切电、用 `tick` 与 `windows` 算"到达后三步能否落进窗口"，太早就在 C 等。
  - 需要注意：策略**使用了未公开的两条前置规则**（见 §3）。运行时可复现，但"仅凭 prompt 就能想到"这一点不成立——这正是 V8 三局失败的一半原因。
- 因此：不标 `INTERFACE_BLOCKED`（存在可执行且可赢的公开策略，且 R1 在决策 14 时仍有一条完胜线），但"切电只能在本节点"的**信息/反馈缺陷要被记录**（§8 次因 C）。

## 5. 预算可行性

| 策略 | 决策数 | 终局 | 备注 |
|---|---|---|---|
| Oracle `near_first` | 27 | `THREE_SIGNALS_SENT` | 含 9 次单 tick 等待、9 tick idle |
| Oracle `far_first_prep` | 21 | `THREE_SIGNALS_SENT` | 先预校准 W，1 tick idle |
| `legal_random` ×20 | 13–19 | `SIGNAL_WINDOW_MISSED` ×20 | 成功 0/20，非法 0，被拒 183 |
| `public_heuristic` | 19 | `THREE_SIGNALS_SENT` | 两个 `wait`（8+2），`idle_ticks=0` |
| `no_power_switch` | 19 | `SIGNAL_WINDOW_MISSED` | 复现 R0 的 `STATION_UNPOWERED` 循环 |
| `no_window_wait` | 26 | `SIGNAL_WINDOW_MISSED` | 校准后立刻发射，1/3 有效 |

预算 38，Oracle 与启发式只用 19–27。三局分别在第 19/20/19 个决策自然终局（未触顶）。**判定：不是预算不够，是模型没做对**——R1 在决策 14（tick 17，站在 C）时仍有完胜线：`switch B`(18)→`C_B`(20)→`align`(21)→`lock`(22)→`send`(23∈[22,25])→`C`(25)→`switch W`(26)→`C_W`(29)→`align`(30)→`lock`(31)→`send`(32∈[29,35])，共 11 个动作、27 个决策 < 38。

## 6. 指标

| 指标 | 类别 | 计算事件 | 分母 | 三局取值 |
|---|---|---|---|---|
| `map05.effective_signals` | primary | 已发射塔数 | 3 | 0/3、1/3、1/3 |
| `map05.window_utilization` | primary | 同一分子 | 常量 `FEASIBLE_TASK_COUNT=3` | 0/3、1/3、1/3 |
| `map05.idle_ticks` | diagnostic | 仅在 `calibration[power_target]==2` 时 `wait` 的 tick | episode | 0、4、5 |
| `map05.missed_windows` | diagnostic | 未发射且 `tick > end` 的塔 | episode | 1、1、1 |
| `map05.power_overcommit` | guardrail | 常量 `0` | episode | 0、0、0 |

- **有未通关仍有意义的连续指标吗**：`effective_signals`（0 / 0.333 / 1.0）与 `idle_ticks`（0/4/5）都是连续的，且随机基线全为 0，能构成下界。
- **N/A 情况**：三局与全部基线都**没有** `not_applicable`（与 `docs/v9/data-integrity.md` §4.2 一致，MAP-05 属于 0 N/A 的图）。
- **区分度**：`effective_signals` 能区分 random(0) / `no_power_switch`(0) / `no_window_wait`(0.333) / `public_heuristic`(1.0)；`idle_ticks` 能区分 `public_heuristic`(0) 与 V8 的 R1/R2(4/5)。
- **指标缺陷（证据）**：
  1. `window_utilization` 的分母在实现里是常量 `3`，与 `effective_signals` 的分子分母逐字相同 → 两条 primary 在本图 25 条本地复算记录（3 局 + 20 随机 + 启发式 + 2 消融）里全部相等（R0 0/3=0/3，R1 1/3=1/3，R2 1/3=1/3，`no_window_wait` 1/3=1/3）。V8 文档写"分母=可完成窗口任务数"，实现里没有这个计算。
  2. `power_overcommit` 恒 0（`metrics()` 直接写 `0`），25 条本地记录无一例外；它是一条永不触发的护栏。
  3. `idle_ticks` 可被"把等待搬离已校准塔"规避（§2 第 2 条），它测的是"等待发生的位置"，不是"浪费的时间"。

## 7. 三次轨迹归因

### R0（failure，19 决策，`SIGNAL_WINDOW_MISSED`）

| # | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 1 | `{"target_id": "schedule_chart", "tool": "inspect"}` | `SCHEDULE:INSPECTED` | `{"schedule_chart_inspected": true, "tick": 1}` |
| 2 | `{"edge_id": "C_R", "tool": "move"}` | `MOVED:R` | `{"location": "R", "tick": 2, "visible_edges": ["C_R"]}` |
| 3 | `{"operation": "calibrate_align", "target_id": "R", "tool": "interact"}` | `STATION_UNPOWERED` | `{"tick": 3}` |
| 4 | `{"station": "R", "tool": "switch_power"}` | `TARGET_NOT_VISIBLE` | `{"tick": 4}` |
| 5 | `{"station": "R", "tool": "switch_power"}` | `TARGET_NOT_VISIBLE` | `{"tick": 5}` |
| 14 | `{"station": "R", "tool": "switch_power"}` | `POWER:R` | `{"power_target": "R", "tick": 14}` |
| 17 | `{"operation": "send_signal", "target_id": "R", "tool": "interact"}` | `CALIBRATION_REQUIRED` | `{"tick": 17}` |
| 18 | `{"operation": "calibrate_phase_lock", "target_id": "R", "tool": "interact"}` | `CALIBRATED:R` | `{"calibration": {"B": 0, "R": 2, "W": 0}, "tick": 18}` |
| 19 | `{"operation": "send_signal", "target_id": "R", "tool": "interact"}` | `SIGNAL_SENT` | `{"terminal": true, "terminal_reason": "SIGNAL_WINDOW_MISSED", "tick": 19}` |

- **首次偏离**：决策 2 —— 没有先在 C 切电就离开 C。此后决策 3–13 是 11 个决策的往返循环（`MOVED:R`/`MOVED:C` 与 3 次 `TARGET_NOT_VISIBLE`），直到决策 13 回到 C、14 才切电成功。
- **失败链**：`无供电校准` → `在错误位置切电 ×3` → `回到 C 重新开始` → `tick 13 才开始有效校准` → `决策 18 完成 phase_lock 时已经在窗口末 tick` → `决策 19 发射结算在 tick 19 > 18`。
- **最后一击的语义问题**：决策 19 返回 `SIGNAL_SENT` 但 `transmitted.R` 仍为 `false`，终局同时给出 `SIGNAL_WINDOW_MISSED`。结果码在失败点上给出的是"已发送"。
- 替代解释：(a) 预算——否，19/38；(b) 规则可解性——否，若在决策 13（tick 13 在 C）就直接 `switch R`，`send` 可落在 tick 18；(c) 信息不足/误导——**部分成立**：11 个决策的浪费直接由"非 C 切电返回 `TARGET_NOT_VISIBLE`"造成，而"窗口末 tick 发射会失败"没有任何公开说明。

### R1（failure，20 决策，`SIGNAL_WINDOW_MISSED`）

| # | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 2 | `{"edge_id": "C_R", "tool": "move"}` | `MOVED:R` | `{"location": "R", "tick": 2, "visible_edges": ["C_R"]}` |
| 3 | `{"station": "R", "tool": "switch_power"}` | `TARGET_NOT_VISIBLE` | `{"tick": 3}` |
| 6 | `{"operation": "calibrate_align", "target_id": "R", "tool": "interact"}` | `STATION_UNPOWERED` | `{"tick": 6}` |
| 8 | `{"station": "R", "tool": "switch_power"}` | `POWER:R` | `{"power_target": "R", "tick": 8}` |
| 13 | `{"operation": "send_signal", "target_id": "R", "tool": "interact"}` | `SIGNAL_SENT` | `{"tick": 16, "transmitted": {"B": false, "R": true, "W": false}}` |
| 14 | `{"edge_id": "C_R", "tool": "move"}` | `MOVED:C` | `{"location": "C", "tick": 17, "visible_edges": ["C_B", "C_R", "C_W"]}` |
| 15 | `{"edge_id": "C_B", "tool": "move"}` | `MOVED:B` | `{"location": "B", "tick": 19, "visible_edges": ["C_B"]}` |
| 16 | `{"operation": "calibrate_align", "target_id": "B", "tool": "interact"}` | `STATION_UNPOWERED` | `{"tick": 20}` |
| 17 | `{"station": "B", "tool": "switch_power"}` | `TARGET_NOT_VISIBLE` | `{"tick": 21}` |
| 20 | `{"station": "B", "tool": "switch_power"}` | `TARGET_NOT_VISIBLE` | `{"terminal": true, "terminal_reason": "SIGNAL_WINDOW_MISSED", "tick": 26}` |

- **首次偏离**：决策 3（在 R 上切电）。它比 R0 恢复得快（决策 7 回到 C，决策 8 切电成功），R 也按时发射（决策 13，tick 16 ∈ [15,18]）。
- **决定性错误在决策 15**：决策 14 结束时它站在 C、`tick=17`、`power_target` 仍为 `R`。此时正确动作是 `switch B`，而它直接 `move C_B` 到 B，导致后面 6 个决策全废（`STATION_UNPOWERED` → 两次 `TARGET_NOT_VISIBLE` → 来回移动），B 窗口在 tick 26 关闭。
- 替代解释：(a) 预算——否，20/38，而且上面已给出 11 个动作的完胜线；(b) 规则——否，B 窗口 [22,25] 与 tick 都公开；(c) 误导——`TARGET_NOT_VISIBLE` 在 B 上再次把"这里没有总电源"报成"目标不可见"，是压死它的直接反馈。

### R2（failure，19 决策，`SIGNAL_WINDOW_MISSED`）

| # | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 3 | `{"operation": "calibrate_align", "target_id": "R", "tool": "interact"}` | `STATION_UNPOWERED` | `{"tick": 3}` |
| 7 | `{"station": "R", "tool": "switch_power"}` | `POWER:R` | `{"power_target": "R", "tick": 7}` |
| 11 | `{"ticks": 5, "tool": "wait"}` | `WAITED` | `{"tick": 15}` |
| 12 | `{"operation": "send_signal", "target_id": "R", "tool": "interact"}` | `SIGNAL_SENT` | `{"tick": 16, "transmitted": {"B": false, "R": true, "W": false}}` |
| 14 | `{"edge_id": "C_B", "tool": "move"}` | `MOVED:B` | `{"location": "B", "tick": 19, "visible_edges": ["C_B"]}` |
| 15 | `{"operation": "calibrate_align", "target_id": "B", "tool": "interact"}` | `STATION_UNPOWERED` | `{"tick": 20}` |
| 16 | `{"station": "B", "tool": "switch_power"}` | `TARGET_NOT_VISIBLE` | `{"tick": 21}` |
| 19 | `{"edge_id": "C_B", "tool": "move"}` | `MOVED:C` | `{"location": "C", "terminal": true, "terminal_reason": "SIGNAL_WINDOW_MISSED", "tick": 27}` |

- **首次偏离**：决策 2（直接去 R 而不先切电），与 R0 同型；决策 7 修正。
- **决定性错误**：决策 13 回到 C（tick 17）后，同样没有切电就去 B（决策 14），与 R1 决策 15 完全同型——同一陷阱在两次重复里各出现一次。
- 替代解释：与 R1 相同，预算与规则都不构成阻塞。

**重复证据有限**：三局同 `seed=0`（MAP-05 的规则不读 seed，环境完全确定性），R1/R2 在"回 C 不切电就出发"这一步逐字同型；因此 **n=3 只能说明这是一个稳定的诱因，不能区分个体差异**。R0 则是另一种写法（在错误节点连续切电）。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **C** schema/接口误导（`switch_power` 在非 C 返回 `TARGET_NOT_VISIBLE`，11 个决策被浪费） | **B** 公开信息不足（窗口"结算 tick"语义未公开，最后一 tick 发射被判失败）+ **E** | 高（C）/ 中（B） | 决策 3–14、18–19 |
| R1 | **E** 策略规划错误（决策 15 在 C 不切电就出发，丢弃完胜线） | **C**（决策 16/17 的误导反馈） | 高 | 决策 14–20 |
| R2 | **E**（决策 14 同型错误） | **C** | 高 | 决策 13–19 |

- 三局共有的放大器：**实现与设计稿的结果码不一致**。`worlds/v4/MAP-05/map_spec.yaml` 的 `reason_codes` 明确列出 `INVALID_LOCATION`、`STATION_NOT_POWERED`、`CALIBRATION_INCOMPLETE`、`SIGNAL_WINDOW_NOT_OPEN`，而 `map05.py` 实际发出的是 `TARGET_NOT_VISIBLE`、`STATION_UNPOWERED`、`CALIBRATION_REQUIRED`，并且**从不发出** `SIGNAL_WINDOW_NOT_OPEN`——窗口外发射返回 `SIGNAL_SENT`。
- 未使用 **D**（预算）与 **A**（环境规则缺陷，指胜负规则本身）：胜负规则没有错，错在反馈文本。

## 9. 标签

- **`MEASUREMENT_VALID`**：三次失败都是可定位的策略/反馈错误，且存在 19 决策的公开策略可以完胜；`effective_signals` 在 random(0) 与启发式(1.0) 之间区分明确。
- **`METRIC_DEFECT`**：`window_utilization` 与 `effective_signals` 恒等（分母被写死为 3）；`power_overcommit` 恒为 0；`idle_ticks` 可通过把等待搬到 C 规避。
- 不标 `CONSTRUCT_BYPASS`：切电位置（必须回 C）与窗口结算两条机制在三条轨迹里都真实生效，无法绕过。
- 不标 `INTERFACE_BLOCKED`：R1 的完胜线证明预算与规则都允许成功；但 C 类缺陷要点名记录。
- 不标 `BUDGET_BLOCKED`。

## 10. 最小可证伪修复（无证据不修改）

> 规则本身保持只读；以下候选都优先"补公开信息/改反馈文本"，不动胜负判定。

**旧规则/旧公开信息**：`map05.py` 的 `_apply`/`_interact` 返回码 + `_VOCABULARY["MAP-05"]` 的一句提示。

- **候选 A（优先，只改公开信息）**：把非 C 节点的 `switch_power` 失败码从 `TARGET_NOT_VISIBLE` 改为 `POWER_SWITCH_REQUIRES_C`（或设计稿原定的 `INVALID_LOCATION`），并在词表里写明"`switch_power` 只能在 C 执行"。
  - 证据/根因：R0 决策 4、5、12 与 R1 决策 3、17、20 与 R2 决策 4、16 全部撞在这上面，R0 因此浪费 11 个决策。
  - 预期变化：不改变任何合法动作序列，只移除"站在 R 上却报 R 不可见"的矛盾；对能力构念是补全接口语义，不是降低难度（回 C 的行程成本仍存在）。
  - 反例/风险：`rule_hash` 会变（`map05.py` 改动）；旧 Trace 不能直接重放，需登记 DCR 与新 hash。若只改词表（不动代码），`rule_hash` 不变而 `prompt_hash` 变。
- **候选 B（优先，只改公开信息）**：公开"`send_signal` 的结算 tick = 动作开始 tick + 1，必须落在窗口内"，或把目标文本改成"在窗口结束前一个 tick 之内开始发射"。同时让窗口外发射返回 `SIGNAL_WINDOW_NOT_OPEN` 而不是 `SIGNAL_SENT`。
  - 证据/根因：R0 决策 19 在 `tick=18`、窗口 [15,18] 内发射，得到 `SIGNAL_SENT` 却当场 `SIGNAL_WINDOW_MISSED`；R1 决策 13 因此在 tick 16 成功、R0 在 19 失败，差别只有一个 tick。
  - 预期变化：把"差一 tick"从运气变成可计算量；仍保留窗口截止的硬约束。
- **候选 C（指标口径，不改规则）**：`window_utilization` 用真实的"可完成窗口任务数"分母（当前恒为 3）；`idle_ticks` 改为"任何未产出动作的等待 tick"，或明确其定义就是"已校准塔上的等待"。
  - 反例/风险：改口径会让 V8 的 `idle_ticks` 与 V9 数字不可比，需在 DCR 中保留旧口径列。
- **候选 D（不推荐）**：给 `switch_power` 加真实容量机制让 `power_overcommit` 能触发。
  - 代价：改变规则与全部 oracle；本图已经有足够机制，属于"新增机制"而非修复缺陷。只登记，不建议本轮实施。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-05.json`：

| 策略 | 状态 | 决策 | 关键指标 |
|---|---|---|---|
| Oracle `near_first` / `far_first_prep` | 2/2 ok | 27 / 21 | — |
| `legal_random` ×20 | 0/20 success | 13–19 | 全部 `SIGNAL_WINDOW_MISSED`；非法 0；被拒 183 |
| `public_heuristic` | success `THREE_SIGNALS_SENT` | 19 | `effective_signals` 3/3；`idle_ticks` 0；`missed_windows` 0 |
| `no_power_switch` | failure | 19 | 0/3；`missed_windows` 1 |
| `no_window_wait` | failure | 26 | 1/3；`missed_windows` 1 |

**独立复算（手工逐决策重数）**：

- R1 `effective_signals`：只有决策 13 之后 `transmitted.R=true`；B、W 始终 false → `1/3 = 0.333`，与 judge 一致。
- R1 `idle_ticks`：唯一 `wait` 是决策 12（`ticks=4`），当时 `power_target=R` 且 `calibration.R=2` → 计 `4`，与 judge 的 `4` 一致。R2 对应决策 11（`ticks=5`）→ `5`，一致。R0 没有 `wait` → `0`，一致。
- R1 `missed_windows`：唯一被跨过且未发射的窗口是 B（end=25），决策 20 结算后 `tick=26 > 25` → `1`，一致。
- `window_utilization ≡ effective_signals`：三局 + 三条基线 + 20 条随机记录，逐条相等（0/3、1/3、1/3 …）。
- `power_overcommit == 0`：25 条本地记录全部为 0。

**`LOW_DISCRIMINATION` 判定**：不成立（`effective_signals` 区分 4 类策略）；但两条 primary 互相冗余，实际只有一条 primary 在起作用。

## 12. V9 状态

**`VALIDATED`，优先级 P1。**

理由：三次失败都能定位到"回 C 不切电 / 在错误节点切电"这一可修复的策略错误，且 19 决策的公开策略可完胜，说明预算、规则与可观察性都成立；但 `switch_power` 的错误码与窗口结算语义是两处明确的接口缺陷（C/B），P1 修复后本图才适合作为"共享供电排程"的正式测量点。
