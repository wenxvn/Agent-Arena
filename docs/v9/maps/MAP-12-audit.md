# MAP-12 逐图审计：极夜三十天

> 本文件由 V9 Batch 1 依据 Trace、证据包与源码重新推导；不复制 `docs/v8` 结论，不声称人工审核。状态待用户确认。

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-12 极夜三十天 / polar / 困难 |
| condition | `default` |
| `rule_hash` | `ec0b473f08d1aa5f2ce6e7288b7877ab07ba66fe8123c772e91f69f216d76bba` |
| `scenario_hash` | `5d942a953707ad85e978b4c36a7364ed6d1e6f326c4cd25f79977c4eefe702be` |
| 决策预算 | **60**（V8 唯一登记过的预算例外；不是 46） |
| V8 三局 | 0/3 成功；`RESEARCH_TARGET_MISSED` ×3；决策 60 / 60 / 60 |

三局属于 `039e25ce6503871ceb31184e85c9265451ee7486` 的预算补跑批次；其余 hash 与冻结清单一致（`docs/v9/baseline-audit.md` §3）。
数据来源：`runs/v9/evidence/MAP-12.json`、`docs/v9/run-index.csv`、`runs/v9/baselines/MAP-12.json`、`docs/v8/maps/MAP-12-final.md`、`worlds/v4/MAP-12/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}`、`src/agent_arena/worlds/scenario_v8/maps/map12.py`、`src/agent_arena/v8/prompts.py`、`src/agent_arena/v9/policies/world_polar.py`。

## 1. 能力构念

**一句话**：把 30 天、每天 2 个劳动槽当成一份有限日历，在“每天供暖/口粮、温室连续供能、零件两段转运、4 次控制器磨损维修、4 轮三日研究串”之间排程，保证第 30 天累计 12 研究积分且供暖/口粮不连续两天中断。

- 成功行为：`day=30` 时 `research_points≥12`，且没有连续 2 天供暖或口粮欠供（`SURVIVED_AND_RESEARCHED`）。
- 明确反例：全程 `wait`（0 分，`thirty_days_passive_research_target_missed`）；只研究不维修（第 7 天后控制器永久离线，最多 6 分，本批消融实测）；把研究日打散（永远凑不满连续 3 日）。
- 递进位置：polar 困难图，也是三图中唯一**没有空间移动、没有随机**、纯日历与库存排程的图；难度来自约束数量与跨期耦合，不是来自不确定性。

## 2. 机制与因果链

起始状态（day 1）：`fuel_E=40`、`food.H=30`、`parts.S=8`、`heater_on=true`、`controller_online=true`、`greenhouse_powered=false`、`crop_planted=false`、`research_points=0`、每日 2 槽。
必需观察：`research_points`/`research_streak`（研究是否在累计）、`controller_online`/`maintenance_today`（当天能否研究/是否需要维修）、`node_inventories`（零件在 S/G/E 的位置）、`labor_slots_remaining`。
关键决策：把“研究”放在在线日的槽位；在磨损日之前把 2 个零件经 `S→G→E` 运到能源站；磨损日开槽 `repair_controller`。
立即后果：连续 3 个在线研究日 → `+3` 分并清零 streak；每次日结算扣 1 燃料供暖、扣 1 份 H 口粮；进入第 7/14/21/28 天时控制器强制离线，研究、温室、发电全部被阻断，直到维修（消耗 E 处 2 零件）。
终局：第 30 天日结算，12 分则成功，否则 `RESEARCH_TARGET_MISSED`。

