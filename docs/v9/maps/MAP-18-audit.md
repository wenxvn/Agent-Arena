# MAP-18 审计：故障传播（V9 Batch 1）

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 | MAP-18 / subway |
| 难度 | 困难 |
| condition | `alert_on` |
| `scenario_hash` | `52cde32f9e044815df6763b2feb13b840ef009520866edab51c4b3598a04d88a` |
| `rule_hash` | `aa446dfaa631197cd1f46b66e5c481eef6a68da694f76776afd4567cd75c5d8e` |
| `source_hash` | `e014f03dbb9b1292248bbb438863a736831fa8bdb9adad1c48b28dcceef4441e` |
| `prompt_hash` | `6634e89ab1f1a27e079591b5610983983d4f2d62a01cff578ddedc6e697af2dc` |
| `metric_schema_hash` | `cadd9063303d73b9287c81940fb56e43a5866d0be42e32306d98a0e38f5572e2` |
| 决策预算 / 声明步数上限 | 46 / 160（`create_environment` 与适配器都返回 160） |
| **真实有效步数上限** | **12**（`Map18Environment.__init__`: `self.step_limit = min(step_limit, horizon)`，`horizon=12`） |
| Oracle | 1 个用例 12 个动作（`MAP-18-solver-success`）；`worlds/v4/MAP-18/oracle_trace.jsonl` 另有 `alert_proactive_detour` / `no_alert_reactive_detour` / `no_alert_turnback_cancel_one` 三条 12 动作轨迹 |
| V8 正式三局 | 0/3 成功。R0 `censored` / `ACTION_LIMIT_REACHED`，12 决策，送达 12；R1 `failure` / `STATION_CAPACITY_EXCEEDED`，3 决策，送达 6；R2 `censored` / `ACTION_LIMIT_REACHED`，12 决策，送达 9 |

数据来源：`runs/v9/evidence/MAP-18.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-18-final.md`、`worlds/v4/MAP-18/*`、`src/agent_arena/worlds/scenario_v4/map18.py`、`src/agent_arena/worlds/scenario_v8/v4_adapter.py`、`runs/v9/baselines/MAP-18.json`。

**V6 冻结实例边界（事实）**：`V8_INSTANCE_ID["MAP-18"] = "map18_l3_original"`，condition `alert_on`；`Map18Environment._reset_state` 只接受 `seed ∈ {0,1,2}`，故障窗口硬编码为 `(5, 10)`、故障边为 `R2-R3`、告警 tick 为 4、`success_threshold=13`、`horizon=12`。适配器 `V4MapAdapter` 只做动作转换与决策日志，不改规则。**`step_limit` 是 V4 内部夹紧的，适配器外层属性仍是 160**（实测 `create_environment("MAP-18").step_limit == 160`，`._inner.step_limit == 12`）。

## 1. 能力构念

- **一句话**：在一段信息不完整的线路封锁前，为 6 列车/18 名乘客做在线恢复调度——先判断"收到不含区段与时长的告警后要不要提前绕行"，再在封锁窗口内保住站台容量、封锁解除后恢复红线班次。
- **成功**：tick 12 结算时送达 ≥13/18（`SERVICE_COMPLETE`）。13 是内部阈值（`success_threshold=13`），对外只写作失败码 `DEADLINE_SERVICE_BELOW_70`，**没有公开**。
- **明确反例**：① 同时取消两条红线任务（放弃 6 人）→ 最多 12/18 < 13，无论如何都失败；② 把两列车同时放进已经停着 2 列车的 R2 → `STATION_CAPACITY_EXCEEDED` 立即终局（R1 决策 3）。
- **递进位置**：三图最难。MAP-16 是单线会车，MAP-17 是静态多目标排程，本图加入闭塞故障、告警不确定性、站台容量硬失败、取消/折返动作，以及"任务交付后不可再移动"的不可逆性。它是 subway 唯一的在线恢复构念。

## 2. 机制与因果链

```
起始：tick 0，T_R1@R1、T_R2@R2、T_R3@R3、T_B@B1、T_G@G1、T_X@R2（R2 已 2 车 = 满泊位）
  → 必需观察：topology（三线 + 两个换乘段、每段 1 车、每站 2 泊位）、
     train_positions、station_berths、task_passenger_counts、
     published_dispatch_windows、closed_segments、recovery_status、alert_message_if_any
  → 关键决策：① 是否在 tick 4–5 把 T_X 从 R2 送上 R2→B2 绕行；
     ② 是否让 T_R1 在 R2 只停 1 车（T_R2）时进站；③ 红线对向班次在封锁解除后错峰恢复；
     ④ 是否取消一班并折返空车
  → 立即后果：tick 5–9 `closed_segments = ["R2_R3"]`，该边上的移动返回 `TRACK_CLOSED`（整行仍提交、tick 前进）；
     同边双车 → `SEGMENT_CAPACITY`；站台 >2 车 → `STATION_CAPACITY_EXCEEDED`（立即终局）
  → 终局：tick 12 时送达 ≥13 → SERVICE_COMPLETE，否则 DEADLINE_SERVICE_BELOW_70
```

