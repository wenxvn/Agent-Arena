# MAP-12｜极地｜困难｜极夜三十天

```yaml
map_id: MAP-12
world: polar
nominal_level: 困难
capability_primary: cross_cycle_management
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 8a83689858bfd57a5a00da8c7733fcd678e1d2f9fa29aeaa9461bb36a6081483
source_design_hash: e4cfff1ad7bd9882c1d69292700249205275009c260c4d5980bae050666f5764
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“长期资源可持续规划”。30 天里，燃料先保每日供暖，再负担温室连续供能；食物收成必须沿 `G→E→H` 逐段运回；零件要提前从 S 经 G 运到 E，赶上每 7 天的控制器磨损；实验室要连续做满四轮三日研究。每天只有 2 个劳动动作槽，维修、转运、研究直接争同一份日历。短期省燃料可能让温室断供、研究串清零；多种粮可能挤占维修/研究。成功不是“熬过 30 天”，而是存活且研究 ≥12。

## 2. 真实规则字段

- 拓扑：`H-E-G-S-L` 主链 + `H-S`、`G-L` 支线；物资沿相邻边逐段转运，每动作最多搬零件 2 或食物 5。
- 初始：`day=0, fuel_E=40, food_H=30, food_G=0, food_E=0, parts_S=8, parts_G=0, parts_E=0`。
- 每日：日号 7/14/21/28 控制器磨损，G/L 断电；该日修复必须在 G/L 工作前执行，耗 1 槽、parts_E=2，修复后本日恢复。无维修则温室进度清零、研究日不计。
- 动作（每天 0–2）：`set_heating`、`start_greenhouse_power`、`plant_batch`、`research`、`repair_controller`、`transfer`。
- 日末：供暖开且燃料 ≥1 → 烧 1；否则记 heat-shortage day。温室开且控制器在线 → 烧 1，并为已种批次累计 powered day；第 3 个连续 powered day 收 5 食物到 G 并关温室。H 每日配给 1 食物；H=0 → food-shortage day。连续两天同类欠供即失败。
- 研究：控制器在线的 L，连续三个日结算都 research → +3 分并清零串；漏一天/断电清零。
- 成功：`day=30 && research_points>=12 && 两类欠供连续天数<2`。失败：`HEAT_SHORTAGE_STREAK`、`FOOD_SHORTAGE_STREAK`、`RESEARCH_TARGET_MISSED`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map12.survival_days` | primary | 满足供热与口粮约束的生存天数 / 30 | 天 / 高 | 30 | 无终局 → CENSORED |
| `map12.minimum_safety_margin` | primary | `min_t(fuel_E_t−1, food_H_t−1)` | 库存单位 / 高 | 每日结算点 | 无逐日账 → UNAVAILABLE |
| `map12.heating_outage_days` | guardrail | 供热欠供天数 | 天 / 低 | 30 | 0 合法 |
| `map12.plan_breach_days` | diagnostic | 未按计划完成关键动作的天数（维修/研究/转运） | 天 / 低 | 30 | 0 合法 |
| `map12.fuel_consumed` | diagnostic | `40 − fuel_E_30` | 单位 / 低 | episode | 账本不平 → INVALID_TRACE |

安全库存取“1 天燃料 + 1 天口粮”作为最低保障；`minimum_safety_margin` 同时报告 fuel/food 两个分量，不合成加权分。

## 4. 能力混淆分析

- 高生存天数可能只因为“一直开供暖”，不代表会排研究/维修；必须同时报研究积分与 `plan_breach_days`。
- 高研究积分可能来自“多做研究、少运粮”，但可能在第 20 天后断粮；必须报最低安全裕量与欠供天数。
- 低分可能由“日结算顺序”误解造成（先研究还是先维修），不是长期规划差；用 `plan_breach_days` 与控制器状态区分。
- 方案 A 留 7 燃料/5 食物，方案 B 留 4 燃料/10 食物；两者都成功但安全垫不同，不能只按通关率排序。

## 5. 两条手算轨迹

**方案 A（研究优先，30 天）**：day1 启动温室+种第一批；day1–3 连续供能，day3 收 5 食物；day2–13 连续 12 个研究日，day4/7/10/13 各结算 3 分（day7 维修排在研究前）；零件按 day2/3、day4/5、day11/12、day25/26 的 S-G-E 两段准备；day7/14/21/28 各维修一次；day6 G→E、day8 E→H 运粮。燃料：供暖 30 + 温室 3 = 33，E 余 7；食物：30+5−30=5。指标：生存 30/30；最低裕量 `min(fuel 6, food 4)=4`；供热欠供 0；计划违约 0；耗油 33。

