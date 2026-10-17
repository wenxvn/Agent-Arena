# MAP-28｜古堡｜简单｜消失的王冠

```yaml
map_id: MAP-28
world: castle
nominal_level: 简单
capability_primary: evidence_timeline_reconstruction
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: d75b3643587b4301ff7f5f3873f8cf16d0e8a523498139521e5f49bdaa9e99f4
source_design_hash: cba4a5035a7a6fa9e866a416c73150be5f940334ca698decabdb47ff9fb21a2e
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“多来源交叉的证据时间线”。王冠失窃后，三名嫌疑人都在场；Agent 要提交**人物、进入 V 的门、进入分钟、离开分钟**四个字段。难点不是“找到线索”，而是每个字段都必须有**至少两种不同来源类别**支持，且最终断言全部正确；同类两份日志不能冒充独立证据。提交一次即结束，`CASE_REJECTED` 不告诉正确答案，也没有试错重试。

## 2. 真实规则字段

- 六室：`H—V—G—K—S—V`，另有 `A—G`；V 三个入口：`H-V`（宴会厅）、`G-V`（守卫室）、`S-V`（密道）。
- 真相（裁判侧）：Celine 21:06 从 `S-V` 进入，21:14 从 `S-V` 离开。
- 时间格式固定 `HH:MM`；`entry_time` 与 `exit_time` 是两个独立字段。
- 四类来源：仪器锁芯日志（V，21:06 K3 从 S 侧开启、21:14 S 侧退出；不识别人名）、物证脚印（S，C7 靴纹连续朝 V，回程窗口 21:13–21:15）、档案钥匙登记（A，K3 于 20:58 交给 Celine）、厨房目击（K，看到 S 门 21:05–21:07 进入、21:13–21:15 离开，但把人误认成 Basil）。
- 动作：`investigate(location)`、`record(evidence_id)`（只接受已观察 ID）、`submit(person, path, entry_time, exit_time)`。
- 提交检验：每个字段的引用必须来自笔记、必须真实支持该字段、每栏至少两种**不同类别**来源；不足或错误只返回 `CASE_REJECTED`。
- 失败：`CASE_REJECTED`；无全局倒计时，无试错重试。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map28.timeline_constraint_satisfaction` | primary | 同时“事实正确 + 双来源独立”的字段数 / 4 | 比例 / 高 | 4（人物/路径/进入/离开） | 未提交 → 0；无证据账 → UNAVAILABLE |
| `map28.key_evidence_coverage` | primary | 已记录的关键证据数 / 4 | 比例 / 高 | 4（K3 登记、K3 锁日志、C7 脚印、厨师证词） | 未调查 → 0（合法） |
| `map28.unsupported_accusations` | guardrail | `count(提交时任一字段无两类来源)` | 次 / 低 | episode | 0 合法；单次提交至多 1 |
| `map28.time_contradictions` | diagnostic | 被已记录证据**排除**的提交时间字段数 | 次 / 低 | episode | 0 合法 |

实现状态：**未实现**（`implemented=False`）。`timeline_constraint_satisfaction` 是**合取**指标：F03 事实全对但只有一类来源，四个字段都不满足，得 0/4——这正是本图与“猜中答案”的分界。

## 4. 能力混淆分析

- 高 `key_evidence_coverage` 不等于高满足率：F03 看了脚印（覆盖 1/4）并猜对全部事实，仍因来源单一失败。
- 高满足率要求“正确 + 独立”，不能只看提交字符串是否等于真值；否则会把“猜中”当能力。
- `unsupported_accusations` 只看**提交**，不看调查过程：调查得少但恰好双来源也可能 0 次；必须与覆盖率并列。
- `time_contradictions` 只抓“与已记录证据冲突”的分钟（如 21:15 落在 21:13–21:15 观测窗内但超出锁芯精确分钟），不抓“无证据支持的猜测”。
- 厨师证词是**有效来源**（路径/时间窗），但其人名猜测不能单独支持 Basil；把整条证词一票否决会低估它，把它当人名证据会高估。

## 5. 两条手算轨迹

**A. 先物证后证词（4/4）**：`H-V` 调查锁芯（记录锁日志）→`V-S` 调查脚印（记录 C7）→经 `K/G` 到 `A` 读 K3 登记（记录登记）→回 `K` 问厨师，听到 Basil 误认但不采信人名 →回 `H` 提交 `Celine / SECRET_S_V / 21:06 / 21:14`。指标：`timeline_constraint_satisfaction = 4/4 = 1.0`；`key_evidence_coverage = 4/4 = 1.0`；`unsupported_accusations = 0`；`time_contradictions = 0`。

