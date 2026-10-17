# MAP-10｜极地｜简单｜最后一桶燃料

```yaml
map_id: MAP-10
world: polar
nominal_level: 简单
capability_primary: multi_purpose_resource_budgeting
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 0186aea149e03e93b50db10440d2735cf31e07b06050d4e4958d64761d8b57a0
source_design_hash: a33287e546ae085db6ff436b06f04366959a2c6f8fc9ec19905e4d0bd6b000b5
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“有限燃料的目标优先级分配”。燃料被拆成位置不同的三个用途：B 的基地油库维持远端基地供暖；随身燃料要送到 E 点燃发电机；E-W 雪地车捷径也从随身燃料扣款。基地供暖只能烧仍留在 B 的燃料，发电机和雪地车只能烧随身燃料；容量 5 刚好覆盖“捷径 2 + 发电机 3”。成功不是“尽快到 T”，而是决定带多少油、走长坡还是捷径、基地热量能维持到何时。

## 2. 真实规则字段

- 拓扑：`B-E` 步行 4、`E-T` 步行 3、`B-W` 步行 1、`W-T` 步行 1；`E-W` 雪地车 1 tick、耗随身燃料 2（仅此边可驾驶）。
- 初始：`seed=0, location=B, fuel_depot=12, carried_fuel=0, carry_capacity=5, base_temperature=5, heater_on=true, generator_online=false`。
- 账本：`fuel_depot + carried_fuel + fuel_spent = 12`；`load_fuel(q)` 只搬运不燃烧；`q<=5`。
- 供暖：每偶数 tick，若供暖开且基地库 ≥1，扣 1 并保持温度；否则关供暖、温度 −1。温度 `<=0` 立即 `BASE_FROZEN`。供暖不升温。
- 发电机：E，1 tick，烧随身 3；不足 3 时 1 tick 失败校验后 `GENERATOR_FUEL_SHORTAGE`。
- 发报：T，1 tick；发电机未启动 → `GRID_OFFLINE`；启动后只有最后一个 tick 热量结算后温度仍 >0 才算通信成功。
- 成功：`transmission_complete && base_temperature>0`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map10.key_task_fuel_efficiency` | primary | 完成的必需任务数（发电机+发报=2）/ 实际消耗燃料 | 任务/燃料 / 高 | 燃料消耗；0 耗 → N/A | 无终局 → CENSORED |
| `map10.minimum_task_guarantee` | primary | 发电机启动与发报是否都完成（0/1/2） | 个 / 高 | 2 | 无终局 → CENSORED |
| `map10.minimum_base_temperature` | guardrail | `min_t base_temperature_t` | 温度 / 高 | episode | 无读数 → UNAVAILABLE |
| `map10.base_frozen` | guardrail | `1[BASE_FROZEN]` | 0/1 / 低 | episode | 终局缺失 → CENSORED |
| `map10.fuel_consumed` | diagnostic | `12 − (fuel_depot + carried_fuel)` | 单位 / 低 | episode | 账本不平 → INVALID_TRACE |

## 4. 能力混淆分析

- 高燃料效率可能只因为“少做任务”；必须同时报 `minimum_task_guarantee`，分母固定为 2 个必需任务。
- 高完成率可能只因为“一直开着供暖”，不代表会分配燃料；必须报 `fuel_consumed`、剩余燃料与最低温度。
- 低分可能由偶数 tick 结算误解造成：tick 1 装载不烧燃料，tick 2 才第一次扣款；不能把动作数当燃烧次数。
- 雪地车快 2 tick 但多花 2 油、少烧 1 油；两条成功路线在“完成 tick / 剩余燃料 / 最低温度”上互不支配，不能只按时间排序。

## 5. 两条手算轨迹

**方案 A（长坡步行，10 tick，耗 8）**：B 装载 3（1）→B-E 步行 4（2–5）→E 启动发电机（6，耗随身 3）→E-T 步行 3（7–9）→发报（10）。偶数 tick 2/4/6/8/10 供暖各烧 1（共 5）；总耗 3+5=8；基地库余 4；随身 0；温度全程 5；完成 10。指标：效率 2/8=0.25；任务保障 2/2；最低温度 5；冻结 0；耗油 8。

