# MAP-09 审计：深海连锁故障（abyss / 困难）

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-09 / abyss / 困难 |
| condition | `default` |
| `rule_hash` | `603948debd2faa2a785e625d14b9a79f5e73676691d5743366c7866652af68d5` |
| `scenario_hash` | `74f17503668585f1d243dcf9a3d83722d8eeb4054db4745696427aa4f8f76ccb` |
| `prompt_hash` | `95021c0f25c32bb074fc635fc46c879a4982d95b0c54c7ea5a74448509859614` |
| 决策预算 | 46（`BUDGETS["困难"]`）；环境 `step_limit=160` |
| V8 三局 | 0/3 成功；R0/R1/R2 均 `failure` / `SHORT_CIRCUIT`，决策 2 / 2 / 2，非法 schema 0 |
| 费用（正式行） | 0.001313 / 0.00024876 / 0.00079924 CNY |
| 证据包 | `runs/v9/evidence/MAP-09.json` |
| Trace 索引 | `docs/v9/run-index.csv` 第 26–28 行（trace sha256 `c582349d…`、`24731a1d…`、`a4e37d03…`） |
| 规则资料 | `docs/v8/maps/MAP-09-final.md`、`worlds/v4/MAP-09/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}` |
| 源码 | `src/agent_arena/worlds/scenario_v8/maps/map09.py` |
| 公开词表 | `src/agent_arena/v8/prompts.py::_VOCABULARY["MAP-09"]` |
| 基线 | `runs/v9/baselines/MAP-09.json` |

## 1. 能力构念

这张图想测的是：**Agent 能否在一条硬性水力时限下，把封舱、发电、供氧、通信四条链排成一个可行次序，并在固定电量里同时支付抽水与发报**。

- 成功行为：先阻断 P→E 漏水，再恢复外部发电（`water_E<=4` 时才能成功）、重启供氧、补氧，最后在 C 发出连续 2 tick 的求救包。
- 明确反例：连续两个 tick 都不封舱（例如先走到 P 抽水、或连读两次仪表）；或封舱后不恢复供氧就发报（`OXYGEN_NOT_STABLE`）；或多抽一次水导致剩余电量 <3（`INSUFFICIENT_TRANSMIT_POWER`）。
- 本图在简单/中等/困难递进中的位置（只写本图）：它是 abyss 唯一带**不可逆硬时限**的图——MAP-07 没有时间压力，MAP-08 的时间压力是软的（水位上限 7）；本图在第 2 个 tick 就可能终局。

## 2. 机制与因果链

起始状态（`runs/v9/evidence/MAP-09.json` 初始 Observation 原文）：

```json
"battery": 5, "bulkhead_state": "open", "generator_online": false,
"location": "E", "oxygen_reserve": 12, "oxygen_stable_ticks": 0,
"oxygen_support_on": false, "p_sacrificed": false, "packet_complete": false,
"tick": 0, "visible_edges": ["C_E", "E_C_EMERGENCY", "E_P"],
"water_E": 3, "water_P": 5,
"goal": "封住漏水、恢复发电主线与供氧，并在 C 发出完整两 tick 求救包。"
```

因果链：

1. **起始**：`water_E=3`、`water_P=5`、舱壁 open、电量 5、氧 12。
2. **必需观察**：`water_P/water_E/bulkhead_state`。每个已结算 tick（任何成本 ≥1 的动作）在 `_after_tick` 里执行：若舱壁未关且 `water_P>0`，则 `water_P -= 1`、`water_E += 1`（`map09.py:267-269`）。
3. **关键决策**：在 `water_E` 越过 4 之前关闭 `bulkhead_E_P`（`map09.py:176-188`）。封舱在当前动作的 tick 结算前生效，所以关舱当 tick 不再进水。
4. **立即后果**：`water_E > 4` → 立即 `_fail("SHORT_CIRCUIT")`（`map09.py:278-281`），与电量、供氧、位置无关。初始 E=3，所以第 1 个 tick 后 E=4（安全），第 2 个 tick 后 E=5（死亡）。
5. **终局**：`generator_online && oxygen_support_on && packet_complete` → `DISTRESS_PACKET_SENT`；发报动作本身占 2 tick，且要求 `oxygen_stable_ticks>=2` 与电量 ≥3。

