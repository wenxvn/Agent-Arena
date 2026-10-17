# MAP-19 审计：温度临界点

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-19 / volcano / 简单 |
| condition | `default` |
| `rule_hash` | `28b181b4b82e63005302789504eb74fb4a81f1186fb808ba3b1ced749b88328d` |
| `scenario_hash` | `5c9491adac611088209ce6c37b98c1a421bc49e039adeed54398a6ce34db96f8` |
| `source_hash` | `a86e153f946ec378d6c3411aa1d5ed57eeb4a88587b9a604667bd023caf621e9` |
| `prompt_hash` | `4750ba4b14041503f7026658e420ce4c43d1746fdf4768e445a6690b753c49e2` |
| `metric_schema_hash` | `04755621dae6661ae0bbf1e99f2727d8a1ddc2f7f6f51ab9be6777913d6de3fd` |
| 决策预算 | 30 |
| V8 三局 | 0/3 成功；`decision_budget_reached`×2、`failure`×1（`THERMAL_RUNAWAY`）；决策 30 / 23 / 30 |

数据来源：`runs/v9/evidence/MAP-19.json`、`docs/v9/run-index.csv`、`docs/v8/maps/MAP-19-final.md`、`worlds/v4/MAP-19/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map19.py`、`src/agent_arena/v8/prompts.py`。本审计新增的只读产物为 `runs/v9/baselines/MAP-19.json` 与 `src/agent_arena/v9/policies/world_volcano.py`；未改写任何 V8 文件、账本或 Trace。

## 1. 能力构念

这张图想测的是**在固定 2 tick 阀门时滞下，用负荷档位换取热安全与产能的前馈控制能力**：玩家要先于危险两 tick 下阀，再在阀门成熟前主动降载，最后回到稳态负荷并走完 12 tick。

- 成功行为：12 个结算 tick 内三区温度始终 `<= 10`，且 `production_points >= 20`；允许把温度压在 10 的等号上。
- 明确反例：在阀门成熟前保持高负荷，让任一区在成熟前 `> 10`（R1 的 C 区）；或把决策预算花在不推进时钟的自由动作上，12 tick 根本没走完（R0、R2）。
- 递进位置：本图是该世界的**简单**图，只保留“时滞 + 负荷/冷却配比”一条因果；没有移动、没有随机事件、没有跨区热传导。中等图把时滞换成有损管网（MAP-20），困难图把热控制换成隐藏喷发时刻的风险决策（MAP-21）。

## 2. 机制与因果链

**本图专属因果链**

1. 起始状态：`temperature_bands={A:WARM,B:WARM,C:COOL}`、`current_load_levels={A:2,B:2,C:2}`、`active_cooling` 全 0、`production_points=0/20`（`runs/v9/evidence/MAP-19.json` 的 `initial_observation`，三局相同）。
2. 必需观察：`temperature_bands`（5 档）、`pending_cooling_commands[].effective_tick`、`active_cooling`、`current_load_levels`、`production_points`；外加至多一个区的精确读数。
3. 关键决策：在 tick 0 提交总预算内的冷却向量（如 `[2,1,1]`）；在 `effective_tick` 之前把三区负荷降到净升温可接受的水平；冷却成熟后回到 `[2,1,1]` 负荷并 `wait` 到 tick 12。
4. 立即后果：`wait` 时先让 `effective_tick <= tick` 的命令成熟，再按 `max(0, T + load - active_cooling)` 同时更新三区；任一区 `> 10` 立即 `THERMAL_RUNAWAY`；否则每 tick 记 `sum(loads)` 产能。
5. 终局：tick 12 且产能 `>= 20` → `PRODUCTION_TARGET_MET`；否则 `PRODUCTION_BELOW_20`。

**可绕过点（事实）**

- `forecast_next` 不改变任何环境状态、不改变成功条件，也不进入任何 V8 指标。它的误差只写进 `judge_state.forecast_errors`（`map19.py::judge_state`），而 `metrics()` 完全不读它；V7 registry 里也没有 MAP-19 的预测误差指标。三局真实轨迹中 **没有任何一次 `forecast_next`**（R0/R1/R2 的 `steps[].action.tool` 无此值）。因此“推算下一次热状态”这一构念可以被 0 个动作完全跳过。
- 成功本身不要求“延迟感知”：固定 `[2,1,1]` 冷却 + 立刻 `[2,1,1]` 负荷（消融 `no_lag_load_curtailment`）仍然成功（14 决策），只是 `temperature_exceedance_area` 从 0 变成 22。时滞只被主指标惩罚，不被成功条件要求。

