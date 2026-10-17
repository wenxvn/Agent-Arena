# MAP-07 审计：逆流阀门（abyss / 简单）

## 0. 元数据

| 字段 | 值 |
|---|---|
| 地图 / 世界 / 难度 | MAP-07 / abyss / 简单 |
| condition | `default` |
| `rule_hash` | `1183d0dea109c7670eb69122eac7bafedf9a0ff3872feb5336d8266dfe336e88` |
| `scenario_hash` | `c18b0b93713e055a2f8bfc162c3befdef1a98de46a15f290767afe38bc2bc81f` |
| `prompt_hash` | `7a4bd1042bb5d5c83a333178af6213ac98e11e8c206c288a58296cca5102fac9` |
| 决策预算 | 30（`BUDGETS["简单"]`）；环境 `step_limit=160` |
| V8 三局 | 0/3 成功；R0/R1/R2 均为 `decision_budget_reached`，决策 30 / 30 / 30，非法 schema 0 |
| 费用（正式行） | 0.02222448 / 0.01893456 / 0.01385244 CNY |
| 证据包 | `runs/v9/evidence/MAP-07.json` |
| Trace 索引 | `docs/v9/run-index.csv` 第 20–22 行（trace sha256 `964bbf67…`、`1ca57794…`、`1c7e1a10…`） |
| 规则资料 | `docs/v8/maps/MAP-07-final.md`、`worlds/v4/MAP-07/{map_spec.yaml,evidence_or_rules.yaml,acceptance.md,oracle_trace.jsonl}` |
| 源码 | `src/agent_arena/worlds/scenario_v8/maps/map07.py` |
| 公开词表 | `src/agent_arena/v8/prompts.py::_VOCABULARY["MAP-07"]` |
| 基线 | `runs/v9/baselines/MAP-07.json` |

## 1. 能力构念

这张图想测的是：**Agent 能否在“动作即流水 tick”的耦合水路里，预判一组串接阀门的联合效果并排出正确开关次序**，而不是逐个开关的独立操作。

- 成功行为：让 A/B/C 在同一批流水结算中逐步降压，最终连续两个流水 tick 三者都 ≤2，且任何 tick 都不 >8。等价于先启泵、再按“下游优先”（v3→v2→v1）把水推向 D 并抽走。
- 明确反例：先开上游或只开 v4。v4 是 C→A 的单向回流，给 C 降压会把水送回 A；`FIXTURES["bypass_v4_backflow_overflows_A"]` 记录 tick3 A=9，直接 `COMPARTMENT_OVERFLOW_A`。
- 本图在简单/中等/困难递进中的位置（只写本图）：它是 abyss 唯一“无行走图、无隐藏故障、无资源稀缺”的纯因果排序题；难度来自同一 tick 内 v1→v2→v3→v4→泵 的固定结算次序，而不是信息或预算。

## 2. 机制与因果链

起始状态（`runs/v9/evidence/MAP-07.json` 初始 Observation 原文）：

```json
"water_levels": {"A": 6, "B": 2, "C": 4, "D": 0},
"valves": {"v1": false, "v2": false, "v3": false, "v4": false},
"pump_active": false, "low_water_streak": 0, "tick": 0,
"goal": "让 A/B/C 连续两个流水 tick 都不超过 2，且任一流水 tick 都不超过 8。"
```

因果链：

1. **起始**：超额水量 `Σ max(0, level-2)`（A/B/C）= 4+0+2 = **6**。
2. **必需观察**：`water_levels` 与 `pipe_diagram`（后者重复给出 v1=A→B2、v2=B→C2、v3=C→D2、v4=C→A1 的单向性）。
3. **关键决策**：每个 `interact`/`inspect`/`wait` 都推进 1 tick，并在 `_after_tick` 里按 v1→v2→v3→v4→泵 结算一次流水（`map07.py:201-246`）。因此“开阀”与“流水”是同一决策的两面。
4. **立即后果**：正确次序（下游先开）每次都能降低总超额；错误次序把水集中在尚未排出的舱。tick 内 A/B/C 任一 >8 立即 `COMPARTMENT_OVERFLOW_<舱>`。
5. **终局**：`low_water_streak >= 2` → `LOW_WATER_STABLE`。