- **可绕过核心机制的动作**：
  1. **完全跳过抽水**。终局条件不包含 `water_P`，也不包含“P 未被淹”。封舱后 P 的水不再增加，`water_P=5` 不影响任何判定。`isolate(preserve)` → `restore_power_line` → `C` → `O` → 重启 → 补氧 → `C` → 发报，共 **8 个动作**即可成功（见 §11 的 `skip_pump` 消融）。设计文档所说的“电量 5 = 两次抽水 2 + 发报 3”的精确张力因此不是必要条件；保留路线只因多抽两次而多花 2 个 tick 与 2 点电。
  2. **弃舱路线**：`sacrifice` 直接让 P 不可达，Oracle 8 步成功（设计上允许，不是缺陷）。
- **机制是否在三条真实轨迹中实际触发**：**触发且立即终局**。三局都在决策 2 的 tick 结算时 `water_E: 4→5`，`terminal_reason: "SHORT_CIRCUIT"`；`repair_actions=0`，封舱动作从未出现。
- **触发所需的最小动作数**：致死不封舱需 2 个 tick（第 1 个任意动作 + 第 2 个未封舱动作）；成功最小 8 个动作（skip_pump），设计意图路线 12 个动作。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `water_P` / `water_E` / `bulkhead_state` | 是，Observation 字段 | 每步 | 是（能看到 3/5/open） |
| `battery` / `oxygen_*` / `packet_complete` | 是 | 每步 | 是 |
| `goal`（封漏水、恢复发电与供氧、发两 tick 包） | 是 | 初始 | 只给目标，不给顺序与时限 |
| 动作契约（inspect/interact/move/wait 字段） | 是 | 初始 | 形状足够 |
| 公开词表：`E/bulkhead_E_P 配 arguments={"mode": preserve|sacrifice}` | 是 | 初始 | **误导**：运行时要求 `target_id="bulkhead_E_P"`、`operation="isolate_compartment"`；词表把 `bulkhead_E_P` 放在“操作”位置，且完全没出现 `isolate_compartment` |
| P→E 漏水速率 | **否**。只在 `map09.py:268-269` 与 `worlds/v4/MAP-09/map_spec.yaml:30` | 不可见 | **否**：无法知道每 tick +1 |
| 短路阈值 `water_E > 4` | **否**。只在 `map09.py:66` 与 `map_spec.yaml:31` | 不可见 | **否**：初始 E=3，模型无法知道只剩 1 个 tick 余量 |
| `SHORT_CIRCUIT` 终局机制 | 只在源码/失败码列表 | 不可见 | **否** |
| 电量/抽水/发报成本（1/1/3）、氧衰减 1/tick、稳定 2 tick | **否**（只在 `map09.py` 常量） | 不可见 | 不影响首步保命，但影响后续规划 |
| `isolate_compartment` 操作名 | **否**（词表中不存在） | 不可见 | **否**：这是保命动作本身 |
| hidden `judge_state`（`safe_ticks`、`short_circuit` 等） | 否 | 不可见 | 不用于公开策略 |
| Oracle 两条路线 | 否（`worlds/v4/MAP-09/oracle_trace.jsonl`） | 不可见 | 不用于公开策略 |

**公开性结论**：本图的保命规则（速率 1、阈值 4、必须在 2 个决策内封舱）与保命动作名（`isolate_compartment`）**全部不在**公开 prompt、动作契约或词表中。唯一公开的线索是目标句里的“封住漏水”和 Observation 里的 `bulkhead_state: open`；它们能说明“应该去封”，但不能说明“还剩几个 tick”和“用哪个字符串封”。

## 4. 可解性与可观察性

### 4.1 Oracle