- 可绕过核心机制的动作：**部分可以**。食物/温室链是可绕过的：H 初始 30 份口粮正好覆盖 30 天，`worlds/v4/MAP-12/evidence_or_rules.yaml` 第 16 行明确写“Harvest delivery is not an additional universal victory predicate”。因此温室、种植、食品转运都可以完全不做。但**维修链不可绕过**：控制器从第 7 天起永久离线，不维修就再也无法研究（本批消融实测只有 6 分）。
- 机制触发：三局都触发了研究、温室、维修、转运四类动作；其中维修尝试 14/11/12 次全部 `PARTS_SHORTAGE`，转运尝试 23/21/18 次全部 `INVALID_EDGE`；三局结束时 `parts.S` 仍是 8，**没有任何一个零件离开仓库**。
- 触发所需最小动作数：失败 0 步（全程等待即可“活着失败”）；成功最少 **24 个有效动作**（12 次研究 + 4 次维修 + 8 次两段转运），其余 36 槽可以空转。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `day` / `labor_slots_remaining` / `labor_actions_used` | 是（Observation） | 每天 | 足以做日粒度排程 |
| `fuel_E` / `heater_on` / `controller_online` | 是 | 每天 | 足以判断供暖与控制器状态 |
| `greenhouse_powered` / `greenhouse_powered_streak` / `greenhouse_crop_planted` | 是 | 每天 | 足以做温室链 |
| `research_points` / `research_streak` | 是 | 每天 | 足以观察“3 日一周期”的**结果**，但需连续研究才能观察到 |
| `node_inventories`（food/parts 在 H/E/G/S/L 的数量） | 是 | 每天 | 足以知道货在哪、有多少 |
| `maintenance_today` | 是 | **仅当天** | 只能事后反应，不能提前知道 7/14/21/28 |
| `goal`（活 30 天 + 12 分 + 不连续欠供） | 是 | tick 0 | 足以定目标，不含周期与磨损规则 |
| 图边 `H_E/E_G/G_S/S_L/H_S/G_L` 与邻接关系 | **否**：Observation 无 `visible_edges`/`local_neighbors` | — | **不能**构造合法 `transfer` |
| 研究周期 = 连续 3 日、每次 +3 | **否** | 只能从 `research_points` 跳变反推 | 不能事前排程 |
| 磨损日固定为 7/14/21/28 | **否** | 只有当天 `maintenance_today=true` 且控制器已离线 | 不能提前备件 |
| `repair_controller` 需 E 处 2 零件、每次耗 2 | **否** | 只有 `PARTS_SHORTAGE` 反馈 | 不能事前计算总需求 8 |
| `transfer` 每次最多 2 零件 / 5 食物、必须匹配无向边 | **否** | 只有 `INVALID_TRANSFER`/`INVALID_EDGE` 反馈 | 不能事前计算 |
| 温室 3 日供能 +5 食物；每次供暖/温室各 1 燃料 | **否** | 只能从结算反推 | 不必要（食物可自给） |
| `judge_state`（`snapshots`、`breach_days`、`research_points` 内部值等） | 否 | — | 否 |

**关键接口缺陷（事实）**：`runs/v9/evidence/MAP-12.json` 的 `action_contract` 明写
`"edge_id": string，当前 Observation 中 visible_edges/local_neighbors 露出的边标识`，
但该图初始 Observation 的字段只有 `day, node_inventories, fuel_E, heater_on, controller_online, greenhouse_*, research_*, consecutive_*, labor_*, maintenance_today, goal`——**没有 `visible_edges`，也没有 `local_neighbors`**。系统 prompt 因此指向了一个不存在的字段。`_VOCABULARY["MAP-12"]`（`prompts.py` 第 193–198 行）只写 `transfer(commodity, from_node, to_node, edge_id, quantity)`，同样不列边 id。这与 MAP-10/11（两者都公开 `visible_edges`）不同，是本图独有的信息缺口。

## 4. 可解性与可观察性

