# MAP-23｜丛林｜中等｜迷雾中的遗迹

```yaml
map_id: MAP-23
world: jungle
nominal_level: 中等
capability_primary: information_value_under_supply_budget
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 6553f77fa05248f995615ff1cd0dd47b5399d2ec02c59f6d6e8e68120aaec952
source_design_hash: ee791a8edff4f2ecb2e47b331fbaaa43ec9478287a11ad09a4b503fbfbeea8f9
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“信息值换算成补给账”。三个入口 X/Y/Z 等概率为真；三处侦察点各把候选从 3 缩到 1 或 2，但**走到侦察点本身要付路费**：H 的远眺信息量最高（1.58496 bits、单位补给效率 0.39624），N/R 各 0.91830 bits（效率 0.30610 / 0.22957）。起点 14 补给、A 处一次性补满。核心不是“侦察越多越好”，而是判断“这次侦察的 bits 值不值这段路 + 2 补给”，以及错了以后还够不够试下一个。

## 2. 真实规则字段

- 路网：`A-N-X/Y`（北线）、`A-R-Y/Z`（河线）、`A-H` 山脊（只能观测、不能步行到入口）；边双向。
- 边成本：`A-N=1, N-X=1, N-Y=2, A-R=2, R-Y=1, R-Z=2, A-H=2`。
- 入口调查成本：`X=3, Y=2, Z=3`；起始补给 14、上限 14；A 的补给箱每局一次，回到 A 后把补给补满到 14。
- 侦察：每站每局一次、固定 2 补给；错误调查扣完整成本并把该入口标为已排除。
- 信号表：N 石刻 → `{X,Y}` 或 `{Z}`；R 水纹 → `{X}` 或 `{Y,Z}`；H 远眺 → `{X}`/`{Y}`/`{Z}`。三变体等先验 1/3。
- 成功：调查到真入口，且扣费后**严格 >0**；恰好 0 也失败（`SUPPLY_MUST_REMAIN_POSITIVE`）。
- 失败：`SUPPLY_STRANDED`（没有任何可负担的推进/离开/补给动作）、补给归零。
- 动作：`move`、`scout`、`investigate`、`mark`、`resupply`；`mark` 只换候选记号，不验真假、不扣补给。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map23.clue_utilization` | primary | 线索缩减掉的候选数 / 该线索最多可缩减数（3→1 记 2） | 比例 / 高 | 可缩减候选数 2 | 未侦察 → 0（合法）；无候选状态 → N/A |
| `map23.cost_per_discovery` | primary | `supplies_spent / discoveries`；`supplies_spent = 14 − 最终剩余`（净消耗） | 补给/发现 / 低 | 发现数；0 → N/A | 0 发现 → N/A，不补 0 |
| `map23.repeated_invalid_exploration` | guardrail | 对**已排除**入口再次调查的次数 | 次 / 低 | episode | 0 合法 |
| `map23.ignored_counterevidence` | diagnostic | `1[最终调查入口已被已得线索排除]` | 0/1 / 低 | episode | 无线索 → 0（合法） |

实现状态：**未实现**（`implemented=False`）。`supplies_spent` 采用**净消耗**（起点 14 − 终点剩余），因此“回 A 补满”不会把之前的路费重复计入；若改用毛支出（Σ 每步 `supply_cost`），同一策略的岭线 X 变体会从 5 变成 11，报告中必须注明口径。

## 4. 能力混淆分析

- 高 `clue_utilization` 可能只因为“选了 H”：H 一次就把 3→1，但路费 6；必须与 `cost_per_discovery` 并列看性价比。
- 低 `cost_per_discovery` 可能只因为“运气好第一次就查到”：单变体净值不能排名，必须按三变体等权求期望。
- `repeated_invalid_exploration=0` 不代表没有浪费：F01/F02/F03 都在“已排除入口”之外做错误调查，仍然耗尽补给；该指标只抓“重复”这一种浪费。
- `ignored_counterevidence=1` 与“补给不够”是两种归因：F02 是**读对了唯一信号却用错**，不是信息不足。
- `mark` 不花钱也不验证，不能把“标记次数”当探索量；V7 不注册该指标。

## 5. 两条手算轨迹

**A. 先上山侦察（H，一次定位）**：`A→H`(2) + `scout H`(2) + `H→A`(2) = 6，回 A `resupply` 补满 14；按唯一信号走 `A→N→X`(2) 调查 X(3)，或 `A→N→Y`(3) 调查 Y(2)，或 `A→R→Z`(4) 调查 Z(3)。三变体剩余 `9/9/7`，平均 8.333；每次只调查 1 个入口。指标：`clue_utilization = 2/2 = 1.0`；`cost_per_discovery = (14−9)/1 = 5`（Y 变体 5、Z 变体 7）；重复无效探索 0；忽略反证 0。

**B. 低成本试探（不侦察）**：先 `A→N→X`(2) 调查 X(3)；若假，`X→N`(1) 再 `N→Y`(2) 调查 Y(2)；若仍假，`Y→N→R→A`(1+2) 补满，再 `A→R→Z`(4) 调查 Z(3)。三变体调查 1/2/3 个入口，剩余 `9/4/7`。指标：`clue_utilization = 0/2 = 0.0`（没有付费线索）；`cost_per_discovery = 5/10/7`（平均 7.33）；重复无效 0；忽略反证 0。