**机制是否在三条轨迹中实际触发（引用决策序号）**

- R1 决策 1 `set_cooling [2,2,0]` → `COOLING_QUEUED_FOR_TICK:2`；决策 2 `wait` 后 `temperature_bands` 变为 `{"A":"RISING","B":"WARM","C":"WARM"}`，说明 tick 1 仍在无冷却状态下升温——时滞**实际触发**。
- R1 决策 21 `wait`：`active_cooling` 变成 `{"A":2,"B":2,"C":0}`，即 tick 2 成熟的是决策 1 的 `[2,2,0]`，而不是模型后补的 `[2,1,1]`——**同 effective_tick 后入队者覆盖**这一语义实际触发。
- R2 决策 8 `wait` 后停在 tick 2，决策 9–30 全部是零时长动作，直到预算耗尽都没再推进时钟——**自由动作不耗时的接口性质**实际触发（见 §7）。

**触发所需最小动作数**：3 个（`set_cooling` + `wait` + `wait`）就能观察到一条命令从入队到 `active_cooling` 生效。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `tick` / `ticks_remaining` | 是（Observation） | 每步 | 是（决定还要 `wait` 几次） |
| `temperature_bands`（COOL<=4 / WARM<=7 / RISING=8 / NEAR_LIMIT<=10 / OVERHEAT>10） | 是 | 每步 | 是（可确认是否已入危险档） |
| 精确温度 | 部分：每 tick 至多一个区，`wait` 后清空 | 读温当步 | 是（静态方案不依赖精确值） |
| `delta`（上一次 `dT`） | 仅随精确读数返回 | 读温当步 | 辅助；单次读数不含其它区 |
| 冷却命令 2 tick 生效 | 是（goal 文本） | 初始 prompt | 是 |
| 冷却总预算 4、每区 0–2 | **否**：词表只说“三个 0..2 的整数”，总和不公开 | 只能靠 `VALVE_BUDGET_EXCEEDED` 试出 | 是（可从拒绝码退让） |
| 同一 `effective_tick` 上多条命令的胜者 | **否**：Observation 只列出全部 pending，不标“最后一条生效” | 只能靠读数反推 | 是（但极易误判，见 R1/R2） |
| 产能记分规则 = 当 tick 负荷之和 | **否**：goal 只说“累计至少 20 点产能” | 由 `production_points` 增量反推 | 是 |
| 转移式 `max(0, T+load-cooling)` | **否**（只在代码与 V4 `map_spec.yaml`） | 由读数/档位反推 | 是 |
| `forecast_next` 的误差反馈 | **否**：错误只进 `judge_state`，不进 Observation，也无指标 | 永不 | 否（该动作对解题无信息价值） |
| `judge_state`（精确温度、`settled_states`、`deltas`、`forecast_errors`） | 否 | — | 不应被使用 |
| Oracle 路径（`ORACLE_CASES`、`oracle_trace.jsonl`） | 否 | — | 不参与运行时 |

结论：**没有只存在于私有 docstring 的“硬规则”被成功条件依赖**；但冷却总预算与队列覆盖顺序是两条只在代码里的运行语义，属于 C 类接口风险，不是 B 类阻断（公开启发式 15 决策可解）。

## 4. 可解性与可观察性

- Oracle：2 个用例（`early_cooling`、`exact_production_boundary`），各 27 个动作，`baseline_run` 复算 `oracle_ok=2/2`（`runs/v9/baselines/MAP-19.json`）。
- **仅凭公开信息**的可执行策略：存在。`world_volcano.py::Map19Heuristic` 只用 bands、`active_cooling`、`current_load_levels` 与 `tick`，15 个动作成功（§11）。其安全性不依赖精确初始温度：`WARM` 上限为 7，延迟窗口内每区负荷 1，两 tick 最多到 9，仍 `<= 10`；冷却在 tick 2 成熟后净变化为 0。
- 反例不是“信息不够”而是“动作经济”：R0、R2 在 tick 5 / tick 2 就耗尽 30 个决策，而走完 12 tick 只需要 12 个 `wait`。因此不标 `INTERFACE_BLOCKED` 或 `BUDGET_BLOCKED`。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| 决策预算 | 30 |
| Oracle 动作数 | 27（含 11 个无效果的 `forecast_next`） |
| 公开启发式动作数 | 15（3 个控制 + 12 个 `wait`） |
| 消融动作数 | 14 |
| 走完 12 tick 的硬下限 | 12 个 `wait` |