- **可绕过核心机制的动作**：没有“成功旁路”。但有一条**失败旁路**：什么都不做永远不会失败——水位恒定在超额 6，低于 8；三局真实轨迹正是这样耗完 30 个决策。也就是说本图只有“自伤型失败”，没有时间压力或资源枯竭压力。
- **机制是否在三条真实轨迹中实际触发**：**没有**。三局 `interventions=0`、`illegal_valve_combo=0`、`overpressure_ticks=0`，`excess_water_integral` 恒为 180（30 tick × 6）。决策 1/3/5/11/15/21/25 的 `set_valve` 全部返回 `TARGET_NOT_VISIBLE`，阀门从未改变。
- **触发所需的最小动作数**：6（`start_pump` + v3 + v2 + v1 + 2×`wait`，见 Oracle `downstream_first`）；另一条 8 步路线 `upstream_staged` 合法但更慢。

## 3. 公开/隐藏信息矩阵

| 信息 | 模型是否可见 | 何时可见 | 是否足以合法解题 |
|---|---|---|---|
| `water_levels`（A/B/C/D） | 是，Observation 字段 | 每步 | 是，可直接算超额 |
| `valves` / `pump_active` / `pump_energy` | 是 | 每步 | 是 |
| `pipe_diagram`（含 v4 单向） | 是 | 初始即全量 | 是，能推出 v4 回流 |
| 成功条件（≤2 连续两 tick、≤8） | 是，`goal` 字符串 | 初始 | 是 |
| 每 tick 结算次序 v1→v2→v3→v4→泵 | **否**（只在源码/`docs/v8`） | 不可见 | 需要推断；`pipe_diagram` 只给拓扑与容量，不给次序 |
| `low_water_streak` | 是 | 每步 | 是（可判断是否已达成） |
| 控制台 `target_id` | **否**。公开词表写 `target_id=console`，运行时只接受 `control_panel` | 不可见 | **否**：按公开词表操作 100% 被拒 |
| `OVERFLOW_LIMIT=8` | 是（`goal` 明说“不超过 8”） | 初始 | 是 |
| Oracle 两条路线 | 否（`worlds/v4/MAP-07/oracle_trace.jsonl` 为裁判侧材料） | 不可见 | 不用于公开策略 |
| hidden `judge_state`（`decidable_valve_ops` 等） | 否 | 不可见 | 不用于公开策略 |

结论：**`target_id=console` 是公开词表与运行时不一致的硬冲突**。这不是“隐藏规则”，而是“公开信息写错”，属 C 类接口误导；模型没有任何合法途径从 Observation 得到 `control_panel`（`visible_edges` 为空，Observation 里没有可交互对象列表）。

## 4. 可解性与可观察性

- Oracle 用例 2 条，均通过：`downstream_first` 6 步、`upstream_staged` 8 步（`runs/v9/baselines/MAP-07.json` 的 `oracle` 段，`ok=true`，终态 `LOW_WATER_STABLE`）。
- **仅凭公开信息是否存在可执行策略：不存在可推导的策略**。原因不是规则难，而是公开词表给出的唯一控制台标识 `console` 在运行时返回 `TARGET_NOT_VISIBLE`（决策 1/3/5 原文见 §7）。在不使用源码信息的条件下，Agent 无法**推导**出 `control_panel` 这个字符串；唯一可能的路径是对同义词逐个枚举（console → control_panel → panel …），而公开文本已经明确断言 `console`，这会把枚举方向锁死。三局都没有尝试任何同义词，20 个随机 seed 也从未产生一次 `interventions`。
- 补充：**规则本身是可解的**。本批的 `Map07Heuristic` 使用运行时合法 `target_id=control_panel`，6 个决策成功（§11）。它证明的是“规则 + 正确接口名可解”，**不能**当作“公开信息可解”的证据。
- 标签依据：避免秒失败不需要隐藏真值（本图不会秒失败），但需要隐藏的接口字符串。按模板定义，公开信息不足以合法触发核心机制，记 `INTERFACE_BLOCKED`。

## 5. 预算可行性

| 项 | 数值 |
|---|---|
| Oracle 动作数 | 6（`downstream_first`）/ 8（`upstream_staged`） |
| 决策预算 | 30 |
| `legal_random` 20 seed | 成功 0/20；**20/20 `decision_budget_reached`**，决策均为 30；非法 schema 0；被拒动作 23–30 次/局（合计 524） |
| 公开启发式 | 6 决策，`LOW_WATER_STABLE`，invalid 0，rejected 0 |
| 三局 MiMo | 30/30/30 决策，均耗尽预算 |