**B. 先证词再核验（4/4）**：`H→V→G→K` 访谈并记录“Basil + S 门 + 时间窗”→`A` 读钥匙登记→`V` 核对 K3 与锁舌方向→`S` 看 C7 路线足迹→修正人名后回 `H` 提交同一真相。指标：满足 4/4；覆盖 4/4；不支持指控 0；时间矛盾 0。

> 两条轨迹调查顺序不同、最终引用集合相同；它们证明“先证词”也能成功，只要**物证推翻了人名**。这不是同一模板换序：B 的中间假设（Basil）被显式否定。

## 6. 三个机制特有失败

1. **F01 只信目击**：只询问厨师、记下证词，提交 Basil 作为人名；人名只有一类证词支持，其他字段也未双来源 → `CASE_REJECTED`。覆盖 1/4、满足 0/4、不支持指控 1。
2. **F02 把矛盾来源硬拼成指控**：读了 K3 登记、K3 锁日志、鞋印后仍提交 Basil；独立物证支持的是 Celine，无法构成 Basil 的双来源 → 拒绝。覆盖 4/4 但满足 0/4。
3. **F03 猜中真相但不交叉验证**：调查到 C7 脚印后猜对 `Celine / SECRET_S_V / 21:06 / 21:14`，但四栏都只引用 `physical_trace` 一类；事实全对仍拒绝。满足 0/4、覆盖 1/4。

## 7. 两个边界

- **同类两记录 ≠ 两类来源（B01）**：`instrument_log` 的进入与离开两份记录只算一类，不能满足“两类来源”；必须至少跨 `instrument_log / physical_trace / archive_registry / witness` 中的两类。
- **精确分钟 vs 观测窗（B02）**：21:06/21:14 精确提交；21:05 或 21:15 虽在证词/鞋印窗口内，也不是目标分钟，且相对锁芯记录构成 `time_contradictions`。

## 8. 信息泄漏负例

若 Observation/prompt 直接给 `private_truth_table.yaml`、真人名或“从 S 门进去”，证据推理被替代。V7 只允许公开房间连接、已访问来源显露的事实、Agent 自己的笔记与提交结果；未访问证据、真人名、下一步结果不得出现。`submit` 的拒绝也不得泄漏正确答案。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有两条手写成功（先物证/先证词），`planning/private_truth_table.yaml` 固定真值与证据蕴含，`failure_traces/cases.yaml` 有 F01–F03 与 B01–B06；离线审计核对四类来源的独立性。**没有运行时、没有真实模型实验**；手算只证明两条调查顺序可行，不证明唯一。

## 10. 与同世界另两图差异

**vs MAP-29**：MAP-29 的证词**不可靠且有植入矛盾**，核心是识别矛盾与问询；MAP-28 只有一条错误人名，且可用档案/物证直接推翻。MAP-28 的提交是“四字段双来源”，MAP-29 是“矛盾检测率 + 证据支持比”。

**vs MAP-30**：MAP-30 有长间隔召回、多事件案卷与审慎指控；MAP-28 是单案、短证据链、无记忆间隔。MAP-28 的失败是来源不足，MAP-30 的失败常是召回失败或错误指控。

## 11. 可计算性来源

需要的字段：`visited_locations`、`observed_evidence_ids`、`recorded_evidence`（含来源类别）、`submit` 的四个字段与引用列表、`terminal_reason`。满足率按“字段值 == 真值 且 引用类别数 ≥ 2”逐字段判定；覆盖率按 4 个关键证据 ID 是否已记录；不支持指控按提交时任一字段类别数 < 2；时间矛盾按提交分钟是否被已记录证据排除。真值只在离线裁判侧。

## 12. 难度定位与对照

D=(2,2,0,0,2,2)。本世界基线：短证据链 + 双来源独立性；无隐藏事件、无资源耦合。V=2（真相隐藏）、M=2（跨房间记录）。

预登记对照：**显式“每栏需两类来源”提示 vs 只给提交格式**。若提示组满足率显著更高，说明构念测“来源独立性”而非“猜真相”；两组共享证据、真值与提交接口。另需 **可试错 vs 单次提交** 对照（若未来加入重试，必须标为不同实验）。

## 13. 未决

- `map28.unsupported_accusations` 的公式写“without two sources”，但未说明是“任一字段不足”还是“全部字段不足”；本卡按“任一字段不足即计 1 次”定义，需在运行时冻结。
- `time_contradictions` 需要“被已记录证据排除”的判定表；若 Agent 未记录锁芯日志，21:15 是否算矛盾取决于证词窗口（21:13–21:15 含端点），边界需明确定义。
- 无运行时、无真实模型结果；所有数值为纸面调查账。状态 `human_approved`。