`legal_random` 20 seed：成功 **0/20**；19 局 `THERMAL_RUNAWAY`、1 局 `decision_budget_reached`；非法动作 48、被拒动作 49；决策数分布为 `{6,7,8,9,10,12,13,14,15,19,24,27,30}`。随机基线在 6–15 个决策内就把温度打穿，说明失败门槛低、成功需要的是控制而不是运气。

**判定：不是预算不够，是模型没做对。** 30 个决策里 12 个必须用于 `wait`，还剩 18 个自由决策；R0 走完 tick 5 后用掉 19 个决策，剩余 11 个全部花在零时长动作上；R2 走完 tick 2 后就用掉 8 个决策，剩余 22 个同样零推进。两局都不是“时间不够”，而是把预算换成了不推进时钟的动作。

## 6. 指标

| 指标 | 类别 | 计算事件 | 分母 | 缺失/截尾规则 | 三局取值 |
|---|---|---|---|---|---|
| `map19.temperature_exceedance_area` | primary | Σ 每 tick 每区 `max(0, T-8)`，含熔断 tick | 声明为“有效 tick 数”，实现返回**未归一化的和** | 声明“预算/provider 截尾 → CENSORED”；实现未执行 | R0=3、R1=15、R2=3（全部 `valid`） |
| `map19.oscillation_count` | primary | 三区相邻非零 `dT` 的符号变化次数之和 | episode | 同上 | R0=2、R1=0、R2=0 |
| `map19.critical_overheat_ticks` | guardrail | 已记录状态中 `T > 10` 的区·tick 数 | episode | 同上 | R0=0、R1=1、R2=0 |
| `map19.coolant_exhausted` | diagnostic | `terminal_reason == COOLANT_EXHAUSTED` | episode | 同上 | 0/0/0（原因码不可达） |

- **未通关仍有意义的连续主指标**：有，`temperature_exceedance_area`（R1=15 与 R0/R2=3 可区分）。但它没有按结算 tick 数归一：R0 结算 5 tick（15 个区·tick）得 3，R2 结算 2 tick（6 个区·tick）得 3，二者原始值相同而每区·tick 严重度是 0.2 与 0.5，跨局不可比。
- **截尾口径**：三局都出现“预算截尾”（R0/R2），但两局的 area 被投影为 `valid` 而非 `censored`。`src/agent_arena/v8/metrics.py::_from_raw` 只在值为 `None` 时才走五态缺失分支，数值型指标一律 `valid`，与指标卡声明的截尾规则不一致。这是本图最明确的 `METRIC_DEFECT`。
- `not_applicable`：0 次（三局 4/4 指标 `valid`）。`coolant_exhausted` 恒为 0 是因为运行时不设冷却剂池、`COOLANT_EXHAUSTED` 不可达，属于“合法但零判别力”，不是 N/A。
- **判别力**：能区分。启发式 area=0 vs 消融 area=22 vs R1 area=15；osc 2 vs 0。唯一无法区分的是 `coolant_exhausted`（恒 0）。

## 7. 三次轨迹归因

### R0（`V8-MAP-19-R0-20261017T093205Z-3f40887f`，`decision_budget_reached`，30 决策，停在 tick 5）

- 决策 2：`{"station":"C","tool":"read_temperature"}` → `TEMPERATURE_READ:C`，观察变化 `{"last_temperature_reading":{"delta":0,"temperature":4,"tick":0,"zone":"C"}}`。
- 决策 3：`{"station":"A","tool":"read_temperature"}` → `READ_ALREADY_USED`，观察变化 `{}`（同 tick 第二次读温被拒，白付 1 个决策）。
- 决策 14：`{"set_cooling":[2,2,2],"tool":"set_cooling"}` → `VALVE_BUDGET_EXCEEDED`，观察变化 `{}`。
- 决策 19：`{"tool":"wait"}` → `TICK_SETTLED`，观察变化 `{"production_points":16,"temperature_bands":{"A":"WARM","B":"COOL","C":"NEAR_LIMIT"},"tick":5,"ticks_remaining":7}`。
- 决策 30：`{"set_cooling":[1,1,2],"tool":"set_cooling"}` → `COOLING_QUEUED_FOR_TICK:7`，此后累计 4 条 `effective_tick=7` 的命令（另有 1 条 tick 5），而时钟停在 tick 5。