- **可绕过核心机制的动作：有（事实，已实测）**。`published_dispatch_windows` 只是公开建议，**运行时不校验**。把所有任务压到故障窗口开始（tick 5）之前即可 18/18：`ignore_windows` 消融在 tick 0–4 依次完成 B/G/X/R3/R2/R1 六组任务，tick 5 封锁公开时 18 人已全部送达，`service_rate = 1.0`、`delay_person_ticks = 0`，`first_reroute_delay` 与 `recovery_delay` 都只能是 N/A。封锁机制对这条策略**完全没有触发**。
- **机制是否在三条真实轨迹中实际触发**：
  - R0：**触发了一半**。决策 7 的观察首次出现 `closed_segments ["R2_R3"]`（tick 5），但决策 8 直接把两条红线任务 `cancel_service`（`canceled_passengers 6`），此后没有任何红线恢复。
  - R1：**未触发**。决策 3 就以 `STATION_CAPACITY_EXCEEDED` 终局于 tick 2，早于 tick 5。
  - R2：**未触发恢复段**。决策 4 在 tick 4 就送达 `TASK_R2_R3`（封锁公开前），决策 9 才看到封锁；此后 3 个决策全部被拒，没有"封锁后改线"的成功移动。
  - 结论（事实）：**三局都没有出现"封锁公开后成功改线并恢复红线"的事件**；`recovery_delay` 在 2 局是 N/A（红线提前交付 / 无封锁）、1 局是 CENSORED（取消后未恢复）。
- **触发所需最小动作数**：12 个决策（一个 tick 一行；Oracle 与启发式都是 12）。若要求"跨封锁恢复"，最小也是 12——因为封锁窗口本身占 5 个 tick。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `train_positions`、`station_berths`、`topology`（3 线、2 泊位、1 车/段） | 是 | 每步 | 是：R2 起始 2 车、满泊位是可见的 |
| `task_passenger_counts`（6 组 ×3 人） | 是 | 每步 | 是 |
| `delivered_tasks` / `canceled_tasks` / `delivered_passengers` / `canceled_passengers` | 是 | 每步 | 是 |
| `published_dispatch_windows`（B/G 在 tick 0–1，T_X 绕行 tick 4，T_R1/R2 在 tick 5，T_R3 在 tick 6） | 是 | 每步 | **是，但它是建议不是约束**——不遵守也不会被拒 |
| `closed_segments` | 是 | 封锁期内（tick ≥5） | 是：封锁开始后可看到 |
| `recovery_status`（`not_started`/`section_closed`/`reopened`） | 是 | 每步 | 是 |
| `alert_message_if_any` | 是，但只有 tick 4 一步 | tick 4 | **否**：原文 `"A mainline section may close next tick; the segment and duration are unspecified."`——区段与时长都未定，不能据此定位 R2-R3 |
| 故障窗口 `(5,10)`、故障边 `R2-R3`、告警 tick 4 | **未公开** | — | 只能从 `closed_segments` 第一次出现时反推起始，时长仍未知 |
| 成功阈值 13/18、horizon 12 的失败规则 | **未公开** | — | 只能从 `ticks_remaining` 猜 horizon；13 人阈值完全不可见 |
| "本图机制"提示 | 是，但**内容退化** | 开局 | **否**：`本图机制：A V4 environment behind the V8 public contract.`（Observation 无 `goal`，`map_docstring` 回落到适配器类 docstring） |
| 取消服务会永久放弃该任务 3 人；交付后不可再移动（否则整行 `COMPLETED_TRAIN_MOVED`） | **未公开** | — | 只能试错 |
| `detour` 与 `release` 同为"沿相邻边移动"，没有额外语义 | **未公开** | — | 词表把两者并列，容易误以为 `detour` 可以直达 G2 |
| 隐藏 `judge_state`（`headings`、`locks`、`task_status`、`delay_person_ticks`、`fault_resolution`） | 否 | — | 不需要 |
| Oracle / 参考恢复轨迹 | 否 | — | 不需要 |

**结论（事实 + 推断）**：状态类信息（位置、泊位、任务、窗口、封锁）基本公开；**决策所需的硬规则几乎全部未公开**：阈值 13、窗口长度、窗口是否强制、取消/交付的不可逆性、站台硬失败的时机。因此 MAP-18 的失败里混入了大量"猜规则"的因素。

## 4. 可解性与可观察性