- 2 条用例，均成功：`preserve_and_pump` 12 步、`sacrifice_P` 8 步（`runs/v9/baselines/MAP-09.json`，`ok=true`，终态 `DISTRESS_PACKET_SENT`）。
- 手算 fixture 3 条（`map09.py::FIXTURES`）：sacrifice 路线、开舱等 2 tick 短路、未发电先开氧被拒。

### 4.2 仅凭公开信息是否存在可执行策略

**不存在可推导的可执行策略；只有“无条件先封舱”的猜测可能蒙中，而该猜测仍要求先知道 `isolate_compartment`。** 原因有两层，任一层单独就足以封死可推导性：

1. **保命动作名缺失**：唯一能封舱的调用是 `{"tool":"interact","target_id":"bulkhead_E_P","operation":"isolate_compartment","arguments":{"mode":"preserve"}}`；`isolate_compartment` 没有出现在任何公开文本中。`ShapeSampler` 的字符串只来自 Observation，20 个 seed 也从未产生该动作（§5）。
2. **时限规则缺失**：即使 Agent 猜到要封舱，它也无法从公开信息知道“第 2 个 tick 就会死”。初始 `water_E=3` 本身不携带阈值；公开目标只说“封住漏水”，没有“每 tick +1、>4 短路”。

### 4.3 特别重点：是否存在“唯一的保命首动作”？

**不存在唯一的保命首动作；存在的是“一个 1 tick 的容错窗口 + 必须在第 2 个决策内封舱”。**

离线探针（用真实 `Map09Environment` 与公开动作，逐步记录 `water_E`；不是 V8 正式局）结果如下：

| 首动作 | 第 1 tick 后 water_E | 第 2 决策 | 结果 | 说明 |
|---|---|---|---|---|
| `isolate_compartment(preserve)` | 3（封舱当 tick 生效） | 继续路线 | 成功（12 步） | 最安全，P 水保留 5，两次抽水后 P=1 |
| `inspect(water_gauges)` → 封舱 | 4 | 封舱 | 成功（13 步） | 容错窗口正好用掉 1 tick |
| `wait(ticks=1)` → 封舱 | 4 | 封舱 | 成功（13 步） | 同上 |
| `restore_power_line`（E，E=3≤4 合法） → 封舱 | 4 | 封舱 | 可存活 | 先修线再封舱也不死，后续同封舱路线 |
| 任意在 E 的非法 interact（如 `send_distress_packet`）→ 封舱 | 4 | 封舱 | 可存活 | 被拒动作仍耗 1 tick，但位置不变 |
| `inspect` 两次 → 封舱 | 4 | 第二次 inspect | **第 2 tick E=5，`SHORT_CIRCUIT`** | 三局真实轨迹就是这一行 |
| `wait(ticks=2)` 作为首动作 | 第 1 tick 内就 E=4→5 | — | **决策 1 即 `SHORT_CIRCUIT`** | 2 tick 首动作必死 |
| `move E_P` → 回 E → 封舱 | 4 | 回 E 时 E=5 | **决策 2 `SHORT_CIRCUIT`** | 首动作离开 E 必死：回程已耗掉第 2 个 tick |

因此：

- 表中“成功”指完整跑到 `DISTRESS_PACKET_SENT`（`isolate` 首动作与两次 inspect/wait 路线各跑完整局）；“可存活”指探针只跑到封舱后若干步、未终局，但已越过唯一的短路点。所有探针都调用真实 `Map09Environment.step`，不使用 `judge_state`。
- **“必须首步封舱”是伪命题**：封舱可以在决策 1 或决策 2 完成；两者都能活。真正的硬约束是“**第 2 个决策必须是在 E 执行封舱**”。
- **首动作可以不是封舱**，但必须是“1 tick 且不离开 E”的动作（inspect / wait(1) / 被拒的 interact）。任何 `move` 首动作都会因为回程多耗 1 tick 而必死。
- 如果要求“在不知道阈值的情况下做 minimax 决策”，那么**唯一理性的首动作确实是立即封舱**——因为任何延迟都在赌一个未知阈值。这一点与“唯一可存活首动作”不同，必须区分。
- 三局的错误不是“首动作选错”，而是**第 2 个决策仍然 inspect**；但这不能单列为模型策略错误，因为模型从未获得“只剩 1 tick”的公开信息。