> A 与 B 的对比是本图核心：**多花 6 补给买 1.58 bits，把“平均 2 次调查”压到“1 次调查”**。A 的期望成本 5.67 vs B 的 7.33，但 A 依赖“H 信号唯一”这一结构；若 H 不存在，B 更稳。

## 6. 三个机制特有失败

1. **F01 明确支持 X 却改查 Z/Y**：真 X 变体在 R 读到 `UPSTREAM_SINK`（仅支持 X），仍去查 Z、再查 Y，错误调查累计耗尽补给，未到 X 即 `SUPPLY_STRANDED`。`ignored_counterevidence=1`。
2. **F02 唯一信号被误读**：H 给出 `RIDGE_NORTH_WHITE_MARK`（唯一 X），被当成 Z；错误调查后只剩 1 补给，回不了 R、也到不了任何未查入口 → `SUPPLY_STRANDED`。信息已足够，错误在解码。
3. **F03 先浪费补给箱再试错**：预先用掉 A 的补满机会，再按无侦察方案错查 X/Y，最后以 1 补给回 A、又走回 N 耗尽，漏掉真 Z。补给箱是**一次性**资源，不是每轮可刷。

## 7. 两个边界

- **余 4 调查 Z 剩 1 成功（B01）vs 余 3 扣到 0 失败（B02）**：成功要求严格 `>0`；`SUPPLY_MUST_REMAIN_POSITIVE` 在扣费后归零时触发，不是“负值才失败”。
- **三变体同步表**：从 Z 变 X 时 N/R/H 三处线索**全改**，任一变体切换至少同步改变两处；不存在“只有一处线索变”的变体。seed0 私有夹具为 Z，公共 Oracle 只给“河谷双涟漪 → 先查 Y 假 → 查 Z 成功剩 1”，不写变体号或未侦察站结果。

## 8. 信息泄漏负例

若 Observation 给出变体号、真入口、未侦察站的信号或“H 会告诉你 X”，信息价值题被替代。V7 只允许公开路网/成本、自己付过费的侦察信号、候选记号、补给余额与已排除入口；`hand_traces.json` 的变体枚举、`private_seed`、Oracle 只在离线侧。`mark` 也不得返回真假。

## 9. Oracle/求解状态

`planning/hand_traces.json` 精确枚举四条策略 × 三变体：岭线 9/9/7（均值 8.33）、河北 9/7/1（5.67）、北林 7/2/3（4.00）、低成本 9/4/7（6.67），全部成功；`failure_traces/cases.yaml` 有 F01–F03；专属审计器核对三处线索分区与变体同步表。**没有运行时、没有独立最优求解器、没有真实模型实验**；枚举证明四条策略可行，不证明它们最优。

## 10. 与同世界另两图差异

**vs MAP-22**：MAP-22 没有线索经济，核心是“记住走过的边”；MAP-23 的地图是**已知**的（路网与成本全公开），核心是“哪条线索值得买”。MAP-23 的失败是补给耗尽，MAP-22 的失败是回不到起点。

**vs MAP-24**：MAP-24 有地形突变，路网在局中改变；MAP-23 的路网静态，不确定性只在“哪个入口为真”。把 MAP-23 加突变会变成 MAP-24 的构念。

## 11. 可计算性来源

需要的字段：`location`、`supplies`、`scouted_sites` 与信号、`excluded_entrances`、`candidate_marks`、`investigations`（含结果）、`terminal_reason`。`clue_utilization` 由“侦察前候选数 − 侦察后候选数”除以 2；`cost_per_discovery` 由起终补给差 / 成功调查数；`repeated_invalid_exploration` 由 `investigate` 目标是否已在 `excluded` 集合；`ignored_counterevidence` 由最终调查目标是否被已得信号分区排除。全部可由公开账重算。

## 12. 难度定位与对照

D=(3,2,1,3,2,3)。相对 MAP-22 提升 **D↑（先侦察再调查的两阶段链）与 R↑（补给/路费/一次性缓存三重约束）**；E 仅到 1（无随机事件，变体固定等先验）。不会与 MAP-22 混淆：MAP-22 的指标是返程成功/路径差，MAP-23 是线索利用率/单位发现成本。

预登记对照：**三处侦察全可用 vs 仅 N/R（禁用 H）**。若禁用 H 后 `cost_per_discovery` 上升，说明构念依赖“高信息量但高路费”的取舍，而不是单纯多走几步。两组共享补给、入口成本、变体表与信号分区。

## 13. 未决

- `supplies_spent` 的净消耗 vs 毛支出口径未在 `map_spec` 冻结；本卡采用净消耗，运行时必须二选一并固定，否则 `cost_per_discovery` 会相差一倍以上。
- `repeated_invalid_exploration` 在 V4 三条失败轨迹中都为 0（它们是补给耗尽，不是重复排查）；需要一个专门用例（二次调查已排除入口）来证明该指标可达非零。
- `SUPPLY_STRANDED` 的判定依赖“所有动作都不可负担”，`mark` 零成本仍可执行但不推进；运行时需确认不会因此死循环。
- 无运行时、无真实模型结果；所有数值为纸面枚举值。状态 `human_approved`。