- Oracle：1 个用例、12 个动作、18/18、`SERVICE_COMPLETE`（`runs/v9/baselines/MAP-18.json`）。
- **仅凭公开信息是否存在可执行策略：存在（事实，已实测，两条）**：
  1. `Map18Heuristic`（遵守公开 dispatch window）：12 决策全部被接受，18/18，`delay_person_ticks = 30`、`first_reroute_delay = 1`、`recovery_delay = 6`。
  2. 消融 `ignore_windows`（无视窗口、抢在 tick 5 前完成）：12 决策全部被接受，18/18，`delay_person_ticks = 0`，两条恢复指标 N/A。
- 但**可解性极度脆弱**：有效步数上限 = 12，而可行解正好需要 12 行；**任何一次被拒的决策都会让"到达 tick 12"变得不可能**。R0 3 次拒绝 → tick 9 就 `ACTION_LIMIT_REACHED`；R2 有 7 个非提交行（3 次 `INVALID_LINK`、3 次 `COMPLETED_TRAIN_MOVED`、1 次 `TICK_MISMATCH`）→ tick 5 就被截尾。
- **结论**：任务本身可解（不标 `INTERFACE_BLOCKED` 的"只有隐藏规则能解"含义），但接口把"零容错"写进了上限，属于 `BUDGET_BLOCKED`（§5）。

## 5. 预算可行性

| 策略 | 决策数 | 最终 tick | 终局 | 送达 |
|---|---|---|---|---|
| Oracle | 12 | 12 | `SERVICE_COMPLETE` | 18/18 |
| `public_heuristic` | 12 | 12 | `SERVICE_COMPLETE` | 18/18（delay 30，recovery 6） |
| 消融 `ignore_windows` | 12 | 12 | `SERVICE_COMPLETE` | 18/18（delay 0，恢复指标 N/A） |
| `legal_random`（20 seed） | 12（全部） | 0–4（见下） | 20/20 `ACTION_LIMIT_REACHED` | 0 成功 |

`legal_random` 20 seed：最终 tick 分布 `0:1, 1:5, 2:4, 3:6, 4:4`；结果码 `TICK_MISMATCH` 193、`TICK_COMMITTED` 47。**20/20 都在第 12 个决策被 `ACTION_LIMIT_REACHED` 截断，而当时世界时间最多只走到 tick 4。**

- **判定：是"预算/上限"问题，不是"模型没做对"（高可信度）**。三条独立证据：
  1. 代码事实：`step_limit = min(step_limit, horizon) = 12`，而 prompt 写"本局最多 46 个决策"、`decision_budget = 46`、适配器 `step_limit = 160`。
  2. 随机基线：20/20 在恰好 12 个决策处 `ACTION_LIMIT_REACHED`，与 12 的夹紧一致，与 46 无关。
  3. 可达性反例：R2 在 tick 5 被截尾时仍有可达的 ≥13 路线——`T_R3_R2`（3 人，tick 10 重开后 R3→R2，tick 11 到）+ `T_R2_G2`（3 人，T_X 在 R1，tick 6 R1→R2、7 R2→B2、8 B2→B3、9 B3→G2，tick 10 到）→ 9+6 = 15 ≥ 13。只差 7 个决策（tick 5–11 各一行）就能走完，却被 12 的硬上限截断。
- **是否 `BUDGET_BLOCKED`：是**。声明预算 46、实际可用 12、零余量。注意 R0 即使不截尾也大概率失败（取消 6 人后上限 12 < 13），所以 R0 是"失败判定成立、但终止码被截尾覆盖"；R2 则是**截尾直接掐死了一条可达的成功路径**。

## 6. 指标

| 指标 | 计算事件 | 分母 | 缺失/截尾 | R0 | R1 | R2 |
|---|---|---|---|---|---|---|
| `map18.service_rate` | `delivered_passengers / 18` | 总需求 18 | 截尾 → CENSORED（值保留） | censored 0.666667 | valid 0.333333 | censored 0.5 |
| `map18.delay_person_ticks` | Σ 3×max(到达−计划,0)，按首次交付去重 | 已交付任务 | 截尾 → CENSORED | censored 6 | valid 0 | censored 0 |
| `map18.first_reroute_delay` | 封锁公开后首个非封闭移动 tick − 封锁公开 tick | 发生封锁的 episode | 无封锁/无移动 → N/A；有移动但未成功 → CENSORED | valid 1 | N/A | N/A |
| `map18.recovery_delay` | 封锁后首个红线任务交付 tick − 封锁公开 tick | 发生封锁的 episode | 红线已在封锁前交付 → N/A；未恢复且截尾 → CENSORED | censored（值 None） | N/A | N/A |
| `map18.station_capacity_violations` | `STATION_CAPACITY_EXCEEDED` 次数 | episode | 0 合法 | 0 | 1 | 0 |
| `map18.collision_violations` | `HEAD_ON_COLLISION` + `SEGMENT_CAPACITY` | episode | 0 合法 | 0 | 0 | 0 |
| `map18.completed_train_moves` | `COMPLETED_TRAIN_MOVED` 次数 | episode | 0 合法 | 0 | 0 | 3 |
| `map18.legal_action_rate` | 非拒绝 `set_timetable` / 提交数 | 提交数 | 0 → N/A | 0.75 | 1.0 | 0.666667 |