### 4.4 标签依据

公开信息不足以合法触发保命机制（动作名缺失 + 时限缺失），且随机基线 20/20 在 1–2 决策内死亡。记 **`INTERFACE_BLOCKED`**。本图**不是** `BUDGET_BLOCKED`：预算 46，Oracle 只要 12/8，瓶颈是信息而非预算。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| Oracle 动作数 | 12（preserve+pump）/ 8（sacrifice） |
| 决策预算 | 46 |
| `legal_random` 20 seed | **0/20 成功；20/20 `SHORT_CIRCUIT`**；决策 1（4 局）或 2（16 局），平均 1.8；非法 schema 0；被拒 27 次合计。环境 seed 固定 0，变动的只是策略 RNG 种子 |
| 公开启发式 | 10 决策，`DISTRESS_PACKET_SENT`（封舱优先、P→O 直达） |
| 消融 `skip_pump` | 8 决策，`DISTRESS_PACKET_SENT` |
| 三局 MiMo | 2/2/2 决策，全部 `SHORT_CIRCUIT` |

判定：**不是“预算不够”，而是“公开信息不够 + 模型没有在 1 个 tick 内转向封舱”**。46 个决策对 8–12 步的解法绰绰有余；随机基线连一次封舱都产生不出来，说明这不是采样运气问题。

## 6. 指标

本图 5 条指标（`map09.py::metrics`）：

| 指标 | 类别 | 计算事件 | 分母 | 缺失/截尾 |
|---|---|---|---|---|
| `map09.stable_time_ratio` | primary | 满足 `water_E<=4 且 oxygen_reserve>0` 的已结算 tick 数 / 全部已结算 tick 数 | 有效 tick 数 | 0 tick → N/A；预算截尾 → CENSORED |
| `map09.fault_propagation_scale` | primary | 首个故障后进入不安全/不可达的子系统数（E 短路、氧耗尽、P 被弃置） | 子系统总数 | 无故障事件 → `None`（N/A） |
| `map09.hard_threshold_breaches` | guardrail | `1[water_E>4] + 1[oxygen_reserve<=0] + 1[INSUFFICIENT_TRANSMIT_POWER]` | episode | 每项每局最多计 1 |
| `map09.repair_actions` | diagnostic | 成功的封舱/抽水/修线/开氧/补氧动作数 | episode | 0 |
| `map09.repair_dependency_violations` | diagnostic | 因前置条件不足被拒的修复/开机/补氧/发报尝试数 | episode | 0 |

- **未通关仍有意义的连续主指标**：有。`stable_time_ratio=1/2` 精确表达“只活了 1 个 tick”，不依赖成功；`hard_threshold_breaches=1` 也是连续/计次指标。
- **三局 N/A 情况**：三局没有 N/A（`docs/v9/data-integrity.md` §4.2 也把 MAP-09 列在“无任何 N/A”名单）。`fault_propagation_scale=1` 有效。
- **成功局的 N/A**：本批启发式成功后 `fault_propagation_scale=None`（没有故障事件），投影为 N/A；这是指标卡的“无故障 → None”规则，语义正确。但它意味着**成功局只剩 `stable_time_ratio` 与 `repair_actions` 两条主/诊断指标**，`fault_propagation_scale` 在成功侧没有分母。若要跨策略比较传播规模，应把成功局单列，不要把它当成“缺失”。
- **区分度**：失败局（stable 0.5、breaches 1、repair 0）与成功局（stable 1.0、breaches 0、repair 6）明确可分；`skip_pump`（repair 4、stable 9/9）与完整启发式（repair 6、stable 11/11）在 `repair_actions` 上可分，在 `stable_time_ratio` 上都饱和为 1.0 → 对“是否保留抽水”这一构念，`stable_time_ratio` 无区分度，应看 `repair_actions`/`water_P`。记 **`LOW_DISCRIMINATION`（stable_time_ratio 在成功侧饱和）**。