**首次偏离合理策略的可观测事件**：决策 3 的 `READ_ALREADY_USED`。之后决策 4/6/7 连续三次重复 `adjust_loads [1,1,2]`，观察变化从第二次起就是 `{}`，说明模型没有把“自由动作重复提交不产生新信息”纳入决策。
**失败链**：同 tick 重复读温 → 排队的冷却向量被后续覆盖（`pending_cooling_commands` 里同 `effective_tick` 的条目越堆越多）→ 反复被 `VALVE_BUDGET_EXCEEDED` 拒绝 → 在 tick 3–5 用零时长动作重排阀门 → 30 个决策耗尽，tick 5 的产能 16 < 20。
**替代解释**：接口误导（队列覆盖顺序未公开，C 类）可以解释“越改越乱”，但解释不了“从决策 3 起主动浪费预算”；预算不足（D）不成立，因为 12 个 `wait` 是硬下限而 30 个决策绰绰有余。

### R1（`V8-MAP-19-R1-20261017T093406Z-d99918e7`，`failure`/`THERMAL_RUNAWAY`，23 决策，tick 4 熔断）

- 决策 1：`{"set_cooling":[2,2,0],"tool":"set_cooling"}` → `COOLING_QUEUED_FOR_TICK:2`，观察变化 `{"pending_cooling_commands":[{"effective_tick":2,"vector":{"A":2,"B":2,"C":0}}]}`。
- 决策 2：`{"tool":"wait"}` → `TICK_SETTLED`，观察变化 `{"production_points":6,"temperature_bands":{"A":"RISING","B":"WARM","C":"WARM"},"tick":1,"ticks_remaining":11}`。
- 决策 21：`{"tool":"wait"}` → `TICK_SETTLED`，观察变化 `{"active_cooling":{"A":2,"B":2,"C":0},"production_points":18,"temperature_bands":{"A":"NEAR_LIMIT","B":"NEAR_LIMIT","C":"NEAR_LIMIT"},"tick":3}`。
- 决策 23：`{"tool":"wait"}` → `THERMAL_RUNAWAY`，观察变化 `{"active_cooling":{"A":2,"B":1,"C":1},"temperature_bands":{"A":"NEAR_LIMIT","B":"NEAR_LIMIT","C":"OVERHEAT"},"terminal":true,"terminal_reason":"THERMAL_RUNAWAY","tick":4}`。

**首次偏离合理策略的可观测事件**：决策 1 的冷却向量给 C 区 0 冷却，而 C 区仍以负荷 2 运行；到决策 19（tick 2）`C` 已是 `RISING`、A/B 已是 `NEAR_LIMIT`，模型仍保持 `[2,2,2]` 负荷。
**失败链**：冷却预算 4 分给 A/B、C 得 0 → 时滞窗口内 C 每 tick +2（4→6→8）→ tick 3 成熟后 C 净 +1 到 10（等号安全）→ tick 4 的 `[2,1,1]` 只给 C 1 冷却，C 变成 11 → 熔断。
**替代解释**：这是真实的热管理错误（E+F），不是接口问题：`active_cooling` 与 bands 在决策 19/21 已经明确暴露了 C 的走向；也不是预算问题（本局只用了 23 个决策）。

### R2（`V8-MAP-19-R2-20261017T093535Z-0027009f`，`decision_budget_reached`，30 决策，停在 tick 2）

- 决策 7：`{"station":"A","tool":"read_temperature"}` → `TEMPERATURE_READ:A`，观察变化 `{"last_temperature_reading":{"delta":2,"temperature":8,"tick":1,"zone":"A"}}`。
- 决策 8：`{"tool":"wait"}` → `TICK_SETTLED`，观察变化 `{"production_points":12,"temperature_bands":{"A":"NEAR_LIMIT","B":"NEAR_LIMIT","C":"RISING"},"tick":2,"ticks_remaining":10}`。
- 决策 9：`{"set_cooling":[2,2,2],"tool":"set_cooling"}` → `VALVE_BUDGET_EXCEEDED`，观察变化 `{}`。
- 决策 16：`{"set_cooling":[0,0,2],"tool":"set_cooling"}` → `COOLING_QUEUED_FOR_TICK:4`，观察变化 `{"pending_cooling_commands":[{"effective_tick":2,"vector":{"A":2,"B":2,"C":0}},{"effective_tick":4,"vector":{"A":0,"B":0,"C":2}}]}`。
- 决策 30：`{"adjust_loads":[0,2,1],"tool":"adjust_loads"}` → `LOADS_UPDATED`，观察变化 `{}`，仍在 tick 2、产能 12。