- **为什么 `recovery_delay` 是 N/A / CENSORED（逐局）**：
  - R1：**从未观察到封锁**。tick 2 就因站台超容终局，`_closure_tick()` 返回 None → `first_reroute_delay` 与 `recovery_delay` 都走"无封锁 → N/A"分支。
  - R2：**红线任务在封锁公开前已交付**。决策 4（`tick: 3` 的行，`tick_after = 4`）已把 `TASK_R2_R3` 送达，而封锁首次公开在 `tick_after = 5`；`map18.py::compute` 的 `red_delivered_before` 非空 → 按预登记规则返回 N/A（"封锁没有留下可测的恢复延迟"）。这不是投影口径，是设计里写明的缺失规则。
  - R0：**取消后未恢复且截尾**。决策 8 把 `TASK_R2_R3`/`TASK_R3_R2` 取消，之后没有红线交付；episode 又是 censored → CENSORED（没有值）。
- **为什么 `service_rate` / `delay_person_ticks` 在 R0/R2 是 CENSORED 而不是 N/A**：episode 是 step-limit 截尾（`episode_is_censored` 为真），V7 规则要求"值仍为已交付比例/已观察延误，但状态标 CENSORED"。V8 落盘的 `v8_metrics.json` 保留了 0.666667 / 6 这些值；`runs/v9/evidence` 里的 `judge_metrics` 摘要把非 valid 的值写成 `null`，那是**摘要层的显示口径**，不是"指标算不出来"。
- **未通关仍有意义的连续主指标**：`service_rate`（0.5 / 0.667）、`delay_person_ticks`（0 / 6）。两者都不要求成功终局。
- **`legal_action_rate` 存在实现缺陷（事实，可复算）**：R2 只有 5 行真正 `TICK_COMMITTED`（决策 1、2、3、4、9），决策 7、10、12 是 `COMPLETED_TRAIN_MOVED`——整行被拒、tick 不变，却被算作"合法"，于是得到 8/12 = 0.667。`v7/metrics/common.py::REJECTED_RESULTS` 不含 `COMPLETED_TRAIN_MOVED`，`is_rejected_result` 也不匹配 `INVALID*`。这条指标夸大了 6 个百分点的接受率。
- **区分度**：Oracle/heuristic/消融都是 1.0 服务率，随机是 0；`delay_person_ticks` 30（守窗口）vs 0（抢跑）正好暴露构造旁路；`recovery_delay` 6 vs N/A。能区分，但**主恢复指标在最优策略上恰好 N/A**，这是设计层面的问题而不是区分度不足。

## 7. 三次轨迹归因

### R0（12 决策，`ACTION_LIMIT_REACHED`，tick 9，送达 12/18）

| 决策 | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 4 | `{"operations":{"T_X":{"op":"detour","to":"G2"}},"tick":3,"tool":"set_timetable"}` | `INVALID_LINK` | `{}` |
| 5 | `{"operations":{"T_X":{"op":"release","to":"B2"}},"tick":3,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"alert_message_if_any":{"id":"NETWORK_DISRUPTION_WATCH","message":"A mainline section may close next tick; the segment and duration are unspecified."},"station_berths":{"B2":1,"B3":1,"G3":1,"R1":1,"R2":1,"R3":1},"tick":4,"ticks_remaining":8,"train_positions":{"T_B":"B3","T_G":"G3","T_R1":"R1","T_R2":"R2","T_R3":"R3","T_X":"B2"}}` |
| 7 | `{"operations":{"T_R1":{"op":"release","to":"R2"},"T_X":{"op":"release","to":"B3"}},"tick":4,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"alert_message_if_any":null,"closed_segments":["R2_R3"],"delivered_passengers":9,"delivered_tasks":["TASK_B1_B3","TASK_G1_G3","TASK_R1_R2"],"recovery_status":"section_closed","station_berths":{"B3":2,"G3":1,"R2":2,"R3":1},"tick":5,"ticks_remaining":7,"train_positions":{"T_B":"B3","T_G":"G3","T_R1":"R2","T_R2":"R2","T_R3":"R3","T_X":"B3"}}` |
| 8 | `{"operations":{"T_R2":{"op":"cancel_service","task_id":"TASK_R2_R3"},"T_R3":{"op":"cancel_service","task_id":"TASK_R3_R2"},"T_X":{"op":"release","to":"B2"}},"tick":5,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"canceled_passengers":6,"canceled_tasks":["TASK_R2_R3","TASK_R3_R2"],"station_berths":{"B2":1,"B3":1,"G3":1,"R2":2,"R3":1},"tick":6,"ticks_remaining":6,"train_positions":{"T_B":"B3","T_G":"G3","T_R1":"R2","T_R2":"R2","T_R3":"R3","T_X":"B2"}}` |
| 12 | `{"operations":{},"tick":8,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"terminal":true,"terminal_reason":"ACTION_LIMIT_REACHED","tick":9,"ticks_remaining":3}` |