## 7. 三次轨迹归因

三局的动作、结果、观察变化**完全相同**（除 run_id 与费用），因此逐局引用相同原文：

### R0 `V8-MAP-09-R0-20261017T081550Z-c6fa53e8`

- 决策 1：`{"target_id":"water_gauges","tool":"inspect"}` → `WATER:P=5,E=3`；观察变化 `{"oxygen_reserve":11,"tick":1,"water_E":4,"water_P":4}`。
- 决策 2：`{"target_id":"water_gauges","tool":"inspect"}` → `WATER:P=4,E=4`；观察变化 `{"oxygen_reserve":10,"terminal":true,"terminal_reason":"SHORT_CIRCUIT","tick":2,"water_E":5,"water_P":3}`。
- 终局：`bulkhead_state:"open"`、`repair_actions=0`、`stable_time_ratio={numerator:1, denominator:2}`。

**首次偏离合理策略的可观测事件**：决策 1 之后。模型已经看到 `water_E: 3→4`、`water_P: 5→4`，即“每 tick 有 1 单位水从 P 进入 E”；它手里还有一个决策。合理反应是“立刻封舱”。它选择了再读一次同一块表。注意：**在看到决策 1 的变化之前，模型没有任何公开依据知道 E=4 已经是临界值**；因此“决策 2 继续 inspect”是可归因于信息缺失的合理误判，而不是纯粹的粗心。

**失败链**：公开信息没有速率/阈值 → 决策 1 用掉唯一容错 tick → 决策 2 仍 inspect → 第 2 tick E=5 → `SHORT_CIRCUIT`。

**替代解释**：
- 预算不足：否（46 vs 12）。
- 接口误导：是首因（`isolate_compartment` 不可见）。
- 模型策略错误：是次因（决策 2 有 1 tick 的转向机会，且它已经观察到进水）。
- 环境规则缺陷：否，规则确定性、Oracle 与 fixture 自洽。

### R1 `V8-MAP-09-R1-20261017T081554Z-1debfaf3`

- 决策 1：`{"target_id":"water_gauges","tool":"inspect"}` → `WATER:P=5,E=3`；`{"oxygen_reserve":11,"tick":1,"water_E":4,"water_P":4}`。
- 决策 2：`{"target_id":"water_gauges","tool":"inspect"}` → `WATER:P=4,E=4`；`{"oxygen_reserve":10,"terminal":true,"terminal_reason":"SHORT_CIRCUIT","tick":2,"water_E":5,"water_P":3}`。
- 终局与 R0 相同；费用更低（0.00024876），因为输入更短。

**首次偏离**：决策 1 之后，与 R0 同一位置。**失败链**：同上。**替代解释**：同上。

### R2 `V8-MAP-09-R2-20261017T081606Z-8d27efe7`

- 决策 1：`{"target_id":"water_gauges","tool":"inspect"}` → `WATER:P=5,E=3`；`{"oxygen_reserve":11,"tick":1,"water_E":4,"water_P":4}`。
- 决策 2：`{"target_id":"water_gauges","tool":"inspect"}` → `WATER:P=4,E=4`；`{"oxygen_reserve":10,"terminal":true,"terminal_reason":"SHORT_CIRCUIT","tick":2,"water_E":5,"water_P":3}`。
- 终局与 R0/R1 相同。

**重复证据有限**：三局是同一 seed 的三次重复，动作序列逐字相同，n=3 **不能**区分“个体策略差异”与“固定公开信息陷阱”；它能说明的只有“该陷阱稳定复现”。真正的独立证据来自 20 个随机 seed（0/20 成功）与离线探针（封舱窗口），而不是这三次重复。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **B** 公开信息不足（速率、阈值、动作名均未公开） | C 接口误导（词表把 `bulkhead_E_P` 放在 operation 位，且无 `isolate_compartment`）；E 策略（决策 2 未转向） | 高 | 决策 1/2；`map09.py:66,82-84,267-281`；`_VOCABULARY["MAP-09"]` |
| R1 | **B** | C；E | 高 | 决策 1/2 |
| R2 | **B** | C；E | 高 | 决策 1/2 |