**方案 B（雪地车捷径，8 tick，耗 9）**：B 装载 5（1）→B-W 步行 1（2）→W-E 驾驶 1（3，耗随身 2）→E 启动发电机（4，耗 3）→E-T 步行 3（5–7）→发报（8）。偶数 tick 2/4/6/8 供暖各烧 1（共 4）；总耗 2+3+4=9；基地库余 3；随身 0；温度 5；完成 8。指标：效率 2/9≈0.222；任务保障 2/2；最低温度 5；冻结 0；耗油 9。

## 6. 三个机制特有失败

1. **只装 4 就驾驶捷径**：B 装 4 → B-W → W-E 扣 2，到 E 只剩 2；启动发电机门槛 3 不足，1 tick 失败校验后 `GENERATOR_FUEL_SHORTAGE`。
2. **关供暖后仍走长坡**：发电机已启动，但基地温度在偶数 tick 递减，tick 10 终点检查降到 0，`BASE_FROZEN`；通信动作本身完成也不算成功。
3. **先装 5 再空等 16 tick**：基地库被供暖烧空，供暖关闭、温度下降；之后即使快速路线完成发报，仍在终点冻结。

## 7. 两个边界

- **随身燃料 3 vs 2**：到 E 时 `=3` 可启动发电机；`=2` 失败。必须用同一路线只改一次捷径/装载量验证。
- **温度 0 vs 1**：`base_temperature=1` 仍可继续；下一次偶数 tick 降到 0 即 `BASE_FROZEN`。通信成功检查在最后一个 tick 热量结算之后。

## 8. 信息泄漏负例

若 prompt 直接给“装 5 走捷径”或公开未来偶数 tick 的热量结算/最优路线，燃料分配被替代。V7 只允许公开当前燃料位置、温度、供暖状态、路线、发电机状态；不公开 Oracle 行动或未来结算。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有 `walk_keep_fuel`（10 tick，耗 8）与 `snowmobile_shortcut`（8 tick，耗 9）两条手写非支配成功；`failure_traces/cases.yaml` 有三条失败；`acceptance.md` 只完成纸面推演。**没有运行时或独立求解器**证明 8 tick 最优；只能证明两条路线可行且互不支配。

## 10. 与同世界另两图差异

**vs MAP-11**：MAP-11 的资源是补给 + 体温 + 队员生命窗，核心是空间搜索与带噪天气下的风险策略；MAP-10 的燃料是同一 12 单位池的分仓支出，没有随机风暴、搜索或救援窗口。MAP-10 的失败是发电机燃料不足/基地冻结，MAP-11 是冻伤/队员生命耗尽；两者的资源账本与不确定性来源不同。

**vs MAP-12**：MAP-12 是 30 天跨期库存与劳动槽排程，燃料要与温室、维修、研究竞争；MAP-10 是单期（最长 10 tick）的燃料分配，没有每日结算、食物或研究。MAP-10 的“偶数 tick 供暖”是单次热损失，MAP-12 的连续欠供天数是长期生存约束；不能把 MAP-10 的 10 tick 拉长成 30 天来冒充 MAP-12。

## 11. 可计算性来源

需要逐 tick 的 `fuel_depot`、`carried_fuel`、`base_temperature`、`heater_on`、`generator_online`、`location`、`terminal_reason`。账本恒等式用于校验 trace；`fuel_consumed` 由 12 − 终局库存计算，不由动作次数估算。

## 12. 难度定位与对照

D=(1,1,1,3,1,2)。单期资源取舍，不加入多日随机天气。预登记对照：**公开需求表 vs 自行从日志汇总**；不能修改总燃料。若需求表额外给最优装载量，标为信息可用性实验。

## 13. 未决

无规则冲突。运行时接入前需固定“偶数 tick 热量结算”与“发报最后 tick 后再检查温度”的顺序，并验证账本恒等式。
