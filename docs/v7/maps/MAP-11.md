# MAP-11｜极地｜中等｜失联的小队

```yaml
map_id: MAP-11
world: polar
nominal_level: 中等
capability_primary: risk_strategy
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 9fbaf264987d57bb388b00181ed1da96feb9bbf9d6dde45b6754d3f08cb08401
source_design_hash: 97bd1182126cecb7e5152eab0883d2bd52b30bb8fe08c0dd7d335c6d6cba4fae
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“有限信息下搜救路线与时机”。山口短路 `B-P-S` 更快，但两段都暴露在风道，每段基础 −1 体温，命中暴风再 −5；长安全路 `B-D-Q-S` 每段 3 tick、只 −1，但没有风暴抽签。侦察在 B 耗 2 tick，只返回噪声信号 `falling/rising`，不揭开本 seed 的逐段风暴。救到人后负重返程每段**多 1 tick**，且暴风同时作用于两人。队员生命计时 15 tick，救援完成前每 tick 递减。核心是“快但险”与“慢但稳”之间的风险策略，不是单次猜天气。

## 2. 真实规则字段

- 拓扑：短路 `B-P`、`P-S` 各 1 tick、补给 2/段；长路 `B-D`、`D-Q`、`Q-S` 各 3 tick、补给 1/段；两路只在 B/S 相接。
- 初始：`location=B`，基地补给 8，随身 0/8，Agent 体温 10，队员体温 10，队员生命 15，天气 `clear`。
- 负重返程：短路每段 2 tick，长路每段 4 tick；补给仍按原路段的每段费用。
- 冷暴露：短路每段先 −1；命中暴风再 −5（B-P 出发时队员不在场；P-S 与返程命中同时作用于在场者）。长路每段 −1，无风暴抽签。
- `rest`：B/D/Q，1 tick + 随身补给 1，当前在场者体温 +2（上限 10）；未获救队员不在场，不回血但生命计时继续。
- 侦察：B，2 tick，`P(rising|unstable)=0.8`、`P(rising|quiet)=0.2`；先验 0.5；rising 后下一段风暴概率 0.5，falling 后 0.2。
- 成功：Agent 与队员都回到 B，且两人体温始终 >0。失败：`BODY_HEAT_DEPLETED`、`TEAM_LIFE_EXPIRED`、`SUPPLY_SHORTAGE`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map11.rescue_count` | primary | 成功救回 B 的队员数 | 人 / 高 | 1 | 无终局 → CENSORED |
| `map11.resource_cost_per_rescue` | primary | 已耗补给 / 获救人数 | 补给/人 / 低 | 获救人数；0 → N/A | 无获救 → N/A |
| `map11.rescuer_hypothermia` | guardrail | `1[BODY_HEAT_DEPLETED]`（任一人） | 0/1 / 低 | episode | 终局缺失 → CENSORED |
| `map11.abandoned_reachable_targets` | diagnostic | 仍可救援却被放弃的人数 | 人 / 低 | 1 | 无放弃 → 0 |
| `map11.first_clue_delay` | diagnostic | 首次侦察结果 tick；未侦察 → N/A | tick / 低 | episode | 未侦察 → N/A |

## 4. 能力混淆分析

- 高救援率可能只因为“走长路”，不需要读侦察；必须报 `first_clue_delay` 与补给成本。
- 高效率可能只因为“少带补给、赌短路”，不代表风险策略好；必须报体温最低值与风暴命中数。
- 低分可能由“负重返程 +1 tick”被忽略造成，不是天气判断错；用返程 tick 与 `TEAM_LIFE_EXPIRED` 区分。
- 侦察不是保险：fixture 中 seed 8 是 falling 假阴性；必须报解析成功率与有限 seed 成功率，不能把一次侥幸当能力。

## 5. 两条手算轨迹

**快速短路，不侦察（seed 0，8 tick）**：B 装载 8（1）→B-P（2）→P-S（3）→救援（4，队员生命余 11）→S-P（5–6，负重 2 tick）→P-B（7–8，负重 2 tick）。四段均无暴风。Agent 体温 10−4=6；队员在 P-S −1、返程两段各 −1 → 7。指标：救援 1；补给 8；每次救援成本 8；冻伤 0；首次线索 N/A。