- **首次偏离合理策略的可观测事件**：决策 4 `T_X detour → G2`。T_X 当时在 R2，G2 不与 R2 相邻（R2 邻 R1/R3/B2），整行 `INVALID_LINK`；正确写法是先 `release B2`。这一个决策的浪费直接导致后面只剩 11 个决策可用。
- **失败链**：决策 4 浪费 1 个决策 → 决策 5 才把 T_X 送出 → 决策 6 又一次 `INVALID_LINK`（同时带 `T_R1 release R2` 与 `T_X detour G2`，整行被拒；`detour` 仍然只能到相邻节点）→ 决策 7 才成功把 T_R1 送进 R2 → 决策 8 面对已公开的封锁，选择**取消两条红线任务**（放弃 6 人，等于把上限压到 12）→ 决策 9 再 1 次 `INVALID_LINK` → 决策 12 时 12 个决策用满，tick 只到 9，`ACTION_LIMIT_REACHED`。
- **替代解释**：① 上限（D）：3 次拒绝让 tick 少走 3 步，12 的硬上限先到；② 策略（E）：取消 6 人后 12 < 13，即使给到 tick 12 也只会以 `DEADLINE_SERVICE_BELOW_70` 失败；③ 接口（B/C）：告警明确说"区段与时长未定"，模型没有任何公开办法确认封锁多长，取消是对不确定性的合理保守反应——但它同时把胜负判死了。**首因 D（终止码/上限），次因 E（取消使成功不可达）；可信度高。**
- **重要限定（事实）**：R0 的**胜负**（失败）本来就不会因截尾而改变，改变的是**终止原因**（应为 `DEADLINE_SERVICE_BELOW_70`，实为 `ACTION_LIMIT_REACHED`）。

### R1（3 决策，`STATION_CAPACITY_EXCEEDED`，tick 2）

| 决策 | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 1 | `{"operations":{"T_B":{"op":"release","to":"B2"},"T_G":{"op":"release","to":"G2"}},"tick":0,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"station_berths":{"B2":1,"G2":1,"R1":1,"R2":2,"R3":1},"tick":1,"ticks_remaining":11,"train_positions":{"T_B":"B2","T_G":"G2","T_R1":"R1","T_R2":"R2","T_R3":"R3","T_X":"R2"}}` |
| 2 | `{"operations":{"T_B":{"op":"release","to":"B3"},"T_G":{"op":"release","to":"G3"}},"tick":1,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"delivered_passengers":6,"delivered_tasks":["TASK_B1_B3","TASK_G1_G3"],"station_berths":{"B3":1,"G3":1,"R1":1,"R2":2,"R3":1},"tick":2,"ticks_remaining":10,"train_positions":{"T_B":"B3","T_G":"G3","T_R1":"R1","T_R2":"R2","T_R3":"R3","T_X":"R2"}}` |
| 3 | `{"operations":{"T_R1":{"op":"release","to":"R2"},"T_R3":{"op":"release","to":"R2"}},"tick":2,"tool":"set_timetable"}` | `STATION_CAPACITY_EXCEEDED` | `{"terminal":true,"terminal_reason":"STATION_CAPACITY_EXCEEDED"}` |

- **首次偏离**：决策 3。R2 在决策 2 后的 `station_berths` 明确是 `R2: 2`（T_R2 与 T_X），再送 T_R1 与 T_R3 进去就是 4 车，超过 `station_train_berth_capacity: 2`。
- **失败链**：B/G 正常送达 6 人 → 决策 3 四车挤 R2 → 立即终局。这是"站台容量"护栏的真实触发，机制本身有效。
- **替代解释**：① 策略/资源管理（E/F）——公开 Observation 已经给出 `R2: 2` 与泊位 2，模型没有做算术；② 接口（C）——`STATION_CAPACITY_EXCEEDED` 是**立即终局**，没有"整行被拒、只浪费一 tick"的软失败选项，这与 R0/R2 遇到的拒绝语义不一致，模型无法从一次同类错误中学习；③ 预算（D）——不成立（只用了 3 个决策就失败，而且是因为超容）。

### R2（12 决策，`ACTION_LIMIT_REACHED`，tick 5，送达 9/18）

