# MAP-13｜金字塔｜简单｜四神之门

```yaml
map_id: MAP-13
world: pyramid
nominal_level: 简单
capability_primary: constraint_satisfaction
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 634b03e0783ac226188286af0de54e9c964c78ee8358dd2e38a7b65e2f9bc654
source_design_hash: 50fe696e371eb535676161cab4131e8cad0ded293941c8849609b54fd5e02817
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: human_approved
reviewed_at: 2026-10-17
reviewed_by: human
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“显式符号约束满足”。四符号 `日/眼/芦/甲` 各放入 N/E/S/W 一间外室；移动图是星形（四室只连 C），但碑文使用另一条**阅读序** `N→E→S→W`。方向钉是第五条消歧信息：没有它，镜像读序也会得到唯一排列，但符号会落入不同物理房间。错误开启三次即失败；前两次不反馈哪条线索冲突。核心不是空间导航，而是把“房间连通图”和“碑文位置序”分开，并保留已读/已记录的区别。

## 2. 真实规则字段

- 拓扑：C 连 N/E/S/W；四室外无直连；每条边 1 tick。
- 阅读序：`N→E→S→W`（方向钉在 C 亲自读取）。
- 四条房间约束：N `pos(日)∈{2,3}`；E `pos(眼)>pos(芦)`；S `abs(pos(甲)−pos(日))=1`；W `pos(芦)≠1`。
- 唯一解：`N=甲, E=日, S=芦, W=眼`；候选数 `24→12→6→4→1`。
- 动作：`move`、`read_inscription`、`record_constraint`（仅 C、仅已读）、`set_trial_layout`、`verify_layout`；移动 1 tick，其余各 1 tick。
- 错误上限：`incorrect_attempts>=3` 终止；前两次不提示冲突。
- 公开：tick、位置、邻居、已观察碑文 ID/文本、已记录 ID、当前试排、错误次数/剩余、门状态、终止原因。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map13.constraint_satisfaction_ratio` | primary | 最终布局满足的独立约束数 / 5（4 条房间约束 + 方向钉） | 比例 / 高 | 5 | 无终局 → CENSORED |
| `map13.correct_sequence` | primary | 最终四室符号是否等于唯一解（0/1） | 0/1 / 高 | episode | 无终局 → CENSORED |
| `map13.illegal_door_attempts` | guardrail | `verify_layout` 错误次数 | 次 / 低 | episode | 0 合法 |
| `map13.state_resets` | diagnostic | 错误开启导致的状态重置次数 | 次 / 低 | episode | 0 合法 |
| `map13.completion_ticks` | diagnostic | 成功终局 tick | tick / 低 | 成功局 | 失败 → N/A |

## 4. 能力混淆分析

- 高 `correct_sequence` 可能只靠 3 次枚举撞对；必须同时报错误尝试数与 `constraint_satisfaction_ratio`。
- 高约束满足率可能只因为“四条都读到了”，但记录/推理缺失；必须报 `recorded_clue_ids` 与验证前覆盖率。
- 低分可能由“把阅读序当移动连通序”造成，不是约束推理错；用错误试排的符号位置分布归因。
- “看过”不等于“记录过”：已读未记录的碑文不计入证据使用率；不能把观察次数当能力。

## 5. 两条手算轨迹

**约束传播路线（20 tick）**：C 读方向钉并记录（2）→C→N 读碑（4）→回 C 记录（6）→C→E 读碑（8）→回 C 记录（10）→C→S 读碑（12）→回 C 记录（14）→C→W 读碑（16）→回 C 记录（18）→`set_trial_layout(甲,日,芦,眼)`（19）→`verify_layout`（20，开门）。指标：约束满足 5/5；正确序列 1；错误 0；重置 0；完成 20。

**系统枚举路线（20 tick）**：C 读方向钉（2）→按 W/S/E/N 探索（4/6/8/10）→回 C 一次性登记方向与四条碑文（12–16）→枚举 24 排列（17–19）→设置唯一排布并验证（20）。指标：约束满足 5/5；正确序列 1；错误 0；完成 20。与路线 1 的访问顺序、记录策略不同，但证据覆盖率相同。

## 6. 三个机制特有失败

1. **忽略方向钉**：按镜像读序得到 `N=甲,W=日,S=芦,E=眼`；验证不通过，部分房间约束失败（约束满足 ≤3/5）。
2. **漏用 E 室“眼在芦右侧”**：剩下候选仍有 5 个，Agent 把第一个自洽排列当唯一解；错误开门 1 次，约束满足 4/5。
3. **漏读 W 室“芦不在首位”**：候选剩 4 个，试排让芦在首槽；验证失败，约束满足 4/5。

## 7. 两个边界

- **错 2 次后仍可成功**：前两次错误只返回“门未开 + 剩余容错”，不提示冲突；第 3 次错误才终止。必须用同一路线只改最后一次试排验证。
- **镜像映射**：方向钉反转后，顺时针 `N=甲,E=日,S=芦,W=眼` 与反向 `N=甲,W=日,S=芦,E=眼` 都各自唯一；方向钉是房间映射的必要信息，不是冗余谓词。

## 8. 信息泄漏负例

若 Observation 直接给 `target_layout`、唯一排列或“哪条线索冲突”，约束满足被替代。V7 只允许公开碑文文本、已记录 ID 与试排结果；`target_layout` 与 `constraint_audit.json` 只在离线裁判侧。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有两条 20 tick 手写成功（约束传播/系统枚举）；`failure_traces/cases.yaml` 有三条证据错误；`planning/constraint_audit.py` 枚举 24 排列，证明唯一解与逐条删约束必要性（2/5/2/4），输出 `constraint_audit.json`。**没有运行时**；审计只证明逻辑唯一性，不证明 Agent 可发现。

## 10. 与同世界另两图差异

**vs MAP-14**：MAP-14 的陈述有真假与说谎者，Agent 要在 9 种“锁型×诚实者”状态中找一致假设；MAP-13 的碑文全部为真、没有说谎者，核心是把显式约束传播到唯一排列。MAP-13 的失败是漏约束/镜像，MAP-14 的失败是误信反报/未识别矛盾；两者的信息可靠性不同。

**vs MAP-15**：MAP-15 的规则本身随 tick 奇偶变化，同一门在不同状态效果不同，核心是动态规则归纳与迁移；MAP-13 的约束静态、明确、无状态转换。MAP-13 只需一次约束求解，MAP-15 需要从训练样例迁移到未见组合；把 MAP-13 的门做成变色不会自动产生 MAP-15 的规则发现。

## 11. 可计算性来源

需要公开的 `observed_clue_ids_and_text`、`recorded_clue_ids`、`trial_layout`、`incorrect_attempts`、`terminal_reason` 与唯一解（离线裁判）。约束满足率用独立谓词逐条计算，不用 `trial_layout==target` 一刀切。

## 12. 难度定位与对照

D=(1,1,0,0,2,2)。显式静态规则，无说谎者或动态转换。预登记对照：**约束列表 vs 自然语言石碑**；同一事实不额外给答案。若约束列表额外给排列顺序，标为信息可用性实验。

## 13. 未决

无规则冲突。运行时接入前需固定“已读未记录不计入证据使用率”与“第 3 次错误立即失败”的结算顺序。