**侦察后 falling 分支（seed 0，10 tick）**：B 侦察 2 tick（tick2，falling，p=0.20）→装载 8（3）→B-P（4）→P-S（5）→救援（6，生命余 9）→返程两段（7–10）。四段无暴风。Agent 6；队员 7。指标：救援 1；补给 8；成本 8；首次线索延迟 2；冻伤 0。

**长安全路（seed 7，25 tick）**：B 装载 6（1）→侦察 2 tick（3，rising，p=0.50）→B-D（4–6）→D-Q（7–9）→Q-S（10–12）→救援（13，生命余 2）→返回 S-Q（14–17）、Q-D（18–21）、D-B（22–25）。Agent 10−6=4；队员返程三段各 −1 → 7。指标：救援 1；补给 6；成本 6；首次线索延迟 2；冻伤 0。

## 6. 三个机制特有失败

1. **两次暴风**：短路四段中两次及以上命中，基础 −4 加 −10，体温从 10 降到 0 以下，`BODY_HEAT_DEPLETED`。
2. **救援太晚**：走长路但先多次休息，到达 S 时队员生命已归零；`TEAM_LIFE_EXPIRED`，与冻伤不同。
3. **补给不足**：短路往返需 8，只带 7；在最后一段移动开始时 `SUPPLY_SHORTAGE`，不是体温失败。

## 7. 两个边界

- **救援开始时生命 2 vs 1**：规则在救援完成 tick 先递减再检查，剩 2 可完成救援（余 1），剩 1 在完成 tick 归零即失败。必须用同一路线只改一个等待动作验证。
- **短路补给 8 vs 7**：8 刚好覆盖四段（2×4）；7 在最后一段无法支付。长路补给 6 vs 5 同理。

## 8. 信息泄漏负例

若 Observation/prompt 公开本 seed 的逐段风暴序列、真实气象态 `quiet/unstable` 或“本次 rising 一定正确”，风险策略被替代。V7 只允许公开先验、噪声信号、已走过的当前天气与递推后验；seed 真值只在离线裁判侧。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有快速短路（seed0）、侦察 falling（seed0）、长安全路（seed7）三条手写计划；`failure_traces/cases.yaml` 有补给/冻伤/生命窗失败；`planning/` 无求解器。解析概率 `r(0.1)=94.77%`、`r(0.6)=17.92%`，未侦察先验 56.345%，自适应 89.70% 均由设计手算；**不是模型实验**。

## 10. 与同世界另两图差异

**vs MAP-10**：MAP-10 是单期燃料分仓，资源是同一 12 单位池，失败是发电机缺油/基地冻结；MAP-11 是空间搜索 + 带噪天气 + 队员生命窗，资源按路线段消耗，失败是冻伤/生命耗尽/补给不足。MAP-10 没有随机风暴或救援对象；把 MAP-10 的燃料减少不会产生 MAP-11 的风险策略。

**vs MAP-12**：MAP-12 是 30 天跨期库存与劳动槽排程，没有空间搜索或暴风抽签；MAP-11 是短时（≤25 tick）风险路线选择，核心是四次相关决策中的冻伤概率与救援窗口。MAP-12 的失败是连续欠供/研究不足，MAP-11 是体温/生命/补给；两者的时间尺度与状态变量不同。

## 11. 可计算性来源

需要逐 tick 的 `location`、`carried_supply`、`agent_heat`、`teammate_heat`、`teammate_life_remaining`、`teammate_rescued`、`current_storm`、`posterior_unstable_probability_belief`、`last_scout_signal`、`terminal_reason`。首次线索延迟由 `scout` 结果事件派生；成本由补给账本计算。

## 12. 难度定位与对照

D=(3,2,3,3,2,3)。相对 MAP-10 提升 V（隐藏气象态）、E（风暴抽签）与 B（多路线/侦察分支）。预登记对照：**可主动测向 vs 无测向**；同隐藏失联位置与同一 seed 分布。若测向组额外获得真实气象态，标为信息可用性实验。

## 13. 未决

公开 `posterior_unstable_probability_belief` 是地图计算值还是 Agent 可写字段需确认（`V7-DCR-005`）。本卡按“信息使用”定义主指标，不把后验计算本身当能力。