判定：**不是“预算不够”，也不是“模型没做对机制”，而是“模型没有可用的合法控制台标识”**。Oracle 只需 6 步，预算 30 步是最小解的 5 倍；三局却在 30 步里一次都没能改变阀门。随机基线同样 0 次干预，说明这是结构性接口问题，不是单模型失误。

## 6. 指标

本图登记 5 条指标（`map07.py::metrics`）：

| 指标 | 类别 | 计算事件 | 分母 | 缺失/截尾 |
|---|---|---|---|---|
| `map07.correct_direction_rate` | primary | 成功改变阀门状态并触发随后流水 tick 的操作中，使总超额下降（或保持 0）的比例 | `decidable_valve_ops` | 分母 0 → N/A |
| `map07.excess_water_integral` | primary | 每个流水 tick 的 `Σ max(0, level-2)` 累加 | 有效流水 tick | 无事件 → 0 |
| `map07.illegal_valve_combo` | diagnostic | 一条命令带多个阀门字段的次数 | episode | 0 |
| `map07.interventions` | diagnostic | 成功开/关阀与启/停泵次数 | episode | 0 |
| `map07.overpressure_ticks` | guardrail | A/B/C 任一 >8 的流水 tick 数 | episode | 0 |

- **未通关仍有意义的连续主指标**：有。`excess_water_integral` 在 0 成功时仍报告 180，且分母非 0；它精确刻画“水位从未被改善”。
- **三局 N/A 情况**：`map07.correct_direction_rate` 三局全 N/A。原因是**真实分母为 0**（`decidable_valve_ops=0`，因为没有任何成功阀门操作），不是 `v8/metrics.py::_empty_status` 的投影口径问题。`docs/v9/data-integrity.md` §4.1 把 MAP-07 列入“预算耗尽导致整列 N/A”，此处应更正为“真实零分母”。
- **区分度**：启发式（0.667、积分 16、干预 4）与随机/三局（N/A、180、0）可以区分；但“随机与三局都是 0 干预”意味着该指标在本批只能区分“能不能操作控制台”，不能区分“阀门次序理解得对不对”。在没有修好接口前，`correct_direction_rate` 的构念效度为零。

## 7. 三次轨迹归因

### R0 `V8-MAP-07-R0-20261017T075714Z-beecf3f5`

- 决策 1：`{"arguments":{"open":true,"valve_id":"v1"},"operation":"set_valve","target_id":"console","tool":"interact"}` → `TARGET_NOT_VISIBLE`；观察变化仅 `{"tick": 1}`。
- 决策 2：`{"target_id":"pipe_diagram","tool":"inspect"}` → `PIPE_DIAGRAM:v1=A>B2;v2=B>C2;v3=C>D2;v4=C>A1`；`{"tick": 2}`。
- 决策 3：再次提交与决策 1 相同的 `console` 动作 → `TARGET_NOT_VISIBLE`；`{"tick": 3}`。
- 决策 7：`{"target_id":"console","tool":"inspect"}` → `TARGET_NOT_VISIBLE`；`{"tick": 7}`。
- 决策 8–10：连续 `wait`，水位保持不变。

**首次偏离合理策略的可观测事件**：决策 1。合理策略的第一步是确认“哪个对象是控制台”；公开词表已经断言是 `console`，而环境立即拒绝。此后模型没有把 `TARGET_NOT_VISIBLE` 当作“标识错误”去换名，而是把它当作“需要更多观察”，于是重复 `inspect`/`wait`。

**失败链**：公开词表 `console` → `TARGET_NOT_VISIBLE`（每次仍耗 1 tick）→ 模型在本局重复同一标识 9 次（决策 1/3/5/7/11/15/21/25/29）→ 水位不变（超额恒 6）→ 既无成功也无溢出 → 30 决策耗尽。

**替代解释**：
- 预算不足：否，6 步 vs 30 步。
- 模型策略错误：部分是，决策 8–30 的大量 `wait` 没有信息价值；但即使策略完美，只要坚持公开词表，也仍然无法干预。
- 接口误导：**是首因**。