- Oracle：`research_priority` 与 `safety_buffer`，展平后各 **60 动作**。
- **`python -m agent_arena.v9.baseline_run` 当前报告 Oracle 2/2**（该入口使用模块内 `ORACLE_CASES`，各 60 动作、12 分；`runs/v9/baselines/MAP-12.json` 的 `oracle[].actions=60`）。
- 但 V8 公共重放器 `scenario_v8/oracle.py::replay_all` 仍为 **0/2**：`worlds/v4/MAP-12/oracle_trace.jsonl` 是“每天一行、动作用 `actions` 数组”，而 `replay_group` 只读单数 `row["action"]`，30 行全部报 `step N has no action object`，`actions=0`、状态停在 `running`。这是 Oracle 文件与 V8 重放器之间的格式不兼容（证据层缺陷），不影响本图的规则与 `baseline_run` 结论，但意味着**公开 jsonl 不能独立复算**。
- 直接重放模块内置的 `ORACLE_CASES`（同一批动作，已展平）**2/2 成功**：`research_priority` 60 动作、12 分、`fuel_consumed=33`、`minimum_safety_margin=4`、`plan_breach_days=0`；`safety_buffer` 60 动作、12 分、`fuel_consumed=36`、`minimum_safety_margin=3`、`plan_breach_days=0`。
- **30 天 × 劳动槽的可行规划（复算）**：总槽 60。必需工作量 = 12 次研究（4 轮 × 3 个连续在线日）+ 4 次维修 + 8 次零件转运（4 次 `S→G`、4 次 `G→E`，每次 2 件）= **24 槽**，余 36 槽。食物与温室 0 槽（H 的 30 份正好 30 天）；供暖 0 槽（`heater_on` 常开，每天自动扣 1 燃料）。因此**预算 60 在槽位数量上足够**。
- 实际成功日历（公开启发式，60 决策）：第 4 天 3 分、第 7 天 6 分、第 10 天 9 分、第 13 天 12 分；维修发生在第 7/14/21/28 天；结束时 `fuel_E=10`、`parts.E=0`、`plan_breach_days=0`。
- **仅凭公开信息是否存在可执行策略**：日历层面存在；但执行层面被 `transfer` 的 `edge_id` 阻断。策略作者使用的 `G_S`、`E_G` 两个边 id 来自源码，不是 Observation 能读到的事实。若严格要求“只看 prompt + Observation”，模型无法知道这 6 条边中的任意一条 id，而维修又必须依赖转运，故标 `INTERFACE_BLOCKED`。
- 是否存在“必死”：**不存在**。只要边 id 可用，公开启发式 60/60 成功；这是接口问题，不是规则或预算问题。

## 5. 预算可行性

| 策略 | 决策数 | 终局 | 关键指标 |
|---|---|---|---|
| Oracle `research_priority`（内置用例） | 60 | `SURVIVED_AND_RESEARCHED` | fuel 33；margin 4；breach 0 |
| Oracle `safety_buffer`（内置用例） | 60 | `SURVIVED_AND_RESEARCHED` | fuel 36；margin 3；breach 0 |
| 公开启发式 | 60 | `SURVIVED_AND_RESEARCHED` | fuel 30；margin -1；breach 0；points 12 |
| 消融 `no_key_mechanism`（不维修/不转运） | 60 | `RESEARCH_TARGET_MISSED` | fuel 30；margin -1；breach 4；points 6 |
| V8 MiMo R0 | 60 | `RESEARCH_TARGET_MISSED` | fuel 33；margin -1；breach 25；points 0 |
| V8 MiMo R1/R2 | 60 / 60 | `RESEARCH_TARGET_MISSED` | fuel 35；margin -1；breach 23/25；points 3/3 |

`legal_random` 20 seed：0 成功，20/20 全部在第 60 决策 `RESEARCH_TARGET_MISSED`；平均 60.0 决策；schema 非法 0；被拒动作 313（该图动作形状唯一，跨进程稳定）。

**判定：不是预算不足。** 60 决策 = 30 天 × 2 槽，成功策略用满 60 且只用了 24 个有效动作。三局也都用满 60，说明不是“没来得及”，而是“有效动作没落在研究/维修/转运上”。

## 6. 指标

| 指标 | 计算事件 | 分母 | 三局取值 | 缺失/截尾 |
|---|---|---|---|---|
| `map12.survival_days` | 日结算时供暖与口粮均正常的天数 | 30 | 1.0/1.0/1.0 | 无 N/A |
| `map12.minimum_safety_margin` | `min_t(fuel_E−1, food_H−1)` | 每日快照 | -1/-1/-1 | 无 N/A |
| `map12.heating_outage_days` | 供暖关闭或无燃料的天数 | 30 | 0/0/0 | 无 N/A |
| `map12.plan_breach_days` | 被拒动作或磨损日未修复的天数 | 30 | 25/23/25 | 无 N/A |
| `map12.fuel_consumed` | `40 − fuel_E` | episode | 33/35/35 | 无 N/A |

- 未通关仍有意义的连续诊断指标：`plan_breach_days`（25/23 vs 0）与 `fuel_consumed`（33/35 vs 30）；两者都是 diagnostic，不是 primary。
- **`survival_days=1.0` 无法区分成功与失败**：本批成功启发式、失败消融、三局 MiMo 都是 30/30。原因是“活着”在本图很容易（30 份口粮 + 40 燃料正好够 30 天），真正的胜负手是研究积分。
- **`minimum_safety_margin=-1` 也不是失败信号**：它只表示第 30 天结束时 H 的口粮从 1 扣到 0（`fuel_E−1` 仍为正）；成功启发式同样是 -1。把 `-1` 读成“资源不安全”会误判。
- **METRIC_DEFECT（事实）**：登记的五条指标里没有任何一条投影 `research_points`，而 `research_points` 正是本图唯一的胜负判据（`day=30` 时 ≥12）。因此“消融 60 步失败（6 分）”与“启发式 60 步成功（12 分）”在主指标上完全同分（survival 1.0、margin -1、outage 0、fuel 30），只能靠 diagnostic `plan_breach_days` 4 vs 0 间接看出差异。这是 `LOW_DISCRIMINATION` 的直接来源。
- 三局无 `not_applicable` / `censored`，五条指标全部 `valid`。