D（预算）不成立：46 vs 12。A（规则缺陷）不成立：阈值与 tick 顺序自洽，Oracle 成功。H（运行异常）不成立：无 provider 错误，费用正常。I（证据不足）成立：n=3 同 seed，只能作为重复证据。

## 9. 标签

- **`INTERFACE_BLOCKED`**：保命动作 `isolate_compartment` 不在公开词表；漏水速率 `1/tick` 与 `water_E>4` 短路阈值不在公开 prompt/Observation；随机基线 20/20 在 1–2 决策内 `SHORT_CIRCUIT`。公开信息不足以合法解题。
- **`CONSTRUCT_BYPASS`**：终局条件不包含 `water_P`，导致“封舱 + 完全不抽水”8 步成功（`skip_pump` 消融），设计声称的“电量刚好够两次抽水 + 发报”的核心张力不是必要条件。
- **`INCONCLUSIVE`（能力层面）**：三局在第 2 个决策终局，`repair_actions=0`，跨系统调度能力完全未被观察。

（不选 `BUDGET_BLOCKED`；不选 `RULE_DEFECT`：水力规则本身正确，缺的是公开信息与终局条件覆盖。）

## 10. 最小可证伪修复（无证据不修改）

**旧公开信息**：

1. `_VOCABULARY["MAP-09"]`：`interact(target_id, operation): E/bulkhead_E_P 配 arguments={"mode": preserve|sacrifice}；P/pump_once, E/restore_power_line, O/restart_oxygen, O/replenish_oxygen, C/send_distress_packet`。该行没有 `isolate_compartment`，且把 `bulkhead_E_P` 放在 operation 位置。
2. 公开 prompt 没有水力硬规则。

**证据与根因**：三局决策 2 的 `water_E: 4→5` 触发短路；`repair_actions=0` 说明封舱从未发生；源码 `map09.py:162-163` 只在 `operation=="isolate_compartment"` 时分派，`map09.py:177-181` 还要求 `target_id="bulkhead_E_P"` 且在节点 E；`map09.py:66,82-84,267-281` 定义速率与阈值。

**候选 A（首选：只补公开信息，不改任何阈值）**：

- 词表改为显式字段形式：
  `interact(target_id=bulkhead_E_P, operation=isolate_compartment, arguments={"mode": "preserve"|"sacrifice"})`；
  其余操作同样写成 `target_id=... operation=...`，消除 `E/bulkhead_E_P` 的歧义。
- 增加一条公开硬规则：
  > “E-P 舱壁打开时，每经过 1 tick，1 单位水从 P 进入 E；`water_E > 4` 立即短路失败。初始 `water_E=3`。封舱在当前 tick 结算前生效。”

预期：Agent 可以在决策 1 或 2 推出“必须现在封舱”，MAP-09 从“猜隐藏常量”变成“在公开时限下排序四条链”。

**候选 B（等价，数值化）**：在 Observation 中公开 `leak_rate_per_tick: 1` 与 `water_E_short_threshold: 4`（或 `water_E_safe_max: 4`），不加长句规则。信息量相同，模型更容易做算术。

**候选 C（不推荐，改规则）**：把初始 `water_E` 从 3 降到 1，或把漏速降到 0.5，以扩大容错窗口。这会改变 `rule_hash` 与所有旧 Trace，且削弱“硬时限”构念；必须先走 DCR，不能作为“修 prompt”的替代。

**终局条件的独立候选（与本条信息修复分开评估）**：若要恢复“抽水是必要步骤”的设计意图，可把 `water_P <= 1`（或“P 未被淹”）加入成功条件，或让 P→O 在 P 被淹时不可通行。该候选会改变规则与 Oracle，必须由主控统一 DCR；**本次不实施**。