### R1 `V8-MAP-07-R1-20261017T075858Z-6e19c745`

- 决策 1：`{"arguments":{"open":true,"valve_id":"v1"},"operation":"set_valve","target_id":"console","tool":"interact"}` → `TARGET_NOT_VISIBLE`；`{"tick": 1}`。
- 决策 2：`{"target_id":"pipe_diagram","tool":"inspect"}` → `PIPE_DIAGRAM:v1=A>B2;v2=B>C2;v3=C>D2;v4=C>A1`；`{"tick": 2}`。
- 决策 3：`{"target_id":"water_levels","tool":"inspect"}` → `WATER_LEVELS:A=6,B=2,C=4,D=0`；`{"tick": 3}`。
- 决策 4：再次提交与决策 1 相同的 `console` 动作 → `TARGET_NOT_VISIBLE`；`{"tick": 4}`。
- 决策 21：再次 `inspect(pipe_diagram)`，结果与决策 2 完全相同（无新信息）。

**首次偏离**：同样是决策 1。R1 比 R0 多读了一次 `water_levels`，但读数自始至终是 `A=6,B=2,C=4,D=0`，说明模型把“没有变化”误读成“还需要观察”。

**失败链**：与 R0 同构：错误标识 → 反复确认 → 30 tick 耗尽。**替代解释**：模型可能把 `TARGET_NOT_VISIBLE` 理解为“目标在当前地点不可见”，于是尝试 `wait` 或 `inspect` 寻找“控制台”，但地图没有行走图（`visible_edges: []`），这条解释也走不通。

### R2 `V8-MAP-07-R2-20261017T080115Z-043df7cf`

- 决策 1：`{"arguments":{"open":true,"valve_id":"v1"},"operation":"set_valve","target_id":"console","tool":"interact"}` → `TARGET_NOT_VISIBLE`；`{"tick": 1}`。
- 决策 2：`{"target_id":"pipe_diagram","tool":"inspect"}` → `PIPE_DIAGRAM:v1=A>B2;v2=B>C2;v3=C>D2;v4=C>A1`；`{"tick": 2}`。
- 决策 3：`{"target_id":"water_levels","tool":"inspect"}` → `WATER_LEVELS:A=6,B=2,C=4,D=0`；`{"tick": 3}`。
- 决策 4：`{"operation":"start_pump","target_id":"console","tool":"interact"}` → `TARGET_NOT_VISIBLE`；`{"tick": 4}`。
- 决策 17 之后基本是 `wait` / `inspect` 交替（决策 24 再读 `console` 仍被拒）；最终 `pump_active=false`、`valves` 全 false。

**首次偏离**：决策 1；R2 是唯一尝试过 `start_pump` 的一局（决策 4），但同样被目标标识挡住。这说明模型**理解**了需要启泵，只是无法把动作落到对象上——进一步支持“接口问题”而非“机制理解问题”。

**重复证据有限**：三局的动作序列高度同构（都以 `console` 开头，都在 30 步内反复 `inspect`/`wait`，都没有任何阀门操作），n=3 只能说明“同一接口缺陷稳定复现”，不能区分个体策略差异。

## 8. 失败分类

| 局 | 首因 | 次因 | 可信度 | 证据位置 |
|---|---|---|---|---|
| R0 | **C** schema/接口误导（`console` vs `control_panel`） | E 策略规划错误（把拒绝当“信息不足”，重复 9 次） | 高 | 决策 1/3/5/7/11/15/21/25/29 |
| R1 | **C** | E（决策 21 重复读同一张图） | 高 | 决策 1/4/21 |
| R2 | **C** | E（`start_pump` 仍用 `console`） | 高 | 决策 1/4 |

D（预算）不成立：Oracle 6 步 vs 预算 30。A（环境规则缺陷）不成立：规则确定性、Oracle 通过。B（公开信息不足）严格说也成立，但这里不是“少写了一条隐藏规则”，而是“公开信息写了一个错误值”，归 C 更准确。H（采样/运行异常）不成立：三局请求与响应正常，费用正常。

## 9. 标签