## 7. 三次轨迹归因

### R0（`V8-MAP-12-R0-20261017T113334Z-e36d02ca`，60 决策，0 分）

- 决策 1 `{"tool":"start_greenhouse_power"}` → `GREENHOUSE_POWERED`；观察变化 `{"greenhouse_powered":true,"labor_slots_remaining":1}`。
- 决策 2 `{"tool":"plant_batch"}` → `BATCH_PLANTED`；观察变化 `{"day":2,"fuel_E":38,"greenhouse_crop_planted":true,"labor_slots_remaining":2}`。
- 决策 4 `{"tool":"repair_controller"}` → `PARTS_SHORTAGE`；观察变化 `{"day":3,"fuel_E":36,"labor_slots_remaining":2,"research_streak":1}`。
- 决策 5 `{"commodity":"parts","edge_id":"S-H","from_node":"S","quantity":4,"to_node":"H","tool":"transfer"}` → `INVALID_EDGE`；观察变化 `{"labor_slots_remaining":1}`。
- 决策 10 `{"tool":"research"}` → `RESEARCH_ALREADY_LOGGED_TODAY`；观察变化 `{"day":6,"fuel_E":32,"labor_slots_remaining":2,"research_streak":2}`。
- 决策 60 `{"tool":"wait"}` → `IDLE_SLOT`；观察变化 `{"fuel_E":7,"labor_actions_used":2,"labor_slots_remaining":0,"node_inventories":{"food":{"E":0,"G":5,"H":0,"L":0,"S":0},"parts":{"E":0,"G":0,"H":0,"L":0,"S":8}},"terminal":true,"terminal_reason":"RESEARCH_TARGET_MISSED"}`。
- 首次偏离：决策 4 在 `parts.E=0` 时尝试维修（公开 Observation 已显示 E 无零件、S 有 8），既没有先转运，也没有把两个槽都用于研究；决策 5 起共 23 次转运全部使用不存在的边 id。
- 失败链：维修空转 + 转运 100% 被拒 → 第 7 天控制器离线且无零件 → 之后每 7 天重复 → 研究日只有 2/4/5 三天且不连续 → 0 分。
- 替代解释：预算（否，60/60）；规则（否，内置 Oracle 通过）；接口（是，边 id 不可见）；策略（是，研究日历不连续）。

### R1（`V8-MAP-12-R1-20261017T114002Z-8090aae0`，60 决策，3 分）

- 决策 3 `{"tool":"research"}` → `RESEARCH_LOGGED`；决策 5 再研究；决策 7 再研究。
- 决策 8 `{"tool":"research"}` → `RESEARCH_ALREADY_LOGGED_TODAY`；观察变化 `{"day":5,"fuel_E":33,"labor_slots_remaining":2,"research_points":3,"research_streak":0}`（第 2–4 天连续，拿到 3 分）。
- 决策 12 `{"tool":"wait"}` → `IDLE_SLOT`；观察变化 `{"controller_online":false,"day":7,"fuel_E":29,"greenhouse_powered":false,"labor_slots_remaining":2}`。
- 决策 13 `{"tool":"repair_controller"}` → `PARTS_SHORTAGE`；观察变化 `{"labor_slots_remaining":1}`。
- 决策 57 `{"tool":"research"}` → `CONTROLLER_OFFLINE`；观察变化 `{"labor_slots_remaining":1}`。
- 首次偏离：决策 8 在同一天重复研究，浪费一个槽；更关键的是从第 5 天起再没有连续研究，且第 7 天离线时 E 处没有零件。
- 失败链：3 分 → 第 7 天永久离线 → 其后 11 次维修全部 `PARTS_SHORTAGE`、21 次转运全部 `INVALID_EDGE` → 终局 3 分。