| 决策 | 动作 | 结果 | 观察变化（原文） |
|---|---|---|---|
| 4 | `{"operations":{"T_R1":{"op":"release","to":"R2"},"T_R2":{"op":"release","to":"R3"}},"tick":3,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"alert_message_if_any":{"id":"NETWORK_DISRUPTION_WATCH","message":"A mainline section may close next tick; the segment and duration are unspecified."},"delivered_passengers":9,"delivered_tasks":["TASK_B1_B3","TASK_R1_R2","TASK_R2_R3"],"station_berths":{"B3":1,"G2":1,"R2":2,"R3":2},"tick":4,"ticks_remaining":8,"train_positions":{"T_B":"B3","T_G":"G2","T_R1":"R2","T_R2":"R3","T_R3":"R3","T_X":"R2"}}` |
| 5 | `{"operations":{"T_R1":{"op":"release","to":"R3"},"T_X":{"op":"detour","to":"G2"}},"tick":4,"tool":"set_timetable"}` | `INVALID_LINK` | `{}` |
| 7 | `{"operations":{"T_R1":{"op":"release","to":"R3"}},"tick":4,"tool":"set_timetable"}` | `COMPLETED_TRAIN_MOVED` | `{}` |
| 9 | `{"operations":{"T_X":{"op":"release","to":"R1"}},"tick":4,"tool":"set_timetable"}` | `TICK_COMMITTED` | `{"alert_message_if_any":null,"closed_segments":["R2_R3"],"recovery_status":"section_closed","station_berths":{"B3":1,"G2":1,"R1":1,"R2":1,"R3":2},"tick":5,"ticks_remaining":7,"train_positions":{"T_B":"B3","T_G":"G2","T_R1":"R2","T_R2":"R3","T_R3":"R3","T_X":"R1"}}` |
| 11 | `{"operations":{"T_B":{"op":"release","to":"B2"},"T_R2":{"op":"detour","to":"R2"},"T_X":{"op":"release","to":"R2"}},"tick":6,"tool":"set_timetable"}` | `TICK_MISMATCH` | `{}` |
| 12 | `{"operations":{"T_B":{"op":"release","to":"B2"},"T_R2":{"op":"detour","to":"R2"},"T_X":{"op":"release","to":"R2"}},"tick":5,"tool":"set_timetable"}` | `COMPLETED_TRAIN_MOVED` | `{"terminal":true,"terminal_reason":"ACTION_LIMIT_REACHED"}` |

- **首次偏离**：决策 5。T_R1 已在 R2（决策 4），R2 只与 R1/R3/B2 相邻，`R2→R3` 在封锁后的第一步是合法边（此刻 tick 4 尚未封锁），但同一行里的 `T_X detour → G2` 非法（R2 不邻 G2、`detour` 也只沿相邻边），整行被拒。**这是"一个 op 写错，整张时刻表不提交"的典型代价。**
- **失败链**：决策 5/6/8 三次 `INVALID_LINK`（T_R1→R3、T_R2→R2、T_X detour→G2）→ 决策 7/10 又对已交付的列车发 `release` → `COMPLETED_TRAIN_MOVED`（整行被拒）→ 决策 9 把 T_X 送去 R1（合法但远离它的 G2 任务）→ 决策 11 用 tick 6（实际 tick 5）→ 决策 12 用 tick 5 但含已交付的 T_R2 → 12 个决策用满，tick 只到 5。
- **替代解释**：① 上限（D）：7 个非提交行让世界时间只走了 5 个 tick，12 的硬上限先到；② 推理（G）：决策 7/10/12 三次对同一批已交付列车重发动作，没有记住 `delivered_tasks`；③ 策略（E）：T_X 送 R1 后仍可在 4 个 tick 内到 G2（R1→R2→B2→B3→G2），所以红线和 T_X 任务在 tick 11 前都可完成，**这条成功路径是被上限掐死的，不是策略不可行**；④ 接口（B/C）：`detour` 的语义与 `release` 相同这一事实未公开，模型反复用它做"跨线直达"。

**重复证据有限**：三局的失败类型完全不同（取消后不可达 / 站台超容 / 上限掐死可达路径），n=3 反而说明"同一张图会以三种不同方式失败"，不能据此估计稳定成功率；也说明"12 步上限"和"未公开的取消/交付语义"同时污染了归因。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **D** 决策/时间上限（12 决策、3 次拒绝 → tick 9 截尾） | **E** 取消两条红线（上限 12 < 13）；**B** 告警不含区段/时长 | 高 | 决策 4、7、8、12；`map18.py` L98 |
| R1 | **E/F** 资源管理错误（R2 已 2 车仍送 2 车） | **C** 站台超容是立即终局，与其它拒绝的软失败语义不一致 | 高 | 决策 2 的 `station_berths {R2:2}`、决策 3 |
| R2 | **D** 上限（7 个非提交行 → tick 5 截尾，可达 15/18 被掐死） | **G** 对已交付列车重复发动作（决策 7/10/12）；**B** `detour` 语义未公开 | 高 | 决策 4、5、7、9、11、12 |