**首次偏离合理策略的可观测事件**：决策 9 的 `VALVE_BUDGET_EXCEEDED`。决策 9–30 共 22 个决策全部是 `set_cooling`/`adjust_loads`/`read_temperature`（`set_cooling` 在 tick 2 反复用 8 条命令堆到 `effective_tick=4`），一次 `wait` 都没有。
**失败链**：tick 2 时三区已 `NEAR_LIMIT/NEAR_LIMIT/RISING`，模型试图靠“继续排队”纠偏；但队列要 tick 4 才成熟，而不 `wait` 就永远到不了 tick 4 → 30 个决策全部耗在零时长动作上。
**替代解释**：如果只看终止码，这局像 D 类（预算/horizon），但它其实在 tick 2 就停住了：决策 9–30 没有任何一次推进时钟。首因是动作经济/规划（E），次因是队列语义未公开（C）。

**重复证据有限**：三局都从同一初态开始，R0 与 R2 的失败链高度相似（重复排队 → 预算耗尽），R1 是唯一真正打到热熔断的局。n=3 只能说明这个初始状态下的三种走法，不能区分个体差异与固定陷阱。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | E 策略规划错误（动作经济：把 11 个决策花在零时长动作上，tick 5 停在产能 16） | C schema/接口误导（同 `effective_tick` 队列覆盖顺序未公开，pending 越堆越多） | 高 | 决策 3/14/19/30；`final_observation.tick=5` |
| R1 | E 策略规划错误（延迟窗口内不降载，且冷却向量给 C 0） | F 资源管理错误（4 点冷却预算分配 2/2/0，漏掉正在升温的 C） | 高 | 决策 1/19/21/23；复算温度 `4→6→8→10→11` |
| R2 | E 策略规划错误（tick 2 后 22 个决策零推进） | C schema/接口误导（反复 requeue 同一 `effective_tick`） | 高 | 决策 8/9/16/30；`final_observation.tick=2` |

## 9. 标签

- `MEASUREMENT_VALID`：主指标区分策略（area 0 / 22 / 15，osc 0 / 2），三种失败码与复算一致，随机 0/20、启发式 15 决策成功。
- `METRIC_DEFECT`：① R0/R2 属预算截尾，但 area 被标 `valid` 而非 `censored`，违反指标卡截尾规则；② area 声明分母为“有效 tick 数”却返回未归一化的和；③ `coolant_exhausted` 的原因码不可达，恒 0 无判别力；④ `forecast_next` 的错误无任何公开出口与指标。
- `CONSTRUCT_BYPASS`（仅预测子机制）：`forecast_next` 不是成功条件、不是指标、三局零使用；消融证明“延迟无感”的固定向量仍能成功（area 22），时滞只被主指标惩罚。

## 10. 最小可证伪修复（无证据不修改）

**候选 A（推荐，公开信息，不改规则）**：在 goal/词表中补齐四条公开语义——冷却总预算 4、每区 0–2、`forecast_next` 的误差不会回传、同一 `effective_tick` 上最后一条入队向量生效且不可取消。
- 证据与根因：R0 决策 14/30、R1 决策 20、R2 决策 16 的重复排队；`map19.py::_mature` 按入队顺序覆盖（代码事实），但 Observation 只列全部 pending（未公开）。
- 预期变化：R0/R2 式的“盲改队列”可被公开推理替代；能力构念不变（仍是延迟热控）。
- 反例与回归：若公开后模型仍烧预算，说明 E 类为主导，不能归因于信息不足；Oracle 与启发式必须保持成功，随机仍应失败。