- **`INTERFACE_BLOCKED`**：公开词表 `target_id=console` 被运行时无条件拒绝（决策 1/3/5… 原文 `TARGET_NOT_VISIBLE`），且 Observation 不提供任何可交互对象标识；三局 `interventions=0`，核心机制从未被触发。
- **`INCONCLUSIVE`**：因为 `interventions=0` 与 `correct_direction_rate` 分母为 0，本图声称要测的“阀门次序预判”在本批**完全没有被测量**。

（不选 `BUDGET_BLOCKED`：预算是最小解的 5 倍；不选 `RULE_DEFECT`：规则与 Oracle 自洽。）

## 10. 最小可证伪修复（无证据不修改）

**旧公开信息**：`_VOCABULARY["MAP-07"]` 的 `interact(target_id=console, operation)`。

**证据与根因**：运行时 `map07.py::_control` 要求 `action.target_id == "control_panel"`，否则 `TARGET_NOT_VISIBLE`；三局全部撞在该判断上，`interventions=0`。

**候选 A（首选，只补公开信息）**：把词表改为
`interact(target_id=control_panel, operation): set_valve …；start_pump, stop_pump；predict_next_levels …`，
并在 Observation 中增加一个公开字段（如 `"console_id": "control_panel"`）以免未来再漂移。

**候选 B（结构性，仍不改规则）**：在 Observation 里发布 `interactables: ["control_panel"]`，所有地图统一用“当前可见对象列表”取代 prompt 里的硬编码 target 名。成本更高，但能一次性消除同类问题。

**预期变化**：`interventions` 应从 0 变为 ≥4，`correct_direction_rate` 从 N/A 变为可计算；模型有机会真正面对“下游优先”的排序难点。

**反例与回归风险**：
- 只改名字不会降低排序难度；错误的开阀次序仍会 `COMPARTMENT_OVERFLOW_*`。
- 若候选 B 泄露过多目标（例如直接列出所有阀门），可能把“发现控制台”这一步也消掉；本图的构念本来就不包含“找控制台”，所以风险可接受。
- 旧 Trace 的 `prompt_hash` 会变化，V9 不得把修复前后的成功率直接比较；需要新账本/新 run_id。

**若无需修改**：不适用——已有三局一致证据，接口必须修。

## 11. 基线与独立复算

来自 `runs/v9/baselines/MAP-07.json`：

| 策略 | 结果 | 决策 | 关键指标 |
|---|---|---|---|
| Oracle `downstream_first` | `scenario_success` / `LOW_WATER_STABLE` | 6 | ok=true |
| Oracle `upstream_staged` | `scenario_success` / `LOW_WATER_STABLE` | 8 | ok=true |
| `legal_random` × 20 | 0 成功，20/20 `decision_budget_reached` | 30 平均 | 干预 0，被拒 524 |
| `public_heuristic`（本批） | `scenario_success` / `LOW_WATER_STABLE` | 6 | `correct_direction_rate=2/3`、积分 16、干预 4、溢流 0 |
| 消融 | 未定义（本图没有可移除的公开机制子步骤） | — | — |

> 注：`public_heuristic` 使用运行时合法但**未公开**的 `control_panel`；它是规则可解性探针，不能作为“公开信息可解”的证据。

**独立复算 1（主指标）**：三局 30 个流水 tick 中阀门全闭、泵未启动，A/B/C 恒为 6/2/4，超额恒为 `(6-2)+(2-2)+(4-2)=6`，故 `excess_water_integral = 30×6 = 180`，与 judge 输出一致。该算法不调用 extractor，只读 Trace 的初始水位与动作序列。

**独立复算 2（启发式方向率）**：按 `map07.py:214-222` 手算 `downstream_first` 的三个可判定操作：v3 前超额 6 → 后 4（正确）；v2 前 4 → 后 4（平局，算错）；v1 前 4 → 后 2（正确），故 2/3，与 fixture `0.666667` 一致。

**区分度**：启发式与随机/三局可区分（0.667 vs N/A、16 vs 180）。但是随机与三局都无法产生任何干预，说明当前“区分”只反映接口可达性；在修复前记 **`LOW_DISCRIMINATION`**（对目标构念而言）。

## 12. V9 状态

**`BLOCKED`（P0）**。理由：三局 0 次阀门操作不是能力差异，而是公开词表把控制台标识写错；在该缺陷修复前，MAP-07 无法测量它声称要测的“阀门次序预判”，任何成功率解读都无效。