### R2（`V8-MAP-12-R2-20261017T114556Z-d7fef335`，60 决策，3 分）

- 决策 3 `{"tool":"research"}` → `RESEARCH_LOGGED`；决策 6 `{"tool":"research"}` → `RESEARCH_LOGGED`（该日结算后公开 `research_streak` 为 2）；决策 7 `{"tool":"research"}` → `RESEARCH_LOGGED`。
- 决策 8 `{"tool":"research"}` → `RESEARCH_ALREADY_LOGGED_TODAY`；观察变化 `{"day":5,"fuel_E":33,"labor_slots_remaining":2,"research_points":3,"research_streak":0}`。
- 决策 12 `{"commodity":"food","edge_id":"H-S","from_node":"H","quantity":5,"to_node":"S","tool":"transfer"}` → `INVALID_EDGE`；观察变化 `{"controller_online":false,"day":7,"fuel_E":29,"greenhouse_powered":false,"labor_slots_remaining":2,"research_streak":1}`。
- 决策 27 `{"tool":"research"}` → `CONTROLLER_OFFLINE`；观察变化 `{"labor_slots_remaining":1}`。
- 决策 60 `{"commodity":"parts","edge_id":"S-H","from_node":"S","quantity":4,"to_node":"H","tool":"transfer"}` → `INVALID_EDGE`；观察变化 `{"fuel_E":5,"labor_actions_used":2,"labor_slots_remaining":0,"node_inventories":{"food":{"E":0,"G":5,"H":0,"L":0,"S":0},"parts":{"E":0,"G":0,"H":0,"L":0,"S":8}},"terminal":true,"terminal_reason":"RESEARCH_TARGET_MISSED"}`。
- 首次偏离：决策 12 把食物从 H 运往 S（在本图里 H 是口粮唯一来源，30 份刚好 30 天），并第一次撞上不存在的边 id；本局 18 次转运全部失败。
- 失败链：与 R1 相同，只是把槽位更多花在 `set_heating`、`start_greenhouse_power` 与重复维修上；终局 3 分。

**重复证据有限**：三局是同一 seed 的重复运行，不是独立 seed；研究积分为 0/3/3，说明个体差异存在，但失败结构完全相同（第 7 天后控制器离线、零件从未离开 S）。n=3 不能区分“模型策略差异”与“固定接口陷阱”。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | C 接口缺陷（`transfer` 的 `edge_id` 不可见，23/23 `INVALID_EDGE`）→ 维修链断裂 | E 策略（研究日不连续、维修前不备件）；B 公开信息不足（3 日周期、磨损日未公开） | C 高 / E 中 / B 中 | 决策 4–5、10；`prompt` 契约；最终 `parts.S=8` |
| R1 | C（21/21 `INVALID_EDGE`） | E（第 5 天后停止连续研究）；B（周期未公开） | C 高 / E 高 | 决策 8、12–13、57 |
| R2 | C（18/18 `INVALID_EDGE`） | E（把槽位用于非研究动作）；B | C 高 / E 高 | 决策 12、27、60 |

排除：D（预算 60，成功策略也正好 60）；A（内置 Oracle 2/2 通过，规则自洽）；H（0 非法动作、0 provider 错误）；F（燃料/口粮从未短缺）。

## 9. 标签

- `INTERFACE_BLOCKED`：`transfer` 的 `edge_id` 在公开面不存在（Observation 无 `visible_edges`，词表不列边 id，契约却声称它来自 `visible_edges/local_neighbors`）。62/62 次转运被拒，零件始终停在 S=8；维修必需零件，因而是硬阻断。
- `METRIC_DEFECT`：五条登记指标都不含 `research_points`；成功与失败在主指标上同分（survival 1.0、margin -1、outage 0、fuel 30），只有 diagnostic 有差异。
- 不选 `BUDGET_BLOCKED`（60 = 30×2，成功策略用满 60）；不选 `RULE_DEFECT`（内置 Oracle 通过）；不选 `CONSTRUCT_BYPASS`（食物链可绕过，但研究+维修链不可绕过，核心构念仍要求排程）。

## 10. 最小可证伪修复（无证据不修改）