**候选 B（接口，规则对齐 V4，需 spec）**：按 `worlds/v4/MAP-19/map_spec.yaml` 的 `frequency: at_most_one_full_vector_per_decision_tick` 限制每 tick 只接受一条 `set_cooling`，第二条返回明确拒绝码，或增加“取消 pending”动作。
- 证据与根因：R2 在 tick 2 用 8 条 `set_cooling` 堆满 `effective_tick=4`；V4 规格与 V8 实现不一致（A 类规则差异），直接放大了 C 类误导。
- 预期变化：队列状态可预测，动作经济失败更容易被识别为策略问题。
- 反例与回归：规则改动使 V8 Trace 不可直接回放，需新 `rule_hash`；Oracle 每 tick 只用一条向量，不受影响。

**候选 C（指标，不改环境）**：① 对 `decision_budget_reached` 局的数值型主指标套用声明的 `censored` 口径；② 把 area 改为 `{numerator: Σmax(0,T-8), denominator: 已结算区·tick}` 或明确标注为未归一化；③ 恢复 V4 的 `mean_absolute_one_tick_prediction_error`，或从动作表中删除 `forecast_next`。
- 预期变化：跨局可比；预测子构念要么可测要么不再伪装成可测。
- 反例与回归：分母口径改变会改变历史数值，旧值只能进 `runs/v9/rescore/` 只读保留，不得覆盖 V8。

**若以上都不做**：保持只读，但 MAP-19 只能宣称“测量了静态热控 + 延迟惩罚”，不能宣称“测量了前馈预测”。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-19.json`：

| 策略 | 成功 | 决策 | 终止码 | area | osc | overheat |
|---|---|---|---|---|---|---|
| Oracle `early_cooling` | 是 | 27 | `PRODUCTION_TARGET_MET` | 22 | 0 | 0 |
| Oracle `exact_production_boundary` | 是 | 27 | `PRODUCTION_TARGET_MET` | 18 | 1 | 0 |
| `legal_random`（20 seed） | 0/20 | 6–30 | 19×`THERMAL_RUNAWAY`、1×预算 | — | — | — |
| `public_heuristic` | 是 | **15** | `PRODUCTION_TARGET_MET` | **0** | 0 | 0 |
| 消融 `no_lag_load_curtailment` | 是 | 14 | `PRODUCTION_TARGET_MET` | **22** | 0 | 0 |

注：Oracle 两行的 area/osc 来自同图 fixture 的期望值（`map19.py::FIXTURES` 的 `early_cooling_area_and_production`=22/0、`production_exactly_twenty_succeeds`=18/1），`runs/v9/baselines/MAP-19.json` 只记录 Oracle 的动作数与成功与否；启发式/消融两行是本轮 `run_policy` 直接产出的 judge 指标。

**独立复算（不复用 `map19.metrics()`，按 `settled_states` 与 `deltas` 另写公式）**：

| 局 | 我的 area | judge area | 我的 osc | judge osc | 我的 overheat | judge overheat |
|---|---|---|---|---|---|---|
| R0 | 3 | 3 | 2 | 2 | 0 | 0 |
| R1 | 15 | 15 | 0 | 0 | 1 | 1 |
| R2 | 3 | 3 | 0 | 0 | 0 | 0 |
| 启发式 | 0 | 0 | 0 | 0 | 0 | 0 |
| 消融 | 22 | 22 | 0 | 0 | 0 | 0 |

手算旁证：消融的结算温度序列是 A=`8` 后连续 11 个 tick 为 `10`、B=`7`、C=`6`，`Σmax(0,T-8) = 0 + 11×2 = 22`，与 judge 完全一致；启发式序列是 A=8、B=7、C=6 后净变化 0，故 area=0、osc=0。R1 的 `4→6→8→10→11` 给出 `0+0+3+5+7=15`，与 judge 一致。

**判别力**：主指标能区分 Oracle(22) / 启发式(0) / 消融(22) / 失败局(15)；`oscillation_count` 能区分 R0(2) 与其余(0)；`coolant_exhausted` 无判别力（恒 0）。

## 12. V9 状态

`NEEDS_REDESIGN`，优先级 **P1**。

理由：热控与 2 tick 时滞本身是可测、可解、可区分的（启发式 15 决策、area 0；随机 0/20），但构念里承诺的“预测”通道 `forecast_next` 既无公开反馈也无指标，且截尾局的 area 被错误标成 `valid`；不修这两处，MAP-19 只能算“热控图”，不能算“延迟预测图”。