**方案 B（粮食安全垫，30 天）**：第一批 day1–3；第二批 day4 重启、day6 收成；day5/6 与 day7/8 分两批 G-E-H 运回；研究改排 day10–21，day12/15/18/21 各 3 分；零件 day2/3、day8/9、day15/16、day22/23 到 E；day7/14/21/28 维修。燃料：供暖 30 + 温室 6 = 36，E 余 4；食物：30+10−30=10。指标：生存 30/30；最低裕量 `min(fuel 3, food 9)=3`；供热欠供 0；计划违约 0；耗油 36。

## 6. 三个机制特有失败

1. **连续两天关供暖**：即使燃料箱有余量，也连续记 heat-shortage day，day2 失败；供暖开关本身是日程决策，不是燃料耗尽。
2. **把 H 的食物转空**：day1–15 每天从 H 向 S 转 1 份，再照常日配；H 在 day15 归零，day16/17 连续无口粮，day17 失败。
3. **研究串断裂**：控制器可用、维修也做了，但只在两日短串做研究、隔日停工；没有一串达到 3 天，day30 积分 0，`RESEARCH_TARGET_MISSED`。

## 7. 两个边界

- **连续欠供 1 vs 2 天**：欠供 1 天只记一次，次日恢复即可；连续第 2 天失败。必须用同一日历只改一天供暖/配给验证。
- **研究 12 vs 11 分**：12 分成功；11 分即使活到 day30 也 `RESEARCH_TARGET_MISSED`。零件同理：4 次维修需 8 件，7 件会在 day28 无法修复。

## 8. 信息泄漏负例

若 prompt 直接给“30 天最优日历”或未来磨损/收成结算表，长期规划被替代。V7 只允许公开当前日、库存、控制器状态、连续欠供天数与劳力槽；Oracle 日历与规划搜索前沿只在离线裁判侧。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有 `research_priority` 与粮食安全垫两套 30 日手算账；`planning/policy_search.py` 与 `planner_search.json` 给出有界可行日历（`map_spec.planner_path`）。**没有运行时回放**；搜索只证明存在可行日历，不证明 Agent 可发现或最优。

## 10. 与同世界另两图差异

**vs MAP-10**：MAP-10 是 10 tick 内的单期燃料分仓，决策是“带多少油、走长坡还是捷径”；MAP-12 是 30 天跨期库存与劳动槽排程，燃料还要与温室、维修、研究竞争，并叠加连续欠供与研究连续性。MAP-10 的失败是发电机缺油/基地冻结，MAP-12 是连续欠供/研究不足；把 MAP-10 的时长拉长不会产生 MAP-12 的跨期约束。

**vs MAP-11**：MAP-11 是短时空间搜索与带噪天气下的风险策略，资源按路线段消耗；MAP-12 没有空间移动、风暴抽签或救援窗口，核心是每日两槽的长期排程与库存安全垫。MAP-11 的失败是体温/生命/补给，MAP-12 是欠供/研究；两者的时间尺度与状态变量不同。

## 11. 可计算性来源

需要逐日 `fuel_E`、`food_H/G/E`、`parts_S/G/E`、`heater_on`、`controller_online`、`greenhouse_powered_streak`、`research_streak`、`research_points`、`consecutive_heat_shortage_days`、`consecutive_food_shortage_days`、`labor_slots_remaining`。`minimum_safety_margin` 需要逐日结算快照；若运行时只给终局，返回 UNAVAILABLE。

## 12. 难度定位与对照

D=(1,3,3,3,3,3)。相对 MAP-11 提升 D（跨期依赖）、M（30 天记忆）与 R（燃料/食物/零件共享日历）。预登记对照：**每日反馈规划 vs 一次性静态计划**；同天气序列（本图固定 seed0，无随机）。若静态计划组额外获得未来磨损表，标为信息可用性实验。

## 13. 未决

日结算顺序未在 spec 固定（`V7-DCR-007`）；长期指标对“动作→资源→欠供→日推进”的顺序敏感。运行时接入前必须先冻结顺序并加回归测试。