**预期变化（仅 A/B）**：修复前 0/3、2 决策、`stable_time_ratio=0.5`；修复后预期模型至少能活过第 2 个 tick，`stable_time_ratio≈1.0` 或进入电量/供氧阶段。启发式已证明 10 步可解（skip_pump 8 步）。

**反例与回归风险**：
- 公开阈值后，模型可能直接背出“封舱→修线→开氧→补氧→发报”的固定串，把跨系统耦合降级为顺序记忆；若担心这一点，应把“资源分配”做成需要根据电池余量选择的决策（例如两个发报窗口），而不是藏起阈值。
- 改 `prompt_hash` 后旧 Trace 不可直接比较；需要新 run_id/账本。
- 候选 A 不改变 `rule_hash`，但改变 `prompt_hash`；V9 审计必须分别记录。

**若无需修改**：不成立——三局 + 20 seed 随机基线一致指向公开信息缺陷。

## 11. 基线与独立复算

来自 `runs/v9/baselines/MAP-09.json`：

| 策略 | 结果 | 决策 | 关键指标 |
|---|---|---|---|
| Oracle `preserve_and_pump` | `scenario_success` / `DISTRESS_PACKET_SENT` | 12 | ok=true |
| Oracle `sacrifice_P` | `scenario_success` / `DISTRESS_PACKET_SENT` | 8 | ok=true |
| `legal_random` × 20 | 0 成功，20/20 `SHORT_CIRCUIT` | 1–2（均值 1.8） | breaches 1，repair 0，stable 1/2 |
| `public_heuristic`（本批） | `scenario_success` / `DISTRESS_PACKET_SENT` | 10 | stable 11/11、breaches 0、repair 6、propagation `null` |
| 消融 `skip_pump` | `scenario_success` / `DISTRESS_PACKET_SENT` | 8 | stable 9/9、breaches 0、repair 4 |

> 注：`public_heuristic` 与 `skip_pump` 都使用运行时合法但**未公开**的 `isolate_compartment`；它们是规则可解性与旁路探针，不能作为“公开信息可解”的证据。

**独立复算 1（`stable_time_ratio`）**：三局只有 2 个已结算 tick。tick1 后 `water_E=4<=4` 且 `oxygen_reserve=11>0` → 安全；tick2 后 `water_E=5>4` → 不安全。`safe_ticks=1`，`valid_ticks=2`，故 1/2 = 0.5，与 judge 输出 `{"numerator":1,"denominator":2}` 一致。该复算只读 Trace 的 `delta`，不调用 extractor。

**独立复算 2（`hard_threshold_breaches`）**：三局 `water_E>4` 发生 1 次（tick2），`oxygen_reserve<=0` 未发生（最低 10），`INSUFFICIENT_TRANSMIT_POWER` 未发生（从未发报），故 1+0+0=1，与 judge 一致。

**独立复算 3（`fault_propagation_scale`）**：三局 `short_circuit=true`、`oxygen_depleted=false`、`p_sacrificed=false`，故 1；`transmit_power_failed=false`，不额外计数。与 judge 一致。

**区分度**：失败局 vs 成功局在 `stable_time_ratio`（0.5 vs 1.0）、`hard_threshold_breaches`（1 vs 0）、`repair_actions`（0 vs 6）上均可区分；但完整启发式与 `skip_pump` 都让 `stable_time_ratio` 饱和为 1.0，无法区分“是否执行了抽水”，需依赖 `repair_actions`。记 **`LOW_DISCRIMINATION`（仅成功侧的 stable_time_ratio）**。

## 12. V9 状态

**`BLOCKED`（P0）**。理由：保命动作名与硬时限规则都不在公开信息中，任何模型在第 2 个决策前都无法合法地知道“必须现在封舱”；三局 0/3 与随机 0/20 是同一缺陷的两份证据。修复公开信息（候选 A/B）后必须重新运行并重新归因；在此之前，MAP-09 的 0/3 不能解释为“跨系统调度能力不足”。