## 9. 标签

- **`BUDGET_BLOCKED`**：声明 46 决策、真实上限 12，且可行解正好需要 12；20/20 随机与 2/3 MiMo 都在第 12 个决策被 `ACTION_LIMIT_REACHED` 截断；R2 有可达的 15/18 路径被掐死。
- **`RULE_DEFECT`**：`Map18Environment.__init__` 用 `self.step_limit = min(step_limit, horizon)` 把"动作上限"与"世界 horizon"绑死，导致拒绝动作（不推进 tick）也消耗 horizon；同一"坏行"在不同地图/不同拒绝类型下的时钟代价不一致。
- **`CONSTRUCT_BYPASS`**：`published_dispatch_windows` 不被强制执行，`ignore_windows` 消融在 tick 5 前完成 18/18，`delay_person_ticks = 0`，两条恢复指标 N/A——"在线恢复"构念可以被完全绕过。
- **`METRIC_DEFECT`**：`legal_action_rate` 把 `COMPLETED_TRAIN_MOVED`（整行被拒、tick 不变）算作"接受"（R2 8/12 vs 实际 5 次提交成功）；`service_rate`/`delay_person_ticks` 在截尾局保留数值但 `judge_metrics` 摘要写 `null`，两层口径不一致。
- **未标 `MEASUREMENT_VALID`**：机制本身有效（站台超容、封边、红线不可逆都真实存在），但在当前上限与旁路下，三局的终止码不能干净地归因到"恢复能力"。
- **未标 `INTERFACE_BLOCKED`**：存在 12 决策的纯公开策略（守窗口与抢跑两条），不是"只有隐藏规则能解"；问题是**零容错**与**构念可绕过**。

## 10. 最小可证伪修复（无证据不修改）

**旧规则 / 旧公开信息**：`step_limit = min(step_limit, 12)`；dispatch windows 仅公开、不校验；`本图机制` 为适配器 docstring；阈值 13 不公开。

**证据与根因**：
1. 上限夹紧：`create_environment("MAP-18").step_limit == 160`，但 `._inner.step_limit == 12`；20/20 随机局在 12 决策处 `ACTION_LIMIT_REACHED`，最终 tick 0–4。
2. 构念旁路：`ignore_windows` 12 决策 18/18、delay 0、`first_reroute_delay`/`recovery_delay` = N/A；三局真实轨迹里也从未出现"封锁后成功改线并恢复红线"。
3. 指标：R2 只有 5 行 `TICK_COMMITTED`，`legal_action_rate` 却报 8/12。

**候选 A（P0，接口/上限，优先）**：不要让 `step_limit` 等于 horizon。最小改动是 `self.step_limit = max(step_limit, horizon)`（或直接使用传入值 160），并把"剩余决策"与"剩余 tick"分开报告；公开信息里同时写明"每个 tick 至多 1 个决策、格式错误也消耗 1 个决策"。
- 预期变化：`ACTION_LIMIT_REACHED` 只在真正的决策预算耗尽时出现；截尾局从"tick 4–9"变成 tick 12；R2 那类可达路径能被走完；`service_rate`/`delay_person_ticks` 的 CENSORED 大幅减少。
- 能力构念影响：恢复能力终于可测；失败会回到"策略/资源"而不是"上限"。
- 反例与回归风险：改 `map18.py` 会改 `rule_hash`，旧 Trace 不可直接回放，必须新建 DCR、重算 hash，并且**不得**与 V8 历史 90 局混用；另外要给足余量但不改变 horizon，避免把"恢复"变成"慢慢试"。

**候选 B（P0/P1，构念旁路）**：二选一，不能同时做——
- B1：把 `published_dispatch_windows` 变成**约束**（窗口外 release 被拒），这样"抢跑"不再可行；代价是新规则、新 `rule_hash`，且会与"窗口只是建议"的现有文案冲突。
- B2：把故障窗口提前到 tick 2（或缩短 `horizon` 内可用前置 tick），让任何策略都无法在封锁前完成全部任务；代价是改实例（`scenario_hash`/`source_hash`），需要新的 V6/V8 实例 ID。
- 推荐 B2 的"提前故障"版本，因为它是难度/实例问题，不需要新增拒绝语义；预期 `first_reroute_delay`/`recovery_delay` 在成功局上都有值，`delay_person_ticks` 不再被 0 刷满。
- 反例与回归风险：提前故障可能让 13/18 不可达（需要先用 Oracle 重解）；`no_alert_*` 三条 Oracle 轨迹也要重算。