- 旧规则/旧公开信息：规则不改；公开面缺图边，指标面缺研究分，Oracle 文件格式与重放器不兼容。
- 证据与根因：三局共 62 次 `transfer` 全部 `INVALID_EDGE`，最终 `parts.S=8`；prompt 契约指向不存在的 `visible_edges`；`replay_all` 报 `step 1 has no action object`。
- 候选 A（优先，补公开信息，不改规则）：在 `_VOCABULARY["MAP-12"]` 增加一行公开图：“无向边：`H_E, E_G, G_S, S_L, H_S, G_L`；零件每次最多转 2，食物最多 5；维修需 E 处 2 零件。”预期：模型能构造合法转运并排程维修；失败将归因于日历规划。反例/回归：R0 有 14 次维修空转、R1 有 11 次，说明即使边可用，模型仍可能不备件；若成功率仍为 0，则说明是策略而非接口问题，本图成为真正的困难图。
- 候选 B（结构层）：把 `visible_edges` 加入 `PUBLIC_FIELDS` 与 `_public()`，让边成为 Observation 的一部分。改动 `scenario_hash` 与公开字段白名单，比 A 重；建议先做 A。
- 候选 C（指标层）：新增 `map12.research_points`（或 `research_points_completion = research_points/12`）为 primary/continuous 指标，直接从已有的 `judge_state["research_points"]` 投影，不新增规则、不伪造分数。预期：成功/失败/消融可区分；风险：需要更新 metric schema hash 与 5 个 fixture 的期望值。
- 候选 D（证据层）：给 `replay_all` 增加 MAP-12 的“每日 `actions` 数组”适配，或把 `oracle_trace.jsonl` 展平为逐步动作；不改规则，只让公开 Oracle 可复算。
- 不建议：增加天数、槽位、燃料或口粮（会把策略失败洗成资源不足）；不建议把 `RESEARCH_TARGET_MISSED` 改成软失败。

## 11. 基线与独立复算

`runs/v9/baselines/MAP-12.json`：

| 类别 | 结果 |
|---|---|
| Oracle（`baseline_run`，模块内 `ORACLE_CASES`） | **2/2 成功**，各 60 动作 |
| Oracle（V8 `replay_all`，公开 jsonl） | 0/2，`actions=0`，`running`；原因是文件格式（见 §4） |
| `legal_random`（20 seed） | 0 成功；20/20 `RESEARCH_TARGET_MISSED`；平均 60.0 决策；schema 非法 0；被拒 313 |
| `public_heuristic` | 成功，60 决策；points 12；breach 0；fuel 30 |
| 消融 `no_key_mechanism` | 失败，60 决策；points 6；breach 4；fuel 30 |

独立复算（不使用 `Map12Environment.metrics()`，只读 `actions[].observation_after` 的公开字段）：
- 每日快照取当天最后一条公开 Observation：`minimum_safety_margin = min(min(fuel_E−1, food.H−1)) = -1`；
- `survival_days = 30/30`（每天 `consecutive_heat_shortage_days=0` 且 `consecutive_food_shortage_days=0`）；
- `fuel_consumed = 40 − fuel_E(终局) = 30`；
- `research_points(终局) = 12`（启发式）/ `6`（消融）。
与 extractor 的 `fuel_consumed=30`、`minimum_safety_margin=-1`、`survival_days=1.0` 逐项一致；**研究分只能从公开 Observation 读到，指标层不投影**——这正是指标缺陷的可复算证据。

`plan_breach_days` 独立核对：用 `runs/v9/evidence/MAP-12.json` 的逐步 `result` 自行计数——日号按 `(i−1)//2+1` 还原，凡出现 `PARTS_SHORTAGE`/`INVALID_EDGE`/`CONTROLLER_OFFLINE`/`RESEARCH_ALREADY_LOGGED_TODAY` 等被拒结果，或 7/14/21/28 当天没有成功维修，即记 1 天。三局分别得到 **25 / 23 / 25**，与 `judge_metrics.map12.plan_breach_days` 完全一致。R0 的违约日集合为 `[2,3,4,5,7,8,9,10,11,12,13,14,16,17,18,20,21,22,23,24,25,26,27,28,30]`，即 30 天里有 25 天至少一个动作被拒或磨损日未修复。

## 12. V9 状态

`BLOCKED`（P0）。理由：本图宣称测“30 天跨期排程”，但必需的零件转运在公开面上没有边 id（62/62 被拒），维修链因此不可执行；同时指标层没有研究分，成功与失败在主指标上不可区分。两处都是接口/指标问题，不是预算或规则问题。优先级 P0：不修则本图的 0/3 不能被解释为能力结论。