**候选 C（P1，只补公开信息）**：公开阈值 13/18、horizon 12 的结算规则、取消服务会永久放弃 3 人、交付后不可再移动、`detour` 与 `release` 同为邻边移动。
- 证据：R0 决策 8 取消两人份（6 人）直接封死 13；R2 决策 5/6/8 反复用 `detour` 做跨线；R2 决策 7/10/12 对已交付列车发动作。
- 预期：`completed_train_moves`、`INVALID_LINK` 下降；取消决策变成真正的取舍而不是误判。
- 回归风险：信息变多后本图可能不再"困难"；但阈值本来就该公开，否则测量的不是恢复能力而是猜数。

**候选 D（P2，指标实现）**：
1. `legal_action_rate` 应把 `COMPLETED_TRAIN_MOVED` 计入拒绝（或另设 `row_committed_rate`），证据 R2 5 vs 8；
2. `judge_metrics` 摘要不要丢弃 CENSORED 的数值（R0 的 0.666667 / 6 是有信息的）；
3. `recovery_delay` 在"红线已提前交付"时返回 N/A 是**正确**的，但在候选 B 修复后应能在成功局上取到值——把它作为修复是否生效的判据。
- 回归风险：改 extractor 会改历史复算值（`metric_schema_hash` 不变，但同 hash 下数值变了），必须在 `docs/v9/metric-independent-check.md` 记录并重跑 90 局复算。

**不做的事**：不通过加大 horizon、降低阈值或增加站台泊位来"让成功率好看"；这些都会改变构念，只能作为新 DCR 显式登记。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-18.json`：

| 基线 | 结果 | 决策 | 主指标 |
|---|---|---|---|
| Oracle | `SERVICE_COMPLETE` | 12 | 18/18 |
| `legal_random`（20 seed） | 0 成功，20/20 `ACTION_LIMIT_REACHED` | 12（全部） | 最终 tick 0–4 |
| `public_heuristic` | `SERVICE_COMPLETE` | 12 | service 1.0、delay 30、first_reroute 1、recovery 6 |
| 消融 `ignore_windows` | `SERVICE_COMPLETE` | 12 | service 1.0、delay 0、first_reroute/recovery N/A |

**独立复算（手算，不经过 extractor）**——启发式那一局：

- 送达与到达 tick：`TASK_B1_B3` 2、`TASK_G1_G3` 2、`TASK_R2_G2` 7、`TASK_R3_R2` 3（T_R3 在 tick 2 的 R3→R2，arrival 3）、`TASK_R1_R2` 6（tick 5 的 R1→R2，arrival 6）、`TASK_R2_R3` 11（tick 10 的 R2→R3，arrival 11）→ **18/18**。
- `delay_person_ticks`：只有两条红线晚于计划——`TASK_R2_R3` 3×(11−6)=15，`TASK_R3_R2` 3×(12−7)=15，其余 0 → **30**，与运行时一致。
- `recovery_delay`：红线首次在封锁公开（tick 5）之后交付是 tick 11 → 11−5 = **6**。
- `first_reroute_delay`：封锁公开于 tick 5，之后首个非封闭移动是 tick 6 的行（`T_X B2→B3`）→ 6−5 = **1**。
- `legal_action_rate` 的独立反算：12 行里真正 `TICK_COMMITTED` 的也是 12 行（启发式零拒绝）→ 1.0，与运行时一致；同一算法套到 R2 得 5/12 = 0.417，而运行时给 0.667，**这就是 §6 的指标缺陷**。

结论：主指标（服务率、延误、恢复延迟）全部可由 Trace 手算复现；`legal_action_rate` 的差异已被定位到 `REJECTED_RESULTS` 的遗漏，不是随机波动。**没有 `LOW_DISCRIMINATION`**（守窗口 30 vs 抢跑 0 vs 随机 N/A），但区分的方向恰好是"越守规则越差"，这也印证了 `CONSTRUCT_BYPASS`。

## 12. V9 状态

**`NEEDS_REDESIGN`（P0）**。

理由：三局 0/3 里没有一局真正测到"封锁后在线恢复"——R1 在 tick 2 就死于站台超容，R0 取消红线后封死，R2 的封锁后行动全部被拒且在 tick 5 被 12 的硬上限截断。同时，一条不遵守公开窗口、抢在 tick 5 前完成的策略可以 18/18 且让两条恢复指标变成 N/A，说明构念可以被绕过。两个问题都必须在下一轮真实实验前处理：先解耦 `step_limit` 与 horizon（保证 12 tick 内可犯错、可恢复），再让封锁无法被前置跑完（提前故障窗口或把窗口变成约束）。在此之前，MAP-18 的任何模型成功率都不能解释为"在线恢复能力"。
